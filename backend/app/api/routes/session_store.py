"""Donde vive el estado de un turno en curso.

El problema: `uvicorn --workers N` corre N procesos independientes. Con el
estado en un dict de modulo, el turno que arranco en el worker A no existe
para el worker B, y como el frontend sondea `/simulation/state` cada 2s sin
afinidad de proceso, la mitad de los polls contestaria 404. Un reinicio
tambien perdia el turno.

La solucion no puede ser "guardar la sesion entera": una sesion carga el
grafo de OSMnx (decenas de miles de nodos) y los objetos de los agentes, que
no son serializables ni tiene sentido mandar a Redis en cada request. Por eso
el estado se parte en dos:

- `SessionState` (session_state.py): todo lo serializable — ordenes
  pendientes, entregas en curso, contadores, eventos, cierre de calle. Esto
  es lo que viaja a Redis.
- el runtime (grafo + agentes): se reconstruye en cada worker a partir del
  estado, apoyandose en que `engine.graph_loader.load_graph()` ya cachea el
  grafo por proceso.

Backends:
- `InMemorySessionStore` (default, cero configuracion): mismo comportamiento
  de siempre, ideal para desarrollo local y para la demo en una sola maquina.
- `RedisSessionStore`: se activa solo si hay `REDIS_URL` en el entorno.

`get_session_store()` elige uno u otro. Si `REDIS_URL` esta puesto pero Redis
no responde, se cae a memoria y lo avisa por log en vez de tumbar el arranque
— a media demo es mejor un backend degradado que un servidor que no prende.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from app.api.routes.session_state import SessionState
from app.config import settings

logger = logging.getLogger(__name__)

# Prefijo de las llaves en Redis y cuanto viven sin tocarse. Un turno
# abandonado no deberia quedarse para siempre ocupando memoria.
_KEY_PREFIX = "lynx:shift:"
_TTL_SECONDS = 60 * 60 * 12


class SessionStore(Protocol):
    def get(self, run_id: str) -> SessionState | None: ...
    def save(self, state: SessionState) -> None: ...
    def delete(self, run_id: str) -> None: ...
    def run_ids(self) -> list[str]: ...


class InMemorySessionStore:
    """Un dict por proceso. Sirve para un solo worker."""

    def __init__(self) -> None:
        self._states: dict[str, SessionState] = {}

    def get(self, run_id: str) -> SessionState | None:
        return self._states.get(run_id)

    def save(self, state: SessionState) -> None:
        self._states[state.run_id] = state

    def delete(self, run_id: str) -> None:
        self._states.pop(run_id, None)

    def run_ids(self) -> list[str]:
        return list(self._states)


class RedisSessionStore:
    """Estado compartido entre workers, serializado como JSON.

    `save()` se llama al final de cada request que toca el turno, asi que el
    siguiente poll lo ve aunque caiga en otro worker.
    """

    def __init__(self, client) -> None:
        self._client = client

    @staticmethod
    def _key(run_id: str) -> str:
        return f"{_KEY_PREFIX}{run_id}"

    def get(self, run_id: str) -> SessionState | None:
        raw = self._client.get(self._key(run_id))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return SessionState.from_dict(json.loads(raw))

    def save(self, state: SessionState) -> None:
        self._client.set(self._key(state.run_id), json.dumps(state.to_dict()), ex=_TTL_SECONDS)

    def delete(self, run_id: str) -> None:
        self._client.delete(self._key(run_id))

    def run_ids(self) -> list[str]:
        keys = self._client.keys(f"{_KEY_PREFIX}*")
        out = []
        for key in keys:
            if isinstance(key, bytes):
                key = key.decode("utf-8")
            out.append(key[len(_KEY_PREFIX):])
        return out


_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    global _store
    if _store is not None:
        return _store

    if not settings.redis_url:
        _store = InMemorySessionStore()
        return _store

    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url)
        client.ping()
        _store = RedisSessionStore(client)
        logger.info("Turnos compartidos via Redis (%s)", settings.redis_url)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo cae a memoria a proposito
        logger.warning("REDIS_URL configurado pero Redis no responde (%s); usando estado en memoria", exc)
        _store = InMemorySessionStore()

    return _store


def reset_session_store(store: SessionStore | None = None) -> None:
    """Para los tests: fuerza un backend concreto (o vuelve a elegir)."""
    global _store
    _store = store
