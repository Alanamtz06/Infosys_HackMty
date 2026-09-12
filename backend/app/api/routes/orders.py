"""Endpoints de ordenes sueltas: generar una de ejemplo y evaluar una a mano.

El flujo real del turno NO pasa por aqui — vive en
`api/routes/simulation.py` (genera, evalua y persiste dentro del tick). Estos
endpoints sirven para probar el motor sin levantar una sesion de simulacion:
utiles para depurar el Score o el ruteo desde Swagger (/docs).
"""

from fastapi import APIRouter, HTTPException

from app.agents.delivery_agent import DeliveryAgent
from app.agents.order_generator import generate_order
from app.config import settings
from app.decision.scoring import VehicleType
from app.engine.graph_loader import apply_traffic, load_graph
from app.engine.pois import load_restaurants
from app.engine.virtual_clock import world_clock
from app.schemas.order import OrderCreate

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("/random")
def get_random_order():
    """Genera una orden de ejemplo: recogida en un restaurante real de OSM
    (ZMM), entrega en una casa aleatoria.

    Nota: la primera llamada descarga el grafo vial y los restaurantes desde
    OpenStreetMap (puede tardar); las siguientes usan el cache en memoria.
    """
    graph = load_graph()
    restaurants = load_restaurants()
    return generate_order(graph, restaurants, virtual_hour=world_clock.virtual_hour())


@router.post("/evaluate")
def evaluate_order(payload: OrderCreate, vehicle: str = "moto", origin_lat: float | None = None, origin_lon: float | None = None):
    """Calcula el Score de una orden concreta con el trafico de la hora
    simulada actual.

    `origin_lat`/`origin_lon` son opcionales: donde esta el repartidor. Sin
    ellos se evalua desde el pickup (solo el tramo de entrega).
    """
    if vehicle not in {"moto", "auto"}:
        raise HTTPException(400, "vehicle must be 'moto' or 'auto'")

    graph = load_graph()
    virtual_hour = world_clock.virtual_hour()
    apply_traffic(graph, virtual_hour)

    agent = DeliveryAgent(graph, vehicle=VehicleType(vehicle))
    if origin_lat is not None and origin_lon is not None:
        agent.position = (origin_lat, origin_lon)

    evaluation = agent.evaluate_order(
        (payload.pickup_lat, payload.pickup_lon),
        (payload.dropoff_lat, payload.dropoff_lon),
        payload.fare,
    )
    if evaluation is None:
        raise HTTPException(422, "No route between those points (a road closure may have cut them off)")

    return {
        "virtual_hour": round(virtual_hour, 3),
        "sim_time": world_clock.iso_timestamp(),
        "vehicle": vehicle,
        "fare": evaluation.fare,
        "distance_km": round(evaluation.distance_km, 3),
        "time_minutes": round(evaluation.time_minutes, 2),
        "gas_cost": round(evaluation.distance_km * evaluation.gas_cost_per_km, 2),
        "time_cost": round(evaluation.time_minutes * settings.time_cost_per_minute, 2),
        "score": round(evaluation.score, 2),
        "should_accept": evaluation.should_accept,
    }
