"""Reglas de congestion vial para la ZMM (Zona Metropolitana de Monterrey).

Cada regla incrementa el peso de las aristas del grafo OSMnx cuyo nombre de via
coincide con `street_names` durante la ventana horaria indicada. `bearing_filter`
se usa para distinguir sentido (oriente/poniente/norte/sur) cuando aplica.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrafficRule:
    street_names: tuple[str, ...]
    direction: str  # descripcion del sentido, informativa
    start_hour: float
    end_hour: float
    weight_multiplier: float
    congestion_level: str


# Friccion urbana de base, aplicada a TODA arista a cualquier hora.
#
# `ox.add_edge_travel_times` calcula tiempo de flujo libre: longitud entre
# velocidad maxima permitida, sin semaforos, sin vueltas, sin topes, sin
# buscar donde estacionarse. Con eso un repartidor cruzaba la ZMM a ~57 km/h
# de promedio, que no es una velocidad de reparto real (un repartidor en moto
# en ciudad promedia mas bien 20-30 km/h puerta a puerta).
#
# Este factor NO reemplaza las reglas por avenida de abajo: se multiplica
# antes que ellas. 2.0 deja el promedio en ~28 km/h fuera de hora pico.
BASE_CITY_FRICTION = 2.0


TRAFFIC_RULES: list[TrafficRule] = [
    TrafficRule(("Paseo de los Leones",), "Hacia Gonzalitos (Oriente)", 7.0, 9.5, 3.0, "Critico"),
    TrafficRule(("Paseo de los Leones",), "Hacia Cumbres (Poniente)", 17.5, 20.5, 3.0, "Critico"),
    TrafficRule(("Avenida Gonzalitos", "Av. Gonzalitos"), "Ambos sentidos", 7.0, 9.5, 3.0, "Severo"),
    TrafficRule(("Avenida Gonzalitos", "Av. Gonzalitos"), "Ambos sentidos", 17.0, 20.5, 3.0, "Severo"),
    TrafficRule(("Avenida Constitucion", "Av. Constitucion"), "Hacia el Centro (Oriente)", 7.0, 9.5, 3.0, "Severo"),
    TrafficRule(("Avenida Constitucion", "Av. Constitucion"), "Hacia el Centro (Oriente)", 18.0, 20.0, 3.0, "Severo"),
    TrafficRule(("Avenida Morones Prieto", "Av. Morones Prieto"), "Hacia San Pedro (Poniente)", 7.5, 9.5, 3.0, "Severo"),
    TrafficRule(("Avenida Morones Prieto", "Av. Morones Prieto"), "Hacia San Pedro (Poniente)", 17.5, 20.5, 3.0, "Severo"),
    TrafficRule(("Avenida Eugenio Garza Sada", "Av. Garza Sada"), "Hacia el Centro (Norte)", 7.0, 9.0, 3.0, "Alto"),
    TrafficRule(("Avenida Eugenio Garza Sada", "Av. Garza Sada"), "Hacia Carretera Nacional (Sur)", 17.5, 20.5, 3.0, "Critico"),
    TrafficRule(("Avenida Universidad", "Av. Universidad"), "Hacia Monterrey (Sur)", 7.0, 9.0, 3.0, "Alto"),
    TrafficRule(("Avenida Universidad", "Av. Universidad"), "Hacia San Nicolas (Norte)", 17.5, 20.0, 3.0, "Alto"),
]


def active_multiplier(street_name: str, virtual_hour: float) -> float:
    """Devuelve el multiplicador de peso vigente para una calle a la hora dada."""
    multiplier = 1.0
    for rule in TRAFFIC_RULES:
        if street_name not in rule.street_names:
            continue
        if rule.start_hour <= virtual_hour <= rule.end_hour:
            multiplier = max(multiplier, rule.weight_multiplier)
    return multiplier
