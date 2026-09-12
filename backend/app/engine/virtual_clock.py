import time


class VirtualClock:
    """Condensa un turno de 8 horas (480 min) en `real_duration_minutes` minutos reales."""

    # 11:00 por defecto: fuera de toda ventana de trafico pico (ver traffic_rules.py),
    # para que el turno no arranque ya dentro de un Modo Dios sin que el usuario lo pida.
    def __init__(self, real_duration_minutes: float, shift_duration_minutes: int = 480, start_hour: float = 11.0):
        self.real_duration_seconds = real_duration_minutes * 60
        self.shift_duration_minutes = shift_duration_minutes
        self.start_hour = start_hour
        self._start_time: float | None = None

    def start(self) -> None:
        self._start_time = time.monotonic()

    def elapsed_ratio(self) -> float:
        if self._start_time is None:
            return 0.0
        elapsed = time.monotonic() - self._start_time
        return min(elapsed / self.real_duration_seconds, 1.0)

    def virtual_minute(self) -> float:
        """Minuto del turno simulado (0 a shift_duration_minutes)."""
        return self.elapsed_ratio() * self.shift_duration_minutes

    def virtual_hour(self) -> float:
        """Hora del dia en formato 24h decimal, p.ej. 18.5 = 18:30."""
        return (self.start_hour + self.virtual_minute() / 60) % 24

    def is_finished(self) -> bool:
        return self.elapsed_ratio() >= 1.0
