"""Zonas nombradas de la ZMM para que el conductor compare ofertas por
vecindario ("hay 2 en Cumbres, 1 en Centro"), no solo como una lista plana.

No es un poligono real de colonias — cada pedido se etiqueta con la zona
cuyo CENTRO cae mas cerca de su punto de recogida (vecino mas cercano sobre
estos centros). Es la misma aproximacion que ya usa el resto del motor
(distancias great-circle en vez de limites administrativos reales) y alcanza
para el proposito: agrupar visualmente, no delimitar catastro.
"""

from dataclasses import dataclass

import osmnx as ox


@dataclass(frozen=True)
class Zone:
    name: str
    lat: float
    lon: float


# Centros aproximados de zonas reales de la ZMM. Elegidas dentro de un radio
# donde el generador de ordenes efectivamente coloca restaurantes (ver
# RESTAURANT_SEARCH_KM en agents/order_generator.py) — una zona fuera de ese
# alcance nunca ganaria el vecino-mas-cercano y sobraria en la lista.
ZONES: tuple[Zone, ...] = (
    Zone("Centro", 25.6702, -100.3099),
    Zone("Obispado", 25.6795, -100.3454),
    Zone("Del Valle", 25.6427, -100.3617),
    Zone("Contry", 25.6291, -100.2841),
    Zone("San Pedro", 25.6506, -100.4023),
    Zone("Cumbres", 25.7203, -100.3776),
    Zone("Guadalupe", 25.6773, -100.2597),
    Zone("San Nicolas", 25.7417, -100.3003),
)


def nearest_zone(lat: float, lon: float) -> str:
    """Nombre de la zona cuyo centro esta mas cerca de (lat, lon)."""
    best = min(ZONES, key=lambda z: ox.distance.great_circle(lat, lon, z.lat, z.lon))
    return best.name
