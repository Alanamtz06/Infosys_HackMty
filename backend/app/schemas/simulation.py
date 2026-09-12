from pydantic import BaseModel


class SimulationStart(BaseModel):
    real_duration_minutes: float = 3.0
    agent_type: str = "inteligente"  # "inteligente" | "novato"


class GodModeRequest(BaseModel):
    preset: str  # "manana" | "comida" | "salida_trabajo"


class SimulationState(BaseModel):
    virtual_hour: float
    virtual_minute: float
    is_finished: bool
    net_earnings: float
