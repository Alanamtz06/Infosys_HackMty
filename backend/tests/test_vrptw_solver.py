"""Sin dependencia de red: matriz de tiempos sintetica."""

import math

import numpy as np
import pytest

from app.decision.vrptw_solver import solve_route

# 0 = inicio del repartidor; (1->2) y (3->4) son pares pickup->delivery.
# 1 y 2 estan cerca entre si (y del inicio); 3 y 4 estan mas lejos.
SIMPLE_MATRIX = np.array(
    [
        [0, 10, 12, 30, 32],
        [10, 0, 3, 25, 27],
        [12, 3, 0, 23, 25],
        [30, 25, 23, 0, 4],
        [32, 27, 25, 4, 0],
    ],
    dtype=float,
)
WIDE_OPEN_WINDOWS = [(0, 10**6)] * 5


def test_respects_pickup_before_delivery():
    result = solve_route(SIMPLE_MATRIX, WIDE_OPEN_WINDOWS, [(1, 2), (3, 4)], start_node=0)
    assert result.feasible
    assert result.node_order.index(1) < result.node_order.index(2)
    assert result.node_order.index(3) < result.node_order.index(4)


def test_no_return_trip_to_start():
    result = solve_route(SIMPLE_MATRIX, WIDE_OPEN_WINDOWS, [(1, 2), (3, 4)], start_node=0)
    assert result.total_time == pytest.approx(40.0)  # suma de tramos reales, sin viaje de vuelta
    assert 0 not in result.node_order[1:]


def test_infeasible_time_window_reported_not_raised():
    tight = [(0, 10**6), (0, 10**6), (0, 5), (0, 10**6), (0, 10**6)]  # imposible: llegar al nodo 2 antes de t=5
    result = solve_route(SIMPLE_MATRIX, tight, [(1, 2), (3, 4)], start_node=0)
    assert not result.feasible
    assert result.total_time == math.inf


def test_unreachable_pair_does_not_crash():
    """Un par de nodos en infinito (p.ej. un cierre de calle los desconecta)
    no debe tumbar el solver con OverflowError."""
    matrix = SIMPLE_MATRIX.copy()
    matrix[0, 1] = float("inf")
    matrix[1, 0] = float("inf")
    result = solve_route(matrix, WIDE_OPEN_WINDOWS, [(1, 2), (3, 4)], start_node=0)
    assert isinstance(result.feasible, bool)  # no exception is the actual assertion


def test_single_node_no_orders():
    result = solve_route(np.array([[0.0]]), [(0, 100)], [], start_node=0)
    assert result.feasible
    assert result.node_order == [0]
    assert result.total_time == 0.0
