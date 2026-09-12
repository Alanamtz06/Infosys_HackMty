"""Puntos de interes de OpenStreetMap usados como origen de las ordenes.

Trae restaurantes/cafes/comida rapida reales (amenity=restaurant|fast_food|cafe)
dentro del radio de la simulacion via osmnx (Overpass por debajo). Requiere
acceso a internet la primera vez, igual que app.engine.graph_loader.load_graph.
"""

import random

import networkx as nx
import numpy as np
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


# Coordenadas de los nodos en arreglos de numpy, para poder filtrar por radio
# sin recorrer el grafo entero en cada orden. El grafo es un singleton por
# proceso (graph_loader lo cachea), asi que basta cachear por id().
_node_coords_cache: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}


def _node_coords(graph: nx.MultiDiGraph) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    key = id(graph)
    cached = _node_coords_cache.get(key)
    if cached is not None:
        return cached

    node_ids = np.fromiter(graph.nodes, dtype=np.int64, count=graph.number_of_nodes())
    lats = np.array([graph.nodes[n]["y"] for n in node_ids], dtype=np.float64)
    lons = np.array([graph.nodes[n]["x"] for n in node_ids], dtype=np.float64)

    coords = (node_ids, lats, lons)
    _node_coords_cache[key] = coords
    return coords


def random_house_near(
    graph: nx.MultiDiGraph,
    lat: float,
    lon: float,
    min_km: float = 0.5,
    max_km: float = 4.5,
) -> tuple[float, float]:
    """Elige una 'casa' dentro de un radio del restaurante.

    Pedir comida es local: uno ordena del restaurante que tiene cerca, no de
    uno al otro lado de la ciudad. Antes el destino era un nodo cualquiera
    del radio completo de la simulacion (8 km), asi que el pedido promedio
    cruzaba la ZMM: ~18 km y 45 minutos por entrega, con lo que un turno de 8
    horas apenas daba para 10 pedidos y las ganancias por hora no se parecian
    a las de un repartidor real.

    Si no hay ningun nodo en el anillo (un restaurante en la orilla del
    grafo), cae a `random_house`.
    """
    node_ids, lats, lons = _node_coords(graph)

    # Prefiltro por caja: convertir grados a km es barato y descarta casi todo
    # antes de calcular distancias reales.
    deg = max_km / 111.0
    box = (np.abs(lats - lat) <= deg) & (np.abs(lons - lon) <= deg / max(np.cos(np.radians(lat)), 0.1))
    if not box.any():
        return random_house(graph)

    candidate_lats = lats[box]
    candidate_lons = lons[box]
    distances_km = ox.distance.great_circle(lat, lon, candidate_lats, candidate_lons) / 1000

    ring = (distances_km >= min_km) & (distances_km <= max_km)
    if not ring.any():
        return random_house(graph)

    index = random.randrange(int(ring.sum()))
    return float(candidate_lats[ring][index]), float(candidate_lons[ring][index])
