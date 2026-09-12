"""Agente Novato: acepta TODAS las ordenes, sin mirar el Score.

Es la linea base del Marcador Global (`/stats/scoreboard`) y de las tarjetas
"Novice" del dashboard en vivo: corre en paralelo al agente inteligente,
sobre EXACTAMENTE el mismo stream de ordenes y el mismo trafico, y la unica
diferencia es la decision. Asi la comparacion mide la calidad de la decision
y no dos turnos con suerte distinta.

Igual que el repartidor inteligente, sus viajes se rutean de verdad sobre el
grafo (necesitamos su distancia/tiempo reales para que su Score sea
comparable), y su posicion tambien avanza: como acepta todo, siempre acaba
en el dropoff de la ultima orden que tomo.
"""

import networkx as nx

from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.routing import try_shortest_route


class NoviceAgent:
    def __init__(self, graph: nx.MultiDiGraph, vehicle: VehicleType = VehicleType.MOTO):
        self.graph = graph
        self.vehicle = vehicle
        self.position: tuple[float, float] | None = None

    def evaluate_order(
        self,
        pickup: tuple[float, float],
        dropoff: tuple[float, float],
        fare: float,
    ) -> OrderEvaluation | None:
        """Rutea la orden desde donde quedo el novato. `None` si es inalcanzable."""
        start = self.position or pickup

        to_pickup = try_shortest_route(self.graph, start, pickup)
        if to_pickup is None:
            return None
        to_dropoff = try_shortest_route(self.graph, pickup, dropoff)
        if to_dropoff is None:
            return None

        _, time_to_pickup_s, distance_to_pickup_m = to_pickup
        _, time_to_dropoff_s, distance_to_dropoff_m = to_dropoff

        return OrderEvaluation(
            fare=fare,
            distance_km=(distance_to_pickup_m + distance_to_dropoff_m) / 1000,
            time_minutes=(time_to_pickup_s + time_to_dropoff_s) / 60,
            vehicle=self.vehicle,
        )

    def should_accept(self, _evaluation: OrderEvaluation | None = None) -> bool:
        """Su politica completa: si le llega, la toma."""
        return True

    def commit(self, dropoff: tuple[float, float]) -> None:
        """Acepto la orden: termina en el dropoff."""
        self.position = dropoff
