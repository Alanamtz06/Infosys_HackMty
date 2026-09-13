"""Clasificacion de pedidos por zona (vecino mas cercano sobre ZONES).
Sin red: `ox.distance.great_circle` es matematica pura, no toca OSM.
"""

from app.engine.zones import ZONES, nearest_zone


def test_zone_names_are_unique():
    names = [zone.name for zone in ZONES]
    assert len(names) == len(set(names)), "dos zonas con el mismo nombre confundirian la agrupacion del frontend"


def test_a_zones_own_center_resolves_to_itself():
    """El caso base: el punto exacto del centro de una zona tiene que
    clasificar como ESA zona (si no, el vecino-mas-cercano esta mal, o dos
    zonas quedaron a la misma distancia — coincidencia que valdria la pena
    investigar antes de confiar en el resto de la funcion)."""
    for zone in ZONES:
        assert nearest_zone(zone.lat, zone.lon) == zone.name


def test_a_point_near_a_zone_classifies_as_that_zone():
    """Un punto desplazado ~300m de un centro de zona (mucho menos que la
    separacion entre zonas vecinas) debe seguir clasificando igual."""
    centro = next(z for z in ZONES if z.name == "Centro")
    nearby_lat = centro.lat + 0.003  # ~330 m hacia el norte
    assert nearest_zone(nearby_lat, centro.lon) == "Centro"


def test_returns_a_known_zone_name_for_an_arbitrary_point():
    """Cualquier punto de la ZMM (no solo los centros exactos) debe resolver
    a una de las zonas del catalogo, nunca a algo fuera de la lista."""
    known_names = {zone.name for zone in ZONES}
    # Un punto generico dentro del radio de la simulacion.
    assert nearest_zone(25.69, -100.32) in known_names
