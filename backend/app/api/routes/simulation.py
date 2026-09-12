"""Endpoints de control de la simulacion: arrancar/terminar un turno,
generar y decidir ordenes en vivo, Modo Dios, y el log de eventos.

El turno corre "abierto" (VirtualClock con loop=True): el reloj virtual
avanza mucho mas rapido que en la vida real y nunca se congela solo — el
usuario decide cuando terminarlo con /simulation/end.

Solo hay un agente disponible (no hay comparacion inteligente vs novato en
la UI). Ese agente unicamente CALCULA el Score de cada orden que llega;
quien decide aceptar o rechazar es el conductor via /simulation/decide.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.delivery_agent import DeliveryAgent
from app.agents.order_generator import generate_order, maybe_generate_order
from app.config import settings
from app.db.connection import get_session
from app.db.models import Order as OrderModel
from app.db.models import SimulationRun, TripRecord
from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.graph_loader import apply_traffic, load_graph
from app.engine.pois import load_restaurants
from app.engine.traffic_rules import GOD_MODE_PRESETS
from app.engine.virtual_clock import VirtualClock
from app.schemas.simulation import (
    DecisionRequest,
    GodModeRequest,
    PendingOrderOut,
    RunIdRequest,
    SimEventOut,
    SimulationStart,
    SimulationState,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])

# Un "dia" virtual completo (24h) se comprime en este tanto de minutos
# reales — el turno no tiene fin automatico, solo le da la vuelta al reloj.
SHIFT_REAL_DURATION_MINUTES = 3.0
SHIFT_VIRTUAL_MINUTES = 24 * 60
DEFAULT_START_HOUR = 8.0
MAX_PENDING_ORDERS = 5
MAX_EVENTS = 200


@dataclass
class PendingOrder:
    order: dict
    evaluation: OrderEvaluation


@dataclass
class SimulationSession:
    run_id: uuid.UUID
    vehicle: str
    graph: nx.MultiDiGraph
    restaurants: list[dict]
    delivery_agent: DeliveryAgent
    clock: VirtualClock
    hour_override: float | None = None
    god_mode_preset: str | None = None
    net_earnings: float = 0.0
    finished: bool = False
    pending_orders: dict[str, PendingOrder] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)


# TODO: mover a Redis si esto llega a correr con mas de un worker de uvicorn
# (el estado en memoria de un proceso no se comparte entre workers).
_sessions: dict[str, SimulationSession] = {}


def _log(session: SimulationSession, event_type: str, message: str) -> None:
    session.events.insert(
        0,
        {"ts": datetime.now(timezone.utc).isoformat(), "type": event_type, "message": message},
    )
    del session.events[MAX_EVENTS:]


def _current_hour(session: SimulationSession) -> float:
    return session.hour_override if session.hour_override is not None else session.clock.virtual_hour()


def _get_session_or_404(run_id: str) -> SimulationSession:
    session = _sessions.get(run_id)
    if session is None:
        raise HTTPException(404, "Shift not found — it may have already ended or the server restarted")
    return session


def _tick(session: SimulationSession, db: Session) -> None:
    """Avanza el trafico y, con cierta probabilidad, genera una orden nueva."""
    if session.finished:
        return

    virtual_hour = _current_hour(session)
    apply_traffic(session.graph, virtual_hour)

    if len(session.pending_orders) >= MAX_PENDING_ORDERS:
        return
    if not maybe_generate_order(virtual_hour):
        return

    order = generate_order(session.graph, session.restaurants)
    evaluation = session.delivery_agent.evaluate_order(
        (order["pickup_lat"], order["pickup_lon"]),
        (order["dropoff_lat"], order["dropoff_lon"]),
        order["fare"],
    )
    session.pending_orders[order["id"]] = PendingOrder(order=order, evaluation=evaluation)

    db.add(
        OrderModel(
            id=uuid.UUID(order["id"]),
            run_id=session.run_id,
            pickup_lat=order["pickup_lat"],
            pickup_lon=order["pickup_lon"],
            pickup_name=order.get("pickup_name"),
            dropoff_lat=order["dropoff_lat"],
            dropoff_lon=order["dropoff_lon"],
            fare=order["fare"],
        )
    )
    db.commit()

    _log(
        session,
        "order_generated",
        f"New order from {order.get('pickup_name') or 'a restaurant'} — "
        f"${order['fare']:.2f} MXN, estimated Score ${evaluation.score:.2f}",
    )


def _to_pending_out(order_id: str, pending: PendingOrder) -> PendingOrderOut:
    order = pending.order
    evaluation = pending.evaluation
    return PendingOrderOut(
        order_id=order_id,
        pickup_name=order.get("pickup_name"),
        pickup_lat=order["pickup_lat"],
        pickup_lon=order["pickup_lon"],
        dropoff_lat=order["dropoff_lat"],
        dropoff_lon=order["dropoff_lon"],
        fare=order["fare"],
        distance_km=evaluation.distance_km,
        time_minutes=evaluation.time_minutes,
        gas_cost=evaluation.distance_km * evaluation.gas_cost_per_km,
        time_cost=evaluation.time_minutes * settings.time_cost_per_minute,
        score=evaluation.score,
        should_accept=evaluation.should_accept,
    )


def _to_state(session: SimulationSession) -> SimulationState:
    return SimulationState(
        run_id=str(session.run_id),
        vehicle=session.vehicle,
        virtual_hour=_current_hour(session),
        virtual_minute=session.clock.virtual_minute() % 60,
        is_finished=session.finished,
        net_earnings=round(session.net_earnings, 2),
        god_mode_preset=session.god_mode_preset,
        pending_orders=[_to_pending_out(oid, p) for oid, p in session.pending_orders.items()],
        events=[SimEventOut(**e) for e in session.events],
    )


@router.post("/start", response_model=SimulationState)
def start_simulation(payload: SimulationStart, db: Session = Depends(get_session)):
    if payload.vehicle not in {"moto", "auto"}:
        raise HTTPException(400, "vehicle must be 'moto' or 'auto'")

    graph = load_graph()
    restaurants = load_restaurants()

    run_id = uuid.uuid4()
    clock = VirtualClock(
        real_duration_minutes=SHIFT_REAL_DURATION_MINUTES,
        shift_duration_minutes=SHIFT_VIRTUAL_MINUTES,
        start_hour=DEFAULT_START_HOUR,
        loop=True,
    )
    clock.start()

    session = SimulationSession(
        run_id=run_id,
        vehicle=payload.vehicle,
        graph=graph,
        restaurants=restaurants,
        delivery_agent=DeliveryAgent(graph, vehicle=VehicleType(payload.vehicle)),
        clock=clock,
    )
    _sessions[str(run_id)] = session
    _log(session, "shift_started", "Shift started — the smart agent is now scoring incoming orders.")

    db.add(
        SimulationRun(
            id=run_id,
            user_id=uuid.UUID(payload.user_id) if payload.user_id else None,
            agent_type="inteligente",
            vehicle=payload.vehicle,
            start_hour=DEFAULT_START_HOUR,
            shift_duration_minutes=SHIFT_VIRTUAL_MINUTES,
            real_duration_minutes=SHIFT_REAL_DURATION_MINUTES,
            is_finished=False,
        )
    )
    db.commit()

    return _to_state(session)


@router.get("/state", response_model=SimulationState)
def get_state(run_id: str, db: Session = Depends(get_session)):
    session = _get_session_or_404(run_id)
    _tick(session, db)
    return _to_state(session)


@router.post("/decide", response_model=SimulationState)
def decide_order(payload: DecisionRequest, db: Session = Depends(get_session)):
    session = _get_session_or_404(payload.run_id)
    pending = session.pending_orders.pop(payload.order_id, None)
    if pending is None:
        raise HTTPException(404, "That order is no longer pending")

    evaluation = pending.evaluation
    gas_cost = evaluation.distance_km * evaluation.gas_cost_per_km
    time_cost = evaluation.time_minutes * settings.time_cost_per_minute
    net_delta = evaluation.score if payload.accept else 0.0
    session.net_earnings += net_delta

    db.add(
        TripRecord(
            run_id=session.run_id,
            order_id=uuid.UUID(payload.order_id),
            agent_type="inteligente",
            vehicle=session.vehicle,
            accepted=payload.accept,
            fare=evaluation.fare,
            distance_km=evaluation.distance_km,
            time_minutes=evaluation.time_minutes,
            gas_cost=gas_cost,
            time_cost=time_cost,
            score=evaluation.score,
            net_earnings_delta=net_delta,
            virtual_hour=_current_hour(session),
        )
    )
    db.commit()

    pickup_name = pending.order.get("pickup_name") or "the order"
    if payload.accept:
        _log(session, "order_accepted", f"Accepted {pickup_name} — net ${evaluation.score:.2f} MXN")
    else:
        _log(session, "order_rejected", f"Rejected {pickup_name} (Score was ${evaluation.score:.2f} MXN)")

    return _to_state(session)


@router.post("/end", response_model=SimulationState)
def end_simulation(payload: RunIdRequest, db: Session = Depends(get_session)):
    session = _get_session_or_404(payload.run_id)
    session.finished = True
    session.pending_orders.clear()
    _log(session, "shift_ended", f"Shift ended — net earnings ${session.net_earnings:.2f} MXN")

    run = db.get(SimulationRun, session.run_id)
    if run is not None:
        run.is_finished = True
        run.ended_at = datetime.utcnow()
        run.final_net_earnings = round(session.net_earnings, 2)
        db.commit()

    return _to_state(session)


@router.post("/god-mode", response_model=SimulationState)
def god_mode(payload: GodModeRequest, db: Session = Depends(get_session)):
    session = _get_session_or_404(payload.run_id)

    if payload.preset is None:
        session.hour_override = None
        session.god_mode_preset = None
        _log(session, "god_mode", "Traffic back to normal.")
    else:
        if payload.preset not in GOD_MODE_PRESETS:
            raise HTTPException(400, f"Unknown preset, options: {list(GOD_MODE_PRESETS)}")
        session.hour_override = GOD_MODE_PRESETS[payload.preset]
        session.god_mode_preset = payload.preset
        _log(session, "god_mode", f"God Mode: jumped to {payload.preset} traffic.")

    _tick(session, db)
    return _to_state(session)
