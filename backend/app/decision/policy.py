"""Umbral de aceptacion dinamico para `PendingOrderOut.should_accept`.

`OrderEvaluation.should_accept` (scoring.py) es un corte estatico en
Score > 0 y se queda igual (es la formula que tambien vive en SQL, no se
toca). Esta capa la envuelve con una segunda senal que SI cambia con el
turno: si el repartidor va muy atrasado en cuantos pedidos ha aceptado
respecto de un ritmo objetivo, se vuelve mas permisivo (acepta incluso un
Score ligeramente negativo) para no terminar el turno con pocas entregas por
ser demasiado selectivo.

Diferencia a proposito con el prototipo original de este algoritmo: alla el
umbral tambien bajaba segun "cuanto tiempo le queda al turno", porque el
turno tenia una duracion fija conocida de antemano. Aqui el VirtualClock
corre "abierto" (`loop=True`, ver engine/virtual_clock.py) — no hay una hora
de fin planeada, el humano decide cuando terminar con /simulation/end — asi
que esa senal de "urgencia por tiempo" no tiene un valor real que usar y se
omite. Solo queda el ajuste por ritmo de aceptacion.
"""

from dataclasses import dataclass

# Cuanto puede bajar el umbral (en pesos de Score) cuando el repartidor va
# muy atrasado de su ritmo objetivo de pedidos aceptados.
MAX_LENIENCY_MXN = 15.0

DEFAULT_TARGET_ORDERS_PER_HOUR = 3.0


@dataclass
class PolicyState:
    orders_accepted: int
    virtual_minutes_elapsed: float
    target_orders_per_hour: float = DEFAULT_TARGET_ORDERS_PER_HOUR


def _pace_ratio(state: PolicyState) -> float:
    """1.0 si vas a tu ritmo objetivo o mejor; se acerca a 0 si vas atrasado."""
    expected_orders_by_now = state.target_orders_per_hour / 60.0 * state.virtual_minutes_elapsed
    if expected_orders_by_now <= 0:
        return 1.0
    return min(state.orders_accepted / expected_orders_by_now, 1.0)


def dynamic_threshold(state: PolicyState) -> float:
    """Score minimo (MXN) para aceptar ahora mismo. 0 si vas a tu ritmo o
    mejor; baja hasta -MAX_LENIENCY_MXN si vas muy atrasado."""
    return -MAX_LENIENCY_MXN * (1.0 - _pace_ratio(state))


def should_accept(score: float, state: PolicyState) -> bool:
    # bool() explicito: si `score` viene de un calculo con atributos del grafo
    # de OSMnx es un numpy.float64 y la comparacion devolveria numpy.bool_.
    return bool(score >= dynamic_threshold(state))
