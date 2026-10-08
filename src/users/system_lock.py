# -*- coding: utf-8 -*-
"""
Interruptor de bloqueo del sistema (control del superadmin Berna.Strauss).

Cuando el sistema esta "bloqueado", ningun usuario (comun o administrador)
puede ingresar, SALVO Berna.Strauss. Esto sirve como mecanismo de corte por
falta de pago al administrador de la plataforma.

PERSISTENCIA (dos capas)
------------------------
1. PostgreSQL (produccion, Railway): es la fuente de verdad. Sobrevive a los
   redeploys (el disco de Railway es efimero, un JSON se borraria). Lo maneja
   system_lock_pg.py, con el mismo patron que business_config.py.
2. JSON local (desarrollo, sin base): config/system_lock.json. Solo se usa como
   fallback cuando PostgreSQL NO esta disponible, para poder probar en local.

Es best-effort y fail-open: si no se puede leer el estado por ningun medio, se
asume que el sistema NO esta bloqueado, para no dejar a todos afuera por un
error de infraestructura.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

# El superadmin es el unico que puede activar/desactivar el bloqueo y el unico
# que puede ingresar mientras el sistema esta bloqueado.
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


def _write_raw(locked: bool, updated_by: str) -> bool:
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        payload = {
            "locked": bool(locked),
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
def is_locked() -> bool:
    """True si el sistema esta bloqueado por falta de pago."""
    if _pg_available():
        try:
            from src.users import system_lock_pg
            return bool(system_lock_pg.is_locked())
        except Exception:
            pass
    return bool(_read_raw().get("locked", False))


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
        "updated_at": data.get("updated_at"),
        "updated_by": data.get("updated_by"),
    }


def set_locked(locked: bool, updated_by: str) -> bool:
    """
    Activa o desactiva el bloqueo del sistema. Devuelve True si se guardo bien.
    Solo deberia llamarse tras validar que updated_by es el superadmin.

    En produccion escribe en PostgreSQL (fuente de verdad). En local, cuando no
    hay base, escribe el JSON de fallback.
    """
    if _pg_available():
        try:
            from src.users import system_lock_pg
            if system_lock_pg.set_locked(locked, updated_by=updated_by):
                return True
        except Exception:
            pass
    return _write_raw(locked, updated_by)
