"""Sesiones aisladas por usuario (ej. telegram chat_id).

Cada sesion guarda su propio historial + estado de autenticacion,
para que Juan y Maria nunca mezclen informacion financiera.
"""

import time
from threading import Lock


SESSION_TIMEOUT_SECONDS = 30 * 60  # 30 min sin actividad -> expira
MAX_HISTORY_ITEMS = 60  # recorta historial para no explotar tokens
MAX_AUTH_ATTEMPTS = 3


_sessions: dict[str, dict] = {}
_lock = Lock()


def _new_session() -> dict:
    return {
        "history": [],
        "customer_id": None,
        "document": None,
        "authenticated": False,
        "pending_customer": None,
        "auth_attempts": 0,
        "pending_agreement": None,
        "last_agreement": None,
        "last_active": time.time(),
    }


def get_session(session_id: str) -> dict:
    """Devuelve la sesion para session_id, creandola o expirandola si toca."""
    sid = str(session_id)
    now = time.time()
    with _lock:
        sess = _sessions.get(sid)
        if sess is None:
            sess = _new_session()
            _sessions[sid] = sess
            return sess
        if now - sess.get("last_active", 0) > SESSION_TIMEOUT_SECONDS:
            sess = _new_session()
            _sessions[sid] = sess
            return sess
        sess["last_active"] = now
        return sess


def touch(session: dict) -> None:
    session["last_active"] = time.time()
    # Recorta historial por la cola (conserva lo mas reciente).
    history = session.get("history", [])
    if len(history) > MAX_HISTORY_ITEMS:
        session["history"] = history[-MAX_HISTORY_ITEMS:]


def reset_session(session_id: str) -> dict:
    """Limpia historial + autenticacion (ej. /start, /salir, cambio de persona)."""
    sid = str(session_id)
    with _lock:
        sess = _new_session()
        _sessions[sid] = sess
        return sess
