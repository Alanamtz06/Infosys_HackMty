"""Regresion del bug real: GET /simulation/route dibujaba el preview desde
`_next_free_position` (donde el repartidor va a quedar libre DESPUES de
terminar lo que ya trae en cola), no desde donde esta parado ahora mismo. Con
una entrega en curso, el preview arrancaba en un punto donde el repartidor
todavia no estaba — el mismo sintoma que "spawnear en un punto random".

Sin red mas alla de la primera descarga del grafo chico (`small_graph`,
cacheado por OSMnx): no toca Tiger Data, `get_order_route` no depende de la
base de datos.
"""

import uuid

import pytest

from app.agents.delivery_agent import DeliveryAgent
from app.agents.novice_agent import NoviceAgent
from app.api.routes import simulation
from app.api.routes.session_state import ActiveDelivery, PendingOrder, SessionState
from app.api.routes.session_store import InMemorySessionStore, reset_session_store
from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.routing import route_total_time, try_shortest_route
from app.engine.virtual_clock import world_clock

pytestmark = pytest.mark.network


def _connected_pair(graph, count=1):
    """`count` pares (origen, destino, ruta) conectados y suficientemente
    largos para que la interpolacion a mitad de camino sea un punto
    claramente distinto del origen y del destino."""
    nodes = list(graph.nodes)
    found = []
    for origin in nodes[:60]:
        for dest in nodes[-60:]:
            if origin == dest:
                continue
            o = (graph.nodes[origin]["y"], graph.nodes[origin]["x"])
            d = (graph.nodes[dest]["y"], graph.nodes[dest]["x"])
            result = try_shortest_route(graph, o, d)
            if result is not None and len(result[0]) > 5:
                found.append((o, d, result[0]))
                if len(found) == count:
                    return found
    pytest.skip("no se encontraron suficientes pares conectados en el recorte de grafo de prueba")


@pytest.fixture
def fresh_store():
    """Cada test parte de un session store en memoria propio, para no
    arrastrar turnos de otros tests (o de un proceso real corriendo en
    paralelo, si `get_session_store()` ya se habia inicializado antes)."""
    reset_session_store(InMemorySessionStore())
    yield
    reset_session_store(None)


def _order_dict(pickup, dropoff, fare=60.0):
    return {
        "id": str(uuid.uuid4()),
        "pickup_lat": pickup[0],
        "pickup_lon": pickup[1],
        "pickup_name": "Fonda de prueba",
        "zone": "Centro",
        "dropoff_lat": dropoff[0],
        "dropoff_lon": dropoff[1],
        "fare": fare,
    }


def test_preview_starts_where_the_courier_actually_is(small_graph, fresh_store, monkeypatch):
    """Con una entrega YA en curso (a medio camino) mas otra en cola detras,
    `_next_free_position` (el dropoff de la ultima en cola) y
    `_courier_live_position` (la interpolacion sobre la ruta actual) deben
    ser dos puntos DISTINTOS — si no, el escenario no prueba nada. El preview
    de una tercera orden pendiente debe arrancar en la posicion REAL, no en
    la futura."""
    monkeypatch.setattr(simulation, "load_graph", lambda: small_graph)
    monkeypatch.setattr(simulation, "load_restaurants", lambda: [])

    (o1, d1, route1), (o2, d2, route2) = _connected_pair(small_graph, count=2)
    total1 = route_total_time(small_graph, route1)
    total2 = route_total_time(small_graph, route2)
    assert total1 > 0 and total2 > 0

    now_s = world_clock.sim_elapsed_seconds()
    # La primera entrega arranco hace "total1/2" segundos simulados: va a
    # medio camino, ni en el origen ni en el destino.
    in_progress = ActiveDelivery(
        order=_order_dict(o1, d1),
        route=route1,
        total_seconds=total1,
        started_sim_seconds=now_s - total1 / 2,
        pickup_index=0,
        to_pickup_seconds=0.0,
    )
    # La segunda todavia no arranca (esta en cola detras de la primera).
    queued = ActiveDelivery(
        order=_order_dict(o2, d2),
        route=route2,
        total_seconds=total2,
        started_sim_seconds=None,
        pickup_index=0,
        to_pickup_seconds=0.0,
    )

    # Una tercera orden, pendiente, cuyo preview vamos a pedir.
    third_pickup = (small_graph.nodes[route2[-1]]["y"], small_graph.nodes[route2[-1]]["x"])
    third_dropoff = (small_graph.nodes[route1[0]]["y"], small_graph.nodes[route1[0]]["x"])
    third_order = _order_dict(third_pickup, third_dropoff)
    third_evaluation = OrderEvaluation(fare=60.0, distance_km=1.0, time_minutes=5.0, vehicle=VehicleType.MOTO)

    run_id = str(uuid.uuid4())
    state = SessionState(
        run_id=run_id,
        novice_run_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        vehicle="moto",
        started_sim_seconds=now_s - 600,
        last_tick_sim_seconds=now_s,
        courier_position=o1,
        active_deliveries=[in_progress, queued],
        pending_orders={third_order["id"]: PendingOrder(order=third_order, evaluation=third_evaluation)},
    )
    from app.api.routes.session_store import get_session_store

    get_session_store().save(state)

    # --- El escenario realmente distingue los dos origenes candidatos ------
    rt = simulation.ShiftRuntime(
        state=state,
        graph=small_graph,
        restaurants=[],
        delivery_agent=DeliveryAgent(small_graph, vehicle=VehicleType.MOTO),
        novice_agent=NoviceAgent(small_graph, vehicle=VehicleType.MOTO),
    )
    live_position = simulation._courier_live_position(rt)
    future_free_position = simulation._next_free_position(rt)
    assert live_position != future_free_position, (
        "el escenario de prueba no separa los dos origenes candidatos; "
        "ajustar los tiempos/rutas para que si lo haga"
    )

    # --- El preview real usa la posicion EN VIVO, no la futura -------------
    preview = simulation.get_order_route(run_id=run_id, order_id=third_order["id"])

    courier_stop = preview.stops[0]
    assert courier_stop.kind == "courier"
    assert (courier_stop.lat, courier_stop.lon) == pytest.approx(live_position)
    assert (courier_stop.lat, courier_stop.lon) != pytest.approx(future_free_position)

    # La primera coordenada de la geometria dibujada tiene que arrancar CERCA
    # de la parada "courier" — no identica: `try_shortest_route` snapea el
    # origen exacto al nodo del grafo mas cercano (`ox.nearest_nodes`), asi
    # que un desvio de un par de cuadras es el comportamiento esperado, no un
    # bug. La tolerancia (~200m) es generosa para el radio de 600m del grafo
    # de prueba, pero seguiria detectando el bug real (arrancar del lado
    # equivocado de la ciudad, a cientos de metros de distancia).
    first_lon, first_lat = preview.coordinates[0]
    assert (first_lat, first_lon) == pytest.approx((courier_stop.lat, courier_stop.lon), abs=2e-3)
