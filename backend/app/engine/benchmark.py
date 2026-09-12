"""Turno headless para medir "cuanto gana el agente vs un baseline simple".

Corre un turno completo sin depender del reloj del mundo: avanza su propio
tiempo simulado en pasos fijos, asi que 8 horas de turno se resuelven en
segundos en vez de en los 16 minutos reales que tomarian en vivo.

Los dos agentes ven EXACTAMENTE el mismo stream de ordenes, el mismo trafico
y arrancan en el mismo punto. La unica diferencia es la decision:

- `inteligente` acepta solo si `decision.policy.should_accept` lo aprueba;
- `novato` acepta todo lo que le quepa.

La pieza que hace que la comparacion signifique algo es la CAPACIDAD: un
repartidor no puede cursar varias entregas a la vez. Mientras esta ocupado,
las ofertas que llegan se le van. Por eso aceptar un pedido malo y largo no
solo deja poco dinero, tambien tapa la agenda para los buenos que vienen
detras — que es el costo real que el reto describe ("take the wrong order and
you burn gas and time crossing the city").

Se persiste igual que un turno normal (dos `simulation_runs` con el mismo
`session_id` + sus `trip_records`), asi que /stats/scoreboard y el dashboard
lo pueden leer despues.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents.delivery_agent import DeliveryAgent
from app.agents.novice_agent import NoviceAgent
from app.agents.order_generator import generate_order, orders_to_generate
from app.config import settings
from app.db.models import Order as OrderModel
from app.db.models import SimulationRun, TripRecord
from app.decision import policy
from app.decision.scoring import OrderEvaluation, VehicleType
from app.engine.graph_loader import apply_traffic, load_graph
from app.engine.pois import load_restaurants
from app.engine.virtual_clock import world_clock

# Cada cuantos minutos simulados se evalua si aparecen ordenes nuevas. 5 min
# es fino para el ritmo de demanda (unas pocas ordenes por hora) y mantiene
# el numero de pasos manejable.
STEP_SIM_MINUTES = 5.0


@dataclass
class _AgentRun:
    """Contabilidad de un agente durante el turno headless."""

    run_id: uuid.UUID
    agent_type: str
    agent: DeliveryAgent | NoviceAgent
    autonomous_policy: bool  # True = decide con policy; False = acepta todo
    busy_until_minute: float = 0.0
    net_earnings: float = 0.0
    accepted: int = 0
    rejected: int = 0
    missed_while_busy: int = 0
    minutes_worked: float = 0.0
    distance_km: float = 0.0
    trips: list[TripRecord] = field(default_factory=list)

    def is_free(self, minute: float) -> bool:
        return minute >= self.busy_until_minute

    def summary(self, hours: float) -> dict:
        return {
            "net_earnings": round(self.net_earnings, 2),
            "accepted": self.accepted,
            "rejected": self.rejected,
            "missed_while_busy": self.missed_while_busy,
            "minutes_worked": round(self.minutes_worked, 1),
            "distance_km": round(self.distance_km, 2),
            "earnings_per_hour": round(self.net_earnings / hours, 2) if hours else 0.0,
        }


def _evaluate(run: _AgentRun, order: dict) -> OrderEvaluation | None:
    return run.agent.evaluate_order(
        (order["pickup_lat"], order["pickup_lon"]),
        (order["dropoff_lat"], order["dropoff_lon"]),
        order["fare"],
    )


def _decide(run: _AgentRun, evaluation: OrderEvaluation, minute: float) -> bool:
    if not run.autonomous_policy:
        return True
    state = policy.PolicyState(orders_accepted=run.accepted, virtual_minutes_elapsed=minute)
    return policy.should_accept(evaluation, state)


def run_benchmark(
    db: Session,
    hours: float = 8.0,
    start_hour: float | None = None,
    vehicle: str = "moto",
    user_id: str | None = None,
) -> dict:
    graph = load_graph()
    restaurants = load_restaurants()

    vehicle_type = VehicleType(vehicle)
    shift_start_hour = world_clock.virtual_hour() if start_hour is None else start_hour
    start_position = (settings.city_center_lat, settings.city_center_lon)

    session_id = uuid.uuid4()
    smart_run_id = uuid.uuid4()
    novice_run_id = uuid.uuid4()

    smart_agent = DeliveryAgent(graph, vehicle=vehicle_type)
    smart_agent.position = start_position
    novice_agent = NoviceAgent(graph, vehicle=vehicle_type)
    novice_agent.position = start_position

    runs = [
        _AgentRun(run_id=smart_run_id, agent_type="inteligente", agent=smart_agent, autonomous_policy=True),
        _AgentRun(run_id=novice_run_id, agent_type="novato", agent=novice_agent, autonomous_policy=False),
    ]

    started_at = datetime.now(timezone.utc)
    parsed_user_id = uuid.UUID(user_id) if user_id else None
    for run in runs:
        db.add(
            SimulationRun(
                id=run.run_id,
                session_id=session_id,
                user_id=parsed_user_id,
                agent_type=run.agent_type,
                vehicle=vehicle,
                start_hour=shift_start_hour,
                shift_duration_minutes=int(hours * 60),
                real_duration_minutes=1440 / world_clock.acceleration,
                started_at=started_at,
                is_finished=False,
            )
        )
    # Los modelos declaran ForeignKey pero no `relationship()`, asi que hay
    # que asegurar que los runs existan antes de las ordenes que los apuntan.
    db.flush()

    orders_offered = 0
    minute = 0.0
    total_minutes = hours * 60

    while minute < total_minutes:
        virtual_hour = (shift_start_hour + minute / 60) % 24
        apply_traffic(graph, virtual_hour)

        for _ in range(orders_to_generate(virtual_hour, STEP_SIM_MINUTES)):
            # Las ofertas se sesgan a la zona del turno (compartida), no a la
            # posicion de cada agente: si el stream siguiera al inteligente,
            # su ventaja seria de cercania y no de criterio.
            order = generate_order(
                graph, restaurants, virtual_hour=virtual_hour, near_point=start_position
            )
            offered_at = started_at + timedelta(minutes=minute)

            # Se evalua primero: si NINGUN agente puede rutearla, la orden no
            # existio (igual que en el turno en vivo).
            evaluations: dict[str, OrderEvaluation] = {}
            for run in runs:
                if not run.is_free(minute):
                    continue
                evaluation = _evaluate(run, order)
                if evaluation is not None:
                    evaluations[run.agent_type] = evaluation

            if not evaluations and all(run.is_free(minute) for run in runs):
                continue

            orders_offered += 1
            db.add(
                OrderModel(
                    id=uuid.UUID(order["id"]),
                    run_id=smart_run_id,
                    pickup_lat=order["pickup_lat"],
                    pickup_lon=order["pickup_lon"],
                    pickup_name=order.get("pickup_name"),
                    dropoff_lat=order["dropoff_lat"],
                    dropoff_lon=order["dropoff_lon"],
                    fare=order["fare"],
                    generated_at=offered_at,
                )
            )
            db.flush()

            for run in runs:
                if not run.is_free(minute):
                    run.missed_while_busy += 1
                    continue

                evaluation = evaluations.get(run.agent_type)
                if evaluation is None:
                    continue

                accept = _decide(run, evaluation, minute)
                if accept:
                    run.accepted += 1
                    run.net_earnings += evaluation.score
                    run.minutes_worked += evaluation.time_minutes
                    run.distance_km += evaluation.distance_km
                    run.busy_until_minute = minute + evaluation.time_minutes
                    run.agent.position = (order["dropoff_lat"], order["dropoff_lon"])
                else:
                    run.rejected += 1

                db.add(
                    TripRecord(
                        run_id=run.run_id,
                        order_id=uuid.UUID(order["id"]),
                        agent_type=run.agent_type,
                        vehicle=vehicle,
                        accepted=accept,
                        fare=evaluation.fare,
                        distance_km=evaluation.distance_km,
                        time_minutes=evaluation.time_minutes,
                        gas_cost=evaluation.distance_km * evaluation.gas_cost_per_km,
                        time_cost=evaluation.time_minutes * settings.time_cost_per_minute,
                        score=evaluation.score,
                        net_earnings_delta=evaluation.score if accept else 0.0,
                        virtual_hour=virtual_hour,
                        created_at=offered_at,
                    )
                )

        minute += STEP_SIM_MINUTES

    ended_at = started_at + timedelta(minutes=total_minutes)
    for run in runs:
        row = db.get(SimulationRun, run.run_id)
        if row is not None:
            row.is_finished = True
            row.ended_at = ended_at
            row.final_net_earnings = round(run.net_earnings, 2)
    db.commit()

    smart, novice = runs[0], runs[1]
    advantage = smart.net_earnings - novice.net_earnings
    advantage_pct = (advantage / abs(novice.net_earnings) * 100) if novice.net_earnings else 0.0

    return {
        "session_id": str(session_id),
        "hours": hours,
        "start_hour": round(shift_start_hour, 2),
        "vehicle": vehicle,
        "orders_offered": orders_offered,
        "inteligente": smart.summary(hours),
        "novato": novice.summary(hours),
        "advantage_mxn": round(advantage, 2),
        "advantage_pct": round(advantage_pct, 1),
    }
