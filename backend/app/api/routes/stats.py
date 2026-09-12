"""Endpoints de analitica historica y en vivo para el Perfil del Repartidor
(Tiger Data)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.connection import get_session
from app.db.repository import PERIOD_TO_TIMEDELTA, get_trips_since

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/history/{period}")
def get_history(period: str, session: Session = Depends(get_session)):
    if period not in PERIOD_TO_TIMEDELTA:
        return {"error": f"periodo invalido, opciones: {list(PERIOD_TO_TIMEDELTA)}"}
    trips = get_trips_since(session, period)
    return {"period": period, "count": len(trips)}


@router.get("/scoreboard")
def get_scoreboard(session: Session = Depends(get_session)):
    # TODO: comparar acumulados de agent_type="inteligente" vs "novato" para el turno actual
    return {"inteligente": {}, "novato": {}}


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
