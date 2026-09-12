"""Crea todas las tablas de Tiger Data para este proyecto.

Dos pasos, en orden:
  1. Las tablas normales (simulation_runs, orders, trip_records,
     decision_audits, agent_q_values) via SQLAlchemy (Base.metadata.create_all).
  2. El DDL especifico de Timescale que SQLAlchemy no puede expresar
     (create_hypertable, continuous aggregate, compresion) desde schema.sql.

Requiere DATABASE_URL apuntando a una instancia de Tiger Data ya provisionada
(ver backend/.env, basado en .env.example).

Uso:
    cd backend
    python -m app.db.init_db
"""

from pathlib import Path

import psycopg2

from app.config import settings
from app.db.connection import engine
from app.db.models import Base

SCHEMA_SQL_PATH = Path(__file__).parent / "schema.sql"


def create_tables() -> None:
    Base.metadata.create_all(engine)
    print(f"Tablas creadas via SQLAlchemy: {list(Base.metadata.tables)}")


def apply_timescale_schema() -> None:
    sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    conn = psycopg2.connect(settings.database_url)
    # autocommit: create_hypertable y las policies de Timescale asumen que no
    # estan corriendo dentro de una transaccion explicita que las envuelva.
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()
    print("schema.sql aplicado: hypertable, continuous aggregate y compresion listos.")


if __name__ == "__main__":
    create_tables()
    apply_timescale_schema()
