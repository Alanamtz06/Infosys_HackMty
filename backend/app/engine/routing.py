"""Calculo de rutas sobre el grafo afectado por trafico.

Usa A* (en vez del Dijkstra simple que habia antes) con una heuristica de
distancia great-circle sobre la velocidad maxima del grafo — una cota
inferior admisible del tiempo real, asi que A* sigue dando la ruta optima
pero explora muchos menos nodos que Dijkstra. Importa porque
`/simulation/state` se sondea cada 2s desde el frontend y cada tick puede
disparar un calculo de ruta nuevo.
"""

import random

import networkx as nx
import numpy as np
import osmnx as ox

# Cota superior de velocidad en la ZMM, usada solo para que la heuristica de
# A* nunca sobreestime el tiempo real (si sobreestimara, A* dejaria de ser
# optimo).
_MAX_SPEED_KPH = 110.0


def _travel_time_heuristic(graph: nx.MultiDiGraph, max_speed_kph: float = _MAX_SPEED_KPH):
    max_speed_mps = max_speed_kph * 1000 / 3600

    def heuristic(u, v) -> float:
        y1, x1 = graph.nodes[u]["y"], graph.nodes[u]["x"]
        y2, x2 = graph.nodes[v]["y"], graph.nodes[v]["x"]
        dist_m = ox.distance.great_circle(y1, x1, y2, x2)
        return dist_m / max_speed_mps

    return heuristic


def _path_time_and_distance(graph: nx.MultiDiGraph, route: list[int]) -> tuple[float, float]:
    travel_time = sum(
        min(d["travel_time"] for d in graph.get_edge_data(u, v).values()) for u, v in zip(route[:-1], route[1:])
    )
    distance = sum(
        min(d["length"] for d in graph.get_edge_data(u, v).values()) for u, v in zip(route[:-1], route[1:])
    )
    return travel_time, distance


def shortest_route(graph: nx.MultiDiGraph, origin_point: tuple[float, float], dest_point: tuple[float, float]):
    """Devuelve (nodos_de_ruta, tiempo_total_seg, distancia_total_m) usando A* sobre `travel_time`.

    Lanza `networkx.NetworkXNoPath` si un cierre de calle (ver
    `apply_road_closure`) deja a `dest_point` inalcanzable desde `origin_point`.
    """
    origin_node = ox.nearest_nodes(graph, origin_point[1], origin_point[0])
    dest_node = ox.nearest_nodes(graph, dest_point[1], dest_point[0])

    route = nx.astar_path(graph, origin_node, dest_node, heuristic=_travel_time_heuristic(graph), weight="travel_time")
    travel_time, distance = _path_time_and_distance(graph, route)
    return route, travel_time, distance


def get_travel_time_matrix(graph: nx.MultiDiGraph, points: list[tuple[float, float]]) -> np.ndarray:
    """Matriz NxN de tiempos de viaje (segundos) entre `points` (lat, lon).

    Pensada como input directo para `decision.vrptw_solver.solve_route`
    (capa de batching): cada `points[i]` se snapea al nodo del grafo mas
    cercano una sola vez, y la diagonal es 0. `float('inf')` si un cierre de
    calle deja un par sin ruta.
    """
    nodes = [ox.nearest_nodes(graph, lon, lat) for lat, lon in points]
    heuristic = _travel_time_heuristic(graph)

    n = len(nodes)
    matrix = np.zeros((n, n))
    for i, origin in enumerate(nodes):
        for j, dest in enumerate(nodes):
            if i == j:
                continue
            try:
                matrix[i, j] = nx.astar_path_length(graph, origin, dest, heuristic=heuristic, weight="travel_time")
            except nx.NetworkXNoPath:
                matrix[i, j] = float("inf")
    return matrix


def apply_road_closure(graph: nx.MultiDiGraph, u: int, v: int) -> None:
    """Simula el cierre de una calle: pone `travel_time` (y `base_travel_time`,
    para que sobreviva al siguiente `apply_traffic`) de `(u, v)` en infinito.

    Cierra tambien las aristas paralelas si las hay (MultiDiGraph). Si hay
    una ruta alterna, `shortest_route`/A* la usa automaticamente en la
    siguiente consulta.
    """
    if not graph.has_edge(u, v):
        raise ValueError(f"No existe arista ({u}, {v}) en el grafo")
    for _key, data in graph[u][v].items():
        data["base_travel_time"] = float("inf")
        data["travel_time"] = float("inf")


def clear_road_closure(graph: nx.MultiDiGraph, u: int, v: int) -> None:
    """Reabre una calle cerrada con `apply_road_closure`, recalculando su
    `base_travel_time` real a partir de `length`/`speed_kph`."""
    if not graph.has_edge(u, v):
        return
    for _key, data in graph[u][v].items():
        speed_kph = data.get("speed_kph")
        length_m = data.get("length")
        if speed_kph and length_m:
            data["base_travel_time"] = length_m / (speed_kph * 1000 / 3600)
        data["travel_time"] = data["base_travel_time"]


def simulate_random_closure(graph: nx.MultiDiGraph, near_point: tuple[float, float] | None = None) -> dict | None:
    """Cierra una calle real al azar (opcionalmente cerca de `near_point`) para
    la demo de "God Mode" — un accidente/obra que fuerza un desvio a mitad
    de turno.

    Devuelve `{"u", "v", "street_name"}` de lo que se cerro, o `None` si no
    se encontro ninguna arista candidata (grafo vacio). Guarda ese dict y
    pasalo a `clear_road_closure(graph, closure["u"], closure["v"])` despues
    para reabrir la calle.
    """
    if near_point is not None:
        center_node = ox.nearest_nodes(graph, near_point[1], near_point[0])
        candidates = list(graph.out_edges(center_node, keys=False))
        # si el nodo mas cercano no tiene salidas utiles, cae al azar sobre todo el grafo
        if not candidates:
            candidates = list(graph.edges(keys=False))
    else:
        candidates = list(graph.edges(keys=False))

    # evita cerrar una arista que ya esta cerrada (travel_time infinito)
    open_candidates = [
        (u, v) for u, v in candidates if all(d.get("travel_time", 0) != float("inf") for d in graph[u][v].values())
    ]
    if not open_candidates:
        return None

    u, v = random.choice(open_candidates)
    street_name = None
    for data in graph[u][v].values():
        name = data.get("name")
        street_name = name[0] if isinstance(name, list) and name else (name if isinstance(name, str) else None)
        if street_name:
            break

    apply_road_closure(graph, u, v)
    return {"u": u, "v": v, "street_name": street_name}
