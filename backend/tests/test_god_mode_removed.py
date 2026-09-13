"""Regresion: Modo Dios se elimino del producto por pedido explicito. Estos
tests no verifican una feature — verifican una AUSENCIA, para que nadie lo
reintroduzca sin querer (p.ej. copiando un endpoint viejo de un branch, o
restaurando un campo de un merge). Sin red ni base de datos: solo inspeccion
de modulos y de las rutas ya registradas en la app.
"""

from app.api.routes import simulation
from app.engine import traffic_rules
from app.schemas import simulation as simulation_schemas


def test_god_mode_endpoint_is_not_registered():
    paths = {route.path for route in simulation.router.routes}
    assert "/simulation/god-mode" not in paths


def test_god_mode_route_function_does_not_exist():
    assert not hasattr(simulation, "god_mode")


def test_god_mode_request_schema_does_not_exist():
    assert not hasattr(simulation_schemas, "GodModeRequest")


def test_simulation_state_no_longer_exposes_a_preset():
    assert "god_mode_preset" not in simulation_schemas.SimulationState.model_fields


def test_god_mode_presets_dict_does_not_exist():
    assert not hasattr(traffic_rules, "GOD_MODE_PRESETS")


def test_session_state_no_longer_carries_god_mode_fields():
    from app.api.routes.session_state import SessionState

    field_names = {f.name for f in SessionState.__dataclass_fields__.values()}
    assert not field_names & {"god_mode_preset", "hour_override", "active_closure"}
