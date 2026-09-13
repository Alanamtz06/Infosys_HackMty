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
  para que las vistas en vivo del dashboard no se desincronicen. Lo que
  decide `policy.py` es otra cosa: si conviene OCUPAR el tiempo del
  repartidor con ese pedido (ver abajo).

### La regla de decision: tasa por hora vs tarifa de reserva

El primer intento fue "aceptar si Score > 0" y **no medía nada**: sobre el
flujo real el agente aceptaba ~83% de las ofertas y terminaba empatando con
el novato que acepta todo (en una corrida quedaron literalmente iguales).

La razon es que el recurso escaso es el tiempo, no las ofertas. Un pedido que
deja $30 en 45 minutos paga $40/hora; uno que deja $25 en 15 minutos paga
$100/hora. Aceptar el primero no solo deja menos, tambien tapa la agenda para
los tres que vienen detras — y con la capacidad de un repartidor real, ~95%
de las ofertas llegan cuando ya esta ocupado.

Asi que `policy.should_accept` compara **MXN netos por hora** de la oferta
contra una **tarifa de reserva** (`RESERVATION_RATE_MXN_PER_HOUR`, default
$30/h netos), que se relaja hasta un 35% si el repartidor va atrasado de su
ritmo objetivo: mejor un pedido mediocre que una hora parado. Un Score
negativo se rechaza siempre.

`policy.explain()` devuelve la razon en una linea y se registra en el log en
vivo, para poder justificarle una decision a un juez sin abrir el codigo:

```
Accepted Tacos Rafa — net $45.92 MXN · $97/h net over 28 min clears the $30/h bar
```

Medido con `/simulation/benchmark` (turno de 8h, mismo stream de ordenes):

| Turno arranca | Agente | Novato | Ventaja |
|---|---|---|---|
| 11:00 | $200.03 | $108.25 | **+$91.78 (+85%)** |
| 13:00 | $268.96 | $210.85 | +$58.11 (+28%) |
| 18:00 | $250.96 | $171.78 | +$79.18 (+46%) |

Y no gana trabajando mas: en el turno de las 11:00 el agente facturo mas
ocupando 295 minutos y 96 km, contra los 420 minutos y 139 km del novato.

### La economia del turno (por que esta calibrada asi)

Para que la decision signifique algo, tiene que haber ofertas malas. Tres
piezas hacen eso, y las tres se calibraron midiendo rutas reales sobre el
grafo de la ZMM:

1. **La plataforma paga por el pedido, no por el viaje del repartidor**
   (`order_generator.fare_for_distance`): la tarifa sale de la distancia
   restaurante → casa. El tramo de ir a recoger no se paga, y es justo la
   trampa real del oficio — un pedido que paga bien con el restaurante lejos
   deja Score negativo.
2. **Friccion urbana** (`traffic_rules.BASE_CITY_FRICTION`, 2.0):
   `ox.add_edge_travel_times` da tiempo de flujo libre (sin semaforos, sin
   vueltas, sin estacionarse) y con eso el repartidor cruzaba la ZMM a 57
   km/h. Con el factor queda en ~28 km/h, que es velocidad de reparto real.
3. **Tiempo de servicio** (`SERVICE_TIME_MINUTES`, 8): esperar la comida y
   entregarla. No estaba modelado, y es lo que evita que un pedido de tarifa
   baja se salve solo por estar cerca.

Ademas las entregas son **locales** (`pois.random_house_near`): uno pide del
restaurante que tiene cerca. Antes el destino era un nodo cualquiera del
radio de 8 km, asi que el pedido promedio cruzaba la ciudad (18 km, 45 min) y
un turno de 8 horas apenas daba para 10 pedidos.

Resultado: ~65% de las ofertas dejan Score positivo fuera de hora pico y casi
todas durante el surge — el agente tiene que discriminar, y el surge cambia
la matematica como pide el reto.

### Modo autonomo (`autonomous`)

`/simulation/start` acepta `autonomous: true`: el agente decide solo, sin
ordenes esperando al conductor (y `/simulation/decide` contesta 409). Es lo
que hace comparable "agente vs baseline". El default es `false`, que es el
modo del frontend: el humano decide y el agente recomienda (ver el comentario
de `PendingOrdersPanel.tsx`) — el frontend no manda el campo y sigue igual.

En modo autonomo el agente tambien tiene **capacidad limitada**: no acepta
mas de `MAX_BATCH_ORDERS` entregas en cola. Sin ese tope, "aceptar todo" y
"elegir bien" darian lo mismo.

### `POST /simulation/benchmark`

Corre un turno headless completo (agente autonomo vs novato, mismo stream)
sin depender del reloj del mundo: simula sus propias horas de corrido, asi
que 8 horas se resuelven en ~60-90 segundos en vez de 16 minutos reales.
Persiste los dos runs con un `session_id` compartido, asi que el resultado se
puede leer despues en `/stats/scoreboard` y en el dashboard.

```bash
curl -X POST localhost:8000/simulation/benchmark \
  -H "Content-Type: application/json" \
  -d '{"hours": 8, "start_hour": 11.0, "vehicle": "moto"}'
```

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

## Estado de los turnos: memoria o Redis

`uvicorn --workers N` son N procesos independientes. Con el estado en un dict
de modulo, el turno que arranca en el worker A no existe para el worker B, y
como el frontend sondea cada 2s sin afinidad de proceso, la mitad de los
polls contestaria 404.

`api/routes/session_store.py` resuelve eso partiendo el estado en dos:

- `SessionState` (`session_state.py`): todo lo serializable (ordenes
  pendientes, entregas en curso, contadores, eventos, cierre de calle). Esto
  es lo que viaja a Redis.
- el runtime (grafo de OSMnx + agentes): NO se serializa, se rehidrata por
  worker (`ShiftRuntime.hydrate`) apoyandose en el cache de proceso de
  `load_graph()`. Un detalle facil de olvidar: el cierre de calle vive en las
  aristas del grafo, asi que al rehidratar se vuelve a aplicar.

Backends: `InMemorySessionStore` (default, cero configuracion) y
`RedisSessionStore`, que se activa solo si hay `REDIS_URL`. Si `REDIS_URL`
esta puesto pero Redis no responde, cae a memoria y lo avisa por log en vez
de tumbar el arranque.

El round-trip de serializacion es lo critico aqui y esta cubierto por
`tests/test_session_store.py` (con `fakeredis`, incluyendo el caso de dos
workers contra el mismo Redis). Lo que **no** se probo es el cliente de Redis
contra un servidor real: no habia uno disponible en este entorno.

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
`deliveries_completed` — el frontend ya los consume (`MapView.tsx` mueve el
marcador real con esto, ya no hay placeholder).

**Fix de congelamiento/teletransporte:** el tiempo de servicio (esperar la
comida en el restaurante, `SERVICE_TIME_MINUTES`) se congelaba al FINAL de
toda la ruta en vez de en el nodo del pickup real, porque `elapsed_seconds`
(que ya incluye esas pausas) se salia del presupuesto fisico de la ruta y
`position_along_route` dejaba al repartidor clavado en el ultimo nodo durante
ese tiempo de mas — se veia como "se congela y luego reaparece en otro lado".
El fix (`dwell_checkpoints` en `routing.position_along_route`) consume cada
pausa de servicio en el nodo fisico donde realmente ocurre (pickup real o
pickup del 2do pedido en una mochila combinada), no acumulada al final.

## Mochila de 2 pedidos (VRPTW en vivo)

`settings.max_active_deliveries` (default 2) es cuantos pedidos puede llevar
el repartidor encima a la vez. Con 1 pedido activo, cada oferta nueva se
evalua como candidata a **fusionarse** en esa misma entrega en vez de
evaluarse sola:

1. **Antes de recoger el 1er pedido** (`_fits_strict_corridor` /
   `backpack_strict_proximity_ratio`, default 0.4): criterio estricto y
   barato — el pickup y el dropoff del 2do pedido tienen que caer dentro de
   un "corredor" alrededor del trayecto pickup→dropoff del 1ro (a lo mas 40%
   de esa distancia de cada punto). Sin este filtro, cada oferta nueva
   forzaria un VRPTW completo solo para descartarla.
2. **Ya con el 1er pedido recogido** (`_evaluate_backpack_candidate` /
   `_is_backpack_marginal_eligible`): se resuelve `batching.plan_backpack_route`
   (VRPTW real via OR-Tools) y se compara el **costo marginal** de agregar el
   2do pedido contra la ruta que ya se iba a hacer de todos modos — el Score
   de la oferta ya no se evalua sola, se evalua como "cuanto cambia mi ruta
   actual si la agrego".

Al aceptar, `_merge_into_backpack` reemplaza la `ActiveDelivery` en curso por
una que incluye ambos pedidos (`extra_order`), con la ruta ya re-optimizada.
`SimulationState.at_capacity` (mochila llena, 2/2) se expone para que el
frontend deshabilite "Aceptar" en la ficha de la oferta
(`OrderDetailCard.tsx`) y `/simulation/decide` tambien lo rechaza con 409 del
lado del servidor si se intenta de todos modos.

Costaba caro recalcularlo: el costo marginal es un VRPTW mas varias
busquedas A*, ~2-4s medido (`profile_backpack.py`). Por eso la reevaluacion
periodica de ofertas pendientes (ver mas abajo) NO lo recalculaba en cada
pasada — el fix de esta misma entrega hace que se salte cuando no aplica en
vez de correrlo de mas.

## El optimizador de turno completo (MILP, offline)

`decision/lp_shift_optimizer.py` es una capa distinta de `batching.py`/
`vrptw_solver.py`: esos resuelven "encajar 1-2 pedidos mas" sobre la marcha
con lo que ya se acepto; el optimizador de turno resuelve, dado TODO el flujo
de ofertas que aparecio durante una ventana de tiempo, que SUBCONJUNTO
conviene tomar y en que orden, maximizando ganancia neta — la pregunta que
`policy.should_accept` responde oferta por oferta, resuelta de una vez con
visibilidad completa.

Es un MILP (OR-Tools) sobre un grafo `START` + 2 nodos por pedido (pickup/
dropoff), con restricciones de causalidad (no se puede visitar un pickup
antes de que la oferta exista — nada de "saltar" a una orden del futuro),
precedencia pickup→dropoff, capacidad de mochila (0-2, misma regla que arriba)
y conectividad (sin sub-tours). Con heuristicas greedy + reduccion de grafo
para acotar el espacio de busqueda en ventanas con muchas ofertas.

**No esta conectado a la simulacion en vivo** — es una herramienta de
analisis offline, corrida por `scripts/run_lp_shift_simulation.py` (simula
varios escenarios y compara contra la politica greedy de
`policy.should_accept`) y cubierta por `tests/test_lp_shift_optimizer.py`.
Sirve para medir que tan cerca del optimo teorico esta la heuristica que
corre en vivo, no para decidir turnos reales.

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
-> `/audit/decision` -> `/stats/*` -> `/end`.

Nota: no hay endpoint de "god mode" — se elimino a proposito (ver
`tests/test_god_mode_removed.py`); las 9 vialidades de `traffic_rules.py`
siguen aplicando congestion normal por hora del dia, solo sin el atajo manual
de "forzar hora pico" que existio en una version anterior.

## Endpoints de analitica (Tiger Data)

- `GET /stats/live` — pulso del turno actual (o el ultimo cerrado, si nadie
  esta corriendo ahora mismo) por agente, mas los ultimos 25 viajes de toda
  la plataforma. `get_latest_session_id` (repository.py) elige el
  `session_id` mas reciente que ya tenga `trip_records` para AMBOS agentes
  (inteligente y novato) — si el turno mas nuevo aun no tiene datos de los
  dos, cae al anterior en vez de mostrar ceros mientras el backend procesa la
  primera oferta. `is_active` le dice al frontend si mostrar la etiqueta
  "Turno actual" o "Turno pasado". Cada request vuelve a agregar
  `trip_records` con `calculate_score()` en Postgres, no es una foto cacheada.
  Es lo que consume `DashboardPage` (tarjetas de resumen + tabla de viajes
  recientes).
- `GET /stats/history/{period}` — serie leida del continuous aggregate
  `trip_records_daily`, agrupada por dia salvo `dia` (agrupa por HORA, para
  que el filtro de un solo dia no se vea como un unico punto). Periodos:
  `dia`, `semana`, `1_mes`, `3_meses`, `6_meses`, `1_anio`. Devuelve
  `points[]` con exactamente las llaves de `EarningsPoint`
  (`date`/`netEarnings`/`gasSaved`/`timeSaved`) mas `totals` — lo que
  consume la seccion "Tendencia historica" de `DashboardPage`
  (`EarningsChart` + `TimeFilterSelector`).
  - `gasSaved`/`timeSaved` no son columnas: son lo que el inteligente se
    ahorro frente al novato ese dia (novato - inteligente), como documenta
    `db/schema.sql`. **`gasSaved` esta en MXN de gasolina no gastada** y el
    frontend ya lo rotula asi ("Gasolina ahorrada" con `$`, no litros).
  - El continuous aggregate se dejo en `materialized_only = false`: su policy
    solo materializa hasta hace una hora, y sin eso el filtro "Day" saldria
    vacio aunque el turno este corriendo ahora mismo.
- `GET /stats/scoreboard` — inteligente vs novato del `session_id` mas
  reciente (o el que se pase por query param), con `savings`. Lee
  `trip_records` en crudo (sin el retraso del aggregate) porque es "el turno
  de ahora".

## Reevaluacion de ofertas pendientes

Las tarjetas que ya estan en pantalla se recalculan cuando cambia algo que
les mueve el precio: entro una hora pico, el repartidor quedo en otra parte
de la ciudad, o se cerro una calle. Antes se congelaban al generarse y podian
mostrar un Score que ya no era cierto.

Cada reevaluacion cuesta dos busquedas A* por orden, asi que tiene dos
frenos: solo corre si cambio la huella de contexto
(`_revaluation_context`: bloque de 15 min de hora + posicion libre + cierre
activo) y no mas seguido que cada 5 minutos simulados. Cuando un Score se
mueve de forma material o cambia de signo, se avisa en el log
(`KFC got worse with the traffic: Score $48.45 → $46.91`): que una oferta se
encarezca sin explicacion es peor que el Score viejo. Si una orden se vuelve
inalcanzable, se retira de la lista.

## Pendiente

Backend:

- **`decision/q_learning.py` sigue sin implementar** (reposicionamiento
  predictivo: moverse a la zona donde van a aparecer los pedidos buenos).
  Es el unico pendiente grande de backend que queda.
- **El reloj del mundo vive en el proceso.** `world_clock` se ancla al
  arranque, asi que reiniciar el backend "regresa" el mundo a la hora real
  actual. Con Redis se comparten los turnos pero no el ancla del reloj: si se
  despliega con varios workers, cada uno tendria su propio ancla (arrancan en
  momentos distintos). Habria que persistir el ancla junto al estado.
- **Latencia del audit**: Gemini tardo entre 3s y 15s en las pruebas. La
  respuesta se cachea en `decision_audits`, asi que solo la primera vez por
  orden es lenta, pero conviene un spinner/timeout en la UI.
- **Redis no se probo contra un servidor real** (no habia uno en este
  entorno). La logica de serializacion si esta cubierta con `fakeredis`,
  incluido el caso de dos workers compartiendo estado.
- **El repartidor no se reposiciona solo.** Se queda donde lo dejo su ultima
  entrega; las ofertas se sesgan a la zona del turno, que es fija. Eso es
  justo lo que resolveria el Q-Learning.
- **`decision/batching.plan_batch` sigue siendo informativo**: calcula el
  ahorro de hacer varias ordenes juntas y lo anuncia en el log, pero nadie
  puede aceptar un lote porque no existe esa accion en la UI.

Frontend (resuelto por la rama `FixFrontEnd`, fusionada en
`alana/merge-agente-fixfrontend` — ver `frontend/README.md` para el detalle
de esa reescritura):

- ~~`MapView.tsx` sigue con `PLACEHOLDER_RIDER_POSITION`~~ — resuelto: usa
  `courier_lat`/`courier_lon` (o la posicion del `ActiveDelivery` en curso)
  con animacion suave e interpolacion de bearing.
- ~~`ProfileStats.tsx` sigue con `SAMPLE_DATA`~~ — resuelto y reubicado:
  `ProfileStats.tsx` ya no existe; la tendencia historica (`EarningsChart` +
  `TimeFilterSelector`, real via `/stats/history/{period}`) se movio a
  `DashboardPage` (es una metrica del turno/negocio, no del perfil
  individual). `ProfilePage` ahora es solo edicion de vehiculo.
- ~~El cierre de calle viaja con el preset "Rush Hour"~~ — ya no aplica: los
  presets de "Modo Dios" se eliminaron del todo (ver nota de
  `test_god_mode_removed.py` arriba), no solo del frontend.

Sigue pendiente (nadie lo toco todavia):

- **`ScoreboardModal.tsx` y `AuditDecisionButton`/`AuditExplanationCard`
  siguen construidos pero ningun page los monta** — `/stats/scoreboard` y
  `/audit/decision` ya responden de verdad.
- **El modo autonomo no tiene entrada en la UI.** `/simulation/start` ya
  acepta `autonomous: true` y `SimulationState` expone el campo `autonomous`,
  pero ningun componente lo manda todavia. Un switch de "el agente juega
  solo" seria el demo mas fuerte del reto (dos agentes corriendo el mismo
  turno lado a lado), y del lado del backend ya esta todo.
- **`/simulation/benchmark` tampoco tiene entrada en la UI**; hoy se corre
  por curl o desde `/docs`. Un boton de "medir turno completo" daria el
  numero de agente-vs-baseline en pantalla.
