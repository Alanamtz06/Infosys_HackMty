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

    # Estado de los turnos en curso compartido entre workers de uvicorn. Vacio
    # (default) = estado en memoria del proceso, que solo sirve con un worker.
    # Ver api/routes/session_store.py.
    redis_url: str = ""

    frontend_origin: str = "http://localhost:5173"

    # Costos operativos (agente repartidor)
    gas_cost_per_km_moto: float = 0.80
    gas_cost_per_km_auto: float = 2.00
    time_cost_per_minute: float = 1.50
    max_batch_orders: int = 3

    # Mochila del repartidor: cuantos pedidos puede llevar encima a la vez.
    max_active_deliveries: int = 2

    # Modo estricto de la mochila (pedido 1 aun sin recoger, ver
    # decision/batching.py::plan_backpack_route y
    # api/routes/simulation.py::_fits_strict_corridor): que tan cerca deben
    # quedar el pickup y el dropoff del 2do pedido de los del 1ro, como
    # fraccion del propio trayecto del 1ro (pickup->dropoff). 0.4 = hasta 40%
    # de esa distancia en cada punto.
    backpack_strict_proximity_ratio: float = 0.4

    # Minutos que se van fuera de la carretera en cada pedido: esperar a que
    # el restaurante saque la comida + entregarla en la puerta. No estaba
    # modelado y es un costo real que cambia la decision: con ~8 minutos
    # fijos, un pedido de tarifa baja no se salva por estar cerca.
    service_time_minutes: float = 8.0

    # Tarifa de reserva (decision/policy.py): MXN NETOS por hora que el
    # repartidor exige para ocupar su tiempo con un pedido. "Netos" = ya
    # descontados gasolina y el valor del tiempo, asi que $30/h de Score es
    # margen por encima de los $90/h a los que la formula ya valora su hora.
    #
    # Calibrado sobre la distribucion real del flujo: con $30 el agente
    # rechaza ~55% de las ofertas fuera de hora pico y ~20% durante el surge.
    reservation_rate_mxn_per_hour: float = 30.0

    class Config:
        env_file = ".env"


settings = Settings()
