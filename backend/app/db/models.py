"""Modelos SQLAlchemy para Tiger Data (Postgres + extension TimescaleDB).

Solo `trip_records` es hypertable (serie de tiempo de alta frecuencia: una fila
por decision del agente repartidor). `users`, `simulation_runs`, `orders`,
`decision_audits` y `agent_q_values` son tablas Postgres normales — no tiene
sentido particionarlas por tiempo a este volumen, y `agent_q_values` en
particular se actualiza in-place (UPSERT), un patron que no calza con el
modelo append-mostly de un hypertable.

Cada columna con default lleva tanto `default=` (Python, para que el objeto
tenga el valor apenas se construye, sin round-trip) como `server_default=`
(Postgres, para que un INSERT en SQL puro desde el editor de Tiger Cloud —
sin pasar por este ORM — tambien funcione).

El DDL especifico de Timescale (create_hypertable, continuous aggregate,
politicas de compresion/retencion) vive en `schema.sql`, porque SQLAlchemy no
tiene una forma nativa de expresarlo.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    """Cuenta del repartidor que inicia sesion en la app. `vehicle_type`
    determina el costo de gasolina por km en la formula de Score (moto vs
    auto) para cada turno que corre con esta cuenta.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    vehicle_type: Mapped[str] = mapped_column(String, default="moto", server_default="moto")  # "moto" | "auto"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=text("now()")
    )


class SimulationRun(Base):
    """Un turno de simulacion (lo que hoy vive en el dict en memoria de
    routes/simulation.py). Agrupa las ordenes y decisiones que ocurrieron
    durante ese turno.

    `session_id` empareja dos runs (uno "inteligente", uno "novato") que
    corrieron sobre el mismo flujo de ordenes, para que /stats/scoreboard
    compare manzanas con manzanas en vez de dos turnos aleatorios distintos.

    `vehicle` se copia de `users.vehicle_type` al arrancar el turno (no se
    lee en vivo de `users` en cada query): si el repartidor cambia de
    vehiculo despues, los turnos pasados no deben cambiar de costo con el.
    """

    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)

    agent_type: Mapped[str] = mapped_column(String)  # "inteligente" | "novato"
    vehicle: Mapped[str] = mapped_column(String, default="moto", server_default="moto")  # "moto" | "auto"
    god_mode_preset: Mapped[str | None] = mapped_column(String, nullable=True)

    start_hour: Mapped[float] = mapped_column(Float, default=11.0, server_default=text("11.0"))
    shift_duration_minutes: Mapped[int] = mapped_column(Integer, default=480, server_default=text("480"))
    real_duration_minutes: Mapped[float] = mapped_column(Float)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=text("now()")
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    # Cache del total final para leer el marcador sin agregar trip_records cada vez.
    final_net_earnings: Mapped[float | None] = mapped_column(Float, nullable=True)


class Order(Base):
    """Una orden generada durante un turno (restaurante real de OSM -> casa
    aleatoria). Antes solo existia como dict efimero en order_generator; sin
    esta tabla no hay forma de reconstruir donde ocurrio un viaje pasado
    (el mapa de historial, la auditoria) ni de evitar duplicar lat/lon en
    cada fila de trip_records.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_runs.id"), index=True)

    pickup_lat: Mapped[float] = mapped_column(Float)
    pickup_lon: Mapped[float] = mapped_column(Float)
    pickup_name: Mapped[str | None] = mapped_column(String, nullable=True)  # nombre del restaurante (OSM)
    dropoff_lat: Mapped[float] = mapped_column(Float)
    dropoff_lon: Mapped[float] = mapped_column(Float)

    fare: Mapped[float] = mapped_column(Float)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=text("now()")
    )


class TripRecord(Base):
    """Hypertable: una fila por decision del agente (aceptar/rechazar una
    orden), particionada por `created_at` via create_hypertable en schema.sql.

    `net_earnings_delta` guarda la contribucion DE ESTA fila (= score si se
    acepto, 0 si no) en vez de un total acumulado. Un total acumulado por fila
    rompe cualquier SUM() en un continuous aggregate (sumarias el mismo total
    creciente una y otra vez) — el acumulado que muestra el reloj virtual en
    vivo se lleva en memoria durante el turno y el final se cachea en
    `simulation_runs.final_net_earnings`.

    `gas_cost`/`time_cost`/`score` se calculan en Python al insertar (ver
    decision/scoring.py) con la MISMA formula que calculate_score() en
    Postgres (schema.sql) — la version SQL es la que usan las vistas en vivo
    del dashboard (live_trip_scores, live_dashboard_summary) para recalcular
    sobre la marcha en vez de confiar en lo que se guardo en su momento.
    """

    __tablename__ = "trip_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=text("now()"), primary_key=True
    )

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_runs.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)

    # Denormalizados desde simulation_runs a proposito: las queries de
    # analitica (y el continuous aggregate) filtran/agrupan por estos
    # constantemente y no queremos un JOIN en cada bucket de tiempo.
    agent_type: Mapped[str] = mapped_column(String, index=True)
    vehicle: Mapped[str] = mapped_column(String)

    accepted: Mapped[bool] = mapped_column(Boolean)
    fare: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    time_minutes: Mapped[float] = mapped_column(Float)
    gas_cost: Mapped[float] = mapped_column(Float)
    time_cost: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    net_earnings_delta: Mapped[float] = mapped_column(Float)
    virtual_hour: Mapped[float] = mapped_column(Float)


class DecisionAudit(Base):
    """Explicacion en lenguaje natural (Gemini) cacheada para una orden, para
    no volver a llamar al modelo si el usuario abre el mismo audit dos veces.
    """

    __tablename__ = "decision_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), index=True)
    explanation: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String, default="gemini-flash-latest", server_default="gemini-flash-latest")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=text("now()")
    )


class AgentQValue(Base):
    """Q-table persistida del agente inteligente (ver decision/q_learning.py).
    Se actualiza in-place por eso NO es un hypertable: un UPSERT frecuente
    sobre la misma fila es justo el patron que un hypertable no esta pensado
    para manejar bien.
    """

    __tablename__ = "agent_q_values"

    agent_type: Mapped[str] = mapped_column(String, primary_key=True)
    state: Mapped[str] = mapped_column(String, primary_key=True)  # p.ej. "zone_12|pico_tarde"
    action: Mapped[str] = mapped_column(String, primary_key=True)  # zona vecina
    q_value: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=text("now()")
    )
