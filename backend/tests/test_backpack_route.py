"""Mochila (2 pedidos maximo): `plan_backpack_route` omite el pickup de la
entrega activa una vez que ya se recogio, y `_settle_order` rechaza un 3er
pedido mientras la mochila ya tiene 2. Usa el fixture `small_graph`
(conftest.py), igual que test_batching.py/test_route_preview.py.
"""

import uuid

import pytest
from fastapi import HTTPException

from app.agents.delivery_agent import DeliveryAgent
from app.agents.novice_agent import NoviceAgent
from app.api.routes import simulation
from app.api.routes.session_state import ActiveDelivery, PendingOrder, SessionState
from app.api.routes.session_store import InMemorySessionStore, reset_session_store
from app.decision.batching import plan_backpack_route
from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.routing import route_total_time, try_shortest_route

pytestmark = pytest.mark.network


def _order(graph, pickup_node, dropoff_node, fare=60.0) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "pickup_lat": graph.nodes[pickup_node]["y"],
        "pickup_lon": graph.nodes[pickup_node]["x"],
        "pickup_name": "Fonda de prueba",
        "dropoff_lat": graph.nodes[dropoff_node]["y"],
        "dropoff_lon": graph.nodes[dropoff_node]["x"],
        "fare": fare,
    }


def _connected_pair(graph):
    nodes = list(graph.nodes)
    for origin in nodes[:40]:
        for dest in nodes[-40:]:
            if origin == dest:
                continue
            o = (graph.nodes[origin]["y"], graph.nodes[origin]["x"])
            d = (graph.nodes[dest]["y"], graph.nodes[dest]["x"])
            result = try_shortest_route(graph, o, d)
            if result is not None and len(result[0]) > 3:
                return origin, dest
    pytest.skip("no se encontraron pares conectados en el recorte de grafo de prueba")


def test_plan_backpack_route_omits_active_pickup_once_picked_up(small_graph):
    nodes = list(small_graph.nodes)
    start_node, _ = _connected_pair(small_graph)
    start = (small_graph.nodes[start_node]["y"], small_graph.nodes[start_node]["x"])

    active_order = _order(small_graph, nodes[1], nodes[10])
    candidate_order = _order(small_graph, nodes[5], nodes[15])

    plan_not_picked_up = plan_backpack_route(
        small_graph, start, active_order, active_picked_up=False, candidate_order=candidate_order
    )
    plan_picked_up = plan_backpack_route(
        small_graph, start, active_order, active_picked_up=True, candidate_order=candidate_order
    )
    if plan_not_picked_up is None or plan_picked_up is None:
        pytest.skip("VRPTW no encontro una solucion factible en este recorte de grafo tan chico")

    kinds_not_picked_up = {(m["order_id"], m["kind"]) for m in plan_not_picked_up.stop_markers}
    kinds_picked_up = {(m["order_id"], m["kind"]) for m in plan_picked_up.stop_markers}

    assert (active_order["id"], "pickup") in kinds_not_picked_up
    assert (active_order["id"], "pickup") not in kinds_picked_up
    assert (active_order["id"], "dropoff") in kinds_picked_up
    assert (candidate_order["id"], "pickup") in kinds_picked_up
    assert (candidate_order["id"], "dropoff") in kinds_picked_up


@pytest.fixture
def fresh_store():
    reset_session_store(InMemorySessionStore())
    yield
    reset_session_store(None)


def test_settle_order_rejects_a_third_order_when_backpack_full(small_graph, fresh_store, monkeypatch):
    """Con 2 pedidos ya en la mochila (`extra_order` fusionado), aceptar una
    3ra oferta debe fallar con 409 en vez de aceptarse silenciosamente."""
    monkeypatch.setattr(simulation, "load_graph", lambda: small_graph)
    monkeypatch.setattr(simulation, "load_restaurants", lambda: [])

    nodes = list(small_graph.nodes)
    origin_node, dest_node = _connected_pair(small_graph)
    origin = (small_graph.nodes[origin_node]["y"], small_graph.nodes[origin_node]["x"])
    route = try_shortest_route(small_graph, origin, (small_graph.nodes[dest_node]["y"], small_graph.nodes[dest_node]["x"]))[0]
    total_seconds = route_total_time(small_graph, route)

    active_order = _order(small_graph, nodes[1], nodes[10])
    extra_order = _order(small_graph, nodes[5], nodes[15])
    full_backpack = ActiveDelivery(
        order=active_order,
        extra_order=extra_order,
        route=route,
        total_seconds=total_seconds,
        started_sim_seconds=0.0,
        pickup_index=0,
        to_pickup_seconds=0.0,
        stop_markers=[
            {"order_id": active_order["id"], "kind": "dropoff", "lat": origin[0], "lon": origin[1], "label": None, "eta_seconds": 60.0},
            {"order_id": extra_order["id"], "kind": "dropoff", "lat": origin[0], "lon": origin[1], "label": None, "eta_seconds": 120.0},
        ],
    )

    third_order = _order(small_graph, nodes[2], nodes[12])
    third_evaluation = OrderEvaluation(fare=60.0, distance_km=1.0, time_minutes=5.0, vehicle=VehicleType.MOTO)

    run_id = str(uuid.uuid4())
    state = SessionState(
        run_id=run_id,
        novice_run_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        vehicle="moto",
        started_sim_seconds=0.0,
        last_tick_sim_seconds=0.0,
        courier_position=origin,
        active_deliveries=[full_backpack],
        pending_orders={third_order["id"]: PendingOrder(order=third_order, evaluation=third_evaluation)},
    )

    rt = simulation.ShiftRuntime(
        state=state,
        graph=small_graph,
        restaurants=[],
        delivery_agent=DeliveryAgent(small_graph, vehicle=VehicleType.MOTO),
        novice_agent=NoviceAgent(small_graph, vehicle=VehicleType.MOTO),
    )

    assert simulation._active_order_count(rt) == 2

    with pytest.raises(HTTPException) as exc_info:
        simulation._settle_order(rt, db=None, order_id=third_order["id"], accept=True)
    assert exc_info.value.status_code == 409
    # La oferta rechazada por capacidad sigue pendiente — no se debe
    # descartar, el conductor podria entregar y aceptarla despues.
    assert third_order["id"] in state.pending_orders
