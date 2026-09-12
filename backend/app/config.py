from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://user:password@localhost:5432/delivery_sim"
    gemini_api_key: str = ""

    city_center_lat: float = 25.6714
    city_center_lon: float = -100.3095
    city_radius_km: float = 8.0

    shift_duration_minutes: int = 180

    frontend_origin: str = "http://localhost:5173"

    # Costos operativos (agente repartidor)
    gas_cost_per_km_moto: float = 0.80
    gas_cost_per_km_auto: float = 2.00
    time_cost_per_minute: float = 1.50
    max_batch_orders: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
