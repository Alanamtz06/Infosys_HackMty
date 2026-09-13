"""Movimiento continuo del repartidor y manejo de rutas inalcanzables.

Usa el fixture `small_graph` (conftest.py).
"""

import pytest

from app.engine.routing import (
    apply_road_closure,
    clear_road_closure,
    position_along_route,
    route_total_time,
    try_shortest_route,
)

pytestmark = pytest.mark.network


def _two_connected_points(graph):
    """Dos puntos del grafo con ruta entre ellos (y la ruta)."""
    nodes = list(graph.nodes)
    for origin in nodes[:40]:
        for dest in nodes[-40:]:
            if origin == dest:
                continue
            o = (graph.nodes[origin]["y"], graph.nodes[origin]["x"])
            d = (graph.nodes[dest]["y"], graph.nodes[dest]["x"])
            found = try_shortest_route(graph, o, d)
            if found is not None and len(found[0]) > 3:
                return o, d, found[0]
    pytest.skip("no se encontro un par conectado en el recorte de grafo de prueba")


def test_position_advances_along_the_route(small_graph):
    _origin, _dest, route = _two_connected_points(small_graph)
    total = route_total_time(small_graph, route)
    assert total > 0

    start = position_along_route(small_graph, route, 0)
    middle = position_along_route(small_graph, route, total / 2)
    end = position_along_route(small_graph, route, total)

    assert start != middle
    assert middle != end
    # el final de la interpolacion coincide con el ultimo nodo de la ruta
    last = small_graph.nodes[route[-1]]
    assert end == pytest.approx((last["y"], last["x"]))


def test_position_is_clamped_past_the_end(small_graph):
    _origin, _dest, route = _two_connected_points(small_graph)
    total = route_total_time(small_graph, route)
    assert position_along_route(small_graph, route, total * 5) == position_along_route(small_graph, route, total)


def test_dwell_checkpoint_pauses_at_the_stop_not_at_the_end(small_graph):
    """Regresion: el tiempo de servicio (esperar la comida) debe congelar al
    repartidor en el PICKUP, no en el ultimo nodo de la ruta. Antes de este
    fix, `elapsed_seconds` (que incluye el tiempo de servicio via
    `total_seconds`) se salia del presupuesto fisico de `route` y
    `position_along_route` devolvia siempre el ultimo nodo durante ese tiempo
    de mas — el repartidor se congelaba en el DESTINO en vez de en el
    origen/pickup, y "reaparecia" avanzando mucho rato despues (se leia como
    un teletransporte)."""
    _origin, _dest, route = _two_connected_points(small_graph)
    total = route_total_time(small_graph, route)
    dwell_seconds = 480.0
    # El checkpoint coincide EXACTO con la llegada a un nodo intermedio (no un
    # total/2 arbitrario que podria caer a mitad de una arista): el
    # repartidor deberia llegar ahi, congelarse `dwell_seconds`, y solo
    # despues seguir avanzando.
    checkpoint_node_idx = len(route) // 2
    checkpoint_time = route_total_time(small_graph, route[: checkpoint_node_idx + 1])
    assert 0 < checkpoint_time < total
    checkpoints = [(checkpoint_time, dwell_seconds)]

    at_checkpoint = position_along_route(small_graph, route, checkpoint_time, checkpoints)
    # Durante toda la pausa, la posicion no debe moverse del punto del checkpoint.
    mid_dwell = position_along_route(small_graph, route, checkpoint_time + dwell_seconds / 2, checkpoints)
    assert mid_dwell == at_checkpoint

    # Elapsed = tiempo fisico total + la pausa completa: SIN dwell_checkpoints
    # esto quedaria clavado en el ULTIMO nodo (el bug); CON el checkpoint,
    # debe reflejar solo el tiempo fisico ya consumido (checkpoint_time),
    # osea seguir en el punto de la pausa apenas se cumple el dwell exacto.
    right_after_dwell = position_along_route(small_graph, route, checkpoint_time + dwell_seconds, checkpoints)
    assert right_after_dwell == at_checkpoint

    # Y con tiempo de sobra despues del dwell, si avanza mas alla del checkpoint.
    after_dwell_and_more = position_along_route(
        small_graph, route, checkpoint_time + dwell_seconds + (total - checkpoint_time), checkpoints
    )
    last = small_graph.nodes[route[-1]]
    assert after_dwell_and_more == pytest.approx((last["y"], last["x"]))


def test_position_returns_plain_floats(small_graph):
    """Los atributos del grafo son numpy.float64; si se filtran, Pydantic
    serializa con DeprecationWarning."""
    _origin, _dest, route = _two_connected_points(small_graph)
    lat, lon = position_along_route(small_graph, route, 1.0)
    assert type(lat) is float
    assert type(lon) is float


def test_try_shortest_route_returns_none_when_unreachable(small_graph):
    """Un cierre de calle no debe propagar excepciones al tick de la simulacion."""
    leaves = [n for n in small_graph.nodes if small_graph.out_degree(n) == 1 and small_graph.in_degree(n) <= 1]
    if not leaves:
        pytest.skip("el recorte de grafo no tiene nodos hoja")
    leaf = leaves[0]
    preds = list(small_graph.predecessors(leaf))
    if not preds:
        pytest.skip("el nodo hoja no tiene predecesor")
    pred = preds[0]

    origin = (small_graph.nodes[pred]["y"], small_graph.nodes[pred]["x"])
    dest = (small_graph.nodes[leaf]["y"], small_graph.nodes[leaf]["x"])
    assert try_shortest_route(small_graph, origin, dest) is not None

    apply_road_closure(small_graph, pred, leaf)
    try:
        assert try_shortest_route(small_graph, origin, dest) is None
    finally:
        clear_road_closure(small_graph, pred, leaf)
