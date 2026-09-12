"""Endpoints de analitica historica para el Perfil del Repartidor (Tiger Data)."""

from fastapi import APIRouter, Depends
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
