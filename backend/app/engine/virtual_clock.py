"""Tiempo simulado del mundo.

Hay dos relojes aqui y hacen cosas distintas:

- `WorldClock` (el que importa hoy): un reloj GLOBAL que arranca con el
  proceso y nunca se detiene, como el mundo real. No depende de que alguien
  le de "Start Shift": cuando un repartidor entra a un turno, simplemente se
  engancha a la hora que el mundo ya traia. Avanza `acceleration` veces mas
  rapido que la vida real (con el default de 120, un minuto real = dos horas
  simuladas, o sea un dia completo cada 12 minutos reales).

- `VirtualClock`: el modelo anterior, de turno con duracion fija que arranca
  y termina. Se conserva porque describe la semantica de las columnas
  `start_hour` / `shift_duration_minutes` / `real_duration_minutes` de
  `simulation_runs`, y sirve si alguna vez se quiere un turno cerrado y
  reproducible (p.ej. correr dos agentes sobre EL MISMO tramo de tiempo en
  un test). La simulacion en vivo ya no lo usa.
"""

import time
from datetime import datetime, timedelta

from app.config import settings


class WorldClock:
    """Reloj del mundo: siempre corriendo, acelerado, compartido por todos.

    El ancla es el instante real en que arranco el proceso, mapeado a la hora
    real de ese momento: si el servidor prende a las 14:37, el mundo simulado
    tambien empieza a las 14:37 y de ahi se acelera. Asi las horas del log
    en vivo arrancan en algo plausible en vez de en una fecha inventada.

    Para medir el paso del tiempo usa `time.monotonic()` (inmune a que el
    sistema ajuste su reloj), no `datetime.now()`.
    """

    def __init__(self, acceleration: float | None = None, epoch: datetime | None = None):
        self.acceleration = acceleration if acceleration is not None else settings.time_acceleration
        self._epoch = epoch or datetime.now()
        self._monotonic_start = time.monotonic()

    def real_elapsed_seconds(self) -> float:
        return time.monotonic() - self._monotonic_start

    def sim_elapsed_seconds(self) -> float:
        """Segundos simulados desde que arranco el proceso."""
        return self.real_elapsed_seconds() * self.acceleration

    def sim_elapsed_minutes(self) -> float:
        return self.sim_elapsed_seconds() / 60

    def now(self) -> datetime:
        """Fecha y hora simuladas (naive, en la zona local del servidor)."""
        return self._epoch + timedelta(seconds=self.sim_elapsed_seconds())

    def virtual_hour(self) -> float:
        """Hora del dia simulada en formato 24h decimal, p.ej. 18.5 = 18:30."""
        now = self.now()
        return now.hour + now.minute / 60 + now.second / 3600

    def virtual_minute(self) -> float:
        """Minuto dentro de la hora simulada (0-60), para mostrar en la UI."""
        now = self.now()
        return now.minute + now.second / 60

    def iso_timestamp(self) -> str:
        """Timestamp simulado para el log en vivo.

        A proposito SIN zona horaria ni sufijo "Z": el frontend hace
        `new Date(iso).toLocaleTimeString(...)`, y JavaScript interpreta un
        ISO sin offset como hora LOCAL, o sea que muestra exactamente esta
        hora simulada. Si mandaramos "...Z" el navegador la convertiria a su
        zona y el log mostraria una hora que no es la del mundo simulado.
        """
        return self.now().isoformat(timespec="milliseconds")

    def is_finished(self) -> bool:
        """El mundo no se acaba; un turno termina cuando el usuario lo termina."""
        return False


# Instancia global: el mundo empieza a correr al importar la app y sigue
# corriendo aunque no haya ningun turno activo.
world_clock = WorldClock()


class VirtualClock:
    """Turno de duracion fija: comprime `shift_duration_minutes` simulados en
    `real_duration_minutes` reales. Ver nota del modulo sobre cuando usar
    este y cuando `WorldClock`.

    Con `loop=True` el reloj no se congela al llegar al 100% del turno, sigue
    avanzando y da la vuelta al llegar a medianoche.
    """

    def __init__(
        self,
        real_duration_minutes: float,
        shift_duration_minutes: int = 480,
        start_hour: float = 11.0,
        loop: bool = False,
    ):
        self.real_duration_seconds = real_duration_minutes * 60
        self.shift_duration_minutes = shift_duration_minutes
        self.start_hour = start_hour
        self.loop = loop
        self._start_time: float | None = None

    def start(self) -> None:
        self._start_time = time.monotonic()

    def elapsed_ratio(self) -> float:
        if self._start_time is None:
            return 0.0
        elapsed = time.monotonic() - self._start_time
        ratio = elapsed / self.real_duration_seconds
        return ratio if self.loop else min(ratio, 1.0)

    def virtual_minute(self) -> float:
        """Minuto del turno simulado (0 a shift_duration_minutes, o mas alla si loop=True)."""
        return self.elapsed_ratio() * self.shift_duration_minutes

    def virtual_hour(self) -> float:
        """Hora del dia en formato 24h decimal, p.ej. 18.5 = 18:30."""
        return (self.start_hour + self.virtual_minute() / 60) % 24

    def is_finished(self) -> bool:
        if self.loop:
            return False
        return self.elapsed_ratio() >= 1.0
