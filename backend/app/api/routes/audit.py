"""Endpoint de auditoria de decisiones (boton 'Auditar Decision' en la UI).

Reconstruye la evaluacion numerica de una orden y le pide a Gemini que la
explique en lenguaje natural. La explicacion se cachea en `decision_audits`:
abrir dos veces el audit de la misma orden no vuelve a pagar una llamada al
modelo.

El frontend (AuditDecisionButton.tsx) solo lee `data.explanation`; el resto
de los campos son informativos.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.connection import get_session
from app.db.models import DecisionAudit, Order as OrderModel, TripRecord
from app.decision.scoring import OrderEvaluation, VehicleType
from app.schemas.order import AuditRequest
from app.services.gemini_service import MODEL_NAME, audit_decision

router = APIRouter(prefix="/audit", tags=["audit"])


def _evaluation_from_trip(trip: TripRecord) -> OrderEvaluation:
    return OrderEvaluation(
        fare=trip.fare,
        distance_km=trip.distance_km,
        time_minutes=trip.time_minutes,
        vehicle=VehicleType(trip.vehicle),
    )


@router.post("/decision")
def audit_order_decision(payload: AuditRequest, db: Session = Depends(get_session)):
    try:
        order_id = uuid.UUID(payload.order_id)
    except ValueError:
        raise HTTPException(400, "order_id must be a UUID")

    cached = db.scalars(
        select(DecisionAudit).where(DecisionAudit.order_id == order_id).order_by(DecisionAudit.generated_at.desc())
    ).first()
    if cached is not None:
        return {
            "order_id": payload.order_id,
            "explanation": cached.explanation,
            "source": "cache",
            "model": cached.model,
        }

    # La decision del agente inteligente sobre esta orden es la que se audita
    # (el novato acepta todo, no hay nada que explicar ahi).
    trip = db.scalars(
        select(TripRecord)
        .where(TripRecord.order_id == order_id, TripRecord.agent_type == "inteligente")
        .order_by(TripRecord.created_at.desc())
    ).first()

    if trip is None:
        # Sin decision todavia: la orden puede existir pero seguir pendiente.
        order = db.get(OrderModel, order_id)
        if order is None:
            raise HTTPException(404, "Unknown order")
        raise HTTPException(
            409,
            "That order has not been decided yet — accept or reject it before auditing the decision",
        )

    evaluation = _evaluation_from_trip(trip)
    explanation, source = audit_decision(evaluation, accepted=trip.accepted)

    db.add(DecisionAudit(order_id=order_id, explanation=explanation, model=MODEL_NAME if source == "gemini" else source))
    db.commit()

    return {
        "order_id": payload.order_id,
        "explanation": explanation,
        "source": source,
        "model": MODEL_NAME if source == "gemini" else source,
        "accepted": trip.accepted,
        "score": trip.score,
    }
