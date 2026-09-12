"""Consultas de analitica historica para el Perfil del Repartidor (filtros: dia/semana/mes/etc)."""

from datetime import datetime, timedelta

from sqlalchemy import select
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
