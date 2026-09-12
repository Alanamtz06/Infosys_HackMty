"""Sin dependencia de red."""

from app.decision.policy import MAX_LENIENCY_MXN, PolicyState, dynamic_threshold, should_accept


def test_threshold_is_zero_when_on_pace():
    state = PolicyState(orders_accepted=4, virtual_minutes_elapsed=60.0, target_orders_per_hour=4.0)
    assert dynamic_threshold(state) == 0.0


def test_threshold_drops_when_behind_pace():
    state = PolicyState(orders_accepted=1, virtual_minutes_elapsed=60.0, target_orders_per_hour=4.0)
    assert dynamic_threshold(state) < 0.0


def test_threshold_never_drops_below_max_leniency():
    state = PolicyState(orders_accepted=0, virtual_minutes_elapsed=1000.0, target_orders_per_hour=4.0)
    assert dynamic_threshold(state) == -MAX_LENIENCY_MXN


def test_threshold_is_zero_at_shift_start():
    # virtual_minutes_elapsed=0 -> no hay ritmo esperado todavia, no penaliza
    state = PolicyState(orders_accepted=0, virtual_minutes_elapsed=0.0)
    assert dynamic_threshold(state) == 0.0


def test_should_accept_uses_threshold():
    behind = PolicyState(orders_accepted=0, virtual_minutes_elapsed=120.0, target_orders_per_hour=4.0)
    assert should_accept(score=-5.0, state=behind)  # se acepta un score negativo porque vas muy atrasado
    assert not should_accept(score=-100.0, state=behind)  # pero no cualquier cosa

    on_pace = PolicyState(orders_accepted=8, virtual_minutes_elapsed=120.0, target_orders_per_hour=4.0)
    assert should_accept(score=0.01, state=on_pace)
    assert not should_accept(score=-0.01, state=on_pace)
