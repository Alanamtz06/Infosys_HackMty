"""Endpoints de ordenes: crear, evaluar (Score) y decidir aceptar/rechazar."""

from fastapi import APIRouter

from app.schemas.order import OrderCreate

router = APIRouter(prefix="/orders", tags=["orders"])

# TODO: conectar con DeliveryAgent.evaluate_order sobre el grafo activo de la simulacion
# y persistir el resultado con app.db.repository.


@router.post("/evaluate")
def evaluate_order(payload: OrderCreate):
    return {"received": payload.model_dump()}
