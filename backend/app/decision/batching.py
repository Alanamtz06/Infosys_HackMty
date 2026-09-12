"""Agrupacion de hasta `max_batch_orders` ordenes simultaneas (greedy).

TODO: implementar la comparacion de Score(batch) vs Score(ordenes individuales)
usando el desvio real de ruta calculado por app.engine.routing.
"""

from app.config import settings
from app.decision.scoring import OrderEvaluation


def evaluate_batch(orders: list[OrderEvaluation]) -> float:
    if len(orders) > settings.max_batch_orders:
        raise ValueError(f"Un batch admite maximo {settings.max_batch_orders} ordenes")
    return sum(order.score for order in orders)
