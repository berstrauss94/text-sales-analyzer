# -*- coding: utf-8 -*-
"""
rate_limiter.py — Limitador de tasa en memoria (por proceso), sin dependencias
externas ni base de datos.

POR QUE
-------
Endpoints sensibles (login, analisis que llama a Gemini y cuesta, chat con IA)
no tenian ningun limite. Un script o abuso podia martillarlos y disparar costo
de IA, saturar la base o intentar fuerza bruta en el login. Este limitador cierra
esa brecha con una ventana deslizante simple.

DISENO
------
- Ventana deslizante en memoria: por clave (p. ej. "login:<ip>") se guardan los
  timestamps de los ultimos hits; se descartan los que quedaron fuera de la
  ventana; si superan el maximo, se rechaza.
- En memoria por PROCESO. Con varios workers gunicorn el limite es por worker
  (aprox. multiplicado por N workers); es una defensa de robustez, no un control
  exacto multi-proceso. Para eso haria falta un store compartido (Redis), que se
  puede sumar despues sin cambiar la interfaz.
- Thread-safe con un lock. Limpieza perezosa de claves viejas para no crecer.
- Cero dependencias, cero I/O: nunca bloquea ni rompe el request.
"""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
# clave -> lista de timestamps (float, epoch seconds) de los hits recientes.
_hits: dict[str, list[float]] = {}
# Para limpiar claves inactivas de tanto en tanto.
_last_cleanup = 0.0
_CLEANUP_EVERY = 300.0  # segundos


def _cleanup(now: float, max_window: float = 3600.0) -> None:
    """Elimina claves cuyo hit mas reciente es mas viejo que max_window."""
    global _last_cleanup
    if now - _last_cleanup < _CLEANUP_EVERY:
        return
    _last_cleanup = now
    muertas = [k for k, ts in _hits.items() if not ts or (now - ts[-1]) > max_window]
    for k in muertas:
        _hits.pop(k, None)


def check(key: str, limit: int, window_seconds: float) -> tuple[bool, int]:
    """
    Registra un hit para `key` y decide si esta permitido.

    Devuelve (permitido, retry_after_segundos):
      - permitido=True si en la ventana hay <= limit hits (contando este).
      - permitido=False si se supero; retry_after estima cuando liberar.

    Best-effort: ante cualquier error interno, permite (fail-open) para no
    romper el uso legitimo por un bug del limitador.
    """
    try:
        now = time.time()
        with _lock:
            _cleanup(now)
            arr = _hits.get(key)
            if arr is None:
                arr = []
                _hits[key] = arr
            # Descartar hits fuera de la ventana.
            corte = now - window_seconds
            # arr esta ordenado ascendente; recortar por el frente.
            i = 0
            for t in arr:
                if t >= corte:
                    break
                i += 1
            if i:
                del arr[:i]
            if len(arr) >= limit:
                # Rechazado. retry_after = cuanto falta para que el hit mas viejo
                # salga de la ventana.
                retry = int(max(1, (arr[0] + window_seconds) - now))
                return False, retry
            arr.append(now)
            return True, 0
    except Exception:
        return True, 0


def reset(key: str | None = None) -> None:
    """Limpia el estado (todo, o una sola clave). Util para tests."""
    with _lock:
        if key is None:
            _hits.clear()
        else:
            _hits.pop(key, None)
