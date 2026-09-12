"""Modelos SQLAlchemy para el historial de la simulacion (tabla hypertable en TimescaleDB).

TODO: convertir `trip_records` en hypertable con
  SELECT create_hypertable('trip_records', 'created_at');
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TripRecord(Base):
    __tablename__ = "trip_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, primary_key=True)
    agent_type: Mapped[str] = mapped_column(String)  # "inteligente" | "novato"
    order_id: Mapped[str] = mapped_column(String)
    accepted: Mapped[bool] = mapped_column(Boolean)
    fare: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    time_minutes: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    net_earnings: Mapped[float] = mapped_column(Float)
    virtual_hour: Mapped[float] = mapped_column(Float)
