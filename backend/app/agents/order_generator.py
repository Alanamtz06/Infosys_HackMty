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
import osmnx as ox

from app.config import settings
from app.engine.pois import random_house_near

PEAK_HOURS = [(13.0, 15.0), (19.0, 22.0)]
PEAK_RATE_MULTIPLIER = 5.0

# --- Tarifas -----------------------------------------------------------------
# La plataforma paga por la distancia del PEDIDO (linea recta
# restaurante -> casa), no por lo que el repartidor tenga que recorrer para
# llegar a recoger. Ese tramo no pagado es justo la trampa real del trabajo:
# un pedido que paga bien pero cuyo restaurante esta del otro lado de la
# ciudad puede dejar Score negativo.
#
# Antes la tarifa era un uniforme(40, 120) sin relacion con la distancia, y
# con eso casi cualquier pedido dejaba Score positivo: "aceptar todo" era una
# estrategia decente y el agente inteligente no tenia nada que discriminar.
# Calibrado midiendo rutas reales sobre el grafo de la ZMM (ver el barrido en
# el README): con estos valores ~54% de las ofertas dejan Score positivo
# fuera de hora pico y ~83% durante el surge. Esa es la mezcla que le da algo
# que discriminar al agente — con tarifas mas generosas "aceptar todo" empata
# con cualquier estrategia, y con tarifas mas duras casi nada vale la pena.
BASE_FARE = 40.0
FARE_PER_KM = 8.0
FARE_NOISE = (0.8, 1.25)
PEAK_FARE_MULTIPLIER = 1.3  # surge en hora pico: mas ofertas se vuelven rentables

MIN_FARE = 32.0
MAX_FARE = 190.0

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


def fare_for_distance(delivery_km: float, virtual_hour: float) -> float:
    """Lo que paga la plataforma por un pedido de `delivery_km` (linea recta
    restaurante -> casa) a esta hora.

    Sublineal a proposito respecto del costo real del repartidor: crece con la
    distancia del pedido, pero nunca cubre el tramo de ir a recoger.
    """
    fare = (BASE_FARE + FARE_PER_KM * delivery_km) * random.uniform(*FARE_NOISE)
    if is_peak_hour(virtual_hour):
        fare *= PEAK_FARE_MULTIPLIER
    return round(min(max(fare, MIN_FARE), MAX_FARE), 2)


# Hasta que tan lejos del repartidor puede estar el restaurante de una oferta.
# Las plataformas ofrecen pedidos de la zona, no del otro lado de la ciudad —
# pero el rango es lo bastante amplio para que siga habiendo ofertas trampa
# (restaurante lejos = tramo no pagado que se come el Score).
RESTAURANT_SEARCH_KM = 6.0


def _restaurants_near(restaurants: list[dict], near_point: tuple[float, float]) -> list[dict]:
    lat, lon = near_point
    nearby = [
        r
        for r in restaurants
        if ox.distance.great_circle(lat, lon, r["lat"], r["lon"]) / 1000 <= RESTAURANT_SEARCH_KM
    ]
    return nearby or restaurants


def generate_order(
    graph: nx.MultiDiGraph,
    restaurants: list[dict],
    virtual_hour: float = 12.0,
    near_point: tuple[float, float] | None = None,
) -> dict:
    """Crea una orden: recogida en un restaurante real de OSM, entrega en una
    casa cercana a ese restaurante.

    `near_point` (donde esta o va a quedar el repartidor) sesga la oferta a
    restaurantes de su zona. Sin el, el restaurante sale de toda la ciudad.

    La tarifa sale de `fare_for_distance` sobre la distancia great-circle del
    pedido — un haversine, no un ruteo: esto corre dentro del tick de la
    simulacion y no puede pagar un A* solo para poner precio.
    """
    pool = _restaurants_near(restaurants, near_point) if near_point else restaurants
    restaurant = random.choice(pool)
    house_lat, house_lon = random_house_near(graph, restaurant["lat"], restaurant["lon"])

    delivery_km = (
        ox.distance.great_circle(restaurant["lat"], restaurant["lon"], house_lat, house_lon) / 1000
    )

    return {
        "id": str(uuid.uuid4()),
        "pickup_lat": restaurant["lat"],
        "pickup_lon": restaurant["lon"],
        "pickup_name": restaurant["name"],
        "dropoff_lat": house_lat,
        "dropoff_lon": house_lon,
        "fare": fare_for_distance(float(delivery_km), virtual_hour),
    }
