from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)
    vehicle_type: str = "moto"  # "moto" | "auto"


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    vehicle_type: str


class UserProfileUpdate(BaseModel):
    """Edicion de perfil: por ahora solo el vehiculo es editable. Cambia el
    costo por km de TODOS los turnos que corran desde ahora — los ya
    terminados no se ven afectados (TripRecord.vehicle queda congelado a como
    era al momento de cada turno, ver comentario en db/models.py).

    `user_id` va en el body, no en la URL: no hay sesion/token en esta app
    (el login solo devuelve el usuario), asi que el frontend identifica de
    quien es la peticion igual que ya hace en /simulation/start.
    """

    user_id: str
    vehicle_type: str
