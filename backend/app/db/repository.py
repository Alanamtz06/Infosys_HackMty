"""Consultas de analitica para el Perfil del Repartidor y el Marcador Global.

El trabajo pesado lo hace Postgres/Tiger Data:
  - rangos largos (semana ... 1 año) leen `trip_records_daily`, el continuous
    aggregate que ya agrupa por dia via `time_bucket` (ver db/schema.sql);
  - el "ahora mismo" del dashboard usa las vistas en vivo
    (`live_dashboard_summary`, `live_trip_scores`), que recalculan
    `calculate_score()` en cada request.
Python solo pivotea el resultado (dos agentes x N dias es trivial) para
entregarlo en la forma que espera el frontend.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import TripRecord

PERIOD_TO_TIMEDELTA = {
    "dia": timedelta(days=1),
    "semana": timedelta(weeks=1),
    "1_mes": timedelta(days=30),
    "3_meses": timedelta(days=90),
    "6_meses": timedelta(days=180),
    "1_anio": timedelta(days=365),
}


def get_trips_since(session: Session, period: str) -> list[TripRecord]:
    delta = PERIOD_TO_TIMEDELTA[period]
    since = datetime.utcnow() - delta
    stmt = select(TripRecord).where(TripRecord.created_at >= since).order_by(TripRecord.created_at)
    return list(session.scalars(stmt))


_DAILY_BY_AGENT_SQL = text("""
    SELECT
        (created_at AT TIME ZONE 'UTC')::date AS bucket_day,
        agent_type,
        COALESCE(sum(net_earnings_delta), 0)   AS net_earnings,
        COALESCE(sum(gas_cost), 0)       AS gas_cost,
        COALESCE(sum(time_cost), 0)      AS time_cost,
        COALESCE(sum(time_minutes), 0)   AS time_minutes,
        count(*)                         AS trips,
        count(*) FILTER (WHERE accepted) AS accepted_trips
    FROM trip_records
    WHERE created_at >= :since
    GROUP BY bucket_day, agent_type
    ORDER BY bucket_day
""")


_HOURLY_BY_AGENT_SQL = text("""
    SELECT
        date_trunc('hour', created_at AT TIME ZONE 'UTC') AS bucket_day,
        agent_type,
        COALESCE(sum(net_earnings_delta), 0)   AS net_earnings,
        COALESCE(sum(gas_cost), 0)       AS gas_cost,
        COALESCE(sum(time_cost), 0)      AS time_cost,
        COALESCE(sum(time_minutes), 0)   AS time_minutes,
        COALESCE(count(*), 0)          AS trips,
        COALESCE(count(*) FILTER (WHERE accepted), 0) AS accepted_trips
    FROM trip_records
    WHERE created_at >= :since
    GROUP BY bucket_day, agent_type
    ORDER BY bucket_day
""")


def get_daily_history(session: Session, period: str, user_id: str | None = None) -> list[dict]:
    """Serie por dia lista para el EarningsChart del frontend.

    Cada punto trae exactamente las llaves de `EarningsPoint`
    (frontend/src/components/profile/EarningsChart.tsx):
      date, netEarnings, gasSaved, timeSaved

    `gasSaved`/`timeSaved` no son columnas: son lo que el agente inteligente
    se ahorro frente al novato ESE dia (novato - inteligente), como documenta
    db/schema.sql. `gasSaved` esta en MXN de gasolina no gastada (el frontend
    hoy lo rotula en litros — ver nota en el README del backend).
    """
    since = datetime.utcnow() - PERIOD_TO_TIMEDELTA[period]
    query = _HOURLY_BY_AGENT_SQL if period == "dia" else _DAILY_BY_AGENT_SQL
    rows = session.execute(query, {"since": since}).mappings().all()

    by_day = {}
    for row in rows:
        by_day.setdefault(row["bucket_day"], {})[row["agent_type"]] = dict(row)

    points: list[dict] = []
    for day in sorted(by_day):
        smart = by_day[day].get("inteligente", {})
        novice = by_day[day].get("novato", {})
        gas_saved = float(novice.get("gas_cost", 0) or 0) - float(smart.get("gas_cost", 0) or 0)
        time_saved = float(novice.get("time_minutes", 0) or 0) - float(smart.get("time_minutes", 0) or 0)
        points.append(
            {
                "date": day.isoformat(),
                "netEarnings": round(float(smart.get("net_earnings", 0) or 0), 2),
                "gasSaved": round(max(gas_saved, 0.0), 2),
                "timeSaved": round(max(time_saved, 0.0), 1),
                "trips": int(smart.get("trips", 0) or 0),
                "acceptedTrips": int(smart.get("accepted_trips", 0) or 0),
                "noviceNetEarnings": round(float(novice.get("net_earnings", 0) or 0), 2),
            }
        )
    return points


_SESSION_TOTALS_SQL = text("""
    SELECT
        sr.agent_type,
        COALESCE(sum(tr.net_earnings_delta), 0)                         AS net_earnings,
        count(*)                                                        AS trips,
        count(*) FILTER (WHERE tr.accepted)                             AS accepted_trips,
        COALESCE(sum(tr.gas_cost) FILTER (WHERE tr.accepted), 0)        AS gas_cost,
        COALESCE(sum(tr.time_minutes) FILTER (WHERE tr.accepted), 0)    AS time_minutes,
        COALESCE(sum(tr.distance_km) FILTER (WHERE tr.accepted), 0)     AS distance_km,
        COALESCE(avg(tr.score) FILTER (WHERE tr.accepted), 0)           AS avg_score,
        COALESCE(avg(tr.score) FILTER (WHERE NOT tr.accepted), 0)       AS avg_rejected_score
    FROM trip_records tr
    JOIN simulation_runs sr ON sr.id = tr.run_id
    WHERE sr.session_id = :session_id
    GROUP BY sr.agent_type
""")


def get_latest_session_id(session: Session) -> str | None:
    """El `session_id` mas reciente que tenga trip_records para los TRES
    agentes (inteligente, novato, autonomo). Si el turno mas nuevo todavia no
    tiene datos para los tres, cae al anterior — evita que el dashboard
    muestre ceros mientras el backend procesa la primera oferta de un turno
    recien arrancado (o mientras el humano no ha decidido nada todavia: novato
    y autonomo escriben su TripRecord al generarse la orden, inteligente solo
    al decidir)."""
    return session.execute(
        text("""
            SELECT sr.session_id
            FROM simulation_runs sr
            JOIN trip_records tr ON tr.run_id = sr.id
            WHERE sr.session_id IS NOT NULL
            GROUP BY sr.session_id
            HAVING count(DISTINCT sr.agent_type) = 3
            ORDER BY max(sr.started_at) DESC
            LIMIT 1
        """)
    ).scalar()


def get_session_scoreboard(session: Session, session_id: str) -> dict[str, dict]:
    """Totales por agente para un `session_id` (inteligente vs novato)."""
    rows = session.execute(_SESSION_TOTALS_SQL, {"session_id": session_id}).mappings().all()
    return {row["agent_type"]: {k: v for k, v in dict(row).items() if k != "agent_type"} for row in rows}
