# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Lynx** — a multi-agent delivery-platform simulation set in the Monterrey
metro area (ZMM), maximizing net earnings per shift using a real OpenStreetMap
road graph with time-of-day traffic. Two independent apps in one repo:
`backend/` (FastAPI simulation engine + API) and `frontend/` (React
dashboard). No shared package/build tooling between them — each has its own
README, `.env`, and dependency file. The product name appears as `app =
FastAPI(title="Lynx")` in `backend/app/main.py` and as the `<title>`/login
wordmark in the frontend — keep both in sync if it's ever renamed again.

## Commands

### Backend (`backend/`)

```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env                                 # fill DATABASE_URL (Tiger Data) + GEMINI_API_KEY
uvicorn app.main:app --reload                         # dev server, http://localhost:8000
python -m app.db.init_db                              # create tables + apply Timescale DDL (idempotent, safe to rerun)
```

No test suite exists yet (`backend/tests/` has only an empty `__init__.py`, no pytest config).

### Frontend (`frontend/`)

```bash
npm install
cp .env.example .env      # VITE_API_URL, defaults to http://localhost:8000
npm run dev                # Vite dev server, http://localhost:5173 (or next free port)
npm run build               # tsc -b && vite build
npx tsc -b --noEmit          # type-check only, fastest correctness check after an edit
```

`npm run lint` currently fails — there is no `eslint.config.js` in `frontend/`
even though `eslint` is a listed dependency (ESLint 9 needs the new flat
config format). Don't assume lint works until that config is added.

## Architecture

### Backend: layered, orchestration not wired yet

`backend/app/` is organized by responsibility, and understanding a feature
means reading across these layers:

- `engine/` — stateless simulation primitives: `virtual_clock.py` (compresses
  an 8h shift into a few real minutes), `graph_loader.py` + `pois.py` (OSMnx
  road graph and restaurant POIs for the ZMM, fetched live from OpenStreetMap
  and cached in-memory — first call needs network), `traffic_rules.py`
  (hardcoded congestion rules for 9 real MTY avenues + `GOD_MODE_PRESETS`),
  `routing.py`.
- `agents/` — `DeliveryAgent` (routes + evaluates orders via `decision/scoring.py`),
  `NoviceAgent` (accepts everything, baseline for comparison), `TrafficAgent`
  (ticks traffic weights off the virtual clock), `order_generator.py`
  (probabilistic order creation, higher during `PEAK_HOURS`).
- `decision/` — `scoring.py` has the Score formula as the single Python source
  of truth (`OrderEvaluation.score` property); `batching.py` and
  `q_learning.py` are scaffolded but not integrated into any route yet.
- `db/` — see **Database** below.
- `api/routes/` — `simulation.py`, `orders.py`, `stats.py`, `audit.py`, `auth.py`.
  **`auth.py` is fully wired** (real bcrypt hashing, real DB reads/writes).
  The rest are still mostly stubs: `simulation.py`'s `_simulation_state` is a
  bare in-memory dict, not backed by an actual running `VirtualClock` +
  `TrafficAgent` + `DeliveryAgent` loop, and nothing currently writes into
  `trip_records`. This is the biggest gap: the live dashboard and profile
  stats have real plumbing but nothing populates them yet outside manual
  test inserts.
- `services/gemini_service.py` — builds a prompt from an `OrderEvaluation`
  and calls Gemini for a natural-language audit explanation; needs
  `GEMINI_API_KEY`.

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
  (`live_trip_scores`, `live_dashboard_summary`, `live_run_earnings`) that
  back `GET /stats/live`. These views recompute on every query against
  whatever is newest in `trip_records` — they are the "instant dashboard"
  half of the Tiger Data story, while `trip_records_daily` (the continuous
  aggregate) is the historical/long-range half.

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

### Frontend: gated single-page app, design system in Tailwind tokens

`App.tsx` is the root gate: no `useAppStore().user` → renders `LoginPage`
only. Once logged in, it shows a pill nav (Simulación / Dashboard / Perfil)
over one of `pages/{SimulationPage,DashboardPage,ProfilePage}.tsx`. `user` is
the only slice of `state/store.ts` (zustand) persisted to `localStorage`
(`partialize` in the `persist` middleware config) — everything else
(`simulation`, `activeOrders`, `godModePreset`) resets on refresh by design.

**What's live vs. mock right now:**
- `LoginPage` → `services/api.ts` `authApi` → real backend auth, real DB rows.
- `DashboardPage` → polls `GET /stats/live` every 4s → real DB views, but
  will render empty until something actually inserts into `trip_records`
  (see the backend orchestration gap above).
- `SimulationPage` (`ControlPanel`, `GodModeButtons`, `MapView`) → purely
  local zustand state; `simulationApi`/`ordersApi` calls exist in
  `services/api.ts` but nothing on `SimulationPage` calls them yet.
- `ProfileStats` → `SAMPLE_DATA` is hardcoded inline (clearly marked with a
  TODO) specifically so the chart/stat-card design has something to render;
  swap for `statsApi.getHistory(period)` when there's real trip history.
- `ScoreboardModal` and `AuditDecisionButton`/`AuditExplanationCard` are
  fully built components that no page currently imports/renders — they're
  waiting on the simulation orchestration gap too.

**Design system** — established through iteration this session, keep new UI
consistent with it rather than reaching for defaults:
- Color tokens in `tailwind.config.js`: `paper` (bg), `ink` (text), `plum`
  (primary accent), `blush` (secondary accent), `dust` (surfaces/borders),
  `charcoal` (secondary text). Don't use raw Tailwind grays/blues — everything
  should route through these.
- Custom easing tokens (`ease-out`, `ease-inout`, `ease-drawer`, `ease-back`)
  and keyframe animations (`fade-up`, `fade-in`, `pop-in`, `pulse-ring`, `bob`)
  are also in `tailwind.config.js`, sourced from specific curves/durations
  (not invented ad hoc) — see the reasoning comments on `DeliveryMarker.tsx`
  for how a "should this animate" / purpose / tool / easing decision was made
  for the live-indicator pulses. Never use `transition-all`; use Tailwind's
  scoped `transition` (or `transition-colors`) so the property list stays
  explicit.
- `MapView.tsx` applies a CSS filter duotone to the raw OpenStreetMap raster
  tiles (`[&_.maplibregl-canvas]:...`) rather than swapping tile providers,
  to keep the map inside the same light palette without needing a token-gated
  vector style.
- A `.paper-grain` fixed overlay (defined in `src/styles/index.css`) gives the
  whole app a subtle paper texture; it's deliberately `pointer-events-none`
  and low-opacity.

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
  `http://localhost:<port>` via regex, since Vite's port shifts when 5173 is
  taken.
