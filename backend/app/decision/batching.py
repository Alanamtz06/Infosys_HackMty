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
from app.engine.routing import get_travel_time_matrix

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
