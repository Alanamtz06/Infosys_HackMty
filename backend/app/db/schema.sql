-- DDL especifico de Tiger Data / TimescaleDB que SQLAlchemy no puede expresar.
-- Correr una vez sobre una base ya creada con `Base.metadata.create_all` (o via
-- Alembic), en cuanto exista una instancia de Tiger Data provisionada
-- (ver DATABASE_URL en backend/.env).
--
-- Orden: 1) crear las tablas normales con SQLAlchemy, 2) correr este archivo.

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- trip_records es la unica hypertable: una fila por decision del agente,
-- particionada por created_at. migrate_data=>TRUE por si la tabla ya tiene
-- filas de pruebas antes de convertirla.
SELECT create_hypertable(
    'trip_records',
    'created_at',
    migrate_data => TRUE,
    if_not_exists => TRUE
);

-- Cada bucket de tiempo casi siempre se filtra tambien por agent_type
-- (comparar inteligente vs novato) y por run_id (un turno especifico).
CREATE INDEX IF NOT EXISTS ix_trip_records_agent_time
    ON trip_records (agent_type, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_trip_records_run_time
    ON trip_records (run_id, created_at DESC);

-- `users` es tabla nueva y create_all ya la crea, pero `simulation_runs` ya
-- existia antes del login: create_all no hace ALTER TABLE sobre tablas que ya
-- existen, asi que la columna se agrega aqui a mano.
ALTER TABLE simulation_runs
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id);

CREATE INDEX IF NOT EXISTS ix_simulation_runs_user
    ON simulation_runs (user_id);

-- Defaults del lado de Postgres (no solo en el ORM) para que un INSERT en
-- SQL puro desde el editor de Tiger Cloud tambien funcione sin tener que
-- pasar todas las columnas. Van aqui porque ALTER COLUMN SET DEFAULT no lo
-- hace create_all sobre columnas de tablas que ya existian.
ALTER TABLE users
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN vehicle_type SET DEFAULT 'moto',
    ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE simulation_runs
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN vehicle SET DEFAULT 'moto',
    ALTER COLUMN start_hour SET DEFAULT 11.0,
    ALTER COLUMN shift_duration_minutes SET DEFAULT 480,
    ALTER COLUMN started_at SET DEFAULT now(),
    ALTER COLUMN is_finished SET DEFAULT false;

ALTER TABLE orders
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN generated_at SET DEFAULT now();

ALTER TABLE trip_records
    ALTER COLUMN created_at SET DEFAULT now();

ALTER TABLE decision_audits
    ALTER COLUMN model SET DEFAULT 'gemini-flash-latest',
    ALTER COLUMN generated_at SET DEFAULT now();

ALTER TABLE agent_q_values
    ALTER COLUMN q_value SET DEFAULT 0.0,
    ALTER COLUMN updated_at SET DEFAULT now();

-- Continuous aggregate: pre-calcula los totales por dia/agente/vehiculo que
-- alimenta GET /stats/history/{period} y el EarningsChart del frontend
-- (date, netEarnings, gasSaved, timeSaved). Se refresca solo via la policy
-- de abajo en vez de recalcularse en cada request.
CREATE MATERIALIZED VIEW IF NOT EXISTS trip_records_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', created_at) AS day,
    run_id,
    agent_type,
    vehicle,
    count(*) AS trips,
    count(*) FILTER (WHERE accepted) AS accepted_trips,
    sum(fare) FILTER (WHERE accepted) AS gross_fare,
    sum(gas_cost) FILTER (WHERE accepted) AS gas_cost,
    sum(time_cost) FILTER (WHERE accepted) AS time_cost,
    sum(time_minutes) FILTER (WHERE accepted) AS time_minutes,
    sum(net_earnings_delta) AS net_earnings,
    avg(score) FILTER (WHERE accepted) AS avg_score
FROM trip_records
GROUP BY day, run_id, agent_type, vehicle
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'trip_records_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- Agregacion en tiempo real: la policy de arriba solo materializa hasta hace
-- una hora, asi que sin esto el filtro "Day" del perfil saldria vacio aunque
-- el turno este corriendo ahora mismo. Con materialized_only = false la vista
-- une lo ya materializado con lo que todavia esta crudo en trip_records.
ALTER MATERIALIZED VIEW trip_records_daily SET (timescaledb.materialized_only = false);

-- "Gasolina ahorrada" / "Tiempo ahorrado" del Perfil del Repartidor no son
-- columnas propias: se calculan comparando, para runs con el mismo
-- session_id, gas_cost/time_cost de agent_type='novato' contra
-- agent_type='inteligente' sobre trip_records_daily. Ejemplo:
--
-- SELECT
--     i.day,
--     n.gas_cost - i.gas_cost AS gas_ahorrado,
--     n.time_minutes - i.time_minutes AS tiempo_ahorrado_min,
--     i.net_earnings
-- FROM trip_records_daily i
-- JOIN simulation_runs ri ON ri.id = i.run_id
-- JOIN simulation_runs rn ON rn.session_id = ri.session_id AND rn.agent_type = 'novato'
-- JOIN trip_records_daily n ON n.run_id = rn.id AND n.day = i.day
-- WHERE i.agent_type = 'inteligente';

-- ============================================================================
-- Formula de Score, vivida en la base de datos (no solo en Python).
-- Score = Tarifa - (Distancia * Costo_Gasolina) - (Tiempo * Costo_Tiempo)
-- Gasolina: $0.80 MXN/km (moto) o $2.00 MXN/km (auto). Tiempo: $1.50 MXN/min.
-- Estas funciones son la unica fuente de verdad de las tarifas: si cambian,
-- cambian aqui y todas las vistas/dashboards de abajo las recogen solas.
-- ============================================================================

CREATE OR REPLACE FUNCTION gas_cost_per_km(p_vehicle TEXT)
RETURNS DOUBLE PRECISION
LANGUAGE SQL IMMUTABLE AS $$
    SELECT CASE WHEN p_vehicle = 'moto' THEN 0.80 ELSE 2.00 END;
$$;

CREATE OR REPLACE FUNCTION calculate_gas_cost(p_distance_km DOUBLE PRECISION, p_vehicle TEXT)
RETURNS DOUBLE PRECISION
LANGUAGE SQL IMMUTABLE AS $$
    SELECT p_distance_km * gas_cost_per_km(p_vehicle);
$$;

CREATE OR REPLACE FUNCTION calculate_time_cost(p_time_minutes DOUBLE PRECISION)
RETURNS DOUBLE PRECISION
LANGUAGE SQL IMMUTABLE AS $$
    SELECT p_time_minutes * 1.50;
$$;

CREATE OR REPLACE FUNCTION calculate_score(
    p_fare DOUBLE PRECISION,
    p_distance_km DOUBLE PRECISION,
    p_time_minutes DOUBLE PRECISION,
    p_vehicle TEXT
) RETURNS DOUBLE PRECISION
LANGUAGE SQL IMMUTABLE AS $$
    SELECT p_fare
        - calculate_gas_cost(p_distance_km, p_vehicle)
        - calculate_time_cost(p_time_minutes);
$$;

-- ============================================================================
-- Vistas en vivo para el dashboard: son VIEW normales (no materializadas), o
-- sea que cada request las recalcula contra los datos mas recientes de
-- trip_records via calculate_score() de arriba. "En vivo" de verdad, no una
-- foto cacheada — el continuous aggregate de arriba (trip_records_daily)
-- sigue siendo la fuente para rangos largos (semana/mes/año), estas vistas
-- son para "ahora mismo".
-- ============================================================================

-- Cada viaje individual con su Score recalculado en el momento + a quien
-- pertenece el turno (para el dashboard "ultimos viajes").
CREATE OR REPLACE VIEW live_trip_scores AS
SELECT
    tr.id,
    tr.created_at,
    tr.run_id,
    tr.order_id,
    tr.agent_type,
    tr.vehicle,
    tr.accepted,
    tr.fare,
    tr.distance_km,
    tr.time_minutes,
    calculate_gas_cost(tr.distance_km, tr.vehicle) AS gas_cost_live,
    calculate_time_cost(tr.time_minutes) AS time_cost_live,
    calculate_score(tr.fare, tr.distance_km, tr.time_minutes, tr.vehicle) AS score_live,
    u.username
FROM trip_records tr
JOIN simulation_runs sr ON sr.id = tr.run_id
LEFT JOIN users u ON u.id = sr.user_id
ORDER BY tr.created_at DESC;

-- Pulso de los ultimos 5 minutos por agente/vehiculo: lo que alimenta las
-- tarjetas "en vivo" del dashboard (viajes, aceptados, score neto/promedio).
CREATE OR REPLACE VIEW live_dashboard_summary AS
SELECT
    agent_type,
    vehicle,
    count(*) AS trips_last_5min,
    count(*) FILTER (WHERE accepted) AS accepted_last_5min,
    COALESCE(sum(calculate_score(fare, distance_km, time_minutes, vehicle)) FILTER (WHERE accepted), 0) AS net_score_last_5min,
    COALESCE(avg(calculate_score(fare, distance_km, time_minutes, vehicle)) FILTER (WHERE accepted), 0) AS avg_score_last_5min
FROM trip_records
WHERE created_at > now() - INTERVAL '5 minutes'
GROUP BY agent_type, vehicle;

-- Acumulado en vivo del turno activo (mientras no termina y no hay todavia
-- un final_net_earnings cacheado en simulation_runs).
CREATE OR REPLACE VIEW live_run_earnings AS
SELECT
    run_id,
    sum(net_earnings_delta) AS net_earnings_so_far,
    count(*) AS trips_so_far,
    count(*) FILTER (WHERE accepted) AS accepted_so_far,
    max(created_at) AS last_trip_at
FROM trip_records
GROUP BY run_id;

-- Datos de mas de 6 meses (el periodo mas largo que ofrece el filtro del
-- frontend) se comprimen para no crecer sin limite. Opcional para la demo,
-- mencionado para cuando esto corra mas de un dia.
ALTER TABLE trip_records SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'agent_type, run_id',
    timescaledb.compress_orderby = 'created_at DESC'
);

SELECT add_compression_policy('trip_records', INTERVAL '30 days', if_not_exists => TRUE);
