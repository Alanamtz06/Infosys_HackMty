"""Siembra historial de demo en Tiger Data para que los filtros del Perfil
(1 mes / 3 meses / 6 meses / 1 año) y el continuous aggregate tengan datos.

Que genera, por cada dia del rango: un turno "inteligente" y su espejo
"novato" con el MISMO stream de ordenes (mismo `session_id`), donde la unica
diferencia es la decision — el novato acepta todo, el inteligente solo lo que
deja Score positivo. De ahi salen el "ahorro de gasolina/tiempo" del perfil y
la comparacion del Marcador Global.

Los Score se calculan con la misma formula que `decision/scoring.py` y que
`calculate_score()` en Postgres, para que las vistas en vivo recalculen
exactamente lo mismo que quedo guardado.

Todo lo sembrado pertenece a un usuario marcador (`demo_seed`), asi que
`--reset` puede borrarlo sin tocar los datos reales de nadie.

Uso:
    cd backend
    python -m app.db.seed_dummy              # 365 dias
    python -m app.db.seed_dummy --days 180
    python -m app.db.seed_dummy --reset      # borra lo sembrado y vuelve a sembrar
"""

import argparse
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text

from app.config import settings
from app.db.connection import SessionLocal, engine
from app.db.models import Order, SimulationRun, TripRecord, User

SEED_USERNAME = "demo_seed"
# Hash bcrypt de una password inutilizable: esta cuenta es un marcador de
# datos sembrados, no una cuenta con la que alguien deba poder entrar.
SEED_PASSWORD_HASH = "$2b$12$seedseedseedseedseedseedseedseedseedseedseedseedseedseedse"

ORDERS_PER_DAY = (8, 22)
FARE_RANGE = (40.0, 140.0)
DISTANCE_KM_RANGE = (1.2, 14.0)
# Minutos por km, incluyendo el tramo de ir a recoger: mas alto en hora pico.
MINUTES_PER_KM = (2.4, 4.8)
PEAK_HOURS = [(13.0, 15.0), (19.0, 22.0)]


def _gas_cost(distance_km: float, vehicle: str) -> float:
    per_km = settings.gas_cost_per_km_moto if vehicle == "moto" else settings.gas_cost_per_km_auto
    return distance_km * per_km


def _score(fare: float, distance_km: float, time_minutes: float, vehicle: str) -> float:
    return fare - _gas_cost(distance_km, vehicle) - time_minutes * settings.time_cost_per_minute


def _random_order_shape(virtual_hour: float) -> tuple[float, float, float]:
    """(fare, distance_km, time_minutes) de una orden plausible."""
    fare = random.uniform(*FARE_RANGE)
    distance_km = random.uniform(*DISTANCE_KM_RANGE)
    peak = any(start <= virtual_hour <= end for start, end in PEAK_HOURS)
    minutes_per_km = random.uniform(*MINUTES_PER_KM) * (1.35 if peak else 1.0)
    return fare, distance_km, distance_km * minutes_per_km


def _get_or_create_seed_user(db) -> User:
    user = db.scalars(select(User).where(User.username == SEED_USERNAME)).first()
    if user is not None:
        return user
    user = User(username=SEED_USERNAME, password_hash=SEED_PASSWORD_HASH, vehicle_type="moto")
    db.add(user)
    db.commit()
    return user


def reset_seed_data(db) -> int:
    """Borra SOLO lo que pertenece al usuario marcador."""
    user = db.scalars(select(User).where(User.username == SEED_USERNAME)).first()
    if user is None:
        return 0

    run_ids = list(db.scalars(select(SimulationRun.id).where(SimulationRun.user_id == user.id)))
    if not run_ids:
        return 0

    db.execute(delete(TripRecord).where(TripRecord.run_id.in_(run_ids)))
    db.execute(delete(Order).where(Order.run_id.in_(run_ids)))
    db.execute(delete(SimulationRun).where(SimulationRun.id.in_(run_ids)))
    db.commit()
    return len(run_ids)


def seed(days: int) -> dict:
    db = SessionLocal()
    try:
        user = _get_or_create_seed_user(db)
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        runs = 0
        trips = 0
        orders = 0

        for day_offset in range(days, 0, -1):
            day_start = today - timedelta(days=day_offset)
            vehicle = "moto" if day_offset % 4 else "auto"
            session_id = uuid.uuid4()

            smart_run_id = uuid.uuid4()
            novice_run_id = uuid.uuid4()
            run_rows = {}
            for run_id, agent_type in ((smart_run_id, "inteligente"), (novice_run_id, "novato")):
                run_rows[agent_type] = SimulationRun(
                    id=run_id,
                    session_id=session_id,
                    user_id=user.id,
                    agent_type=agent_type,
                    vehicle=vehicle,
                    start_hour=11.0,
                    shift_duration_minutes=1440,
                    real_duration_minutes=1440 / settings.time_acceleration,
                    started_at=day_start,
                    ended_at=day_start + timedelta(hours=8),
                    is_finished=True,
                )
                db.add(run_rows[agent_type])
                runs += 1

            # Los modelos declaran ForeignKey pero no `relationship()`, asi que
            # el unit of work de SQLAlchemy no garantiza insertar los runs antes
            # que las ordenes/viajes que los referencian. Un flush explicito si.
            db.flush()

            smart_total = 0.0
            novice_total = 0.0

            for _ in range(random.randint(*ORDERS_PER_DAY)):
                minute_of_shift = random.uniform(0, 8 * 60)
                created_at = day_start + timedelta(hours=10) + timedelta(minutes=minute_of_shift)
                virtual_hour = (created_at.hour + created_at.minute / 60) % 24

                fare, distance_km, time_minutes = _random_order_shape(virtual_hour)
                order_id = uuid.uuid4()
                db.add(
                    Order(
                        id=order_id,
                        run_id=smart_run_id,
                        pickup_lat=settings.city_center_lat + random.uniform(-0.05, 0.05),
                        pickup_lon=settings.city_center_lon + random.uniform(-0.05, 0.05),
                        pickup_name="Seeded restaurant",
                        dropoff_lat=settings.city_center_lat + random.uniform(-0.06, 0.06),
                        dropoff_lon=settings.city_center_lon + random.uniform(-0.06, 0.06),
                        fare=round(fare, 2),
                        generated_at=created_at,
                    )
                )
                orders += 1

                score = _score(fare, distance_km, time_minutes, vehicle)

                # El inteligente solo toma lo que deja dinero; el novato todo.
                # Cuando el inteligente rechaza, no gasta gasolina ni tiempo:
                # por eso sus sumas de gas_cost/time_minutes salen mas bajas y
                # la resta novato - inteligente es el "ahorro" del perfil.
                smart_accepted = score > 0
                for run_id, agent_type, accepted in (
                    (smart_run_id, "inteligente", smart_accepted),
                    (novice_run_id, "novato", True),
                ):
                    db.add(
                        TripRecord(
                            run_id=run_id,
                            order_id=order_id,
                            agent_type=agent_type,
                            vehicle=vehicle,
                            accepted=accepted,
                            fare=round(fare, 2),
                            distance_km=round(distance_km, 3),
                            time_minutes=round(time_minutes, 2),
                            gas_cost=round(_gas_cost(distance_km, vehicle), 2),
                            time_cost=round(time_minutes * settings.time_cost_per_minute, 2),
                            score=round(score, 2),
                            net_earnings_delta=round(score, 2) if accepted else 0.0,
                            virtual_hour=round(virtual_hour, 2),
                            created_at=created_at,
                        )
                    )
                    trips += 1

                if smart_accepted:
                    smart_total += score
                novice_total += score

            run_rows["inteligente"].final_net_earnings = round(smart_total, 2)
            run_rows["novato"].final_net_earnings = round(novice_total, 2)
            db.commit()

        return {"runs": runs, "orders": orders, "trip_records": trips, "days": days}
    finally:
        db.close()


def refresh_continuous_aggregate() -> None:
    """El continuous aggregate se creo WITH NO DATA y su policy solo cubre los
    ultimos dias: hay que materializar a mano el historial recien sembrado o
    /stats/history no veria nada."""
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))  # refresh_continuous_aggregate no corre dentro de una transaccion
        conn.exec_driver_sql("CALL refresh_continuous_aggregate('trip_records_daily', NULL, NULL)")
    print("trip_records_daily refrescado.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Siembra historial de demo en Tiger Data")
    parser.add_argument("--days", type=int, default=365, help="cuantos dias hacia atras sembrar (default 365)")
    parser.add_argument("--reset", action="store_true", help="borrar lo sembrado antes (solo del usuario demo_seed)")
    args = parser.parse_args()

    if args.reset:
        db = SessionLocal()
        try:
            removed = reset_seed_data(db)
            print(f"Turnos sembrados borrados: {removed}")
        finally:
            db.close()

    stats = seed(args.days)
    print(f"Sembrado: {stats}")
    refresh_continuous_aggregate()
