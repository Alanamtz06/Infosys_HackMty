"""Carga del grafo vial de la ZMM usando OSMnx y aplicacion de pesos de trafico.

TODO: requiere `osmnx` y descarga de datos de OpenStreetMap (red o cache local .graphml).
"""

import networkx as nx
import osmnx as ox

from app.config import settings
from app.engine.traffic_rules import BASE_CITY_FRICTION, active_multiplier

# El grafo de la ZMM no cambia durante el turno; se descarga una sola vez por
# proceso porque la consulta a OSM/Overpass toma varios segundos.
_graph_cache: nx.MultiDiGraph | None = None


def load_graph(force_refresh: bool = False) -> nx.MultiDiGraph:
    global _graph_cache
    if _graph_cache is not None and not force_refresh:
        return _graph_cache

    graph = ox.graph_from_point(
        (settings.city_center_lat, settings.city_center_lon),
        dist=settings.city_radius_km * 1000,
        network_type="drive",
    )
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    for _, _, data in graph.edges(data=True):
        data["base_travel_time"] = data.get("travel_time", 1.0)

    _graph_cache = graph
    return graph


def apply_traffic(graph: nx.MultiDiGraph, virtual_hour: float) -> None:
    """Actualiza `travel_time` de cada arista segun la hora virtual y `traffic_rules`.

    Sobre el tiempo de flujo libre de OSMnx se aplica la friccion urbana de
    base (`BASE_CITY_FRICTION`, siempre) y, si la calle esta en una ventana
    de hora pico, el multiplicador de esa regla (el mayor si coincide varias).
    """
    for _, _, data in graph.edges(data=True):
        name = data.get("name")
        street_names = name if isinstance(name, list) else [name]
        multiplier = 1.0
        for street in street_names:
            if not street:
                continue
            multiplier = max(multiplier, active_multiplier(street, virtual_hour))
        data["travel_time"] = data["base_travel_time"] * BASE_CITY_FRICTION * multiplier
