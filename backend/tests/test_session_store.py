"""Estado de turno compartido entre workers. Sin red, sin base de datos.

El round-trip de serializacion es lo critico: si algo del estado no sobrevive
el viaje a JSON, con Redis prendido el turno se corrompe en silencio en el
siguiente poll (y justo eso no lo detecta el modo en memoria, que guarda el
objeto tal cual).
"""

import fakeredis
import pytest

from app.api.routes.session_state import ActiveDelivery, PendingOrder, SessionState
from app.api.routes.session_store import InMemorySessionStore, RedisSessionStore
from app.decision.scoring import OrderEvaluation, VehicleType

ORDER = {
    "id": "3f1e7b0c-0000-4000-8000-000000000001",
    "pickup_lat": 25.67,
    "pickup_lon": -100.31,
    "pickup_name": "Taqueria de prueba",
    "dropoff_lat": 25.69,
    "dropoff_lon": -100.28,
    "fare": 88.5,
}


def _state() -> SessionState:
    evaluation = OrderEvaluation(fare=88.5, distance_km=7.2, time_minutes=23.4, vehicle=VehicleType.MOTO)
    return SessionState(
        run_id="run-1",
        novice_run_id="run-2",
        session_id="sess-1",
        vehicle="moto",
        started_sim_seconds=120.0,
        last_tick_sim_seconds=180.0,
        autonomous=True,
        hour_override=18.5,
        god_mode_preset="salida_trabajo",
        net_earnings=143.25,
        novice_earnings=98.1,
        orders_accepted=3,
        deliveries_completed=2,
        courier_position=(25.66, -100.30),
        novice_position=(25.70, -100.25),
        novice_busy_until_sim_seconds=999.0,
        active_closure={"u": 111, "v": 222, "street_name": "Av. Gonzalitos"},
        pending_orders={ORDER["id"]: PendingOrder(order=ORDER, evaluation=evaluation)},
        active_deliveries=[
            ActiveDelivery(order=ORDER, route=[1, 2, 3], total_seconds=640.0, started_sim_seconds=200.0)
        ],
        events=[{"ts": "2026-09-12T18:30:00.000", "type": "order_accepted", "message": "ok"}],
    )


def test_serialization_round_trip_keeps_everything():
    original = _state()
    restored = SessionState.from_dict(original.to_dict())

    assert restored.run_id == original.run_id
    assert restored.autonomous is True
    assert restored.hour_override == 18.5
    assert restored.net_earnings == pytest.approx(143.25)
    assert restored.novice_busy_until_sim_seconds == pytest.approx(999.0)
    assert restored.courier_position == (25.66, -100.30)
    assert restored.active_closure == original.active_closure
    assert restored.events == original.events


def test_round_trip_rebuilds_order_evaluations():
    restored = SessionState.from_dict(_state().to_dict())
    pending = restored.pending_orders[ORDER["id"]]

    assert isinstance(pending.evaluation, OrderEvaluation)
    assert pending.evaluation.vehicle is VehicleType.MOTO
    # el Score es una propiedad calculada: tiene que dar lo mismo despues del viaje
    assert pending.evaluation.score == pytest.approx(_state().pending_orders[ORDER["id"]].evaluation.score)


def test_round_trip_keeps_active_deliveries():
    restored = SessionState.from_dict(_state().to_dict())
    delivery = restored.active_deliveries[0]

    assert delivery.route == [1, 2, 3]
    assert delivery.total_seconds == pytest.approx(640.0)
    assert delivery.started_sim_seconds == pytest.approx(200.0)


def test_in_memory_store_basics():
    store = InMemorySessionStore()
    state = _state()
    assert store.get("run-1") is None

    store.save(state)
    assert store.run_ids() == ["run-1"]
    assert store.get("run-1") is state  # mismo proceso: es el mismo objeto

    store.delete("run-1")
    assert store.get("run-1") is None


def test_redis_store_shares_state_across_workers():
    """Dos stores contra el mismo Redis = dos workers de uvicorn."""
    server = fakeredis.FakeServer()
    worker_a = RedisSessionStore(fakeredis.FakeStrictRedis(server=server))
    worker_b = RedisSessionStore(fakeredis.FakeStrictRedis(server=server))

    worker_a.save(_state())

    # el turno que arranco en A existe para B (esto es lo que hoy da 404)
    seen_by_b = worker_b.get("run-1")
    assert seen_by_b is not None
    assert seen_by_b.net_earnings == pytest.approx(143.25)
    assert seen_by_b.pending_orders[ORDER["id"]].order["pickup_name"] == "Taqueria de prueba"
    assert worker_b.run_ids() == ["run-1"]

    # y lo que B cambia lo ve A
    seen_by_b.net_earnings = 200.0
    worker_b.save(seen_by_b)
    assert worker_a.get("run-1").net_earnings == pytest.approx(200.0)

    worker_a.delete("run-1")
    assert worker_b.get("run-1") is None


def test_redis_store_returns_none_for_unknown_run():
    store = RedisSessionStore(fakeredis.FakeStrictRedis())
    assert store.get("no-existe") is None
