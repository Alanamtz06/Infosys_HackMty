"""Fixtures compartidos. El grafo de prueba es un radio chico (600m) real de
OSM alrededor del centro de la ZMM configurado en .env/config.py — no usa
`engine.graph_loader.load_graph()` a proposito, para no tocar su cache
global en memoria (compartido con el proceso de la app real) ni depender de
`city_radius_km` completo (8km, mucho mas lento de descargar).

Descarga una sola vez por sesion de pytest; las corridas siguientes usan el
cache en disco de OSMnx (`~/.cache/osmnx` por defecto).
"""

import pytest

from app.config import settings
from app.engine.graph_loader import apply_traffic


@pytest.fixture(scope="session")
def small_graph():
    import osmnx as ox

    graph = ox.graph_from_point(
        (settings.city_center_lat, settings.city_center_lon),
        dist=600,
        network_type="drive",
    )
    graph = ox.add_edge_speeds(graph)
    graph = ox.add_edge_travel_times(graph)
    for _, _, data in graph.edges(data=True):
        data["base_travel_time"] = data.get("travel_time", 1.0)
    apply_traffic(graph, virtual_hour=11.0)  # hora neutra, fuera de toda ventana de trafico pico
    return graph
