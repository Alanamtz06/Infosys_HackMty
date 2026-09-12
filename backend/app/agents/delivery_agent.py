"""Agente repartidor: calcula rutas con app.engine.routing y decide con app.decision.scoring."""

import networkx as nx

from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.routing import shortest_route


class DeliveryAgent:
    def __init__(self, graph: nx.MultiDiGraph, vehicle: VehicleType = VehicleType.MOTO):
        self.graph = graph
        self.vehicle = vehicle
        self.position: tuple[float, float] | None = None

    def evaluate_order(self, pickup: tuple[float, float], dropoff: tuple[float, float], fare: float) -> OrderEvaluation:
        """Evalua una orden en DOS tramos: de donde esta el repartidor hasta
        el pickup, y del pickup al dropoff. Antes esto calculaba una sola
        ruta directa a `dropoff` (si `self.position` era `None`, arrancaba
        desde `pickup` y de pura casualidad quedaba bien; si `self.position`
        ya tenia un valor, la ruta directa a `dropoff` se saltaba el pickup
        por completo) — subestimaba el costo real de ir a recoger el pedido.
        """
        origin = self.position or pickup
        _, time_to_pickup_s, distance_to_pickup_m = shortest_route(self.graph, origin, pickup)
        _, time_to_dropoff_s, distance_to_dropoff_m = shortest_route(self.graph, pickup, dropoff)

        return OrderEvaluation(
            fare=fare,
            distance_km=(distance_to_pickup_m + distance_to_dropoff_m) / 1000,
            time_minutes=(time_to_pickup_s + time_to_dropoff_s) / 60,
            vehicle=self.vehicle,
        )
