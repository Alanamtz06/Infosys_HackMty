"""Auditoria de decisiones con Gemini: explica en lenguaje natural por que
el agente acepto o rechazo una orden, a partir de las variables numericas del Score.

Requiere GEMINI_API_KEY en .env. Si la llamada falla (sin key, sin red,
cuota agotada), `audit_decision` NO explota: cae a una explicacion
deterministica armada con los mismos numeros. Para el criterio de "puede
explicarle una decision a un juez", una explicacion sin adornos siempre es
mejor que un error 500 a media demo.
"""

import google.generativeai as genai

from app.config import settings
from app.decision.scoring import OrderEvaluation

genai.configure(api_key=settings.gemini_api_key)

MODEL_NAME = "gemini-flash-latest"

PROMPT_TEMPLATE = """You are an assistant auditing a delivery courier's decisions in Monterrey, Mexico.
In 2-3 sentences, in plain English, explain why the following move was to
{decision} the order:

Fare: ${fare:.2f} MXN
Distance: {distance_km:.2f} km
Estimated time: {time_minutes:.1f} min
Fuel cost: ${gas_cost:.2f} MXN
Time cost: ${time_cost:.2f} MXN
Score (estimated net profit): ${score:.2f} MXN
"""


def _decision_label(evaluation: OrderEvaluation, accepted: bool | None) -> str:
    """La decision REAL si se conoce (en esta app la toma el conductor, no el
    agente), si no la que recomendaba el Score."""
    if accepted is None:
        return "accept" if evaluation.should_accept else "reject"
    return "accept" if accepted else "reject"


def fallback_explanation(evaluation: OrderEvaluation, accepted: bool | None = None) -> str:
    """Explicacion sin IA, armada con los mismos numeros del Score."""
    gas_cost = evaluation.distance_km * evaluation.gas_cost_per_km
    time_cost = evaluation.time_minutes * settings.time_cost_per_minute
    decision = _decision_label(evaluation, accepted)
    verdict = (
        "the fare covers the cost of the trip with room to spare"
        if evaluation.score >= 0
        else "the fare does not cover what the trip costs to run"
    )
    return (
        f"Decision: {decision}. The order paid ${evaluation.fare:.2f} MXN for "
        f"{evaluation.distance_km:.1f} km and about {evaluation.time_minutes:.0f} min of work. "
        f"Fuel runs ${gas_cost:.2f} and the time is worth ${time_cost:.2f}, leaving a Score of "
        f"${evaluation.score:.2f} MXN — {verdict}."
    )


def audit_decision(evaluation: OrderEvaluation, accepted: bool | None = None) -> tuple[str, str]:
    """Devuelve (explicacion, fuente) donde fuente es "gemini" o "fallback"."""
    prompt = PROMPT_TEMPLATE.format(
        decision=_decision_label(evaluation, accepted),
        fare=evaluation.fare,
        distance_km=evaluation.distance_km,
        time_minutes=evaluation.time_minutes,
        gas_cost=evaluation.distance_km * evaluation.gas_cost_per_km,
        time_cost=evaluation.time_minutes * settings.time_cost_per_minute,
        score=evaluation.score,
    )

    if not settings.gemini_api_key:
        return fallback_explanation(evaluation, accepted), "fallback"

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
    except Exception:
        return fallback_explanation(evaluation, accepted), "fallback"

    if not text:
        return fallback_explanation(evaluation, accepted), "fallback"
    return text, "gemini"
