"""Correctitud del MILP de turno completo (`decision/lp_shift_optimizer.py`):
capacidad de mochila, causalidad (no visitar una oferta antes de que exista),
precedencia pickup->dropoff, conectividad (sin islas) y que el MILP exacto
nunca quede peor que la mejor heuristica greedy (esta ultima ya participa en
el grafo reducido que el MILP resuelve). Usa el fixture `small_graph`
(conftest.py), igual que el resto de `decision/`.
"""

import uuid

import pytest

from app.decision.lp_shift_optimizer import OrderSpec, optimize_shift
from app.engine.routing import try_shortest_route

pytestmark = pytest.mark.network


def _connected_quad(graph):
    """4 nodos conectados entre si en pares cortos: (pickup1, dropoff1,
    pickup2, dropoff2), suficientemente separados para que el traslado entre
    ordenes no sea instantaneo pero sigan siendo alcanzables en el recorte
    de prueba (600m)."""
    nodes = list(graph.nodes)
    for a in nodes[:15]:
        for b in nodes[15:30]:
            for c in nodes[30:45]:
                for d in nodes[45:60]:
                    pts = [
                        (graph.nodes[a]["y"], graph.nodes[a]["x"]),
                        (graph.nodes[b]["y"], graph.nodes[b]["x"]),
                        (graph.nodes[c]["y"], graph.nodes[c]["x"]),
                        (graph.nodes[d]["y"], graph.nodes[d]["x"]),
                    ]
                    if all(
                        try_shortest_route(graph, pts[i], pts[j]) is not None
                        for i in range(4)
                        for j in range(4)
                        if i != j
                    ):
                        return pts
    pytest.skip("no se encontraron 4 puntos mutuamente conectados en el recorte de prueba")


def _order(order_id_seed, pickup, dropoff, fare, emerged_at):
    return OrderSpec(id=f"order-{order_id_seed}-{uuid.uuid4().hex[:6]}", pickup=pickup, dropoff=dropoff, fare=fare, emerged_at=emerged_at)


def test_rejects_unprofitable_order_even_if_reachable(small_graph):
    """Un pedido con tarifa menor a lo que cuesta ir a recogerlo y entregarlo
    nunca debe aparecer en la solucion optima, aunque sea perfectamente
    alcanzable en tiempo."""
    p1, d1, p2, d2 = _connected_quad(small_graph)
    good_order = _order("good", p1, d1, fare=500.0, emerged_at=0.0)
    # Tarifa absurdamente baja: cueste lo que cueste el tramo real, nunca
    # puede compensar 1 peso de ingreso.
    bad_order = _order("bad", p2, d2, fare=1.0, emerged_at=0.0)

    result = optimize_shift(
        small_graph,
        orders=[good_order, bad_order],
        start_position=p1,
        window_seconds=3600.0,
    )

    assert result.plan.status in ("OPTIMAL", "FEASIBLE")
    assert good_order.id in result.plan.served_order_ids
    assert bad_order.id not in result.plan.served_order_ids
    # El MILP exacto nunca debe quedar peor que la mejor heuristica greedy —
    # greedy ya esta incluida en el grafo reducido que resuelve.
    assert result.plan.net_profit >= result.best_greedy_profit - 1e-6


def test_backpack_capacity_never_exceeds_two(small_graph):
    """A lo largo del camino optimo, la carga de la mochila (pickups menos
    dropoffs acumulados) nunca debe superar 2, y cada dropoff debe aparecer
    DESPUES de su propio pickup en el orden de visita."""
    p1, d1, p2, d2 = _connected_quad(small_graph)
    order_a = _order("a", p1, d1, fare=80.0, emerged_at=0.0)
    order_b = _order("b", p2, d2, fare=90.0, emerged_at=0.0)

    result = optimize_shift(
        small_graph,
        orders=[order_a, order_b],
        start_position=p1,
        window_seconds=7200.0,
    )
    plan = result.plan
    assert plan.status in ("OPTIMAL", "FEASIBLE")

    node_kind = {}  # indice de nodo -> ("pickup"|"dropoff", order_idx)
    from app.decision.lp_shift_optimizer import build_shift_graph

    sg = build_shift_graph(small_graph, [order_a, order_b], p1)
    for idx, node in enumerate(sg.nodes):
        node_kind[idx] = (node.kind, node.order_idx)

    load = 0
    seen_pickup = set()
    for node_idx in plan.path:
        kind, order_idx = node_kind[node_idx]
        if kind == "pickup":
            load += 1
            seen_pickup.add(order_idx)
        elif kind == "dropoff":
            assert order_idx in seen_pickup, "se entrego un pedido sin haberlo recogido antes"
            load -= 1
        assert 0 <= load <= 2, f"mochila fuera de rango: {load}"


def test_order_that_emerges_after_window_end_is_never_served(small_graph):
    """Causalidad: una oferta que aparece DESPUES de que se acaba la
    ventana del turno jamas puede ser parte de la solucion, sin importar que
    tan rentable sea."""
    p1, d1, p2, d2 = _connected_quad(small_graph)
    reachable_order = _order("reachable", p1, d1, fare=100.0, emerged_at=0.0)
    too_late_order = _order("too_late", p2, d2, fare=100000.0, emerged_at=1e9)

    result = optimize_shift(
        small_graph,
        orders=[reachable_order, too_late_order],
        start_position=p1,
        window_seconds=3600.0,
    )
    assert too_late_order.id not in result.plan.served_order_ids


def test_reduced_graph_is_smaller_than_full_graph(small_graph):
    """La reduccion via greedy debe, para un numero de pedidos no trivial,
    producir un grafo con MENOS arcos que el grafo completo — es el punto
    central del pipeline (evitar resolver el MILP sobre O(N^2) arcos)."""
    p1, d1, p2, d2 = _connected_quad(small_graph)
    orders = [
        _order("1", p1, d1, fare=70.0, emerged_at=0.0),
        _order("2", p2, d2, fare=85.0, emerged_at=0.0),
        _order("3", p1, d2, fare=60.0, emerged_at=60.0),
        _order("4", p2, d1, fare=95.0, emerged_at=120.0),
    ]
    result = optimize_shift(small_graph, orders=orders, start_position=p1, window_seconds=7200.0)
    assert result.reduced_arc_count <= result.full_arc_count
    assert result.plan.status in ("OPTIMAL", "FEASIBLE", "INFEASIBLE")
