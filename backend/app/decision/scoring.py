"""Formula de decision del agente repartidor.

Score = Tarifa - (Distancia * Costo_Gasolina) - (Tiempo * Costo_Tiempo)
"""

from dataclasses import dataclass
from enum import Enum

from app.config import settings


class VehicleType(str, Enum):
    MOTO = "moto"
    AUTO = "auto"


@dataclass
class OrderEvaluation:
    fare: float
    distance_km: float
    time_minutes: float
    vehicle: VehicleType

    @property
    def gas_cost_per_km(self) -> float:
        return settings.gas_cost_per_km_moto if self.vehicle == VehicleType.MOTO else settings.gas_cost_per_km_auto

    @property
    def score(self) -> float:
        gas_cost = self.distance_km * self.gas_cost_per_km
        time_cost = self.time_minutes * settings.time_cost_per_minute
        return self.fare - gas_cost - time_cost

    @property
    def should_accept(self) -> bool:
        return self.score > 0
