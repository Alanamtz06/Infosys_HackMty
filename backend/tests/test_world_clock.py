"""Sin dependencia de red."""

import re
from datetime import datetime

from app.engine.virtual_clock import WorldClock


def test_clock_runs_without_being_started():
    """El mundo no espera un "Start Shift": ya viene corriendo."""
    clock = WorldClock(acceleration=60, epoch=datetime(2026, 1, 1, 8, 0, 0))
    assert clock.now() >= datetime(2026, 1, 1, 8, 0, 0)
    assert clock.is_finished() is False


def test_simulated_time_runs_faster_than_real_time():
    clock = WorldClock(acceleration=3600, epoch=datetime(2026, 1, 1, 8, 0, 0))
    # sin dormir: se compara el tiempo simulado contra el real transcurrido
    real = clock.real_elapsed_seconds()
    sim = clock.sim_elapsed_seconds()
    assert sim >= real * 3599  # ~3600x, con margen por el tiempo entre las dos lecturas


def test_virtual_hour_matches_epoch():
    clock = WorldClock(acceleration=1, epoch=datetime(2026, 1, 1, 18, 30, 0))
    assert 18.5 <= clock.virtual_hour() < 18.51


def test_iso_timestamp_has_no_timezone_suffix():
    """El frontend hace new Date(ts).toLocaleTimeString(): un ISO sin offset
    se interpreta como hora local y muestra la hora simulada tal cual. Con
    "Z" el navegador la convertiria a su zona y mostraria otra hora."""
    clock = WorldClock(acceleration=1, epoch=datetime(2026, 1, 1, 18, 30, 0))
    ts = clock.iso_timestamp()
    assert not ts.endswith("Z")
    assert "+" not in ts
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$", ts)
