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


class DecisionRequest(BaseModel):
    run_id: str
    order_id: str
    accept: bool


class RunIdRequest(BaseModel):
    run_id: str
