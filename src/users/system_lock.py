# -*- coding: utf-8 -*-
"""
Interruptor de bloqueo del sistema (control del superadmin Berna.Strauss).

Cuando el bloqueo esta activo, impide el ingreso. Soporta dos modos:
  - "general":   bloquea a TODOS los usuarios, SALVO Berna.Strauss.
  - "selective": bloquea SOLO a los usuarios de la lista blocked_users.
Sirve como mecanismo de corte por falta de pago al administrador.

PERSISTENCIA (dos capas)
------------------------
1. PostgreSQL (produccion, Railway): es la fuente de verdad. Sobrevive a los
   redeploys (el disco de Railway es efimero, un JSON se borraria). Lo maneja
   system_lock_pg.py, con el mismo patron que business_config.py.
2. JSON local (desarrollo, sin base): config/system_lock.json. Solo se usa como
   fallback cuando PostgreSQL NO esta disponible, para poder probar en local.

Es best-effort y fail-open: si no se puede leer el estado por ningun medio, se
asume que NO hay bloqueo, para no dejar a nadie afuera por un error de
infraestructura.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

# El superadmin es el unico que puede activar/desactivar el bloqueo y el unico
# que NUNCA queda bloqueado (ni en modo general ni selectivo).
SUPERADMIN_USER = "Berna.Strauss"

# config/system_lock.json  (relativo a la raiz del proyecto)
_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
)
_LOCK_FILE = os.path.join(_CONFIG_DIR, "system_lock.json")


# ───────────────────────────── PostgreSQL ──────────────────────────────
def _pg_available() -> bool:
    try:
        from src.users import system_lock_pg
        return bool(system_lock_pg.is_available())
    except Exception:
        return False


# ──────────────────────────── JSON local ───────────────────────────────
def _read_raw() -> dict:
    """Lee el JSON de estado local. Devuelve {} si no existe o no se puede leer."""
    try:
        with open(_LOCK_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return {}


def _norm_users(raw) -> list:
    if isinstance(raw, list):
        return [str(u) for u in raw if str(u).strip()]
    return []


def _write_raw(locked: bool, mode: str, blocked_users: list, updated_by: str) -> bool:
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        payload = {
            "locked": bool(locked),
            "mode": "selective" if mode == "selective" else "general",
            "blocked_users": _norm_users(blocked_users),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": updated_by,
        }
        tmp = _LOCK_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, _LOCK_FILE)
        return True
    except Exception:
        return False


# ─────────────────────────── API publica ───────────────────────────────
def get_state() -> dict:
    """Estado completo del bloqueo (para el panel del superadmin)."""
    if _pg_available():
        try:
            from src.users import system_lock_pg
            return system_lock_pg.get_state()
        except Exception:
            pass
    data = _read_raw()
    return {
        "locked": bool(data.get("locked", False)),
        "mode": "selective" if data.get("mode") == "selective" else "general",
        "blocked_users": _norm_users(data.get("blocked_users", [])),
        "updated_at": data.get("updated_at"),
        "updated_by": data.get("updated_by"),
    }


def is_locked() -> bool:
    """True si el bloqueo esta activo (en cualquier modo)."""
    return bool(get_state().get("locked", False))


def is_user_blocked(username: str) -> bool:
    """
    True si ESTE usuario tiene el ingreso bloqueado AHORA.

    Reglas:
      - El superadmin (Berna.Strauss) NUNCA esta bloqueado.
      - Si el bloqueo no esta activo -> nadie bloqueado.
      - Modo "general"   -> todos los demas bloqueados.
      - Modo "selective" -> solo los de blocked_users.
    """
    if not username or username == SUPERADMIN_USER:
        return False
    st = get_state()
    if not st.get("locked"):
        return False
    if st.get("mode") == "selective":
        return username in set(st.get("blocked_users", []))
    return True  # general


def set_state(locked: bool, mode: str, blocked_users=None, updated_by: str = "") -> bool:
    """
    Guarda el estado completo del bloqueo. Solo deberia llamarse tras validar
    que updated_by es el superadmin. En produccion escribe en PostgreSQL; en
    local (sin base) escribe el JSON de fallback.
    """
    users = _norm_users(blocked_users or [])
    mode = "selective" if mode == "selective" else "general"
    if _pg_available():
        try:
            from src.users import system_lock_pg
            if system_lock_pg.set_state(locked, mode, users, updated_by=updated_by):
                return True
        except Exception:
            pass
    return _write_raw(locked, mode, users, updated_by)


def set_locked(locked: bool, updated_by: str) -> bool:
    """Compat: activa/desactiva en modo general (sin tocar la lista)."""
    return set_state(locked, "general", [], updated_by=updated_by)
