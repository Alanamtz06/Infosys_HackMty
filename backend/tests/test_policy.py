"""Sin dependencia de red."""

import pytest

from app.config import settings
from app.decision.policy import (
    MIN_PACE_FACTOR,
    PolicyState,
    net_rate_per_hour,
    reservation_rate,
    should_accept,
)
from app.decision.scoring import OrderEvaluation, VehicleType


def _evaluation(fare: float, distance_km: float, time_minutes: float) -> OrderEvaluation:
    return OrderEvaluation(
        fare=fare, distance_km=distance_km, time_minutes=time_minutes, vehicle=VehicleType.MOTO
    )


ON_PACE = PolicyState(orders_accepted=5, virtual_minutes_elapsed=120.0, target_orders_per_hour=2.5)
BEHIND = PolicyState(orders_accepted=0, virtual_minutes_elapsed=120.0, target_orders_per_hour=2.5)


def test_net_rate_is_score_over_time():
    # $100 - (10km * 0.80) - (20min * 1.50) = $62 en 20 min = $186/h
    evaluation = _evaluation(fare=100.0, distance_km=10.0, time_minutes=20.0)
    assert evaluation.score == pytest.approx(62.0)
    assert net_rate_per_hour(evaluation) == pytest.approx(186.0)


def test_rejects_negative_score_even_when_desperate():
    """Por muy atrasado que vaya, perder dinero no es una opcion."""
    losing = _evaluation(fare=20.0, distance_km=12.0, time_minutes=40.0)
    assert losing.score < 0
    assert not should_accept(losing, BEHIND)


def test_prefers_rate_over_absolute_score():
    """El punto de la politica: un pedido que deja MAS en total puede ser peor
    negocio que uno chico y rapido, porque ocupa el recurso escaso (tiempo)."""
    # 75 min, 18 km: deja $30 -> $24/h
    big_and_slow = _evaluation(fare=156.90, distance_km=18.0, time_minutes=75.0)
    # 15 min, 3 km: deja $20 -> $80/h
    small_and_fast = _evaluation(fare=44.90, distance_km=3.0, time_minutes=15.0)

    assert big_and_slow.score == pytest.approx(30.0)
    assert small_and_fast.score == pytest.approx(20.0)
    assert big_and_slow.score > small_and_fast.score  # deja mas en total...

    assert net_rate_per_hour(big_and_slow) == pytest.approx(24.0)
    assert net_rate_per_hour(small_and_fast) == pytest.approx(80.0)  # ...pero paga peor por hora

    assert should_accept(small_and_fast, ON_PACE)
    assert not should_accept(big_and_slow, ON_PACE)


def test_reservation_rate_drops_when_behind_pace():
    assert reservation_rate(BEHIND) < reservation_rate(ON_PACE)
    assert reservation_rate(ON_PACE) == pytest.approx(settings.reservation_rate_mxn_per_hour)
    assert reservation_rate(BEHIND) == pytest.approx(
        settings.reservation_rate_mxn_per_hour * MIN_PACE_FACTOR
    )


def test_behind_pace_accepts_a_mediocre_order_that_on_pace_would_reject():
    # 45 min, 6 km, deja $12 -> $16/h: por debajo de la barra base ($30/h)
    # pero por encima de la barra relajada de quien lleva el turno en ceros.
    mediocre = _evaluation(fare=84.30, distance_km=6.0, time_minutes=45.0)
    assert mediocre.score == pytest.approx(12.0)
    rate = net_rate_per_hour(mediocre)
    assert rate == pytest.approx(16.0)
    assert reservation_rate(BEHIND) < rate < reservation_rate(ON_PACE)

    assert should_accept(mediocre, BEHIND)
    assert not should_accept(mediocre, ON_PACE)


def test_reservation_rate_is_full_at_shift_start():
    # sin tiempo transcurrido no hay ritmo esperado todavia: no se relaja nada
    fresh = PolicyState(orders_accepted=0, virtual_minutes_elapsed=0.0)
    assert reservation_rate(fresh) == pytest.approx(settings.reservation_rate_mxn_per_hour)


def test_should_accept_returns_plain_bool():
    """Los atributos del grafo son numpy; si se filtran, Pydantic serializa
    con DeprecationWarning."""
    import numpy as np

    evaluation = OrderEvaluation(
        fare=np.float64(100.0),
        distance_km=np.float64(5.0),
        time_minutes=np.float64(20.0),
        vehicle=VehicleType.MOTO,
    )
    assert type(should_accept(evaluation, ON_PACE)) is bool
