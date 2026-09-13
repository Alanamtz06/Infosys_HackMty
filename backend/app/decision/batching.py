"""Agrupacion de ordenes pendientes: compara Score(batch) vs Score(ordenes
individuales) usando el desvio real de ruta calculado por
`app.engine.routing` + `app.decision.vrptw_solver` (antes era un TODO).

No hay todavia una interaccion en el frontend para "aceptar varias ordenes
juntas" (`PendingOrdersPanel` decide una por una) — por eso `plan_batch` no
cambia el Score individual de cada orden pendiente, solo produce un dato
informativo ("si tomaras estas 3 juntas ahorrarias 12 min") que
`api/routes/simulation.py` registra en el log en vivo. Es el punto de
partida para cuando exista una accion de "aceptar batch" en la UI.
"""

from dataclasses import dataclass, field

import networkx as nx

from app.config import settings
from app.decision.scoring import OrderEvaluation
from app.decision.vrptw_solver import solve_route
from app.engine.routing import get_travel_time_matrix, route_total_time, try_shortest_route

_WIDE_OPEN_WINDOW = (0, 10**7)  # sin ventanas de tiempo reales por orden todavia; ver TODO en schemas/order.py


def evaluate_batch(orders: list[OrderEvaluation]) -> float:
    """Suma de Scores individuales — conveniencia para cuando ya se decidio
    aceptar un conjunto de ordenes y solo hace falta el total."""
    if len(orders) > settings.max_batch_orders:
        raise ValueError(f"Un batch admite maximo {settings.max_batch_orders} ordenes")
    return sum(order.score for order in orders)


@dataclass
class BatchPlan:
    visit_sequence: list[tuple[str, str]] = field(default_factory=list)  # [(order_id, "pickup"|"dropoff"), ...]
    batched_total_seconds: float = 0.0
    sequential_total_seconds: float = 0.0
    time_saved_seconds: float = 0.0


def plan_batch(
    graph: nx.MultiDiGraph,
    start_point: tuple[float, float],
    pending_orders: list[dict],
) -> BatchPlan | None:
    """Compara "visitar todas las `pending_orders` juntas, en el orden optimo
    de VRPTW" contra "hacerlas una por una, cada vez de vuelta desde
    `start_point`" (que es como se evaluan hoy individualmente en
    `DeliveryAgent.evaluate_order`).

    `pending_orders` son dicts con la forma de `order_generator.generate_order`
    (id, pickup_lat/lon, dropoff_lat/lon). Devuelve `None` si hay menos de 2
    ordenes (nada que batchear) o si VRPTW no encuentra una solucion factible.
    """
    if len(pending_orders) < 2:
        return None
    pending_orders = pending_orders[: settings.max_batch_orders]

    points: list[tuple[float, float]] = [start_point]
    node_to_leg: dict[int, tuple[str, str]] = {}
    pickup_delivery_pairs: list[tuple[int, int]] = []

    for order in pending_orders:
        pickup_idx = len(points)
        points.append((order["pickup_lat"], order["pickup_lon"]))
        node_to_leg[pickup_idx] = (order["id"], "pickup")

        dropoff_idx = len(points)
        points.append((order["dropoff_lat"], order["dropoff_lon"]))
        node_to_leg[dropoff_idx] = (order["id"], "dropoff")

        pickup_delivery_pairs.append((pickup_idx, dropoff_idx))

    matrix = get_travel_time_matrix(graph, points)
    time_windows = [_WIDE_OPEN_WINDOW] * len(points)

    batched = solve_route(matrix, time_windows, pickup_delivery_pairs, start_node=0)
    if not batched.feasible:
        return None

    sequential_total = sum(
        matrix[0][pickup_idx] + matrix[pickup_idx][dropoff_idx] for pickup_idx, dropoff_idx in pickup_delivery_pairs
    )

    return BatchPlan(
        visit_sequence=[node_to_leg[node] for node in batched.node_order if node != 0],
        batched_total_seconds=batched.total_time,
        sequential_total_seconds=sequential_total,
        time_saved_seconds=max(sequential_total - batched.total_time, 0.0),
    )


@dataclass
class BackpackPlan:
    """Ruta combinada real para los 2 pedidos que caben en la mochila del
    repartidor: a diferencia de `BatchPlan` (que solo compara tiempos para un
    log informativo), aqui `route` ya son nodos concatenados sobre calles
    reales — lista para asignarse directo a `ActiveDelivery.route`."""

    route: list[int]
    # Cada parada en orden de visita: {"order_id", "kind": "pickup"|"dropoff",
    # "lat", "lon", "label", "eta_seconds"}.
    stop_markers: list[dict]
    pickup_index: int  # indice en `route` del PRIMER pickup aun pendiente
    to_pickup_seconds: float
    total_seconds: float  # incluye service_time_minutes*60 por cada pickup servido
    total_meters: float
    # Pausas de servicio, en el punto REAL donde ocurren (cada pickup — "esperar
    # a que el restaurante saque la comida"), no acumuladas al final de la ruta.
    # [(tiempo_fisico_acumulado_al_llegar_a_la_parada, segundos_de_pausa), ...]
    # — ver `app.engine.routing.position_along_route`.
    dwell_checkpoints: list[tuple[float, float]]


def plan_backpack_route(
    graph: nx.MultiDiGraph,
    start_point: tuple[float, float],
    active_order: dict,
    active_picked_up: bool,
    candidate_order: dict,
    *,
    include_route: bool = True,
) -> BackpackPlan | None:
    """Resuelve la ruta optima para cargar `candidate_order` junto con
    `active_order` (que el repartidor ya trae encima) en una sola mochila.

    Si `active_picked_up` es True, el pickup de `active_order` YA paso: se
    omite del plan (solo su dropoff sigue siendo obligatorio) — su tiempo de
    servicio tampoco se vuelve a cobrar, ya se pago cuando se acepto/recogio
    la primera vez. El pickup y dropoff de `candidate_order` siempre son
    obligatorios.

    `include_route=False` se salta las busquedas de ruta reales
    (`try_shortest_route` por tramo, la parte cara medida en produccion:
    ~2.5s vs ~1.1s con esto apagado) y calcula los tiempos directo de la
    matriz que el VRPTW ya resolvio, sin reconstruir `route` (queda vacio) ni
    `total_meters` (queda en 0.0). Sirve para PUNTUAR una oferta pendiente,
    donde la precision del metro importa menos que no tumbar el tick con
    varias busquedas A* por oferta — mismo criterio que el fare estimado con
    great-circle (no ruteo) en `order_generator.generate_order`.
    `include_route=True` (default) es obligatorio para comprometer la ruta
    real al aceptar (`api/routes/simulation.py::_merge_into_backpack`).

    Devuelve None si el VRPTW no encuentra una solucion factible, o (con
    `include_route=True`) si algun tramo entre paradas consecutivas resulta
    inalcanzable (cierre de calle a mitad del plan).
    """
    points: list[tuple[float, float]] = [start_point]
    # idx -> (order_id, kind, label)
    node_meta: dict[int, tuple[str, str, str | None]] = {}
    pickup_delivery_pairs: list[tuple[int, int]] = []

    if not active_picked_up:
        pickup_idx = len(points)
        points.append((active_order["pickup_lat"], active_order["pickup_lon"]))
        node_meta[pickup_idx] = (active_order["id"], "pickup", active_order.get("pickup_name"))

        dropoff_idx = len(points)
        points.append((active_order["dropoff_lat"], active_order["dropoff_lon"]))
        node_meta[dropoff_idx] = (active_order["id"], "dropoff", None)

        pickup_delivery_pairs.append((pickup_idx, dropoff_idx))
    else:
        dropoff_idx = len(points)
        points.append((active_order["dropoff_lat"], active_order["dropoff_lon"]))
        node_meta[dropoff_idx] = (active_order["id"], "dropoff", None)

    candidate_pickup_idx = len(points)
    points.append((candidate_order["pickup_lat"], candidate_order["pickup_lon"]))
    node_meta[candidate_pickup_idx] = (candidate_order["id"], "pickup", candidate_order.get("pickup_name"))

    candidate_dropoff_idx = len(points)
    points.append((candidate_order["dropoff_lat"], candidate_order["dropoff_lon"]))
    node_meta[candidate_dropoff_idx] = (candidate_order["id"], "dropoff", None)

    pickup_delivery_pairs.append((candidate_pickup_idx, candidate_dropoff_idx))

    matrix = get_travel_time_matrix(graph, points)
    time_windows = [_WIDE_OPEN_WINDOW] * len(points)

    result = solve_route(matrix, time_windows, pickup_delivery_pairs, start_node=0)
    if not result.feasible:
        return None

    if not include_route:
        stop_markers: list[dict] = []
        dwell_checkpoints: list[tuple[float, float]] = []
        pickup_index = 0
        to_pickup_seconds = 0.0
        pickups_served = 0
        pickup_index_set = False
        for i, node in enumerate(result.node_order):
            if node == 0:
                continue
            order_id, kind, label = node_meta[node]
            # `arrival_times[i]` es el tiempo FISICO acumulado (matriz real,
            # sin dwell) que el VRPTW ya calculo — no hace falta re-recorrer
            # la ruta. La pausa de servicio se registra AQUI, en el punto
            # donde ocurre de verdad (llegando al pickup), no sumada al final.
            if kind == "pickup":
                pickups_served += 1
                dwell_checkpoints.append((result.arrival_times[i], settings.service_time_minutes * 60))
            eta_seconds = result.arrival_times[i] + settings.service_time_minutes * 60 * pickups_served
            if kind == "pickup" and not pickup_index_set:
                to_pickup_seconds = eta_seconds
                pickup_index_set = True
            stop_markers.append(
                {
                    "order_id": order_id,
                    "kind": kind,
                    "lat": points[node][0],
                    "lon": points[node][1],
                    "label": label,
                    "eta_seconds": eta_seconds,
                }
            )
        total_seconds = stop_markers[-1]["eta_seconds"] if stop_markers else 0.0
        return BackpackPlan(
            route=[],
            stop_markers=stop_markers,
            pickup_index=pickup_index,
            to_pickup_seconds=to_pickup_seconds,
            total_seconds=total_seconds,
            total_meters=0.0,
            dwell_checkpoints=dwell_checkpoints,
        )

    route: list[int] = []
    stop_markers: list[dict] = []
    dwell_checkpoints: list[tuple[float, float]] = []
    pickup_index = 0
    to_pickup_seconds = 0.0
    total_meters = 0.0
    pickups_served = 0
    pickup_index_set = False
    cursor = start_point

    for node in result.node_order:
        if node == 0:
            continue
        leg = try_shortest_route(graph, cursor, points[node])
        if leg is None:
            return None
        leg_route, _leg_seconds, leg_meters = leg
        route = leg_route if not route else route + leg_route[1:]
        total_meters += leg_meters

        order_id, kind, label = node_meta[node]
        # Tiempo FISICO (sin dwell) para llegar a esta parada — la pausa de
        # servicio se registra en este punto exacto, no al final de la ruta
        # (ver dwell_checkpoints en position_along_route).
        physical_time_here = route_total_time(graph, route)
        if kind == "pickup":
            pickups_served += 1
            dwell_checkpoints.append((physical_time_here, settings.service_time_minutes * 60))
        eta_seconds = physical_time_here + settings.service_time_minutes * 60 * pickups_served

        if kind == "pickup" and not pickup_index_set:
            pickup_index = len(route) - 1
            to_pickup_seconds = eta_seconds
            pickup_index_set = True

        stop_markers.append(
            {
                "order_id": order_id,
                "kind": kind,
                "lat": points[node][0],
                "lon": points[node][1],
                "label": label,
                "eta_seconds": eta_seconds,
            }
        )
        cursor = points[node]

    total_seconds = stop_markers[-1]["eta_seconds"] if stop_markers else 0.0

    return BackpackPlan(
        route=route,
        stop_markers=stop_markers,
        pickup_index=pickup_index,
        to_pickup_seconds=to_pickup_seconds,
        total_seconds=total_seconds,
        total_meters=total_meters,
        dwell_checkpoints=dwell_checkpoints,
    )
