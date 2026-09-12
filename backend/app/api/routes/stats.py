"""Endpoints de analitica historica y en vivo para el Perfil del Repartidor
y el Dashboard (Tiger Data)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import get_session
from app.db.repository import (
    PERIOD_TO_TIMEDELTA,
    get_daily_history,
    get_latest_session_id,
    get_session_scoreboard,
)

router = APIRouter(prefix="/stats", tags=["stats"])

_EMPTY_AGENT_TOTALS = {
    "net_earnings": 0.0,
    "trips": 0,
    "accepted_trips": 0,
    "gas_cost": 0.0,
    "time_minutes": 0.0,
    "avg_score": 0.0,
}


@router.get("/history/{period}")
def get_history(period: str, session: Session = Depends(get_session)):
    """Serie diaria del periodo pedido, leida del continuous aggregate
    `trip_records_daily` de Tiger Data.

    `points` viene con las llaves que consume EarningsChart
    (date/netEarnings/gasSaved/timeSaved), asi que ProfileStats puede
    reemplazar su SAMPLE_DATA por esto directo.
    """
    if period not in PERIOD_TO_TIMEDELTA:
        raise HTTPException(400, f"Invalid period, options: {list(PERIOD_TO_TIMEDELTA)}")

    points = get_daily_history(session, period)
    totals = {
        "netEarnings": round(sum(p["netEarnings"] for p in points), 2),
        "gasSaved": round(sum(p["gasSaved"] for p in points), 2),
        "timeSaved": round(sum(p["timeSaved"] for p in points), 1),
        "trips": sum(p["trips"] for p in points),
        "acceptedTrips": sum(p["acceptedTrips"] for p in points),
    }
    return {"period": period, "count": len(points), "points": points, "totals": totals}


@router.get("/scoreboard")
def get_scoreboard(session_id: str | None = None, session: Session = Depends(get_session)):
    """Marcador Global: agente inteligente vs novato sobre el MISMO stream de
    ordenes (los dos turnos comparten `session_id`; los crea /simulation/start).

    Sin `session_id` usa el turno mas reciente. `savings` es lo que el agente
    inteligente le saco de ventaja al novato.
    """
    target = session_id or get_latest_session_id(session)
    if target is None:
        return {"session_id": None, "inteligente": _EMPTY_AGENT_TOTALS, "novato": _EMPTY_AGENT_TOTALS, "savings": {}}

    totals = get_session_scoreboard(session, str(target))
    smart = {**_EMPTY_AGENT_TOTALS, **totals.get("inteligente", {})}
    novice = {**_EMPTY_AGENT_TOTALS, **totals.get("novato", {})}

    return {
        "session_id": str(target),
        "inteligente": smart,
        "novato": novice,
        "savings": {
            "net_earnings": round(float(smart["net_earnings"]) - float(novice["net_earnings"]), 2),
            "gas_cost": round(float(novice["gas_cost"]) - float(smart["gas_cost"]), 2),
            "time_minutes": round(float(novice["time_minutes"]) - float(smart["time_minutes"]), 1),
        },
    }


@router.get("/live")
def get_live_dashboard(session: Session = Depends(get_session)):
    """Pulso en vivo para el dashboard: recalculado en cada request contra
    live_dashboard_summary / live_trip_scores (ver app/db/schema.sql) — no es
    una foto cacheada, cada llamada corre calculate_score() de nuevo sobre lo
    ultimo que haya en trip_records.
    """
    summary_rows = session.execute(
        text("""
            SELECT agent_type, vehicle, trips_last_5min, accepted_last_5min,
                   net_score_last_5min, avg_score_last_5min
            FROM live_dashboard_summary
            ORDER BY agent_type, vehicle
        """)
    ).mappings().all()

    recent_trips_rows = session.execute(
        text("""
            SELECT id, created_at, run_id, order_id, agent_type, vehicle, accepted,
                   fare, distance_km, time_minutes, gas_cost_live, time_cost_live,
                   score_live, username
            FROM live_trip_scores
            ORDER BY created_at DESC
            LIMIT 25
        """)
    ).mappings().all()

    return {
        "summary": [dict(row) for row in summary_rows],
        "recent_trips": [
            {**dict(row), "created_at": row["created_at"].isoformat()} for row in recent_trips_rows
        ],
    }
