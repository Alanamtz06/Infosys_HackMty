"""Siembra historial de demo en Tiger Data: turnos pasados (hasta ~13 meses
atras) para que /stats/history/{period} y ProfileStats tengan algo real que
mostrar antes de que exista trafico de produccion.

No es un mock del frontend: escribe filas reales en `trip_records` (con
`created_at` retrofechado) usando la MISMA formula de Score que el turno en
vivo (`decision.scoring.OrderEvaluation`), asi que los numeros que produce
son consistentes con los que el sistema calcularia si esos turnos hubieran
corrido de verdad. `trip_records_daily` (continuous aggregate, ver
schema.sql) los recoge solo: no hace falta refrescarlo a mano porque la vista
tiene `materialized_only = false`.

Idempotente: cada (dia, turno) usa un UUID determinista (`uuid5` sobre la
fecha y el indice de turno, con un RNG de semilla fija), asi que correr el
script dos veces no duplica nada — solo agrega los dias que todavia no
existian. `--wipe` borra exactamente esos ids (los recalcula, no adivina por
heuristica) y nunca toca un turno real, que siempre usa `uuid4()`.

Uso:
    cd backend
    python -m app.db.seed_dummy_history            # ~13 meses hacia atras
    python -m app.db.seed_dummy_history --days 30   # solo el ultimo mes
    python -m app.db.seed_dummy_history --wipe      # borra el historial de demo
"""

from __future__ import annotations

import argparse
import math
import random
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import settings
from app.db.connection import SessionLocal
from app.db.models import Order as OrderModel
from app.db.models import SimulationRun, TripRecord
from app.decision.scoring import OrderEvaluation, VehicleType

DAYS_DEFAULT = 400  # cubre "1_anio" (365d) con margen

# Semilla fija: recorrer el mismo rango de dias produce SIEMPRE la misma
# historia (mismos turnos, mismas ordenes) — necesario para que `--wipe`
# pueda recalcular exactamente que ids sembrar/borrar sin guardar un catalogo
# aparte.
_SEED = 20240101

# Mismas constantes narrativas que agents/order_generator.py, para que un
# pedido sembrado no se distinga de uno que si corrio en un turno real.
PEAK_HOURS = [(13.0, 15.0), (19.0, 22.0)]
BASE_FARE = 40.0
FARE_PER_KM = 8.0
MIN_FARE, MAX_FARE = 32.0, 190.0
SERVICE_TIME_MINUTES = 8.0

_NAMESPACE = uuid.UUID("6f2c9d2e-6c3a-4f0a-9a1e-3c9a6d7b8e10")


def _det_uuid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, ":".join(parts))


def _weekday_factor(day: datetime) -> float:
    """Viernes/sabado son mas fuertes para comida a domicilio; martes flojo."""
    return {0: 0.85, 1: 0.8, 2: 0.95, 3: 1.0, 4: 1.25, 5: 1.3, 6: 1.05}[day.weekday()]


def _growth_factor(days_ago: int, total_days: int) -> float:
    """Tendencia de adopcion: mas turnos entre mas cerca de hoy, no un
    escalon plano — un año identico dia a dia se ve fabricado."""
    progress = 1.0 - (days_ago / max(total_days, 1))
    return 0.45 + 0.75 * progress


@dataclass
class PlannedShift:
    day: datetime
    shift_i: int
    session_id: uuid.UUID
    smart_run_id: uuid.UUID
    novice_run_id: uuid.UUID
    vehicle: str
    start_hour: float


def _plan_shifts(days: int) -> Iterator[PlannedShift]:
    """Recorre el rango de dias con el RNG de semilla fija y produce el plan
    exacto de turnos a sembrar. `seed()` los inserta; `wipe()` solo necesita
    los ids que arroja este generador, sin tocar la base primero — por eso
    ambos comparten esta funcion en vez de cada uno reimplementar el sorteo.
    """
    rng = random.Random(_SEED)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    for days_ago in range(days, 0, -1):
        day = today - timedelta(days=days_ago)
        weight = _weekday_factor(day) * _growth_factor(days_ago, days)
        # Poisson pobre-hombre: cuantos turnos hubo ese dia. Incluye dias en
        # cero (nadie trabajo) para que la serie no sea perfectamente lisa.
        n_shifts = sum(1 for _ in range(4) if rng.random() < weight / 4 * 2.2)

        for shift_i in range(n_shifts):
            vehicle = "moto" if rng.random() < 0.7 else "auto"
            start_hour = rng.uniform(9.0, 21.0)
            yield PlannedShift(
                day=day,
                shift_i=shift_i,
                session_id=_det_uuid("session", day.date().isoformat(), str(shift_i)),
                smart_run_id=_det_uuid("run", "inteligente", day.date().isoformat(), str(shift_i)),
                novice_run_id=_det_uuid("run", "novato", day.date().isoformat(), str(shift_i)),
                vehicle=vehicle,
                start_hour=start_hour,
            )


def _sample_order(rng: random.Random, hour: float) -> tuple[float, float, float]:
    """(distance_km, time_minutes, fare) para un pedido sembrado, con la
    misma logica de tarifa que order_generator.py (base + por km, surge en
    hora pico, piso/techo), para que el Score resultante sea creible."""
    distance_km = rng.uniform(0.8, 11.5)

    is_peak = any(start <= hour <= end for start, end in PEAK_HOURS)
    speed_kph = rng.uniform(14.0, 24.0) if is_peak else rng.uniform(20.0, 38.0)
    time_minutes = (distance_km / speed_kph) * 60 + SERVICE_TIME_MINUTES

    fare = (BASE_FARE + FARE_PER_KM * distance_km) * rng.uniform(0.8, 1.25)
    if is_peak:
        fare *= 1.3
    fare = min(max(fare, MIN_FARE), MAX_FARE)

    return distance_km, time_minutes, fare


def _random_point_near(rng: random.Random, lat: float, lon: float, radius_km: float) -> tuple[float, float]:
    """Punto uniforme dentro de un radio (aprox, valido a escala de ciudad)."""
    angle = rng.uniform(0, 2 * math.pi)
    r = radius_km * (rng.random() ** 0.5)
    dlat = (r / 111.0) * math.cos(angle)
    dlon = (r / (111.0 * math.cos(math.radians(lat)))) * math.sin(angle)
    return lat + dlat, lon + dlon


def _insert_shift(session: Session, rng: random.Random, plan: PlannedShift) -> int:
    """Inserta un turno ya planeado (par inteligente/novato + sus ordenes).
    Devuelve cuantas ordenes se insertaron; 0 si el turno ya existia."""
    if session.get(SimulationRun, plan.smart_run_id) is not None:
        return 0  # ya sembrado en una corrida anterior

    shift_start = plan.day.replace(hour=int(plan.start_hour), minute=int((plan.start_hour % 1) * 60))

    session.add(
        SimulationRun(
            id=plan.smart_run_id,
            session_id=plan.session_id,
            user_id=None,
            agent_type="inteligente",
            vehicle=plan.vehicle,
            start_hour=plan.start_hour,
            shift_duration_minutes=180,
            real_duration_minutes=rng.uniform(90, 180),
            started_at=shift_start,
            ended_at=shift_start + timedelta(hours=3),
            is_finished=True,
        )
    )
    session.add(
        SimulationRun(
            id=plan.novice_run_id,
            session_id=plan.session_id,
            user_id=None,
            agent_type="novato",
            vehicle=plan.vehicle,
            start_hour=plan.start_hour,
            shift_duration_minutes=180,
            real_duration_minutes=rng.uniform(90, 180),
            started_at=shift_start,
            ended_at=shift_start + timedelta(hours=3),
            is_finished=True,
        )
    )

    # Flush explicito: los modelos no declaran `relationship()` entre si
    # (solo columnas `ForeignKey` crudas), asi que SQLAlchemy no arma un
    # grafo de dependencias para ordenar el INSERT automaticamente. Sin este
    # flush, el batch de `orders`/`trip_records` de mas abajo puede intentar
    # insertarse antes que sus propios `simulation_runs` en la misma
    # transaccion -> violacion de la foreign key.
    session.flush()

    n_orders = rng.randint(6, 16)
    inserted = 0
    for order_i in range(n_orders):
        order_hour = (plan.start_hour + (order_i / max(n_orders - 1, 1)) * 3.0) % 24
        order_ts = shift_start + timedelta(minutes=(order_i / max(n_orders, 1)) * 170)

        pickup_lat, pickup_lon = _random_point_near(
            rng, settings.city_center_lat, settings.city_center_lon, settings.city_radius_km
        )
        dropoff_lat, dropoff_lon = _random_point_near(
            rng, settings.city_center_lat, settings.city_center_lon, settings.city_radius_km
        )

        distance_km, time_minutes, fare = _sample_order(rng, order_hour)
        evaluation = OrderEvaluation(
            fare=fare, distance_km=distance_km, time_minutes=time_minutes, vehicle=VehicleType(plan.vehicle)
        )
        gas_cost = distance_km * evaluation.gas_cost_per_km
        time_cost = time_minutes * settings.time_cost_per_minute

        order_id = _det_uuid("order", plan.day.date().isoformat(), str(plan.shift_i), str(order_i))
        session.add(
            OrderModel(
                id=order_id,
                run_id=plan.smart_run_id,
                pickup_lat=pickup_lat,
                pickup_lon=pickup_lon,
                pickup_name=None,
                dropoff_lat=dropoff_lat,
                dropoff_lon=dropoff_lon,
                fare=fare,
                generated_at=order_ts,
            )
        )

        # El inteligente discrimina: mismo umbral que el turno real
        # (should_accept = score > 0). Se registra incluso el rechazo — asi
        # cuenta en "trips" sin sumar a "net_earnings".
        smart_accepts = evaluation.should_accept
        session.add(
            TripRecord(
                created_at=order_ts,
                run_id=plan.smart_run_id,
                order_id=order_id,
                agent_type="inteligente",
                vehicle=plan.vehicle,
                accepted=smart_accepts,
                fare=fare,
                distance_km=distance_km,
                time_minutes=time_minutes,
                gas_cost=gas_cost,
                time_cost=time_cost,
                score=evaluation.score,
                net_earnings_delta=evaluation.score if smart_accepts else 0.0,
                virtual_hour=order_hour,
            )
        )

        # El novato acepta casi todo; ~12% se le va por estar ocupado con la
        # entrega anterior (igual que _record_novice_decision en vivo) y esa
        # orden no deja fila — se le fue, no la rechazo.
        if rng.random() < 0.88:
            session.add(
                TripRecord(
                    created_at=order_ts,
                    run_id=plan.novice_run_id,
                    order_id=order_id,
                    agent_type="novato",
                    vehicle=plan.vehicle,
                    accepted=True,
                    fare=fare,
                    distance_km=distance_km,
                    time_minutes=time_minutes,
                    gas_cost=gas_cost,
                    time_cost=time_cost,
                    score=evaluation.score,
                    net_earnings_delta=evaluation.score,
                    virtual_hour=order_hour,
                )
            )

        inserted += 1

    return inserted


def seed(days: int = DAYS_DEFAULT) -> None:
    rng = random.Random(_SEED)
    session = SessionLocal()
    total_orders = 0
    days_with_shifts: set[str] = set()

    try:
        for plan in _plan_shifts(days):
            inserted = _insert_shift(session, rng, plan)
            if inserted:
                session.commit()
                total_orders += inserted
                days_with_shifts.add(plan.day.date().isoformat())
            else:
                session.rollback()

        print(
            f"Historial de demo listo: {len(days_with_shifts)} dias con turnos "
            f"(de {days} revisados), {total_orders} ordenes sembradas (las ya "
            "presentes de una corrida anterior se saltan)."
        )
    finally:
        session.close()


def wipe(days: int = DAYS_DEFAULT) -> None:
    """Borra el historial de demo, recalculando los mismos ids que `seed()`
    habria producido — nunca por heuristica (p.ej. "user_id nulo"), porque un
    turno real anonimo tambien podria calzar con eso. Un turno real siempre
    usa `uuid4()`, asi que jamas coincide con un id `uuid5(_NAMESPACE, ...)`."""
    plans = list(_plan_shifts(days))
    run_ids = [rid for p in plans for rid in (p.smart_run_id, p.novice_run_id)]
    if not run_ids:
        print("No hay historial de demo que borrar.")
        return

    session = SessionLocal()
    try:
        session.execute(delete(TripRecord).where(TripRecord.run_id.in_(run_ids)))
        session.execute(delete(OrderModel).where(OrderModel.run_id.in_(run_ids)))
        result = session.execute(delete(SimulationRun).where(SimulationRun.id.in_(run_ids)))
        session.commit()
        print(f"Historial de demo borrado: {result.rowcount} turnos.")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=DAYS_DEFAULT, help="Cuantos dias hacia atras sembrar/borrar")
    parser.add_argument("--wipe", action="store_true", help="Borra el historial de demo y no reinserta")
    args = parser.parse_args()

    if args.wipe:
        wipe(days=args.days)
    else:
        seed(days=args.days)
