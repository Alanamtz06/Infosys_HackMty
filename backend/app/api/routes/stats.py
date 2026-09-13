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
    "distance_km": 0.0,
    "avg_score": 0.0,
    "avg_rejected_score": 0.0,
    "acceptance_rate": 0.0,
    "earnings_per_hour": 0.0,
    "earnings_per_km": 0.0,
}


def _with_derived_rates(totals: dict) -> dict:
    """Agrega las tasas que hacen la comparacion accionable en vez de solo
    acumulada: cuanto deja por HORA trabajada (la misma metrica que
    `policy.should_accept` compara contra `RESERVATION_RATE_MXN_PER_HOUR`,
    nunca antes expuesta al dashboard) y por KM recorrido, mas que fraccion de
    las ofertas se acepta. Todo derivado de columnas que `trip_records` ya
    tenia — ningun dato nuevo que trackear.
    """
    trips = int(totals.get("trips", 0) or 0)
    accepted = int(totals.get("accepted_trips", 0) or 0)
    net = float(totals.get("net_earnings", 0.0) or 0.0)
    time_minutes = float(totals.get("time_minutes", 0.0) or 0.0)
    distance_km = float(totals.get("distance_km", 0.0) or 0.0)

    return {
        **totals,
        "acceptance_rate": round(accepted / trips, 3) if trips > 0 else 0.0,
        "earnings_per_hour": round(net / (time_minutes / 60), 2) if time_minutes > 0 else 0.0,
        "earnings_per_km": round(net / distance_km, 2) if distance_km > 0 else 0.0,
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
    smart = _with_derived_rates({**_EMPTY_AGENT_TOTALS, **totals.get("inteligente", {})})
    novice = _with_derived_rates({**_EMPTY_AGENT_TOTALS, **totals.get("novato", {})})

    return {
        "session_id": str(target),
        "inteligente": smart,
        "novato": novice,
        "savings": {
            "net_earnings": round(float(smart["net_earnings"]) - float(novice["net_earnings"]), 2),
            "gas_cost": round(float(novice["gas_cost"]) - float(smart["gas_cost"]), 2),
            "time_minutes": round(float(novice["time_minutes"]) - float(smart["time_minutes"]), 1),
            "earnings_per_hour": round(float(smart["earnings_per_hour"]) - float(novice["earnings_per_hour"]), 2),
        },
    }


@router.get("/live")
def get_live_dashboard(session: Session = Depends(get_session)):
    """Pulso en vivo para el dashboard: muestra los acumulados del turno actual/ultimo
    por agente.
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
        for agent_type in ["inteligente", "novato", "autonomo"]:
            data = _with_derived_rates({**_EMPTY_AGENT_TOTALS, **totals.get(agent_type, {})})
            trips = data.get("trips", 0)
            accepted = data.get("accepted_trips", 0)
            net = float(data.get("net_earnings", 0.0))
            summary.append({
                "agent_type": agent_type,
                "vehicle": "moto",
                "trips": trips,
                "accepted": accepted,
                "net_score": net,
                "avg_score": net / accepted if accepted > 0 else 0.0,
                "acceptance_rate": data["acceptance_rate"],
                "earnings_per_hour": data["earnings_per_hour"],
            })

    return {
        "is_active": bool(is_active),
        "summary": summary,
    }
