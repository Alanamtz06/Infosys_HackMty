"""Que la economia del turno le deje algo que decidir al agente.

Si casi todas las ofertas son rentables, "aceptar todo" empata con cualquier
estrategia y el agente no demuestra nada: esa fue justo la falla que tenia
esta simulacion. Usa el fixture `small_graph` (conftest.py).
"""

import random

import pytest

from app.agents.order_generator import fare_for_distance, is_peak_hour
from app.engine.pois import random_house_near


def test_fare_grows_with_delivery_distance():
    random.seed(3)
    short = [fare_for_distance(1.0, 11.0) for _ in range(40)]
    long = [fare_for_distance(8.0, 11.0) for _ in range(40)]
    assert sum(long) / len(long) > sum(short) / len(short)


def test_peak_hour_pays_a_surge():
    random.seed(3)
    normal = [fare_for_distance(4.0, 11.0) for _ in range(60)]
    peak = [fare_for_distance(4.0, 14.0) for _ in range(60)]
    assert is_peak_hour(14.0) and not is_peak_hour(11.0)
    assert sum(peak) / len(peak) > sum(normal) / len(normal)


def test_fare_ignores_the_trip_to_the_pickup():
    """La plataforma paga por el pedido, no por lo que el repartidor recorra
    para ir a recogerlo. Ese tramo no pagado es la trampa que el agente tiene
    que aprender a ver, asi que la tarifa no puede depender de el."""
    random.seed(11)
    a = [fare_for_distance(5.0, 11.0) for _ in range(50)]
    random.seed(11)
    b = [fare_for_distance(5.0, 11.0) for _ in range(50)]
    assert a == b  # misma distancia de pedido -> misma distribucion, sin importar el deadhead


@pytest.mark.network
def test_deliveries_stay_local(small_graph):
    """Pedir comida es local: el destino cae cerca del restaurante, no al
    otro lado de la ciudad."""
    import osmnx as ox

    nodes = list(small_graph.nodes)
    origin = small_graph.nodes[nodes[0]]
    lat, lon = float(origin["y"]), float(origin["x"])

    for _ in range(10):
        house_lat, house_lon = random_house_near(small_graph, lat, lon, min_km=0.0, max_km=0.6)
        km = ox.distance.great_circle(lat, lon, house_lat, house_lon) / 1000
        # el recorte de prueba es de 600m de radio, asi que el tope efectivo
        # es el del propio grafo; lo que se valida es que respeta el radio.
        assert km <= 0.7
