"""Registro / login del repartidor. El vehiculo elegido aqui (moto | auto)
es el que despues determina el costo de gasolina por km en calculate_score()
(ver app/db/schema.sql) para los turnos que corra esta cuenta.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.connection import get_session
from app.db.models import User
from app.schemas.auth import UserLogin, UserOut, UserProfileUpdate, UserRegister
from app.services.auth_service import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

VEHICLE_TYPES = {"moto", "auto"}


def _to_user_out(user: User) -> UserOut:
    return UserOut(id=str(user.id), username=user.username, vehicle_type=user.vehicle_type)


@router.post("/register", response_model=UserOut)
def register(payload: UserRegister, session: Session = Depends(get_session)):
    if payload.vehicle_type not in VEHICLE_TYPES:
        raise HTTPException(400, f"Invalid vehicle_type, options: {sorted(VEHICLE_TYPES)}")

    existing = session.scalar(select(User).where(User.username == payload.username))
    if existing is not None:
        raise HTTPException(409, "That username is already taken")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        vehicle_type=payload.vehicle_type,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _to_user_out(user)


@router.post("/login", response_model=UserOut)
def login(payload: UserLogin, session: Session = Depends(get_session)):
    user = session.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return _to_user_out(user)


@router.patch("/profile", response_model=UserOut)
def update_profile(payload: UserProfileUpdate, session: Session = Depends(get_session)):
    """Edita el perfil del repartidor. Por ahora solo el vehiculo: cambia el
    costo por km (calculate_score()) de los turnos que arranquen desde este
    momento en adelante — los ya corridos no se recalculan retroactivamente.
    """
    if payload.vehicle_type not in VEHICLE_TYPES:
        raise HTTPException(400, f"Invalid vehicle_type, options: {sorted(VEHICLE_TYPES)}")

    try:
        user_id = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user_id")

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")

    user.vehicle_type = payload.vehicle_type
    session.commit()
    session.refresh(user)
    return _to_user_out(user)
