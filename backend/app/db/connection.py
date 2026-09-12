"""Conexion a Tiger Data (Postgres + extension TimescaleDB).

TODO: requiere una instancia de Tiger Data / TimescaleDB provisionada
(ver DATABASE_URL en .env) antes de poder ejecutar migraciones o queries.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
