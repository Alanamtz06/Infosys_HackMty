"""Endpoints de ordenes: generar, evaluar (Score) y decidir aceptar/rechazar."""

from fastapi import APIRouter

from app.agents.order_generator import generate_order
from app.engine.graph_loader import load_graph
from app.engine.pois import load_restaurants
from app.schemas.order import OrderCreate

router = APIRouter(prefix="/orders", tags=["orders"])

# TODO: conectar /evaluate con DeliveryAgent.evaluate_order sobre el grafo activo
# de la simulacion y persistir el resultado con app.db.repository.


@router.get("/random")
def get_random_order():
    """Genera una orden de ejemplo: recogida en un restaurante real de OSM
    (ZMM), entrega en una casa aleatoria. Util para probar sin tener toda la
    sesion de simulacion orquestada todavia.

    Nota: la primera llamada descarga el grafo vial y los restaurantes desde
    OpenStreetMap (puede tardar); las siguientes usan el cache en memoria.
    """
    graph = load_graph()
    restaurants = load_restaurants()
    return generate_order(graph, restaurants)


@router.post("/evaluate")
def evaluate_order(payload: OrderCreate):
    return {"received": payload.model_dump()}
