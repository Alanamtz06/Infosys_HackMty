from pydantic import BaseModel


class SimulationStart(BaseModel):
    user_id: str | None = None
    vehicle: str = "moto"  # "moto" | "auto" — viene del vehicle_type elegido al loguearse


class GodModeRequest(BaseModel):
    run_id: str
    preset: str | None = None  # None = quitar el override y volver al reloj normal


class PendingOrderOut(BaseModel):
    order_id: str
    pickup_name: str | None
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    fare: float
    distance_km: float
    time_minutes: float
    gas_cost: float
    time_cost: float
    score: float
    should_accept: bool


class SimEventOut(BaseModel):
    ts: str
    type: str
    message: str


class SimulationState(BaseModel):
    run_id: str
    vehicle: str
    virtual_hour: float
    virtual_minute: float
    is_finished: bool
    net_earnings: float
    god_mode_preset: str | None
    pending_orders: list[PendingOrderOut]
    events: list[SimEventOut]

    # --- Campos aditivos (el frontend actual no los lee todavia) -------------
    # JSON extra no rompe nada en TypeScript: `SimulationState` en
    # frontend/src/types/index.ts simplemente no los declara. Estan aqui para
    # que el integrante que trabaje el frontend los pueda usar sin tocar el
    # backend otra vez.

    # Hora simulada completa (ISO sin zona horaria, a proposito: ver
    # engine/virtual_clock.py::WorldClock.iso_timestamp).
    sim_time: str
    time_acceleration: float

    # Posicion en vivo del repartidor, interpolada sobre su ruta real. Para
    # reemplazar PLACEHOLDER_RIDER_POSITION en MapView.tsx.
    courier_lat: float | None
    courier_lon: float | None
    active_deliveries: int
    deliveries_completed: int

    orders_accepted: int

    # Acumulado del agente novato sobre el MISMO stream de ordenes: es lo que
    # ScoreboardModal.tsx necesita para `noviceEarnings`.
    novice_earnings: float
    session_id: str


class DecisionRequest(BaseModel):
    run_id: str
    order_id: str
    accept: bool


class RunIdRequest(BaseModel):
    run_id: str
