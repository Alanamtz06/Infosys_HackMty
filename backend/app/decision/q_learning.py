"""Reposicionamiento predictivo del agente repartidor via Q-Learning.

Estado: zona (celda de una grilla sobre la ZMM) + franja horaria.
Accion: moverse a una zona vecina.
Recompensa: ordenes aceptadas con score positivo originadas en esa zona.

TODO: definir la grilla de zonas, entrenar con el historial de ordenes
(Tiger Data) y persistir la Q-table.
"""

import random
from collections import defaultdict


class QLearningAgent:
    def __init__(self, actions: list[str], alpha: float = 0.1, gamma: float = 0.9, epsilon: float = 0.1):
        self.actions = actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.q_table: dict[str, dict[str, float]] = defaultdict(lambda: {a: 0.0 for a in actions})

    def choose_action(self, state: str) -> str:
        if random.random() < self.epsilon:
            return random.choice(self.actions)
        return max(self.q_table[state], key=self.q_table[state].get)

    def update(self, state: str, action: str, reward: float, next_state: str) -> None:
        best_next = max(self.q_table[next_state].values())
        current = self.q_table[state][action]
        self.q_table[state][action] = current + self.alpha * (reward + self.gamma * best_next - current)
