"""Registro, login y edicion de perfil, contra Tiger Data REAL — el proyecto
no tiene una base de prueba separada (ver db/connection.py), asi que estas
pruebas siguen la misma convencion que test_session_store.py con Redis:
infraestructura real, no un doble. El usuario de prueba se crea con un
username unico por corrida y se borra en el teardown del fixture, para no
dejar filas huerfanas en la tabla real.
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.auth import login, register, update_profile
from app.db.connection import SessionLocal
from app.db.models import User
from app.schemas.auth import UserLogin, UserProfileUpdate, UserRegister

pytestmark = pytest.mark.db


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def registered_user(db_session):
    """Un usuario real, unico por corrida, borrado al terminar el test."""
    payload = UserRegister(
        username=f"qa_test_{uuid.uuid4().hex[:12]}",
        password="correcthorse",
        vehicle_type="moto",
    )
    user = register(payload, db_session)
    yield user
    db_session.execute(select(User).where(User.id == uuid.UUID(user.id)))
    row = db_session.get(User, uuid.UUID(user.id))
    if row is not None:
        db_session.delete(row)
        db_session.commit()


def test_register_rejects_a_duplicate_username(db_session, registered_user):
    with pytest.raises(HTTPException) as exc_info:
        register(
            UserRegister(username=registered_user.username, password="whatever1", vehicle_type="auto"),
            db_session,
        )
    assert exc_info.value.status_code == 409


def test_register_rejects_an_invalid_vehicle_type(db_session):
    with pytest.raises(HTTPException) as exc_info:
        register(
            UserRegister(username=f"qa_test_{uuid.uuid4().hex[:12]}", password="whatever1", vehicle_type="bicicleta"),
            db_session,
        )
    assert exc_info.value.status_code == 400


def test_login_with_correct_password_returns_the_user(db_session, registered_user):
    result = login(UserLogin(username=registered_user.username, password="correcthorse"), db_session)
    assert result.id == registered_user.id
    assert result.vehicle_type == "moto"


def test_login_with_wrong_password_is_rejected(db_session, registered_user):
    with pytest.raises(HTTPException) as exc_info:
        login(UserLogin(username=registered_user.username, password="not-the-password"), db_session)
    assert exc_info.value.status_code == 401


def test_update_profile_changes_the_vehicle(db_session, registered_user):
    updated = update_profile(
        UserProfileUpdate(user_id=registered_user.id, vehicle_type="auto"),
        db_session,
    )
    assert updated.vehicle_type == "auto"
    assert updated.id == registered_user.id
    assert updated.username == registered_user.username

    # Se quedo escrito de verdad, no solo en el objeto devuelto en memoria.
    fresh_session = SessionLocal()
    try:
        row = fresh_session.get(User, uuid.UUID(registered_user.id))
        assert row is not None
        assert row.vehicle_type == "auto"
    finally:
        fresh_session.close()


def test_update_profile_rejects_an_invalid_vehicle_type(db_session, registered_user):
    with pytest.raises(HTTPException) as exc_info:
        update_profile(UserProfileUpdate(user_id=registered_user.id, vehicle_type="bicicleta"), db_session)
    assert exc_info.value.status_code == 400


def test_update_profile_rejects_an_unknown_user(db_session):
    with pytest.raises(HTTPException) as exc_info:
        update_profile(UserProfileUpdate(user_id=str(uuid.uuid4()), vehicle_type="moto"), db_session)
    assert exc_info.value.status_code == 404


def test_update_profile_rejects_a_malformed_user_id(db_session):
    with pytest.raises(HTTPException) as exc_info:
        update_profile(UserProfileUpdate(user_id="not-a-uuid", vehicle_type="moto"), db_session)
    assert exc_info.value.status_code == 400
