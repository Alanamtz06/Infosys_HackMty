"""Endpoint de auditoria de decisiones (boton 'Auditar Decision' en la UI)."""

from fastapi import APIRouter

from app.schemas.order import AuditRequest

router = APIRouter(prefix="/audit", tags=["audit"])

# TODO: recuperar la OrderEvaluation real de la orden (por order_id) desde el
# estado de simulacion o la base de datos, y pasarla a app.services.gemini_service.audit_decision


@router.post("/decision")
def audit_decision(payload: AuditRequest):
    return {"order_id": payload.order_id, "explanation": "TODO: conectar con gemini_service.audit_decision"}
