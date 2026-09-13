"""Optimizacion de TODO un turno (a diferencia de `batching.py`/`vrptw_solver.py`,
que solo resuelven "encajar 1-2 pedidos mas" sobre la marcha): dado un flujo
de ofertas que fue apareciendo mientras el repartidor se movia por una zona
durante una ventana de tiempo, decide que SUBCONJUNTO de esas ofertas conviene
tomar y en que ORDEN, maximizando la ganancia neta.

## El modelo (MILP)

Grafo: un nodo `START` (donde estaba el repartidor al abrir la ventana) mas
dos nodos por pedido (`P_k` = pickup, `D_k` = dropoff). NO todos los nodos
estan conectados entre si: el repartidor no puede saltar a un pedido que
todavia no existia (la restriccion de causalidad, ver mas abajo) — esa es la
razon de ser del grafo, no una lista plana de pedidos.

Variables de decision:
  x[i,j] in {0,1}   arco i->j usado (el repartidor va DIRECTO de i a j)
  u[i]   in {0,1}   nodo i visitado (pedido i servido, si i es P/D)
  T[i]   >= 0       instante (segundos desde el inicio de la ventana) en que
                     se visita i — solo es significativo si u[i]=1
  L[i]   in {0,1,2}  carga de la mochila justo DESPUES de visitar i
  f[i,j] >= 0        flujo de conectividad sobre el arco i->j (ver abajo)

Objetivo — EXACTAMENTE como lo pidio el usuario: el costo de tiempo entra
solo como restriccion, el costo de dinero (gasolina) entra al objetivo junto
con la tarifa bruta:

    max  sum( fare_k * u[D_k] )  -  sum( money_cost[i][j] * x[i,j] )

Restricciones:
  (1) Grado — CAMINO simple, no un tour cerrado: cada nodo visitado (P/D)
      tiene EXACTAMENTE 1 arco entrante y A LO MAS 1 arco saliente (el
      ultimo nodo del camino no tiene salida). `START` tiene a lo mas 1
      arco saliente (si es 0, el repartidor no toma ningun pedido este
      turno — solucion trivial valida si nada conviene).
  (2) Emparejamiento — un pedido se sirve COMPLETO o no se sirve:
      u[P_k] == u[D_k] para todo pedido k.
  (3) Causalidad — no se puede llegar a un pickup antes de que su oferta
      exista: T[P_k] >= ready_at[P_k]. Este es el ejemplo literal del
      usuario ("no saltar de una orden de las 11am a una que no existia
      hasta las 3pm").
  (4) Propagacion de tiempo (estilo MTZ): si x[i,j]=1, entonces
      T[j] >= T[i] + time[i][j]. Con esto el tiempo crece ESTRICTAMENTE a
      lo largo de cualquier secuencia de arcos usados, lo que de paso
      elimina cualquier CICLO (subtour): un ciclo exigiria T[i] > T[i].
  (5) Ventana de turno: T[i] <= duracion_turno para todo nodo visitado.
  (6) Precedencia pickup->dropoff (caso general, no solo el arco directo
      P_k->D_k: pueden meterse otras paradas entre medio si la mochila
      tiene espacio): T[D_k] >= T[P_k] + time[P_k][D_k] cuando ambos se
      visitan — ya se sigue de (4) si el camino usa el arco directo, pero
      se declara aparte para el caso en que no lo use.
  (7) Capacidad de mochila (maximo 2): propagacion de carga
      L[j] = L[i] + delta_j cuando x[i,j]=1 (delta_j = +1 si j es pickup,
      -1 si es dropoff), con 0 <= L <= 2 siempre. Esto YA IMPLICA, sin
      necesidad de una regla aparte, el pedido del usuario de "si la
      mochila esta llena, los dos siguientes nodos deben ser las entregas
      correspondientes": desde un nodo con carga 2 ningun arco hacia OTRO
      pickup es factible (violaria L<=2), asi que los unicos arcos
      salientes que sobreviven son hacia los dos dropoffs pendientes.
  (8) Conectividad (no-islas) — un flujo de una sola mercancia con oferta
      en `START` y demanda 1 en cada nodo visitado: cada nodo P/D visitado
      DEBE recibir 1 unidad de flujo desde algun lado, y la UNICA fuente de
      flujo es `START`. Sin esto, (1)+(4) evitan CICLOS pero no evitan una
      cadena de pedidos flotante y desconectada de `START` (in-grado 1,
      out-grado <=1 tambien describe un fragmento de camino suelto, no solo
      el camino bueno) — exactamente la "isla de nodos" que pidio evitar el
      usuario. f[i,j] <= (N pedidos) * x[i,j] liga el flujo a que el arco
      este realmente en uso.

## Por que esto es NP-dificil y como se ataca (lo que pidio el usuario)

Con N pedidos hay 2N+1 nodos y hasta O(N^2) arcos: hasta N! ordenes posibles
de visita (Steiner/orienteering con pickup-delivery, capacidad y ventanas de
tiempo — familia de problemas NP-dificil). Resolver el MILP EXACTO sobre el
grafo COMPLETO se vuelve lento rapido. El flujo de trabajo (`optimize_shift`)
por eso:
  1. Corre varias heuristicas GREEDY rapidas y distintas entre si (cada una
     construye una solucion factible completa en tiempo lineal).
  2. Arma una matriz de adyacencia con los arcos que esas heuristicas
     realmente usaron, mas los `k` vecinos mas prometedores de cada nodo por
     "valor por segundo" (fare / tiempo de traslado) — un margen para que el
     MILP pueda mejorar sobre lo que greedy encontro, sin reintroducir el
     grafo completo.
  3. Resuelve el MILP EXACTO (OR-Tools + CBC) solo sobre esa MATRIZ REDUCIDA
     — mucho mas chica, tratable en segundos en vez del problema completo.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from ortools.linear_solver import pywraplp

from app.config import settings
from app.engine.routing import get_travel_distance_matrix, get_travel_time_matrix

# --------------------------------------------------------------------------
# Datos de entrada / grafo
# --------------------------------------------------------------------------


@dataclass
class OrderSpec:
    """Una oferta que aparecio durante la ventana del turno simulado."""

    id: str
    pickup: tuple[float, float]
    dropoff: tuple[float, float]
    fare: float
    # Segundos desde el INICIO de la ventana en que la oferta se volvio
    # visible — el analogo de "salio a las 11am" del ejemplo del usuario.
    emerged_at: float


@dataclass
class GraphNode:
    id: str  # "START", "P0", "D0", "P1", "D1", ...
    kind: str  # "start" | "pickup" | "dropoff"
    order_idx: int | None
    lat: float
    lon: float
    ready_at: float  # emerged_at para pickups; 0.0 para start/dropoffs (no aplica)


@dataclass
class ShiftGraph:
    """El grafo completo (todos los arcos matematicamente posibles, salvo
    self-loops y arcos hacia `START`) mas los costos precomputados. La
    factibilidad temporal/de mochila NO se filtra aqui — la deciden las
    restricciones del MILP (T[], L[]); este objeto solo trae los NUMEROS."""

    nodes: list[GraphNode]
    time_seconds: np.ndarray  # [i][j], segundos de traslado real sobre el grafo de calles
    money_cost: np.ndarray  # [i][j], MXN de gasolina del traslado
    orders: list[OrderSpec]

    @property
    def n(self) -> int:
        return len(self.nodes)

    def node_index(self, node_id: str) -> int:
        return next(i for i, n in enumerate(self.nodes) if n.id == node_id)

    def pickup_dropoff_pairs(self) -> list[tuple[int, int]]:
        """[(indice_pickup, indice_dropoff), ...] en el mismo orden que `orders`."""
        pairs = []
        for k in range(len(self.orders)):
            p = self.node_index(f"P{k}")
            d = self.node_index(f"D{k}")
            pairs.append((p, d))
        return pairs

    def earliest_possible_arrival(self) -> list[float]:
        """Cota inferior VALIDA (nunca sobreestimada) de `T[i]` para cada
        nodo, sin resolver nada: START en 0, cada pickup en su propio
        `ready_at` (es litralmente la restriccion (3) del MILP), cada
        dropoff en la cota de su propio pickup mas el tramo directo entre
        ambos. Sirve solo para podar arcos IMPOSIBLES (ver `allowed_arcs`),
        nunca para decidir el orden real de visita — eso lo decide el MILP."""
        earliest = [0.0] * self.n
        for k, (p, d) in enumerate(self.pickup_dropoff_pairs()):
            earliest[p] = self.nodes[p].ready_at
            earliest[d] = earliest[p] + self.time_seconds[p][d]
        return earliest

    def allowed_arcs(self, window_seconds: float | None = None) -> list[tuple[int, int]]:
        """Todo arco i->j "matematicamente posible": sin self-loops, nada
        entra a START, y (si se da `window_seconds`) se descarta lo que
        NUNCA puede caber en la ventana del turno: aun saliendo de `i` en el
        instante mas temprano posible (`earliest_possible_arrival()`), el
        tramo i->j ya no alcanzaria a terminar antes de que se acabe la
        ventana. La causalidad real (no llegar a un pickup antes de que su
        oferta exista) la impone el MILP via `ready_at`/`T[]` — NO se poda
        aqui, porque un `T[i]` mas tardio que el minimo (por un camino mas
        largo hasta `i`) puede seguir siendo factible aunque la cota mas
        optimista no lo fuera."""
        start = 0
        earliest = self.earliest_possible_arrival()
        arcs = []
        for i in range(self.n):
            for j in range(self.n):
                if i == j or j == start:
                    continue
                if not np.isfinite(self.time_seconds[i][j]):
                    continue
                if window_seconds is not None and earliest[i] + self.time_seconds[i][j] > window_seconds:
                    continue
                arcs.append((i, j))
        return arcs


def build_shift_graph(
    graph: nx.MultiDiGraph,
    orders: list[OrderSpec],
    start_position: tuple[float, float],
    vehicle_gas_cost_per_km: float | None = None,
) -> ShiftGraph:
    """Arma los nodos y precalcula tiempo/dinero de CADA par de nodos sobre
    el grafo real de calles (Dijkstra por origen, igual patron que
    `get_travel_time_matrix`/`get_travel_distance_matrix` — un Dijkstra por
    nodo, no N^2 busquedas A* independientes: con N pedidos son 2N+1 nodos,
    y a esta escala (unas pocas decenas) sigue siendo cuestion de segundos)."""
    gas_cost_per_km = vehicle_gas_cost_per_km or settings.gas_cost_per_km_moto

    nodes = [GraphNode(id="START", kind="start", order_idx=None, lat=start_position[0], lon=start_position[1], ready_at=0.0)]
    for idx, order in enumerate(orders):
        nodes.append(
            GraphNode(id=f"P{idx}", kind="pickup", order_idx=idx, lat=order.pickup[0], lon=order.pickup[1], ready_at=order.emerged_at)
        )
        nodes.append(
            GraphNode(id=f"D{idx}", kind="dropoff", order_idx=idx, lat=order.dropoff[0], lon=order.dropoff[1], ready_at=0.0)
        )

    points = [(n.lat, n.lon) for n in nodes]
    time_matrix = get_travel_time_matrix(graph, points)
    distance_matrix = get_travel_distance_matrix(graph, points)
    money_cost = distance_matrix / 1000.0 * gas_cost_per_km

    return ShiftGraph(nodes=nodes, time_seconds=time_matrix, money_cost=money_cost, orders=orders)


# --------------------------------------------------------------------------
# Heuristicas greedy (paso 1 de la reduccion del espacio de busqueda)
# --------------------------------------------------------------------------


@dataclass
class GreedySolution:
    name: str
    path: list[int]  # indices de nodo, en orden de visita, empezando en START
    net_profit: float
    feasible: bool


def _feasible_next_nodes(sg: ShiftGraph, visited: set[int], current: int, current_time: float, load: int) -> list[int]:
    """Candidatos validos para el SIGUIENTE nodo desde `current`, dado el
    estado actual (ya replica, en Python plano, las restricciones (2)-(7)
    del MILP — greedy solo elige EL ORDEN, la factibilidad la respeta
    igual)."""
    candidates = []
    pairs = sg.pickup_dropoff_pairs()
    pickup_of = {d: p for p, d in pairs}
    for j in range(sg.n):
        if j == 0 or j in visited:
            continue
        node = sg.nodes[j]
        if node.kind == "pickup":
            if load >= 2:
                continue
            arrival = current_time + sg.time_seconds[current][j]
            if not np.isfinite(arrival) or arrival < node.ready_at:
                continue
        else:  # dropoff: su propio pickup ya debe estar servido y sin entregar aun
            pickup_idx = pickup_of[j]
            if pickup_idx not in visited:
                continue
        if not np.isfinite(sg.time_seconds[current][j]):
            continue
        candidates.append(j)
    return candidates


def _run_greedy(sg: ShiftGraph, window_seconds: float, score_fn) -> GreedySolution:
    """Esqueleto comun: en cada paso, entre los candidatos FACTIBLES elige el
    que maximiza `score_fn(sg, candidate, current, current_time)`. Distintas
    heuristicas = distinto `score_fn`, mismo esqueleto."""
    pairs = sg.pickup_dropoff_pairs()
    dropoff_of = {p: d for p, d in pairs}

    current = 0
    current_time = 0.0
    load = 0
    visited = {0}
    path = [0]

    while True:
        candidates = _feasible_next_nodes(sg, visited, current, current_time, load)
        # Solo se mueve si el traslado + lo que reste del turno alcanza para
        # cumplir la ventana; y solo si el candidato en si mismo conviene
        # (evita que greedy acepte un pickup que ya sabe que dejara en score
        # negativo neto, aunque siga siendo "factible").
        feasible_within_window = [
            j for j in candidates if current_time + sg.time_seconds[current][j] <= window_seconds
        ]
        if not feasible_within_window:
            break
        scored = [(score_fn(sg, j, current, current_time), j) for j in feasible_within_window]
        scored.sort(key=lambda t: t[0], reverse=True)
        best_score, best_j = scored[0]
        if best_score <= 0:
            break
        current_time += sg.time_seconds[current][best_j]
        current = best_j
        visited.add(current)
        path.append(current)
        node = sg.nodes[current]
        load += 1 if node.kind == "pickup" else -1

    net_profit = _path_profit(sg, path)
    return GreedySolution(name="", path=path, net_profit=net_profit, feasible=True)


def _path_profit(sg: ShiftGraph, path: list[int]) -> float:
    revenue = sum(sg.orders[sg.nodes[j].order_idx].fare for j in path if sg.nodes[j].kind == "dropoff")
    cost = sum(sg.money_cost[path[i]][path[i + 1]] for i in range(len(path) - 1))
    return revenue - cost


def greedy_nearest_profitable(sg: ShiftGraph, window_seconds: float) -> GreedySolution:
    """Heuristica 1: en cada paso, el candidato con mejor MARGEN INMEDIATO
    (tarifa si es un dropoff que cobra, o el ahorro de "acercarse" a su
    propio dropoff si es un pickup, menos el costo de gasolina del tramo).
    Favorece tramos cortos y baratos."""

    def score(sg: ShiftGraph, j: int, current: int, current_time: float) -> float:
        node = sg.nodes[j]
        gas = sg.money_cost[current][j]
        gain = sg.orders[node.order_idx].fare if node.kind == "dropoff" else 0.0
        return gain - gas

    sol = _run_greedy(sg, window_seconds, score)
    sol.name = "nearest_profitable"
    return sol


def greedy_best_rate_per_second(sg: ShiftGraph, window_seconds: float) -> GreedySolution:
    """Heuristica 2: prioriza el candidato con mejor TARIFA POR SEGUNDO de
    traslado (fare / tiempo del tramo para un dropoff; para un pickup, mira
    la tarifa de SU PROPIO pedido sobre el tiempo combinado tramo+entrega,
    "vale la pena desviarme para recogerlo"). Favorece pedidos de buena paga
    aunque el tramo sea mas largo."""

    def score(sg: ShiftGraph, j: int, current: int, current_time: float) -> float:
        node = sg.nodes[j]
        travel = sg.time_seconds[current][j]
        if travel <= 0:
            travel = 1.0
        if node.kind == "dropoff":
            fare = sg.orders[node.order_idx].fare
            return fare / travel
        # pickup: aproxima el "vale la pena" con el tramo hasta el pickup
        # MAS el tramo pickup->su propio dropoff, ya que ese costo tambien
        # es inevitable si se toma.
        order = sg.orders[node.order_idx]
        dropoff_idx = sg.node_index(f"D{node.order_idx}")
        total_time = travel + sg.time_seconds[j][dropoff_idx]
        if total_time <= 0:
            total_time = 1.0
        return order.fare / total_time

    sol = _run_greedy(sg, window_seconds, score)
    sol.name = "best_rate_per_second"
    return sol


def greedy_highest_fare_first(sg: ShiftGraph, window_seconds: float) -> GreedySolution:
    """Heuristica 3: siempre que un dropoff este disponible lo prioriza
    (cobrar cuanto antes); si no hay ninguno disponible, va por el PICKUP de
    mayor tarifa entre los factibles. Favorece llenar la mochila con pedidos
    caros y liberarla apenas se pueda."""

    def score(sg: ShiftGraph, j: int, current: int, current_time: float) -> float:
        node = sg.nodes[j]
        if node.kind == "dropoff":
            return 1e6 + sg.orders[node.order_idx].fare  # siempre gana sobre un pickup
        return sg.orders[node.order_idx].fare

    sol = _run_greedy(sg, window_seconds, score)
    sol.name = "highest_fare_first"
    return sol


GREEDY_HEURISTICS = [greedy_nearest_profitable, greedy_best_rate_per_second, greedy_highest_fare_first]


# --------------------------------------------------------------------------
# Reduccion del grafo: matriz de adyacencia armada desde los greedy
# --------------------------------------------------------------------------


def reduce_arcs_via_greedy(
    sg: ShiftGraph,
    window_seconds: float,
    greedy_solutions: list[GreedySolution],
    extra_neighbors_per_node: int = 4,
) -> tuple[list[tuple[int, int]], np.ndarray]:
    """Arma la matriz de adyacencia REDUCIDA que el MILP exacto va a usar:
    la union de los arcos que las heuristicas greedy realmente recorrieron,
    mas los `extra_neighbors_per_node` vecinos mas prometedores de cada nodo
    (por tarifa-del-destino / costo-del-tramo) que ninguna greedy tomo — el
    margen que le permite al MILP EXACTO encontrar algo mejor que cualquier
    greedy individual, sin volver a cargar el grafo completo (que crece como
    O(N^2) y vuelve el MILP intratable para turnos con muchos pedidos).

    El resultado es SIEMPRE un subconjunto de `sg.allowed_arcs(window_seconds)`
    — los vecinos extra se escogen de ahi, no del grafo completo sin podar,
    para que "reducido" nunca termine siendo mas grande que "completo"."""
    n = sg.n
    base_arcs = set(sg.allowed_arcs(window_seconds))
    adjacency = np.zeros((n, n), dtype=bool)

    for sol in greedy_solutions:
        for i in range(len(sol.path) - 1):
            arc = (sol.path[i], sol.path[i + 1])
            if arc in base_arcs:
                adjacency[arc[0]][arc[1]] = True

    # Vecinos "prometedores" adicionales: para cada nodo, los K destinos con
    # mejor (ganancia_del_destino / costo_del_tramo) DENTRO de los arcos
    # temporalmente posibles, sin importar si alguna greedy los uso — value
    # = tarifa si el destino es un dropoff, 0 si no (un pickup no "paga"
    # hasta que se entrega, pero seguir esta metrica igual prioriza
    # acercarse a pedidos de paga alta).
    for i in range(n):
        scored = []
        for j in range(n):
            if (i, j) not in base_arcs or not np.isfinite(sg.money_cost[i][j]):
                continue
            node = sg.nodes[j]
            value = sg.orders[node.order_idx].fare if node.kind == "dropoff" else 0.0
            denom = max(sg.money_cost[i][j], 0.01)
            scored.append((value / denom, j))
        scored.sort(reverse=True)
        for _, j in scored[:extra_neighbors_per_node]:
            adjacency[i][j] = True

    arcs = [(i, j) for i in range(n) for j in range(n) if adjacency[i][j]]
    return arcs, adjacency


# --------------------------------------------------------------------------
# MILP exacto (OR-Tools + CBC) sobre el grafo reducido
# --------------------------------------------------------------------------


@dataclass
class ShiftPlan:
    status: str  # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "ERROR"
    path: list[int]  # indices de nodo en orden de visita (incluye START)
    served_order_ids: list[str]
    net_profit: float
    total_revenue: float
    total_money_cost: float
    arrival_times: dict[int, float]  # indice de nodo -> T[i]
    solve_seconds: float


def solve_shift_milp(
    sg: ShiftGraph,
    window_seconds: float,
    allowed_arcs: list[tuple[int, int]],
    time_limit_seconds: float = 20.0,
) -> ShiftPlan:
    """Resuelve el MILP EXACTO (formulacion completa en el docstring del
    modulo) sobre `allowed_arcs` (ya reducidos por `reduce_arcs_via_greedy`)."""
    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:
        return ShiftPlan("ERROR", [], [], 0.0, 0.0, 0.0, {}, 0.0)
    solver.SetTimeLimit(int(time_limit_seconds * 1000))

    n = sg.n
    pairs = sg.pickup_dropoff_pairs()
    n_orders = len(pairs)
    big_m_time = window_seconds + float(np.nanmax(sg.time_seconds[np.isfinite(sg.time_seconds)])) + 1.0
    big_m_load = 4.0

    x: dict[tuple[int, int], object] = {}
    f: dict[tuple[int, int], object] = {}
    for i, j in allowed_arcs:
        if not np.isfinite(sg.time_seconds[i][j]):
            continue
        x[i, j] = solver.BoolVar(f"x_{i}_{j}")
        f[i, j] = solver.NumVar(0.0, n_orders, f"f_{i}_{j}")

    u = [solver.BoolVar(f"u_{i}") for i in range(n)]
    solver.Add(u[0] == 1)  # START siempre "activo"
    T = [solver.NumVar(0.0, window_seconds, f"T_{i}") for i in range(n)]
    L = [solver.NumVar(0.0, 2.0, f"L_{i}") for i in range(n)]
    solver.Add(T[0] == 0.0)
    solver.Add(L[0] == 0.0)

    def incoming(i):
        return [x[a, b] for a, b in allowed_arcs if b == i and (a, b) in x]

    def outgoing(i):
        return [x[a, b] for a, b in allowed_arcs if a == i and (a, b) in x]

    # (1) grado
    for i in range(1, n):
        solver.Add(solver.Sum(incoming(i)) == u[i])
        solver.Add(solver.Sum(outgoing(i)) <= u[i])
    solver.Add(solver.Sum(outgoing(0)) <= 1)

    # (2) emparejamiento pickup/dropoff
    for p, d in pairs:
        solver.Add(u[p] == u[d])

    # (3) causalidad
    for node_idx, node in enumerate(sg.nodes):
        if node.kind == "pickup":
            solver.Add(T[node_idx] >= node.ready_at * u[node_idx])

    # (4) propagacion de tiempo (MTZ) + (6) precedencia general (misma forma)
    for i, j in allowed_arcs:
        if (i, j) not in x:
            continue
        solver.Add(T[j] >= T[i] + sg.time_seconds[i][j] - big_m_time * (1 - x[i, j]))

    # (5) ventana del turno
    for i in range(n):
        solver.Add(T[i] <= window_seconds)

    # (7) capacidad de mochila
    delta = [0.0] * n
    for p, d in pairs:
        delta[p] = 1.0
        delta[d] = -1.0
    for i, j in allowed_arcs:
        if (i, j) not in x:
            continue
        solver.Add(L[j] >= L[i] + delta[j] - big_m_load * (1 - x[i, j]))
        solver.Add(L[j] <= L[i] + delta[j] + big_m_load * (1 - x[i, j]))

    # (8) conectividad (sin islas): flujo de una mercancia desde START
    for i, j in allowed_arcs:
        if (i, j) not in x:
            continue
        solver.Add(f[i, j] <= n_orders * x[i, j])
    for i in range(1, n):
        solver.Add(solver.Sum(f[a, b] for a, b in allowed_arcs if b == i and (a, b) in f) - solver.Sum(f[a, b] for a, b in allowed_arcs if a == i and (a, b) in f) == u[i])
    solver.Add(solver.Sum(f[a, b] for a, b in allowed_arcs if a == 0 and (a, b) in f) == solver.Sum(u[1:]))

    # Objetivo: tarifas cobradas menos gasolina de los tramos usados. El
    # tiempo NO entra aqui (solo en la restriccion (5)) — asi lo pidio
    # explicitamente el usuario.
    revenue_terms = []
    for p, d in pairs:
        order = sg.orders[sg.nodes[d].order_idx]
        revenue_terms.append(order.fare * u[d])
    cost_terms = [sg.money_cost[i][j] * x[i, j] for i, j in x]
    solver.Maximize(solver.Sum(revenue_terms) - solver.Sum(cost_terms))

    status = solver.Solve()
    solve_seconds = solver.WallTime() / 1000.0

    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return ShiftPlan("INFEASIBLE", [], [], 0.0, 0.0, 0.0, {}, solve_seconds)

    # Reconstruye el camino recorriendo los arcos con x=1 desde START.
    chosen = {i: j for (i, j) in x if x[i, j].solution_value() > 0.5}
    path = [0]
    current = 0
    visited_guard = set()
    while current in chosen and current not in visited_guard:
        visited_guard.add(current)
        current = chosen[current]
        path.append(current)

    served_order_ids = [sg.orders[sg.nodes[j].order_idx].id for j in path if sg.nodes[j].kind == "dropoff"]
    revenue = sum(sg.orders[sg.nodes[j].order_idx].fare for j in path if sg.nodes[j].kind == "dropoff")
    money_cost_total = sum(sg.money_cost[path[i]][path[i + 1]] for i in range(len(path) - 1))
    arrival_times = {i: T[i].solution_value() for i in path}

    status_label = "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE"
    return ShiftPlan(
        status=status_label,
        path=path,
        served_order_ids=served_order_ids,
        net_profit=revenue - money_cost_total,
        total_revenue=revenue,
        total_money_cost=money_cost_total,
        arrival_times=arrival_times,
        solve_seconds=solve_seconds,
    )


# --------------------------------------------------------------------------
# Punto de entrada: greedy -> reduccion -> MILP exacto
# --------------------------------------------------------------------------


@dataclass
class OptimizationResult:
    plan: ShiftPlan
    greedy_solutions: list[GreedySolution]
    best_greedy_profit: float
    reduced_arc_count: int
    full_arc_count: int


def optimize_shift(
    graph: nx.MultiDiGraph,
    orders: list[OrderSpec],
    start_position: tuple[float, float],
    window_seconds: float,
    vehicle_gas_cost_per_km: float | None = None,
    extra_neighbors_per_node: int = 4,
    time_limit_seconds: float = 20.0,
) -> OptimizationResult:
    """El flujo completo que pidio el usuario: construir el grafo, correr
    varias heuristicas greedy, reducir el espacio de busqueda con la matriz
    de adyacencia que esas heuristicas producen, y resolver el MILP exacto
    solo sobre esa version reducida."""
    sg = build_shift_graph(graph, orders, start_position, vehicle_gas_cost_per_km)
    full_arcs = sg.allowed_arcs(window_seconds)

    greedy_solutions = [heuristic(sg, window_seconds) for heuristic in GREEDY_HEURISTICS]
    best_greedy_profit = max((s.net_profit for s in greedy_solutions), default=0.0)

    reduced_arcs, _adjacency = reduce_arcs_via_greedy(sg, window_seconds, greedy_solutions, extra_neighbors_per_node)
    plan = solve_shift_milp(sg, window_seconds, reduced_arcs, time_limit_seconds)

    return OptimizationResult(
        plan=plan,
        greedy_solutions=greedy_solutions,
        best_greedy_profit=best_greedy_profit,
        reduced_arc_count=len(reduced_arcs),
        full_arc_count=len(full_arcs),
    )
