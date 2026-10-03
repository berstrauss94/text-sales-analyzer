# -*- coding: utf-8 -*-
"""
business_config.py — Parametros financieros y de costos por empresa (tenant)
para el modulo de Inteligencia Comercial / ROI.

QUE ES
------
El sistema analiza conversaciones, pero NO conoce datos financieros reales
(cuanto vale un lote, cuantos se vendieron, margen). En vez de inventarlos, el
usuario carga PARAMETROS ESTIMADOS editables desde la interfaz, y el modulo
PROYECTA sobre ellos (LTV, ARR, ROI). Si cambian los parametros, cambian las
proyecciones. Son estimaciones honestas, no datos de ventas reales.

Parametros (todos por tenant, con defaults razonables en 0 o neutro):
  - ticket_promedio: valor promedio de un lote/operacion (moneda local).
  - margen_pct: margen de ganancia estimado sobre el ticket (0-100).
  - cierre_base_pct: tasa de cierre actual estimada SIN la herramienta (0-100).
  - cierre_mejora_pct: mejora en la tasa de cierre atribuida a la herramienta
    (en puntos porcentuales; ej. 3 = pasar de 20% a 23%).
  - leads_por_mes: cantidad de leads/prospectos trabajados por mes.
  - costo_mensual: costo total mensual de operar el sistema (TCO: computo + IA +
    base de datos + mantenimiento), en la misma moneda.

DISENO
------
- Tabla propia business_config (tenant_id PK). No toca ninguna otra tabla.
- Best-effort: si PG no esta, devuelve los defaults.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_table_ready = False

# Defaults neutros: hasta que el admin cargue valores, las proyecciones dan 0
# (no se inventan numeros). El admin los edita desde la interfaz.
DEFAULTS = {
    "ticket_promedio": 0.0,
    "margen_pct": 0.0,
    "cierre_base_pct": 0.0,
    "cierre_mejora_pct": 0.0,
    "leads_por_mes": 0.0,
    "costo_mensual": 0.0,
    "moneda": "USD",
}

_NUM_FIELDS = ("ticket_promedio", "margen_pct", "cierre_base_pct",
               "cierre_mejora_pct", "leads_por_mes", "costo_mensual")


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


def _ensure_table(conn) -> None:
    global _table_ready
    if _table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS business_config (
                tenant_id        TEXT        NOT NULL,
                ticket_promedio  DOUBLE PRECISION NOT NULL DEFAULT 0,
                margen_pct       DOUBLE PRECISION NOT NULL DEFAULT 0,
                cierre_base_pct  DOUBLE PRECISION NOT NULL DEFAULT 0,
                cierre_mejora_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
                leads_por_mes    DOUBLE PRECISION NOT NULL DEFAULT 0,
                costo_mensual    DOUBLE PRECISION NOT NULL DEFAULT 0,
                moneda           TEXT        NOT NULL DEFAULT 'USD',
                updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (tenant_id)
            )
            """
        )
    conn.commit()
    _table_ready = True


def get_config(tenant_id: str = "__legacy__") -> dict:
    """Devuelve los parametros del tenant, o los defaults si no estan cargados."""
    base = dict(DEFAULTS)
    if not is_available():
        return base
    conn = _conn()
    if conn is None:
        return base
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ticket_promedio, margen_pct, cierre_base_pct, "
                "cierre_mejora_pct, leads_por_mes, costo_mensual, moneda "
                "FROM business_config WHERE tenant_id = %s LIMIT 1",
                (tenant_id or "__legacy__",),
            )
            row = cur.fetchone()
        _release(conn)
        if not row:
            return base
        return {
            "ticket_promedio": float(row[0]), "margen_pct": float(row[1]),
            "cierre_base_pct": float(row[2]), "cierre_mejora_pct": float(row[3]),
            "leads_por_mes": float(row[4]), "costo_mensual": float(row[5]),
            "moneda": row[6] or "USD",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"business_config get error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return base


def set_config(tenant_id: str, values: dict) -> bool:
    """Guarda (upsert) los parametros del tenant. Best-effort."""
    if not is_available():
        return False

    def _num(key):
        try:
            v = float(values.get(key, 0) or 0)
        except (TypeError, ValueError):
            v = 0.0
        return max(0.0, v)

    moneda = str(values.get("moneda", "USD") or "USD").strip()[:8] or "USD"
    conn = _conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO business_config
                    (tenant_id, ticket_promedio, margen_pct, cierre_base_pct,
                     cierre_mejora_pct, leads_por_mes, costo_mensual, moneda, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now())
                ON CONFLICT (tenant_id) DO UPDATE SET
                    ticket_promedio   = EXCLUDED.ticket_promedio,
                    margen_pct        = EXCLUDED.margen_pct,
                    cierre_base_pct   = EXCLUDED.cierre_base_pct,
                    cierre_mejora_pct = EXCLUDED.cierre_mejora_pct,
                    leads_por_mes     = EXCLUDED.leads_por_mes,
                    costo_mensual     = EXCLUDED.costo_mensual,
                    moneda            = EXCLUDED.moneda,
                    updated_at        = now()
                """,
                (tenant_id or "__legacy__", _num("ticket_promedio"),
                 _num("margen_pct"), _num("cierre_base_pct"),
                 _num("cierre_mejora_pct"), _num("leads_por_mes"),
                 _num("costo_mensual"), moneda),
            )
        conn.commit()
        _release(conn)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"business_config set error: {exc}")
        try:
            conn.rollback()
        except Exception:
            pass
        _release(conn, close=True)
        return False


def project_metrics(cfg: dict) -> dict:
    """
    Calcula las PROYECCIONES financieras a partir de los parametros. Son
    estimaciones sobre los valores cargados, NO datos de ventas reales.

    - ganancia_por_venta = ticket_promedio * margen_pct/100
    - LTV proyectado = ganancia por operacion cerrada (modelo simple: 1 lote por
      cliente; sin recurrencia real, el LTV equivale a la ganancia de la venta).
    - ventas_base/mes = leads_por_mes * cierre_base_pct/100
    - ventas_mejora/mes = leads_por_mes * (cierre_base_pct + cierre_mejora_pct)/100
    - ventas_extra/mes = ventas_mejora - ventas_base (atribuibles a la herramienta)
    - ingreso_extra/mes = ventas_extra * ganancia_por_venta
    - ARR_proyectado = ingreso (ganancia) anual con la tasa mejorada
    - ROI = (beneficio_extra_anual - costo_anual) / costo_anual
    """
    tk = float(cfg.get("ticket_promedio", 0) or 0)
    margen = float(cfg.get("margen_pct", 0) or 0) / 100.0
    base = float(cfg.get("cierre_base_pct", 0) or 0) / 100.0
    mejora = float(cfg.get("cierre_mejora_pct", 0) or 0) / 100.0
    leads = float(cfg.get("leads_por_mes", 0) or 0)
    costo_mes = float(cfg.get("costo_mensual", 0) or 0)

    ganancia_por_venta = tk * margen
    ventas_base_mes = leads * base
    ventas_mejora_mes = leads * min(1.0, base + mejora)
    ventas_extra_mes = max(0.0, ventas_mejora_mes - ventas_base_mes)
    ingreso_extra_mes = ventas_extra_mes * ganancia_por_venta
    ingreso_extra_anual = ingreso_extra_mes * 12
    costo_anual = costo_mes * 12
    # ARR proyectado: ganancia anual total con la tasa mejorada.
    arr_proyectado = ventas_mejora_mes * ganancia_por_venta * 12
    roi_pct = None
    if costo_anual > 0:
        roi_pct = round(((ingreso_extra_anual - costo_anual) / costo_anual) * 100, 1)

    return {
        "ganancia_por_venta": round(ganancia_por_venta, 2),
        "ltv_proyectado": round(ganancia_por_venta, 2),
        "ventas_base_mes": round(ventas_base_mes, 2),
        "ventas_mejora_mes": round(ventas_mejora_mes, 2),
        "ventas_extra_mes": round(ventas_extra_mes, 2),
        "ingreso_extra_mes": round(ingreso_extra_mes, 2),
        "ingreso_extra_anual": round(ingreso_extra_anual, 2),
        "arr_proyectado": round(arr_proyectado, 2),
        "costo_mensual": round(costo_mes, 2),
        "costo_anual": round(costo_anual, 2),
        "roi_pct": roi_pct,
    }
