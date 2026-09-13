# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Nova** (originally scaffolded as "Lynx"; renamed mid-project — see the
naming note below) — a multi-agent delivery-platform simulation set in the
Monterrey metro area (ZMM), maximizing net earnings per shift using a real
OpenStreetMap road graph with time-of-day traffic. Two independent apps in
one repo: `backend/` (FastAPI simulation engine + API) and `frontend/`
(React dashboard). No shared package/build tooling between them — each has
its own README, `.env`, and dependency file. The product name appears as
`app = FastAPI(title="Nova")` in `backend/app/main.py` and as the
`<title>`/header wordmark in the frontend (`App.tsx`, `index.html`,
`package.json`'s `name`) — **keep all of these in sync if it's ever renamed
again.**

The backend orchestration is no longer a stub: `/simulation/*` runs a real,
continuously-ticking simulation (world clock + traffic + two competing
agents), and it's what backs the live dashboard and profile stats end to
end. See "Architecture" below for the current state of each layer — a lot
of this changed since the project's initial scaffold, so don't assume an
older mental model of "routes are stubs, nothing writes to the DB" still
holds.

## Commands

### Backend (`backend/`)

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env                                 # fill DATABASE_URL (Tiger Data) + GEMINI_API_KEY
uvicorn app.main:app --reload                         # dev server, http://localhost:8000
python -m app.db.init_db                              # create tables + apply Timescale DDL (idempotent, safe to rerun)
python -m app.db.seed_dummy                           # optional: seed a year of demo trip history (see backend/README.md)
```

`ortools` (used by `decision/batching.py`, `vrptw_solver.py` and
`lp_shift_optimizer.py`) is pinned to `9.9.3963` on purpose — newer versions
pull in a `protobuf`/`numpy` combo that conflicts with `osmnx`/
`google-generativeai`. Don't bump it casually.

```bash
pytest -v   # real test suite now — see backend/tests/
```

Tests marked `@pytest.mark.network` in `tests/conftest.py` (routing,
batching, delivery agent) download a small real graph (600m around the
configured center) on first run — needs internet once, OSMnx caches after.
`vrptw_solver.py`, `policy.py` and `lp_shift_optimizer.py` are tested with
synthetic data, no network. No tests hit Tiger Data directly (no DB
fixtures yet) — the full HTTP flow was validated manually against a real
Tiger Cloud instance instead.

### Frontend (`frontend/`)

```bash
npm install
cp .env.example .env      # VITE_API_URL, defaults to http://localhost:8000
npm run dev                # Vite dev server, http://localhost:5173 (or next free port)
npm run build               # tsc -b && vite build
npx tsc -b --noEmit          # type-check only, fastest correctness check after an edit
npm run test                 # vitest run — real test suite (i18n keys, geo/stopLabel/zoneGroups helpers, useDraggableWidget)
```

`npm run lint` still fails — there is no `eslint.config.js` in `frontend/`
even though `eslint` is a listed dependency (ESLint 9 needs the new flat
config format). Don't assume lint works until that config is added.

## Architecture

### Backend: layered, and the orchestration IS wired up

`backend/app/` is organized by responsibility, and understanding a feature
means reading across these layers:

- `engine/` — stateless simulation primitives: `virtual_clock.py` (a world
  clock that runs continuously from process start, independent of any
  single shift — see "The world clock" below), `graph_loader.py` + `pois.py`
  (OSMnx road graph and restaurant POIs for the ZMM, fetched live from
  OpenStreetMap and cached in-memory — first call needs network),
  `traffic_rules.py` (hardcoded congestion rules for 9 real MTY avenues by
  hour of day — no manual "god mode" override anymore, see below),
  `routing.py` (A* with a great-circle heuristic, `position_along_route` for
  continuous courier movement, road-closure primitives), `zones.py`
  (neighborhood grouping used by the frontend's order list and, eventually,
  Q-learning state), `benchmark.py` (headless full-shift runner used by
  `/simulation/benchmark`).
- `agents/` — `DeliveryAgent` (routes + evaluates orders via
  `decision/scoring.py`), `NoviceAgent` (accepts everything, baseline for
  comparison — runs as a real second agent in parallel, not just a UI
  label), `TrafficAgent` (ticks traffic weights off the virtual clock),
  `order_generator.py` (Poisson process over *simulated* elapsed minutes,
  higher during `PEAK_HOURS` — independent of how often the frontend polls).
- `decision/` — `scoring.py` has the Score formula as the single Python
  source of truth (`OrderEvaluation.score` property) — **this formula is
  frozen and hasn't changed**. `policy.py` is what actually decides
  accept/reject in the live loop: **not** "Score > 0" (that was tried and
  measured indistinguishable from the novice baseline — see
  `backend/README.md`) but a reservation-wage rule (net MXN/hour vs
  `RESERVATION_RATE_MXN_PER_HOUR`, relaxed if the courier is behind pace).
  `vrptw_solver.py` (OR-Tools VRPTW — pickup/dropoff ordering for 1-2 active
  orders) + `batching.py` (uses it for both the informational "batching tip"
  log line and, live, the 2-order backpack merge — see below).
  `lp_shift_optimizer.py` is a **separate, offline** MILP tool (OR-Tools)
  that solves "given the whole stream of offers in a window, which subset
  and order maximizes net earnings" with full look-ahead — it is NOT wired
  into the live per-request decision loop; it's run via
  `scripts/run_lp_shift_simulation.py` to benchmark how close the live
  greedy policy gets to the theoretical optimum. `q_learning.py` is still an
  unintegrated generic Q-learning skeleton (predictive repositioning) — the
  one big backend TODO that remains.
- `db/` — see **Database** below.
- `api/routes/` — `simulation.py` (~1200 lines: the real orchestration —
  order generation, pending-offer re-evaluation, accept/reject, the 2-order
  backpack merge, courier movement, `/benchmark`), `session_state.py` +
  `session_store.py` (splits shift state into a serializable `SessionState`
  — pending orders, active deliveries, event log — vs. an unserialized
  runtime, the OSMnx graph + agents, rehydrated per worker; backed by
  `InMemorySessionStore` by default or `RedisSessionStore` if `REDIS_URL` is
  set, so multiple `uvicorn --workers N` processes see the same shift),
  `orders.py` (debug-only endpoints — generate/evaluate one order without a
  running session; the real flow never goes through here), `stats.py`,
  `audit.py`, `auth.py`. **`auth.py` is fully wired** (real bcrypt hashing,
  real DB reads/writes, includes a `PATCH /auth/profile` for changing
  vehicle type). All of these are live against a real Tiger Data instance,
  not stubs.
- `services/gemini_service.py` — builds a prompt from an `OrderEvaluation`
  and calls Gemini for a natural-language audit explanation; needs
  `GEMINI_API_KEY`. Cached in `decision_audits` so only the first request per
  order pays the 3-15s Gemini latency.

**"God mode" was removed on purpose** — there is no manual traffic-override
endpoint or preset anymore (see `tests/test_god_mode_removed.py`). Don't
reintroduce `GOD_MODE_PRESETS` from an old mental model of `traffic_rules.py`;
the 9 avenues still get real hour-of-day congestion, just without a manual
"force rush hour" switch. Road-closure primitives
(`apply_road_closure`/`clear_road_closure`/`simulate_random_closure` in
`routing.py`) still exist but aren't triggered anywhere in the live loop
today — only exercised by tests and surfaced as an error case in
`orders.py`.

**The two agents run in parallel for real.** `/simulation/start` creates
**two** `simulation_runs` rows sharing a `session_id`: the user's turn
(`agent_type="inteligente"`, human-in-the-loop unless `autonomous: true`)
and a mirror turn (`agent_type="novato"`, accepts every offer instantly).
Both actually route over the graph and move, so the comparison measures
decision quality, not luck — this is what `/stats/live`'s summary cards and
`/stats/scoreboard`'s `savings` come from.

**The world clock always runs.** `engine/virtual_clock.py::world_clock` is
global, starts with the process, and never stops — it doesn't wait for
"Start Shift". It anchors to real server-start wall-clock time and runs
`TIME_ACCELERATION`x faster (default 30x: one simulated hour per 2 real
minutes). A courier's shift just attaches to whatever simulated time the
world already has. Consequence: restarting the backend resets the anchor to
"now" (still an open TODO — see `backend/README.md` § Pendiente).

**Backpack of 2 orders (live).** `settings.max_active_deliveries` (default
2): with one order in progress, a new offer is evaluated as a candidate to
*merge* into that same delivery (cheap geographic-corridor check before
pickup, real VRPTW marginal-cost comparison after) rather than scored on its
own. `SimulationState.at_capacity` tells the frontend to disable "Accept"
when full. See `backend/README.md` for the exact mechanics — it's the most
recently-added piece of the live loop and easy to have a stale mental model
of.

### Database: Tiger Data (Postgres + TimescaleDB), two-file schema

The schema is split across two files that must be applied together, in order
(`python -m app.db.init_db` does both):

1. `app/db/models.py` — SQLAlchemy models for everything ordinary Postgres
   DDL can express: `User`, `SimulationRun`, `Order`, `TripRecord`,
   `DecisionAudit`, `AgentQValue`. Every column with a default sets **both**
   `default=` (Python-side, for the ORM) **and** `server_default=` (Postgres-side)
   — this matters because Tiger Cloud's own SQL editor / any raw-SQL insert
   bypasses the ORM entirely, so a Python-only default silently breaks those.
2. `app/db/schema.sql` — everything SQLAlchemy can't express: `CREATE EXTENSION
   timescaledb`, `create_hypertable('trip_records', 'created_at')`, the
   `trip_records_daily` continuous aggregate (feeds `/stats/history/{period}`),
   a compression policy, and `ALTER TABLE ... SET DEFAULT` migrations for
   columns added to tables that already existed in a live instance (SQLAlchemy's
   `create_all` never alters existing tables).

Only `trip_records` is a hypertable — it's the one genuinely high-frequency,
append-mostly time series (one row per accept/reject decision). Everything
else is a normal table; `agent_q_values` in particular is UPSERT-heavy, which
is the wrong access pattern for a hypertable.

**The Score formula lives in two places on purpose**, and they must be kept in
sync if the constants ever change:
- Python: `decision/scoring.py` (`OrderEvaluation.score`), used by the
  simulation logic.
- SQL: `calculate_score()` / `calculate_gas_cost()` / `calculate_time_cost()`
  functions in `schema.sql`, used by the **live, non-materialized** views
  (`live_trip_scores`, etc.) — `GET /stats/live` no longer reads
  `live_dashboard_summary` directly, though; it now aggregates `trip_records`
  itself via `repository.get_session_scoreboard`/`get_latest_session_id`,
  scoped to the most recent `session_id` that has data for *both* agents (so
  the dashboard doesn't show zeros while a fresh shift's first offer is
  still being processed). `trip_records_daily` (the continuous aggregate) is
  still the historical/long-range half, feeding `/stats/history/{period}`.

Formula: `Score = Tarifa - (Distancia * Costo_Gasolina) - (Tiempo * Costo_Tiempo)`,
gasolina $0.80 MXN/km (moto) or $2.00 MXN/km (auto), tiempo $1.50 MXN/min.
`TripRecord.vehicle` is denormalized from `SimulationRun.vehicle` (itself
copied from `User.vehicle_type` at run start, frozen so a later vehicle change
doesn't retroactively change past turns' costs) — analytics queries filter/
group by `agent_type`/`vehicle` constantly and shouldn't need a join for it.

`TripRecord.net_earnings_delta` is this row's own contribution (score if
accepted, else 0), **not** a running cumulative total — storing a cumulative
value per row would make any `SUM()` in the continuous aggregate wrong (it'd
sum the same growing number repeatedly). The live cumulative total for an
in-progress turn is meant to be tracked in-memory during the run; the final
total is cached once in `SimulationRun.final_net_earnings`.

`SimulationRun.session_id` pairs two runs (one `inteligente`, one `novato`)
that consumed the same order stream, so the scoreboard/`"ahorrado"` savings
stats can compare the two agents against the same conditions instead of two
unrelated random turns — see the example query in `schema.sql`.
`gasSaved`/`timeSaved` in `/stats/history/{period}` are **derived**, not
columns — novato minus inteligente for that day — and `gasSaved` is in MXN
of gas not spent (the frontend labels it that way now; it was mislabeled as
liters at one point but that's been fixed).

### Frontend: gated single-page app, design system in Tailwind tokens

`App.tsx` is the root gate: no `useAppStore().user` → renders `LoginPage`
only. Once logged in, it renders a **global header** (virtual clock, net
earnings, backpack indicator, the shift start/end button, nav, language
toggle, logout) that's shared across all three views — not a per-page
`ControlPanel` — plus a pill nav (Simulación / Dashboard / Perfil) over one
of `pages/{SimulationPage,DashboardPage,ProfilePage}.tsx`. `user` and
`language` are the slices of `state/store.ts` (zustand) persisted to
`localStorage` (`partialize` in the `persist` middleware config) —
everything else (`simulation`, `selectedOrderId`) resets on refresh by
design.

**Everything is live now — nothing is left in mock/placeholder state**
except two fully-built components that no page mounts yet:
`ScoreboardModal.tsx` (would consume `GET /stats/scoreboard`) and
`AuditDecisionButton.tsx`/`AuditExplanationCard.tsx` (would consume
`POST /audit/decision`). There's also no UI entry point yet for the
backend's autonomous mode (`autonomous: true` on `/simulation/start`) or for
`/simulation/benchmark`.

- `LoginPage` → `services/api.ts` `authApi` → real backend auth, real DB rows.
- `DashboardPage` → polls `GET /stats/live` every 4s (current/last-shift
  summary per agent + recent trips) and `GET /stats/history/{period}` (the
  historical earnings trend chart + totals) — this is also where the
  earnings chart and time-period filter live now; they used to be under
  Profile but moved here because they're shift/business stats, not
  per-courier ones.
- `SimulationPage` → `MapView` (real animated courier marker, on-demand
  route preview with a looping "ghost" vehicle, camera auto-framing) plus
  two draggable/closable floating panels: `OrdersWidget` (pending offers
  grouped by zone, each one showing **both agents' verdict on the same
  order side by side** before the courier decides; selecting one swaps to
  `OrderDetailCard` for the accept/reject/preview-route detail view) and
  `LiveLog`. `WidgetControls` (show/hide/reset those panels) is the one
  control still specific to this page rather than the global header.
- `ProfilePage` → `ProfileEdit` only now (vehicle type, which determines gas
  cost/km for *new* shifts — past `TripRecord`s stay frozen to whatever
  vehicle was active then). No earnings chart here anymore (see
  `DashboardPage` above).

**Design system** — established through iteration this session, keep new UI
consistent with it rather than reaching for defaults:
- Color tokens in `tailwind.config.js`: `paper` (bg), `ink` (text), `plum`
  (primary accent), `blush` (secondary accent), `dust` (surfaces/borders),
  `charcoal` (secondary text). Don't use raw Tailwind grays/blues — everything
  should route through these.
- Custom easing tokens (`ease-out`, `ease-inout`, `ease-drawer`, `ease-back`)
  and keyframe animations (`fade-up`, `fade-in`, `pop-in`, `pulse-ring`, `bob`)
  are also in `tailwind.config.js`, sourced from specific curves/durations
  (not invented ad hoc) — see the reasoning comments on `VehicleMarker.tsx`
  (renamed from `DeliveryMarker.tsx`) for how a "should this animate" /
  purpose / tool / easing decision was made for the live-indicator pulses.
  Never use `transition-all`; use Tailwind's
  scoped `transition` (or `transition-colors`) so the property list stays
  explicit.
- `MapView.tsx` applies a CSS filter duotone to the raw OpenStreetMap raster
  tiles (`[&_.maplibregl-canvas]:...`) rather than swapping tile providers,
  to keep the map inside the same light palette without needing a token-gated
  vector style.
- A `.paper-grain` fixed overlay (defined in `src/styles/index.css`) gives the
  whole app a subtle paper texture; it's deliberately `pointer-events-none`
  and low-opacity.
- **Bilingual ES/EN**: `i18n/translations.ts` (`es`/`en` objects, keyed by
  string literal) + `useTranslation()`. Default is `es`. Every new
  user-facing string needs a key in *both* objects —
  `i18n/translations.test.ts` checks the two stay in sync, so a forgotten
  translation fails `npm run test`, not just at runtime.
- Floating panels over the map (`OrdersWidget`, `LiveLog`, the widget-controls
  panel) share a common `DraggableWidget` wrapper: draggable via
  `transform: translate3d` (never `top`/`left`, to avoid layout thrash per
  frame), position remembered per-widget in `localStorage`.

## Environment / external dependencies

- **Tiger Data (Postgres + TimescaleDB)**: `backend/.env` → `DATABASE_URL`.
  Already provisioned for this project; `python -m app.db.init_db` is
  idempotent, safe to rerun after any `db/models.py` or `db/schema.sql` change.
- **Gemini**: `backend/.env` → `GEMINI_API_KEY`, required for
  `services/gemini_service.py` (decision audit explanations).
- **OpenStreetMap**: `engine/graph_loader.py` and `engine/pois.py` fetch the
  ZMM road graph and restaurant POIs live via OSMnx/Overpass on first use and
  cache in-memory — needs network access, no API key.
- CORS in `main.py` allows `settings.frontend_origin` plus any
  `http://(localhost|127.0.0.1):<port>` via regex, since Vite's port shifts
  when 5173 is taken and the browser treats `localhost`/`127.0.0.1` as
  different origins.
