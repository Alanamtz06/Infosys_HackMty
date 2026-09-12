"""Endpoints de control de la simulacion: iniciar turno, estado del reloj virtual, Modo Dios."""

from fastapi import APIRouter

from app.engine.traffic_rules import GOD_MODE_PRESETS
from app.schemas.simulation import GodModeRequest, SimulationStart

router = APIRouter(prefix="/simulation", tags=["simulation"])

# TODO: reemplazar por un manejador de sesion de simulacion real (in-memory o Redis)
# que instancie VirtualClock, TrafficAgent, DeliveryAgent y el grafo cargado.
_simulation_state: dict = {}


@router.post("/start")
def start_simulation(payload: SimulationStart):
    return {"status": "started", "agent_type": payload.agent_type, "duration_min": payload.real_duration_minutes}


@router.get("/state")
def get_state():
    return _simulation_state


@router.post("/god-mode")
def god_mode(payload: GodModeRequest):
    if payload.preset not in GOD_MODE_PRESETS:
        return {"error": f"preset desconocido, opciones: {list(GOD_MODE_PRESETS)}"}
    return {"preset": payload.preset, "virtual_hour": GOD_MODE_PRESETS[payload.preset]}
