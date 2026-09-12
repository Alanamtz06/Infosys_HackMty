"""Agente de entorno (trafico): vigila el reloj virtual y actualiza los pesos del grafo."""

import networkx as nx

from app.engine.graph_loader import apply_traffic
from app.engine.virtual_clock import VirtualClock


class TrafficAgent:
    def __init__(self, graph: nx.MultiDiGraph, clock: VirtualClock):
        self.graph = graph
        self.clock = clock

    def tick(self) -> None:
        apply_traffic(self.graph, self.clock.virtual_hour())
