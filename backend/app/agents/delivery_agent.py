"""Agente repartidor: calcula rutas con app.engine.routing y decide con app.decision.scoring."""

import networkx as nx

from app.config import settings
from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.routing import try_shortest_route


class DeliveryAgent:
    def __init__(self, graph: nx.MultiDiGraph, vehicle: VehicleType = VehicleType.MOTO):
        self.graph = graph
        self.vehicle = vehicle
        self.position: tuple[float, float] | None = None

    def evaluate_order(
        self,
        pickup: tuple[float, float],
        dropoff: tuple[float, float],
        fare: float,
        origin: tuple[float, float] | None = None,
    ) -> OrderEvaluation | None:
        """Evalua una orden en DOS tramos: de donde esta el repartidor hasta
        el pickup, y del pickup al dropoff. Antes esto calculaba una sola
        ruta directa a `dropoff` (si `self.position` era `None`, arrancaba
        desde `pickup` y de pura casualidad quedaba bien; si `self.position`
        ya tenia un valor, la ruta directa a `dropoff` se saltaba el pickup
        por completo) — subestimaba el costo real de ir a recoger el pedido.

        `origin` permite evaluar desde un punto distinto al actual (p.ej. el
        dropoff de la ultima entrega ya aceptada, que es donde el repartidor
        va a estar realmente cuando pueda atender esta orden).

        Devuelve `None` si el pickup o el dropoff quedaron inalcanzables
        (tipicamente por un cierre de calle): la orden no es servible y
        quien llama debe descartarla, no tratarla como gratis.
        """
        start = origin or self.position or pickup

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
            # Al tiempo en la carretera se le suma el tiempo de servicio
            # (esperar la comida + entregarla): ver settings.service_time_minutes.
            time_minutes=(time_to_pickup_s + time_to_dropoff_s) / 60 + settings.service_time_minutes,
            vehicle=self.vehicle,
        )
