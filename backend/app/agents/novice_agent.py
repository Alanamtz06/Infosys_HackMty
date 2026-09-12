"""Agente Novato: acepta todas las ordenes sin calcular Score.

Sirve como linea base de comparacion en el Marcador Global.
"""


class NoviceAgent:
    def evaluate_order(self, *_args, **_kwargs) -> bool:
        return True
