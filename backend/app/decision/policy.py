"""Decide si una oferta vale la pena: tasa por hora contra tarifa de reserva.

`OrderEvaluation.score` (scoring.py) dice cuanto deja un pedido en total, y
esa formula no se toca (tambien vive en SQL, ver db/schema.sql). Lo que esta
capa decide es otra cosa: si conviene OCUPAR el tiempo del repartidor con
este pedido.

Por que no basta con "Score > 0": el tiempo del repartidor es el recurso
escaso. Un pedido que deja $30 en 45 minutos y otro que deja $25 en 15
minutos no son comparables — el primero paga $40/hora y el segundo $100/hora,
y aceptar el primero tapa la agenda para los tres siguientes. Medido sobre el
flujo real, con el corte en Score > 0 el agente aceptaba ~83% de las ofertas
y terminaba empatando con el novato que acepta todo: la decision no estaba
midiendo nada.

Asi que la regla es de tarifa de reserva (el mismo razonamiento del salario
de reserva): se acepta si la oferta paga, por hora, mas que el minimo que el
repartidor esta dispuesto a cobrar por estar ocupado.

Ese minimo se relaja si el repartidor va atrasado respecto de su ritmo
objetivo de pedidos aceptados: mejor un pedido mediocre que una hora parado.
Nota: el prototipo original de este algoritmo tambien bajaba el umbral segun
"cuanto le queda al turno", pero aqui el reloj corre abierto (ver
engine/virtual_clock.py::WorldClock) y no hay una hora de fin conocida de
antemano, asi que esa señal no existe.
"""

from dataclasses import dataclass

from app.config import settings
from app.decision.scoring import OrderEvaluation

# Que tanto puede bajar la tarifa de reserva cuando el repartidor va muy
# atrasado de su ritmo: 0.35 = hasta el 35% de la tarifa base.
MIN_PACE_FACTOR = 0.35

DEFAULT_TARGET_ORDERS_PER_HOUR = 2.5


@dataclass
class PolicyState:
    orders_accepted: int
    virtual_minutes_elapsed: float
    target_orders_per_hour: float = DEFAULT_TARGET_ORDERS_PER_HOUR


def net_rate_per_hour(evaluation: OrderEvaluation) -> float:
    """MXN netos por hora de trabajo que paga esta oferta.

    Es el Score repartido sobre el tiempo que ocupa (viaje + tiempo de
    servicio), que es la magnitud con la que un repartidor compara ofertas de
    distinto tamaño.
    """
    if evaluation.time_minutes <= 0:
        return float("inf") if evaluation.score > 0 else float("-inf")
    return float(evaluation.score) / float(evaluation.time_minutes) * 60


def _pace_ratio(state: PolicyState) -> float:
    """1.0 si va a su ritmo objetivo o mejor; se acerca a 0 si va atrasado."""
    expected_orders_by_now = state.target_orders_per_hour / 60.0 * state.virtual_minutes_elapsed
    if expected_orders_by_now <= 0:
        return 1.0
    return min(state.orders_accepted / expected_orders_by_now, 1.0)


def reservation_rate(state: PolicyState) -> float:
    """MXN netos por hora que el repartidor exige ahora mismo para aceptar."""
    pace_factor = max(_pace_ratio(state), MIN_PACE_FACTOR)
    return settings.reservation_rate_mxn_per_hour * pace_factor


def should_accept(evaluation: OrderEvaluation, state: PolicyState) -> bool:
    """True si la oferta paga por hora mas que la tarifa de reserva actual.

    Un Score negativo se rechaza siempre: por muy parado que este, perder
    dinero no es una opcion que el agente deba recomendar.
    """
    if evaluation.score <= 0:
        return False
    return bool(net_rate_per_hour(evaluation) >= reservation_rate(state))


def explain(evaluation: OrderEvaluation, state: PolicyState) -> str:
    """Una linea de por que si o por que no — para el log y para poder
    justificarle la decision a un juez sin abrir el codigo."""
    rate = net_rate_per_hour(evaluation)
    bar = reservation_rate(state)
    if evaluation.score <= 0:
        return f"Score ${evaluation.score:.2f} — loses money outright"
    verdict = "clears" if rate >= bar else "below"
    return (
        f"${rate:.0f}/h net over {evaluation.time_minutes:.0f} min {verdict} "
        f"the ${bar:.0f}/h bar"
    )
