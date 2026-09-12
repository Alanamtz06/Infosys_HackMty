"""Agente de entorno (trafico): vigila el reloj y actualiza los pesos del grafo."""

from typing import Protocol

import networkx as nx

from app.engine.graph_loader import apply_traffic


class HasVirtualHour(Protocol):
    """Cualquier reloj que sepa que hora del dia es: `WorldClock` (el global
    que usa la simulacion en vivo) o `VirtualClock` (turno de duracion fija).
    Ver app/engine/virtual_clock.py."""

    def virtual_hour(self) -> float: ...


class TrafficAgent:
    def __init__(self, graph: nx.MultiDiGraph, clock: HasVirtualHour):
        self.graph = graph
        self.clock = clock

    def tick(self) -> None:
        apply_traffic(self.graph, self.clock.virtual_hour())
