"""Agente generador de ordenes: crea pedidos esporadicos con origen en un
restaurante real de OpenStreetMap y destino ("casa") aleatorio sobre el grafo vial.

La probabilidad de generar una orden aumenta en horarios clave (comida, noche).

La generacion es proporcional al tiempo SIMULADO transcurrido (ver
`orders_to_generate`), no a cada request del frontend: el reloj del mundo
corre acelerado y el frontend sondea cada 2s, asi que atar la generacion al
poll haria que la demanda dependiera de la frecuencia de sondeo en vez de
del reloj.

TODO: calibrar las curvas de probabilidad segun datos reales de demanda.
"""

import math
import random
import uuid

import networkx as nx

from app.config import settings
from app.engine.pois import random_house

PEAK_HOURS = [(13.0, 15.0), (19.0, 22.0)]
PEAK_RATE_MULTIPLIER = 5.0

MIN_FARE = 40.0
MAX_FARE = 120.0

# Tope de seguridad: por muy largo que sea el salto de tiempo simulado entre
# dos ticks (p.ej. si el servidor se quedo sin sondear un rato), nunca se
# generan mas de estas ordenes de golpe.
MAX_ORDERS_PER_TICK = 3


def is_peak_hour(virtual_hour: float) -> bool:
    return any(start <= virtual_hour <= end for start, end in PEAK_HOURS)


def orders_per_sim_hour(virtual_hour: float) -> float:
    """Ordenes esperadas por hora simulada a esta hora del dia."""
    rate = settings.orders_per_sim_hour
    return rate * PEAK_RATE_MULTIPLIER if is_peak_hour(virtual_hour) else rate


def orders_to_generate(virtual_hour: float, sim_minutes_elapsed: float) -> int:
    """Cuantas ordenes aparecen en un tramo de `sim_minutes_elapsed` minutos simulados.

    Proceso de Poisson con media `lambda = tasa_por_hora * horas_transcurridas`,
    muestreado con el algoritmo de Knuth. Que sea Poisson (y no "una moneda
    por tick") es lo que hace que la demanda dependa del tiempo simulado y no
    de cada cuanto pregunte el frontend.
    """
    if sim_minutes_elapsed <= 0:
        return 0

    lam = orders_per_sim_hour(virtual_hour) * (sim_minutes_elapsed / 60)
    if lam <= 0:
        return 0

    # Knuth: multiplica uniformes hasta cruzar e^-lambda.
    limit = math.exp(-min(lam, 50))  # el clamp evita underflow con lambdas absurdos
    count = 0
    product = random.random()
    while product > limit and count < MAX_ORDERS_PER_TICK:
        count += 1
        product *= random.random()
    return count


def order_probability(virtual_hour: float) -> float:
    """Compat: probabilidad de una orden en un minuto simulado."""
    return 1 - math.exp(-orders_per_sim_hour(virtual_hour) / 60)


def maybe_generate_order(virtual_hour: float, sim_minutes_elapsed: float = 1.0) -> bool:
    return orders_to_generate(virtual_hour, sim_minutes_elapsed) > 0


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
