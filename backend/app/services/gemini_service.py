"""Auditoria de decisiones con Gemini: explica en lenguaje natural por que
el agente acepto o rechazo una orden, a partir de las variables numericas del Score.

TODO: requiere GEMINI_API_KEY valida en .env.
"""

import google.generativeai as genai

from app.config import settings
from app.decision.scoring import OrderEvaluation

genai.configure(api_key=settings.gemini_api_key)

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


def audit_decision(evaluation: OrderEvaluation) -> str:
    model = genai.GenerativeModel("gemini-flash-latest")
    prompt = PROMPT_TEMPLATE.format(
        decision="accept" if evaluation.should_accept else "reject",
        fare=evaluation.fare,
        distance_km=evaluation.distance_km,
        time_minutes=evaluation.time_minutes,
        gas_cost=evaluation.distance_km * evaluation.gas_cost_per_km,
        time_cost=evaluation.time_minutes * settings.time_cost_per_minute,
        score=evaluation.score,
    )
    response = model.generate_content(prompt)
    return response.text
