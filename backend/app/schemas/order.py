from pydantic import BaseModel


class OrderCreate(BaseModel):
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    fare: float


class OrderDecision(BaseModel):
    order_id: str
    accepted: bool
    score: float
    distance_km: float
    time_minutes: float


class AuditRequest(BaseModel):
    order_id: str
