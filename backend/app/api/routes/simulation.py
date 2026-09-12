"""Endpoints de control de la simulacion: arrancar/terminar un turno,
generar y decidir ordenes en vivo, Modo Dios, y el log de eventos.

El tiempo NO arranca con el turno: `engine.virtual_clock.world_clock` es un
reloj global que corre desde que prende el proceso, acelerado
(`TIME_ACCELERATION`), y nunca se detiene. Un turno solo se engancha a la
hora que el mundo ya traia; termina cuando el usuario llama a
/simulation/end. Todo lo que se registra en el log en vivo lleva la hora
SIMULADA, no la hora real del servidor.

Quien decide aceptar o rechazar es el conductor via /simulation/decide; el
agente inteligente calcula el Score y una recomendacion (decision.policy).
En paralelo corre un agente NOVATO invisible que acepta todo sobre el mismo
stream de ordenes: es la linea base del Marcador Global y de las tarjetas
"Novice" del dashboard (ambos runs comparten `session_id`).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.delivery_agent import DeliveryAgent
from app.agents.novice_agent import NoviceAgent
from app.agents.order_generator import generate_order, orders_to_generate
from app.config import settings
from app.db.connection import get_session
from app.db.models import Order as OrderModel
from app.db.models import SimulationRun, TripRecord
from app.decision import batching, policy
from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.graph_loader import apply_traffic, load_graph
from app.engine.pois import load_restaurants
from app.engine.routing import (
    clear_road_closure,
    position_along_route,
    route_total_time,
    simulate_random_closure,
    try_shortest_route,
)
from app.engine.traffic_rules import GOD_MODE_PRESETS
from app.engine.virtual_clock import world_clock
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

MAX_PENDING_ORDERS = 5
MAX_EVENTS = 200

# El God Mode "salida_trabajo" (hora pico de la tarde) es, ademas de trafico
# pesado, el momento que usamos para la demo de "cierre de calle a mitad de
# turno" que pide el reto: no hay boton nuevo en la UI para esto (no se toco
# el frontend), se aprovecha el preset que ya existe.
ROAD_CLOSURE_PRESET = "salida_trabajo"

# Cada cuantos minutos simulados, como maximo, se recalcula el insight de
# batching (ver _log_batching_insight).
BATCHING_INSIGHT_COOLDOWN_SIM_MINUTES = 20.0


@dataclass
class PendingOrder:
    order: dict
    evaluation: OrderEvaluation


@dataclass
class ActiveDelivery:
    """Una orden aceptada que el repartidor esta cursando ahora mismo.

    `started_sim_seconds` se asigna cuando esta entrega llega al frente de
    la cola (las entregas se hacen de una en una, en orden de aceptacion),
    no cuando se acepto: si hay dos aceptadas, la segunda empieza a contar
    cuando termina la primera.
    """

    order: dict
    route: list[int]
    total_seconds: float
    started_sim_seconds: float | None = None


@dataclass
class SimulationSession:
    run_id: uuid.UUID
    novice_run_id: uuid.UUID
    session_id: uuid.UUID
    vehicle: str
    graph: nx.MultiDiGraph
    restaurants: list[dict]
    delivery_agent: DeliveryAgent
    novice_agent: NoviceAgent
    started_sim_seconds: float
    last_tick_sim_seconds: float
    hour_override: float | None = None
    god_mode_preset: str | None = None
    net_earnings: float = 0.0
    novice_earnings: float = 0.0
    finished: bool = False
    pending_orders: dict[str, PendingOrder] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    orders_accepted: int = 0  # para decision.policy: ritmo de aceptacion vs. tiempo transcurrido
    deliveries_completed: int = 0
    active_deliveries: list[ActiveDelivery] = field(default_factory=list)
    courier_position: tuple[float, float] | None = None
    active_closure: dict | None = None  # {"u", "v", "street_name"} del cierre vigente, si hay uno
    last_batching_insight_sim_minute: float = -1e9
    evaluations_by_order: dict[str, OrderEvaluation] = field(default_factory=dict)  # historial para /audit


# TODO: mover a Redis si esto llega a correr con mas de un worker de uvicorn
# (el estado en memoria de un proceso no se comparte entre workers).
_sessions: dict[str, SimulationSession] = {}


def _log(session: SimulationSession, event_type: str, message: str) -> None:
    """Registra un evento con la hora SIMULADA (no la del servidor).

    `world_clock.iso_timestamp()` devuelve un ISO sin zona horaria a
    proposito, para que el `new Date(ts).toLocaleTimeString()` del frontend
    muestre exactamente la hora del mundo simulado.
    """
    session.events.insert(
        0,
        {"ts": world_clock.iso_timestamp(), "type": event_type, "message": message},
    )
    del session.events[MAX_EVENTS:]


def _current_hour(session: SimulationSession) -> float:
    return session.hour_override if session.hour_override is not None else world_clock.virtual_hour()


def _get_session_or_404(run_id: str) -> SimulationSession:
    session = _sessions.get(run_id)
    if session is None:
        raise HTTPException(404, "Shift not found — it may have already ended or the server restarted")
    return session


def _courier_live_position(session: SimulationSession) -> tuple[float, float] | None:
    """Donde va el repartidor AHORA: interpolado sobre la ruta si esta
    entregando, o su ultima posicion conocida si esta libre."""
    if session.active_deliveries:
        head = session.active_deliveries[0]
        started = head.started_sim_seconds
        if started is not None:
            elapsed = world_clock.sim_elapsed_seconds() - started
            try:
                return position_along_route(session.graph, head.route, elapsed)
            except (ValueError, KeyError):
                pass
    return session.courier_position


def _next_free_position(session: SimulationSession) -> tuple[float, float] | None:
    """Donde va a estar el repartidor cuando se desocupe: el dropoff de la
    ultima entrega en cola. Es el origen correcto para evaluar una orden
    nueva (no donde esta parado ahora, que ya esta comprometido)."""
    if session.active_deliveries:
        last = session.active_deliveries[-1].order
        return (last["dropoff_lat"], last["dropoff_lon"])
    return _courier_live_position(session)


def _advance_deliveries(session: SimulationSession) -> None:
    """Avanza la cola de entregas con el reloj del mundo y cierra las que ya
    terminaron (una por una, en orden de aceptacion)."""
    now_s = world_clock.sim_elapsed_seconds()

    while session.active_deliveries:
        head = session.active_deliveries[0]
        if head.started_sim_seconds is None:
            head.started_sim_seconds = now_s
        if now_s - head.started_sim_seconds < head.total_seconds:
            break

        session.courier_position = (head.order["dropoff_lat"], head.order["dropoff_lon"])
        session.delivery_agent.position = session.courier_position
        session.deliveries_completed += 1
        session.active_deliveries.pop(0)
        _log(
            session,
            "order_accepted",
            f"Delivered {head.order.get('pickup_name') or 'the order'} — "
            f"{head.total_seconds / 60:.0f} min on the road.",
        )


def _tick(session: SimulationSession, db: Session) -> None:
    """Avanza trafico, entregas en curso y demanda, en tiempo simulado."""
    if session.finished:
        return

    virtual_hour = _current_hour(session)
    apply_traffic(session.graph, virtual_hour)

    now_s = world_clock.sim_elapsed_seconds()
    sim_minutes_elapsed = max((now_s - session.last_tick_sim_seconds) / 60, 0.0)
    session.last_tick_sim_seconds = now_s

    _advance_deliveries(session)

    if len(session.pending_orders) >= MAX_PENDING_ORDERS:
        return

    how_many = orders_to_generate(virtual_hour, sim_minutes_elapsed)
    generated = 0
    for _ in range(how_many):
        if len(session.pending_orders) >= MAX_PENDING_ORDERS:
            break
        if _generate_and_evaluate_order(session, db, virtual_hour):
            generated += 1

    if generated:
        _log_batching_insight(session)


def _generate_and_evaluate_order(session: SimulationSession, db: Session, virtual_hour: float) -> bool:
    """Crea una orden, la evalua para ambos agentes y la deja pendiente.

    Devuelve False si la orden resulto inservible (pickup o dropoff
    inalcanzables, tipicamente por un cierre de calle): en ese caso no se
    guarda nada y simplemente no llega esa oferta.
    """
    order = generate_order(session.graph, session.restaurants)

    evaluation = session.delivery_agent.evaluate_order(
        (order["pickup_lat"], order["pickup_lon"]),
        (order["dropoff_lat"], order["dropoff_lon"]),
        order["fare"],
        origin=_next_free_position(session),
    )
    if evaluation is None:
        return False

    session.pending_orders[order["id"]] = PendingOrder(order=order, evaluation=evaluation)
    session.evaluations_by_order[order["id"]] = evaluation

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

    _record_novice_decision(session, db, order, virtual_hour)

    _log(
        session,
        "order_generated",
        f"New order from {order.get('pickup_name') or 'a restaurant'} — "
        f"${order['fare']:.2f} MXN, estimated Score ${evaluation.score:.2f}",
    )
    return True


def _record_novice_decision(
    session: SimulationSession,
    db: Session,
    order: dict,
    virtual_hour: float,
) -> None:
    """El agente novato decide la misma orden al instante: la acepta siempre.

    Escribe su propio TripRecord bajo `novice_run_id` (mismo `session_id`
    que el turno inteligente), que es lo que alimenta las tarjetas "Novice"
    de /stats/live y la comparacion de /stats/scoreboard. No aparece en la
    UI del turno: el novato no es un repartidor que el usuario maneje, es la
    vara con la que se mide.
    """
    evaluation = session.novice_agent.evaluate_order(
        (order["pickup_lat"], order["pickup_lon"]),
        (order["dropoff_lat"], order["dropoff_lon"]),
        order["fare"],
    )
    if evaluation is None:
        return

    session.novice_agent.commit((order["dropoff_lat"], order["dropoff_lon"]))
    session.novice_earnings += evaluation.score

    db.add(
        TripRecord(
            run_id=session.novice_run_id,
            order_id=uuid.UUID(order["id"]),
            agent_type="novato",
            vehicle=session.vehicle,
            accepted=True,
            fare=evaluation.fare,
            distance_km=evaluation.distance_km,
            time_minutes=evaluation.time_minutes,
            gas_cost=evaluation.distance_km * evaluation.gas_cost_per_km,
            time_cost=evaluation.time_minutes * settings.time_cost_per_minute,
            score=evaluation.score,
            net_earnings_delta=evaluation.score,
            virtual_hour=virtual_hour,
        )
    )
    db.commit()


def _log_batching_insight(session: SimulationSession) -> None:
    """Con 2+ ordenes pendientes, corre VRPTW (app.decision.batching) sobre
    todas juntas y, si conviene, lo anuncia en el log — informativo nada
    mas: el frontend no tiene una accion de "aceptar batch", cada orden se
    sigue decidiendo una por una en PendingOrdersPanel.

    Con enfriamiento: resolver el VRPTW pide una matriz de tiempos sobre el
    grafo real (segundos de CPU), y el reloj del mundo sigue corriendo
    mientras la request trabaja. Calcularlo en cada orden nueva hacia que un
    tick se comiera varios minutos simulados.
    """
    if len(session.pending_orders) < 2:
        return

    now_sim_minutes = world_clock.sim_elapsed_seconds() / 60
    if now_sim_minutes - session.last_batching_insight_sim_minute < BATCHING_INSIGHT_COOLDOWN_SIM_MINUTES:
        return
    session.last_batching_insight_sim_minute = now_sim_minutes

    start_point = _next_free_position(session) or _any_pending_pickup(session)
    orders = [p.order for p in session.pending_orders.values()]
    try:
        plan = batching.plan_batch(session.graph, start_point, orders)
    except Exception:
        return  # el insight de batching es informativo; nunca debe tumbar el tick
    if plan is None or plan.time_saved_seconds < 30:
        return

    _log(
        session,
        "order_generated",
        f"Batching tip: doing these {len(orders)} pending orders together saves "
        f"~{plan.time_saved_seconds / 60:.0f} min vs. one at a time.",
    )


def _any_pending_pickup(session: SimulationSession) -> tuple[float, float]:
    first = next(iter(session.pending_orders.values()))
    return (first.order["pickup_lat"], first.order["pickup_lon"])


def _to_pending_out(session: SimulationSession, order_id: str, pending: PendingOrder) -> PendingOrderOut:
    order = pending.order
    evaluation = pending.evaluation

    # should_accept es una recomendacion (el conductor sigue decidiendo via
    # /simulation/decide, ver PendingOrdersPanel.tsx): en vez del corte
    # estatico Score > 0, usa el umbral dinamico de decision.policy, que se
    # vuelve mas permisivo si el repartidor va atrasado en su ritmo de
    # pedidos aceptados.
    policy_state = policy.PolicyState(
        orders_accepted=session.orders_accepted,
        virtual_minutes_elapsed=(world_clock.sim_elapsed_seconds() - session.started_sim_seconds) / 60,
    )
    recommendation = policy.should_accept(evaluation.score, policy_state)

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
        should_accept=recommendation,
    )


def _to_state(session: SimulationSession) -> SimulationState:
    position = _courier_live_position(session)
    return SimulationState(
        run_id=str(session.run_id),
        vehicle=session.vehicle,
        virtual_hour=_current_hour(session),
        virtual_minute=world_clock.virtual_minute(),
        is_finished=session.finished,
        net_earnings=round(session.net_earnings, 2),
        god_mode_preset=session.god_mode_preset,
        pending_orders=[_to_pending_out(session, oid, p) for oid, p in session.pending_orders.items()],
        events=[SimEventOut(**e) for e in session.events],
        # Campos nuevos, aditivos: el frontend actual los ignora sin romperse
        # (MapView.tsx todavia usa una posicion placeholder).
        sim_time=world_clock.iso_timestamp(),
        time_acceleration=world_clock.acceleration,
        courier_lat=position[0] if position else None,
        courier_lon=position[1] if position else None,
        active_deliveries=len(session.active_deliveries),
        deliveries_completed=session.deliveries_completed,
        orders_accepted=session.orders_accepted,
        novice_earnings=round(session.novice_earnings, 2),
        session_id=str(session.session_id),
    )


@router.post("/start", response_model=SimulationState)
def start_simulation(payload: SimulationStart, db: Session = Depends(get_session)):
    if payload.vehicle not in {"moto", "auto"}:
        raise HTTPException(400, "vehicle must be 'moto' or 'auto'")

    graph = load_graph()
    restaurants = load_restaurants()

    run_id = uuid.uuid4()
    novice_run_id = uuid.uuid4()
    session_id = uuid.uuid4()
    now_s = world_clock.sim_elapsed_seconds()
    start_hour = world_clock.virtual_hour()

    session = SimulationSession(
        run_id=run_id,
        novice_run_id=novice_run_id,
        session_id=session_id,
        vehicle=payload.vehicle,
        graph=graph,
        restaurants=restaurants,
        delivery_agent=DeliveryAgent(graph, vehicle=VehicleType(payload.vehicle)),
        novice_agent=NoviceAgent(graph, vehicle=VehicleType(payload.vehicle)),
        started_sim_seconds=now_s,
        last_tick_sim_seconds=now_s,
        courier_position=(settings.city_center_lat, settings.city_center_lon),
    )
    session.delivery_agent.position = session.courier_position
    session.novice_agent.position = session.courier_position
    _sessions[str(run_id)] = session
    _log(
        session,
        "shift_started",
        f"Shift started at {world_clock.now():%H:%M} simulated time — "
        f"the clock runs {world_clock.acceleration:.0f}x faster than real life.",
    )

    # Un dia simulado completo (1440 min) toma esto en minutos reales; es el
    # equivalente honesto de `real_duration_minutes` ahora que el reloj es
    # global y no por turno.
    real_minutes_per_sim_day = 1440 / world_clock.acceleration

    user_id = uuid.UUID(payload.user_id) if payload.user_id else None
    db.add(
        SimulationRun(
            id=run_id,
            session_id=session_id,
            user_id=user_id,
            agent_type="inteligente",
            vehicle=payload.vehicle,
            start_hour=start_hour,
            shift_duration_minutes=1440,
            real_duration_minutes=real_minutes_per_sim_day,
            is_finished=False,
        )
    )
    # Turno espejo del novato: mismo session_id para que /stats/scoreboard
    # compare los dos agentes sobre el mismo stream de ordenes.
    db.add(
        SimulationRun(
            id=novice_run_id,
            session_id=session_id,
            user_id=user_id,
            agent_type="novato",
            vehicle=payload.vehicle,
            start_hour=start_hour,
            shift_duration_minutes=1440,
            real_duration_minutes=real_minutes_per_sim_day,
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

    if payload.accept:
        session.orders_accepted += 1
        _start_delivery(session, pending.order)

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


def _start_delivery(session: SimulationSession, order: dict) -> None:
    """Encola la entrega para que el repartidor la recorra en tiempo simulado.

    Si la ruta resulta inalcanzable (cierre de calle justo ahi), se cae al
    comportamiento viejo: el repartidor "aparece" en el dropoff. Perder la
    animacion es preferible a perder la orden que el usuario ya acepto.
    """
    origin = _next_free_position(session) or (order["pickup_lat"], order["pickup_lon"])
    pickup = (order["pickup_lat"], order["pickup_lon"])
    dropoff = (order["dropoff_lat"], order["dropoff_lon"])

    to_pickup = try_shortest_route(session.graph, origin, pickup)
    to_dropoff = try_shortest_route(session.graph, pickup, dropoff)
    if to_pickup is None or to_dropoff is None:
        session.courier_position = dropoff
        session.delivery_agent.position = dropoff
        return

    route = to_pickup[0] + to_dropoff[0][1:]
    session.active_deliveries.append(
        ActiveDelivery(order=order, route=route, total_seconds=route_total_time(session.graph, route))
    )


@router.post("/end", response_model=SimulationState)
def end_simulation(payload: RunIdRequest, db: Session = Depends(get_session)):
    session = _get_session_or_404(payload.run_id)
    session.finished = True
    session.pending_orders.clear()
    session.active_deliveries.clear()
    if session.active_closure is not None:
        clear_road_closure(session.graph, session.active_closure["u"], session.active_closure["v"])
        session.active_closure = None
    _log(session, "shift_ended", f"Shift ended — net earnings ${session.net_earnings:.2f} MXN")

    for run_id, total in ((session.run_id, session.net_earnings), (session.novice_run_id, session.novice_earnings)):
        run = db.get(SimulationRun, run_id)
        if run is not None:
            run.is_finished = True
            run.ended_at = datetime.utcnow()
            run.final_net_earnings = round(total, 2)
    db.commit()

    return _to_state(session)


@router.post("/god-mode", response_model=SimulationState)
def god_mode(payload: GodModeRequest, db: Session = Depends(get_session)):
    session = _get_session_or_404(payload.run_id)

    if payload.preset is None:
        session.hour_override = None
        session.god_mode_preset = None
        if session.active_closure is not None:
            clear_road_closure(session.graph, session.active_closure["u"], session.active_closure["v"])
            session.active_closure = None
        _log(session, "god_mode", "Traffic back to normal, roads reopened.")
    else:
        if payload.preset not in GOD_MODE_PRESETS:
            raise HTTPException(400, f"Unknown preset, options: {list(GOD_MODE_PRESETS)}")
        session.hour_override = GOD_MODE_PRESETS[payload.preset]
        session.god_mode_preset = payload.preset
        _log(session, "god_mode", f"God Mode: jumped to {payload.preset} traffic.")

        # El reto pide que el agente reaccione a un cierre de calle a mitad
        # de turno ademas del surge de trafico; no hay un boton nuevo en la
        # UI para esto (no se toco el frontend), asi que se aprovecha el
        # preset de hora pico de salida que ya existe.
        if payload.preset == ROAD_CLOSURE_PRESET and session.active_closure is None:
            near = _courier_live_position(session) or (settings.city_center_lat, settings.city_center_lon)
            closure = simulate_random_closure(session.graph, near_point=near)
            if closure is not None:
                session.active_closure = closure
                street = closure["street_name"] or "a nearby street"
                _log(session, "god_mode", f"Accident reported on {street} — the agent must reroute around it.")

    _tick(session, db)
    return _to_state(session)
