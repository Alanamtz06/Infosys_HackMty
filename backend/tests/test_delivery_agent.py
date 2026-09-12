"""Usa el fixture `small_graph` (conftest.py)."""

import pytest

from app.agents.delivery_agent import DeliveryAgent
from app.decision.scoring import VehicleType

pytestmark = pytest.mark.network


def _point(graph, node):
    return (graph.nodes[node]["y"], graph.nodes[node]["x"])


def test_evaluate_order_includes_courier_to_pickup_leg(small_graph):
    """Antes del fix, si el repartidor ya tenia `.position` distinto del
    pickup, `evaluate_order` calculaba la ruta directo a `dropoff` saltandose
    el pickup — subestimando el tiempo/distancia real."""
    nodes = list(small_graph.nodes)
    agent = DeliveryAgent(small_graph, vehicle=VehicleType.MOTO)
    agent.position = _point(small_graph, nodes[0])

    pickup = _point(small_graph, nodes[len(nodes) // 2])
    dropoff = _point(small_graph, nodes[-1])

    evaluation = agent.evaluate_order(pickup, dropoff, fare=50.0)

    # cota inferior: al menos el tramo pickup->dropoff solo (sin contar el
    # tramo repartidor->pickup) ya deberia caber dentro del tiempo total.
    from app.engine.routing import shortest_route

    _, pickup_to_dropoff_s, pickup_to_dropoff_m = shortest_route(small_graph, pickup, dropoff)
    assert evaluation.time_minutes * 60 >= pickup_to_dropoff_s
    assert evaluation.distance_km * 1000 >= pickup_to_dropoff_m


def test_evaluate_order_without_position_starts_from_pickup(small_graph):
    nodes = list(small_graph.nodes)
    agent = DeliveryAgent(small_graph, vehicle=VehicleType.MOTO)
    assert agent.position is None

    pickup = _point(small_graph, nodes[0])
    dropoff = _point(small_graph, nodes[-1])
    evaluation = agent.evaluate_order(pickup, dropoff, fare=50.0)

    assert evaluation.time_minutes >= 0
    assert evaluation.distance_km >= 0
