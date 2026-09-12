# Backend — Lynx

Python + FastAPI. Motor de simulacion multiagente sobre un grafo de OSMnx de la
Zona Metropolitana de Monterrey.

## Estructura

```
app/
  main.py            FastAPI app + CORS + routers
  config.py           Variables de entorno (.env)
  api/routes/          Endpoints HTTP (simulation, orders, audit, stats, auth)
  agents/              Agentes: generador de ordenes, trafico, repartidor, novato
  engine/              Reloj virtual, carga del grafo (OSMnx), reglas de trafico MTY, routing (A*)
  decision/            Formula de Score, batching (OR-Tools VRPTW), umbral dinamico, Q-Learning
  db/                  Conexion a Tiger Data (Postgres/TimescaleDB), modelos, queries
  services/            Integracion con Gemini (auditoria de decisiones)
  schemas/             Modelos Pydantic de request/response
tests/                Pytest — ver "Tests" abajo
```

### El algoritmo de 3 capas (routing / batching / decision)

- **Routing** (`engine/routing.py`): A* sobre el grafo real de OSMnx con
  heuristica de distancia great-circle, matriz de tiempos NxN
  (`get_travel_time_matrix`, input de la capa de batching) y simulacion de
  cierre de calle (`apply_road_closure`/`clear_road_closure`/`simulate_random_closure`).
  `engine/traffic_rules.py` sigue siendo quien decide la congestion sintetica
  por hora del dia y avenida real — routing.py no la calcula, solo la usa via
  el atributo `travel_time` que ya trae el grafo.
- **Batching** (`decision/vrptw_solver.py` + `decision/batching.py`): dado el
  punto de partida del repartidor y sus ordenes pendientes, resuelve con
  OR-Tools (`ortools.constraint_solver.routing`) en que orden conviene
  visitar los pickups/deliveries respetando precedencia. `batching.plan_batch`
  compara el total de hacerlas juntas contra hacerlas una por una; se usa hoy
  solo como dato informativo en el log en vivo (`order_generated` con
  "Batching tip: ..."), porque `PendingOrdersPanel.tsx` no tiene todavia una
  accion de "aceptar batch" — cada orden se sigue decidiendo individualmente.
- **Decision** (`decision/scoring.py` + `decision/policy.py`): el Score
  (`Tarifa - Gasolina - Tiempo`) es la formula ya establecida y **no se
  toco** — sigue siendo la misma que `calculate_score()` en `db/schema.sql`
  para que las vistas en vivo del dashboard no se desincronicen. Lo que si es
  nuevo es `policy.should_accept`: en vez del corte estatico Score > 0, el
  umbral baja si el repartidor va atrasado en su ritmo de pedidos aceptados
  (ver docstring de `policy.py` para por que NO se porto el ajuste por
  "tiempo restante de turno" del prototipo original de este algoritmo — el
  `VirtualClock` de este backend corre en loop, sin fin conocido de antemano).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env         # completar DATABASE_URL y GEMINI_API_KEY
uvicorn app.main:app --reload
```

`ortools` (batching) esta pinneado a `9.9.3963` a proposito en
`requirements.txt` — versiones `>=9.10` piden `protobuf>=6.33` y
`numpy>=2.0`, lo cual choca con `osmnx==1.9.4` (`numpy<1.27`) y
`google-generativeai==0.8.3` (`protobuf<6`) que ya estaban en el proyecto.

## Tests

```bash
pip install -r requirements.txt   # pytest ya esta incluido
pytest -v
```

Los tests de `engine/routing.py`, `decision/batching.py` y
`agents/delivery_agent.py` (marcados `@pytest.mark.network` en
`tests/conftest.py`) descargan un grafo real chico (600m alrededor del
centro configurado en `.env`) la primera vez — necesitan internet una sola
vez, osmnx cachea despues. `decision/vrptw_solver.py` y `decision/policy.py`
se prueban con datos sinteticos, sin red.

No hay credenciales de Tiger Data en este entorno de desarrollo, asi que los
tests no ejercitan los endpoints HTTP completos (`api/routes/simulation.py`
escribe a la base de datos vía `Depends(get_session)`) — prueban la logica
de cada capa por separado. Antes de integrar con una base real, vale la pena
un smoke test manual de `/simulation/start` -> `/state` -> `/decide` ->
`/god-mode` contra una base de verdad.

## Pendiente

Ver la lista completa (incluye frontend) en el mensaje de la sesion que
integro el algoritmo de 3 capas a esta rama. Lo especifico de backend:

- `api/routes/orders.py` (`/orders/evaluate`) sigue siendo un stub que solo
  hace echo del payload — la evaluacion real vive inline en
  `api/routes/simulation.py::_tick`.
- `api/routes/audit.py` (`/audit/decision`) no llama a
  `services/gemini_service.py` todavia, y `db/models.py::DecisionAudit` (para
  cachear la explicacion) no se usa. Requiere `GEMINI_API_KEY` en `.env`.
- `/stats/scoreboard` sigue siendo un stub (`{"inteligente": {}, "novato": {}}`)
  — no existe todavia un segundo agente "novato" corriendo en paralelo sobre
  el mismo stream de ordenes para comparar.
- El repartidor no tiene una posicion que avance continuamente por su ruta:
  `DeliveryAgent.position` se actualiza recien al ACEPTAR una orden (salta al
  dropoff), no mientras la esta cursando. Si se agrega un WebSocket/stream de
  posicion en vivo para el mapa, esto hay que resolverlo primero.
- Si un cierre de calle deja un pickup/dropoff totalmente inalcanzable,
  `engine.routing.shortest_route` puede lanzar `networkx.NetworkXNoPath` sin
  que nada la capture en `simulation.py` — hoy es un caso de borde poco
  probable (grafo real bien conectado) pero no esta manejado explicitamente.
