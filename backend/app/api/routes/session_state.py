"""Estado serializable de un turno en curso.

Todo lo que hay aqui tiene que poder ir y venir de JSON (ver
session_store.py): nada de grafos, agentes ni objetos de OSMnx. El runtime
(grafo + agentes) se reconstruye por worker a partir de estos datos.

Las evaluaciones (`OrderEvaluation`) se guardan como numeros planos y se
reconstruyen al leer, porque `VehicleType` es un Enum y `OrderEvaluation`
tiene propiedades calculadas — serializar el objeto entero seria fragil.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.decision.scoring import OrderEvaluation, VehicleType


def _evaluation_to_dict(evaluation: OrderEvaluation) -> dict:
    return {
        "fare": float(evaluation.fare),
        "distance_km": float(evaluation.distance_km),
        "time_minutes": float(evaluation.time_minutes),
        "vehicle": evaluation.vehicle.value,
    }


def _evaluation_from_dict(data: dict) -> OrderEvaluation:
    return OrderEvaluation(
        fare=data["fare"],
        distance_km=data["distance_km"],
        time_minutes=data["time_minutes"],
        vehicle=VehicleType(data["vehicle"]),
    )


@dataclass
class PendingOrder:
    order: dict
    evaluation: OrderEvaluation
    # Lo que el agente novato YA decidio para esta MISMA orden, al instante en
    # que se genero (ver _record_novice_decision) — no una prediccion, el
    # veredicto real que ya escribio su propio TripRecord. Se guarda aqui para
    # que el panel pueda mostrar los dos veredictos lado a lado sin que el
    # frontend tenga que re-derivarlo.
    #
    # Forma: {"outcome": "accepted", "score", "fare", "distance_km",
    # "time_minutes"} si lo tomo: {"outcome": "busy"} si ya traia otra entrega
    # encima: {"outcome": "unreachable"} si un cierre de calle le dejo la
    # orden sin ruta. None solo por compatibilidad con un estado serializado
    # antes de este campo (Redis entre despliegues) — no deberia pasar en
    # el flujo normal, se calcula sincronico junto con la orden.
    novice_outcome: dict | None = None

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "evaluation": _evaluation_to_dict(self.evaluation),
            "novice_outcome": self.novice_outcome,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PendingOrder:
        return cls(
            order=data["order"],
            evaluation=_evaluation_from_dict(data["evaluation"]),
            novice_outcome=data.get("novice_outcome"),
        )


@dataclass
class ActiveDelivery:
    """Una orden aceptada que el repartidor esta cursando ahora mismo.

    `started_sim_seconds` se asigna cuando esta entrega llega al frente de la
    cola (las entregas se hacen de una en una, en orden de aceptacion), no
    cuando se acepto: si hay dos aceptadas, la segunda empieza a contar
    cuando termina la primera.
    """

    order: dict
    route: list[int]
    total_seconds: float
    started_sim_seconds: float | None = None
    # Donde termina el tramo "voy por la comida" y empieza "voy a entregarla".
    # `route` es la concatenacion de los dos tramos, y sin guardar el corte no
    # hay forma de saber despues en cual de las dos fases va el repartidor —
    # que es justo lo que el mapa pinta distinto (ver /simulation/route).
    pickup_index: int = 0
    to_pickup_seconds: float = 0.0

    # Cache de geometria (coordenadas ya partidas para el mapa), calculada
    # UNA vez y reusada en cada poll de /simulation/state mientras dure esta
    # entrega — la ruta no cambia entre aceptar la orden y completarla, asi
    # que recorrer sus aristas y adelgazarla en cada sondeo de 2s es trabajo
    # identico repetido. No es parte del estado serializable (no va en
    # to_dict/from_dict): es puramente un cache de este proceso, y si el
    # estado se rehidrata en otro worker se recalcula una vez ahi y punto.
    _geometry_cache: Any = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "route": self.route,
            "total_seconds": self.total_seconds,
            "started_sim_seconds": self.started_sim_seconds,
            "pickup_index": self.pickup_index,
            "to_pickup_seconds": self.to_pickup_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ActiveDelivery:
        return cls(
            order=data["order"],
            route=list(data["route"]),
            total_seconds=data["total_seconds"],
            started_sim_seconds=data.get("started_sim_seconds"),
            pickup_index=data.get("pickup_index", 0),
            to_pickup_seconds=data.get("to_pickup_seconds", 0.0),
        )


@dataclass
class SessionState:
    run_id: str
    novice_run_id: str
    session_id: str
    vehicle: str
    started_sim_seconds: float
    last_tick_sim_seconds: float
    net_earnings: float = 0.0
    novice_earnings: float = 0.0
    finished: bool = False
    orders_accepted: int = 0
    deliveries_completed: int = 0
    courier_position: tuple[float, float] | None = None
    novice_position: tuple[float, float] | None = None
    # Zona donde el repartidor trabaja el turno. Las ofertas se sesgan a esta
    # zona (no a donde esta parado cada agente) para que el inteligente y el
    # novato vean EXACTAMENTE el mismo stream: si el stream siguiera al
    # inteligente, tendria una ventaja de cercania que no es merito de su
    # decision. Alejarse de la zona cuesta, y eso si es consecuencia propia.
    zone_center: tuple[float, float] | None = None
    # Hasta cuando esta ocupado el novato: un repartidor no puede cursar diez
    # entregas a la vez, y ese limite es justo lo que hace que "aceptar todo"
    # cueste algo (ver _record_novice_decision).
    novice_busy_until_sim_seconds: float = 0.0
    last_batching_insight_sim_minute: float = -1e9
    last_revaluation_sim_minute: float = -1e9
    last_revaluation_context: str | None = None
    pending_orders: dict[str, PendingOrder] = field(default_factory=dict)
    active_deliveries: list[ActiveDelivery] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "novice_run_id": self.novice_run_id,
            "session_id": self.session_id,
            "vehicle": self.vehicle,
            "started_sim_seconds": self.started_sim_seconds,
            "last_tick_sim_seconds": self.last_tick_sim_seconds,
            "net_earnings": self.net_earnings,
            "novice_earnings": self.novice_earnings,
            "finished": self.finished,
            "orders_accepted": self.orders_accepted,
            "deliveries_completed": self.deliveries_completed,
            "courier_position": list(self.courier_position) if self.courier_position else None,
            "novice_position": list(self.novice_position) if self.novice_position else None,
            "zone_center": list(self.zone_center) if self.zone_center else None,
            "novice_busy_until_sim_seconds": self.novice_busy_until_sim_seconds,
            "last_batching_insight_sim_minute": self.last_batching_insight_sim_minute,
            "last_revaluation_sim_minute": self.last_revaluation_sim_minute,
            "last_revaluation_context": self.last_revaluation_context,
            "pending_orders": {oid: p.to_dict() for oid, p in self.pending_orders.items()},
            "active_deliveries": [d.to_dict() for d in self.active_deliveries],
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SessionState:
        position = data.get("courier_position")
        novice_position = data.get("novice_position")
        zone_center = data.get("zone_center")
        return cls(
            run_id=data["run_id"],
            novice_run_id=data["novice_run_id"],
            session_id=data["session_id"],
            vehicle=data["vehicle"],
            started_sim_seconds=data["started_sim_seconds"],
            last_tick_sim_seconds=data["last_tick_sim_seconds"],
            net_earnings=data.get("net_earnings", 0.0),
            novice_earnings=data.get("novice_earnings", 0.0),
            finished=data.get("finished", False),
            orders_accepted=data.get("orders_accepted", 0),
            deliveries_completed=data.get("deliveries_completed", 0),
            courier_position=tuple(position) if position else None,
            novice_position=tuple(novice_position) if novice_position else None,
            zone_center=tuple(zone_center) if zone_center else None,
            novice_busy_until_sim_seconds=data.get("novice_busy_until_sim_seconds", 0.0),
            last_batching_insight_sim_minute=data.get("last_batching_insight_sim_minute", -1e9),
            last_revaluation_sim_minute=data.get("last_revaluation_sim_minute", -1e9),
            last_revaluation_context=data.get("last_revaluation_context"),
            pending_orders={
                oid: PendingOrder.from_dict(p) for oid, p in (data.get("pending_orders") or {}).items()
            },
            active_deliveries=[ActiveDelivery.from_dict(d) for d in (data.get("active_deliveries") or [])],
            events=list(data.get("events") or []),
        )
