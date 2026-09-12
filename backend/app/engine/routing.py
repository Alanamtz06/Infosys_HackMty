"""Calculo de rutas sobre el grafo afectado por trafico (A* / Dijkstra)."""

import networkx as nx
import osmnx as ox


def shortest_route(graph: nx.MultiDiGraph, origin_point: tuple[float, float], dest_point: tuple[float, float]):
    """Devuelve (nodos_de_ruta, tiempo_total_seg, distancia_total_m) usando Dijkstra sobre `travel_time`."""
    origin_node = ox.nearest_nodes(graph, origin_point[1], origin_point[0])
    dest_node = ox.nearest_nodes(graph, dest_point[1], dest_point[0])

    route = nx.shortest_path(graph, origin_node, dest_node, weight="travel_time")

    travel_time = sum(
        min(d["travel_time"] for d in graph.get_edge_data(u, v).values())
        for u, v in zip(route[:-1], route[1:])
    )
    distance = sum(
        min(d["length"] for d in graph.get_edge_data(u, v).values())
        for u, v in zip(route[:-1], route[1:])
    )
    return route, travel_time, distance
