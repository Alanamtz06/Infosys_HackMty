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
  engine/              Reloj del mundo, carga del grafo (OSMnx), reglas de trafico MTY, routing (A*)
  decision/            Formula de Score, batching (OR-Tools VRPTW), umbral dinamico, Q-Learning
  db/                  Conexion a Tiger Data (Postgres/TimescaleDB), modelos, queries, seed de demo
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

## El reloj del mundo (siempre corriendo)

`engine/virtual_clock.py::world_clock` es un reloj **global** que arranca con
el proceso y nunca se detiene: no depende de que alguien apriete "Start
Shift". Cuando un repartidor entra a un turno, se engancha a la hora que el
mundo ya traia. El ancla es la hora real del arranque del servidor (si prende
a las 14:37, el mundo simulado empieza a las 14:37) y de ahi corre
`TIME_ACCELERATION` veces mas rapido.

Con el default de **30x**: una hora simulada cada 2 minutos reales, un dia
completo en ~48 minutos reales, y una entrega de 15 minutos toma 30 segundos
reales — se ve avanzar al repartidor en el mapa. Se probo con 120x y era
demasiado: una entrega se resolvia en 7 segundos y las ofertas cambiaban
antes de poder leerlas.

Dos consecuencias de diseño que importan:

- **La demanda va con el reloj, no con el poll.** `agents/order_generator.py`
  usa un proceso de Poisson sobre los minutos SIMULADOS transcurridos entre
  ticks (`orders_to_generate`), no una moneda por request. Si el frontend
  sondeara cada 5s en vez de cada 2s, la cantidad de ordenes por hora
  simulada no cambiaria.
- **El log en vivo va en hora simulada.** `_log()` sella cada evento con
  `world_clock.iso_timestamp()`, que devuelve un ISO **sin zona horaria a
  proposito**: el frontend hace `new Date(ts).toLocaleTimeString()` y
  JavaScript interpreta un ISO sin offset como hora local, asi que muestra
  exactamente la hora del mundo simulado. Con un sufijo "Z" el navegador la
  convertiria a su zona y el log mostraria una hora que no es la de la
  simulacion.

Ojo con el costo de CPU: el reloj corre mientras la request trabaja, asi que
un tick lento se "come" minutos simulados. Por eso
`routing.get_travel_time_matrix` hace un Dijkstra por origen en vez de N*N
busquedas A* (11x11 bajo de decenas de segundos a ~3.7s) y el insight de
batching tiene un enfriamiento de 20 minutos simulados.

## Los dos agentes (inteligente vs novato)

`/simulation/start` crea **dos** filas en `simulation_runs` con el mismo
`session_id`: el turno del usuario (`agent_type="inteligente"`) y un turno
espejo (`agent_type="novato"`). Cada orden generada la deciden los dos:

- el **inteligente** la deja pendiente para que el conductor decida
  (`PendingOrdersPanel`), con Score y recomendacion de `decision/policy.py`;
- el **novato** la acepta al instante, siempre, y escribe su propio
  `TripRecord`.

Los dos rutean de verdad sobre el grafo y los dos avanzan su posicion, asi
que la comparacion mide la calidad de la decision y no dos turnos con suerte
distinta. De ahi salen las tarjetas "Novice" de `/stats/live`, el
`/stats/scoreboard` y el `novice_earnings` de `SimulationState`.

**Como leer el marcador:** compara lo que hizo el conductor (asesorado por el
agente) contra aceptar todo. Si el conductor rechaza muchas ofertas buenas, el
novato puede ir ganando — el numero es honesto, no un bug. Para un
"agente solo vs baseline" puro hace falta un modo autonomo (ver Pendiente).

## Movimiento continuo del repartidor

Al aceptar una orden se encola una `ActiveDelivery` con su ruta real
(repartidor -> pickup -> dropoff) y su duracion; en cada tick el repartidor
avanza sobre esa ruta con el reloj del mundo
(`routing.position_along_route`, interpolando dentro de la arista en curso).
Las entregas se hacen de una en una, en orden de aceptacion.

`SimulationState` expone `courier_lat`/`courier_lon`, `active_deliveries` y
`deliveries_completed` — listos para reemplazar `PLACEHOLDER_RIDER_POSITION`
en `MapView.tsx` (eso es cambio de frontend, no se hizo aqui).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env         # completar DATABASE_URL y GEMINI_API_KEY
python -m app.db.init_db      # tablas + DDL de Timescale (idempotente)
uvicorn app.main:app --reload
```

### Datos de demo (historial de un año)

Los filtros del Perfil (1 mes / 6 meses / 1 año) necesitan historial. El
seed genera, por cada dia, un turno inteligente y su espejo novato sobre el
mismo stream de ordenes, y refresca el continuous aggregate:

```bash
python -m app.db.seed_dummy                # 365 dias
python -m app.db.seed_dummy --days 180
python -m app.db.seed_dummy --reset        # borra lo sembrado antes y vuelve a sembrar
```

Todo lo sembrado pertenece al usuario marcador `demo_seed`, asi que `--reset`
no toca datos reales de nadie mas.

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

Los tests no pegan a Tiger Data (no hay fixtures de base todavia): prueban la
logica de cada capa. El flujo HTTP completo SI se valido a mano contra la
instancia real de Tiger Cloud — `/simulation/start` -> `/state` -> `/decide`
-> `/audit/decision` -> `/god-mode` -> `/stats/*` -> `/end`.

## Endpoints de analitica (Tiger Data)

- `GET /stats/live` — pulso de los ultimos 5 minutos por agente/vehiculo y
  ultimos 25 viajes, leidos de las vistas NO materializadas
  (`live_dashboard_summary`, `live_trip_scores`): cada request vuelve a
  correr `calculate_score()` en Postgres. Es lo que consume `DashboardPage`,
  que ya sabe pintar filas de `inteligente` y `novato`.
- `GET /stats/history/{period}` — serie por dia leida del continuous
  aggregate `trip_records_daily` (`time_bucket` de 1 dia). Periodos:
  `dia`, `semana`, `1_mes`, `3_meses`, `6_meses`, `1_anio`. Devuelve
  `points[]` con exactamente las llaves de `EarningsPoint`
  (`date`/`netEarnings`/`gasSaved`/`timeSaved`), asi que `ProfileStats` puede
  cambiar su `SAMPLE_DATA` por esto sin transformar nada.
  - `gasSaved`/`timeSaved` no son columnas: son lo que el inteligente se
    ahorro frente al novato ese dia (novato - inteligente), como documenta
    `db/schema.sql`. **`gasSaved` esta en MXN de gasolina no gastada**,
    mientras que `ProfileStats` hoy lo rotula en litros — hay que corregir
    el rotulo (frontend) o convertir a litros con un precio por litro.
  - El continuous aggregate se dejo en `materialized_only = false`: su policy
    solo materializa hasta hace una hora, y sin eso el filtro "Day" saldria
    vacio aunque el turno este corriendo ahora mismo.
- `GET /stats/scoreboard` — inteligente vs novato del `session_id` mas
  reciente (o el que se pase por query param), con `savings`. Lee
  `trip_records` en crudo (sin el retraso del aggregate) porque es "el turno
  de ahora".

## Pendiente

Backend:

- **Modo autonomo del agente.** Hoy el agente solo recomienda
  (`should_accept`) y el conductor decide, asi que `/stats/scoreboard` compara
  "decisiones del conductor" vs "aceptar todo". Para el criterio de
  "cuanto gana el agente vs un baseline" haria falta un turno donde el agente
  decida solo. Es una decision de producto: el frontend puso al humano en el
  loop a proposito (ver comentario en `PendingOrdersPanel.tsx`).
- **Estado en memoria, un solo worker.** `_sessions` en
  `api/routes/simulation.py` es un dict del proceso: con `uvicorn --workers >1`
  cada worker veria turnos distintos, y un reinicio pierde el turno en curso
  (el frontend ya no puede re-suscribirse). Mover a Redis si se despliega.
- **El reloj del mundo vive en el proceso.** `world_clock` se ancla al
  arranque, asi que reiniciar el backend "regresa" el mundo a la hora real
  actual. Si se quiere continuidad entre reinicios, hay que persistir el ancla.
- **Las evaluaciones de las ordenes pendientes no se recalculan** cuando el
  repartidor se mueve o cuando cambia el trafico: se congelan al momento de
  generarse. Se dejo asi a proposito (un Score que baila en una tarjeta ya
  visible confunde al conductor), pero si se quiere precision total hay que
  recalcular y decidir como comunicar el cambio.
- **`decision/q_learning.py` sigue sin implementar** (reposicionamiento
  predictivo). Fuera de alcance por ahora.
- **Latencia del audit**: Gemini tardo entre 3s y 15s en las pruebas. La
  respuesta se cachea en `decision_audits`, asi que solo la primera vez por
  orden es lenta, pero conviene un spinner/timeout en la UI.
- **El mix de ordenes es generoso**: con tarifas de $40-140 MXN, casi
  cualquier orden deja Score positivo, asi que "aceptar todo" es una
  estrategia decente y el agente tiene poco que discriminar. Vale la pena
  calibrar `order_generator.py` para que existan ofertas claramente malas
  (mucha distancia, poca paga).

Frontend (para el integrante que lleve esa parte — nada de esto se toco):

- `MapView.tsx` sigue con `PLACEHOLDER_RIDER_POSITION`; ya hay
  `courier_lat`/`courier_lon` en `SimulationState`.
- `ProfileStats.tsx` sigue con `SAMPLE_DATA`; `/stats/history/{period}` ya
  devuelve la forma que necesita (ver nota de litros vs MXN arriba).
- `ScoreboardModal.tsx` y `AuditDecisionButton` estan construidos pero ningun
  page los monta; `/stats/scoreboard` y `/audit/decision` ya responden de
  verdad (o usar `novice_earnings` de `SimulationState`, que viene en cada
  poll).
- El cierre de calle viaja con el preset "Rush Hour" porque no se podia
  agregar un boton nuevo sin tocar el frontend.
