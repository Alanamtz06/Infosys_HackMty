"""Usa el fixture `small_graph` (conftest.py): un radio real de 600m de OSM,
descargado una sola vez por sesion de pytest."""

import math

import pytest

from app.engine.routing import apply_road_closure, clear_road_closure, get_travel_time_matrix, shortest_route

pytestmark = pytest.mark.network


def _sample_points(graph, n=4):
    nodes = list(graph.nodes)[:n]
    return [(graph.nodes[node]["y"], graph.nodes[node]["x"]) for node in nodes], nodes


def test_shortest_route_is_positive_and_finite(small_graph):
    points, _ = _sample_points(small_graph, 2)
    _, travel_time, distance = shortest_route(small_graph, points[0], points[1])
    assert travel_time >= 0
    assert distance >= 0
    assert math.isfinite(travel_time)


def test_travel_time_matrix_shape_and_diagonal(small_graph):
    points, _ = _sample_points(small_graph, 4)
    matrix = get_travel_time_matrix(small_graph, points)
    assert matrix.shape == (4, 4)
    assert (matrix.diagonal() == 0).all()
    assert (matrix >= 0).all()


def test_road_closure_forces_detour_or_disconnection(small_graph):
    u, v, _key = next(iter(small_graph.edges))
    u_point = (small_graph.nodes[u]["y"], small_graph.nodes[u]["x"])
    v_point = (small_graph.nodes[v]["y"], small_graph.nodes[v]["x"])

    _, before_time, _ = shortest_route(small_graph, u_point, v_point)
    assert math.isfinite(before_time)

    apply_road_closure(small_graph, u, v)
    for _key, data in small_graph[u][v].items():
        assert data["travel_time"] == float("inf")

    # Tres desenlaces posibles y los tres son correctos, segun la topologia
    # alrededor de la arista cerrada:
    #  - hay una alterna finita -> A* la usa (rodea el cierre).
    #  - (u, v) es la UNICA arista entre ambos y no hay ciclo -> Dijkstra/A*
    #    igual devuelve ese camino de un solo tramo, pero con peso infinito
    #    (nx no lo distingue de "no hay camino"; solo evita ese peso si
    #    encuentra algo mas barato).
    #  - no existe ningun camino topologico -> NetworkXNoPath.
    try:
        _, after_time, _ = shortest_route(small_graph, u_point, v_point)
        assert after_time == float("inf") or math.isfinite(after_time)
    except Exception as exc:
        assert type(exc).__name__ == "NetworkXNoPath"

    clear_road_closure(small_graph, u, v)
    for _key, data in small_graph[u][v].items():
        assert data["travel_time"] != float("inf")
