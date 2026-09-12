"""Puntos de interes de OpenStreetMap usados como origen de las ordenes.

Trae restaurantes/cafes/comida rapida reales (amenity=restaurant|fast_food|cafe)
dentro del radio de la simulacion via osmnx (Overpass por debajo). Requiere
acceso a internet la primera vez, igual que app.engine.graph_loader.load_graph.
"""

import random

import networkx as nx
import osmnx as ox

from app.config import settings

RESTAURANT_TAGS = {"amenity": ["restaurant", "fast_food", "cafe"]}

# Igual que el grafo vial, los restaurantes no cambian durante el turno.
_restaurant_cache: list[dict] | None = None


def load_restaurants(force_refresh: bool = False) -> list[dict]:
    global _restaurant_cache
    if _restaurant_cache is not None and not force_refresh:
        return _restaurant_cache

    gdf = ox.features_from_point(
        (settings.city_center_lat, settings.city_center_lon),
        tags=RESTAURANT_TAGS,
        dist=settings.city_radius_km * 1000,
    )

    restaurants: list[dict] = []
    for osm_id, row in gdf.iterrows():
        centroid = row.geometry.centroid
        name = row.get("name")
        restaurants.append(
            {
                "osm_id": "/".join(str(part) for part in osm_id) if isinstance(osm_id, tuple) else str(osm_id),
                "name": name if isinstance(name, str) and name else "Restaurante sin nombre",
                "lat": centroid.y,
                "lon": centroid.x,
            }
        )

    if not restaurants:
        raise RuntimeError(
            "No se encontraron restaurantes en OSM para el radio configurado "
            "(CITY_CENTER_LAT/LON, CITY_RADIUS_KM en .env)"
        )

    _restaurant_cache = restaurants
    return restaurants


def random_house(graph: nx.MultiDiGraph) -> tuple[float, float]:
    """Elige un nodo aleatorio del grafo vial como 'casa' (destino de la orden)."""
    node_id = random.choice(list(graph.nodes))
    node = graph.nodes[node_id]
    return node["y"], node["x"]
