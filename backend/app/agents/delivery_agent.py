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
        origin = self.position or pickup
        _, time_seconds, distance_m = shortest_route(self.graph, origin, dropoff)
        return OrderEvaluation(
            fare=fare,
            distance_km=distance_m / 1000,
            time_minutes=time_seconds / 60,
            vehicle=self.vehicle,
        )
