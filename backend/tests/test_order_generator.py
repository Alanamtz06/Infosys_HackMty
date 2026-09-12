"""Sin dependencia de red."""

import random

from app.agents.order_generator import is_peak_hour, orders_per_sim_hour, orders_to_generate


def test_no_orders_without_elapsed_time():
    """La demanda depende del tiempo SIMULADO, no de cada poll del frontend:
    sin tiempo transcurrido no aparecen ordenes."""
    assert orders_to_generate(virtual_hour=14.0, sim_minutes_elapsed=0) == 0
    assert orders_to_generate(virtual_hour=14.0, sim_minutes_elapsed=-5) == 0


def test_more_elapsed_time_means_more_orders_on_average():
    random.seed(11)
    short = sum(orders_to_generate(11.0, 1) for _ in range(300))
    random.seed(11)
    long = sum(orders_to_generate(11.0, 20) for _ in range(300))
    assert long > short


def test_peak_hours_have_a_higher_rate():
    assert is_peak_hour(14.0)
    assert not is_peak_hour(11.0)
    assert orders_per_sim_hour(14.0) > orders_per_sim_hour(11.0)


def test_never_floods_in_a_single_tick():
    random.seed(5)
    # un salto absurdo de tiempo simulado no debe generar cientos de ordenes
    assert all(orders_to_generate(14.0, 10_000) <= 3 for _ in range(50))
