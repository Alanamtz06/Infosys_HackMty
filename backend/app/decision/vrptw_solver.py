"""Batching: dado el punto de partida del repartidor y un conjunto de ordenes
pendientes (cada una con su pickup y su dropoff), resuelve en que orden
conviene visitarlas.

Un solo repartidor = "1 vehiculo" en terminos de OR-Tools
(`ortools.constraint_solver.routing`): esto modela que cada corredor de
simulacion resuelve su propio sub-problema, no que el sistema solo admita un
repartidor — nada impide correr esta misma logica para varios agentes en
paralelo. No sabe nada de calles: recibe una matriz de tiempos ya calculada
por `app.engine.routing.get_travel_time_matrix`.

Decision de diseno: el repartidor NO esta obligado a volver al nodo de
partida al terminar (agrega un nodo "sumidero" virtual al que llegar cuesta
0 segundos desde cualquier parada) — el turno no es un tour cerrado, el
repartidor sigue a lo que sea que le llegue despues.

Gotcha de OR-Tools: `RoutingIndexManager.NodeToIndex()` no resuelve nodos
usados solo como "end" de un vehiculo (devuelve -1 en silencio, y pasarle
ese -1 a `CumulVar()` hace segfault). Hay que usar `routing.End(0)`.

Sin metaheuristica de busqueda local (`GUIDED_LOCAL_SEARCH`, la que usan la
mayoria de los ejemplos de OR-Tools): agota siempre el `time_limit`
completo, y este solver puede llamarse varias veces por segundo mientras el
frontend sondea `/simulation/state`. Con solo `PATH_CHEAPEST_ARC` (sin
metaheuristica) resuelve en milisegundos para el tamano real del problema
(un repartidor con unas pocas ordenes pendientes a la vez).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

_SOLVER_TIME_LIMIT_SECONDS = 2
_FALLBACK_HORIZON_SECONDS = 10**7

# OR-Tools trabaja con enteros y `int(round(float('inf')))` explota con
# OverflowError. Un par de nodos puede llegar como infinito en `time_matrix`
# si un cierre de calle (app.engine.routing.apply_road_closure) los
# desconecta — se trata como "carisimo pero finito" para que el solver lo
# evite en vez de tumbar la llamada.
_UNREACHABLE_SECONDS = 10**8


@dataclass
class RouteResult:
    """node_order/arrival_times excluyen el nodo sumidero virtual (no es una
    parada real). `total_time` es la duracion real de la ruta (segundos),
    sin viaje de regreso. `feasible=False` si no hay forma de cumplir las
    ventanas de tiempo y la precedencia pickup->delivery."""

    node_order: list[int]
    arrival_times: list[float]
    total_time: float
    feasible: bool
    dropped_nodes: list[int] = field(default_factory=list)


def solve_route(
    time_matrix: np.ndarray,
    time_windows: list[tuple[float, float]],
    pickup_delivery_pairs: list[tuple[int, int]],
    start_node: int,
) -> RouteResult:
    """Resuelve el orden optimo de visita para un repartidor.

    `time_matrix[i][j]` = segundos de viaje de i a j. `time_windows[i]` =
    (inicio, fin) en segundos en los que es valido visitar el nodo i.
    `pickup_delivery_pairs` = [(indice_pickup, indice_delivery), ...].
    """
    n = len(time_matrix)
    if n == 0:
        return RouteResult(node_order=[], arrival_times=[], total_time=0.0, feasible=True)

    sink_node = n
    manager = pywrapcp.RoutingIndexManager(n + 1, 1, [start_node], [sink_node])
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if from_node == sink_node or to_node == sink_node:
            return 0
        raw = time_matrix[from_node][to_node]
        return int(round(raw)) if math.isfinite(raw) else _UNREACHABLE_SECONDS

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    horizon = int(max((w[1] for w in time_windows), default=0))
    if horizon <= 0:
        horizon = _FALLBACK_HORIZON_SECONDS

    routing.AddDimension(transit_callback_index, horizon, horizon, False, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")

    for node in range(n):
        index = manager.NodeToIndex(node)
        window_start, window_end = time_windows[node]
        time_dimension.CumulVar(index).SetRange(int(window_start), int(window_end))

    sink_index = routing.End(0)
    time_dimension.CumulVar(sink_index).SetRange(0, horizon)

    for pickup_node, delivery_node in pickup_delivery_pairs:
        pickup_index = manager.NodeToIndex(pickup_node)
        delivery_index = manager.NodeToIndex(delivery_node)
        routing.AddPickupAndDelivery(pickup_index, delivery_index)
        routing.solver().Add(routing.VehicleVar(pickup_index) == routing.VehicleVar(delivery_index))
        routing.solver().Add(time_dimension.CumulVar(pickup_index) <= time_dimension.CumulVar(delivery_index))

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.time_limit.FromSeconds(_SOLVER_TIME_LIMIT_SECONDS)

    solution = routing.SolveWithParameters(search_params)

    if solution is None:
        return RouteResult(
            node_order=[], arrival_times=[], total_time=float("inf"), feasible=False, dropped_nodes=list(range(n))
        )

    node_order: list[int] = []
    arrival_times: list[float] = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node_order.append(manager.IndexToNode(index))
        arrival_times.append(float(solution.Value(time_dimension.CumulVar(index))))
        index = solution.Value(routing.NextVar(index))

    total_time = arrival_times[-1] - arrival_times[0] if len(arrival_times) > 1 else 0.0

    return RouteResult(node_order=node_order, arrival_times=arrival_times, total_time=total_time, feasible=True)
