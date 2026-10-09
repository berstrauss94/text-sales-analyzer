# -*- coding: utf-8 -*-
"""
kanban_pg.py — Tablero Kanban del pipeline inmobiliario, persistido en PostgreSQL.

QUE ES
------
Extiende el CRM/Lead actual (lead_store_pg.py) a un tablero Kanban multi-lead,
conservando los datos existentes mediante una migracion NO destructiva. Cada
tarjeta = un lead que avanza por 7 etapas (NEW -> ... -> CLOSED_WON/LOST), con
transiciones validadas, control anti doble venta sobre un inventario opcional de
unidades, y sincronizacion del estado de vuelta al CRM (lead_fichas) para no
perder la vista actual del vendedor.

COMPATIBILIDAD CON EL STACK
---------------------------
- Mismo patron que lead_store_pg.py / system_lock_pg.py: funciones de modulo
  _conn/_release/is_available, _ensure_table idempotente con flag _tables_ready,
  conexiones del pool de history_manager (autocommit=False), commit explicito y
  liberacion en finally. Best-effort: si PG no esta, degrada sin romper.
- Multi-tenant: toda tarjeta pertenece a un tenant_id (igual que lead_fichas).

MAPEOS DE ESTADO (CRM 4 estados  <->  Kanban 7 etapas)
------------------------------------------------------
El CRM (lead_fichas.lead_estado) solo tiene 4 estados; el Kanban tiene 7. La
sincronia es necesariamente con perdida de granularidad en el sentido Kanban->CRM
(5 etapas intermedias colapsan en 'seguimiento'). En el sentido CRM->Kanban
(migracion), 'seguimiento' -> CONTACTED por defecto (el vendedor reubica luego).
"""
from __future__ import annotations

import logging
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_tables_ready = False


# =====================================================================
# 1. ETAPAS, TRANSICIONES Y PROBABILIDADES
# =====================================================================
class KanbanStage(Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    PROPERTY_TOUR = "PROPERTY_TOUR"
    RESERVATION = "RESERVATION"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


VALID_TRANSITIONS = {
    KanbanStage.NEW: [KanbanStage.CONTACTED, KanbanStage.CLOSED_LOST],
    KanbanStage.CONTACTED: [KanbanStage.QUALIFIED, KanbanStage.CLOSED_LOST],
    KanbanStage.QUALIFIED: [KanbanStage.PROPERTY_TOUR, KanbanStage.CLOSED_LOST],
    KanbanStage.PROPERTY_TOUR: [KanbanStage.RESERVATION, KanbanStage.CLOSED_LOST],
    KanbanStage.RESERVATION: [KanbanStage.CLOSED_WON, KanbanStage.CLOSED_LOST],
    KanbanStage.CLOSED_WON: [],
    KanbanStage.CLOSED_LOST: [],
}

STAGE_PROBABILITIES = {
    KanbanStage.NEW: 0.10,
    KanbanStage.CONTACTED: 0.30,
    KanbanStage.QUALIFIED: 0.50,
    KanbanStage.PROPERTY_TOUR: 0.70,
    KanbanStage.RESERVATION: 0.95,
    KanbanStage.CLOSED_WON: 1.00,
    KanbanStage.CLOSED_LOST: 0.00,
}

# CRM (4) -> Kanban (7). 'seguimiento' aterriza en CONTACTED (conservador).
CRM_TO_KANBAN = {
    "nuevo": KanbanStage.NEW,
    "seguimiento": KanbanStage.CONTACTED,
    "cerrado": KanbanStage.CLOSED_WON,
    "perdido": KanbanStage.CLOSED_LOST,
}

# Kanban (7) -> CRM (4). Las 5 etapas de trabajo colapsan en 'seguimiento'.
KANBAN_TO_CRM = {
    KanbanStage.NEW: "nuevo",
    KanbanStage.CONTACTED: "seguimiento",
    KanbanStage.QUALIFIED: "seguimiento",
    KanbanStage.PROPERTY_TOUR: "seguimiento",
    KanbanStage.RESERVATION: "seguimiento",
    KanbanStage.CLOSED_WON: "cerrado",
    KanbanStage.CLOSED_LOST: "perdido",
}

# Para la sincronia CRM->Kanban (bidireccional): que etapas del Kanban
# corresponden a cada estado del CRM. Clave para NO degradar el progreso:
# si el CRM dice 'seguimiento' y la tarjeta ya esta en CUALQUIERA de las etapas
# de trabajo, se respeta la etapa (mas especifica) del Kanban.
CRM_ESTADO_A_ETAPAS = {
    "nuevo": {KanbanStage.NEW},
    "seguimiento": {KanbanStage.CONTACTED, KanbanStage.QUALIFIED,
                    KanbanStage.PROPERTY_TOUR, KanbanStage.RESERVATION},
    "cerrado": {KanbanStage.CLOSED_WON},
    "perdido": {KanbanStage.CLOSED_LOST},
}
# Etapa por defecto al traer un estado del CRM que no coincide con la actual.
CRM_ESTADO_DEFAULT_ETAPA = {
    "nuevo": KanbanStage.NEW,
    "seguimiento": KanbanStage.CONTACTED,
    "cerrado": KanbanStage.CLOSED_WON,
    "perdido": KanbanStage.CLOSED_LOST,
}


# =====================================================================
# 2. CONEXION (mismo patron que lead_store_pg / system_lock_pg)
# =====================================================================
def _conn():
    try:
        from src.users.history_manager import _get_pg_conn
        return _get_pg_conn()
    except Exception:
        return None


def _release(conn, close: bool = False) -> None:
    try:
        from src.users.history_manager import _return_pg_conn
        _return_pg_conn(conn, close=close)
    except Exception:
        pass


def is_available() -> bool:
    try:
        from src.users.history_manager import _is_pg_available
        return bool(_is_pg_available())
    except Exception:
        return False


def _ensure_tables_cur(cur) -> None:
    """
    Crea las tablas del Kanban usando un cursor ya abierto (NO hace commit:
    el commit lo maneja el llamador, para que viva en su misma transaccion).
    """
    # Tarjetas del tablero: una por lead. PK card_id. Aislada por tenant.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kanban_cards (
            card_id         TEXT        PRIMARY KEY,
            tenant_id       TEXT        NOT NULL DEFAULT '__legacy__',
            owner_username  TEXT        NOT NULL DEFAULT '',
            customer_name   TEXT        NOT NULL DEFAULT '',
            contacto        TEXT        NOT NULL DEFAULT '',
            operacion       TEXT        NOT NULL DEFAULT '',
            budget_range    TEXT        NOT NULL DEFAULT '',
            interest_zone   TEXT        NOT NULL DEFAULT '',
            notas           TEXT        NOT NULL DEFAULT '',
            tags            TEXT        NOT NULL DEFAULT '',
            crm_text        TEXT        NOT NULL DEFAULT '',
            property_id     TEXT,
            property_value  DOUBLE PRECISION NOT NULL DEFAULT 0,
            current_stage   TEXT        NOT NULL DEFAULT 'NEW',
            loss_reason_code TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_kanban_tenant_stage "
        "ON kanban_cards (tenant_id, current_stage)"
    )
    # Historial inmutable de movimientos (para metricas de velocidad).
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS internal_pipeline_history (
            history_id   TEXT        PRIMARY KEY,
            card_id      TEXT        NOT NULL,
            tenant_id    TEXT        NOT NULL DEFAULT '__legacy__',
            moved_by     TEXT        NOT NULL DEFAULT '',
            from_stage   TEXT        NOT NULL,
            to_stage     TEXT        NOT NULL,
            loss_reason  TEXT,
            updated_at   TIMESTAMPTZ NOT NULL
        )
        """
    )
    # Inventario de propiedades (opcional). Anti doble venta via UPDATE atomico.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS units (
            unit_id     TEXT        PRIMARY KEY,
            tenant_id   TEXT        NOT NULL DEFAULT '__legacy__',
            name        TEXT        NOT NULL DEFAULT '',
            status      TEXT        NOT NULL DEFAULT 'AVAILABLE',
            price       DOUBLE PRECISION NOT NULL DEFAULT 0,
            lock_until  TIMESTAMPTZ,
            updated_at  TIMESTAMPTZ
        )
        """
    )
    # Marca de migracion (para saber si ya se corrio y no duplicar).
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kanban_migration_flag (
            tenant_id   TEXT        PRIMARY KEY,
            migrated_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    # Configuracion del tablero por tenant (visibilidad global, etc.).
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kanban_settings (
            tenant_id          TEXT    PRIMARY KEY,
            global_visibility  BOOLEAN NOT NULL DEFAULT FALSE,
            updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _ensure_tables(conn) -> None:
    """Crea las tablas una sola vez por proceso, con commit propio."""
    global _tables_ready
    if _tables_ready:
        return
    with conn.cursor() as cur:
        _ensure_tables_cur(cur)
    conn.commit()
    _tables_ready = True


# =====================================================================
# 3. MOTOR DE LOGICA DEL TABLERO
# =====================================================================
class KiroKanbanEngine:
    """Motor del Kanban: validaciones de estado, atomicidad y sincronia con el CRM."""

    def calculate_stage_header(self, stage: KanbanStage,
                               cards_in_stage: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Totales de una columna: valor bruto y ponderado por probabilidad."""
        probability = STAGE_PROBABILITIES[stage]
        total_raw_revenue = 0.0
        for card in cards_in_stage:
            try:
                val = card.get("property_value")
                total_raw_revenue += float(val) if val is not None else 0.0
            except (ValueError, TypeError):
                continue
        return {
            "stage": stage.value,
            "card_count": len(cards_in_stage),
            "total_raw_revenue": total_raw_revenue,
            "planned_revenue": total_raw_revenue * probability,
            "probability_percentage": probability * 100,
        }

    def move_card(self, card_id: str, target_stage_val: str,
                  moved_by: str, tenant_id: str = "__legacy__",
                  card_patch: Optional[Dict[str, Any]] = None,
                  is_admin: bool = False) -> Dict[str, Any]:
        """
        Mueve una tarjeta a target_stage leyendo su estado ACTUAL de la base
        (no se confia en el frontend). Valida la transicion, aplica compuertas de
        datos, maneja inventario (reserva/liberacion) y sincroniza lead_fichas.
        TODO en una sola transaccion: o se hace todo o nada.
        """
        if not is_available():
            return {"success": False, "error": "Persistencia no disponible."}

        try:
            target_stage = KanbanStage(target_stage_val)
        except ValueError:
            return {"success": False, "error": "Etapa destino invalida."}

        # Garantizar que la tabla lead_fichas del CRM exista ANTES de la
        # transaccion (puede no existir si nadie uso el CRM todavia). Usa la
        # creacion oficial del modulo del CRM, en su propia transaccion. Si falla,
        # no corta: la sincronia es best-effort.
        try:
            from src.users import lead_store_pg
            _lf_conn = _conn()
            if _lf_conn is not None:
                try:
                    lead_store_pg._ensure_table(_lf_conn)
                finally:
                    _release(_lf_conn)
        except Exception:
            pass

        conn = _conn()
        if conn is None:
            return {"success": False, "error": "No hay conexion a la base."}

        should_close = False
        try:
            _ensure_tables(conn)
            with conn:  # COMMIT al salir OK, ROLLBACK ante cualquier excepcion
                with conn.cursor() as cur:
                    # 1. Leer el estado ACTUAL real de la tarjeta (fuente de verdad).
                    cur.execute(
                        "SELECT current_stage, property_id, owner_username, "
                        "budget_range, interest_zone "
                        "FROM kanban_cards WHERE card_id = %s AND tenant_id = %s",
                        (card_id, tenant_id or "__legacy__"),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise _KanbanError("La tarjeta no existe para este tenant.")

                    current_stage = KanbanStage(row[0])
                    property_id = row[1]
                    owner_username = row[2]
                    budget_range = (card_patch or {}).get("budget_range", row[3])
                    interest_zone = (card_patch or {}).get("interest_zone", row[4])
                    loss_reason = (card_patch or {}).get("loss_reason_code")

                    # 1.b Permisos (punto 2): un vendedor solo mueve SUS tarjetas.
                    #     El admin puede mover cualquiera.
                    if not is_admin and owner_username and moved_by != owner_username:
                        raise _KanbanError("No podes mover una tarjeta de otro vendedor.")

                    # 2. Validar la transicion contra la maquina de estados.
                    if target_stage not in VALID_TRANSITIONS[current_stage]:
                        raise _KanbanError(
                            f"Transicion invalida: {current_stage.value} -> {target_stage.value}")

                    # 3. Compuertas de datos obligatorios.
                    if target_stage == KanbanStage.PROPERTY_TOUR:
                        if not budget_range or not interest_zone:
                            raise _KanbanError(
                                "Falta 'Rango de Presupuesto' y/o 'Zona de Interes' para avanzar a Visita.")
                    if target_stage == KanbanStage.CLOSED_LOST and not loss_reason:
                        raise _KanbanError(
                            "Es obligatorio el motivo de perdida (loss_reason_code) para archivar.")

                    # 4. Inventario: reserva atomica o liberacion.
                    if target_stage == KanbanStage.RESERVATION:
                        if not property_id:
                            raise _KanbanError("La tarjeta no tiene property_id para reservar.")
                        cur.execute(
                            """
                            UPDATE units SET status = 'TEMPORARILY_LOCKED',
                                lock_until = %s, updated_at = %s
                            WHERE unit_id = %s AND tenant_id = %s AND status = 'AVAILABLE'
                            """,
                            (datetime.now(timezone.utc) + timedelta(hours=48),
                             datetime.now(timezone.utc), property_id,
                             tenant_id or "__legacy__"),
                        )
                        if cur.rowcount == 0:
                            raise _KanbanError(
                                "La propiedad ya no esta disponible o fue reservada en paralelo.")
                    elif target_stage == KanbanStage.CLOSED_LOST and property_id:
                        cur.execute(
                            "UPDATE units SET status = 'AVAILABLE', lock_until = NULL "
                            "WHERE unit_id = %s AND tenant_id = %s",
                            (property_id, tenant_id or "__legacy__"),
                        )

                    # 5. Actualizar la tarjeta.
                    now = datetime.now(timezone.utc)
                    cur.execute(
                        """
                        UPDATE kanban_cards SET current_stage = %s, budget_range = %s,
                            interest_zone = %s, loss_reason_code = %s, updated_at = %s
                        WHERE card_id = %s AND tenant_id = %s
                        """,
                        (target_stage.value, budget_range or "", interest_zone or "",
                         loss_reason, now, card_id, tenant_id or "__legacy__"),
                    )

                    # 6. Historial inmutable del movimiento.
                    cur.execute(
                        """
                        INSERT INTO internal_pipeline_history
                            (history_id, card_id, tenant_id, moved_by,
                             from_stage, to_stage, loss_reason, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (str(uuid.uuid4()), card_id, tenant_id or "__legacy__",
                         moved_by or "", current_stage.value, target_stage.value,
                         loss_reason, now),
                    )

                    # 7. Sincronia con el CRM: reflejar el estado en lead_fichas
                    #    del vendedor dueno (mapa 7->4). Misma transaccion.
                    crm_estado = KANBAN_TO_CRM[target_stage]
                    if owner_username:
                        cur.execute(
                            "UPDATE lead_fichas SET lead_estado = %s, updated_at = now() "
                            "WHERE tenant_id = %s AND username = %s",
                            (crm_estado, tenant_id or "__legacy__", owner_username),
                        )

            # Transaccion commiteada OK.
            return {
                "success": True,
                "message": f"Tarjeta movida a {target_stage.value}.",
                "card": {
                    "card_id": card_id,
                    "current_stage": target_stage.value,
                    "probability": STAGE_PROBABILITIES[target_stage],
                    "crm_estado": KANBAN_TO_CRM[target_stage],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            }

        except _KanbanError as ke:
            # Error de negocio controlado: ROLLBACK ya ocurrio al salir del 'with'.
            return {"success": False, "error": str(ke)}
        except Exception as exc:  # noqa: BLE001
            logger.error(f"kanban move_card error: {exc}")
            should_close = True
            return {"success": False, "error": f"Fallo de persistencia: {exc}"}
        finally:
            _release(conn, close=should_close)


class _KanbanError(Exception):
    """Error de regla de negocio: fuerza ROLLBACK y se reporta como 422."""
    pass


# Instancia unica del motor y funciones de modulo que delegan en ella. Asi el
# resto del codigo (endpoints) usa kanban_pg.move_card(...) de forma uniforme,
# igual que create_card / get_board / migrate_from_lead_fichas.
_engine = KiroKanbanEngine()


def move_card(card_id: str, target_stage_val: str, moved_by: str,
              tenant_id: str = "__legacy__",
              card_patch: Optional[Dict[str, Any]] = None,
              is_admin: bool = False) -> Dict[str, Any]:
    """Funcion de modulo: delega en el motor (ver KiroKanbanEngine.move_card)."""
    return _engine.move_card(card_id, target_stage_val, moved_by,
                             tenant_id=tenant_id, card_patch=card_patch,
                             is_admin=is_admin)


def calculate_stage_header(stage: KanbanStage, cards_in_stage: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Funcion de modulo: delega en el motor."""
    return _engine.calculate_stage_header(stage, cards_in_stage)


# =====================================================================
# 4. BORRADO DE TARJETAS
# =====================================================================
def delete_card(card_id: str, tenant_id: str = "__legacy__",
                requested_by: str = "", is_admin: bool = False) -> Dict[str, Any]:
    """
    Borra una tarjeta y su historial. Si tenia una unidad reservada
    (TEMPORARILY_LOCKED), la libera (status AVAILABLE). Todo en una transaccion.
    Permisos (punto 2): un vendedor solo borra SUS tarjetas; el admin, cualquiera.
    """
    if not is_available():
        return {"success": False, "error": "Persistencia no disponible."}
    conn = _conn()
    if conn is None:
        return {"success": False, "error": "No hay conexion."}
    should_close = False
    try:
        _ensure_tables(conn)
        with conn:
            with conn.cursor() as cur:
                # Buscar la tarjeta, su propiedad vinculada y su dueno.
                cur.execute(
                    "SELECT property_id, current_stage, owner_username FROM kanban_cards "
                    "WHERE card_id = %s AND tenant_id = %s",
                    (card_id, tenant_id or "__legacy__"),
                )
                row = cur.fetchone()
                if not row:
                    # raise (no return) para que el 'with conn' haga ROLLBACK, no COMMIT.
                    raise _KanbanError("La tarjeta no existe.")
                property_id, stage, owner_username = row[0], row[1], row[2]
                # Permisos: un vendedor solo borra lo suyo.
                if not is_admin and owner_username and requested_by != owner_username:
                    raise _KanbanError("No podes borrar una tarjeta de otro vendedor.")
                # Si tenia la unidad reservada por esta tarjeta, liberarla.
                if property_id and stage == KanbanStage.RESERVATION.value:
                    cur.execute(
                        "UPDATE units SET status = 'AVAILABLE', lock_until = NULL "
                        "WHERE unit_id = %s AND tenant_id = %s",
                        (property_id, tenant_id or "__legacy__"),
                    )
                # Borrar historial de la tarjeta y la tarjeta.
                cur.execute(
                    "DELETE FROM internal_pipeline_history WHERE card_id = %s AND tenant_id = %s",
                    (card_id, tenant_id or "__legacy__"),
                )
                cur.execute(
                    "DELETE FROM kanban_cards WHERE card_id = %s AND tenant_id = %s",
                    (card_id, tenant_id or "__legacy__"),
                )
        return {"success": True, "message": "Tarjeta borrada."}
    except _KanbanError as ke:
        # Error de negocio (tarjeta inexistente): ROLLBACK ya ocurrio al salir del 'with'.
        return {"success": False, "error": str(ke)}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"kanban delete_card error: {exc}")
        should_close = True
        return {"success": False, "error": str(exc)}
    finally:
        _release(conn, close=should_close)


# =====================================================================
# 5. CREACION DE TARJETAS NUEVAS
# =====================================================================
def create_card(owner_username: str, customer_name: str, property_value: Any = 0.0,
                property_id: Optional[str] = None, tenant_id: str = "__legacy__",
                extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Crea una tarjeta nueva en NEW. Devuelve {'success', 'card_id'/'error'}."""
    try:
        pv = float(property_value)
        if pv < 0:
            pv = 0.0
    except (ValueError, TypeError):
        pv = 0.0

    if not is_available():
        return {"success": False, "error": "Persistencia no disponible."}
    conn = _conn()
    if conn is None:
        return {"success": False, "error": "No hay conexion."}
    e = extra or {}
    card_id = str(uuid.uuid4())
    should_close = False
    try:
        _ensure_tables(conn)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kanban_cards
                        (card_id, tenant_id, owner_username, customer_name, contacto,
                         operacion, budget_range, interest_zone, notas, tags, crm_text,
                         property_id, property_value, current_stage, created_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), now())
                    """,
                    (card_id, tenant_id or "__legacy__", owner_username or "",
                     str(customer_name or "").strip()[:200],
                     str(e.get("contacto", ""))[:200], str(e.get("operacion", ""))[:60],
                     str(e.get("budget_range", ""))[:100], str(e.get("interest_zone", ""))[:200],
                     str(e.get("notas", ""))[:4000], str(e.get("tags", ""))[:300],
                     str(e.get("crm_text", ""))[:8000], property_id, pv,
                     KanbanStage.NEW.value),
                )
        return {"success": True, "card_id": card_id}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"kanban create_card error: {exc}")
        should_close = True
        return {"success": False, "error": str(exc)}
    finally:
        _release(conn, close=should_close)


# =====================================================================
# CONFIGURACION DEL TABLERO (visibilidad global)
# =====================================================================
def get_global_visibility(tenant_id: str = "__legacy__") -> bool:
    """True si el admin habilito que todos vean el tablero completo del tenant."""
    if not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_tables(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT global_visibility FROM kanban_settings WHERE tenant_id = %s",
                (tenant_id or "__legacy__",),
            )
            row = cur.fetchone()
        conn.rollback()  # cerrar la transaccion de solo-lectura (no dejar idle-in-transaction)
        _release(conn)
        return bool(row[0]) if row else False
    except Exception as exc:  # noqa: BLE001
        logger.error(f"kanban get_global_visibility error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def set_global_visibility(enabled: bool, tenant_id: str = "__legacy__") -> bool:
    """Activa/desactiva la visibilidad global del tablero (solo admin). Upsert."""
    if not is_available():
        return False
    conn = _conn()
    if conn is None:
        return False
    should_close = False
    try:
        _ensure_tables(conn)
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kanban_settings (tenant_id, global_visibility, updated_at)
                    VALUES (%s, %s, now())
                    ON CONFLICT (tenant_id) DO UPDATE SET
                        global_visibility = EXCLUDED.global_visibility,
                        updated_at = now()
                    """,
                    (tenant_id or "__legacy__", bool(enabled)),
                )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"kanban set_global_visibility error: {exc}")
        should_close = True
        return False
    finally:
        _release(conn, close=should_close)


# =====================================================================
# 5. LECTURA DEL TABLERO
# =====================================================================
def get_board(tenant_id: str = "__legacy__", owner_username: Optional[str] = None,
              is_admin: bool = False) -> Dict[str, Any]:
    """Devuelve las tarjetas agrupadas por etapa (para pintar el tablero)."""
    empty = {s.value: [] for s in KanbanStage}
    if not is_available():
        return {"success": True, "columns": empty, "available": False}
    conn = _conn()
    if conn is None:
        return {"success": True, "columns": empty, "available": False}
    try:
        _ensure_tables(conn)
        # Visibilidad: un admin ve todo. Un vendedor ve solo lo suyo, SALVO que
        # el admin haya activado la visibilidad global del tenant.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT global_visibility FROM kanban_settings WHERE tenant_id = %s",
                (tenant_id or "__legacy__",),
            )
            _vrow = cur.fetchone()
            global_vis = bool(_vrow[0]) if _vrow else False
            ve_todo = bool(is_admin) or global_vis
            if ve_todo or not owner_username:
                cur.execute(
                    "SELECT card_id, customer_name, property_value, current_stage, "
                    "property_id, budget_range, interest_zone, owner_username "
                    "FROM kanban_cards WHERE tenant_id = %s ORDER BY updated_at DESC",
                    (tenant_id or "__legacy__",),
                )
            else:
                cur.execute(
                    "SELECT card_id, customer_name, property_value, current_stage, "
                    "property_id, budget_range, interest_zone, owner_username "
                    "FROM kanban_cards WHERE tenant_id = %s AND owner_username = %s "
                    "ORDER BY updated_at DESC",
                    (tenant_id or "__legacy__", owner_username),
                )
            rows = cur.fetchall()
        conn.rollback()  # cerrar la transaccion de solo-lectura (no dejar idle-in-transaction)
        _release(conn)
        cols = {s.value: [] for s in KanbanStage}
        for r in rows:
            stage = r[3] if r[3] in cols else KanbanStage.NEW.value
            cols[stage].append({
                "card_id": r[0], "customer_name": r[1] or "",
                "property_value": float(r[2] or 0), "current_stage": stage,
                "property_id": r[4], "budget_range": r[5] or "",
                "interest_zone": r[6] or "", "owner_username": r[7] or "",
            })
        return {"success": True, "columns": cols, "available": True,
                "global_visibility": global_vis}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"kanban get_board error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return {"success": True, "columns": empty, "available": False}


# =====================================================================
# 6. MIGRACION NO DESTRUCTIVA DESDE lead_fichas
# =====================================================================
def migrate_from_lead_fichas(tenant_id: str = "__legacy__", dry_run: bool = True) -> Dict[str, Any]:
    """
    Lee lead_fichas (CRM actual) y crea una tarjeta Kanban por cada ficha,
    conservando todos los datos y traduciendo el estado (CRM 4 -> Kanban 7).

    NO toca ni borra lead_fichas (queda como respaldo).
    - dry_run=True  : solo cuenta y simula, NO escribe nada. Riesgo cero.
    - dry_run=False : inserta las tarjetas (idempotente: no duplica si ya migro).

    Devuelve un resumen con cuantas fichas se migrarian/migraron y el detalle
    de estados, para poder verificar antes de ejecutar en serio.
    """
    if not is_available():
        return {"success": False, "error": "Persistencia no disponible."}
    conn = _conn()
    if conn is None:
        return {"success": False, "error": "No hay conexion."}
    should_close = False
    try:
        _ensure_tables(conn)
        resumen = {"dry_run": dry_run, "tenant_id": tenant_id or "__legacy__",
                   "fichas_encontradas": 0, "tarjetas_a_crear": 0,
                   "ya_migrado": False, "por_estado": {}, "detalle": []}

        with conn.cursor() as cur:
            # Si ya se migro este tenant, no repetir (salvo dry_run informativo).
            cur.execute(
                "SELECT migrated_at FROM kanban_migration_flag WHERE tenant_id = %s",
                (tenant_id or "__legacy__",),
            )
            if cur.fetchone():
                resumen["ya_migrado"] = True

            # Leer todas las fichas del tenant (NO se modifican).
            cur.execute(
                "SELECT username, crm_text, lead_nombre, lead_contacto, lead_operacion, "
                "lead_presupuesto, lead_zona, lead_estado, lead_notas, lead_tags "
                "FROM lead_fichas WHERE tenant_id = %s",
                (tenant_id or "__legacy__",),
            )
            fichas = cur.fetchall()
            resumen["fichas_encontradas"] = len(fichas)

            for f in fichas:
                estado_crm = (f[7] or "nuevo").strip().lower()
                stage = CRM_TO_KANBAN.get(estado_crm, KanbanStage.NEW)
                resumen["por_estado"][stage.value] = resumen["por_estado"].get(stage.value, 0) + 1
                resumen["detalle"].append({
                    "username": f[0], "lead_nombre": f[2] or "",
                    "estado_crm": estado_crm, "stage_kanban": stage.value,
                })
                resumen["tarjetas_a_crear"] += 1

                if not dry_run and not resumen["ya_migrado"]:
                    cur.execute(
                        """
                        INSERT INTO kanban_cards
                            (card_id, tenant_id, owner_username, customer_name, contacto,
                             operacion, budget_range, interest_zone, notas, tags, crm_text,
                             property_id, property_value, current_stage, created_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NULL, 0, %s, now(), now())
                        ON CONFLICT (card_id) DO NOTHING
                        """,
                        (str(uuid.uuid4()), tenant_id or "__legacy__", f[0], f[2] or "",
                         f[3] or "", f[4] or "", f[5] or "", f[6] or "", f[8] or "",
                         f[9] or "", f[1] or "", stage.value),
                    )

            if not dry_run and not resumen["ya_migrado"]:
                cur.execute(
                    "INSERT INTO kanban_migration_flag (tenant_id, migrated_at) "
                    "VALUES (%s, %s) ON CONFLICT (tenant_id) DO NOTHING",
                    (tenant_id or "__legacy__", datetime.now(timezone.utc)),
                )

        if dry_run:
            # No se escribio nada: deshacer cualquier estado transaccional abierto.
            conn.rollback()
            resumen["success"] = True
            resumen["mensaje"] = "SIMULACION: no se escribio nada en la base."
        else:
            conn.commit()
            resumen["success"] = True
            resumen["mensaje"] = ("Migracion completada." if not resumen["ya_migrado"]
                                  else "Ya estaba migrado: no se crearon tarjetas nuevas.")
        _release(conn)
        return resumen

    except Exception as exc:  # noqa: BLE001
        logger.error(f"kanban migrate error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return {"success": False, "error": str(exc)}


# =====================================================================
# 7. SINCRONIA CRM -> KANBAN (bidireccional, disparada al guardar la ficha)
# =====================================================================
def sync_from_crm_ficha(username: str, ficha: dict, tenant_id: str = "__legacy__") -> dict:
    """
    Refleja en el Kanban una ficha del CRM recien guardada (lead_store_pg).
    Se llama automaticamente desde save_ficha. Best-effort: NUNCA rompe el
    guardado del CRM (si falla, se ignora).

    Comportamiento (una tarjeta por vendedor, igual que el CRM):
      - Si el vendedor no tiene tarjeta: crea una con los datos de la ficha, en
        la etapa que corresponde al estado del CRM.
      - Si ya tiene tarjeta: actualiza SIEMPRE los datos (nombre, zona, etc.) y
        ajusta la etapa SOLO si el estado del CRM cambio de categoria. Regla
        anti-retroceso: si el CRM dice 'seguimiento' y la tarjeta ya esta en
        cualquiera de las etapas de trabajo (CONTACTED..RESERVATION), se respeta
        la etapa (mas especifica) del Kanban y NO se degrada el progreso.
    """
    if not username or not is_available():
        return {"success": False, "error": "no disponible"}
    f = ficha or {}
    estado_crm = str(f.get("lead_estado", "nuevo")).strip().lower()
    if estado_crm not in CRM_ESTADO_A_ETAPAS:
        estado_crm = "nuevo"

    conn = _conn()
    if conn is None:
        return {"success": False, "error": "sin conexion"}
    should_close = False
    try:
        _ensure_tables(conn)
        with conn:
            with conn.cursor() as cur:
                # Buscar la tarjeta del vendedor (la mas reciente si hubiera varias).
                cur.execute(
                    "SELECT card_id, current_stage FROM kanban_cards "
                    "WHERE tenant_id = %s AND owner_username = %s "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (tenant_id or "__legacy__", username),
                )
                row = cur.fetchone()

                nombre = str(f.get("lead_nombre", "") or "")[:200]
                contacto = str(f.get("lead_contacto", "") or "")[:200]
                operacion = str(f.get("lead_operacion", "") or "")[:60]
                presupuesto = str(f.get("lead_presupuesto", "") or "")[:100]
                zona = str(f.get("lead_zona", "") or "")[:200]
                notas = str(f.get("lead_notas", "") or "")[:4000]
                tags = str(f.get("lead_tags", "") or "")[:300]
                crm_text = str(f.get("crm_text", "") or "")[:8000]
                now = datetime.now(timezone.utc)

                if not row:
                    # No existe tarjeta: crearla en la etapa del estado del CRM.
                    stage = CRM_ESTADO_DEFAULT_ETAPA.get(estado_crm, KanbanStage.NEW)
                    cur.execute(
                        """
                        INSERT INTO kanban_cards
                            (card_id, tenant_id, owner_username, customer_name, contacto,
                             operacion, budget_range, interest_zone, notas, tags, crm_text,
                             property_id, property_value, current_stage, created_at, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NULL, 0, %s, %s, %s)
                        """,
                        (str(uuid.uuid4()), tenant_id or "__legacy__", username, nombre,
                         contacto, operacion, presupuesto, zona, notas, tags, crm_text,
                         stage.value, now, now),
                    )
                    return {"success": True, "action": "created", "stage": stage.value}

                # Existe: actualizar datos siempre; etapa solo si cambio de categoria.
                card_id, cur_stage_val = row[0], row[1]
                try:
                    cur_stage = KanbanStage(cur_stage_val)
                except ValueError:
                    cur_stage = KanbanStage.NEW
                # Anti-retroceso: si la etapa actual YA corresponde al estado del
                # CRM, no se toca. Si no, se lleva a la etapa por defecto del estado.
                etapas_validas = CRM_ESTADO_A_ETAPAS.get(estado_crm, {KanbanStage.NEW})
                if cur_stage in etapas_validas:
                    nueva_stage = cur_stage  # respetar progreso del Kanban
                else:
                    nueva_stage = CRM_ESTADO_DEFAULT_ETAPA.get(estado_crm, KanbanStage.NEW)

                cur.execute(
                    """
                    UPDATE kanban_cards SET customer_name = %s, contacto = %s,
                        operacion = %s, budget_range = %s, interest_zone = %s,
                        notas = %s, tags = %s, crm_text = %s, current_stage = %s,
                        updated_at = %s
                    WHERE card_id = %s AND tenant_id = %s
                    """,
                    (nombre, contacto, operacion, presupuesto, zona, notas, tags,
                     crm_text, nueva_stage.value, now, card_id, tenant_id or "__legacy__"),
                )
                return {"success": True, "action": "updated", "stage": nueva_stage.value}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"kanban sync_from_crm_ficha error: {exc}")
        should_close = True
        return {"success": False, "error": str(exc)}
    finally:
        _release(conn, close=should_close)
