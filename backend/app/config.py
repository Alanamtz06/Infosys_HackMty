from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost:5432/lynx"
    gemini_api_key: str = ""

    city_center_lat: float = 25.6714
    city_center_lon: float = -100.3095
    city_radius_km: float = 8.0

    shift_duration_minutes: int = 180

    # Reloj del mundo (engine/virtual_clock.py::WorldClock): cuantas veces mas
    # rapido corre el tiempo simulado que el real. 30 = un segundo real son 30
    # segundos simulados (una hora simulada cada 2 minutos reales, un dia
    # completo en ~48 minutos reales).
    #
    # No subirlo mucho mas sin medir: a 120x una entrega de 15 minutos se
    # resolvia en 7 segundos reales — el repartidor "aparecia" en el destino
    # y no habia forma de leer una oferta antes de que cambiara el mundo.
    time_acceleration: float = 30.0

    # Ordenes esperadas por hora simulada (fuera de hora pico). La generacion
    # es proporcional al tiempo SIMULADO transcurrido, no a cada poll del
    # frontend, para que no dependa de la frecuencia de sondeo.
    orders_per_sim_hour: float = 6.0

    frontend_origin: str = "http://localhost:5173"

    # Costos operativos (agente repartidor)
    gas_cost_per_km_moto: float = 0.80
    gas_cost_per_km_auto: float = 2.00
    time_cost_per_minute: float = 1.50
    max_batch_orders: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
