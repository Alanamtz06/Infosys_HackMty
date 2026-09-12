"""Endpoints de control de la simulacion: arrancar/terminar un turno,
generar y decidir ordenes en vivo, Modo Dios, y el log de eventos.

El tiempo NO arranca con el turno: `engine.virtual_clock.world_clock` es un
reloj global que corre desde que prende el proceso, acelerado
(`TIME_ACCELERATION`), y nunca se detiene. Un turno solo se engancha a la
hora que el mundo ya traia; termina cuando el usuario llama a
/simulation/end. Todo lo que se registra en el log en vivo lleva la hora
SIMULADA, no la hora real del servidor.

Dos modos de decision:
  - manual (default): el agente calcula el Score y una recomendacion
    (decision.policy) y el conductor decide via /simulation/decide. Es lo que
    usa el frontend hoy (ver PendingOrdersPanel.tsx).
  - autonomo (`autonomous=true` en /simulation/start): el agente decide solo,
    sin intervencion. Es el modo que hace comparable "agente vs baseline".

En paralelo corre siempre un agente NOVATO invisible que acepta todo lo que
le cabe, sobre el mismo stream de ordenes: es la linea base del Marcador
Global y de las tarjetas "Novice" del dashboard (ambos runs comparten
`session_id`).

El estado del turno vive en `session_store` (memoria o Redis); el grafo y los
agentes NO se serializan, se rehidratan por worker (ver ShiftRuntime).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.delivery_agent import DeliveryAgent
from app.agents.novice_agent import NoviceAgent
from app.agents.order_generator import generate_order, orders_to_generate
from app.api.routes.session_state import ActiveDelivery, PendingOrder, SessionState
from app.api.routes.session_store import get_session_store
from app.config import settings
from app.db.connection import get_session
from app.db.models import Order as OrderModel
from app.db.models import SimulationRun, TripRecord
from app.decision import batching, policy
from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.benchmark import run_benchmark
from app.engine.graph_loader import apply_traffic, load_graph
from app.engine.pois import load_restaurants
from app.engine.routing import (
    apply_road_closure,
    clear_road_closure,
    position_along_route,
    route_total_time,
    simulate_random_closure,
    try_shortest_route,
)
from app.engine.traffic_rules import GOD_MODE_PRESETS
from app.engine.virtual_clock import world_clock
from app.schemas.simulation import (
    BenchmarkRequest,
    BenchmarkResult,
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
# batching (ver _log_batching_insight) y se reevaluan las ordenes pendientes
# (ver _revalue_pending_orders). Los dos cuestan ruteo sobre el grafo real.
BATCHING_INSIGHT_COOLDOWN_SIM_MINUTES = 20.0
REVALUATION_COOLDOWN_SIM_MINUTES = 5.0

# Cambio relativo de Score a partir del cual vale la pena avisarle al
# conductor que una oferta que ya tiene en pantalla cambio de precio.
REVALUATION_LOG_THRESHOLD = 0.20


@dataclass
class ShiftRuntime:
    """Estado del turno + lo que no se serializa, rehidratado por worker.

    El grafo viene del cache de proceso de `load_graph()`, asi que rehidratar
    es barato. Lo que si hay que rehacer a mano es el cierre de calle: vive
    en las aristas del grafo, y el grafo de ESTE worker puede no tenerlo
    aplicado todavia.
    """

    state: SessionState
    graph: nx.MultiDiGraph
    restaurants: list[dict]
    delivery_agent: DeliveryAgent
    novice_agent: NoviceAgent

    @classmethod
    def hydrate(cls, state: SessionState) -> "ShiftRuntime":
        graph = load_graph()
        restaurants = load_restaurants()
        vehicle = VehicleType(state.vehicle)

        delivery_agent = DeliveryAgent(graph, vehicle=vehicle)
        delivery_agent.position = state.courier_position
        novice_agent = NoviceAgent(graph, vehicle=vehicle)
        novice_agent.position = state.novice_position or state.courier_position

        if state.active_closure is not None:
            try:
                apply_road_closure(graph, state.active_closure["u"], state.active_closure["v"])
            except ValueError:
                state.active_closure = None

        return cls(
            state=state,
            graph=graph,
            restaurants=restaurants,
            delivery_agent=delivery_agent,
            novice_agent=novice_agent,
        )

    def persist(self) -> None:
        """Baja al estado lo que los agentes cambiaron y lo guarda."""
        self.state.courier_position = self.delivery_agent.position
        self.state.novice_position = self.novice_agent.position
        get_session_store().save(self.state)


def _load_runtime(run_id: str) -> ShiftRuntime:
    state = get_session_store().get(run_id)
    if state is None:
        raise HTTPException(404, "Shift not found — it may have already ended or the server restarted")
    return ShiftRuntime.hydrate(state)


def _log(rt: ShiftRuntime, event_type: str, message: str) -> None:
    """Registra un evento con la hora SIMULADA (no la del servidor).

    `world_clock.iso_timestamp()` devuelve un ISO sin zona horaria a
    proposito, para que el `new Date(ts).toLocaleTimeString()` del frontend
    muestre exactamente la hora del mundo simulado.
    """
    rt.state.events.insert(
        0,
        {"ts": world_clock.iso_timestamp(), "type": event_type, "message": message},
    )
    del rt.state.events[MAX_EVENTS:]


def _current_hour(state: SessionState) -> float:
    return state.hour_override if state.hour_override is not None else world_clock.virtual_hour()


def _courier_live_position(rt: ShiftRuntime) -> tuple[float, float] | None:
    """Donde va el repartidor AHORA: interpolado sobre la ruta si esta
    entregando, o su ultima posicion conocida si esta libre."""
    if rt.state.active_deliveries:
        head = rt.state.active_deliveries[0]
        if head.started_sim_seconds is not None:
            elapsed = world_clock.sim_elapsed_seconds() - head.started_sim_seconds
            try:
                return position_along_route(rt.graph, head.route, elapsed)
            except (ValueError, KeyError):
                pass
    return rt.state.courier_position


def _next_free_position(rt: ShiftRuntime) -> tuple[float, float] | None:
    """Donde va a estar el repartidor cuando se desocupe: el dropoff de la
    ultima entrega en cola. Es el origen correcto para evaluar una orden
    nueva (no donde esta parado ahora, que ya esta comprometido)."""
    if rt.state.active_deliveries:
        last = rt.state.active_deliveries[-1].order
        return (last["dropoff_lat"], last["dropoff_lon"])
    return _courier_live_position(rt)


def _advance_deliveries(rt: ShiftRuntime) -> None:
    """Avanza la cola de entregas con el reloj del mundo y cierra las que ya
    terminaron (una por una, en orden de aceptacion)."""
    now_s = world_clock.sim_elapsed_seconds()

    while rt.state.active_deliveries:
        head = rt.state.active_deliveries[0]
        if head.started_sim_seconds is None:
            head.started_sim_seconds = now_s
        if now_s - head.started_sim_seconds < head.total_seconds:
            break

        rt.state.courier_position = (head.order["dropoff_lat"], head.order["dropoff_lon"])
        rt.delivery_agent.position = rt.state.courier_position
        rt.state.deliveries_completed += 1
        rt.state.active_deliveries.pop(0)
        _log(
            rt,
            "order_accepted",
            f"Delivered {head.order.get('pickup_name') or 'the order'} — "
            f"{head.total_seconds / 60:.0f} min on the road.",
        )


def _tick(rt: ShiftRuntime, db: Session) -> None:
    """Avanza trafico, entregas en curso y demanda, en tiempo simulado."""
    state = rt.state
    if state.finished:
        return

    virtual_hour = _current_hour(state)
    apply_traffic(rt.graph, virtual_hour)

    now_s = world_clock.sim_elapsed_seconds()
    sim_minutes_elapsed = max((now_s - state.last_tick_sim_seconds) / 60, 0.0)
    state.last_tick_sim_seconds = now_s

    _advance_deliveries(rt)
    _revalue_pending_orders(rt)

    if len(state.pending_orders) >= MAX_PENDING_ORDERS:
        return

    how_many = orders_to_generate(virtual_hour, sim_minutes_elapsed)
    generated = 0
    for _ in range(how_many):
        if len(state.pending_orders) >= MAX_PENDING_ORDERS:
            break
        if _generate_and_evaluate_order(rt, db, virtual_hour):
            generated += 1

    if generated:
        _log_batching_insight(rt)


# --------------------------------------------------------------------------
# Reevaluacion de ordenes pendientes
# --------------------------------------------------------------------------


def _revaluation_context(rt: ShiftRuntime) -> str:
    """Huella de lo que le cambia el precio a una oferta pendiente.

    Si esta huella no cambio, reevaluar daria exactamente el mismo numero y
    solo gastaria ruteo. Entran: el bloque de hora (el trafico se recalcula
    por hora del dia), donde va a quedar libre el repartidor, y si hay un
    cierre de calle activo.
    """
    hour_bucket = round(_current_hour(rt.state) * 4)  # bloques de 15 min
    position = _next_free_position(rt)
    position_key = f"{position[0]:.3f},{position[1]:.3f}" if position else "none"
    closure = rt.state.active_closure["u"] if rt.state.active_closure else "open"
    return f"{hour_bucket}|{position_key}|{closure}"


def _revalue_pending_orders(rt: ShiftRuntime) -> None:
    """Recalcula el Score de las ordenes que siguen en pantalla.

    Antes las evaluaciones se congelaban al generarse: si entraba una hora
    pico o el repartidor se movia al otro lado de la ciudad, las tarjetas
    seguian mostrando el Score viejo. Ahora se recalculan, con dos frenos
    porque cada reevaluacion cuesta dos busquedas A* por orden:
      - solo si cambio `_revaluation_context`,
      - y no mas seguido que REVALUATION_COOLDOWN_SIM_MINUTES.

    Cuando un Score se mueve de forma material (o cambia de signo) se avisa
    en el log: que una oferta se encarezca sin explicacion es peor que el
    Score viejo.
    """
    state = rt.state
    if not state.pending_orders:
        return

    now_sim_minutes = world_clock.sim_elapsed_seconds() / 60
    if now_sim_minutes - state.last_revaluation_sim_minute < REVALUATION_COOLDOWN_SIM_MINUTES:
        return

    context = _revaluation_context(rt)
    if context == state.last_revaluation_context:
        return

    state.last_revaluation_sim_minute = now_sim_minutes
    state.last_revaluation_context = context

    origin = _next_free_position(rt)
    unreachable: list[str] = []

    for order_id, pending in state.pending_orders.items():
        order = pending.order
        previous_score = pending.evaluation.score
        evaluation = rt.delivery_agent.evaluate_order(
            (order["pickup_lat"], order["pickup_lon"]),
            (order["dropoff_lat"], order["dropoff_lon"]),
            order["fare"],
            origin=origin,
        )
        if evaluation is None:
            unreachable.append(order_id)
            continue

        pending.evaluation = evaluation
        _log_score_change(rt, order, previous_score, evaluation.score)

    for order_id in unreachable:
        order = state.pending_orders.pop(order_id).order
        _log(
            rt,
            "order_rejected",
            f"Dropped {order.get('pickup_name') or 'an order'} — no route available right now.",
        )


def _log_score_change(rt: ShiftRuntime, order: dict, previous: float, current: float) -> None:
    changed_sign = (previous >= 0) != (current >= 0)
    reference = max(abs(previous), 1.0)
    materially_changed = abs(current - previous) / reference >= REVALUATION_LOG_THRESHOLD
    if not (changed_sign or materially_changed):
        return

    name = order.get("pickup_name") or "an order"
    direction = "better" if current > previous else "worse"
    _log(
        rt,
        "order_generated",
        f"{name} got {direction} with the traffic: Score ${previous:.2f} → ${current:.2f}",
    )


# --------------------------------------------------------------------------
# Generacion y decision de ordenes
# --------------------------------------------------------------------------


def _generate_and_evaluate_order(rt: ShiftRuntime, db: Session, virtual_hour: float) -> bool:
    """Crea una orden, la evalua para ambos agentes y la deja pendiente (o la
    decide sola si el turno es autonomo).

    Devuelve False si la orden resulto inservible (pickup o dropoff
    inalcanzables, tipicamente por un cierre de calle): en ese caso no se
    guarda nada y simplemente no llega esa oferta.
    """
    state = rt.state
    origin = _next_free_position(rt)
    # La oferta se sesga a la ZONA del turno, no a donde esta el inteligente:
    # ver el comentario de `zone_center` en session_state.py.
    order = generate_order(
        rt.graph, rt.restaurants, virtual_hour=virtual_hour, near_point=state.zone_center
    )

    evaluation = rt.delivery_agent.evaluate_order(
        (order["pickup_lat"], order["pickup_lon"]),
        (order["dropoff_lat"], order["dropoff_lon"]),
        order["fare"],
        origin=origin,
    )
    if evaluation is None:
        return False

    pending = PendingOrder(order=order, evaluation=evaluation)
    state.pending_orders[order["id"]] = pending

    db.add(
        OrderModel(
            id=uuid.UUID(order["id"]),
            run_id=uuid.UUID(state.run_id),
            pickup_lat=order["pickup_lat"],
            pickup_lon=order["pickup_lon"],
            pickup_name=order.get("pickup_name"),
            dropoff_lat=order["dropoff_lat"],
            dropoff_lon=order["dropoff_lon"],
            fare=order["fare"],
        )
    )
    db.commit()

    _record_novice_decision(rt, db, order, virtual_hour)

    _log(
        rt,
        "order_generated",
        f"New order from {order.get('pickup_name') or 'a restaurant'} — "
        f"${order['fare']:.2f} MXN, estimated Score ${evaluation.score:.2f}",
    )

    if state.autonomous:
        _decide_autonomously(rt, db, order["id"], pending)

    return True


def _policy_state(rt: ShiftRuntime) -> policy.PolicyState:
    return policy.PolicyState(
        orders_accepted=rt.state.orders_accepted,
        virtual_minutes_elapsed=(world_clock.sim_elapsed_seconds() - rt.state.started_sim_seconds) / 60,
    )


def _agent_recommendation(rt: ShiftRuntime, evaluation: OrderEvaluation) -> bool:
    return policy.should_accept(evaluation, _policy_state(rt))


def _decide_autonomously(rt: ShiftRuntime, db: Session, order_id: str, pending: PendingOrder) -> None:
    """El agente decide sin el humano (turno autonomo).

    Tiene capacidad limitada: si ya trae `max_batch_orders` entregas en cola,
    rechaza aunque la oferta sea buena. Sin ese tope "aceptar todo" y "elegir
    bien" darian lo mismo, y la comparacion contra el novato no mediria nada.
    """
    at_capacity = len(rt.state.active_deliveries) >= settings.max_batch_orders
    accept = (not at_capacity) and _agent_recommendation(rt, pending.evaluation)
    _settle_order(rt, db, order_id, accept=accept, reason="capacity" if at_capacity else "policy")


def _record_novice_decision(
    rt: ShiftRuntime,
    db: Session,
    order: dict,
    virtual_hour: float,
) -> None:
    """El agente novato decide la misma orden al instante: la acepta siempre
    que este libre.

    El "siempre que este libre" importa para que la comparacion sea honesta:
    un repartidor no puede cursar diez entregas a la vez. Si esta ocupado,
    la oferta se le va — que es justo el costo de haber aceptado algo malo.

    Escribe su propio TripRecord bajo `novice_run_id` (mismo `session_id` que
    el turno inteligente), que es lo que alimenta las tarjetas "Novice" de
    /stats/live y la comparacion de /stats/scoreboard.
    """
    state = rt.state
    now_s = world_clock.sim_elapsed_seconds()
    if now_s < state.novice_busy_until_sim_seconds:
        return

    evaluation = rt.novice_agent.evaluate_order(
        (order["pickup_lat"], order["pickup_lon"]),
        (order["dropoff_lat"], order["dropoff_lon"]),
        order["fare"],
    )
    if evaluation is None:
        return

    rt.novice_agent.commit((order["dropoff_lat"], order["dropoff_lon"]))
    state.novice_position = rt.novice_agent.position
    state.novice_busy_until_sim_seconds = now_s + evaluation.time_minutes * 60
    state.novice_earnings += evaluation.score

    db.add(
        TripRecord(
            run_id=uuid.UUID(state.novice_run_id),
            order_id=uuid.UUID(order["id"]),
            agent_type="novato",
            vehicle=state.vehicle,
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


def _settle_order(rt: ShiftRuntime, db: Session, order_id: str, accept: bool, reason: str = "driver") -> None:
    """Cierra una orden pendiente: persiste la decision, cobra y arranca la
    entrega. Unico camino por el que pasan tanto el conductor como el modo
    autonomo, para que no se dupliquen las reglas del dinero."""
    state = rt.state
    pending = state.pending_orders.pop(order_id, None)
    if pending is None:
        raise HTTPException(404, "That order is no longer pending")

    evaluation = pending.evaluation
    gas_cost = evaluation.distance_km * evaluation.gas_cost_per_km
    time_cost = evaluation.time_minutes * settings.time_cost_per_minute
    net_delta = evaluation.score if accept else 0.0
    state.net_earnings += net_delta

    if accept:
        state.orders_accepted += 1
        _start_delivery(rt, pending.order)

    db.add(
        TripRecord(
            run_id=uuid.UUID(state.run_id),
            order_id=uuid.UUID(order_id),
            agent_type="inteligente",
            vehicle=state.vehicle,
            accepted=accept,
            fare=evaluation.fare,
            distance_km=evaluation.distance_km,
            time_minutes=evaluation.time_minutes,
            gas_cost=gas_cost,
            time_cost=time_cost,
            score=evaluation.score,
            net_earnings_delta=net_delta,
            virtual_hour=_current_hour(state),
        )
    )
    db.commit()

    pickup_name = pending.order.get("pickup_name") or "the order"
    rationale = policy.explain(evaluation, _policy_state(rt))
    if accept:
        _log(rt, "order_accepted", f"Accepted {pickup_name} — net ${evaluation.score:.2f} MXN · {rationale}")
    elif reason == "capacity":
        _log(
            rt,
            "order_rejected",
            f"Skipped {pickup_name} — already carrying {settings.max_batch_orders} deliveries.",
        )
    else:
        _log(rt, "order_rejected", f"Rejected {pickup_name} — {rationale}")


def _start_delivery(rt: ShiftRuntime, order: dict) -> None:
    """Encola la entrega para que el repartidor la recorra en tiempo simulado.

    Si la ruta resulta inalcanzable (cierre de calle justo ahi), se cae al
    comportamiento viejo: el repartidor "aparece" en el dropoff. Perder la
    animacion es preferible a perder la orden que ya se acepto.
    """
    origin = _next_free_position(rt) or (order["pickup_lat"], order["pickup_lon"])
    pickup = (order["pickup_lat"], order["pickup_lon"])
    dropoff = (order["dropoff_lat"], order["dropoff_lon"])

    to_pickup = try_shortest_route(rt.graph, origin, pickup)
    to_dropoff = try_shortest_route(rt.graph, pickup, dropoff)
    if to_pickup is None or to_dropoff is None:
        rt.state.courier_position = dropoff
        rt.delivery_agent.position = dropoff
        return

    route = to_pickup[0] + to_dropoff[0][1:]
    # El tiempo de servicio (esperar la comida, entregarla) tambien ocupa al
    # repartidor, asi que cuenta para cuando se libera.
    total_seconds = route_total_time(rt.graph, route) + settings.service_time_minutes * 60
    rt.state.active_deliveries.append(
        ActiveDelivery(order=order, route=route, total_seconds=total_seconds)
    )


def _log_batching_insight(rt: ShiftRuntime) -> None:
    """Con 2+ ordenes pendientes, corre VRPTW (app.decision.batching) sobre
    todas juntas y, si conviene, lo anuncia en el log — informativo nada
    mas: el frontend no tiene una accion de "aceptar batch", cada orden se
    sigue decidiendo una por una en PendingOrdersPanel.

    Con enfriamiento: resolver el VRPTW pide una matriz de tiempos sobre el
    grafo real (segundos de CPU), y el reloj del mundo sigue corriendo
    mientras la request trabaja.
    """
    state = rt.state
    if len(state.pending_orders) < 2:
        return

    now_sim_minutes = world_clock.sim_elapsed_seconds() / 60
    if now_sim_minutes - state.last_batching_insight_sim_minute < BATCHING_INSIGHT_COOLDOWN_SIM_MINUTES:
        return
    state.last_batching_insight_sim_minute = now_sim_minutes

    start_point = _next_free_position(rt) or _any_pending_pickup(rt)
    orders = [p.order for p in state.pending_orders.values()]
    try:
        plan = batching.plan_batch(rt.graph, start_point, orders)
    except Exception:
        return  # el insight de batching es informativo; nunca debe tumbar el tick
    if plan is None or plan.time_saved_seconds < 30:
        return

    _log(
        rt,
        "order_generated",
        f"Batching tip: doing these {len(orders)} pending orders together saves "
        f"~{plan.time_saved_seconds / 60:.0f} min vs. one at a time.",
    )


def _any_pending_pickup(rt: ShiftRuntime) -> tuple[float, float]:
    first = next(iter(rt.state.pending_orders.values()))
    return (first.order["pickup_lat"], first.order["pickup_lon"])


# --------------------------------------------------------------------------
# Serializacion a la respuesta
# --------------------------------------------------------------------------


def _to_pending_out(rt: ShiftRuntime, order_id: str, pending: PendingOrder) -> PendingOrderOut:
    order = pending.order
    evaluation = pending.evaluation

    # should_accept es una recomendacion (en modo manual el conductor sigue
    # decidiendo via /simulation/decide, ver PendingOrdersPanel.tsx): en vez
    # del corte estatico Score > 0, usa el umbral dinamico de
    # decision.policy, que se vuelve mas permisivo si el repartidor va
    # atrasado en su ritmo de pedidos aceptados.
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
        should_accept=_agent_recommendation(rt, evaluation),
    )


def _to_state(rt: ShiftRuntime) -> SimulationState:
    state = rt.state
    position = _courier_live_position(rt)
    return SimulationState(
        run_id=state.run_id,
        vehicle=state.vehicle,
        virtual_hour=_current_hour(state),
        virtual_minute=world_clock.virtual_minute(),
        is_finished=state.finished,
        net_earnings=round(state.net_earnings, 2),
        god_mode_preset=state.god_mode_preset,
        pending_orders=[_to_pending_out(rt, oid, p) for oid, p in state.pending_orders.items()],
        events=[SimEventOut(**e) for e in state.events],
        # Campos aditivos: el frontend actual los ignora sin romperse
        # (MapView.tsx todavia usa una posicion placeholder).
        sim_time=world_clock.iso_timestamp(),
        time_acceleration=world_clock.acceleration,
        courier_lat=position[0] if position else None,
        courier_lon=position[1] if position else None,
        active_deliveries=len(state.active_deliveries),
        deliveries_completed=state.deliveries_completed,
        orders_accepted=state.orders_accepted,
        novice_earnings=round(state.novice_earnings, 2),
        session_id=state.session_id,
        autonomous=state.autonomous,
    )


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@router.post("/start", response_model=SimulationState)
def start_simulation(payload: SimulationStart, db: Session = Depends(get_session)):
    if payload.vehicle not in {"moto", "auto"}:
        raise HTTPException(400, "vehicle must be 'moto' or 'auto'")

    graph = load_graph()
    load_restaurants()

    run_id = uuid.uuid4()
    novice_run_id = uuid.uuid4()
    session_id = uuid.uuid4()
    now_s = world_clock.sim_elapsed_seconds()
    start_hour = world_clock.virtual_hour()
    start_position = (settings.city_center_lat, settings.city_center_lon)

    state = SessionState(
        run_id=str(run_id),
        novice_run_id=str(novice_run_id),
        session_id=str(session_id),
        vehicle=payload.vehicle,
        started_sim_seconds=now_s,
        last_tick_sim_seconds=now_s,
        autonomous=payload.autonomous,
        courier_position=start_position,
        novice_position=start_position,
        zone_center=start_position,
    )
    rt = ShiftRuntime.hydrate(state)

    mode = "autonomously" if payload.autonomous else "scoring orders for the driver"
    _log(
        rt,
        "shift_started",
        f"Shift started at {world_clock.now():%H:%M} simulated time — the clock runs "
        f"{world_clock.acceleration:.0f}x faster than real life, agent is {mode}.",
    )

    # Un dia simulado completo (1440 min) toma esto en minutos reales; es el
    # equivalente honesto de `real_duration_minutes` ahora que el reloj es
    # global y no por turno.
    real_minutes_per_sim_day = 1440 / world_clock.acceleration

    user_id = uuid.UUID(payload.user_id) if payload.user_id else None
    for rid, agent_type in ((run_id, "inteligente"), (novice_run_id, "novato")):
        db.add(
            SimulationRun(
                id=rid,
                session_id=session_id,
                user_id=user_id,
                agent_type=agent_type,
                vehicle=payload.vehicle,
                start_hour=start_hour,
                shift_duration_minutes=1440,
                real_duration_minutes=real_minutes_per_sim_day,
                is_finished=False,
            )
        )
    db.commit()

    rt.persist()
    return _to_state(rt)


@router.get("/state", response_model=SimulationState)
def get_state(run_id: str, db: Session = Depends(get_session)):
    rt = _load_runtime(run_id)
    _tick(rt, db)
    rt.persist()
    return _to_state(rt)


@router.post("/decide", response_model=SimulationState)
def decide_order(payload: DecisionRequest, db: Session = Depends(get_session)):
    rt = _load_runtime(payload.run_id)
    if rt.state.autonomous:
        raise HTTPException(409, "This shift runs autonomously — the agent decides its own orders")

    _settle_order(rt, db, payload.order_id, accept=payload.accept)
    rt.persist()
    return _to_state(rt)


@router.post("/end", response_model=SimulationState)
def end_simulation(payload: RunIdRequest, db: Session = Depends(get_session)):
    rt = _load_runtime(payload.run_id)
    state = rt.state

    state.finished = True
    state.pending_orders.clear()
    state.active_deliveries.clear()
    if state.active_closure is not None:
        clear_road_closure(rt.graph, state.active_closure["u"], state.active_closure["v"])
        state.active_closure = None
    _log(rt, "shift_ended", f"Shift ended — net earnings ${state.net_earnings:.2f} MXN")

    for run_id, total in ((state.run_id, state.net_earnings), (state.novice_run_id, state.novice_earnings)):
        run = db.get(SimulationRun, uuid.UUID(run_id))
        if run is not None:
            run.is_finished = True
            run.ended_at = datetime.utcnow()
            run.final_net_earnings = round(total, 2)
    db.commit()

    rt.persist()
    return _to_state(rt)


@router.post("/god-mode", response_model=SimulationState)
def god_mode(payload: GodModeRequest, db: Session = Depends(get_session)):
    rt = _load_runtime(payload.run_id)
    state = rt.state

    if payload.preset is None:
        state.hour_override = None
        state.god_mode_preset = None
        if state.active_closure is not None:
            clear_road_closure(rt.graph, state.active_closure["u"], state.active_closure["v"])
            state.active_closure = None
        _log(rt, "god_mode", "Traffic back to normal, roads reopened.")
    else:
        if payload.preset not in GOD_MODE_PRESETS:
            raise HTTPException(400, f"Unknown preset, options: {list(GOD_MODE_PRESETS)}")
        state.hour_override = GOD_MODE_PRESETS[payload.preset]
        state.god_mode_preset = payload.preset
        _log(rt, "god_mode", f"God Mode: jumped to {payload.preset} traffic.")

        # El reto pide que el agente reaccione a un cierre de calle a mitad
        # de turno ademas del surge de trafico; no hay un boton nuevo en la
        # UI para esto (no se toco el frontend), asi que se aprovecha el
        # preset de hora pico de salida que ya existe.
        if payload.preset == ROAD_CLOSURE_PRESET and state.active_closure is None:
            near = _courier_live_position(rt) or (settings.city_center_lat, settings.city_center_lon)
            closure = simulate_random_closure(rt.graph, near_point=near)
            if closure is not None:
                state.active_closure = closure
                street = closure["street_name"] or "a nearby street"
                _log(rt, "god_mode", f"Accident reported on {street} — the agent must reroute around it.")

    _tick(rt, db)
    rt.persist()
    return _to_state(rt)


@router.post("/benchmark", response_model=BenchmarkResult)
def benchmark(payload: BenchmarkRequest, db: Session = Depends(get_session)):
    """Corre un turno completo headless: el agente decide solo contra el
    novato que acepta todo, sobre el MISMO stream de ordenes.

    Es el numero de "cuanto gana el agente vs un baseline simple" sobre un
    turno que no ha visto. No usa el reloj del mundo: simula sus propias
    horas de corrido, asi que un turno de 8 horas se resuelve en segundos en
    vez de en 16 minutos reales.
    """
    if payload.hours <= 0 or payload.hours > 24:
        raise HTTPException(400, "hours must be between 0 and 24")

    return BenchmarkResult(**run_benchmark(db, hours=payload.hours, start_hour=payload.start_hour, vehicle=payload.vehicle, user_id=payload.user_id))
