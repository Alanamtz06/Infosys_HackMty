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
    """Pulso en vivo para el dashboard: muestra los acumulados del turno actual/ultimo
    y los viajes mas recientes de toda la plataforma.
    """
    target = get_latest_session_id(session)
    summary = []
    is_active = False
    
    if target:
        is_active = session.execute(
            text("SELECT NOT bool_and(is_finished) FROM simulation_runs WHERE session_id = :sid"),
            {"sid": target}
        ).scalar()
        totals = get_session_scoreboard(session, str(target))
        for agent_type in ["inteligente", "novato"]:
            data = totals.get(agent_type, {})
            trips = data.get("trips", 0)
            accepted = data.get("accepted_trips", 0)
            net = float(data.get("net_earnings", 0.0))
            summary.append({
                "agent_type": agent_type,
                "vehicle": "moto",
                "trips": trips,
                "accepted": accepted,
                "net_score": net,
                "avg_score": net / accepted if accepted > 0 else 0.0
            })

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
        "is_active": bool(is_active),
        "summary": summary,
        "recent_trips": [
            {**dict(row), "created_at": row["created_at"].isoformat()} for row in recent_trips_rows
        ],
    }
