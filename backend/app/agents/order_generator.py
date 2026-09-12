"""Agente generador de ordenes: crea pedidos esporadicos.

La probabilidad de generar una orden aumenta en horarios clave (comida, noche).
TODO: calibrar las curvas de probabilidad y los puntos de origen/destino
sobre el grafo real de la ZMM.
"""

import random


PEAK_HOURS = [(13.0, 15.0), (19.0, 22.0)]
BASE_ORDER_PROBABILITY = 0.05
PEAK_ORDER_PROBABILITY = 0.25


def order_probability(virtual_hour: float) -> float:
    for start, end in PEAK_HOURS:
        if start <= virtual_hour <= end:
            return PEAK_ORDER_PROBABILITY
    return BASE_ORDER_PROBABILITY


def maybe_generate_order(virtual_hour: float) -> bool:
    return random.random() < order_probability(virtual_hour)
