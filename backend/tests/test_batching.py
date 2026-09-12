"""Usa el fixture `small_graph` (conftest.py)."""

import uuid

import pytest

from app.decision.batching import plan_batch

pytestmark = pytest.mark.network


def _order(graph, pickup_node, dropoff_node) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "pickup_lat": graph.nodes[pickup_node]["y"],
        "pickup_lon": graph.nodes[pickup_node]["x"],
        "dropoff_lat": graph.nodes[dropoff_node]["y"],
        "dropoff_lon": graph.nodes[dropoff_node]["x"],
    }


def test_returns_none_with_fewer_than_two_orders(small_graph):
    nodes = list(small_graph.nodes)
    start = (small_graph.nodes[nodes[0]]["y"], small_graph.nodes[nodes[0]]["x"])
    assert plan_batch(small_graph, start, []) is None
    assert plan_batch(small_graph, start, [_order(small_graph, nodes[1], nodes[2])]) is None


def test_batches_two_orders_and_reports_savings_or_none(small_graph):
    nodes = list(small_graph.nodes)
    start = (small_graph.nodes[nodes[0]]["y"], small_graph.nodes[nodes[0]]["x"])
    orders = [
        _order(small_graph, nodes[1], nodes[2]),
        _order(small_graph, nodes[3], nodes[4]),
    ]

    plan = plan_batch(small_graph, start, orders)
    # puede ser None si VRPTW no encuentra una solucion factible en este
    # recorte de grafo tan chico; lo que nunca debe pasar es una excepcion,
    # y si hay plan, sus numeros deben ser consistentes entre si.
    if plan is not None:
        assert plan.batched_total_seconds >= 0
        assert plan.sequential_total_seconds >= 0
        assert plan.time_saved_seconds == pytest.approx(
            max(plan.sequential_total_seconds - plan.batched_total_seconds, 0.0)
        )
        order_ids_visited = {order_id for order_id, _leg in plan.visit_sequence}
        assert order_ids_visited == {o["id"] for o in orders}
