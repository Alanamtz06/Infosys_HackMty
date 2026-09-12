"""Agente generador de ordenes: crea pedidos esporadicos con origen en un
restaurante real de OpenStreetMap y destino ("casa") aleatorio sobre el grafo vial.

La probabilidad de generar una orden aumenta en horarios clave (comida, noche).
TODO: calibrar las curvas de probabilidad segun datos reales de demanda.
"""

import random
import uuid

import networkx as nx

from app.engine.pois import random_house

PEAK_HOURS = [(13.0, 15.0), (19.0, 22.0)]
BASE_ORDER_PROBABILITY = 0.05
PEAK_ORDER_PROBABILITY = 0.25

MIN_FARE = 40.0
MAX_FARE = 120.0


def order_probability(virtual_hour: float) -> float:
    for start, end in PEAK_HOURS:
        if start <= virtual_hour <= end:
            return PEAK_ORDER_PROBABILITY
    return BASE_ORDER_PROBABILITY


def maybe_generate_order(virtual_hour: float) -> bool:
    return random.random() < order_probability(virtual_hour)


def generate_order(graph: nx.MultiDiGraph, restaurants: list[dict]) -> dict:
    """Crea una orden: recogida en un restaurante real de OSM, entrega en una
    casa aleatoria (nodo del grafo vial)."""
    restaurant = random.choice(restaurants)
    house_lat, house_lon = random_house(graph)
    return {
        "id": str(uuid.uuid4()),
        "pickup_lat": restaurant["lat"],
        "pickup_lon": restaurant["lon"],
        "pickup_name": restaurant["name"],
        "dropoff_lat": house_lat,
        "dropoff_lon": house_lon,
        "fare": round(random.uniform(MIN_FARE, MAX_FARE), 2),
    }
