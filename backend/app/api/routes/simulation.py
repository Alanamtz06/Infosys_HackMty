"""Endpoints de control de la simulacion: arrancar/terminar un turno,
generar y decidir ordenes en vivo, y el log de eventos.

El tiempo NO arranca con el turno: `engine.virtual_clock.world_clock` es un
reloj global que corre desde que prende el proceso, acelerado
(`TIME_ACCELERATION`), y nunca se detiene. Un turno solo se engancha a la
hora que el mundo ya traia; termina cuando el usuario llama a
/simulation/end. Todo lo que se registra en el log en vivo lleva la hora
SIMULADA, no la hora real del servidor.

El agente calcula el Score y una recomendacion (decision.policy) para cada
oferta, pero SIEMPRE decide el conductor via /simulation/decide — no existe
un modo donde el agente acepte/rechace por su cuenta durante un turno en
vivo. Es deliberado: el conductor real decide, el agente solo aconseja (ver
OrdersWidget.tsx en el frontend). La UNICA comparacion automatizada
agente-vs-agente vive en /simulation/benchmark, un turno headless aparte que
no toca ningun turno en curso ni sus ordenes.

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
import osmnx as ox
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
from app.engine.zones import nearest_zone
from app.engine.routing import (
    downsample_coordinates,
    edge_times_for_route,
    position_along_route,
    route_coordinates,
    route_total_time,
    try_shortest_route,
)
from app.engine.virtual_clock import world_clock
from app.schemas.simulation import (
    ActiveRouteOut,
    BenchmarkRequest,
    BenchmarkResult,
    DecisionRequest,
    NoviceOutcomeOut,
    PendingOrderOut,
    RouteLegOut,
    RoutePreviewOut,
    RouteStopOut,
    RunIdRequest,
    SimEventOut,
    SimulationStart,
    SimulationState,
)

router = APIRouter(prefix="/simulation", tags=["simulation"])

MAX_PENDING_ORDERS = 5
MAX_EVENTS = 200

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
    es barato.
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
    return world_clock.virtual_hour()


def _courier_live_position(rt: ShiftRuntime) -> tuple[float, float] | None:
    """Donde va el repartidor AHORA: interpolado sobre la ruta si esta
    entregando, o su ultima posicion conocida si esta libre."""
    if rt.state.active_deliveries:
        head = rt.state.active_deliveries[0]
        if head.started_sim_seconds is not None:
            elapsed = world_clock.sim_elapsed_seconds() - head.started_sim_seconds
            try:
                return position_along_route(
                    rt.graph, head.route, elapsed, head.dwell_checkpoints, head.edge_times or None
                )
            except (ValueError, KeyError):
                pass
    return rt.state.courier_position


def _next_free_position(rt: ShiftRuntime) -> tuple[float, float] | None:
    """Donde va a estar el repartidor cuando se desocupe: el dropoff de la
    ultima entrega en cola. Es el origen correcto para evaluar una orden
    nueva (no donde esta parado ahora, que ya esta comprometido)."""
    if rt.state.active_deliveries:
        last = rt.state.active_deliveries[-1]
        if last.extra_order is not None:
            # Mochila combinada: el VRPTW pudo haber elegido terminar en
            # cualquiera de los dos dropoffs, no necesariamente el de
            # `last.order` — la ultima parada real es la fuente de verdad.
            final_stop = last.stop_markers[-1]
            return (final_stop["lat"], final_stop["lon"])
        return (last.order["dropoff_lat"], last.order["dropoff_lon"])
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

        if head.extra_order is not None:
            # Mochila combinada: la ruta pudo terminar en el dropoff de
            # cualquiera de los dos pedidos — la ultima parada real manda.
            final_stop = head.stop_markers[-1]
            rt.state.courier_position = (final_stop["lat"], final_stop["lon"])
            completed_orders = [head.order, head.extra_order]
        else:
            rt.state.courier_position = (head.order["dropoff_lat"], head.order["dropoff_lon"])
            completed_orders = [head.order]

        rt.delivery_agent.position = rt.state.courier_position
        rt.state.deliveries_completed += len(completed_orders)
        rt.state.active_deliveries.pop(0)
        for order in completed_orders:
            _log(
                rt,
                "order_accepted",
                f"Delivered {order.get('pickup_name') or 'the order'} — "
                f"{head.total_seconds / 60:.0f} min on the road.",
            )


def _is_picked_up(delivery: ActiveDelivery) -> bool:
    """True si el repartidor ya paso por el pickup de `delivery.order` (el
    tramo `to_pickup_seconds` ya se cumplio en tiempo simulado)."""
    if delivery.started_sim_seconds is None:
        return False
    elapsed = world_clock.sim_elapsed_seconds() - delivery.started_sim_seconds
    return elapsed >= delivery.to_pickup_seconds


def _active_order_count(rt: ShiftRuntime) -> int:
    """Pedidos en la mochila ahora mismo (0/1/2) — no confundir con
    `len(active_deliveries)`, que a lo mas vale 1 (el 2do pedido se fusiona
    en la misma entrega, ver `_merge_into_backpack`)."""
    deliveries = rt.state.active_deliveries
    if not deliveries:
        return 0
    return 2 if deliveries[0].extra_order is not None else 1


def _fits_strict_corridor(active_order: dict, candidate_order: dict) -> bool:
    """Modo estricto de la mochila (pedido activo AUN sin recoger): el 2do
    pedido solo se considera "de paso" si su pickup queda cerca del pickup
    del activo Y su dropoff queda cerca del dropoff del activo — rutas casi
    paralelas. "Cerca" es proporcional al propio trayecto del pedido activo
    (pickup->dropoff), no un radio fijo, para que se adapte a pedidos cortos
    y largos por igual. Great-circle (no ruteo): esto corre en el tick, igual
    que `order_generator._restaurants_near`."""
    active_leg_km = (
        ox.distance.great_circle(
            active_order["pickup_lat"],
            active_order["pickup_lon"],
            active_order["dropoff_lat"],
            active_order["dropoff_lon"],
        )
        / 1000
    )
    threshold_km = settings.backpack_strict_proximity_ratio * active_leg_km

    pickup_gap_km = (
        ox.distance.great_circle(
            candidate_order["pickup_lat"],
            candidate_order["pickup_lon"],
            active_order["pickup_lat"],
            active_order["pickup_lon"],
        )
        / 1000
    )
    dropoff_gap_km = (
        ox.distance.great_circle(
            candidate_order["dropoff_lat"],
            candidate_order["dropoff_lon"],
            active_order["dropoff_lat"],
            active_order["dropoff_lon"],
        )
        / 1000
    )
    return pickup_gap_km <= threshold_km and dropoff_gap_km <= threshold_km


def _evaluate_backpack_candidate(
    rt: ShiftRuntime, existing: ActiveDelivery, candidate_order: dict
) -> OrderEvaluation | None:
    """Costo-beneficio MARGINAL de aceptar `candidate_order` encima de
    `existing`: la diferencia entre la ruta combinada optima (VRPTW) y lo que
    ya costaria terminar `existing` solo. Un pickup genuinamente "de paso"
    sale casi gratis (score alto); uno que obliga a desviarse sale caro
    (score bajo o negativo) — este es el criterio multilateral pedido, ya que
    el VRPTW optimiza conjuntamente el orden de TODAS las paradas."""
    live_position = _courier_live_position(rt)
    if live_position is None:
        return None

    picked_up = _is_picked_up(existing)
    if picked_up:
        alone_leg = try_shortest_route(rt.graph, live_position, (existing.order["dropoff_lat"], existing.order["dropoff_lon"]))
        if alone_leg is None:
            return None
        alone_seconds = alone_leg[1] + settings.service_time_minutes * 60
        alone_meters = alone_leg[2]
    else:
        to_pickup = try_shortest_route(rt.graph, live_position, (existing.order["pickup_lat"], existing.order["pickup_lon"]))
        if to_pickup is None:
            return None
        to_dropoff = try_shortest_route(
            rt.graph, (existing.order["pickup_lat"], existing.order["pickup_lon"]),
            (existing.order["dropoff_lat"], existing.order["dropoff_lon"]),
        )
        if to_dropoff is None:
            return None
        alone_seconds = to_pickup[1] + to_dropoff[1] + settings.service_time_minutes * 60
        alone_meters = to_pickup[2] + to_dropoff[2]

    # include_route=False: solo puntuamos la oferta, no hace falta la ruta
    # real todavia (eso se recalcula al aceptar, ver _merge_into_backpack) —
    # esto evita las busquedas A* de mas que hacian el tick lento/se
    # "congelaba" con varias ofertas pendientes (ver profile_backpack.py).
    combined = batching.plan_backpack_route(
        rt.graph, live_position, existing.order, picked_up, candidate_order, include_route=False
    )
    if combined is None:
        return None

    marginal_seconds = max(combined.total_seconds - alone_seconds, 0.0)
    if combined.total_meters > 0:
        marginal_meters = max(combined.total_meters - alone_meters, 0.0)
    else:
        # Sin ruta real (modo rapido) no hay distancia directa: se estima con
        # la velocidad promedio ya medida en el tramo "solo" (mismo grafo,
        # misma zona) en vez de pagar otra bateria de busquedas de ruta solo
        # para convertir tiempo a metros.
        avg_speed_m_per_s = alone_meters / alone_seconds if alone_seconds > 0 else 0.0
        marginal_meters = max(marginal_seconds * avg_speed_m_per_s, 0.0)

    return OrderEvaluation(
        fare=candidate_order["fare"],
        distance_km=marginal_meters / 1000,
        time_minutes=marginal_seconds / 60,
        vehicle=VehicleType(rt.state.vehicle),
    )


def _is_backpack_marginal_eligible(rt: ShiftRuntime, order: dict) -> bool:
    """True si `order` calificaria para el costo-beneficio MARGINAL de
    mochila (VRPTW) en vez de la evaluacion normal: hay exactamente 1 pedido
    activo sin fusionar todavia, y o ya se recogio (modo normal) o el
    candidato pasa el filtro geografico estricto (modo estricto, ver
    `_fits_strict_corridor`)."""
    deliveries = rt.state.active_deliveries
    if not (len(deliveries) == 1 and deliveries[0].extra_order is None):
        return False
    existing = deliveries[0]
    return _is_picked_up(existing) or _fits_strict_corridor(existing.order, order)


def _evaluate_order_for_offer(rt: ShiftRuntime, order: dict) -> OrderEvaluation | None:
    """Punto unico de evaluacion de una oferta (nueva o reevaluada): decide
    si aplica el costo marginal de mochila (1 pedido activo, sin extra
    todavia) o la evaluacion de siempre (mochila vacia o ya llena)."""
    deliveries = rt.state.active_deliveries
    if len(deliveries) == 1 and deliveries[0].extra_order is None:
        existing = deliveries[0]
        if _is_backpack_marginal_eligible(rt, order):
            try:
                evaluation = _evaluate_backpack_candidate(rt, existing, order)
            except Exception:
                # El costo marginal es un VRPTW sobre el grafo real — nunca
                # debe tumbar el tick por una falla del solver (mismo
                # criterio que `_log_batching_insight`).
                evaluation = None
            if evaluation is not None:
                return evaluation
        # Modo estricto sin corredor, o el plan combinado resulto infactible
        # (p. ej. un cierre de calle a mitad de ruta): se cotiza como un
        # pedido totalmente aparte, parado desde donde esta AHORA el
        # repartidor — sin credito por compartir ruta con el pedido activo,
        # lo cual naturalmente sale caro y desalienta aceptarlo (el humano
        # sigue pudiendo forzarlo).
        return rt.delivery_agent.evaluate_order(
            (order["pickup_lat"], order["pickup_lon"]),
            (order["dropoff_lat"], order["dropoff_lon"]),
            order["fare"],
            origin=_courier_live_position(rt),
        )

    origin = _next_free_position(rt)
    return rt.delivery_agent.evaluate_order(
        (order["pickup_lat"], order["pickup_lon"]),
        (order["dropoff_lat"], order["dropoff_lon"]),
        order["fare"],
        origin=origin,
    )


def _merge_into_backpack(rt: ShiftRuntime, candidate_order: dict) -> None:
    """Fusiona `candidate_order` en la entrega activa unica, reemplazandola
    por una ruta combinada real (VRPTW + calles reales). Nunca se agrega una
    2da entrada a `active_deliveries` — la mochila tiene capacidad 2 y cabe
    entera en la entrega que ya existe."""
    existing = rt.state.active_deliveries[0]
    live_position = _courier_live_position(rt) or (
        existing.order["pickup_lat"],
        existing.order["pickup_lon"],
    )
    picked_up = _is_picked_up(existing)

    try:
        plan = batching.plan_backpack_route(rt.graph, live_position, existing.order, picked_up, candidate_order)
    except Exception:
        plan = None
    if plan is None:
        raise HTTPException(409, "No route available to combine this order with your current delivery")

    rt.state.active_deliveries[0] = ActiveDelivery(
        order=existing.order,
        extra_order=candidate_order,
        route=plan.route,
        total_seconds=plan.total_seconds,
        started_sim_seconds=world_clock.sim_elapsed_seconds(),
        pickup_index=plan.pickup_index,
        to_pickup_seconds=plan.to_pickup_seconds,
        stop_markers=plan.stop_markers,
        dwell_checkpoints=plan.dwell_checkpoints,
        # Congelado AQUI, mismo instante que `plan.total_seconds` (ver
        # `edge_times_for_route` y el comentario en `_start_delivery`).
        edge_times=edge_times_for_route(rt.graph, plan.route),
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
    por hora del dia) y donde va a quedar libre el repartidor.
    """
    hour_bucket = round(_current_hour(rt.state) * 4)  # bloques de 15 min
    position = _next_free_position(rt)
    position_key = f"{position[0]:.3f},{position[1]:.3f}" if position else "none"
    return f"{hour_bucket}|{position_key}"


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

    unreachable: list[str] = []

    for order_id, pending in state.pending_orders.items():
        order = pending.order
        if _is_backpack_marginal_eligible(rt, order):
            # El costo marginal de mochila es un VRPTW + varias busquedas de
            # ruta reales sobre el grafo COMPLETO (~29k nodos en la ZMM): un
            # solo calculo cuesta 2-4s medido en produccion (profile_backpack.py).
            # Recalcularlo aqui para cada oferta pendiente, en cada ciclo de
            # reevaluacion, fue lo que "congelaba" el motor de generacion de
            # ordenes (un solo tick podia tardar >10s con varias ofertas
            # pendientes). Se calcula UNA vez al generar la oferta
            # (`_generate_and_evaluate_order`) y se deja congelado hasta que
            # se acepte/rechace o cambie de modo (estricto -> normal al
            # recoger el pedido activo, que si dispara un recalculo nuevo la
            # primera vez que dejes de calificar aqui).
            continue

        previous_score = pending.evaluation.score
        evaluation = _evaluate_order_for_offer(rt, order)
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
    """Crea una orden, la evalua para ambos agentes y la deja pendiente,
    esperando la decision del conductor.

    Devuelve False si la orden resulto inservible (pickup o dropoff
    inalcanzables, tipicamente por un cierre de calle): en ese caso no se
    guarda nada y simplemente no llega esa oferta.
    """
    state = rt.state
    # La oferta se sesga a la ZONA del turno, no a donde esta el inteligente:
    # ver el comentario de `zone_center` en session_state.py.
    order = generate_order(
        rt.graph, rt.restaurants, virtual_hour=virtual_hour, near_point=state.zone_center
    )

    evaluation = _evaluate_order_for_offer(rt, order)
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

    _record_novice_decision(rt, db, order, virtual_hour, pending)
    _record_autonomous_decision(rt, db, order, virtual_hour, evaluation)

    _log(
        rt,
        "order_generated",
        f"New order from {order.get('pickup_name') or 'a restaurant'} — "
        f"${order['fare']:.2f} MXN, estimated Score ${evaluation.score:.2f}",
    )

    return True


def _policy_state(rt: ShiftRuntime) -> policy.PolicyState:
    return policy.PolicyState(
        orders_accepted=rt.state.orders_accepted,
        virtual_minutes_elapsed=(world_clock.sim_elapsed_seconds() - rt.state.started_sim_seconds) / 60,
    )


def _agent_recommendation(rt: ShiftRuntime, evaluation: OrderEvaluation) -> bool:
    return policy.should_accept(evaluation, _policy_state(rt))


def _record_novice_decision(
    rt: ShiftRuntime,
    db: Session,
    order: dict,
    virtual_hour: float,
    pending: PendingOrder,
) -> None:
    """El agente novato decide la misma orden al instante: la acepta siempre
    que este libre.

    El "siempre que este libre" importa para que la comparacion sea honesta:
    un repartidor no puede cursar diez entregas a la vez. Si esta ocupado,
    la oferta se le va — que es justo el costo de haber aceptado algo malo.

    Escribe su propio TripRecord bajo `novice_run_id` (mismo `session_id` que
    el turno inteligente), que es lo que alimenta las tarjetas "Novice" de
    /stats/live y la comparacion de /stats/scoreboard. Ademas deja el
    veredicto en `pending.novice_outcome`, para que el panel de ofertas lo
    muestre al lado del veredicto del inteligente sin volver a calcularlo.
    """
    state = rt.state
    now_s = world_clock.sim_elapsed_seconds()
    if now_s < state.novice_busy_until_sim_seconds:
        pending.novice_outcome = {"outcome": "busy"}
        return

    evaluation = rt.novice_agent.evaluate_order(
        (order["pickup_lat"], order["pickup_lon"]),
        (order["dropoff_lat"], order["dropoff_lon"]),
        order["fare"],
    )
    if evaluation is None:
        pending.novice_outcome = {"outcome": "unreachable"}
        return

    rt.novice_agent.commit((order["dropoff_lat"], order["dropoff_lon"]))
    state.novice_position = rt.novice_agent.position
    state.novice_busy_until_sim_seconds = now_s + evaluation.time_minutes * 60
    state.novice_earnings += evaluation.score

    pending.novice_outcome = {
        "outcome": "accepted",
        "score": evaluation.score,
        "fare": evaluation.fare,
        "distance_km": evaluation.distance_km,
        "time_minutes": evaluation.time_minutes,
    }

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


def _autonomous_policy_state(rt: ShiftRuntime) -> policy.PolicyState:
    """Ritmo del autonomo, INDEPENDIENTE del contador del humano
    (`_policy_state`) — cada agente relaja su tarifa de reserva segun su
    propio atraso, no el ajeno."""
    return policy.PolicyState(
        orders_accepted=rt.state.autonomous_orders_accepted,
        virtual_minutes_elapsed=(world_clock.sim_elapsed_seconds() - rt.state.started_sim_seconds) / 60,
    )


def _record_autonomous_decision(
    rt: ShiftRuntime, db: Session, order: dict, virtual_hour: float, evaluation: OrderEvaluation
) -> None:
    """El tercer agente decide la MISMA oferta que ya se evaluo para el humano
    (mismos numeros, `evaluation` reusada — nada de rutear otra vez) con la
    MISMA regla (`decision.policy.should_accept`), sin esperar a que nadie
    apriete Aceptar/Rechazar.

    A proposito SIN capacidad ni posicion propia (a diferencia del novato,
    que si "ocupa tiempo" con `busy_until`): este agente no compite por
    entregas reales, es una referencia PURA de calidad de decision — que tan
    seguido el criterio dice "si" sobre CADA oferta que aparece, para poder
    comparar y mejorar las decisiones futuras. Meterle un limite de capacidad
    lo volveria un tercer repartidor mas (con su propia suerte de agenda),
    exactamente lo que ya mide el novato; el valor de este agente es medir la
    politica en aislamiento, sin ese ruido.

    Es lo que permite comparar los tres en tiempo real en el dashboard
    (`/stats/live`), a diferencia de `/simulation/benchmark`, que corre un
    turno headless aparte sobre un stream distinto.
    """
    state = rt.state
    if not state.autonomous_run_id:
        # Turno que arranco antes de que este tercer agente existiera y
        # sigue vivo en Redis tras un deploy — no hay run_id donde escribir.
        return

    accept = policy.should_accept(evaluation, _autonomous_policy_state(rt))
    net_delta = evaluation.score if accept else 0.0

    if accept:
        state.autonomous_earnings += evaluation.score
        state.autonomous_orders_accepted += 1

    db.add(
        TripRecord(
            run_id=uuid.UUID(state.autonomous_run_id),
            order_id=uuid.UUID(order["id"]),
            agent_type="autonomo",
            vehicle=state.vehicle,
            accepted=accept,
            fare=evaluation.fare,
            distance_km=evaluation.distance_km,
            time_minutes=evaluation.time_minutes,
            gas_cost=evaluation.distance_km * evaluation.gas_cost_per_km,
            time_cost=evaluation.time_minutes * settings.time_cost_per_minute,
            score=evaluation.score,
            net_earnings_delta=net_delta,
            virtual_hour=virtual_hour,
        )
    )
    db.commit()


def _settle_order(rt: ShiftRuntime, db: Session, order_id: str, accept: bool) -> None:
    """Cierra una orden pendiente: persiste la decision, cobra y arranca la
    entrega. Unico camino por el que se resuelve una oferta — siempre a partir
    de una decision explicita del conductor via /simulation/decide, para que
    no se dupliquen las reglas del dinero."""
    state = rt.state
    if accept and _active_order_count(rt) >= settings.max_active_deliveries:
        raise HTTPException(409, "Backpack is full (2/2) — deliver one before accepting another.")

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
        if state.active_deliveries and state.active_deliveries[0].extra_order is None:
            _merge_into_backpack(rt, pending.order)
        else:
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
        ActiveDelivery(
            order=order,
            route=route,
            total_seconds=total_seconds,
            # Indice sobre los NODOS, no sobre las coordenadas dibujadas: la
            # geometria se recalcula (y se adelgaza) en cada respuesta, asi
            # que un indice sobre ella quedaria desfasado.
            pickup_index=len(to_pickup[0]) - 1,
            to_pickup_seconds=to_pickup[1],
            # La pausa de servicio ocurre AL LLEGAR al pickup (esperando la
            # comida), no al final de la ruta — ver position_along_route.
            dwell_checkpoints=[(to_pickup[1], settings.service_time_minutes * 60)],
            # Congelado AQUI, mismo instante que `total_seconds`: el trafico
            # sigue cambiando en los ticks siguientes (`apply_traffic`) y
            # `position_along_route` no debe releerlo en vivo para una
            # entrega ya en curso (ver `edge_times_for_route`).
            edge_times=edge_times_for_route(rt.graph, route),
        )
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


def _split_route_geometry(
    graph: nx.MultiDiGraph, route: list[int], pickup_index: int, max_points: int = 400
) -> tuple[list[list[float]], int]:
    """La ruta como coordenadas `[lon, lat]` + el indice donde cae el pickup.

    Los dos tramos (ida al restaurante / entrega) se adelgazan por separado a
    proposito: si se adelgazara la polilinea completa de una, el punto del
    pickup podria desaparecer y el indice dejaria de apuntar a donde
    realmente esta la parada.
    """
    if not route:
        return [], 0

    idx = min(max(pickup_index, 0), len(route) - 1)
    budget = max(max_points // 2, 2)
    leg_a = downsample_coordinates(route_coordinates(graph, route[: idx + 1]), budget)
    leg_b = downsample_coordinates(route_coordinates(graph, route[idx:]), budget)

    if leg_a and leg_b and leg_a[-1] == leg_b[0]:
        leg_b = leg_b[1:]

    coords = [[lon, lat] for lon, lat in leg_a + leg_b]
    return coords, max(len(leg_a) - 1, 0)


def _stops_for(
    order: dict,
    origin: tuple[float, float],
    to_pickup_minutes: float,
    total_minutes: float,
) -> list[RouteStopOut]:
    """Las tres paradas de una entrega, en el orden en que se visitan."""
    return [
        RouteStopOut(
            kind="courier",
            label="You are here",
            lat=origin[0],
            lon=origin[1],
            eta_minutes=0.0,
        ),
        RouteStopOut(
            kind="pickup",
            label=order.get("pickup_name") or "Pick up the order",
            lat=order["pickup_lat"],
            lon=order["pickup_lon"],
            eta_minutes=round(to_pickup_minutes, 1),
        ),
        RouteStopOut(
            kind="dropoff",
            label="Drop off to the customer",
            lat=order["dropoff_lat"],
            lon=order["dropoff_lon"],
            eta_minutes=round(total_minutes, 1),
        ),
    ]


def _stops_for_delivery(delivery: ActiveDelivery, origin: tuple[float, float]) -> list[RouteStopOut]:
    """Las paradas de una entrega EN CURSO, en orden de visita — delega en
    `_stops_for` para el caso normal (1 pedido); para una mochila combinada
    (2 pedidos) arma la lista completa a partir de `stop_markers`."""
    if delivery.extra_order is None:
        return _stops_for(delivery.order, origin, delivery.to_pickup_seconds / 60, delivery.total_seconds / 60)

    stops = [
        RouteStopOut(kind="courier", label="You are here", lat=origin[0], lon=origin[1], eta_minutes=0.0)
    ]
    for marker in delivery.stop_markers:
        default_label = "Pick up the order" if marker["kind"] == "pickup" else "Drop off to the customer"
        stops.append(
            RouteStopOut(
                kind=marker["kind"],
                label=marker["label"] or default_label,
                lat=marker["lat"],
                lon=marker["lon"],
                eta_minutes=round(marker["eta_seconds"] / 60, 1),
                order_id=marker["order_id"],
            )
        )
    return stops


def _to_active_routes(rt: ShiftRuntime) -> list[ActiveRouteOut]:
    """Las entregas en curso con su geometria y el avance real encima de ella.

    Es lo que mueve el vehiculo en el mapa: `progress` va sobre el TIEMPO
    total (incluye el tiempo de servicio), asi que la barra de avance y el
    marcador cuentan la misma historia que el reloj del mundo.
    """
    now_s = world_clock.sim_elapsed_seconds()
    routes: list[ActiveRouteOut] = []

    for i, delivery in enumerate(rt.state.active_deliveries):
        # La geometria de una entrega no cambia entre aceptarla y
        # completarla: se calcula UNA vez (primer poll que la ve) y se
        # reusa en los siguientes, en vez de recorrer y adelgazar la ruta
        # entera cada 2s durante los minutos que dura la entrega.
        if delivery._geometry_cache is None:
            delivery._geometry_cache = _split_route_geometry(rt.graph, delivery.route, delivery.pickup_index)
        coords, pickup_idx = delivery._geometry_cache
        if not coords:
            continue

        # Una entrega encolada todavia no arranca: se dibuja completa, con el
        # vehiculo parado en su punto de salida.
        elapsed = 0.0
        if delivery.started_sim_seconds is not None:
            elapsed = max(now_s - delivery.started_sim_seconds, 0.0)

        try:
            lat, lon = position_along_route(
                rt.graph, delivery.route, elapsed, delivery.dwell_checkpoints, delivery.edge_times or None
            )
        except (ValueError, KeyError):
            lon, lat = coords[0]

        total = delivery.total_seconds
        progress = min(elapsed / total, 1.0) if total > 0 else 1.0
        origin = (coords[0][1], coords[0][0])

        fare = delivery.order["fare"] + (delivery.extra_order["fare"] if delivery.extra_order else 0)
        routes.append(
            ActiveRouteOut(
                order_id=delivery.order["id"],
                pickup_name=delivery.order.get("pickup_name"),
                coordinates=coords,
                pickup_index=pickup_idx,
                stops=_stops_for_delivery(delivery, origin),
                progress=round(progress, 4),
                phase="to_pickup" if elapsed < delivery.to_pickup_seconds else "to_dropoff",
                courier_lat=lat,
                courier_lon=lon,
                eta_minutes=round(max(total - elapsed, 0.0) / 60, 1),
                fare=fare,
                is_current=i == 0,
                extra_pickup_name=delivery.extra_order.get("pickup_name") if delivery.extra_order else None,
            )
        )

    return routes


def _to_pending_out(rt: ShiftRuntime, order_id: str, pending: PendingOrder) -> PendingOrderOut:
    order = pending.order
    evaluation = pending.evaluation

    # should_accept es una recomendacion (en modo manual el conductor sigue
    # decidiendo via /simulation/decide, ver PendingOrdersPanel.tsx): en vez
    # del corte estatico Score > 0, usa el umbral dinamico de
    # decision.policy, que se vuelve mas permisivo si el repartidor va
    # atrasado en su ritmo de pedidos aceptados.
    # `novice_outcome` deberia estar siempre presente (se calcula sincronico
    # junto con la orden); el fallback "busy" solo cubre un estado
    # serializado antes de este campo (Redis entre despliegues).
    novice_outcome = pending.novice_outcome or {"outcome": "busy"}

    return PendingOrderOut(
        order_id=order_id,
        pickup_name=order.get("pickup_name"),
        # Fallback calculado (no solo el `.get`) por si la orden se genero
        # antes de que este campo existiera en un turno ya en curso.
        zone=order.get("zone") or nearest_zone(order["pickup_lat"], order["pickup_lon"]),
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
        at_capacity=_active_order_count(rt) >= settings.max_active_deliveries,
        novice=NoviceOutcomeOut(**novice_outcome),
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
        pending_orders=[_to_pending_out(rt, oid, p) for oid, p in state.pending_orders.items()],
        events=[SimEventOut(**e) for e in state.events],
        # Campos aditivos: el frontend actual los ignora sin romperse
        # (MapView.tsx todavia usa una posicion placeholder).
        sim_time=world_clock.iso_timestamp(),
        time_acceleration=world_clock.acceleration,
        courier_lat=position[0] if position else None,
        courier_lon=position[1] if position else None,
        active_deliveries=_active_order_count(rt),
        deliveries_completed=state.deliveries_completed,
        active_routes=_to_active_routes(rt),
        orders_accepted=state.orders_accepted,
        novice_earnings=round(state.novice_earnings, 2),
        session_id=state.session_id,
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
    autonomous_run_id = uuid.uuid4()
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
        courier_position=start_position,
        novice_position=start_position,
        zone_center=start_position,
        autonomous_run_id=str(autonomous_run_id),
    )
    rt = ShiftRuntime.hydrate(state)

    _log(
        rt,
        "shift_started",
        f"Shift started at {world_clock.now():%H:%M} simulated time — the clock runs "
        f"{world_clock.acceleration:.0f}x faster than real life, agent is scoring orders for the driver.",
    )

    # Un dia simulado completo (1440 min) toma esto en minutos reales; es el
    # equivalente honesto de `real_duration_minutes` ahora que el reloj es
    # global y no por turno.
    real_minutes_per_sim_day = 1440 / world_clock.acceleration

    user_id = uuid.UUID(payload.user_id) if payload.user_id else None
    for rid, agent_type in ((run_id, "inteligente"), (novice_run_id, "novato"), (autonomous_run_id, "autonomo")):
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


@router.get("/route", response_model=RoutePreviewOut)
def get_order_route(run_id: str, order_id: str):
    """La ruta real que se recorreria si se acepta `order_id`, EMPEZANDO DESDE
    DONDE ESTA EL REPARTIDOR AHORA MISMO (`_courier_live_position`) — nunca
    desde `_next_free_position` (donde quedaria libre tras terminar lo que ya
    trae en cola). Usar la posicion futura aqui era el bug: la vista previa
    dibujaba una ruta que arrancaba en un punto en el que el repartidor
    todavia no esta, un salto que no corresponde a nada visible en el mapa.

    La recomendacion de la tarjeta (should_accept en la lista) SI sigue
    evaluandose sobre `_next_free_position` (ver _revalue_pending_orders): esa
    es la pregunta economica correcta ("¿conviene aceptar esto para cuando me
    desocupe?"). Esta vista previa contesta una pregunta distinta ("¿como se
    ve la ruta si fuera ahora mismo?"), por eso recalcula su propia evaluacion
    en vez de reusar `pending.evaluation` — sin esto, los tramos dibujados
    (frescos, desde la posicion real) y los totales mostrados (congelados,
    desde la posicion futura) contarian dos historias distintas.

    Bajo demanda y de solo lectura (no hace `_tick` ni `persist`): el
    frontend la pide cuando el conductor SELECCIONA una oferta, no en cada
    sondeo. Rutear las 5 ofertas pendientes cada 2s costaria cinco A* sobre
    el grafo de la ZMM para pintar, casi siempre, una sola.
    """
    rt = _load_runtime(run_id)
    pending = rt.state.pending_orders.get(order_id)
    if pending is None:
        raise HTTPException(404, "That order is no longer available")

    order = pending.order
    pickup = (order["pickup_lat"], order["pickup_lon"])
    dropoff = (order["dropoff_lat"], order["dropoff_lon"])
    origin = _courier_live_position(rt) or pickup

    to_pickup = try_shortest_route(rt.graph, origin, pickup)
    to_dropoff = try_shortest_route(rt.graph, pickup, dropoff)
    if to_pickup is None or to_dropoff is None:
        # Un cierre de calle dejo la orden sin ruta servible. 409 y no 500:
        # el estado del turno esta bien, es esta oferta la que ya no sirve.
        raise HTTPException(409, "No route available for this order right now")

    route = to_pickup[0] + to_dropoff[0][1:]
    coords, pickup_idx = _split_route_geometry(rt.graph, route, len(to_pickup[0]) - 1)

    to_pickup_minutes = to_pickup[1] / 60
    to_dropoff_minutes = to_dropoff[1] / 60
    # Evaluacion fresca desde la posicion REAL actual — no la congelada de
    # `pending.evaluation` (calculada con la posicion futura libre).
    live_evaluation = OrderEvaluation(
        fare=order["fare"],
        distance_km=(to_pickup[2] + to_dropoff[2]) / 1000,
        time_minutes=to_pickup_minutes + to_dropoff_minutes + settings.service_time_minutes,
        vehicle=VehicleType(rt.state.vehicle),
    )

    return RoutePreviewOut(
        order_id=order_id,
        pickup_name=order.get("pickup_name"),
        coordinates=coords,
        pickup_index=pickup_idx,
        stops=_stops_for(order, origin, to_pickup_minutes, live_evaluation.time_minutes),
        legs=[
            RouteLegOut(
                kind="to_pickup",
                distance_km=to_pickup[2] / 1000,
                minutes=round(to_pickup_minutes, 1),
            ),
            RouteLegOut(
                kind="to_dropoff",
                distance_km=to_dropoff[2] / 1000,
                minutes=round(to_dropoff_minutes, 1),
            ),
        ],
        total_minutes=live_evaluation.time_minutes,
        distance_km=live_evaluation.distance_km,
        fare=order["fare"],
        score=live_evaluation.score,
    )


@router.post("/decide", response_model=SimulationState)
def decide_order(payload: DecisionRequest, db: Session = Depends(get_session)):
    rt = _load_runtime(payload.run_id)
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
    _log(rt, "shift_ended", f"Shift ended — net earnings ${state.net_earnings:.2f} MXN")

    for run_id, total in (
        (state.run_id, state.net_earnings),
        (state.novice_run_id, state.novice_earnings),
        (state.autonomous_run_id, state.autonomous_earnings),
    ):
        # `run_id` puede venir vacio para un turno que arranco ANTES de que
        # este tercer agente existiera y sigue vivo en Redis tras un deploy.
        run = db.get(SimulationRun, uuid.UUID(run_id)) if run_id else None
        if run is not None:
            run.is_finished = True
            run.ended_at = datetime.utcnow()
            run.final_net_earnings = round(total, 2)
    db.commit()

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
