# -*- coding: utf-8 -*-
"""
Web interface for the text sales and real estate analyzer.

Run with:
    python web_app.py

Then open: http://localhost:5000
"""
from __future__ import annotations

import sys
import os

# Set UTF-8 encoding for Windows console output
os.environ["PYTHONIOENCODING"] = "utf-8"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import secrets
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from src.factory import create_analyzer
from src.components.commercial_analyzer import CommercialAnalyzer
from src.components.audio_transcriber import AudioTranscriber
from src.models.data_models import AnalysisReport, AnalysisError
from src.users.user_manager import UserManager
from src.users.history_manager import add_entry, get_history, get_flat_entries

app = Flask(__name__)

# SECRET_KEY: use env var in production (Railway).
# In development, use a stable hardcoded fallback so local sessions survive restarts.
# NEVER use the dev fallback in production — set SECRET_KEY in Railway env vars.
_SECRET_KEY = os.environ.get("SECRET_KEY")
if not _SECRET_KEY:
    _is_prod_env = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PORT"))
    if _is_prod_env:
        # In production without SECRET_KEY, generate a random one and warn loudly.
        # Sessions will break on restart, but at least the app won't crash.
        _SECRET_KEY = secrets.token_hex(32)
        import logging as _logging_init
        _logging_init.warning(
            "CRITICAL: SECRET_KEY not set in production. "
            "All sessions will be invalidated on every restart. "
            "Set SECRET_KEY in Railway environment variables immediately."
        )
    else:
        # Local dev: stable key so sessions survive `python web_app.py` restarts.
        # This is NOT a secret — do not use in production.
        _SECRET_KEY = "dev-local-stable-key-not-for-production-analizador-v3"

app.secret_key = _SECRET_KEY

# Limit upload size to 200 MB to prevent out-of-memory crashes from large audio files.
# Audio files larger than this should be split before uploading.
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB
commercial_analyzer = CommercialAnalyzer()
user_manager = UserManager()
audio_transcriber = AudioTranscriber(model_name="base")


def _dedup_transcription(text: str) -> str:
    """
    Remove consecutive repeated words/phrases that transcription systems produce.

    Examples:
        "bueno bueno bueno entonces" → "bueno entonces"
        "si si si claro" → "si claro"
        "CVU CVU CVU CVU CVU" → "CVU"
        "Si, si. Si, si. Si, si." → "Si, si."
        "vamos a vamos a ver" → "vamos a ver"

    Handles repeated words and phrases regardless of case,
    including repetitions separated by punctuation.
    """
    import re

    if not text or len(text) < 5:
        return text

    result = text

    # Pass 1: Remove consecutive repeated single words separated by commas/spaces
    # Handles: "no, no, no, no, no" → "no"
    # Handles: "si, si, si, si" → "si"
    for _ in range(5):
        prev = result
        result = re.sub(r'\b(\w+)([,;.\s]+\1)+\b', r'\1', result, flags=re.IGNORECASE)
        if result == prev:
            break

    # Pass 2: Remove consecutive repeated single words (space-only separated)
    for _ in range(3):
        prev = result
        result = re.sub(r'\b(\w+)(\s+\1)+\b', r'\1', result, flags=re.IGNORECASE)
        if result == prev:
            break

    # Pass 3: Remove consecutive repeated two-word phrases (with comma/space separators)
    for _ in range(3):
        prev = result
        result = re.sub(r'\b(\w+\s+\w+)([,;.\s]+\1)+\b', r'\1', result, flags=re.IGNORECASE)
        if result == prev:
            break

    # Pass 4: Remove consecutive repeated three-word phrases
    for _ in range(2):
        prev = result
        result = re.sub(r'\b(\w+\s+\w+\s+\w+)([,;.\s]+\1)+\b', r'\1', result, flags=re.IGNORECASE)
        if result == prev:
            break

    # Pass 4b: Remove consecutive repeated phrases of ANY length (4 to 10 words)
    # Handles: "a ver si lo corto, a ver si lo corto, ..." → "a ver si lo corto"
    # Iterates from longest to shortest so long phrases collapse first.
    for phrase_len in range(10, 3, -1):
        word = r'\w+'
        phrase_pattern = r'\b(' + word + r'(?:\s+' + word + r'){' + str(phrase_len - 1) + r'})([,;.\s]+\1)+\b'
        for _ in range(3):
            prev = result
            result = re.sub(phrase_pattern, r'\1', result, flags=re.IGNORECASE)
            if result == prev:
                break

    # Pass 5: Remove repeated short sentences/phrases separated by punctuation
    # Handles: "Si, si. Si, si. Si, si." → "Si, si."
    for _ in range(3):
        prev = result
        result = re.sub(
            r'((?:\w+[,.]?\s*){1,5}[.!?])\s*(\1\s*)+',
            r'\1 ',
            result,
            flags=re.IGNORECASE
        )
        if result == prev:
            break

    # Pass 5: Remove repeated lines (entire lines that are identical)
    lines = result.split('\n')
    deduped_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i > 0 and stripped and stripped == lines[i-1].strip():
            continue
        deduped_lines.append(line)
    result = '\n'.join(deduped_lines)

    # Clean up multiple spaces and trailing spaces
    result = re.sub(r'  +', ' ', result)
    result = re.sub(r' +\n', '\n', result)

    return result.strip()


def _build_commercial_dict(ca) -> dict:
    """Build the commercial analysis dictionary for JSON response."""
    return {
        "palabras_positivas": ca.palabras_positivas,
        "respuestas_afirmativas": ca.respuestas_afirmativas,
        "indicios_cierre": ca.indicios_cierre,
        "escasez_comercial": ca.escasez_comercial,
        "pedidos_referidos": ca.pedidos_referidos,
        "objeciones": ca.objeciones,
        "indicios_prospeccion": ca.indicios_prospeccion,
        "total_palabras": ca.total_palabras,
        "densidad_comercial": ca.densidad_comercial,
        "probabilidad_cierre": ca.probabilidad_cierre,
        "tipo_lead": ca.tipo_lead,
        "nivel_interes": ca.nivel_interes,
        "tendencia_cierre": ca.tendencia_cierre,
        "recomendacion": ca.recomendacion,
        "detalle": ca.detalle,
        "formula": {
            "indicios_cierre_pts": ca.indicios_cierre * 5,
            "respuestas_afirmativas_pts": ca.respuestas_afirmativas * 2,
            "objeciones_pts": ca.objeciones * 3,
            "puntaje_neto": (ca.indicios_cierre * 5) + (ca.respuestas_afirmativas * 2) - (ca.objeciones * 3),
            "total_palabras": ca.total_palabras,
            "para_caliente": max(0, round(70 - ca.probabilidad_cierre, 1)),
            "para_tibio": max(0, round(40 - ca.probabilidad_cierre, 1)),
        },
        "etapa_funnel": ca.etapa_funnel,
        "urgencia": ca.urgencia,
        "nivel_compromiso": ca.nivel_compromiso,
        "senales_compra": ca.senales_compra,
        "objeciones_especificas": ca.objeciones_especificas,
        "tipo_operacion": ca.tipo_operacion,
        "financiamiento": ca.financiamiento,
        "tecnicas_persuasion": ca.tecnicas_persuasion,
        "preguntas_abiertas": ca.preguntas_abiertas,
        "keywords": ca.keywords,
        "resumen": ca.resumen,
        "accion_siguiente": ca.accion_siguiente,
        "prospeccion_detalle": ca.prospeccion_detalle,
        "indicadores_detalle_categorias": ca.indicadores_detalle_categorias,
        "indicadores_total_frases": ca.indicadores_total_frases,
        # --- Reglas de negocio inmobiliarias ---
        "co_decisores": ca.co_decisores,
        "es_multi_decisor": ca.es_multi_decisor,
        "rango_presupuestario": ca.rango_presupuestario,
        "presupuesto_detalle": ca.presupuesto_detalle,
        "alertas_vendedor": ca.alertas_vendedor,
        "requiere_revision_coordinador": ca.requiere_revision_coordinador,
        "motivo_revision": ca.motivo_revision,
    }

# Load analyzer once at startup
print("Loading models...")

def _train_models():
    """Train models from scratch using the training data."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "src.training.train_models"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Training stdout:", result.stdout)
        print("Training stderr:", result.stderr)
        raise RuntimeError(
            "Could not train models. "
            "Run 'python -m src.training.train_models' locally."
        )

# In production (Railway), always retrain to avoid version mismatch issues
_is_production = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PORT"))

if _is_production:
    print("Production environment detected. Training models fresh...")
    _train_models()
    analyzer = create_analyzer()
    # Sanity check
    _test = analyzer.analyze("Test de verificacion de modelos.")
    if hasattr(_test, 'error_code') and _test.error_code == "ANALYSIS_ERROR":
        raise RuntimeError(f"Freshly trained models failed: {_test.error_message}")
    print("Models trained and loaded successfully.")
else:
    try:
        analyzer = create_analyzer()
        # Quick sanity check: run a test analysis to verify models work
        _test = analyzer.analyze("Test de verificacion de modelos.")
        if hasattr(_test, 'error_code') and _test.error_code == "ANALYSIS_ERROR":
            raise RuntimeError(f"Models loaded but analysis failed: {_test.error_message}")
        print("Models loaded successfully.")
    except Exception as exc:
        print(f"Models could not be loaded: {exc}")
        print("Training models now (this may take a minute)...")
        _train_models()
        analyzer = create_analyzer()
        print("Models trained and loaded.")

# ---------------------------------------------------------------------------
# Sync Pipeline + Scheduler — DESACTIVADO temporalmente
# ---------------------------------------------------------------------------
import logging
logging.basicConfig(level=logging.INFO)

# Sync desactivado hasta resolver los problemas de asignación de fechas
print("Info: Sync automático DESACTIVADO temporalmente.")

# ---------------------------------------------------------------------------
# Auto-migrate JSON history files → PostgreSQL (runs once at startup)
# ---------------------------------------------------------------------------
try:
    from src.users.history_manager import migrate_json_to_pg, _is_pg_available, _get_pg_conn, _return_pg_conn
    import os as _os_check

    # Log database connectivity status at startup
    _db_url = _os_check.environ.get("DATABASE_URL", "")
    print(f"[DB STATUS] DATABASE_URL set: {bool(_db_url)}")
    print(f"[DB STATUS] RAILWAY_ENVIRONMENT: {_os_check.environ.get('RAILWAY_ENVIRONMENT', 'NOT SET')}")

    _pg_ok = _is_pg_available()
    print(f"[DB STATUS] PostgreSQL available: {_pg_ok}")

    if _pg_ok:
        _diag_conn = _get_pg_conn()
        if _diag_conn:
            try:
                with _diag_conn.cursor() as _cur:
                    _cur.execute("SELECT COUNT(*) FROM analysis_history")
                    _total = _cur.fetchone()[0]
                    _cur.execute("SELECT username, COUNT(*) FROM analysis_history GROUP BY username")
                    _by_user = dict(_cur.fetchall())
                print(f"[DB STATUS] Total entries in DB: {_total}")
                print(f"[DB STATUS] Entries by user: {_by_user}")
            except Exception as _diag_exc:
                print(f"[DB STATUS] Error querying DB: {_diag_exc}")
            finally:
                _return_pg_conn(_diag_conn)
    else:
        print("[DB STATUS] Using JSON fallback (PostgreSQL not available)")

    _migration = migrate_json_to_pg()
    if not _migration.get("skipped"):
        print(f"Migración JSON→PG: {_migration.get('migrated', 0)} entradas migradas, "
              f"{_migration.get('errors', 0)} errores.")
except Exception as _mig_exc:
    print(f"Warning: migración JSON→PG falló: {_mig_exc}")

# ---------------------------------------------------------------------------
# Data-protection: ensure backup tables exist and take a boot-time snapshot.
# Runs in the background so it never delays app startup. Best-effort.
# ---------------------------------------------------------------------------
try:
    from src.users.backup_manager import ensure_backup_tables, take_backup, get_backup_status, auto_fix
    ensure_backup_tables()
    # AUTO FIX at boot: reconcile the live table against the union of ALL
    # backups, entry-by-entry, and re-insert any missing texts automatically.
    # Only adds, never deletes — so it can only recover, never lose data.
    try:
        _fix = auto_fix()
        if _fix.get("ok") and _fix.get("restored", 0) > 0:
            print(f"[AUTO-FIX] Recuperados {_fix['restored']} textos faltantes al arrancar "
                  f"(de {_fix.get('missing_count')} detectados).")
        elif _fix.get("ok"):
            print(f"[AUTO-FIX] Sin textos faltantes. Vivos={_fix.get('live_count')}, "
                  f"backup-union={_fix.get('backup_union_count')}.")
    except Exception as _fx_exc:
        print(f"[AUTO-FIX] omitido (no critico): {_fx_exc}")

    _bstat = get_backup_status()
    # Only take a boot backup if there is NO significant loss detected. If a loss
    # IS detected, we must NOT overwrite the good backup with a diminished one.
    if not _bstat.get("alert"):
        take_backup(reason="startup")
        print(f"[BACKUP] Snapshot inicial OK. Entradas: {_bstat.get('current_total', '?')}")
    else:
        print(f"[BACKUP] ALERTA: posible perdida de datos detectada al arrancar. "
              f"Actual={_bstat.get('current_total')} vs backup={_bstat.get('last_backup_total')}. "
              f"NO se sobrescribio el backup. Revisar /admin/backup-status")
except Exception as _bk_exc:
    print(f"Warning: inicializacion de backups fallo (no critico): {_bk_exc}")

# Solo iniciar el scheduler si las credenciales están configuradas
# DESACTIVADO TEMPORALMENTE — sync automático apagado
_mpc_configured = False  # Forzar desactivado

if _mpc_configured:
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(
            func=lambda: sync_pipeline.run(historical=False),
            trigger=CronTrigger(hour=9, minute=0),
            id="sync_morning",
            name="Sync transcripciones 9:00",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        _scheduler.add_job(
            func=lambda: sync_pipeline.run(historical=False),
            trigger=CronTrigger(hour=18, minute=0),
            id="sync_evening",
            name="Sync transcripciones 18:00",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        _scheduler.start()
        print("Scheduler de sincronización iniciado (9:00 y 18:00 diario).")
    except Exception as _exc:
        print(f"Warning: No se pudo iniciar el scheduler: {_exc}")
else:
    print("Info: Sync automático DESACTIVADO.")

# ---------------------------------------------------------------------------
# Historical sync — DESACTIVADO
# ---------------------------------------------------------------------------
# Desactivado hasta resolver problemas de asignación de fechas

# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

import json as _json_mod
from src.components.commercial_analyzer import _INDICADOR_CATEGORIAS, _PROSPECCION_CATEGORIAS
_INDICADOR_CATEGORIAS_JSON = _json_mod.dumps(
    {**_INDICADOR_CATEGORIAS, "indicios_prospeccion": _PROSPECCION_CATEGORIAS},
    ensure_ascii=False
)

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <title>Analizador de Textos - Ventas y Bienes Raices v7</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        /* Theme tokens for the neo-morphic / neon depth system.
           --accent drives the neon glow; override it per-container to tint
           the halo to that card's category color. */
        :root {
            --accent: #4a6cf7;
            --depth-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
            --depth-inset: inset 0 1px 0 rgba(255, 255, 255, 0.05);
            /* Single, uniform animation duration used across the whole UI:
               page entrance, section reveals and collapsible expand/collapse. */
            --anim-duration: 6400ms;
            --anim-ease: cubic-bezier(0.22, 0.61, 0.36, 1);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f1117;
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
        }

        h1 {
            font-size: 1.6rem;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 6px;
        }

        .subtitle {
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 28px;
        }

        .input-section {
            background: #1a1d27;
            border: 1px solid #2a2d3a;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 24px;
        }

        textarea {
            width: 100%;
            height: 650px;
            background: #0f1117;
            border: 1px solid #2a2d3a;
            border-radius: 8px;
            color: #e0e0e0;
            font-size: 0.95rem;
            padding: 12px;
            resize: vertical;
            outline: none;
            font-family: inherit;
            line-height: 1.5;
        }

        textarea:focus {
            border-color: #4a6cf7;
        }

        textarea::placeholder { color: #555; }

        /* Highlight overlay for indicator word highlighting */
        .textarea-wrapper {
            position: relative;
        }

        .highlight-overlay {
            display: none;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            min-height: 650px;
            height: 100%;
            background: #0f1117;
            border: 2px solid #4a6cf7;
            border-radius: 8px;
            color: #e0e0e0;
            font-size: 0.95rem;
            padding: 12px;
            padding-right: 30px;
            overflow-y: auto;
            font-family: inherit;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
            z-index: 10;
            cursor: text;
            user-select: text;
            -webkit-user-select: text;
            box-sizing: border-box;
        }

        .highlight-overlay.active {
            display: block;
        }

        .highlight-close-btn {
            display: none;
            position: absolute;
            top: 8px;
            right: 12px;
            background: #1a1d27;
            border: 1px solid #4a6cf7;
            color: #fff;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            min-width: 32px;
            min-height: 32px;
            flex: 0 0 32px;
            padding: 0;
            font-size: 0.95rem;
            cursor: pointer;
            z-index: 20;
            line-height: 1;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.5);
            box-sizing: border-box;
        }

        .highlight-close-btn.active {
            display: flex;
        }

        .highlight-close-btn:hover {
            background: #4a6cf7;
            color: #fff;
        }

        .hl-palabras_positivas { background: rgba(255, 255, 0, 0.25); color: #FFFF00; border-radius: 3px; padding: 0 2px; }
        .hl-respuestas_afirmativas { background: rgba(0, 128, 0, 0.30); color: #2ecc71; border-radius: 3px; padding: 0 2px; }
        .hl-indicios_cierre { background: rgba(255, 165, 0, 0.25); color: #FFA500; border-radius: 3px; padding: 0 2px; }
        .hl-escasez_comercial { background: rgba(255, 0, 255, 0.25); color: #FF00FF; border-radius: 3px; padding: 0 2px; }
        .hl-pedidos_referidos { background: rgba(163, 91, 245, 0.25); color: #b38bff; border-radius: 3px; padding: 0 2px; }
        .hl-objeciones { background: rgba(255, 0, 0, 0.25); color: #FF4444; border-radius: 3px; padding: 0 2px; }
        .hl-indicios_prospeccion { background: rgba(0, 191, 255, 0.25); color: #00BFFF; border-radius: 3px; padding: 0 2px; }
        .hl-intent { background: rgba(123, 91, 245, 0.3); color: #b38bff; border-radius: 3px; padding: 0 2px; }

        /* Resaltar y Definir - highlight & define tool */
        .highlight-define-row {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 8px;
            position: relative;
        }

        .btn-highlight-define {
            background: linear-gradient(135deg, #2a2d3a 0%, #1a1d27 100%);
            border: 1px solid #3a3d4a;
            color: #e0e0e0;
            padding: 8px 16px;
            border-radius: 7px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .btn-highlight-define:hover {
            border-color: #4a6cf7;
            background: linear-gradient(135deg, #2a3050 0%, #1a2040 100%);
            color: #fff;
        }

        /* Button is always enabled now — no disabled styling */

        .highlight-selection-info {
            font-size: 0.7rem;
            color: #666;
            font-style: italic;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .highlight-selection-info .selected-text {
            color: #4a6cf7;
            font-style: normal;
            font-weight: 600;
        }

        /* Category popover */
        .category-popover {
            display: none;
            position: absolute;
            bottom: calc(100% + 8px);
            left: 0;
            background: #1a1d27;
            border: 1px solid #3a3d4a;
            border-radius: 10px;
            padding: 12px;
            z-index: 100;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
            min-width: 280px;
        }

        .category-popover.active {
            display: block;
        }

        .category-popover-title {
            font-size: 0.7rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
            margin-bottom: 10px;
        }

        .category-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }

        .category-option {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 7px;
            cursor: pointer;
            border: 1px solid transparent;
            transition: all 0.15s;
            background: #0f1117;
        }

        .category-option:hover {
            border-color: var(--cat-color);
            background: #151820;
            transform: scale(1.02);
        }

        .category-option .cat-dot {
            width: 12px;
            height: 12px;
            border-radius: 3px;
            flex-shrink: 0;
        }

        .category-option .cat-label {
            font-size: 0.75rem;
            font-weight: 500;
            color: #ccc;
        }

        /* Manual highlights stored */
        .hl-manual-palabras_positivas { background: rgba(255, 255, 0, 0.35); color: #FFFF00; border-radius: 3px; padding: 0 2px; text-decoration: underline dotted; }
        .hl-manual-respuestas_afirmativas { background: rgba(0, 128, 0, 0.40); color: #2ecc71; border-radius: 3px; padding: 0 2px; text-decoration: underline dotted; }
        .hl-manual-indicios_cierre { background: rgba(255, 165, 0, 0.35); color: #FFA500; border-radius: 3px; padding: 0 2px; text-decoration: underline dotted; }
        .hl-manual-escasez_comercial { background: rgba(255, 0, 255, 0.35); color: #FF00FF; border-radius: 3px; padding: 0 2px; text-decoration: underline dotted; }
        .hl-manual-pedidos_referidos { background: rgba(163, 91, 245, 0.35); color: #b38bff; border-radius: 3px; padding: 0 2px; text-decoration: underline dotted; }
        .hl-manual-objeciones { background: rgba(255, 0, 0, 0.35); color: #FF4444; border-radius: 3px; padding: 0 2px; text-decoration: underline dotted; }
        .hl-manual-indicios_prospeccion { background: rgba(0, 191, 255, 0.35); color: #00BFFF; border-radius: 3px; padding: 0 2px; text-decoration: underline dotted; }

        /* Date selectors */
        .date-selectors {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 10px;
        }
        .date-select-group { min-width: 0; }
        .date-select-group {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .date-select-group label {
            font-size: 0.7rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-weight: 600;
        }
        .date-select-group select {
            background: #0d0f18;
            color: #e0e0e0;
            border: 1px solid #2a2d3e;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 0.85rem;
            cursor: pointer;
            outline: none;
            min-width: 120px;
            appearance: auto;
        }
        .date-select-group select:focus {
            border-color: #4a6cf7;
        }

        /* Save confirmation panel */
        .save-confirmation {
            margin-top: 12px;
            padding: 12px 16px;
            background: #111828;
            border: 1px solid #1e2a40;
            border-radius: 10px;
        }
        .save-conf-main {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .save-conf-icon { font-size: 1.1rem; }
        .save-conf-text {
            font-size: 0.82rem;
            color: #ccc;
            flex: 1;
        }
        .save-conf-text strong { color: #5bf5a3; }
        .save-conf-btn {
            background: transparent;
            border: 1px solid #4a6cf7;
            color: #4a6cf7;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 0.75rem;
            cursor: pointer;
            transition: background 0.2s;
        }
        .save-conf-btn:hover {
            background: #111828;
        }
        .save-relocate-panel {
            display: none;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #1e2130;
        }
        .save-relocate-panel.open { display: block; }
        .save-relocate-desc {
            font-size: 0.73rem;
            color: #888;
            margin-bottom: 8px;
        }
        .save-relocate-selects {
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
        }
        .save-relocate-selects select {
            background: #0d0f18;
            color: #e0e0e0;
            border: 1px solid #2a2d3e;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 0.8rem;
            cursor: pointer;
            outline: none;
        }
        .save-relocate-selects select:focus { border-color: #4a6cf7; }
        .save-relocate-confirm {
            background: #4a6cf7;
            color: #fff;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.78rem;
            cursor: pointer;
            transition: background 0.2s;
        }
        .save-relocate-confirm:hover { background: #3a5cd7; }
        .save-delete-btn {
            background: transparent;
            color: #f55b5b;
            border: 1px solid #f55b5b;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 0.78rem;
            cursor: pointer;
            transition: background 0.2s;
        }
        .save-delete-btn:hover { background: #2a0d0d; }

        /* Save name input */
        .save-name-row {
            margin-bottom: 6px;
        }
        .save-name-input {
            width: 100%;
            background: #0d0f18;
            color: #e0e0e0;
            border: 1px solid #2a2d3e;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 0.82rem;
            outline: none;
        }
        .save-name-input:focus { border-color: #4a6cf7; }

        /* Saved texts button and panel */
        .saved-texts-btn {
            background: #0d0f18;
            color: #e0e0e0;
            border: 1px solid #2a2d3e;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 0.82rem;
            cursor: pointer;
            transition: border-color 0.2s;
            white-space: nowrap;
        }
        .saved-texts-btn:hover { border-color: #4a6cf7; }
        .saved-texts-panel {
            display: none;
            margin-top: 10px;
            padding: 12px;
            background: #0a0c14;
            border: 1px solid #1e2a40;
            border-radius: 10px;
            max-height: 250px;
            overflow-y: auto;
        }
        .saved-texts-panel.open { display: block; }
        .saved-texts-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            font-size: 0.78rem;
            color: #888;
            font-weight: 600;
        }
        .saved-texts-close {
            background: none;
            border: none;
            color: #666;
            font-size: 1rem;
            cursor: pointer;
        }
        .saved-texts-close:hover { color: #f55b5b; }
        .saved-text-item {
            padding: 8px 10px;
            background: #111828;
            border: 1px solid #1e2130;
            border-radius: 6px;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: border-color 0.2s;
        }
        .saved-text-item:hover { border-color: #4a6cf7; }
        .saved-text-row {
            flex: 1;
            cursor: pointer;
            min-width: 0;
        }
        .saved-text-name {
            font-size: 0.8rem;
            color: #e0e0e0;
            font-weight: 500;
            margin-bottom: 3px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .saved-text-meta {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.68rem;
            color: #666;
        }
        .saved-text-delete {
            background: none;
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 4px 6px;
            cursor: pointer;
            font-size: 0.8rem;
            opacity: 0.5;
            transition: opacity 0.2s, border-color 0.2s;
        }
        .saved-text-item:hover .saved-text-delete { opacity: 1; }
        .saved-text-delete:hover { border-color: #f55b5b; opacity: 1; }
        .st-badge {
            background: #1a2a3a;
            color: #5bd4f5;
            padding: 1px 6px;
            border-radius: 8px;
            font-size: 0.62rem;
        }
        .saved-text-time { color: #555; }
        .saved-texts-empty {
            font-size: 0.78rem;
            color: #555;
            font-style: italic;
            text-align: center;
            padding: 12px;
        }

        .btn-row {
            display: flex;
            gap: 10px;
            margin-top: 12px;
        }

        button {
            padding: 10px 24px;
            border: none;
            border-radius: 7px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }

        button:hover { opacity: 0.85; }

        .btn-primary { background: #4a6cf7; color: white; }
        .btn-secondary { background: #2a2d3a; color: #aaa; }
        .btn-save { background: #2a8a4a; color: white; white-space: nowrap; }

        .loading { display: none; color: #888; font-size: 0.85rem; margin-top: 10px; }

        /* Results */
        .results { display: none; }

        .result-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 14px;
        }

        @media (max-width: 600px) {
            .result-grid { grid-template-columns: 1fr; }
        }

        .card {
            background: #1a1d27;
            border: 1px solid #2a2d3a;
            border-radius: 10px;
            padding: 16px;
            position: relative;
        }
        /* Neo-morphic / neon depth applied to ALL main information bubbles.
           Fallback (no color-mix): plain elevation + inner top highlight. */
        .card,
        .input-section {
            box-shadow: var(--depth-shadow), var(--depth-inset);
            transition: box-shadow 0.25s ease, transform 0.25s ease, border-color 0.25s ease;
        }
        /* Progressive enhancement: browsers with color-mix get the neon halo
           tinted by --accent. Visible but still clean. */
        @supports (background: color-mix(in srgb, red, blue)) {
            .card,
            .input-section {
                box-shadow:
                    var(--depth-shadow),
                    var(--depth-inset),
                    0 0 0 1px color-mix(in srgb, var(--accent) 35%, transparent),
                    0 0 20px -2px color-mix(in srgb, var(--accent) 42%, transparent);
            }
            .card:hover,
            .input-section:hover {
                border-color: color-mix(in srgb, var(--accent) 55%, #2a2d3a);
                box-shadow:
                    var(--depth-shadow),
                    var(--depth-inset),
                    0 0 0 1px color-mix(in srgb, var(--accent) 55%, transparent),
                    0 0 30px -1px color-mix(in srgb, var(--accent) 58%, transparent);
            }
        }

        /* Depth for the smaller information bubbles. Each can set --accent inline
           to tint its own halo (e.g. indicator cards use their category color). */
        .indicator-item,
        .history-entry,
        .formula-result,
        .recomendacion-box {
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4), var(--depth-inset);
            transition: box-shadow 0.25s ease, transform 0.2s ease, border-color 0.25s ease;
        }
        @supports (background: color-mix(in srgb, red, blue)) {
            .indicator-item,
            .history-entry,
            .formula-result,
            .recomendacion-box {
                box-shadow:
                    0 4px 12px rgba(0, 0, 0, 0.4),
                    var(--depth-inset),
                    0 0 0 1px color-mix(in srgb, var(--accent) 30%, transparent),
                    0 0 14px -3px color-mix(in srgb, var(--accent) 40%, transparent);
            }
            .indicator-item:hover,
            .history-entry:hover {
                transform: translateY(-1px);
                box-shadow:
                    0 8px 18px rgba(0, 0, 0, 0.5),
                    var(--depth-inset),
                    0 0 20px -2px color-mix(in srgb, var(--accent) 55%, transparent);
            }
        }

        .card-title {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #666;
            margin-bottom: 10px;
            position: relative;
        }

        /* Report sections: highlight the whole section (title + paragraphs) when
           hovered with the cursor or tapped on touch (.rep-active). Subtle glow
           tied to the section accent (#7b9cff). Keeps text fully readable. */
        .report-section {
            padding: 8px 12px;
            margin: 0 -12px 4px -12px;
            border-radius: 8px;
            border-left: 3px solid transparent;
            transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
            cursor: default;
        }
        .report-section:hover,
        .report-section.rep-active {
            background: rgba(123, 156, 255, 0.08);
            border-left-color: #7b9cff;
            box-shadow: 0 0 16px -6px rgba(123, 156, 255, 0.5);
        }
        .report-section:hover .rep-sec-title,
        .report-section.rep-active .rep-sec-title {
            color: #a9c2ff;
        }

        /* ── GLOBAL INTERACTIVITY: subtle highlight on point/tap ──────────────
           Table rows glow and lift, selects light up their border, and the admin
           donut scales slightly when pointed at. Keeps everything readable. */
        table tbody tr {
            transition: background 0.15s ease, box-shadow 0.15s ease;
        }
        table tbody tr:hover {
            background: rgba(123, 156, 255, 0.10) !important;
            box-shadow: inset 3px 0 0 #7b9cff;
        }
        select:hover,
        select:focus {
            border-color: #7b9cff !important;
            box-shadow: 0 0 12px -3px rgba(123, 156, 255, 0.6);
            outline: none;
        }
        select { transition: border-color 0.15s ease, box-shadow 0.15s ease; }
        /* Admin donut: gentle zoom + glow when pointed/tapped */
        #statsPieChart {
            transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
        }
        #statsPieChart:hover,
        #statsPieChart.pie-active {
            transform: scale(1.05);
            box-shadow: 0 8px 26px rgba(0,0,0,0.55), 0 0 24px -4px rgba(123,156,255,0.55);
        }
        /* Wrap the seller table so it reads as a framed, hover-aware block. */
        .seller-table-frame {
            border: 1px solid #2a2d3a;
            border-radius: 10px;
            padding: 4px;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        .seller-table-frame:hover {
            border-color: #7b9cff;
            box-shadow: 0 0 18px -6px rgba(123, 156, 255, 0.5);
        }

        /* ── GLOBAL HOVER for ALL content blocks (analysis, intent, pills,
           questions, keywords, formula, narrative, etc.). Every information
           container subtly lights up when pointed at or tapped. ────────── */
        .ext-data-row,
        .intent-detail-section,
        .lead-extended-item,
        .ext-data-pill,
        .concept-detail-item,
        .lead-ext-card,
        .ext-question,
        .input-preview {
            transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .ext-data-row:hover,
        .intent-detail-section:hover,
        .lead-extended-item:hover,
        .concept-detail-item:hover {
            background: rgba(123, 156, 255, 0.06) !important;
            border-color: #7b9cff !important;
            box-shadow: 0 0 14px -5px rgba(123, 156, 255, 0.45);
        }
        .ext-data-pill:hover,
        .lead-ext-card:hover {
            border-color: #7b9cff !important;
            box-shadow: 0 0 12px -4px rgba(123, 156, 255, 0.5);
            transform: translateY(-1px);
        }
        .ext-data-pill,
        .lead-ext-card {
            transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
        }
        .ext-question {
            transition: background 0.18s ease, border-left-color 0.18s ease, box-shadow 0.18s ease, color 0.18s ease, transform 0.18s ease;
        }
        .ext-question:hover {
            background: rgba(123, 156, 255, 0.14) !important;
            border-left-color: #7b9cff !important;
            border-left-width: 4px !important;
            color: #e8eeff !important;
            box-shadow: 0 0 14px -4px rgba(123, 156, 255, 0.55);
            transform: translateX(2px);
        }
        .phrase-chip {
            transition: transform 0.1s ease, box-shadow 0.1s ease;
        }
        .phrase-chip:hover {
            transform: scale(1.08);
            box-shadow: 0 0 8px -2px rgba(123, 156, 255, 0.6);
        }
        .input-preview:hover {
            border-left-color: #7b9cff !important;
            background: rgba(123, 156, 255, 0.04) !important;
        }
        /* Analysis blocks below the intent cards: Distribucion de Indicadores,
           Informe del Texto, Analisis Narrativo. */
        .analysis-block {
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        .analysis-block:hover {
            border-color: #7b9cff !important;
            box-shadow: 0 0 18px -5px rgba(123, 156, 255, 0.5);
        }
        /* Commercial analysis container highlights when pointed at/tapped. */
        .commercial-section {
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        .commercial-section:hover {
            border-color: #7b9cff;
            box-shadow: 0 0 18px -5px rgba(123, 156, 255, 0.5);
        }
        /* Recommendation box, probability formula and the lead-gap verdict box. */
        .recomendacion-box,
        .formula-result,
        .lead-gap {
            transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
        }
        .recomendacion-box:hover,
        .formula-result:hover,
        .lead-gap:hover {
            border-color: #7b9cff !important;
            box-shadow: 0 0 16px -5px rgba(123, 156, 255, 0.55);
        }
        /* Pie legend rows (indicator distribution) glow on point/tap. */
        .pie-legend-row {
            transition: background 0.15s ease, box-shadow 0.15s ease;
            border-radius: 5px;
        }
        .pie-legend-row:hover {
            background: rgba(123, 156, 255, 0.1);
            box-shadow: 0 0 10px -3px rgba(123, 156, 255, 0.5);
        }
        /* The small indicator donuts zoom slightly when pointed at/tapped. */
        .pie-chart-click {
            transition: transform 0.15s ease, filter 0.15s ease;
        }
        .pie-chart-click:hover {
            transform: scale(1.12);
            filter: drop-shadow(0 0 6px rgba(123, 156, 255, 0.6));
        }

        /* ════════════════════════════════════════════════════════════════════
           MOTION DESIGN — reusable entrance-animation utilities.
           Moderate, fluid UI animations (300–600ms) with natural easing.
           Add the class to any element to play its entrance once.
           Respects prefers-reduced-motion (see the media query below).
           ════════════════════════════════════════════════════════════════════ */

        /* 1. .fade-in-smooth — gradual opacity fade with a soft upward lift.
              Apply to cards, panels or text blocks as they appear. */
        @keyframes fadeInSmooth {
            from { opacity: 0; transform: translateY(8px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .fade-in-smooth {
            animation: fadeInSmooth var(--anim-duration) var(--anim-ease) both;
        }

        /* 2. .graph-line-reveal — progressive stroke draw for SVG line charts.
              Apply to an SVG <path>/<polyline>; the stroke "draws" itself.
              Note: pathLength="1" on the SVG element normalizes the dash math. */
        @keyframes graphLineReveal {
            from { stroke-dashoffset: 1; }
            to   { stroke-dashoffset: 0; }
        }
        .graph-line-reveal {
            stroke-dasharray: 1;
            stroke-dashoffset: 1;
            animation: graphLineReveal var(--anim-duration) ease-in-out forwards;
        }

        /* 3. .pie-chart-expand — circular reveal growing from the center.
              Apply to a pie/donut container; it scales up while fading in. */
        @keyframes pieChartExpand {
            from { opacity: 0; transform: scale(0.6); }
            to   { opacity: 1; transform: scale(1); }
        }
        .pie-chart-expand {
            transform-origin: center center;
            animation: pieChartExpand var(--anim-duration) cubic-bezier(0.34, 1.2, 0.64, 1) both;
        }

        /* 4. .staggered-entry — base for sequential delays on sibling items.
              Put .staggered-entry on each child; the :nth-child rules below
              cascade the animation-delay so items appear one after another. */
        /* Uniform: every item uses the SAME duration and no per-item delay. */
        .staggered-entry {
            animation: fadeInSmooth var(--anim-duration) var(--anim-ease) both;
        }

        /* ── INLINE TEXT REPLACEMENT — smooth content swap in one box ─────────
           For content that reloads inside the same text box (e.g. the analyzed
           text area). Old text fades out & lifts; new text fades in from below.
           Subtle 250–400ms with an eased, professional feel. ──────────────── */

        /* 1. .text-container-box — the box; animates its height fluidly and
              clips content during the swap to avoid flicker. */
        .text-container-box {
            overflow: hidden;
            transition: height 2800ms cubic-bezier(0.25, 1, 0.5, 1),
                        max-height 2800ms cubic-bezier(0.25, 1, 0.5, 1);
        }

        /* 2. .text-swap-exit — old text leaves: fade-out + slight upward lift. */
        @keyframes textSwapExit {
            from { opacity: 1; transform: translateY(0); }
            to   { opacity: 0; transform: translateY(-8px); }
        }
        .text-swap-exit {
            animation: textSwapExit 2400ms ease-out both;
        }

        /* 3. .text-swap-enter — new text arrives: fade-in rising from below. */
        @keyframes textSwapEnter {
            from { opacity: 0; transform: translateY(10px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .text-swap-enter {
            animation: textSwapEnter 2800ms cubic-bezier(0.25, 1, 0.5, 1) both;
        }

        /* 4. .typing-loader-inline — 3 blinking dots while new text loads. */
        .typing-loader-inline {
            display: inline-flex;
            gap: 4px;
            align-items: center;
            vertical-align: middle;
        }
        .typing-loader-inline span {
            width: 6px; height: 6px;
            border-radius: 50%;
            background: #7b9cff;
            animation: typingBlink 1s infinite ease-in-out both;
        }
        .typing-loader-inline span:nth-child(2) { animation-delay: 0.2s; }
        .typing-loader-inline span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingBlink {
            0%, 80%, 100% { opacity: 0.25; transform: scale(0.8); }
            40%           { opacity: 1;    transform: scale(1); }
        }

        /* ── PROGRESSIVE TEXT STREAMING — word-by-word reveal with role color ─
           Each word starts hidden and fades in sequentially (JS sets the
           per-word --d delay). Role classes tint the words as they appear. */
        @keyframes wordReveal {
            from { opacity: 0; transform: translateY(4px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .stream-word {
            opacity: 0;
            display: inline;
            animation: wordReveal 2400ms ease-out forwards;
            animation-delay: var(--d, 0ms);
        }
        .stream-word.role-vendedor { color: #5bd4f5; }  /* Vendedor → celeste */
        .stream-word.role-cliente  { color: #f5a35b; }  /* Cliente  → naranja */
        @media (prefers-reduced-motion: reduce) {
            .text-swap-exit, .text-swap-enter, .stream-word {
                animation: none !important; opacity: 1 !important; transform: none !important;
            }
        }

        /* AUTOMATIC page entrance (CSS-only, always fires on paint).
           Top-level containers reveal top-to-bottom in a fluid cascade. */
        @keyframes pageBlockIn {
            from { opacity: 0; transform: translateY(16px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .top-bar,
        .input-section,
        #adminStatsPanel,
        .results {
            animation: pageBlockIn var(--anim-duration) var(--anim-ease) both;
        }

        /* Accessibility: honor users who prefer reduced motion. */
        @media (prefers-reduced-motion: reduce) {
            .fade-in-smooth,
            .graph-line-reveal,
            .pie-chart-expand,
            .staggered-entry,
            .top-bar,
            .input-section,
            #adminStatsPanel,
            .results {
                animation: none !important;
                opacity: 1 !important;
                transform: none !important;
                stroke-dashoffset: 0 !important;
            }
        }
        /* Buttons glow on hover (Analizar, Limpiar, Guardar, etc.) */
        button {
            transition: box-shadow 0.15s ease, transform 0.1s ease;
        }
        button:hover {
            box-shadow: 0 0 14px -4px rgba(123, 156, 255, 0.55);
        }
        button:active {
            transform: scale(0.97);
        }

        .card-info-icon {
            position: absolute;
            top: -2px;
            right: 0;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: transparent;
            border: 1px solid #7b5bf5;
            color: #7b5bf5;
            font-size: 0.6rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            opacity: 0.6;
            transition: opacity 0.2s, background 0.2s;
        }
        .card-info-icon:hover {
            opacity: 1;
            background: #7b5bf520;
        }
        .card-info-tooltip {
            display: none;
            position: absolute;
            top: 22px;
            right: 0;
            background: #1a1d27;
            border: 1px solid #7b5bf5;
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 0.75rem;
            color: #ccc;
            font-weight: 400;
            text-transform: none;
            letter-spacing: 0;
            line-height: 1.5;
            width: 260px;
            z-index: 20;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .card-info-icon:hover + .card-info-tooltip,
        .card-info-tooltip:hover {
            display: block;
        }

        /* Source fragment toggle */
        .source-toggle {
            display: flex;
            justify-content: flex-end;
            padding: 4px 6px 0;
            cursor: pointer;
            opacity: 0.5;
            transition: opacity 0.2s;
        }
        .source-toggle:hover { opacity: 1; }
        .source-fragment {
            display: none;
            margin-top: 6px;
            padding: 8px 10px;
            background: #0a0c14;
            border: 1px solid #1e2130;
            border-radius: 6px;
            font-size: 0.72rem;
            color: #999;
            line-height: 1.5;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 150px;
            overflow-y: auto;
        }
        .source-fragment.open { display: block; }

        /* Inline source toggle (violet arrow) */
        .src-toggle-inline {
            text-align: right;
            padding: 2px 6px;
            font-size: 0.6rem;
            color: #7b5bf5;
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.2s;
        }
        .src-toggle-inline:hover { opacity: 1; }
        .src-fragment-inline {
            margin-top: 4px;
            padding: 6px 8px;
            background: #0a0c14;
            border: 1px solid #1e2130;
            border-left: 2px solid #7b5bf5;
            border-radius: 4px;
            font-size: 0.7rem;
            color: #999;
            line-height: 1.5;
            animation: slideDown var(--anim-duration) var(--anim-ease);
        }
        .src-fragment-inline .src-phrase {
            display: block;
            padding: 3px 0;
            cursor: pointer;
            border-bottom: 1px solid #1a1d27;
            transition: color 0.15s;
        }
        .src-fragment-inline .src-phrase:last-child { border-bottom: none; }
        .src-fragment-inline .src-phrase:hover { color: #7b5bf5; }
        @media (max-width: 600px) {
            .card-info-tooltip { width: 200px; right: -10px; }
        }

        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }

        .badge-OFFER      { background: #1a3a5c; color: #5ba3f5; }
        .badge-INQUIRY    { background: #1a3a2a; color: #5bf5a3; }
        .badge-NEGOTIATION{ background: #3a2a1a; color: #f5a35b; }
        .badge-CLOSING    { background: #2a1a3a; color: #a35bf5; }
        .badge-DESCRIPTION{ background: #1a2a3a; color: #5bd4f5; }
        .badge-UNKNOWN    { background: #2a2a2a; color: #888; }
        .badge-POSITIVE   { background: #1a3a2a; color: #5bf5a3; }
        .badge-NEUTRAL    { background: #2a2a2a; color: #aaa; }
        .badge-NEGATIVE   { background: #3a1a1a; color: #f55b5b; }

        .confidence {
            font-size: 0.8rem;
            color: #666;
            margin-top: 6px;
        }

        .conf-bar {
            height: 4px;
            background: #2a2d3a;
            border-radius: 2px;
            margin-top: 4px;
            overflow: hidden;
        }

        .conf-fill {
            height: 100%;
            background: #4a6cf7;
            border-radius: 2px;
            transition: width 0.5s ease;
        }

        .concept-list { list-style: none; }

        .concept-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 5px 0;
            border-bottom: 1px solid #1e2130;
            font-size: 0.85rem;
        }

        .concept-item:last-child { border-bottom: none; }

        .concept-name { color: #c0c0c0; }

        .concept-conf {
            font-size: 0.75rem;
            color: #666;
            background: #0f1117;
            padding: 2px 8px;
            border-radius: 10px;
        }

        .entity-item {
            padding: 6px 0;
            border-bottom: 1px solid #1e2130;
            font-size: 0.85rem;
        }

        .entity-item:last-child { border-bottom: none; }

        .entity-concept {
            font-size: 0.7rem;
            text-transform: uppercase;
            color: #4a6cf7;
            font-weight: 600;
        }

        .entity-value { color: #e0e0e0; margin-top: 2px; }

        .entity-numeric { color: #5bf5a3; font-size: 0.8rem; }

        /* Grouped entity styles */
        .entity-group {
            padding: 8px 0;
            border-bottom: 1px solid #1e2130;
        }
        .entity-group:last-child { border-bottom: none; }
        .entity-group-header {
            font-size: 0.72rem;
            text-transform: uppercase;
            color: #4a6cf7;
            letter-spacing: 0.04em;
            margin-bottom: 5px;
            font-weight: 600;
        }
        .entity-group-values {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }
        .entity-value-chip {
            display: inline-block;
            background: #111828;
            border: 1px solid #1e2a40;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 0.78rem;
            color: #e0e0e0;
        }
        .entity-value-chip .entity-numeric {
            color: #5bf5a3;
            font-size: 0.78rem;
        }
        .entity-count-badge {
            background: #4a6cf7;
            color: #fff;
            font-size: 0.6rem;
            font-weight: 700;
            padding: 1px 5px;
            border-radius: 8px;
            margin-left: 4px;
        }
        .entity-clickable {
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
        }
        .entity-clickable:hover {
            border-color: #4a6cf7;
            background: #1a2a4a;
        }

        /* Extended data extraction styles */
        .ext-data-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 6px;
            margin: 12px 0;
            padding-top: 10px;
            border-top: 1px solid #1e2130;
        }
        .ext-data-pill {
            background: #0d0f18;
            border: 1px solid #1e2130;
            border-radius: 8px;
            padding: 8px 10px;
            text-align: center;
        }
        .ext-pill-label {
            display: block;
            font-size: 0.6rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 3px;
        }
        .ext-pill-value {
            display: block;
            font-size: 0.75rem;
            color: #e0e0e0;
            font-weight: 600;
        }
        .ext-data-row {
            margin-top: 10px;
            padding: 8px 10px;
            background: #0a0c14;
            border-radius: 6px;
            border: 1px solid #1a1d2e;
        }
        .ext-row-label {
            display: block;
            font-size: 0.68rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 5px;
            font-weight: 600;
        }
        .ext-row-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }
        .ext-tag {
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.68rem;
        }
        .ext-tag-green { background: #0d2818; color: #5bf5a3; border: 1px solid #1a4a2a; }
        .ext-tag-red { background: #2a0d0d; color: #f55b5b; border: 1px solid #4a1a1a; }
        .ext-tag-purple { background: #1a0d2a; color: #a35bf5; border: 1px solid #2a1a4a; }
        .ext-tag-blue { background: #0d1a2a; color: #5b9ef5; border: 1px solid #1a2a4a; }
        .ext-row-questions {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .ext-question {
            font-size: 0.72rem;
            color: #aaa;
            font-style: italic;
            padding: 3px 8px;
            background: #111320;
            border-radius: 4px;
            border-left: 2px solid #4a6cf7;
        }
        .ext-summary-row { border-left: 3px solid #4a6cf7; }
        .ext-summary-text {
            font-size: 0.76rem;
            color: #ccc;
            line-height: 1.5;
        }
        .ext-action-row { border-left: 3px solid #5bf5a3; background: #0a140a; }
        .ext-action-text {
            font-size: 0.78rem;
            color: #5bf5a3;
            font-weight: 500;
            line-height: 1.4;
        }

        /* Clickable pills and detail panels */
        .ext-pill-clickable {
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
            position: relative;
        }
        .ext-pill-clickable:hover {
            border-color: #4a6cf7;
            background: #111828;
        }
        .ext-pill-arrow {
            display: block;
            font-size: 0.55rem;
            color: #555;
            margin-top: 3px;
            transition: color 0.2s;
        }
        .ext-pill-clickable:hover .ext-pill-arrow { color: #4a6cf7; }

        .ext-detail-panel {
            display: none;
            margin-top: 8px;
            padding: 14px;
            background: #0a0c14;
            border: 1px solid #1e2a40;
            border-radius: 10px;
            border-left: 3px solid #4a6cf7;
            animation: slideDown var(--anim-duration) var(--anim-ease);
        }
        .ext-detail-panel.open { display: block; }

        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .ext-detail-header {
            font-size: 0.82rem;
            color: #e0e0e0;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid #1e2130;
        }
        .ext-detail-progress {
            height: 6px;
            background: #1a1d2e;
            border-radius: 3px;
            margin-bottom: 8px;
            overflow: hidden;
        }
        .ext-detail-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #4a6cf7, #5bf5a3);
            border-radius: 3px;
            transition: width 0.5s ease;
        }
        .ext-progress-urgencia {
            background: linear-gradient(90deg, #5bf5a3, #f5a35b, #f55b5b);
        }
        .ext-progress-compromiso {
            background: linear-gradient(90deg, #555, #f5a35b, #5bf5a3);
        }
        .ext-detail-stages {
            display: flex;
            justify-content: space-between;
            margin-bottom: 12px;
            padding: 0 2px;
        }
        .ext-detail-stages span {
            font-size: 0.62rem;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            padding: 2px 6px;
            border-radius: 4px;
        }
        .ext-detail-stages .stage-active {
            color: #4a6cf7;
            background: #111828;
            font-weight: 700;
            border: 1px solid #4a6cf7;
        }
        .ext-detail-body {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .ext-detail-desc {
            font-size: 0.78rem;
            color: #ccc;
            line-height: 1.5;
        }
        .ext-detail-item {
            font-size: 0.73rem;
            color: #aaa;
            line-height: 1.4;
            padding: 6px 10px;
            background: #0d1018;
            border-radius: 6px;
        }
        .ext-detail-item strong {
            color: #ddd;
        }

        .empty-msg { color: #555; font-size: 0.85rem; font-style: italic; }

        /* Collapsible card styles */
        .card-title-collapsible {
            cursor: pointer;
            user-select: none;
            transition: color 0.2s;
        }
        .card-title-collapsible:hover {
            color: #4a6cf7;
        }
        .card-arrow {
            font-size: 0.65rem;
            color: #555;
            transition: transform 0.3s, color 0.2s;
            display: inline-block;
        }
        .card-title-collapsible:hover .card-arrow { color: #4a6cf7; }
        .card-arrow.open { transform: rotate(180deg); }
        .card-collapsible-content {
            display: block;
            animation: slideDown var(--anim-duration) var(--anim-ease);
        }
        .card-collapsible-content.closed { display: none; }

        /* Intent detail panel styles */
        .intent-detail-panel {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #1e2130;
        }
        .intent-detail-header {
            font-size: 0.9rem;
            color: #e0e0e0;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .intent-detail-desc {
            font-size: 0.78rem;
            color: #aaa;
            line-height: 1.5;
            margin-bottom: 12px;
        }
        .intent-detail-section {
            margin-bottom: 10px;
            padding: 10px;
            background: #0a0c14;
            border-radius: 8px;
            border: 1px solid #1a1d2e;
        }
        .intent-section-title {
            font-size: 0.7rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 5px;
            font-weight: 600;
        }
        .intent-section-text {
            font-size: 0.76rem;
            color: #ccc;
            line-height: 1.5;
        }
        .intent-seller-box {
            border-left: 3px solid #4a6cf7;
        }
        .intent-tips-list {
            margin: 0;
            padding-left: 18px;
            list-style: none;
        }
        .intent-tips-list li {
            font-size: 0.74rem;
            color: #bbb;
            line-height: 1.6;
            position: relative;
            padding-left: 4px;
        }
        .intent-tips-list li::before {
            content: "•";
            color: #4a6cf7;
            font-weight: bold;
            position: absolute;
            left: -14px;
        }
        .intent-next-step {
            border-left: 3px solid #5bf5a3;
            background: #0a140a;
        }
        .intent-next-step .intent-section-text {
            color: #5bf5a3;
            font-weight: 500;
        }

        /* Concepts detail panel styles */
        .concepts-detail-panel {
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #1e2130;
        }
        .concepts-detail-title {
            font-size: 0.7rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 10px;
            font-weight: 600;
        }
        .concept-detail-item {
            margin-bottom: 10px;
            padding: 10px;
            background: #0a0c14;
            border-radius: 8px;
            border: 1px solid #1a1d2e;
            border-left: 3px solid #4a6cf7;
        }
        .concept-detail-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
            font-size: 0.8rem;
            color: #e0e0e0;
        }
        .concept-conf {
            font-size: 0.7rem;
            color: #4a6cf7;
            background: #111828;
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid #1e2a40;
        }
        .concept-detail-desc {
            font-size: 0.73rem;
            color: #aaa;
            margin-bottom: 4px;
        }
        .concept-detail-source {
            font-size: 0.7rem;
            color: #777;
            margin-bottom: 6px;
            padding: 4px 8px;
            background: #0d1018;
            border-radius: 4px;
        }
        .concept-detail-source em {
            color: #999;
        }
        .concept-detail-tip {
            font-size: 0.73rem;
            color: #5bf5a3;
            padding: 6px 8px;
            background: #0a140a;
            border-radius: 4px;
            border-left: 2px solid #5bf5a3;
        }

        .full-width { grid-column: 1 / -1; }

        .error-card {
            background: #2a1a1a;
            border: 1px solid #5a2a2a;
            border-radius: 10px;
            padding: 16px;
            color: #f55b5b;
        }

        .timestamp { color: #444; font-size: 0.75rem; margin-top: 14px; text-align: right; }

        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }

        .user-info {
            font-size: 0.8rem;
            color: #555;
        }

        .user-info strong { color: #888; }

        .btn-logout {
            font-size: 0.75rem;
            padding: 4px 12px;
            background: #2a2d3a;
            color: #888;
            border: 1px solid #3a3d4a;
            border-radius: 6px;
            cursor: pointer;
            text-decoration: none;
            transition: opacity 0.2s;
        }

        .btn-logout:hover { opacity: 0.75; }

        .input-preview {
            background: #0f1117;
            border-left: 3px solid #4a6cf7;
            padding: 8px 12px;
            border-radius: 0 6px 6px 0;
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 14px;
            word-break: break-word;
        }

        /* Commercial analysis section */
        .commercial-section {
            background: #1a1d27;
            border: 1px solid #2a2d3a;
            border-radius: 10px;
            padding: 20px;
            margin-top: 14px;
        }

        .commercial-title {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #666;
            margin-bottom: 16px;
        }

        .lead-badge {
            display: inline-block;
            padding: 6px 18px;
            border-radius: 20px;
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 16px;
        }

        .lead-CALIENTE { background: #3a1a1a; color: #f55b5b; border: 1px solid #f55b5b; }
        .lead-TIBIO    { background: #3a2a1a; color: #f5a35b; border: 1px solid #f5a35b; }
        .lead-FRIO     { background: #1a2a3a; color: #5bd4f5; border: 1px solid #5bd4f5; }

        .prob-bar-container {
            margin-bottom: 16px;
        }

        .prob-label {
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            color: #888;
            margin-bottom: 4px;
        }

        .prob-value {
            font-size: 1.4rem;
            font-weight: 700;
            color: #ffffff;
        }

        .prob-bar {
            height: 8px;
            background: #2a2d3a;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 6px;
        }

        .prob-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.6s ease;
        }

        .prob-fill-hot  { background: linear-gradient(90deg, #f55b5b, #ff8c00); }
        .prob-fill-warm { background: linear-gradient(90deg, #f5a35b, #f5d05b); }
        .prob-fill-cold { background: linear-gradient(90deg, #5bd4f5, #4a6cf7); }

        .indicators-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
            gap: 10px;
            margin-bottom: 16px;
        }

        .indicator-item {
            background: #0f1117;
            border: 1px solid #2a2d3a;
            border-radius: 8px;
            padding: 10px 12px;
            text-align: center;
        }

        .indicator-label {
            font-size: 0.65rem;
            text-transform: uppercase;
            color: #555;
            letter-spacing: 0.06em;
            margin-bottom: 4px;
        }

        .indicator-value {
            font-size: 1.3rem;
            font-weight: 700;
            color: #e0e0e0;
        }

        .indicator-value.highlight { color: #f55b5b; }
        .indicator-value.positive  { color: #5bf5a3; }

        .recomendacion-box {
            background: #0f1117;
            border-left: 3px solid #4a6cf7;
            padding: 10px 14px;
            border-radius: 0 8px 8px 0;
            font-size: 0.85rem;
            color: #c0c0c0;
            line-height: 1.5;
        }

        /* Expandable indicator cards */
        .indicator-item {
            background: #0f1117;
            border: 1px solid #2a2d3a;
            border-radius: 8px;
            padding: 10px 12px;
            text-align: center;
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
            position: relative;
        }

        .indicator-item:hover {
            border-color: #4a6cf7;
            background: #141720;
        }

        .indicator-item.has-detail::after {
            content: '▼';
            position: absolute;
            bottom: 4px;
            right: 6px;
            font-size: 0.55rem;
            color: #444;
        }

        .indicator-item.expanded::after { content: '▲'; }

        .indicator-detail {
            display: none;
            background: #0a0c14;
            border: 1px solid #2a2d3a;
            border-top: none;
            border-radius: 0 0 8px 8px;
            padding: 8px 12px;
            margin-top: -4px;
            text-align: left;
        }

        .indicator-detail.open {
            display: block;
            animation: slideDown var(--anim-duration) var(--anim-ease);
        }

        .detail-word-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 3px 0;
            border-bottom: 1px solid #1a1d27;
            font-size: 0.8rem;
        }

        .detail-word-row:last-child { border-bottom: none; }

        .detail-word-clickable {
            cursor: pointer;
            border-radius: 4px;
            padding: 3px 6px !important;
            transition: background 0.15s;
        }

        .detail-word-clickable:hover {
            background: #1a1d27;
        }

        .detail-word { color: #c0c0c0; }

        .detail-count {
            background: #1a2a3a;
            color: #5bd4f5;
            padding: 1px 8px;
            border-radius: 10px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .detail-empty {
            color: #444;
            font-size: 0.75rem;
            font-style: italic;
        }

        /* Lead detail panel */
        .lead-detail-panel {
            display: none;
            background: #0a0c14;
            border: 1px solid #2a2d3a;
            border-radius: 0 0 10px 10px;
            padding: 16px;
            margin-top: -2px;
        }

        .lead-detail-panel.open {
            display: block;
            animation: slideDown var(--anim-duration) var(--anim-ease);
        }

        .formula-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
            margin-bottom: 14px;
        }

        .formula-table td {
            padding: 5px 8px;
            border-bottom: 1px solid #1a1d27;
            color: #c0c0c0;
        }

        .formula-table td:last-child {
            text-align: right;
            font-weight: 600;
        }

        .formula-table .positive-row td:last-child { color: #5bf5a3; }
        .formula-table .negative-row td:last-child { color: #f55b5b; }
        .formula-table .total-row td {
            border-top: 2px solid #2a2d3a;
            border-bottom: none;
            font-weight: 700;
            color: #ffffff;
        }

        .formula-result {
            background: #0f1117;
            border: 1px solid #2a2d3a;
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 0.82rem;
            color: #888;
            margin-bottom: 10px;
        }

        .formula-result strong { color: #e0e0e0; }

        .lead-gap {
            font-size: 0.8rem;
            padding: 8px 12px;
            border-radius: 8px;
            margin-top: 8px;
        }

        .lead-gap-caliente { background: #1a3a1a; color: #5bf5a3; }
        .lead-gap-tibio    { background: #3a2a1a; color: #f5a35b; }
        .lead-gap-frio     { background: #1a2a3a; color: #5bd4f5; }

        /* Lead extended panel styles */
        .lead-extended-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 8px;
            margin-bottom: 14px;
        }
        .lead-ext-card {
            background: #111320;
            border: 1px solid #222;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
        }
        .lead-ext-card-title {
            font-size: 0.65rem;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 4px;
        }
        .lead-ext-card-value {
            font-size: 0.8rem;
            color: #e0e0e0;
            font-weight: 600;
        }
        .lead-extended-item {
            margin-bottom: 12px;
            padding: 10px;
            background: #0d0f18;
            border-radius: 8px;
            border: 1px solid #1a1d2e;
        }
        .lead-ext-label {
            display: block;
            font-size: 0.72rem;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .lead-ext-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }
        .tag-green {
            background: #0d2818;
            color: #5bf5a3;
            border: 1px solid #1a4a2a;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
        }
        .tag-red {
            background: #2a0d0d;
            color: #f55b5b;
            border: 1px solid #4a1a1a;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
        }
        .tag-purple {
            background: #1a0d2a;
            color: #a35bf5;
            border: 1px solid #2a1a4a;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
        }
        .tag-blue {
            background: #0d1a2a;
            color: #5b9ef5;
            border: 1px solid #1a2a4a;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.7rem;
        }
        .lead-ext-list {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .lead-question {
            font-size: 0.75rem;
            color: #aaa;
            font-style: italic;
            padding: 4px 8px;
            background: #111320;
            border-radius: 4px;
            border-left: 2px solid #4a6cf7;
        }
        .lead-ext-summary {
            font-size: 0.78rem;
            color: #ccc;
            line-height: 1.5;
        }
        .lead-next-action {
            border: 1px solid #2a4a1a;
            background: #0d1a0d;
        }
        .lead-ext-action {
            font-size: 0.8rem;
            color: #5bf5a3;
            font-weight: 500;
            line-height: 1.4;
        }
        .lead-formula-section {
            margin-top: 14px;
            padding-top: 14px;
            border-top: 1px solid #222;
        }

        /* ── History Section ── */
        .history-section {
            background: #1a1d27;
            border: 1px solid #2a2d3a;
            border-radius: 10px;
            padding: 20px;
            margin-top: 24px;
        }

        .history-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            cursor: pointer;
        }

        .history-title {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #666;
        }

        .history-toggle {
            font-size: 0.7rem;
            color: #444;
        }

        .history-tree { display: none; }
        .history-tree.open { display: block; }

        .history-year {
            margin-bottom: 12px;
        }

        .history-year-label {
            font-size: 0.8rem;
            font-weight: 700;
            color: #888;
            padding: 4px 0;
            border-bottom: 1px solid #2a2d3a;
            margin-bottom: 8px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
        }

        .history-month {
            margin-left: 12px;
            margin-bottom: 8px;
        }

        .history-month-label {
            font-size: 0.75rem;
            font-weight: 600;
            color: #666;
            cursor: pointer;
            padding: 3px 0;
            display: flex;
            justify-content: space-between;
        }

        .history-week {
            margin-left: 12px;
            margin-bottom: 6px;
        }

        .history-week-label {
            font-size: 0.7rem;
            color: #555;
            cursor: pointer;
            padding: 2px 0;
            display: flex;
            justify-content: space-between;
        }

        .history-day {
            margin-left: 12px;
        }

        .history-day-label {
            font-size: 0.68rem;
            color: #444;
            padding: 2px 0;
            font-weight: 600;
        }

        .history-entry {
            background: #0f1117;
            border: 1px solid #1e2130;
            border-radius: 8px;
            padding: 10px 12px;
            margin: 4px 0 4px 12px;
            cursor: pointer;
            transition: border-color 0.2s;
        }

        .history-entry:hover { border-color: #4a6cf7; }

        .history-entry-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }

        .history-entry-badges {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }

        .history-entry-time {
            font-size: 0.68rem;
            color: #444;
        }

        .history-entry-text {
            font-size: 0.78rem;
            color: #777;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .source-badge {
            font-size: 0.65rem;
            padding: 2px 7px;
            border-radius: 10px;
            font-weight: 600;
        }

        .source-text  { background: #1a2a3a; color: #5bd4f5; }
        .source-audio { background: #2a1a3a; color: #a35bf5; }

        .history-empty {
            color: #444;
            font-size: 0.82rem;
            font-style: italic;
            text-align: center;
            padding: 20px 0;
        }

        .history-entry-detail {
            display: none;
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid #1e2130;
            font-size: 0.78rem;
            color: #888;
            line-height: 1.6;
        }

        .history-entry-detail.open { display: block; }

        /* ═══════════════════════════════════════════════════════════════
           RESPONSIVE LAYOUT ENGINE
           Breakpoints: mobile-S ≤400 · mobile ≤480 · tablet ≤768 ·
                        laptop ≤1200 · desktop (default) · TV ≥1600
           Fluid scaling via clamp() + auto-wrapping grids.
           ═══════════════════════════════════════════════════════════════ */

        /* Fluid base: container width and body font scale with the viewport */
        .container {
            width: 100%;
            max-width: 900px;
            padding-left: clamp(8px, 2vw, 20px);
            padding-right: clamp(8px, 2vw, 20px);
        }

        /* Date selectors: fluid columns that wrap automatically on any screen */
        .date-selectors { row-gap: 10px; }
        .date-select-group select,
        #selectFecha { width: 100%; }

        /* ── TABLET (≤768px) ── */
        @media (max-width: 768px) {
            .container { padding: 10px; max-width: 100%; }
            .top-bar { flex-direction: column; gap: 8px; align-items: stretch; }
            .btn-row { flex-wrap: wrap; gap: 6px; }
            .btn-row button, .btn-row input { font-size: 0.8rem; }
            textarea { font-size: 0.85rem; min-height: 150px; }
            .result-grid { grid-template-columns: 1fr; gap: 10px; }
            .indicators-grid { grid-template-columns: repeat(3, 1fr); gap: 6px; }
            .commercial-section { padding: 12px; }
            /* Date selectors: 2 per row on tablet */
            .date-selectors { gap: 10px; }
            .date-select-group { flex: 1 1 calc(50% - 10px); min-width: 120px; }
            .date-select-group select, #selectFecha { font-size: 0.82rem; min-width: 0; }
            .date-select-group label { font-size: 0.7rem; }
            .save-name-input { font-size: 0.8rem; }
            .card { padding: 12px; }
            .card-title { font-size: 0.7rem; }
        }

        /* ── MOBILE (≤480px) ── */
        @media (max-width: 480px) {
            /* On phones use x1.5 base (1600 * 1.5 = 2400ms) for a snappier feel. */
            :root { --anim-duration: 2400ms; }
            body { font-size: 13px; }
            .container { padding: 8px; }
            .top-bar { padding: 8px; }
            h1 { font-size: 1.15rem; }
            .subtitle { font-size: 0.8rem; }
            textarea { font-size: 0.85rem; min-height: 260px; }
            .btn-row { flex-direction: column; }
            .btn-row button { width: 100%; padding: 10px; }
            .btn-row input { width: 100%; margin-left: 0 !important; }
            .result-grid { grid-template-columns: 1fr; }
            .indicators-grid { grid-template-columns: repeat(2, 1fr); gap: 4px; }
            .indicator-item { padding: 6px 4px; }
            .indicator-label { font-size: 0.6rem; }
            .indicator-value { font-size: 1rem; }
            .commercial-title { font-size: 0.85rem; }
            /* Date selectors: each on its own full-width row so nothing is clipped */
            .date-selectors { gap: 8px; }
            .date-select-group { flex: 1 1 100%; min-width: 0; width: 100%; }
            .date-select-group select, #selectFecha { width: 100%; font-size: 0.85rem; min-width: 0; box-sizing: border-box; }
            .card { padding: 10px; border-radius: 8px; }
            .card-title { font-size: 0.68rem; }
            .badge { font-size: 0.75rem; padding: 3px 8px; }
            .prob-bar-container { margin: 8px 0; }
            .save-relocate-panel { padding: 8px; }
            .save-relocate-selects { flex-direction: column; gap: 6px; }
            .save-relocate-selects select { width: 100%; }
            .save-relocate-selects button { width: 100%; }
            .highlight-define-row { flex-wrap: wrap; }
        }

        /* ── MOBILE-S (≤400px) — very small phones ── */
        @media (max-width: 400px) {
            body { font-size: 12px; }
            h1 { font-size: 1.05rem; }
            .indicators-grid { grid-template-columns: repeat(2, 1fr); }
            .btn-highlight-define { font-size: 0.72rem; padding: 7px 10px; }
        }

        /* ── LAPTOP (≤1200px) — keep comfortable width ── */
        @media (min-width: 769px) and (max-width: 1200px) {
            .container { max-width: 92%; }
        }

        /* ── TV / LARGE DISPLAYS (≥1600px) — scale everything up ── */
        @media (min-width: 1600px) {
            .container { max-width: 1300px; }
            body { font-size: 17px; }
            h1 { font-size: 2.1rem; }
            .subtitle { font-size: 1.05rem; }
            textarea { font-size: 1.05rem; }
            .card-title { font-size: 0.9rem; }
            .indicator-value { font-size: 1.6rem; }
        }
        @media (min-width: 2200px) {
            .container { max-width: 1700px; }
            body { font-size: 20px; }
            h1 { font-size: 2.6rem; }
        }

        /* Utility: prevent horizontal scroll on any device */
        html, body { overflow-x: hidden; max-width: 100%; }
        *, *::before, *::after { box-sizing: border-box; }

        /* ── Sales Simulator Styles ── */
        .sim-diff-btn {
            background: #1a1d27;
            border: 1px solid #2a2d3a;
            color: #ccc;
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 0.82rem;
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
        }
        .sim-diff-btn:hover {
            border-color: #4a6cf7;
            background: #1e2235;
        }
        .sim-diff-btn.active {
            border-color: #4a6cf7;
            background: #2a3a6a;
            color: #fff;
            font-weight: 600;
        }
        .sim-msg {
            margin-bottom: 8px;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.84rem;
            line-height: 1.4;
            max-width: 85%;
            word-wrap: break-word;
        }
        .sim-msg-client {
            background: rgba(91, 245, 163, 0.12);
            border: 1px solid rgba(91, 245, 163, 0.25);
            color: #a8f0c8;
            margin-right: auto;
        }
        .sim-msg-vendor {
            background: rgba(74, 108, 247, 0.12);
            border: 1px solid rgba(74, 108, 247, 0.25);
            color: #a8c4ff;
            margin-left: auto;
        }
        .sim-msg-system {
            background: rgba(245, 215, 91, 0.1);
            border: 1px solid rgba(245, 215, 91, 0.2);
            color: #f5d75b;
            text-align: center;
            font-size: 0.76rem;
            max-width: 100%;
        }
        .sim-typing {
            font-size: 0.76rem;
            color: #888;
            font-style: italic;
            padding: 6px 12px;
            animation: simPulse 1.2s infinite;
        }
        @keyframes simPulse {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 1; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="top-bar">
        <div>
            <h1>Analizador de Textos</h1>
            <p class="subtitle">Ventas y Bienes Raices &mdash; Analisis con Machine Learning <span style="font-size:0.7rem;font-weight:700;color:#4da3ff;background:rgba(77,163,255,0.12);padding:1px 7px;border-radius:8px;">v12.6 &middot; audio campana</span></p>
        </div>
        <div style="text-align:right;">
            <div class="user-info" style="margin-bottom:4px;">Usuario: <strong>{{ username }}</strong></div>
            <button id="soundToggleBtn" type="button" onclick="toggleUISound()" title="Activar/silenciar sonidos de interfaz" aria-label="Activar o silenciar sonidos de interfaz" style="font-size:0.75rem;padding:4px 10px;margin-right:6px;background:#2a2d3a;color:#888;border:1px solid #3a3d4a;border-radius:6px;cursor:pointer;">&#128266; Sonido</button>
            <a href="/logout" class="btn-logout">Cerrar sesion</a>
        </div>
    </div>

    <div class="input-section">
        <div class="date-selectors">
            {% if username in ['admin', 'Vanesa.Admin', 'Berna.Strauss', 'FedericoCeballos', 'MartinianoSosa'] %}
            <div class="date-select-group">
                <label for="selectUser">👤 Usuario</label>
                <select id="selectUser" onchange="loadSavedTexts(); loadAdminStats();" style="min-width:120px;">
                    <option value="">-- Todos --</option>
                    {% for u in all_users %}
                    <option value="{{ u }}">{{ u }}</option>
                    {% endfor %}
                </select>
            </div>
            {% endif %}
            <div class="date-select-group">
                <label for="selectYear">Año</label>
                <select id="selectYear" onchange="loadSavedTexts()">
                    <option value="2025">2025</option>
                    <option value="2026" selected>2026</option>
                    <option value="2027">2027</option>
                    <option value="2028">2028</option>
                    <option value="2029">2029</option>
                    <option value="2030">2030</option>
                </select>
            </div>
            <div class="date-select-group">
                <label for="selectMonth">Mes</label>
                <select id="selectMonth" onchange="loadSavedTexts()">
                    <option value="">-- Todos --</option>
                    <option value="1">Enero</option>
                    <option value="2">Febrero</option>
                    <option value="3">Marzo</option>
                    <option value="4">Abril</option>
                    <option value="5">Mayo</option>
                    <option value="6">Junio</option>
                    <option value="7">Julio</option>
                    <option value="8">Agosto</option>
                    <option value="9">Septiembre</option>
                    <option value="10">Octubre</option>
                    <option value="11">Noviembre</option>
                    <option value="12">Diciembre</option>
                </select>
            </div>
            <div class="date-select-group">
                <label for="selectFecha">Fecha</label>
                <input type="date" id="selectFecha" style="background:#0d0f18;color:#e0e0e0;border:1px solid #2a2d3e;border-radius:6px;padding:7px 10px;font-size:0.82rem;cursor:pointer;outline:none;min-width:120px;max-width:100%;box-sizing:border-box;">
            </div>
            <div class="date-select-group">
                <label for="selectText">Textos <span id="savedTextsCount" style="color:#555;"></span></label>
                <div style="display:flex;align-items:center;gap:6px;">
                    <select id="selectText" onchange="onTextSelected(this.value)" style="flex:1;">
                        <option value="">-- Seleccionar texto --</option>
                    </select>
                    <button id="deleteTextBtn" onclick="deleteSelectedText()" style="display:none;background:transparent;border:1px solid #f55b5b;color:#f55b5b;border-radius:6px;padding:5px 8px;font-size:0.75rem;cursor:pointer;white-space:nowrap;" title="Eliminar texto seleccionado">🗑️</button>
                </div>
            </div>
        </div>

        <div class="textarea-wrapper" id="textareaWrapper">
            <textarea id="textInput"
                placeholder="O escribe / pega aqui el texto que quieres analizar...&#10;&#10;Ejemplo: Ofrezco apartamento de 3 habitaciones en USD 180,000 negociable, zona norte, 95 m2."></textarea>
            <div class="highlight-overlay" id="highlightOverlay"></div>
            <button class="highlight-close-btn" id="highlightCloseBtn" onclick="closeHighlightOverlay()" title="Cerrar resaltado">✕</button>
        </div>
        <!-- Resaltar y Definir -->
        <div class="highlight-define-row" id="highlightDefineRow">
            <button class="btn-highlight-define" id="btnHighlightDefine" type="button">
                &#9998; Resaltar y definir <span style="font-size:0.6rem;opacity:0.5;">v4</span>
            </button>
            <span class="highlight-selection-info" id="highlightSelectionInfo"></span>
            <div class="category-popover" id="categoryPopover">
                <div class="category-popover-title">Selecciona una categoria</div>
                <div class="category-grid" id="categoryGrid"></div>
            </div>
        </div>
        <div class="btn-row">
            <button class="btn-primary" onclick="analyze()">&#128269; Analizar</button>
            <button class="btn-secondary" onclick="clearAll()">Limpiar</button>
            {% if username in ['admin', 'Vanesa.Admin', 'Berna.Strauss', 'FedericoCeballos', 'MartinianoSosa'] %}
            <input type="text" id="entryNameInput" class="save-name-input" placeholder="Titulo del texto (obligatorio para guardar)..." style="flex:1; margin-left:8px;">
            <button class="btn-save" onclick="saveEntry()">&#128190; Guardar</button>
            {% endif %}
        </div>
        <div class="loading" id="loading" style="margin-top:10px;">Analizando texto...</div>
    </div>

    <div class="results" id="results"></div>

    {% if username in ['admin', 'Vanesa.Admin', 'Berna.Strauss', 'FedericoCeballos', 'MartinianoSosa'] %}
    <!-- ── ADMIN STATS PANEL ── -->
    <div class="input-section" id="adminStatsPanel" style="margin-top:20px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
            <div style="font-size:0.85rem;font-weight:600;color:#b38bff;">📊 Panel de Seguimiento (Admin)</div>
            <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <select id="statsVendor" onchange="loadAdminStats()" style="background:#0d0f18;color:#e0e0e0;border:1px solid #2a2d3e;border-radius:6px;padding:6px 10px;font-size:0.8rem;">
                    <option value="_all">General (todos)</option>
                    {% for u in all_users %}
                    <option value="{{ u }}">{{ u }}</option>
                    {% endfor %}
                </select>
                <select id="statsMonth" onchange="onStatsMonthChange()" style="background:#0d0f18;color:#e0e0e0;border:1px solid #2a2d3e;border-radius:6px;padding:6px 10px;font-size:0.8rem;">
                    <option value="">Mes (todos)</option>
                    <option value="1">Enero</option>
                    <option value="2">Febrero</option>
                    <option value="3">Marzo</option>
                    <option value="4">Abril</option>
                    <option value="5">Mayo</option>
                    <option value="6">Junio</option>
                    <option value="7">Julio</option>
                    <option value="8">Agosto</option>
                    <option value="9">Septiembre</option>
                    <option value="10">Octubre</option>
                    <option value="11">Noviembre</option>
                    <option value="12">Diciembre</option>
                </select>
                <select id="statsPeriod" onchange="loadAdminStats()" style="background:#0d0f18;color:#e0e0e0;border:1px solid #2a2d3e;border-radius:6px;padding:6px 10px;font-size:0.8rem;">
                    <option value="mensual">Mensual</option>
                    <option value="bimestral">Bimestral</option>
                    <option value="trimestral">Trimestral</option>
                    <option value="cuatrimestral">Cuatrimestral</option>
                    <option value="semestral">Semestral</option>
                    <option value="anual" selected>Anual (Ene a hoy)</option>
                </select>
            </div>
        </div>
        <div id="adminStatsContent" style="display:flex;flex-wrap:wrap;gap:16px;justify-content:center;">
            <div style="color:#555;font-size:0.8rem;">Selecciona un usuario y periodo para ver estadisticas.</div>
        </div>
    </div>

    <!-- ── INFORME DE SEGUIMIENTO ── -->
    <div class="input-section" id="informePanel" style="margin-top:20px;">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
            <div style="font-size:0.85rem;font-weight:600;color:#5bf5a3;">&#128202; Informe de Seguimiento</div>
            <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                <select id="informePreset" onchange="applyInformePreset()" style="background:#101c2a;color:#5bd4f5;border:1px solid #2a3a4a;border-radius:6px;padding:6px 10px;font-size:0.78rem;font-weight:600;">
                    <option value="anual" selected>Enero a la fecha</option>
                    <option value="mes_actual">Mes en curso</option>
                    <option value="s1">Mes en curso · Semana 1</option>
                    <option value="s2">Mes en curso · Semana 2</option>
                    <option value="s3">Mes en curso · Semana 3</option>
                    <option value="s4">Mes en curso · Semana 4</option>
                    <option value="s12">Mes en curso · Primeras 2 semanas</option>
                    <option value="s123">Mes en curso · Primeras 3 semanas</option>
                    <option value="custom">Personalizado</option>
                </select>
                <select id="informeYear" onchange="loadInforme()" style="background:#0d0f18;color:#e0e0e0;border:1px solid #2a2d3e;border-radius:6px;padding:6px 10px;font-size:0.78rem;">
                    <option value="2026" selected>2026</option>
                    <option value="2025">2025</option>
                </select>
                <select id="informeMonth" onchange="_informeManualChange()" style="background:#0d0f18;color:#e0e0e0;border:1px solid #2a2d3e;border-radius:6px;padding:6px 10px;font-size:0.78rem;">
                    <option value="0">Todos los meses</option>
                    <option value="1">Enero</option><option value="2">Febrero</option><option value="3">Marzo</option>
                    <option value="4">Abril</option><option value="5">Mayo</option><option value="6">Junio</option>
                    <option value="7">Julio</option><option value="8">Agosto</option><option value="9">Septiembre</option>
                    <option value="10">Octubre</option><option value="11">Noviembre</option><option value="12">Diciembre</option>
                </select>
                <select id="informeWeek" onchange="_informeManualChange()" style="background:#0d0f18;color:#e0e0e0;border:1px solid #2a2d3e;border-radius:6px;padding:6px 10px;font-size:0.78rem;">
                    <option value="0">Todas las semanas</option>
                    <option value="1">Semana 1 (1-7)</option>
                    <option value="2">Semana 2 (8-14)</option>
                    <option value="3">Semana 3 (15-21)</option>
                    <option value="4">Semana 4 (22-31)</option>
                </select>
                <select id="informeSeller" onchange="loadInforme()" style="background:#0d0f18;color:#e0e0e0;border:1px solid #2a2d3e;border-radius:6px;padding:6px 10px;font-size:0.78rem;">
                    <option value="_all">Todos los vendedores</option>
                    {% for u in all_users %}
                    <option value="{{ u }}">{{ u }}</option>
                    {% endfor %}
                </select>
                <button onclick="printInforme()" style="background:#1a2a3a;color:#5bd4f5;border:1px solid #2a3a4a;border-radius:6px;padding:6px 12px;font-size:0.75rem;cursor:pointer;" title="Imprimir informe">&#128424; Imprimir</button>
            </div>
        </div>
        <div id="informeContent" style="font-size:0.78rem;color:#aaa;">Cargando informe...</div>
    </div>
    {% endif %}

    <!-- ── SALES SIMULATOR ── -->
    <div class="history-section" id="simulatorSection">
        <div class="history-header" onclick="toggleSimulator()">
            <div class="history-title">&#129302; Simulador de Ventas IA</div>
            <div class="history-toggle" id="simToggleIcon">&#9660; Abrir simulador</div>
        </div>
        <div id="simulatorPanel" style="display:none; padding: 16px;">
            <!-- Setup panel -->
            <div id="simSetup">
                <p style="font-size:0.82rem; color:#aaa; margin-bottom:12px;">Selecciona la dificultad del cliente simulado:</p>
                <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px;">
                    <button class="sim-diff-btn" data-level="facil" onclick="selectDifficulty('facil')">F&aacute;cil</button>
                    <button class="sim-diff-btn" data-level="mediano" onclick="selectDifficulty('mediano')">Mediano</button>
                    <button class="sim-diff-btn" data-level="dificil" onclick="selectDifficulty('dificil')">Dif&iacute;cil</button>
                    <button class="sim-diff-btn" data-level="muy_dificil" onclick="selectDifficulty('muy_dificil')">Muy Dif&iacute;cil</button>
                    <button class="sim-diff-btn" data-level="veterano" onclick="selectDifficulty('veterano')">Veterano</button>
                </div>
                <button id="simStartBtn" class="btn-primary" onclick="startSimulation()" disabled style="width:100%;">Iniciar Simulaci&oacute;n</button>
            </div>
            <!-- Chat panel -->
            <div id="simChat" style="display:none;">
                <div id="simMessages" style="height:320px; overflow-y:auto; background:#0f1117; border:1px solid #2a2d3a; border-radius:8px; padding:12px; margin-bottom:10px;"></div>
                <div style="display:flex; gap:8px;">
                    <input type="text" id="simInput" placeholder="Escribe tu mensaje de vendedor..." style="flex:1; background:#0f1117; border:1px solid #2a2d3a; border-radius:6px; color:#e0e0e0; padding:10px; font-size:0.88rem; outline:none;" onkeydown="if(event.key==='Enter')sendSimMessage()">
                    <button class="btn-primary" onclick="sendSimMessage()" style="padding:10px 18px;">Enviar</button>
                    <button class="btn-secondary" onclick="endSimulation()" style="padding:10px 14px;">Terminar</button>
                </div>
            </div>
            <!-- Feedback panel -->
            <div id="simFeedback" style="display:none; margin-top:14px;">
                <label style="font-size:0.8rem; color:#aaa; display:block; margin-bottom:6px;">&iquest;Qu&eacute; te pareci&oacute; la simulaci&oacute;n?</label>
                <textarea id="simFeedbackText" style="width:100%; height:16cm; background:#0f1117; border:1px solid #2a2d3a; border-radius:8px; color:#e0e0e0; padding:10px; font-size:0.85rem; resize:vertical; outline:none;" placeholder="Escribe tu feedback aqui..."></textarea>
                <button class="btn-save" onclick="submitFeedback()" style="margin-top:8px; width:100%;">Enviar Feedback</button>
            </div>
        </div>
    </div>
</div>

<script>
const INDICADOR_CATEGORIAS = {{ indicador_categorias_json | safe }};
let _lastCommercialData = null;
window._currentEntryName = '';
window._currentEntryId = '';
window._lastAnalysisData = {};
window._manualHighlights = [];
window._selectedTextForHighlight = '';

async function analyze() {
    const text = document.getElementById('textInput').value.trim();
    if (!text) return;

    const year = document.getElementById('selectYear').value;
    const month = document.getElementById('selectMonth').value;

    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, year: parseInt(year), month: parseInt(month) })
        });
        const data = await response.json();
        _lastCommercialData = data.commercial || null;
        // Update textarea with cleaned text (deduped)
        if (!data.error && data.input_text) {
            document.getElementById('textInput').value = data.input_text;
        }
        renderResults(data, data.input_text || text);
    } catch (e) {
        document.getElementById('results').innerHTML =
            '<div class="error-card">Error de conexion: ' + e.message + '</div>';
        document.getElementById('results').style.display = 'block';
    }

    document.getElementById('loading').style.display = 'none';
}

async function saveEntry() {
    const text = document.getElementById('textInput').value.trim();
    const entryName = document.getElementById('entryNameInput').value.trim();

    if (!text) { alert('Pega o escribe un texto primero.'); return; }
    if (!entryName) { alert('El titulo es obligatorio para guardar.'); return; }

    const year = document.getElementById('selectYear').value;
    const month = document.getElementById('selectMonth').value;

    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';

    try {
        // If admin has a user selected, save to that user
        const userSelect = document.getElementById('selectUser');
        const targetUser = userSelect ? userSelect.value : '';

        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, year: parseInt(year), month: parseInt(month), entry_name: entryName, target_user: targetUser, fecha: document.getElementById('selectFecha') ? document.getElementById('selectFecha').value : '', existing_entry_id: window._currentEntryId || '' })
        });
        const data = await response.json();
        _lastCommercialData = data.commercial || null;
        if (!data.error && data.input_text) {
            document.getElementById('textInput').value = data.input_text;
        }
        renderResults(data, data.input_text || text);

        // Scroll to top after saving
        window.scrollTo({ top: 0, behavior: 'smooth' });
        // Clear the title input
        document.getElementById('entryNameInput').value = '';
        // Refresh saved texts count
        loadSavedTexts();
        // Real-time sync: refresh the Annual Panel and admin stats after saving
        if (typeof loadInforme === 'function' && document.getElementById('informePanel')) {
            loadInforme();
        }
        if (typeof loadAdminStats === 'function' && document.getElementById('adminStatsPanel')) {
            loadAdminStats();
        }
    } catch (e) {
        document.getElementById('results').innerHTML =
            '<div class="error-card">Error de conexion: ' + e.message + '</div>';
        document.getElementById('results').style.display = 'block';
    }

    document.getElementById('loading').style.display = 'none';
}

function clearAll() {
    document.getElementById('textInput').value = '';
    document.getElementById('results').style.display = 'none';
    closeHighlightOverlay();
    clearManualHighlights();
    window._resaltarActivo = false;
    _lastCommercialData = null;
}

function confBar(value) {
    const pct = Math.round(value * 100);
    return `<div class="confidence">${pct}% confianza</div>
            <div class="conf-bar"><div class="conf-fill" style="width:${pct}%"></div></div>`;
}

// Translations for concept names
const SALES_CONCEPTS_ES = {
    'offer': 'Oferta',
    'discount': 'Descuento / Rebaja',
    'commission': 'Comision',
    'closing': 'Cierre de Venta',
    'prospect': 'Prospecto / Cliente',
    'objection': 'Objecion',
    'follow_up': 'Seguimiento',
    'negotiation': 'Negociacion'
};

const RE_CONCEPTS_ES = {
    'property_type': 'Tipo de Propiedad',
    'price': 'Precio',
    'area_sqm': 'Metraje / Area',
    'bedrooms': 'Habitaciones',
    'bathrooms': 'Banos',
    'location': 'Ubicacion',
    'amenities': 'Amenidades',
    'zoning': 'Zonificacion',
    'condition': 'Estado / Condicion'
};

const INTENT_ES = {
    'OFFER': 'OFERTA',
    'INQUIRY': 'CONSULTA',
    'NEGOTIATION': 'NEGOCIACION',
    'CLOSING': 'CIERRE',
    'DESCRIPTION': 'DESCRIPCION',
    'UNKNOWN': 'DESCONOCIDO'
};

const SENTIMENT_ES = {
    'POSITIVE': 'POSITIVO',
    'NEUTRAL': 'NEUTRAL',
    'NEGATIVE': 'NEGATIVO'
};

const ENTITY_ES = {
    'price': 'Precio',
    'area_sqm': 'Metraje',
    'bedrooms': 'Habitaciones',
    'bathrooms': 'Baños',
    'location': 'Ubicacion',
    'date': 'Fecha/Plazo',
    'schedule': 'Horario/Disponibilidad',
    'percentage': 'Porcentaje',
    'contact': 'Contacto',
    'action': 'Accion comprometida',
    'role': 'Persona/Rol',
    'condition': 'Condicion/Requisito'
};

const ENTITY_ICONS = {
    'price': '💰',
    'area_sqm': '📐',
    'bedrooms': '🛏️',
    'bathrooms': '🚿',
    'location': '📍',
    'date': '📅',
    'schedule': '🕐',
    'percentage': '📊',
    'contact': '📞',
    'action': '✅',
    'role': '👤',
    'condition': '📋'
};

function translateConcept(key, map) {
    return map[key] || key;
}

function renderResults(data, inputText) {
    const el = document.getElementById('results');
    window._lastInputText = inputText || '';
    window._lastAnalysisData = data || {};

    if (data.error) {
        const errorMessages = {
            'INPUT_TOO_SHORT': 'El texto es demasiado corto para analizar.',
            'INPUT_TOO_LONG': 'El texto supera el limite maximo permitido.',
            'INPUT_EMPTY': 'El texto no contiene contenido analizable.',
            'ANALYSIS_ERROR': 'Ocurrio un error durante el analisis.'
        };
        const msg = errorMessages[data.error_code] || data.error_message;
        el.innerHTML = `<div class="error-card"><strong>Error:</strong> ${msg}</div>`;
        el.style.display = 'block';
        return;
    }

    const preview = inputText.length > 100 ? inputText.substring(0, 100) + '...' : inputText;
    const intentEs = INTENT_ES[data.intent] || data.intent;
    const sentimentEs = SENTIMENT_ES[data.sentiment] || data.sentiment;

    let salesHtml = '';
    if (data.sales_concepts && data.sales_concepts.length > 0) {
        salesHtml = '<ul class="concept-list">' +
            data.sales_concepts.map(c =>
                `<li class="concept-item">
                    <span class="concept-name">${translateConcept(c.concept, SALES_CONCEPTS_ES)}</span>
                    <span class="concept-conf">${Math.round(c.confidence*100)}%</span>
                </li>`
            ).join('') + '</ul>';
    } else {
        salesHtml = '<span class="empty-msg">Ninguno detectado</span>';
    }

    let reHtml = '';
    if (data.real_estate_concepts && data.real_estate_concepts.length > 0) {
        reHtml = '<ul class="concept-list">' +
            data.real_estate_concepts.map(c =>
                `<li class="concept-item">
                    <span class="concept-name">${translateConcept(c.concept, RE_CONCEPTS_ES)}</span>
                    <span class="concept-conf">${Math.round(c.confidence*100)}%</span>
                </li>`
            ).join('') + '</ul>';
    } else {
        reHtml = '<span class="empty-msg">Ninguno detectado</span>';
    }

    let entitiesHtml = '';
    if (data.entities && data.entities.length > 0) {
        // Group entities by concept
        const grouped = {};
        data.entities.forEach(e => {
            if (!grouped[e.concept]) grouped[e.concept] = [];
            grouped[e.concept].push(e);
        });

        // Render order: core first, then extended
        const order = ['price', 'area_sqm', 'bedrooms', 'bathrooms', 'location', 'date', 'schedule', 'percentage', 'contact', 'action', 'role', 'condition'];
        const sortedKeys = Object.keys(grouped).sort((a, b) => {
            const ia = order.indexOf(a), ib = order.indexOf(b);
            return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
        });

        entitiesHtml = sortedKeys.map(concept => {
            const items = grouped[concept];
            const icon = ENTITY_ICONS[concept] || '📎';
            const label = translateConcept(concept, ENTITY_ES);

            // Group duplicate raw_values and count them
            const valueCounts = {};
            items.forEach(e => {
                const key = e.raw_value.toLowerCase().trim();
                if (!valueCounts[key]) {
                    valueCounts[key] = { entity: e, count: 0 };
                }
                valueCounts[key].count++;
            });

            const valuesHtml = Object.values(valueCounts).map(({entity: e, count}) => {
                let numStr = '';
                if (e.numeric_value !== null) {
                    numStr = ` → <span class="entity-numeric">${e.numeric_value.toLocaleString()}${e.unit ? ' ' + e.unit : ''}</span>`;
                }
                const countBadge = count > 1 ? ` <span class="entity-count-badge">${count}x</span>` : '';
                const safeValue = e.raw_value.replace(/'/g, "\\\\'");
                return `<span class="entity-value-chip entity-clickable" onclick="highlightEntityInText('${safeValue}')">"${e.raw_value}"${numStr}${countBadge}</span>`;
            }).join('');
            return `<div class="entity-group">
                <div class="entity-group-header">${icon} ${label}</div>
                <div class="entity-group-values">${valuesHtml}</div>
            </div>`;
        }).join('');
    } else {
        entitiesHtml = '<span class="empty-msg">Ninguna detectada</span>';
    }

    // Build extended data section
    const c = data.commercial || {};
    let extDataHtml = '';
    if (c) {
        const funnelLabels = {
            'AWARENESS': '🔍 Conocimiento', 'CONSIDERATION': '⚖️ Evaluacion',
            'DECISION': '🎯 Decision', 'CLOSED': '✅ Cerrado'
        };
        const urgLabels = {
            'BAJA': '🟢 Baja', 'MEDIA': '🟡 Media', 'ALTA': '🟠 Alta', 'CRITICA': '🔴 Critica'
        };
        const compLabels = {
            'BAJO': '⬜ Bajo', 'MEDIO': '🟨 Medio', 'ALTO': '🟩 Alto'
        };
        const opLabels = {
            'VENTA': '🏷️ Compra-Venta', 'ALQUILER': '🔑 Alquiler',
            'INVERSION': '📈 Inversion', 'INDEFINIDO': '—'
        };
        const finLabels = {
            'CONTADO': '💵 Contado', 'CREDITO': '🏦 Credito',
            'FINANCIAMIENTO_DIRECTO': '🤝 Directo', 'NO_DETECTADO': '—'
        };

        // Build detailed explanations for each pill
        const funnelDetail = {
            'AWARENESS': {
                desc: 'El cliente esta en la etapa inicial. Aun no conoce bien la oferta ni ha mostrado interes concreto.',
                signals: 'No hay indicios de cierre ni respuestas afirmativas claras.',
                action: 'Presentar la propuesta de valor, generar interes y calificar al prospecto.',
                progress: 10
            },
            'CONSIDERATION': {
                desc: 'El cliente esta evaluando opciones activamente. Muestra interes pero aun no decide.',
                signals: 'Se detectan indicios de prospeccion, objeciones o respuestas positivas iniciales.',
                action: 'Resolver dudas, enviar comparables, mostrar beneficios diferenciadores.',
                progress: 50
            },
            'DECISION': {
                desc: 'El cliente esta muy cerca de tomar una decision. Las senales de cierre son claras.',
                signals: 'Indicios de cierre presentes, respuestas afirmativas y/o alta probabilidad.',
                action: 'Presentar propuesta final, crear urgencia y facilitar el cierre.',
                progress: 80
            },
            'CLOSED': {
                desc: 'La operacion esta cerrada o practicamente cerrada.',
                signals: 'Acuerdo alcanzado, firma realizada o precio final acordado.',
                action: 'Gestionar post-venta, solicitar referidos y mantener la relacion.',
                progress: 100
            }
        };

        const urgenciaDetail = {
            'BAJA': {
                desc: 'No se detectan senales de urgencia en el texto. El cliente no tiene prisa.',
                signals: 'Sin menciones de tiempo, plazos o inmediatez.',
                action: 'Crear urgencia con escasez o beneficios por tiempo limitado.',
                progress: 15
            },
            'MEDIA': {
                desc: 'Hay alguna senal de urgencia moderada. El cliente tiene cierta prisa.',
                signals: 'Menciones aisladas de tiempo o plazos.',
                action: 'Reforzar la urgencia y facilitar el proceso para no perder momentum.',
                progress: 45
            },
            'ALTA': {
                desc: 'Multiples senales de urgencia. El cliente necesita resolver pronto.',
                signals: 'Varias menciones de inmediatez, plazos cortos o necesidad rapida.',
                action: 'Actuar rapido, simplificar pasos y ofrecer solucion inmediata.',
                progress: 75
            },
            'CRITICA': {
                desc: 'Urgencia maxima. El cliente necesita una solucion ya.',
                signals: 'Multiples palabras de urgencia: hoy, ahora, urgente, inmediato.',
                action: 'Priorizar este lead. Responder de inmediato y cerrar hoy si es posible.',
                progress: 95
            }
        };

        const compromisoDetail = {
            'BAJO': {
                desc: 'El cliente muestra poco compromiso. Hay mas evasivas que confirmaciones.',
                signals: 'Frases como "tengo que pensar", "despues", "no estoy seguro".',
                action: 'No presionar. Nutrir con informacion y hacer seguimiento suave.',
                progress: 20
            },
            'MEDIO': {
                desc: 'Compromiso moderado. Hay senales positivas pero tambien dudas.',
                signals: 'Mezcla de confirmaciones y evasivas. Interes real pero con reservas.',
                action: 'Resolver las dudas especificas y reforzar los beneficios clave.',
                progress: 55
            },
            'ALTO': {
                desc: 'Alto compromiso. El cliente esta decidido y muestra disposicion clara.',
                signals: 'Multiples confirmaciones: "acepto", "listo", "de acuerdo", "vamos".',
                action: 'Aprovechar el momento. Facilitar el cierre y no agregar friccion.',
                progress: 90
            }
        };

        const operacionDetail = {
            'VENTA': {
                desc: 'Se trata de una operacion de compra-venta de inmueble.',
                signals: 'Palabras detectadas: venta, vender, comprar, adquirir.',
                action: 'Enfocar en precio, condiciones de pago y documentacion legal.',
                icon: '🏷️'
            },
            'ALQUILER': {
                desc: 'Se trata de una operacion de alquiler o arrendamiento.',
                signals: 'Palabras detectadas: alquiler, renta, arrendamiento, inquilino.',
                action: 'Enfocar en plazo, condiciones del contrato y garantias.',
                icon: '🔑'
            },
            'INVERSION': {
                desc: 'El cliente busca una oportunidad de inversion inmobiliaria.',
                signals: 'Palabras detectadas: inversion, invertir, rentabilidad, retorno.',
                action: 'Presentar numeros: ROI, rentabilidad, plusvalia y proyecciones.',
                icon: '📈'
            },
            'INDEFINIDO': {
                desc: 'No se pudo determinar el tipo de operacion con claridad.',
                signals: 'No se detectaron palabras clave de ningun tipo de operacion.',
                action: 'Preguntar directamente al cliente que tipo de operacion busca.',
                icon: '❓'
            }
        };

        const financDetail = {
            'CONTADO': {
                desc: 'El cliente menciona pago de contado o en efectivo.',
                signals: 'Palabras detectadas: contado, cash, efectivo, pago completo.',
                action: 'Ofrecer descuento por pago de contado. Agilizar el cierre.',
                icon: '💵'
            },
            'CREDITO': {
                desc: 'Se menciona financiamiento bancario o hipotecario.',
                signals: 'Palabras detectadas: credito, hipoteca, banco, prestamo, pre-aprobado.',
                action: 'Verificar pre-aprobacion, coordinar con el banco y ajustar plazos.',
                icon: '🏦'
            },
            'FINANCIAMIENTO_DIRECTO': {
                desc: 'Se menciona financiamiento directo del vendedor o pago en cuotas.',
                signals: 'Palabras detectadas: cuotas, facilidades de pago, plan de pago.',
                action: 'Definir condiciones: enganche, plazo, tasa y garantias.',
                icon: '🤝'
            },
            'NO_DETECTADO': {
                desc: 'No se detecto mencion de forma de pago o financiamiento.',
                signals: 'Sin palabras clave de financiamiento en el texto.',
                action: 'Preguntar al cliente como planea financiar la operacion.',
                icon: '—'
            }
        };

        const fd = funnelDetail[c.etapa_funnel] || funnelDetail['AWARENESS'];
        const ud = urgenciaDetail[c.urgencia] || urgenciaDetail['BAJA'];
        const cd = compromisoDetail[c.nivel_compromiso] || compromisoDetail['BAJO'];
        const od = operacionDetail[c.tipo_operacion] || operacionDetail['INDEFINIDO'];
        const fid = financDetail[c.financiamiento] || financDetail['NO_DETECTADO'];

        extDataHtml = `
            <div class="ext-data-grid">
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-funnel')">
                    <span class="ext-pill-label">Funnel</span>
                    <span class="ext-pill-value">${funnelLabels[c.etapa_funnel] || c.etapa_funnel || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-urgencia')">
                    <span class="ext-pill-label">Urgencia</span>
                    <span class="ext-pill-value">${urgLabels[c.urgencia] || c.urgencia || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-compromiso')">
                    <span class="ext-pill-label">Compromiso</span>
                    <span class="ext-pill-value">${compLabels[c.nivel_compromiso] || c.nivel_compromiso || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-operacion')">
                    <span class="ext-pill-label">Operacion</span>
                    <span class="ext-pill-value">${opLabels[c.tipo_operacion] || c.tipo_operacion || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-financ')">
                    <span class="ext-pill-label">Financiamiento</span>
                    <span class="ext-pill-value">${finLabels[c.financiamiento] || c.financiamiento || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-funnel">
                <div class="ext-detail-header">🎯 Etapa del Funnel: <strong>${c.etapa_funnel}</strong></div>
                <div class="ext-detail-progress"><div class="ext-detail-progress-fill" style="width:${fd.progress}%"></div></div>
                <div class="ext-detail-stages">
                    <span class="${c.etapa_funnel === 'AWARENESS' ? 'stage-active' : ''}">Awareness</span>
                    <span class="${c.etapa_funnel === 'CONSIDERATION' ? 'stage-active' : ''}">Consideration</span>
                    <span class="${c.etapa_funnel === 'DECISION' ? 'stage-active' : ''}">Decision</span>
                    <span class="${c.etapa_funnel === 'CLOSED' ? 'stage-active' : ''}">Closed</span>
                </div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${fd.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${fd.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${fd.action}</div>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-urgencia">
                <div class="ext-detail-header">⏱️ Nivel de Urgencia: <strong>${c.urgencia}</strong></div>
                <div class="ext-detail-progress"><div class="ext-detail-progress-fill ext-progress-urgencia" style="width:${ud.progress}%"></div></div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${ud.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${ud.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${ud.action}</div>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-compromiso">
                <div class="ext-detail-header">🤝 Nivel de Compromiso: <strong>${c.nivel_compromiso}</strong></div>
                <div class="ext-detail-progress"><div class="ext-detail-progress-fill ext-progress-compromiso" style="width:${cd.progress}%"></div></div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${cd.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${cd.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${cd.action}</div>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-operacion">
                <div class="ext-detail-header">${od.icon} Tipo de Operacion: <strong>${c.tipo_operacion}</strong></div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${od.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${od.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${od.action}</div>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-financ">
                <div class="ext-detail-header">${fid.icon} Financiamiento: <strong>${c.financiamiento.replace('_', ' ')}</strong></div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${fid.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${fid.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${fid.action}</div>
                </div>
            </div>
        `;

        // Señales de compra
        if (c.senales_compra && c.senales_compra.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">🛒 Senales de compra</span>
                <div class="ext-row-tags">${c.senales_compra.map(s => `<span class="ext-tag ext-tag-green">${s}</span>`).join('')}</div>
            </div>`;
        }

        // Objeciones específicas
        if (c.objeciones_especificas && c.objeciones_especificas.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">⚠️ Objeciones</span>
                <div class="ext-row-tags">${c.objeciones_especificas.map(o => `<span class="ext-tag ext-tag-red">${o}</span>`).join('')}</div>
            </div>`;
        }

        // Técnicas de persuasión
        if (c.tecnicas_persuasion && c.tecnicas_persuasion.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">🧠 Persuasion</span>
                <div class="ext-row-tags">${c.tecnicas_persuasion.map(t => `<span class="ext-tag ext-tag-purple">${t}</span>`).join('')}</div>
            </div>`;
        }

        // Preguntas abiertas
        if (c.preguntas_abiertas && c.preguntas_abiertas.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">❓ Preguntas abiertas</span>
                <div class="ext-row-questions">${c.preguntas_abiertas.map(q => `<div class="ext-question">"${q}"</div>`).join('')}</div>
            </div>`;
        }

        // Keywords
        if (c.keywords && c.keywords.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">🔑 Keywords</span>
                <div class="ext-row-tags">${c.keywords.map(k => `<span class="ext-tag ext-tag-blue">${k}</span>`).join('')}</div>
            </div>`;
        }

        // Resumen
        if (c.resumen) {
            extDataHtml += `<div class="ext-data-row ext-summary-row">
                <span class="ext-row-label">📋 Resumen del analisis</span>
                <div class="ext-summary-text">${c.resumen}</div>
            </div>`;
        }

        // Acción siguiente
        if (c.accion_siguiente) {
            extDataHtml += `<div class="ext-data-row ext-action-row">
                <span class="ext-row-label">&#9654;&#65039; Accion siguiente</span>
                <div class="ext-action-text">${c.accion_siguiente}</div>
            </div>`;
        }

        // --- Alertas del vendedor ---
        if (c.alertas_vendedor && c.alertas_vendedor.length > 0) {
            const alertColors = { CRITICA: '#f55b5b', ALTA: '#f5a35b', MEDIA: '#f5d75b', INFO: '#5bd4f5' };
            const alertBgs = { CRITICA: '#2a0d0d', ALTA: '#2a1a0d', MEDIA: '#2a2a0d', INFO: '#0d1a2a' };
            const alertBorders = { CRITICA: '#4a1a1a', ALTA: '#4a2a1a', MEDIA: '#4a4a1a', INFO: '#1a2a4a' };
            let alertasHtml = c.alertas_vendedor.map(a => {
                const color = alertColors[a.nivel] || '#aaa';
                const bg = alertBgs[a.nivel] || '#1a1d27';
                const border = alertBorders[a.nivel] || '#2a2d3a';
                let guiaHtml = '';
                if (a.guia && a.guia.tecnicas) {
                    guiaHtml = '<div style="margin-top:6px;padding:8px;background:#0a0c14;border-radius:6px;border-left:2px solid ' + color + ';">' +
                        '<div style="font-size:0.65rem;color:#888;font-weight:600;margin-bottom:4px;">' + (a.guia.titulo || 'Guia') + '</div>' +
                        a.guia.tecnicas.map(t => '<div style="font-size:0.68rem;color:#ccc;padding:2px 0;">&#8226; ' + t + '</div>').join('') +
                    '</div>';
                }
                return '<div style="padding:10px 12px;background:' + bg + ';border:1px solid ' + border + ';border-left:3px solid ' + color + ';border-radius:8px;margin-bottom:6px;">' +
                    '<div style="font-size:0.78rem;color:' + color + ';font-weight:600;">' + a.mensaje + '</div>' +
                    guiaHtml +
                '</div>';
            }).join('');
            extDataHtml += `<div class="ext-data-row" style="border-left:3px solid #f55b5b;background:#0d0a0a;">
                <span class="ext-row-label" style="color:#f55b5b;">&#128680; Alertas para el vendedor</span>
                ${alertasHtml}
            </div>`;
        }

        // --- Co-decisores ---
        if (c.es_multi_decisor && c.co_decisores && c.co_decisores.length > 0) {
            extDataHtml += `<div class="ext-data-row" style="border-left:3px solid #b38bff;">
                <span class="ext-row-label" style="color:#b38bff;">&#128101; Multi-decisor detectado</span>
                <div style="font-size:0.78rem;color:#ccc;margin-bottom:6px;">La decision de compra involucra a mas de una persona:</div>
                <div class="ext-row-tags">${c.co_decisores.map(d => '<span class="ext-tag ext-tag-purple">' + d + '</span>').join('')}</div>
                <div style="margin-top:6px;font-size:0.72rem;color:#b38bff;font-style:italic;">Tip: Proponer incluir al co-decisor en la proxima reunion.</div>
            </div>`;
        }

        // --- Rango presupuestario ---
        if (c.rango_presupuestario && c.rango_presupuestario !== 'NO_DETECTADO') {
            const rpLabels = { CONTADO: '&#128181; Contado', CREDITO: '&#127974; Credito', CUOTAS: '&#129309; Cuotas', ENTRADA: '&#128176; Entrada/Anticipo' };
            let detalleHtml = '';
            if (c.presupuesto_detalle && Object.keys(c.presupuesto_detalle).length > 0) {
                detalleHtml = Object.entries(c.presupuesto_detalle).map(([tipo, frases]) =>
                    '<div style="margin-top:4px;"><span style="font-size:0.65rem;color:#888;font-weight:600;">' + tipo + ':</span> ' +
                    frases.map(f => '<span class="ext-tag ext-tag-blue">' + f + '</span>').join(' ') + '</div>'
                ).join('');
            }
            extDataHtml += `<div class="ext-data-row" style="border-left:3px solid #5bf5a3;">
                <span class="ext-row-label" style="color:#5bf5a3;">&#128176; Rango presupuestario: ${rpLabels[c.rango_presupuestario] || c.rango_presupuestario}</span>
                ${detalleHtml}
            </div>`;
        }

        // --- Revisión coordinador ---
        if (c.requiere_revision_coordinador) {
            extDataHtml += `<div class="ext-data-row" style="border-left:3px solid #f5a35b;background:#1a1000;">
                <span class="ext-row-label" style="color:#f5a35b;">&#128209; Requiere revision del coordinador</span>
                <div style="font-size:0.78rem;color:#f5a35b;">${c.motivo_revision || 'Sin detalle'}</div>
            </div>`;
        }
    }

    // Build intent detail panel
    const intentDetail = {
        'OFFER': {
            icon: '🏷️',
            desc: 'El texto contiene una oferta activa. Alguien esta presentando una propiedad o servicio para la venta.',
            meaning: 'El emisor esta en modo de venta activa, presentando precio, condiciones o disponibilidad de un inmueble.',
            forSeller: 'Si eres el vendedor: tu mensaje esta bien posicionado como oferta. Asegurate de incluir precio, ubicacion y diferenciadores. Si eres el comprador: evalua si la oferta se ajusta a tus necesidades.',
            tips: ['Incluir precio claro y condiciones', 'Destacar beneficios unicos de la propiedad', 'Crear sentido de urgencia si es posible', 'Facilitar el siguiente paso (visita, llamada)'],
            nextStep: 'Esperar respuesta del prospecto. Si no responde en 24-48hs, hacer seguimiento.'
        },
        'INQUIRY': {
            icon: '❓',
            desc: 'El texto contiene preguntas o solicitudes de informacion. Alguien quiere saber mas.',
            meaning: 'El emisor esta interesado pero necesita mas datos antes de avanzar. Esta en etapa de evaluacion.',
            forSeller: 'El prospecto esta mostrando interes real. Cada pregunta es una oportunidad para acercarlo al cierre. Responde rapido y con informacion completa.',
            tips: ['Responder todas las preguntas de forma clara y completa', 'Agregar informacion adicional que anticipe futuras dudas', 'Incluir fotos, planos o documentos relevantes', 'Proponer una visita o llamada para profundizar'],
            nextStep: 'Responder con toda la informacion solicitada y proponer una accion concreta (visita, llamada).'
        },
        'NEGOTIATION': {
            icon: '⚖️',
            desc: 'El texto contiene elementos de negociacion. Se estan discutiendo terminos, precios o condiciones.',
            meaning: 'Las partes estan activamente negociando. Esto indica interes real y cercania al cierre.',
            forSeller: 'La negociacion es una senal muy positiva: el cliente quiere comprar, solo esta ajustando condiciones. No pierdas este momentum.',
            tips: ['Mantener firmeza en los puntos clave pero mostrar flexibilidad en secundarios', 'Ofrecer alternativas en vez de solo decir no', 'Crear urgencia: "esta oferta es valida hasta..."', 'Buscar el win-win para cerrar mas rapido'],
            nextStep: 'Presentar contraoferta o aceptar condiciones. No dejar pasar mas de 24hs sin responder.'
        },
        'CLOSING': {
            icon: '✅',
            desc: 'El texto indica que se esta cerrando o ya se cerro una operacion. Hay acuerdo entre las partes.',
            meaning: 'La venta esta practicamente cerrada. Se mencionan firmas, acuerdos finales o confirmaciones.',
            forSeller: 'Felicidades, estas en la recta final. Asegurate de que todos los documentos esten en orden y no haya sorpresas de ultimo momento.',
            tips: ['Confirmar todos los terminos por escrito', 'Coordinar firma y entrega de documentos', 'Preparar la documentacion legal necesaria', 'Planificar el seguimiento post-venta y solicitar referidos'],
            nextStep: 'Coordinar firma, verificar documentacion y planificar entrega. Solicitar referidos.'
        },
        'DESCRIPTION': {
            icon: '📝',
            desc: 'El texto es principalmente descriptivo. Detalla caracteristicas de una propiedad o situacion.',
            meaning: 'Se esta presentando informacion factual sobre un inmueble: metraje, habitaciones, ubicacion, amenidades.',
            forSeller: 'Las descripciones son la base de la venta. Asegurate de que sean atractivas, completas y destaquen los diferenciadores.',
            tips: ['Destacar los 3-5 beneficios principales primero', 'Usar numeros concretos (m2, habitaciones, precio)', 'Incluir la ubicacion y sus ventajas', 'Mencionar amenidades y valor agregado'],
            nextStep: 'Compartir la descripcion con prospectos calificados y medir el interes generado.'
        },
        'UNKNOWN': {
            icon: '🔍',
            desc: 'No se pudo determinar una intencion clara del texto con suficiente confianza.',
            meaning: 'El texto puede ser ambiguo, muy corto, o no encaja claramente en ninguna categoria de venta.',
            forSeller: 'El texto no tiene una intencion comercial clara. Puede ser una conversacion casual o un mensaje incompleto.',
            tips: ['Revisar si el texto esta completo', 'Buscar el contexto de la conversacion', 'Hacer preguntas para clarificar la intencion del interlocutor'],
            nextStep: 'Solicitar mas contexto o informacion al interlocutor.'
        }
    };

    const iDetail = intentDetail[data.intent] || intentDetail['UNKNOWN'];

    // Get the title: from input field (admin), from selected dropdown option, or from global var
    const entryNameInputEl = document.getElementById('entryNameInput');
    const selectTextEl = document.getElementById('selectText');
    let entryTitle = '';
    if (entryNameInputEl && entryNameInputEl.value.trim()) {
        entryTitle = entryNameInputEl.value.trim();
    } else if (window._currentEntryName) {
        entryTitle = window._currentEntryName;
    } else if (selectTextEl && selectTextEl.value) {
        const selOpt = selectTextEl.options[selectTextEl.selectedIndex];
        if (selOpt) entryTitle = selOpt.getAttribute('data-fullname') || selOpt.textContent || '';
    }
    const displayTitle = entryTitle || preview;

    el.innerHTML = `
        <div class="input-preview">"${displayTitle}"</div>
        <div class="result-grid">
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('intencion-content')">
                    Intencion del Texto &nbsp;<span class="card-arrow" id="intencion-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Clasifica la intencion principal del texto: si es una oferta, consulta, negociacion, cierre o descripcion. Ayuda a entender en que etapa de la venta esta la conversacion.</div>
                </div>
                <div class="card-collapsible-content closed" id="intencion-content">
                    <span class="badge badge-${data.intent}">${intentEs}</span>
                    ${confBar(data.intent_confidence)}
                    <div class="intent-detail-panel">
                        <div class="intent-detail-header">${iDetail.icon} ${intentEs}</div>
                        <div class="intent-detail-desc">${iDetail.desc}</div>
                        <div class="intent-detail-section">
                            <div class="intent-section-title">Que significa para la venta</div>
                            <div class="intent-section-text">${iDetail.meaning}</div>
                            <div class="src-toggle-inline" data-section="meaning">▼</div>
                            <div class="src-fragment-inline" style="display:none;"></div>
                        </div>
                        <div class="intent-detail-section intent-seller-box">
                            <div class="intent-section-title">👤 Para el vendedor</div>
                            <div class="intent-section-text">${iDetail.forSeller}</div>
                            <div class="src-toggle-inline" data-section="seller">▼</div>
                            <div class="src-fragment-inline" style="display:none;"></div>
                        </div>
                        <div class="intent-detail-section">
                            <div class="intent-section-title">💡 Tips practicos</div>
                            <ul class="intent-tips-list">
                                ${iDetail.tips.map(t => `<li>${t}</li>`).join('')}
                            </ul>
                            <div class="src-toggle-inline" data-section="tips">▼</div>
                            <div class="src-fragment-inline" style="display:none;"></div>
                        </div>
                        <div class="intent-detail-section intent-next-step">
                            <div class="intent-section-title">▶️ Siguiente paso</div>
                            <div class="intent-section-text">${iDetail.nextStep}</div>
                            <div class="src-toggle-inline" data-section="next">▼</div>
                            <div class="src-fragment-inline" style="display:none;"></div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('sentimiento-content')">
                    Sentimiento &nbsp;<span class="card-arrow" id="sentimiento-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Evalua el tono emocional del texto: positivo, neutral o negativo. Indica si el cliente esta contento, indiferente o insatisfecho con la propuesta.</div>
                </div>
                <div class="card-collapsible-content closed" id="sentimiento-content">
                    <span class="badge badge-${data.sentiment}">${sentimentEs}</span>
                    ${confBar(data.sentiment_confidence)}
                    ${renderSentimentDetail(data.sentiment)}
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('ventas-content')">
                    Conceptos de Ventas Detectados &nbsp;<span class="card-arrow" id="ventas-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Detecta conceptos del proceso de venta usando Machine Learning: ofertas, descuentos, comisiones, cierres, prospectos, objeciones, seguimiento y negociacion. El modelo analiza el 100% del texto buscando patrones y frases clave, extrae los fragmentos relevantes y calcula la confianza de cada deteccion. A mayor confianza, mas clara es la presencia del concepto en la conversacion.</div>
                </div>
                <div class="card-collapsible-content closed" id="ventas-content">
                    ${salesHtml}
                    ${renderSalesConceptsDetail(data.sales_concepts)}
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('bienes-raices-content')">
                    Conceptos de Bienes Raices Detectados &nbsp;<span class="card-arrow" id="bienes-raices-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Identifica conceptos inmobiliarios: tipo de propiedad, precio, metraje, habitaciones, ubicacion, amenidades, zonificacion y estado. Extrae los fragmentos relevantes del texto.</div>
                </div>
                <div class="card-collapsible-content closed" id="bienes-raices-content">
                    ${reHtml}
                    ${renderRealEstateConceptsDetail(data.real_estate_concepts)}
                </div>
            </div>
            <div class="card full-width">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('datos-extraidos-content')">
                    Datos Extraidos del Texto &nbsp;<span class="card-arrow" id="datos-extraidos-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Extrae datos concretos del texto: precios, metrajes, ubicaciones, fechas, horarios, porcentajes, acciones comprometidas y personas mencionadas. Haz clic en cada dato para verlo resaltado en el texto.</div>
                </div>
                <div class="card-collapsible-content closed" id="datos-extraidos-content">
                    ${entitiesHtml}
                    ${extDataHtml}
                </div>
            </div>
        </div>
        ${renderCommercial(data.commercial)}
        ${renderTextProgressChart(data.commercial)}
        ${renderTextReport(data)}
        <div class="timestamp">Analizado el: ${data.analyzed_at}</div>
        ${renderSaveConfirmation(data)}
    `;
    el.style.display = 'block';
    // Focus-a-slice interactivity for the indicator distribution donut.
    setTimeout(function() { attachIndicatorPieInteractivity(); }, 0);
    // Fluid staggered entrance for the freshly rendered analysis blocks.
    setTimeout(function() { animateEntrance(el); }, 20);
}

function renderCommercial(c) {
    if (!c) return '';

    const pct = c.probabilidad_cierre;
    const fillClass = pct > 70 ? 'prob-fill-hot' : pct > 40 ? 'prob-fill-warm' : 'prob-fill-cold';

    const indicators = [
        { key: 'palabras_positivas',    label: 'Palabras Positivas',     value: c.palabras_positivas,    cls: c.palabras_positivas > 0 ? 'positive' : '', color: '#FFFF00', desc: 'Mide expresiones de entusiasmo, aprobacion y satisfaccion del cliente. Un numero alto indica que el prospecto esta receptivo y con buena predisposicion hacia la propuesta.' },
        { key: 'respuestas_afirmativas',label: 'Induccion al Si',        value: c.respuestas_afirmativas, cls: c.respuestas_afirmativas > 0 ? 'positive' : '', color: '#008000', desc: 'Cuenta confirmaciones directas, expresiones de acuerdo y disposicion a avanzar. Indica el nivel de aceptacion del cliente ante lo que se le propone.' },
        { key: 'indicios_cierre',       label: 'Indicios de Cierre',     value: c.indicios_cierre,       cls: c.indicios_cierre > 0 ? 'positive' : '', color: '#FFA500', desc: 'Detecta senales de que el cliente quiere concretar: reservar, firmar, avanzar. Es el indicador mas fuerte de que la venta esta proxima a cerrarse.' },
        { key: 'escasez_comercial',     label: 'Escasez Comercial',      value: c.escasez_comercial,     cls: '', color: '#FF00FF', desc: 'Identifica menciones de disponibilidad limitada, urgencia temporal y exclusividad. Refleja el uso de tecnicas de escasez para motivar la decision de compra.' },
        { key: 'pedidos_referidos',     label: 'Pedidos de Referidos',   value: c.pedidos_referidos,     cls: '', color: '#b38bff', desc: 'Detecta solicitudes de recomendaciones, menciones de contactos y red de referidos. Indica si se esta trabajando la expansion de la cartera de clientes.' },
        { key: 'objeciones',            label: 'Objeciones',             value: c.objeciones,            cls: c.objeciones > 2 ? 'highlight' : '', color: '#FF0000', desc: 'Cuenta objeciones de precio, indecision y postergacion del cliente. Un numero alto indica resistencia que debe ser abordada antes de intentar el cierre.' },
        { key: 'indicios_prospeccion',  label: 'Prospeccion',            value: c.indicios_prospeccion,  cls: '', color: '#00BFFF', desc: 'Mide frases de apertura, calificacion del prospecto y exploracion de necesidades. Indica si la conversacion esta en etapa inicial de descubrimiento del cliente.' },
    ];

    const indicatorsHtml = indicators.map((ind, idx) => {
        const detail = c.detalle ? c.detalle[ind.key] : {};
        const hasDetail = detail && Object.keys(detail).length > 0;
        const detailId = 'detail-' + idx;
        const missingPanelId = 'missing-' + idx;

        // Pie chart data
        const totalFrases = (c.indicadores_total_frases || {})[ind.key] || 0;
        const catDetail = (c.indicadores_detalle_categorias || {})[ind.key] || {};
        const detectedCount = Object.values(catDetail).reduce((sum, arr) => sum + arr.length, 0);

        // Pie chart HTML — clickeable para mostrar frases faltantes, hover/long-press para tooltip de palabras detectadas
        let pieHtml = '';
        if (totalFrases > 0) {
            const piePct = Math.round((detectedCount / totalFrases) * 100);
            const deg = Math.round((piePct / 100) * 360);
            // Build tooltip content: detected phrases grouped by category
            let tooltipContent = '';
            if (Object.keys(catDetail).length > 0) {
                tooltipContent = Object.entries(catDetail).map(([cat, phrases]) =>
                    '<div style="margin-bottom:4px;"><div style="font-size:0.6rem;color:' + ind.color + ';font-weight:600;margin-bottom:2px;">' + cat.replace(/_/g, ' ') + ' (' + phrases.length + ')</div><div style="display:flex;flex-wrap:wrap;gap:2px;">' + phrases.map(p => '<span style="background:rgba(255,255,255,0.08);border:1px solid ' + ind.color + '44;color:#fff;padding:1px 5px;border-radius:6px;font-size:0.55rem;">' + p + '</span>').join('') + '</div></div>'
                ).join('');
            } else {
                tooltipContent = '<div style="font-size:0.6rem;color:#888;">Sin palabras detectadas</div>';
            }
            const tooltipId = 'pie-tooltip-' + idx;
            pieHtml = '<div class="pie-chart-click" data-missing="' + missingPanelId + '" data-tooltip="' + tooltipId + '" style="position:relative;width:40px;height:40px;border-radius:50%;background:conic-gradient(' + ind.color + ' 0deg ' + deg + 'deg, #2a2a2a ' + deg + 'deg 360deg);display:flex;align-items:center;justify-content:center;margin:4px auto;cursor:pointer;" title=""><div style="width:26px;height:26px;border-radius:50%;background:#0f1117;display:flex;align-items:center;justify-content:center;"><span style="font-size:0.55rem;color:#fff;font-weight:600;">' + piePct + '%</span></div></div>';
            pieHtml += '<div id="' + tooltipId + '" class="pie-tooltip" style="display:none;position:absolute;z-index:1000;left:50%;transform:translateX(-50%);bottom:calc(100% + 8px);min-width:180px;max-width:260px;max-height:220px;overflow-y:auto;padding:8px 10px;background:#12151f;border:1px solid ' + ind.color + '55;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.6);pointer-events:none;"><div style="font-size:0.62rem;color:#fff;font-weight:700;margin-bottom:4px;">' + ind.label + ' — ' + piePct + '% (' + detectedCount + '/' + totalFrases + ')</div>' + tooltipContent + '</div>';
        }

        // Category detail panel — chips clickeables que resaltan en el texto
        let detailHtml = '';
        if (Object.keys(catDetail).length > 0) {
            const catRows = Object.entries(catDetail).map(([cat, phrases]) =>
                '<div style="margin-bottom:5px;"><div style="font-size:0.65rem;color:#aaa;font-weight:600;margin-bottom:2px;">' + cat.replace(/_/g, ' ') + ' (' + phrases.length + ')</div><div style="display:flex;flex-wrap:wrap;gap:3px;">' + phrases.map(p => '<span class="phrase-chip" data-word="' + p.replace(/"/g, '&quot;') + '" data-group="' + ind.key + '" style="background:#0d1a2a;border:1px solid #1a3a5c;color:' + ind.color + ';padding:1px 6px;border-radius:8px;font-size:0.6rem;cursor:pointer;">' + p + '</span>').join('') + '</div></div>'
            ).join('');
            detailHtml = '<div class="indicator-detail" id="' + detailId + '" style="border-left:3px solid ' + ind.color + ';">' + catRows + '</div>';
        } else if (hasDetail) {
            const rows = Object.entries(detail)
                .sort((a, b) => b[1] - a[1])
                .map(([word, count]) => {
                    return '<div class="detail-word-row phrase-chip" data-word="' + word.replace(/"/g, '&quot;') + '" data-group="' + ind.key + '" style="cursor:pointer;"><span class="detail-word">' + word + '</span><span class="detail-count">' + count + 'x</span></div>';
                }).join('');
            detailHtml = '<div class="indicator-detail" id="' + detailId + '" style="border-left:3px solid ' + ind.color + ';">' + rows + '</div>';
        } else {
            detailHtml = '<div class="indicator-detail" id="' + detailId + '"><span class="detail-empty">Ninguna detectada</span></div>';
        }

        // Missing phrases panel (shown on pie chart click)
        const allCats = INDICADOR_CATEGORIAS[ind.key] || {};
        let missingHtml = '';
        let totalMissing = 0;
        Object.entries(allCats).forEach(([cat, allPhrases]) => {
            const found = catDetail[cat] || [];
            const missing = allPhrases.filter(p => !found.includes(p));
            if (missing.length > 0) {
                totalMissing += missing.length;
                missingHtml += '<div style="margin-bottom:4px;"><div style="font-size:0.6rem;color:#888;font-weight:600;">' + cat.replace(/_/g, ' ') + '</div><div style="display:flex;flex-wrap:wrap;gap:3px;">' + missing.map(p => '<span style="background:#1a0d0d;border:1px solid #3a1a1a;color:#f55b5b;padding:1px 6px;border-radius:8px;font-size:0.55rem;">' + p + '</span>').join('') + '</div></div>';
            }
        });
        if (totalMissing === 0) {
            missingHtml = '<div style="font-size:0.6rem;color:#5bf5a3;">Todas las frases detectadas</div>';
        }
        const scrollStyle = totalMissing > 15 ? 'max-height:200px;overflow-y:auto;' : '';
        const missingPanel = '<div id="' + missingPanelId + '" style="display:none;margin-top:4px;padding:8px;background:#0a0c14;border:1px solid #2a1a1a;border-radius:8px;border-left:3px solid #f55b5b;' + scrollStyle + '"><div style="font-size:0.62rem;color:#f55b5b;font-weight:600;margin-bottom:4px;">Frases no detectadas (' + totalMissing + ')</div>' + missingHtml + '</div>';

        return `
        <div class="staggered-entry">
            <div class="indicator-item has-detail"
                 style="border-top: 2px solid ${ind.color}; --accent: ${ind.color}; position:relative;"
                 onclick="toggleDetail('${detailId}', this);">
                <span class="card-info-icon" style="position:absolute;top:2px;right:2px;font-size:0.55rem;width:14px;height:14px;line-height:14px;" onclick="event.stopPropagation()">!</span>
                <div class="card-info-tooltip" style="top:18px;right:0;min-width:180px;max-width:220px;font-size:0.6rem;">${ind.desc}</div>
                <div class="indicator-label">${ind.label}</div>
                <div class="indicator-value ${ind.cls}">${ind.value}</div>
                ${pieHtml}
            </div>
            ${detailHtml}
            ${missingPanel}
        </div>`;
    }).join('');

    return `
    <div class="commercial-section">
        <div class="commercial-title card-title-collapsible" style="position:relative;" onclick="toggleCardContent('commercial-content')">Analisis Comercial Inmobiliario &nbsp;<span class="card-arrow" id="commercial-arrow">&#9660;</span>
            <span class="card-info-icon" style="position:absolute; top:2px; right:28px;" onclick="event.stopPropagation()">!</span>
            <div class="card-info-tooltip" style="top:22px; right:0;">Analiza indicadores comerciales de la conversacion: palabras positivas, respuestas afirmativas, indicios de cierre, objeciones y mas. Calcula la probabilidad de cierre y clasifica el lead.</div>
        </div>

        <div class="card-collapsible-content closed" id="commercial-content">
        <div style="margin-bottom:4px;">
            <span class="lead-badge lead-${c.tipo_lead}" style="cursor:pointer;"
                  onclick="toggleLeadDetail('lead-detail-panel')">
                LEAD ${c.tipo_lead} &nbsp;&#9660;
            </span>
        </div>

        <div class="lead-detail-panel" id="lead-detail-panel">
            ${renderLeadDetail(c)}
        </div>

        <div style="display:flex; align-items:center; gap:16px; margin:12px 0; flex-wrap:wrap;">
            <div>
                <div style="font-size:0.75rem; color:#666; margin-bottom:2px;">Nivel de interes: <strong style="color:#aaa">${c.nivel_interes}</strong></div>
                <div style="font-size:0.75rem; color:#666;">Tendencia de cierre: <strong style="color:#aaa">${c.tendencia_cierre}</strong></div>
            </div>
        </div>

        <div class="prob-bar-container">
            <div class="prob-label">
                <span>Probabilidad de Cierre</span>
                <span class="prob-value">${pct.toFixed(1)}%</span>
            </div>
            <div class="prob-bar">
                <div class="prob-fill ${fillClass}" style="width:${pct}%"></div>
            </div>
        </div>

        <div style="font-size:0.7rem; color:#555; margin-bottom:8px;">
            Haz clic en cada indicador para ver el detalle y resaltar las palabras en el texto.
        </div>

        <div class="indicators-grid">${indicatorsHtml}</div>

        <div style="font-size:0.75rem; color:#555; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.06em;">Recomendacion</div>
        <div class="recomendacion-box">${c.recomendacion}</div>

        <div style="font-size:0.7rem; color:#444; margin-top:10px; text-align:right;">
            Densidad comercial: ${c.densidad_comercial.toFixed(4)} &nbsp;|&nbsp; Total palabras: ${c.total_palabras}
        </div>
        </div>
    </div>`;
}

function renderTextProgressChart(c) {
    if (!c) return '';
    const indicators = [
        { key: 'palabras_positivas', label: 'Positivas', color: '#FFFF00' },
        { key: 'respuestas_afirmativas', label: 'Induccion al Si', color: '#008000' },
        { key: 'indicios_cierre', label: 'Cierre', color: '#FFA500' },
        { key: 'escasez_comercial', label: 'Escasez', color: '#FF00FF' },
        { key: 'pedidos_referidos', label: 'Referidos', color: '#b38bff' },
        { key: 'objeciones', label: 'Objeciones', color: '#FF0000' },
        { key: 'indicios_prospeccion', label: 'Prospeccion', color: '#00BFFF' },
    ];
    const total = indicators.reduce((s, ind) => s + (c[ind.key] || 0), 0) || 1;

    const indPieId = 'indpie_' + Math.random().toString(36).slice(2, 8);
    let gradientParts = [];
    let currentDeg = 0;
    let pctLabels = '';
    let indSegments = [];
    indicators.forEach((ind, i) => {
        const val = c[ind.key] || 0;
        const pct = Math.round((val / total) * 100);
        const degSpan = (val / total) * 360;
        gradientParts.push(ind.color + ' ' + currentDeg + 'deg ' + (currentDeg + degSpan) + 'deg');
        indSegments.push({ i: i, start: currentDeg, end: currentDeg + degSpan, color: ind.color, key: ind.key, mid: currentDeg + degSpan / 2 });
        if (pct >= 5) {
            const midDeg = currentDeg + degSpan / 2;
            const rad = (midDeg - 90) * Math.PI / 180;
            const x = 50 + 35 * Math.cos(rad);
            const y = 50 + 35 * Math.sin(rad);
            // Each % label is hoverable and focuses its slice (data-i links them).
            pctLabels += '<span class="' + indPieId + '-pct" data-i="' + i + '" style="position:absolute;left:' + x + '%;top:' + y + '%;transform:translate(-50%,-50%);font-size:0.6rem;color:#fff;font-weight:700;text-shadow:0 1px 3px rgba(0,0,0,0.9);cursor:pointer;">' + pct + '%</span>';
        }
        currentDeg += degSpan;
    });

    const legend = indicators.map((ind, i) => {
        const val = c[ind.key] || 0;
        const pct = Math.round((val / total) * 100);
        const seg = indSegments[i];
        return '<div class="pie-legend-row ' + indPieId + '-leg" data-i="' + i + '" data-start="' + seg.start.toFixed(2) + '" data-end="' + seg.end.toFixed(2) + '" data-col="' + ind.color + '" style="display:flex;align-items:center;gap:5px;font-size:0.65rem;padding:2px 5px;cursor:pointer;"><div style="width:8px;height:8px;border-radius:2px;background:' + ind.color + ';"></div><span style="color:#aaa;">' + ind.label + ': ' + val + ' (' + pct + '%)</span></div>';
    }).join('');

    // Register this pie so its slice can be focused on hover/tap of a % or legend.
    window._indPieInteractive = window._indPieInteractive || {};
    window._indPieInteractive[indPieId] = {
        base: 'conic-gradient(' + gradientParts.join(',') + ')',
        segments: indSegments
    };

    // Action buttons row: toggle highlight all + print highlighted transcript
    const btnRow =
        '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;padding-top:12px;border-top:1px solid #1e2130;">' +
            '<button id="btnResaltarPalabras" type="button" onclick="toggleResaltarPalabras()" ' +
                'style="background:linear-gradient(135deg,#2a2d3a,#1a1d27);border:1px solid #3a3d4a;color:#e0e0e0;' +
                'padding:8px 16px;border-radius:7px;font-size:0.8rem;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:6px;">' +
                '&#127752; Resaltar palabras' +
            '</button>' +
            '<button id="btnImprimirResaltado" type="button" onclick="imprimirTextoResaltado()" ' +
                'style="display:none;background:linear-gradient(135deg,#1a3a2a,#0d2a1a);border:1px solid #2a5a3a;color:#5bf5a3;' +
                'padding:8px 16px;border-radius:7px;font-size:0.8rem;font-weight:600;cursor:pointer;align-items:center;gap:6px;">' +
                '&#128424; Imprimir texto resaltado' +
            '</button>' +
        '</div>';

    return '<div class="analysis-block" style="margin-top:16px;padding:14px;background:#0a0c14;border:1px solid #1e2130;border-radius:10px;">' +
        '<div style="font-size:0.75rem;color:#888;font-weight:600;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.05em;">Distribucion de Indicadores — Este Texto</div>' +
        '<div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap;justify-content:center;">' +
            '<div id="' + indPieId + '" class="pie-chart-expand" style="position:relative;width:140px;height:140px;border-radius:50%;background:conic-gradient(' + gradientParts.join(',') + ');box-shadow:0 4px 12px rgba(0,0,0,0.3);transition:transform 0.2s ease, box-shadow 0.2s ease;">' +
                pctLabels +
                '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:60px;height:60px;border-radius:50%;background:#0f1117;display:flex;align-items:center;justify-content:center;"><span style="font-size:0.6rem;color:#aaa;">' + total + ' ind.</span></div>' +
            '</div>' +
            '<div style="display:flex;flex-direction:column;gap:4px;">' + legend + '</div>' +
        '</div>' +
        btnRow +
    '</div>';
}

function renderTextReport(data) {
    if (!data || data.error) return '';
    const c = data.commercial || {};
    const intentEs = INTENT_ES[data.intent] || data.intent;
    const sentimentEs = SENTIMENT_ES[data.sentiment] || data.sentiment;

    // Sales concepts summary
    let salesSummary = 'Ninguno detectado';
    if (data.sales_concepts && data.sales_concepts.length > 0) {
        salesSummary = data.sales_concepts.map(sc => translateConcept(sc.concept, SALES_CONCEPTS_ES) + ' (' + Math.round(sc.confidence * 100) + '%)').join(', ');
    }

    // Real estate concepts summary
    let reSummary = 'Ninguno detectado';
    if (data.real_estate_concepts && data.real_estate_concepts.length > 0) {
        reSummary = data.real_estate_concepts.map(rc => translateConcept(rc.concept, RE_CONCEPTS_ES) + ' (' + Math.round(rc.confidence * 100) + '%)').join(', ');
    }

    // Entities summary
    let entitiesSummary = '';
    if (data.entities && data.entities.length > 0) {
        const grouped = {};
        data.entities.forEach(e => { if (!grouped[e.concept]) grouped[e.concept] = []; grouped[e.concept].push(e); });
        entitiesSummary = Object.entries(grouped).map(([concept, items]) => {
            const label = (ENTITY_ES && ENTITY_ES[concept]) || concept;
            return label + ': ' + items.slice(0, 3).map(e => e.raw_value).join(', ') + (items.length > 3 ? ' (+' + (items.length - 3) + ')' : '');
        }).join(' | ');
    }

    // Commercial indicators summary
    const indLabels = { palabras_positivas: 'Positivas', respuestas_afirmativas: 'Induccion al Si', indicios_cierre: 'Cierre', escasez_comercial: 'Escasez', pedidos_referidos: 'Referidos', objeciones: 'Objeciones', indicios_prospeccion: 'Prospeccion' };
    const indSummary = Object.entries(indLabels).map(([k, label]) => label + ': ' + (c[k] || 0)).join(' | ');

    // Build report
    let report = '<div class="analysis-block" style="margin-top:16px;padding:16px;background:#0a0c14;border:1px solid #1e2130;border-radius:10px;">';
    report += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;"><div style="font-size:0.75rem;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">📋 Informe del Texto</div><button onclick="copyReport()" style="background:#1a1d27;border:1px solid #2a2d3e;color:#aaa;padding:4px 10px;border-radius:6px;font-size:0.6rem;cursor:pointer;">📋 Copiar</button></div>';

    report += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.65rem;">';
    report += '<div style="padding:6px 8px;background:#0d1017;border-radius:6px;border-left:3px solid #4a6cf7;"><span style="color:#666;">Intencion:</span> <strong style="color:#e0e0e0;">' + intentEs + '</strong> (' + Math.round((data.intent_confidence || 0) * 100) + '%)</div>';
    report += '<div style="padding:6px 8px;background:#0d1017;border-radius:6px;border-left:3px solid ' + (data.sentiment === 'POSITIVE' ? '#5bf5a3' : data.sentiment === 'NEGATIVE' ? '#f55b5b' : '#f5a35b') + ';"><span style="color:#666;">Sentimiento:</span> <strong style="color:#e0e0e0;">' + sentimentEs + '</strong> (' + Math.round((data.sentiment_confidence || 0) * 100) + '%)</div>';
    report += '<div style="padding:6px 8px;background:#0d1017;border-radius:6px;border-left:3px solid #f5d75b;"><span style="color:#666;">Lead:</span> <strong style="color:#e0e0e0;">' + (c.tipo_lead || '-') + '</strong></div>';
    report += '<div style="padding:6px 8px;background:#0d1017;border-radius:6px;border-left:3px solid #5bf5a3;"><span style="color:#666;">Prob. Cierre:</span> <strong style="color:#e0e0e0;">' + (c.probabilidad_cierre || 0).toFixed(1) + '%</strong></div>';
    report += '<div style="padding:6px 8px;background:#0d1017;border-radius:6px;border-left:3px solid #b38bff;"><span style="color:#666;">Etapa:</span> <strong style="color:#e0e0e0;">' + (c.etapa_funnel || '-') + '</strong></div>';
    report += '<div style="padding:6px 8px;background:#0d1017;border-radius:6px;border-left:3px solid #f5a35b;"><span style="color:#666;">Urgencia:</span> <strong style="color:#e0e0e0;">' + (c.urgencia || '-') + '</strong></div>';
    report += '</div>';

    report += '<div style="margin-top:8px;padding:6px 8px;background:#0d1017;border-radius:6px;font-size:0.63rem;"><span style="color:#666;">Indicadores:</span> <span style="color:#ccc;">' + indSummary + '</span></div>';
    report += '<div style="margin-top:4px;padding:6px 8px;background:#0d1017;border-radius:6px;font-size:0.63rem;"><span style="color:#666;">Conceptos Venta:</span> <span style="color:#ccc;">' + salesSummary + '</span></div>';
    report += '<div style="margin-top:4px;padding:6px 8px;background:#0d1017;border-radius:6px;font-size:0.63rem;"><span style="color:#666;">Conceptos Inmobiliarios:</span> <span style="color:#ccc;">' + reSummary + '</span></div>';

    if (entitiesSummary) {
        report += '<div style="margin-top:4px;padding:6px 8px;background:#0d1017;border-radius:6px;font-size:0.63rem;"><span style="color:#666;">Datos Extraidos:</span> <span style="color:#ccc;">' + entitiesSummary + '</span></div>';
    }

    if (c.recomendacion) {
        report += '<div style="margin-top:8px;padding:8px;background:#0d1a0d;border:1px solid #1a3a1a;border-radius:6px;font-size:0.65rem;color:#5bf5a3;">💡 ' + c.recomendacion + '</div>';
    }
    if (c.accion_siguiente) {
        report += '<div style="margin-top:4px;padding:8px;background:#0d0d1a;border:1px solid #1a1a3a;border-radius:6px;font-size:0.65rem;color:#7b9cff;">▶️ ' + c.accion_siguiente + '</div>';
    }

    // --- Expanded Narrative Summary ---
    report += '<div class="analysis-block" style="margin-top:14px;padding:14px;background:#080a10;border:1px solid #1e2130;border-radius:8px;border-left:3px solid #4a6cf7;">';
    report += '<div style="font-size:0.7rem;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:10px;">Analisis Narrativo del Texto</div>';

    // Intent analysis
    const intentConf = Math.round((data.intent_confidence || 0) * 100);
    report += '<p style="font-size:0.72rem;color:#ccc;line-height:1.7;margin-bottom:10px;text-align:justify;">';
    report += 'La intencion principal del texto fue clasificada como <strong style="color:#e0e0e0;">' + intentEs + '</strong> con una confianza del <strong>' + intentConf + '%</strong>. ';
    if (intentConf >= 50) {
        report += 'Este nivel de confianza indica que el modelo identifico patrones claros y consistentes en el discurso que permiten afirmar con solidez la naturaleza de la interaccion. ';
    } else if (intentConf >= 25) {
        report += 'La confianza moderada sugiere que el texto contiene elementos mixtos que dificultan una clasificacion definitiva, posiblemente porque la conversacion transita entre multiples etapas del proceso de venta. ';
    } else {
        report += 'La baja confianza indica que el texto no presenta patrones claros de ninguna intencion especifica, lo cual puede deberse a una conversacion inicial sin foco comercial definido. ';
    }
    report += '</p>';

    // Lead & probability analysis
    const prob = (c.probabilidad_cierre || 0);
    report += '<p style="font-size:0.72rem;color:#ccc;line-height:1.7;margin-bottom:10px;text-align:justify;">';
    report += 'El lead fue clasificado como <strong style="color:' + (c.tipo_lead === 'CALIENTE' ? '#f55b5b' : c.tipo_lead === 'TIBIO' ? '#f5a35b' : '#5bd4f5') + ';">' + (c.tipo_lead || 'FRIO') + '</strong> con una probabilidad de cierre del <strong>' + prob.toFixed(1) + '%</strong>. ';
    if (prob >= 60) {
        report += 'Esta probabilidad elevada se sustenta en la presencia significativa de indicios de cierre (' + (c.indicios_cierre || 0) + '), respuestas afirmativas (' + (c.respuestas_afirmativas || 0) + ') y un bajo nivel de objeciones relativas. El prospecto demuestra disposicion activa para avanzar hacia la concrecion de la operacion.';
    } else if (prob >= 30) {
        report += 'La probabilidad moderada refleja un equilibrio entre senales positivas (indicios de cierre: ' + (c.indicios_cierre || 0) + ', afirmativas: ' + (c.respuestas_afirmativas || 0) + ') y factores de resistencia (objeciones: ' + (c.objeciones || 0) + '). El lead muestra interes pero requiere trabajo adicional para superar las barreras identificadas.';
    } else {
        report += 'La probabilidad baja se explica por la ausencia o escasez de senales de cierre (' + (c.indicios_cierre || 0) + ') combinada con un nivel de objeciones (' + (c.objeciones || 0) + ') que supera las respuestas afirmativas (' + (c.respuestas_afirmativas || 0) + '). Se recomienda un enfoque de nutricion y seguimiento antes de intentar el cierre.';
    }
    report += '</p>';

    // Funnel + Urgency analysis
    report += '<p style="font-size:0.72rem;color:#ccc;line-height:1.7;margin-bottom:10px;text-align:justify;">';
    report += 'La etapa del funnel identificada es <strong style="color:#e0e0e0;">' + (c.etapa_funnel || 'AWARENESS') + '</strong> con urgencia <strong style="color:' + (c.urgencia === 'CRITICA' ? '#f55b5b' : c.urgencia === 'ALTA' ? '#f5a35b' : '#aaa') + ';">' + (c.urgencia || 'BAJA') + '</strong>. ';
    if (c.etapa_funnel === 'DECISION' && (c.urgencia === 'CRITICA' || c.urgencia === 'ALTA')) {
        report += 'La combinacion de etapa avanzada con urgencia elevada constituye una senal inequivoca de que el prospecto requiere atencion inmediata. Cada hora sin contacto reduce significativamente las probabilidades de conversion. Se requiere accion comercial dentro de las proximas 2-4 horas.';
    } else if (c.etapa_funnel === 'CONSIDERATION') {
        report += 'El prospecto se encuentra evaluando opciones activamente. En esta etapa es fundamental proveer informacion diferenciadora, resolver dudas pendientes y mantener un ritmo de seguimiento que no permita que el interes se enfrie.';
    } else if (c.etapa_funnel === 'AWARENESS') {
        report += 'El prospecto se encuentra en etapa inicial de conocimiento. La conversacion aun no ha generado compromiso concreto. Se recomienda calificar al lead (presupuesto, plazo, necesidades) y agendar un contacto de profundizacion.';
    }
    report += '</p>';

    // Indicators deep analysis
    const totalInd = (c.palabras_positivas || 0) + (c.respuestas_afirmativas || 0) + (c.indicios_cierre || 0) + (c.escasez_comercial || 0) + (c.pedidos_referidos || 0) + (c.objeciones || 0) + (c.indicios_prospeccion || 0);
    report += '<p style="font-size:0.72rem;color:#ccc;line-height:1.7;margin-bottom:10px;text-align:justify;">';
    report += 'El analisis de indicadores comerciales arrojo un total de <strong>' + totalInd + '</strong> marcadores detectados sobre <strong>' + (c.total_palabras || 0) + '</strong> palabras (densidad: ' + ((c.densidad_comercial || 0) * 100).toFixed(2) + '%). ';
    if ((c.densidad_comercial || 0) > 0.04) {
        report += 'La alta densidad comercial indica que la conversacion estuvo fuertemente orientada a la gestion de ventas, con un discurso cargado de tecnicas y respuestas comerciales activas.';
    } else if ((c.densidad_comercial || 0) > 0.02) {
        report += 'La densidad moderada sugiere una conversacion con contenido comercial presente pero no predominante. Existe espacio para intensificar el enfoque de ventas en futuras interacciones.';
    } else {
        report += 'La baja densidad comercial revela que la conversacion tuvo escaso contenido orientado a la venta. Esto puede indicar una llamada exploratoria, de servicio, o una oportunidad desaprovechada de aplicar tecnicas de prospeccion.';
    }
    report += '</p>';

    // Conclusion
    report += '<p style="font-size:0.72rem;color:#5bf5a3;line-height:1.7;padding:8px 10px;background:#0d1a0d;border-radius:6px;border-left:2px solid #5bf5a3;text-align:justify;">';
    report += '<strong>Conclusion:</strong> ';
    if (prob >= 60) {
        report += 'La conversacion presenta un perfil de cierre avanzado. Se recomienda ejecutar la accion de cierre de forma inmediata, minimizando la friccion administrativa y facilitando el siguiente paso concreto para el prospecto.';
    } else if (prob >= 30) {
        report += 'La conversacion muestra potencial comercial con barreras identificables. El seguimiento estrategico, la resolucion de objeciones y el refuerzo de beneficios clave son las palancas principales para elevar la probabilidad de cierre en el proximo contacto.';
    } else {
        report += 'La conversacion no alcanzo un nivel de madurez comercial suficiente. Se sugiere clasificar este lead para nutricion, programar seguimiento en 48-72hs, y preparar material de valor que aborde las dudas implicitas detectadas en el texto.';
    }
    report += '</p>';
    report += '</div>';

    report += '</div>';
    return report;
}

function copyReport() {
    const c = _lastCommercialData || {};
    const data = window._lastAnalysisData || {};
    const intentEs = INTENT_ES[data.intent] || data.intent || '';
    const sentimentEs = SENTIMENT_ES[data.sentiment] || data.sentiment || '';
    const title = window._currentEntryName || '';

    let text = '=== INFORME DE ANALISIS ===\\n';
    if (title) text += 'Texto: ' + title + '\\n';
    text += 'Intencion: ' + intentEs + ' (' + Math.round((data.intent_confidence || 0) * 100) + '%)\\n';
    text += 'Sentimiento: ' + sentimentEs + ' (' + Math.round((data.sentiment_confidence || 0) * 100) + '%)\\n';
    text += 'Lead: ' + (c.tipo_lead || '-') + ' | Prob. Cierre: ' + (c.probabilidad_cierre || 0).toFixed(1) + '%\\n';
    text += 'Etapa: ' + (c.etapa_funnel || '-') + ' | Urgencia: ' + (c.urgencia || '-') + '\\n';
    text += '---\\n';
    text += 'Positivas: ' + (c.palabras_positivas || 0) + ' | Afirmativas: ' + (c.respuestas_afirmativas || 0) + ' | Cierre: ' + (c.indicios_cierre || 0) + '\\n';
    text += 'Objeciones: ' + (c.objeciones || 0) + ' | Referidos: ' + (c.pedidos_referidos || 0) + ' | Prospeccion: ' + (c.indicios_prospeccion || 0) + '\\n';
    if (c.recomendacion) text += '---\\nRecomendacion: ' + c.recomendacion + '\\n';
    if (c.accion_siguiente) text += 'Siguiente paso: ' + c.accion_siguiente + '\\n';

    navigator.clipboard.writeText(text.replace(/\\\\n/g, '\\n')).then(() => {
        const btn = document.querySelector('[onclick="copyReport()"]');
        if (btn) { btn.textContent = '✓ Copiado'; setTimeout(() => { btn.textContent = '📋 Copiar'; }, 2000); }
    });
}

function renderLeadDetail(c) {
    if (!c.formula) return '';
    const f = c.formula;
    const pct = c.probabilidad_cierre;

    let gapHtml = '';
    if (c.tipo_lead === 'CALIENTE') {
        gapHtml = `<div class="lead-gap lead-gap-caliente">
            Este lead ya es CALIENTE. Proceder al cierre inmediatamente.
        </div>`;
    } else if (c.tipo_lead === 'TIBIO') {
        gapHtml = `<div class="lead-gap lead-gap-tibio">
            Para ser CALIENTE necesita superar 70%. Le faltan <strong>${f.para_caliente} puntos</strong>.
            Reforzar indicios de cierre y respuestas afirmativas.
        </div>`;
    } else {
        const gapTibio = f.para_tibio > 0
            ? `Para ser TIBIO necesita superar 40%. Le faltan <strong>${f.para_tibio} puntos</strong>.`
            : `Ya esta cerca del nivel TIBIO.`;
        gapHtml = `<div class="lead-gap lead-gap-frio">
            ${gapTibio} Nutrir con informacion y seguimiento activo.
        </div>`;
    }

    // Extended analysis sections
    const funnelLabels = {
        'AWARENESS': '🔍 Conocimiento inicial',
        'CONSIDERATION': '⚖️ Evaluando opciones',
        'DECISION': '🎯 Cerca de decidir',
        'CLOSED': '✅ Operacion cerrada'
    };
    const urgenciaLabels = {
        'BAJA': '🟢 Baja', 'MEDIA': '🟡 Media', 'ALTA': '🟠 Alta', 'CRITICA': '🔴 Critica'
    };
    const compromisoLabels = {
        'BAJO': '⬜ Bajo', 'MEDIO': '🟨 Medio', 'ALTO': '🟩 Alto'
    };
    const operacionLabels = {
        'VENTA': '🏷️ Compra-Venta', 'ALQUILER': '🔑 Alquiler',
        'INVERSION': '📈 Inversion', 'INDEFINIDO': '❓ No identificado'
    };
    const financLabels = {
        'CONTADO': '💵 Contado', 'CREDITO': '🏦 Credito/Hipoteca',
        'FINANCIAMIENTO_DIRECTO': '🤝 Financiamiento directo', 'NO_DETECTADO': '—'
    };

    let senalesHtml = '';
    if (c.senales_compra && c.senales_compra.length > 0) {
        senalesHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">🛒 Senales de compra</span>
            <div class="lead-ext-tags">${c.senales_compra.map(s => `<span class="tag-green">${s}</span>`).join('')}</div>
        </div>`;
    }

    let objeccionesEspHtml = '';
    if (c.objeciones_especificas && c.objeciones_especificas.length > 0) {
        objeccionesEspHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">⚠️ Objeciones detectadas</span>
            <div class="lead-ext-tags">${c.objeciones_especificas.map(o => `<span class="tag-red">${o}</span>`).join('')}</div>
        </div>`;
    }

    let persuasionHtml = '';
    if (c.tecnicas_persuasion && c.tecnicas_persuasion.length > 0) {
        persuasionHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">🧠 Tecnicas de persuasion</span>
            <div class="lead-ext-tags">${c.tecnicas_persuasion.map(t => `<span class="tag-purple">${t}</span>`).join('')}</div>
        </div>`;
    }

    let preguntasHtml = '';
    if (c.preguntas_abiertas && c.preguntas_abiertas.length > 0) {
        preguntasHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">❓ Preguntas abiertas</span>
            <div class="lead-ext-list">${c.preguntas_abiertas.map(q => `<div class="lead-question">"${q}"</div>`).join('')}</div>
        </div>`;
    }

    let keywordsHtml = '';
    if (c.keywords && c.keywords.length > 0) {
        keywordsHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">🔑 Keywords principales</span>
            <div class="lead-ext-tags">${c.keywords.map(k => `<span class="tag-blue">${k}</span>`).join('')}</div>
        </div>`;
    }

    return `
        <div class="lead-extended-grid">
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Etapa del Funnel</div>
                <div class="lead-ext-card-value">${funnelLabels[c.etapa_funnel] || c.etapa_funnel}</div>
            </div>
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Urgencia</div>
                <div class="lead-ext-card-value">${urgenciaLabels[c.urgencia] || c.urgencia}</div>
            </div>
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Compromiso</div>
                <div class="lead-ext-card-value">${compromisoLabels[c.nivel_compromiso] || c.nivel_compromiso}</div>
            </div>
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Tipo Operacion</div>
                <div class="lead-ext-card-value">${operacionLabels[c.tipo_operacion] || c.tipo_operacion}</div>
            </div>
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Financiamiento</div>
                <div class="lead-ext-card-value">${financLabels[c.financiamiento] || c.financiamiento}</div>
            </div>
        </div>

        ${senalesHtml}
        ${objeccionesEspHtml}
        ${persuasionHtml}
        ${preguntasHtml}
        ${keywordsHtml}

        ${c.resumen ? `<div class="lead-extended-item">
            <span class="lead-ext-label">📋 Resumen</span>
            <div class="lead-ext-summary">${c.resumen}</div>
        </div>` : ''}

        ${c.accion_siguiente ? `<div class="lead-extended-item lead-next-action">
            <span class="lead-ext-label">▶️ Accion siguiente recomendada</span>
            <div class="lead-ext-action">${c.accion_siguiente}</div>
        </div>` : ''}

        <div class="lead-formula-section">
            <div class="lead-ext-label" style="margin-bottom:8px;">📊 Formula de probabilidad</div>
            <div style="font-size:0.75rem; color:#666; margin-bottom:10px;">
                <code style="color:#4a6cf7; font-size:0.8rem;">(Indicios_Cierre x 5 + Respuestas_Afirm x 2 - Objeciones x 3) / Total_Palabras x 100</code>
            </div>
            <table class="formula-table">
                <tr class="positive-row">
                    <td>Indicios de Cierre</td>
                    <td>${c.indicios_cierre} x 5</td>
                    <td>+${f.indicios_cierre_pts}</td>
                </tr>
                <tr class="positive-row">
                    <td>Respuestas Afirmativas</td>
                    <td>${c.respuestas_afirmativas} x 2</td>
                    <td>+${f.respuestas_afirmativas_pts}</td>
                </tr>
                <tr class="negative-row">
                    <td>Objeciones</td>
                    <td>${c.objeciones} x 3</td>
                    <td>-${f.objeciones_pts}</td>
                </tr>
                <tr class="total-row">
                    <td colspan="2">Puntaje neto</td>
                    <td>${f.puntaje_neto}</td>
                </tr>
            </table>
            <div class="formula-result">
                <strong>(${f.puntaje_neto} / ${f.total_palabras} palabras) x 100 = ${pct.toFixed(2)}%</strong>
                <br>
                <span style="font-size:0.75rem;">
                    Umbral CALIENTE: &gt;70% &nbsp;|&nbsp; Umbral TIBIO: &gt;40% &nbsp;|&nbsp; FRIO: &lt;40%
                </span>
            </div>
            ${gapHtml}
        </div>
    `;
}

function toggleLeadDetail(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    panel.classList.toggle('open');
}

function toggleExtDetail(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    // Close other ext-detail panels
    document.querySelectorAll('.ext-detail-panel').forEach(p => {
        if (p.id !== panelId) p.classList.remove('open');
    });
    panel.classList.toggle('open');
}

function toggleCardContent(contentId) {
    const content = document.getElementById(contentId);
    if (!content) return;
    content.classList.toggle('closed');
    const arrow = document.getElementById(contentId.replace('-content', '-arrow'));
    if (arrow) arrow.classList.toggle('open');
}

function renderSaveConfirmation(data) {
    const months = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    const savedYear = data.year || new Date().getFullYear();
    const savedMonth = data.month || (new Date().getMonth() + 1);
    const monthName = months[savedMonth] || '';

    // Generate a default name from the first words of the text
    const defaultName = (data.input_text || '').substring(0, 40).replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ\\s]/g, '').trim() + '...';

    let yearOptions = '';
    for (let y = 2026; y <= 2030; y++) {
        yearOptions += `<option value="${y}" ${y == savedYear ? 'selected' : ''}>${y}</option>`;
    }
    let monthOptions = '';
    for (let m = 1; m <= 12; m++) {
        monthOptions += `<option value="${m}" ${m == savedMonth ? 'selected' : ''}>${months[m]}</option>`;
    }

    return `
        <div class="save-confirmation">
            <div class="save-conf-main">
                <span class="save-conf-icon">📁</span>
                <span class="save-conf-text">Guardado en: <strong>${monthName} ${savedYear}</strong></span>
                <button class="save-conf-btn" onclick="toggleRelocate()">&#9998; Editar</button>
            </div>
            <div class="save-relocate-panel" id="relocatePanel">
                <div class="save-relocate-desc">Nombre del texto (para identificarlo):</div>
                <div class="save-name-row">
                    <input type="text" id="entryName" class="save-name-input" value="${defaultName}" placeholder="Nombre del texto...">
                </div>
                <div class="save-relocate-desc" style="margin-top:8px;">Periodo:</div>
                <div class="save-relocate-selects">
                    <select id="relocateYear">${yearOptions}</select>
                    <select id="relocateMonth">${monthOptions}</select>
                    <button class="save-relocate-confirm" onclick="saveWithName()">💾 Guardar</button>
                    <button class="save-delete-btn" onclick="deleteLastEntry()">🗑️ Eliminar</button>
                </div>
            </div>
        </div>
    `;
}

function toggleRelocate() {
    const panel = document.getElementById('relocatePanel');
    if (panel) panel.classList.toggle('open');
}

async function saveWithName() {
    const year = parseInt(document.getElementById('relocateYear').value);
    const month = parseInt(document.getElementById('relocateMonth').value);
    const name = document.getElementById('entryName').value.trim() || 'Sin nombre';
    const months = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

    // Update the selectors at the top to match
    document.getElementById('selectYear').value = year;
    document.getElementById('selectMonth').value = month;

    const text = document.getElementById('textInput').value.trim();
    if (!text) return;

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, year, month, entry_name: name, existing_entry_id: window._currentEntryId || '' })
        });
        const data = await response.json();
        if (!data.error) {
            const confText = document.querySelector('.save-conf-text');
            if (confText) confText.innerHTML = `Guardado en: <strong>${months[month]} ${year}</strong> como "<em>${name}</em>"`;
            const panel = document.getElementById('relocatePanel');
            if (panel) panel.classList.remove('open');
            const btn = document.querySelector('.save-relocate-confirm');
            if (btn) {
                btn.textContent = '✓ Guardado';
                btn.style.background = '#1a4a2a';
                setTimeout(() => { btn.textContent = '💾 Guardar'; btn.style.background = ''; }, 2000);
            }
            if (typeof loadHistory === 'function') loadHistory();
            loadSavedTexts();
        }
    } catch(e) {
        console.error('Error saving:', e);
    }
}

function toggleSavedTexts() {
    // Legacy — now using dropdown select
    loadSavedTexts();
}

async function loadSavedTexts() {
    const year = document.getElementById('selectYear').value;
    const month = document.getElementById('selectMonth').value;

    // If admin has a user selected, use admin endpoint
    const userSelect = document.getElementById('selectUser');
    const adminUser = userSelect ? userSelect.value : '';

    // For admin: if no user selected, can't load texts
    if (userSelect && !adminUser) {
        const select = document.getElementById('selectText');
        const count = document.getElementById('savedTextsCount');
        if (select) select.innerHTML = '<option value="">-- Seleccionar usuario primero --</option>';
        if (count) count.textContent = '';
        return;
    }

    let url = adminUser
        ? `/admin/user-texts/${adminUser}?year=${year}&month=${month}&_t=${Date.now()}`
        : `/saved-texts?year=${year}&month=${month}&_t=${Date.now()}`;

    try {
        const response = await fetch(url, { cache: 'no-store' });
        const data = await response.json();
        const select = document.getElementById('selectText');
        const count = document.getElementById('savedTextsCount');
        if (!select) return;

        // Clear existing options except the first placeholder
        select.innerHTML = '<option value="">-- Seleccionar texto --</option>';

        if (data.entries && data.entries.length > 0) {
            count.textContent = `(${data.entries.length})`;
            data.entries.forEach((e, i) => {
                const rawName = e.entry_name || (e.text || '').substring(0, 16) || 'Texto #' + (i+1);
                const name = rawName.length > 16 ? rawName.substring(0, 16) + '...' : rawName;
                const opt = document.createElement('option');
                opt.value = e.id;
                opt.textContent = name;
                opt.setAttribute('data-fullname', e.entry_name || rawName);
                opt.setAttribute('data-timestamp', e.timestamp || '');
                select.appendChild(opt);
            });
        } else {
            count.textContent = '(0)';
        }
    } catch(e) {
        console.error('Error loading saved texts:', e);
    }
}

function onTextSelected(entryId) {
    if (!entryId) {
        document.getElementById('deleteTextBtn').style.display = 'none';
        window._currentEntryId = '';
        return;
    }
    document.getElementById('deleteTextBtn').style.display = 'inline-block';
    window._currentEntryId = entryId;  // Track loaded entry ID for UPSERT
    // Capture the full entry name from the selected option
    const select = document.getElementById('selectText');
    const selectedOpt = select.options[select.selectedIndex];
    if (selectedOpt) {
        window._currentEntryName = selectedOpt.getAttribute('data-fullname') || selectedOpt.textContent || '';
        // Show the entry's date in the fecha input
        const ts = selectedOpt.getAttribute('data-timestamp') || '';
        if (ts && ts.length >= 10) {
            document.getElementById('selectFecha').value = ts.substring(0, 10);
        }
    }
    loadSavedText(entryId);
}

async function deleteSelectedText() {
    const select = document.getElementById('selectText');
    const entryId = select.value;
    if (!entryId) return;
    const name = select.options[select.selectedIndex].textContent;
    if (!confirm('¿Eliminar "' + name + '"?')) return;
    try {
        const response = await fetch('/delete-entry/' + entryId, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            document.getElementById('deleteTextBtn').style.display = 'none';
            loadSavedTexts();
        } else {
            alert('No se pudo eliminar.');
        }
    } catch(e) {
        alert('Error: ' + e.message);
    }
}

async function loadSavedText(entryId) {
    // Load a saved text into the textarea for re-analysis
    try {
        const response = await fetch(`/saved-text/${entryId}`);
        const data = await response.json();
        if (data.text) {
            const ta = document.getElementById('textInput');
            // Inline text-replacement effect: old content fades out, new fades in.
            // Purely visual — never changes the value used by the analyzer.
            const applySwap = !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
            if (applySwap) {
                ta.classList.remove('text-swap-enter');
                ta.classList.add('text-swap-exit');
                setTimeout(function() {
                    ta.value = data.text;
                    ta.classList.remove('text-swap-exit');
                    ta.classList.add('text-swap-enter');
                    setTimeout(function() { ta.classList.remove('text-swap-enter'); }, 3200);
                }, 1280);
            } else {
                ta.value = data.text;
            }
        }
        // Store entry_name globally for display in results preview
        window._currentEntryName = data.entry_name || '';
        // Put entry_name in the title input if it exists (admin only)
        const nameInput = document.getElementById('entryNameInput');
        if (nameInput && data.entry_name) {
            nameInput.value = data.entry_name;
        }
    } catch(e) {
        console.error('Error loading text:', e);
    }
}

// ── ADMIN FUNCTIONS ──
function onStatsMonthChange() {
    const monthSelect = document.getElementById('statsMonth');
    const periodSelect = document.getElementById('statsPeriod');
    if (monthSelect.value) {
        // Specific month selected — disable period selector
        periodSelect.disabled = true;
        periodSelect.style.opacity = '0.4';
    } else {
        // No specific month — enable period selector
        periodSelect.disabled = false;
        periodSelect.style.opacity = '1';
    }
    loadAdminStats();
}

async function loadAdminUsers() {
    try {
        const resp = await fetch('/admin/users-list');
        if (!resp.ok) { console.error('admin/users-list failed:', resp.status); return; }
        const data = await resp.json();
        const select = document.getElementById('selectUser');
        const vendorSelect = document.getElementById('statsVendor');
        if (!data.users || !data.users.length) { console.error('No users returned'); return; }
        if (select) {
            data.users.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u;
                opt.textContent = u;
                select.appendChild(opt);
            });
        }
        if (vendorSelect) {
            data.users.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u;
                opt.textContent = u;
                vendorSelect.appendChild(opt);
            });
        }
    } catch(e) { console.error('Error loading users:', e); }
}

async function loadAdminStats() {
    const vendorSelect = document.getElementById('statsVendor');
    const periodSelect = document.getElementById('statsPeriod');
    const monthSelect = document.getElementById('statsMonth');
    if (!vendorSelect || !periodSelect) return;

    const vendor = vendorSelect.value;
    const period = periodSelect.value;
    const specificMonth = monthSelect ? monthSelect.value : '';
    const container = document.getElementById('adminStatsContent');
    if (!container) return;

    // Build URL — _all means aggregate all users
    let url;
    if (vendor === '_all') {
        url = `/admin/stats/_all?period=${period}&year=2026`;
    } else {
        url = `/admin/stats/${vendor}?period=${period}&year=2026`;
    }
    if (specificMonth) {
        url += `&month=${specificMonth}`;
        url = url.replace(`period=${period}`, 'period=specific');
    }

    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            container.innerHTML = '<div style="color:#f55b5b;font-size:0.8rem;">Error: ' + resp.status + ' - Verifica que estas logueado como admin.</div>';
            return;
        }
        const data = await resp.json();

        if (data.error) {
            container.innerHTML = '<div style="color:#f55b5b;font-size:0.8rem;">Error: ' + (data.error || 'desconocido') + '</div>';
            return;
        }

        if (data.entry_count === 0) {
            container.innerHTML = '<div style="color:#555;font-size:0.8rem;">No hay datos para este periodo.</div>';
            return;
        }

        const totals = data.totals;
        const total = Object.values(totals).reduce((s, v) => s + v, 0) || 1;
        const indicators = [
            { key: 'palabras_positivas', label: 'Positivas', color: '#FFFF00' },
            { key: 'respuestas_afirmativas', label: 'Induccion al Si', color: '#008000' },
            { key: 'indicios_cierre', label: 'Cierre', color: '#FFA500' },
            { key: 'escasez_comercial', label: 'Escasez', color: '#FF00FF' },
            { key: 'pedidos_referidos', label: 'Referidos', color: '#b38bff' },
            { key: 'objeciones', label: 'Objeciones', color: '#FF0000' },
            { key: 'indicios_prospeccion', label: 'Prospeccion', color: '#00BFFF' },
        ];

        // Build conic-gradient for 3D-style pie chart with percentage labels
        let gradientParts = [];
        let currentDeg = 0;
        let pctLabels = '';
        indicators.forEach((ind, i) => {
            const pct = Math.round((totals[ind.key] / total) * 100);
            const degSpan = (totals[ind.key] / total) * 360;
            gradientParts.push(`${ind.color} ${currentDeg}deg ${currentDeg + degSpan}deg`);
            // Position label at midpoint of segment
            if (pct >= 5) {
                const midDeg = currentDeg + degSpan / 2;
                const rad = (midDeg - 90) * Math.PI / 180;
                const x = 50 + 38 * Math.cos(rad);
                const y = 50 + 38 * Math.sin(rad);
                pctLabels += `<span style="position:absolute;left:${x}%;top:${y}%;transform:translate(-50%,-50%);font-size:0.7rem;color:#fff;font-weight:700;text-shadow:0 1px 3px rgba(0,0,0,0.9),0 0 6px rgba(0,0,0,0.7);pointer-events:none;z-index:2;">${pct}%</span>`;
            }
            currentDeg += degSpan;
        });

        // Store word_detail globally for click interaction
        window._adminWordDetail = data.word_detail || {};

        // Store segment angles for hover detection
        window._pieSegments = [];
        let segStart = 0;
        indicators.forEach((ind) => {
            const degSpan = (totals[ind.key] / total) * 360;
            const pct = Math.round((totals[ind.key] / total) * 100);
            window._pieSegments.push({ key: ind.key, label: ind.label, color: ind.color, startDeg: segStart, endDeg: segStart + degSpan, pct: pct, count: totals[ind.key] });
            segStart += degSpan;
        });

        const pieChart = `
            <div id="statsPieChart" style="position:relative;width:200px;height:200px;border-radius:50%;background:conic-gradient(${gradientParts.join(',')});box-shadow:0 6px 16px rgba(0,0,0,0.4);margin:0 auto;cursor:pointer;">
                ${pctLabels}
                <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:80px;height:80px;border-radius:50%;background:#0f1117;display:flex;align-items:center;justify-content:center;pointer-events:none;">
                    <span style="font-size:0.7rem;color:#aaa;">${data.entry_count} textos</span>
                </div>
                <div id="pieHoverTooltip" style="display:none;position:absolute;z-index:1000;min-width:220px;max-width:320px;max-height:280px;overflow-y:auto;padding:12px 14px;background:#0f1219;border:1px solid #333;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,0.8);pointer-events:none;left:50%;transform:translateX(-50%);bottom:calc(100% + 12px);"></div>
            </div>
        `;

        const legend = indicators.map(ind => {
            const pct = Math.round((totals[ind.key] / total) * 100);
            return `<div class="stats-legend-item" data-cat="${ind.key}" style="display:flex;align-items:center;gap:6px;font-size:0.7rem;cursor:pointer;padding:3px 6px;border-radius:4px;transition:background 0.15s;" onmouseenter="this.style.background='#1a1d27'" onmouseleave="this.style.background=''">
                <div style="width:10px;height:10px;border-radius:2px;background:${ind.color};"></div>
                <span style="color:#aaa;">${ind.label}: ${totals[ind.key]} (${pct}%)</span>
            </div>`;
        }).join('');

        container.innerHTML = `
            <div style="text-align:center;">
                <div style="font-size:0.72rem;color:#888;margin-bottom:8px;">${data.username || vendor} — ${period} (${(data.months||[]).length} meses, ${data.entry_count} textos)</div>
                ${pieChart}
                <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:12px;">
                    ${legend}
                </div>
                <div id="statsWordDetail" style="margin-top:10px;text-align:left;display:none;padding:8px;background:#0a0c14;border:1px solid #1e2130;border-radius:6px;max-height:150px;overflow-y:auto;"></div>
            </div>
        `;

        // Add click handlers to legend items
        container.querySelectorAll('.stats-legend-item').forEach(el => {
            el.addEventListener('click', function() {
                const cat = this.getAttribute('data-cat');
                const detail = window._adminWordDetail[cat] || {};
                const detailEl = document.getElementById('statsWordDetail');
                if (!detailEl) return;
                const entries = Object.entries(detail).sort((a,b) => b[1] - a[1]).slice(0, 15);
                if (entries.length === 0) {
                    detailEl.innerHTML = '<div style="color:#555;font-size:0.7rem;">Sin detalle de palabras para esta categoria.</div>';
                } else {
                    const catTotal = entries.reduce((s, e) => s + e[1], 0);
                    detailEl.innerHTML = '<div style="font-size:0.68rem;color:#aaa;margin-bottom:4px;font-weight:600;">' + cat.replace(/_/g, ' ') + ' — Top palabras:</div>' + entries.map(([word, count]) => {
                        const wpct = Math.round((count / catTotal) * 100);
                        return '<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid #1a1d27;font-size:0.65rem;"><span style="color:#ccc;">' + word + '</span><span style="color:#888;">' + count + 'x (' + wpct + '%)</span></div>';
                    }).join('');
                }
                detailEl.style.display = 'block';
            });
        });

        // Hover/touch on pie chart segments — show tooltip with word detail
        const pieEl = document.getElementById('statsPieChart');
        const tooltipEl = document.getElementById('pieHoverTooltip');
        if (pieEl && tooltipEl) {
            function getSegmentAtAngle(angleDeg) {
                if (!window._pieSegments) return null;
                for (const seg of window._pieSegments) {
                    if (angleDeg >= seg.startDeg && angleDeg < seg.endDeg) return seg;
                }
                return null;
            }

            function getAngleFromEvent(e, rect) {
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                const clientX = e.touches ? e.touches[0].clientX : e.clientX;
                const clientY = e.touches ? e.touches[0].clientY : e.clientY;
                const dx = clientX - cx;
                const dy = clientY - cy;
                // Distance from center — ignore if inside donut hole
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < rect.width * 0.2) return -1; // inside hole
                let angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90;
                if (angle < 0) angle += 360;
                return angle;
            }

            function showPieTooltip(seg) {
                if (!seg) { tooltipEl.style.display = 'none'; return; }
                const detail = window._adminWordDetail[seg.key] || {};
                const entries = Object.entries(detail).sort((a,b) => b[1] - a[1]);
                const segTotal = entries.reduce((s, e) => s + e[1], 0) || 1;
                // seg.pct is the segment's % of the total pie (e.g. 5%)
                // Each word's share = (wordCount / segTotal) * seg.pct
                // So all words inside sum exactly to seg.pct
                let html = '<div style="font-size:0.8rem;color:' + seg.color + ';font-weight:700;margin-bottom:8px;border-bottom:1px solid ' + seg.color + '44;padding-bottom:6px;letter-spacing:0.02em;">' + seg.pct + '% · ' + seg.label + '</div>';
                if (entries.length > 0) {
                    const maxCount = entries[0][1] || 1;  // top word for relative bar scaling
                    html += '<div style="display:flex;flex-direction:column;gap:4px;">';
                    entries.slice(0, 15).forEach(function(e) {
                        // Proportion of this word within the segment's total percentage
                        const wordShare = (e[1] / segTotal) * seg.pct;
                        const displayPct = wordShare < 0.1 ? '<0.1' : wordShare.toFixed(1);
                        // Bar scaled relative to the most frequent word (clearer visual).
                        const barWidth = Math.max(Math.round((e[1] / maxCount) * 100), 6);
                        html += '' +
                          '<div style="display:flex;align-items:center;gap:8px;">' +
                            '<div style="width:42px;text-align:right;font-size:0.64rem;color:' + seg.color + ';font-weight:700;font-variant-numeric:tabular-nums;">' + displayPct + '%</div>' +
                            '<div style="flex:1;background:#12141c;border:1px solid ' + seg.color + '22;border-radius:5px;height:18px;position:relative;overflow:hidden;">' +
                              '<div style="position:absolute;left:0;top:0;height:100%;width:' + Math.min(barWidth, 100) + '%;background:linear-gradient(90deg,' + seg.color + '55,' + seg.color + '22);border-radius:5px;"></div>' +
                              '<span style="position:relative;z-index:1;font-size:0.62rem;color:#f0f0f0;padding-left:8px;line-height:18px;white-space:nowrap;">' + e[0] + '</span>' +
                            '</div>' +
                            '<div style="font-size:0.6rem;color:#999;min-width:32px;text-align:right;font-variant-numeric:tabular-nums;">' + e[1] + 'x</div>' +
                          '</div>';
                    });
                    if (entries.length > 15) {
                        html += '<div style="font-size:0.58rem;color:#666;text-align:center;margin-top:4px;">+ ' + (entries.length - 15) + ' palabras mas</div>';
                    }
                    html += '</div>';
                } else {
                    html += '<div style="font-size:0.62rem;color:#666;">Sin detalle de palabras disponible</div>';
                }
                tooltipEl.innerHTML = html;
                tooltipEl.style.display = 'block';
                tooltipEl.style.borderColor = seg.color + '66';
            }

            let lastSegKey = null;
            pieEl.addEventListener('mousemove', function(e) {
                const rect = pieEl.getBoundingClientRect();
                const angle = getAngleFromEvent(e, rect);
                if (angle < 0) { tooltipEl.style.display = 'none'; lastSegKey = null; return; }
                const seg = getSegmentAtAngle(angle);
                if (seg && seg.key !== lastSegKey) {
                    lastSegKey = seg.key;
                    showPieTooltip(seg);
                } else if (!seg) {
                    tooltipEl.style.display = 'none';
                    lastSegKey = null;
                }
            });

            pieEl.addEventListener('mouseleave', function() {
                tooltipEl.style.display = 'none';
                lastSegKey = null;
            });

            // Mobile: long-press to show, release to hide
            let _pieTouchTimer = null;
            pieEl.addEventListener('touchstart', function(e) {
                const rect = pieEl.getBoundingClientRect();
                const angle = getAngleFromEvent(e, rect);
                if (angle < 0) return;
                const seg = getSegmentAtAngle(angle);
                _pieTouchTimer = setTimeout(function() {
                    showPieTooltip(seg);
                }, 350);
            }, {passive: true});

            pieEl.addEventListener('touchend', function() {
                if (_pieTouchTimer) { clearTimeout(_pieTouchTimer); _pieTouchTimer = null; }
                setTimeout(function() { tooltipEl.style.display = 'none'; }, 2500);
            }, {passive: true});

            pieEl.addEventListener('touchmove', function() {
                if (_pieTouchTimer) { clearTimeout(_pieTouchTimer); _pieTouchTimer = null; }
                tooltipEl.style.display = 'none';
            }, {passive: true});
        }
    } catch(e) {
        console.error('Stats error:', e);
        container.innerHTML = '<div style="color:#f55b5b;font-size:0.8rem;">Error cargando estadisticas: ' + e.message + '</div>';
    }
}

async function deleteSavedText(entryId) {
    if (!confirm('Eliminar este texto del historial?')) return;
    try {
        const response = await fetch(`/delete-entry/${entryId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            loadSavedTexts();
            if (typeof loadHistory === 'function') loadHistory();
        }
    } catch(e) {
        console.error('Error deleting:', e);
    }
}

async function deleteLastEntry() {
    if (!confirm('¿Eliminar este texto del historial? Esta accion no se puede deshacer.')) return;

    try {
        const response = await fetch('/delete-last-entry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            // Hide the save confirmation
            const conf = document.querySelector('.save-confirmation');
            if (conf) {
                conf.innerHTML = '<div style="color:#f55b5b; font-size:0.8rem; padding:8px;">🗑️ Texto eliminado del historial.</div>';
                setTimeout(() => { conf.style.display = 'none'; }, 3000);
            }
            // Refresh history and saved texts
            if (typeof loadHistory === 'function') loadHistory();
            loadSavedTexts();
        } else {
            alert('No se pudo eliminar: ' + (data.message || 'Error desconocido'));
        }
    } catch(e) {
        console.error('Error deleting:', e);
    }
}

function srcToggle(section) {
    // Not used inline anymore — kept for compatibility
    return '';
}

function getRelevantFragments(section) {
    var text = window._lastInputText || '';
    if (!text || text.length < 50) return [];
    var keywords = [];
    if (section === 'meaning') keywords = ['precio', 'cuota', 'entrega', 'pesos', 'dolares', 'usd', 'oferta', 'promocion', 'descuento', 'negociar', 'condicion', 'monto', 'valor', 'costo'];
    else if (section === 'seller') keywords = ['vendedor', 'le ofrezco', 'tenemos', 'le puedo', 'podemos', 'le sugiero', 'le recomiendo', 'nuestra empresa', 'nuestro compromiso'];
    else if (section === 'tips') keywords = ['no se', 'pensar', 'duda', 'caro', 'lejos', 'problema', 'pero', 'no puedo', 'dificil', 'objecion', 'esperar'];
    else if (section === 'next') keywords = ['reserva', 'firma', 'cierre', 'agenda', 'coordin', 'miercoles', 'manana', 'visita', 'compromet', 'acepto', 'dale', 'perfecto'];
    else keywords = ['precio', 'cuota', 'terreno', 'lote', 'barrio'];

    // Scan the ENTIRE text and collect ALL matching sentences
    var sentences = text.split(/[.!?]+/).filter(function(s) { return s.trim().length > 20; });
    var allMatches = [];
    for (var i = 0; i < sentences.length; i++) {
        var lower = sentences[i].toLowerCase();
        for (var j = 0; j < keywords.length; j++) {
            if (lower.indexOf(keywords[j]) >= 0) {
                var trimmed = sentences[i].trim();
                if (allMatches.indexOf(trimmed) < 0) allMatches.push(trimmed);
                break;
            }
        }
    }

    // Select up to 5 distributed across the text (beginning, middle, end)
    if (allMatches.length <= 5) return allMatches;
    var step = Math.floor(allMatches.length / 5);
    return [allMatches[0], allMatches[step], allMatches[step*2], allMatches[step*3], allMatches[allMatches.length-1]];
}

function renderSentimentDetail(sentiment) {
    const details = {
        'POSITIVE': {
            icon: '😊',
            desc: 'El tono del texto es positivo. El emisor expresa satisfaccion, entusiasmo o aprobacion.',
            meaning: 'Un sentimiento positivo indica que el cliente esta contento, interesado o satisfecho con la propuesta. Es el mejor momento para avanzar.',
            forSeller: 'El cliente esta receptivo. Aprovecha este momento para proponer el siguiente paso: visita, oferta formal o cierre.',
            tips: ['Reforzar los puntos que generan entusiasmo', 'Proponer accion inmediata mientras el animo es alto', 'No sobre-vender: el cliente ya esta convencido', 'Solicitar referidos aprovechando la buena disposicion'],
            risk: 'Bajo. El cliente esta en buena disposicion.'
        },
        'NEUTRAL': {
            icon: '😐',
            desc: 'El tono del texto es neutral. No hay emociones fuertes ni positivas ni negativas.',
            meaning: 'Un sentimiento neutral puede indicar que el cliente esta evaluando friamente, es profesional en su comunicacion, o aun no se ha formado una opinion.',
            forSeller: 'El cliente no esta ni entusiasmado ni molesto. Necesitas generar emocion positiva: mostrar beneficios, crear urgencia o conectar emocionalmente.',
            tips: ['Hacer preguntas para descubrir motivaciones emocionales', 'Presentar beneficios que conecten con sus necesidades', 'Usar testimonios o casos de exito similares', 'No asumir desinteres: neutral no es negativo'],
            risk: 'Medio. Puede ir hacia cualquier lado. Necesita estimulo.'
        },
        'NEGATIVE': {
            icon: '😟',
            desc: 'El tono del texto es negativo. El emisor expresa insatisfaccion, preocupacion o rechazo.',
            meaning: 'Un sentimiento negativo indica problemas: objeciones no resueltas, expectativas no cumplidas o mala experiencia previa.',
            forSeller: 'Atencion: el cliente esta insatisfecho. Antes de vender, necesitas resolver el problema. Escucha activamente y valida sus preocupaciones.',
            tips: ['Escuchar sin interrumpir ni justificar', 'Validar la preocupacion del cliente', 'Ofrecer solucion concreta al problema planteado', 'No presionar la venta hasta resolver la objecion', 'Si es necesario, ofrecer alternativas o compensaciones'],
            risk: 'Alto. Riesgo de perder al cliente si no se maneja bien.'
        }
    };
    const d = details[sentiment] || details['NEUTRAL'];
    return `
        <div class="intent-detail-panel">
            <div class="intent-detail-header">${d.icon} Sentimiento: ${sentiment}</div>
            <div class="intent-detail-desc">${d.desc}</div>
            <div class="intent-detail-section">
                <div class="intent-section-title">Que significa para la venta</div>
                <div class="intent-section-text">${d.meaning}</div>
                <div class="src-toggle-inline" data-section="meaning">▼</div>
                <div class="src-fragment-inline" style="display:none;"></div>
            </div>
            <div class="intent-detail-section intent-seller-box">
                <div class="intent-section-title">👤 Para el vendedor</div>
                <div class="intent-section-text">${d.forSeller}</div>
                <div class="src-toggle-inline" data-section="seller">▼</div>
                <div class="src-fragment-inline" style="display:none;"></div>
            </div>
            <div class="intent-detail-section">
                <div class="intent-section-title">💡 Tips practicos</div>
                <ul class="intent-tips-list">
                    ${d.tips.map(t => `<li>${t}</li>`).join('')}
                </ul>
                <div class="src-toggle-inline" data-section="tips">▼</div>
                <div class="src-fragment-inline" style="display:none;"></div>
            </div>
            <div class="intent-detail-section" style="border-left:3px solid ${sentiment === 'NEGATIVE' ? '#f55b5b' : sentiment === 'POSITIVE' ? '#5bf5a3' : '#f5a35b'}">
                <div class="intent-section-title">⚠️ Nivel de riesgo</div>
                <div class="intent-section-text">${d.risk}</div>
                <div class="src-toggle-inline" data-section="tips">▼</div>
                <div class="src-fragment-inline" style="display:none;"></div>
            </div>
        </div>
    `;
}

function renderSalesConceptsDetail(concepts) {
    if (!concepts || concepts.length === 0) return '';
    const conceptInfo = {
        'offer': { icon: '🏷️', label: 'Oferta', desc: 'Se detecto una oferta comercial activa.', tip: 'Asegurate de que la oferta sea clara, con precio y condiciones. Facilita el siguiente paso.' },
        'discount': { icon: '🔖', label: 'Descuento', desc: 'Se menciona un descuento o reduccion de precio.', tip: 'Los descuentos crean urgencia. Establece un plazo limite para maximizar el efecto.' },
        'commission': { icon: '💼', label: 'Comision', desc: 'Se habla de comisiones o honorarios del agente.', tip: 'Transparencia en comisiones genera confianza. Deja claro quien paga que.' },
        'closing': { icon: '✅', label: 'Cierre', desc: 'Hay indicios de cierre de operacion.', tip: 'No agregues friccion. Facilita la firma y coordina todos los pasos finales.' },
        'prospect': { icon: '🎯', label: 'Prospecto', desc: 'Se menciona un prospecto o comprador potencial.', tip: 'Califica al prospecto: presupuesto, plazo, necesidades. No pierdas tiempo con no calificados.' },
        'objection': { icon: '🚫', label: 'Objecion', desc: 'Se detecto una objecion o preocupacion del cliente.', tip: 'Escucha la objecion completa, valida y responde con datos. Nunca ignores una objecion.' },
        'follow_up': { icon: '📞', label: 'Seguimiento', desc: 'Se menciona seguimiento o contacto futuro.', tip: 'El seguimiento es clave. Programa recordatorios y cumple siempre lo prometido.' },
        'negotiation': { icon: '⚖️', label: 'Negociacion', desc: 'Se estan negociando terminos o condiciones.', tip: 'Negocia con margen. Ten claro tu precio minimo y ofrece valor en vez de solo bajar precio.' }
    };
    let html = '<div class="concepts-detail-panel">';
    html += '<div class="concepts-detail-title">Detalle de conceptos detectados</div>';
    concepts.forEach(c => {
        const info = conceptInfo[c.concept] || { icon: '📎', label: c.concept, desc: 'Concepto detectado.', tip: 'Evaluar en contexto.' };
        const confPct = (c.confidence * 100).toFixed(0);
        html += `<div class="concept-detail-item">
            <div class="concept-detail-head">
                <span>${info.icon} <strong>${info.label}</strong></span>
                <span class="concept-conf">${confPct}%</span>
            </div>
            <div class="concept-detail-desc">${info.desc}</div>
            <div class="concept-detail-source">${c.source_text ? c.source_text.split(' /// ').map(f => '<div class="phrase-chip" data-word="' + f.replace(/"/g, '&quot;') + '" data-group="intent" style="margin:3px 0; padding:3px 8px; background:#0a0c14; border-left:2px solid #7b5bf5; border-radius:3px; cursor:pointer; transition:background 0.15s;"><em>"' + f + '"</em></div>').join('') : '<em>Sin fragmento</em>'}</div>
            <div class="concept-detail-tip">💡 ${info.tip}</div>
        </div>`;
    });
    html += '</div>';
    return html;
}

function renderRealEstateConceptsDetail(concepts) {
    if (!concepts || concepts.length === 0) return '';
    const conceptInfo = {
        'property_type': { icon: '🏠', label: 'Tipo de propiedad', desc: 'Se identifica el tipo de inmueble.', tip: 'Adapta tu discurso al tipo de propiedad. Un apartamento se vende diferente a un terreno.' },
        'price': { icon: '💰', label: 'Precio', desc: 'Se menciona precio o valor del inmueble.', tip: 'Justifica el precio con comparables del mercado. Ten datos listos para respaldar.' },
        'area_sqm': { icon: '📐', label: 'Metraje', desc: 'Se menciona el area o superficie.', tip: 'Relaciona el metraje con el precio por m2 de la zona para mostrar valor.' },
        'bedrooms': { icon: '🛏️', label: 'Habitaciones', desc: 'Se menciona cantidad de habitaciones.', tip: 'Las habitaciones definen el perfil del comprador. Adapta tu pitch al tipo de familia.' },
        'bathrooms': { icon: '🚿', label: 'Banos', desc: 'Se menciona cantidad de banos.', tip: 'Banos adicionales agregan valor. Destaca si tiene bano en suite o de servicio.' },
        'location': { icon: '📍', label: 'Ubicacion', desc: 'Se menciona la ubicacion del inmueble.', tip: 'La ubicacion es el factor #1. Destaca cercanias: colegios, transporte, comercios.' },
        'amenities': { icon: '🏊', label: 'Amenidades', desc: 'Se mencionan amenidades o servicios.', tip: 'Las amenidades justifican precio premium. Calcula el ahorro vs. pagar gym/pool aparte.' },
        'zoning': { icon: '📋', label: 'Zonificacion', desc: 'Se menciona zonificacion o uso de suelo.', tip: 'La zonificacion define el potencial. Comercial = mas valor. Verifica restricciones.' },
        'condition': { icon: '🔧', label: 'Estado', desc: 'Se menciona el estado o condicion del inmueble.', tip: 'Se honesto con el estado. Si necesita arreglos, presenta presupuesto y descuenta del precio.' }
    };
    let html = '<div class="concepts-detail-panel">';
    html += '<div class="concepts-detail-title">Detalle de conceptos detectados</div>';
    concepts.forEach(c => {
        const info = conceptInfo[c.concept] || { icon: '📎', label: c.concept, desc: 'Concepto detectado.', tip: 'Evaluar en contexto.' };
        const confPct = (c.confidence * 100).toFixed(0);
        html += `<div class="concept-detail-item">
            <div class="concept-detail-head">
                <span>${info.icon} <strong>${info.label}</strong></span>
                <span class="concept-conf">${confPct}%</span>
            </div>
            <div class="concept-detail-desc">${info.desc}</div>
            <div class="concept-detail-source">${c.source_text ? c.source_text.split(' /// ').map(f => '<div class="phrase-chip" data-word="' + f.replace(/"/g, '&quot;') + '" data-group="intent" style="margin:3px 0; padding:3px 8px; background:#0a0c14; border-left:2px solid #7b5bf5; border-radius:3px; cursor:pointer; transition:background 0.15s;"><em>"' + f + '"</em></div>').join('') : '<em>Sin fragmento</em>'}</div>
            <div class="concept-detail-tip">💡 ${info.tip}</div>
        </div>`;
    });
    html += '</div>';
    return html;
}

function highlightSingleWord(word, indicatorKey) {
    const textarea = document.getElementById('textInput');
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    const text = textarea.value;

    if (!text) return;

    // Build highlighted HTML for just this one word
    const highlightedHtml = buildHighlightedText(text, [word], indicatorKey);

    overlay.innerHTML = highlightedHtml;
    overlay.classList.add('active');
    closeBtn.classList.add('active');

    // Scroll to the textarea area
    const wrapper = document.getElementById('textareaWrapper');
    wrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Auto-scroll inside the overlay to the first highlighted span
    setTimeout(function() {
        const firstHl = overlay.querySelector('.hl-' + indicatorKey);
        if (firstHl) {
            firstHl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, 300);
}

function highlightEntityInText(rawValue) {
    const textarea = document.getElementById('textInput');
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    const text = textarea.value;

    if (!text) return;

    // Use a generic entity highlight class
    const highlightedHtml = buildHighlightedText(text, [rawValue], 'indicios_cierre');

    overlay.innerHTML = highlightedHtml;
    overlay.classList.add('active');
    closeBtn.classList.add('active');

    // Scroll to the textarea area
    const wrapper = document.getElementById('textareaWrapper');
    wrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Auto-scroll inside the overlay to the first highlighted span
    setTimeout(function() {
        const firstHl = overlay.querySelector('.hl-indicios_cierre');
        if (firstHl) {
            firstHl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }, 300);
}

function highlightInText(indicatorKey) {
    const textarea = document.getElementById('textInput');
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    const text = textarea.value;

    if (!text || !_lastCommercialData || !_lastCommercialData.detalle) return;

    const detail = _lastCommercialData.detalle[indicatorKey];
    if (!detail || Object.keys(detail).length === 0) return;

    // Get the words to highlight for this indicator
    const words = Object.keys(detail);

    // Build highlighted HTML
    const highlightedHtml = buildHighlightedText(text, words, indicatorKey);

    overlay.innerHTML = highlightedHtml;
    overlay.classList.add('active');
    closeBtn.classList.add('active');

    // Auto-scroll the viewport to the text box, then to the first highlight.
    const wrapper = document.getElementById('textareaWrapper') || overlay;
    wrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(function() {
        const firstHl = overlay.querySelector('.hl-' + indicatorKey);
        if (firstHl) firstHl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 350);
}

function buildHighlightedText(text, words, indicatorKey) {
    // Normalize function to remove accents for matching
    function normalize(str) {
        return str.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
    }

    const normalizedText = normalize(text);
    const hlClass = 'hl-' + indicatorKey;

    // Find all match positions
    let matches = [];
    for (const word of words) {
        // Special handling for "si" in respuestas_afirmativas:
        // Only highlight affirmative "si" (at sentence start + comma/period/exclamation)
        if (indicatorKey === 'respuestas_afirmativas' && word === 'si') {
            const affirmativePatterns = [
                /(?:^|[.!?\\n]\\s*)si(?:\\s*[,.]|\\s*$)/gim,
                /(?:^|[.!?\\n]\\s*)si,\\s/gim,
                /(?:^|[.!?\\n]\\s*)si[.!]/gim,
            ];
            for (const pattern of affirmativePatterns) {
                let match;
                while ((match = pattern.exec(normalizedText)) !== null) {
                    // Find the actual "si" position within the match
                    const siIdx = match[0].toLowerCase().indexOf('si');
                    const start = match.index + siIdx;
                    matches.push({ start: start, end: start + 2 });
                }
            }
            continue;
        }

        const normalizedWord = normalize(word);
        // Use word boundary matching for short words, substring for long phrases
        const escapedWord = normalizedWord.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
        let regex;
        if (normalizedWord.split(' ').length > 3) {
            // Long phrase: search as substring (no word boundaries)
            regex = new RegExp(escapedWord, 'gi');
        } else {
            regex = new RegExp('(?<![a-z])' + escapedWord + '(?![a-z])', 'gi');
        }
        let match;
        while ((match = regex.exec(normalizedText)) !== null) {
            matches.push({ start: match.index, end: match.index + match[0].length });
        }
    }

    // Sort by position and merge overlapping
    matches.sort((a, b) => a.start - b.start);
    const merged = [];
    for (const m of matches) {
        if (merged.length > 0 && m.start <= merged[merged.length - 1].end) {
            merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, m.end);
        } else {
            merged.push({ ...m });
        }
    }

    // Build HTML with highlights using original text characters
    let result = '';
    let lastIdx = 0;
    for (const m of merged) {
        // Add text before this match
        result += escapeHtml(text.substring(lastIdx, m.start));
        // Add highlighted match (use original text casing)
        result += `<span class="${hlClass}">${escapeHtml(text.substring(m.start, m.end))}</span>`;
        lastIdx = m.end;
    }
    result += escapeHtml(text.substring(lastIdx));

    // Highlight roles: Vendedor=green, Cliente=orange
    result = result.replace(/(Vendedor)/g, '<span style="color:#5bf5a3;font-weight:700;">$1</span>');
    result = result.replace(/(Cliente(?:\\s*\\d*)?)/g, '<span style="color:#f5a35b;font-weight:700;">$1</span>');

    return result;
}

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function closeHighlightOverlay() {
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    if (overlay) overlay.classList.remove('active');
    if (closeBtn) closeBtn.classList.remove('active');
    // Reset the "Resaltar palabras" toggle so its state stays consistent
    window._resaltarActivo = false;
    const rp = document.getElementById('btnResaltarPalabras');
    const pr = document.getElementById('btnImprimirResaltado');
    if (rp) { rp.style.background = 'linear-gradient(135deg,#2a2d3a,#1a1d27)'; rp.style.color = '#e0e0e0'; }
    if (pr) pr.style.display = 'none';
}

// Close the highlight overlay with the Escape key (accessibility / easy exit)
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const ov = document.getElementById('highlightOverlay');
        if (ov && ov.classList.contains('active')) closeHighlightOverlay();
    }
});

// ── RESALTAR PALABRAS (toggle all detected keywords with category colors) ──
window._resaltarActivo = false;

// Build HTML highlighting ALL detected keywords across ALL categories at once,
// each with its own category color class (hl-<indicatorKey>).
function buildAllHighlightedText(text) {
    function normalize(str) {
        return str.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
    }
    const normalizedText = normalize(text);

    // Collect matches from every category present in _lastCommercialData.detalle
    const detalle = (_lastCommercialData && _lastCommercialData.detalle) || {};
    let matches = [];  // {start, end, key}
    Object.keys(detalle).forEach(function(key) {
        const words = Object.keys(detalle[key] || {});
        for (const word of words) {
            if (key === 'respuestas_afirmativas' && word === 'si') {
                const patterns = [
                    /(?:^|[.!?\\n]\\s*)si(?:\\s*[,.]|\\s*$)/gim,
                    /(?:^|[.!?\\n]\\s*)si,\\s/gim,
                    /(?:^|[.!?\\n]\\s*)si[.!]/gim,
                ];
                for (const pat of patterns) {
                    let mm;
                    while ((mm = pat.exec(normalizedText)) !== null) {
                        const siIdx = mm[0].toLowerCase().indexOf('si');
                        const start = mm.index + siIdx;
                        matches.push({ start: start, end: start + 2, key: key });
                    }
                }
                continue;
            }
            const nw = normalize(word);
            const esc = nw.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
            let regex;
            if (nw.split(' ').length > 3) {
                regex = new RegExp(esc, 'gi');
            } else {
                regex = new RegExp('(?<![a-z])' + esc + '(?![a-z])', 'gi');
            }
            let m;
            while ((m = regex.exec(normalizedText)) !== null) {
                matches.push({ start: m.index, end: m.index + m[0].length, key: key });
            }
        }
    });

    if (matches.length === 0) return null;

    // Sort by start; drop overlaps (keep the first / longest-anchored match)
    matches.sort((a, b) => a.start - b.start || b.end - a.end);
    const merged = [];
    let lastEnd = -1;
    for (const m of matches) {
        if (m.start >= lastEnd) {
            merged.push(m);
            lastEnd = m.end;
        }
    }

    let result = '';
    let lastIdx = 0;
    for (const m of merged) {
        result += escapeHtml(text.substring(lastIdx, m.start));
        result += '<span class="hl-' + m.key + '">' + escapeHtml(text.substring(m.start, m.end)) + '</span>';
        lastIdx = m.end;
    }
    result += escapeHtml(text.substring(lastIdx));

    // Role highlighting
    result = result.replace(/(Vendedor)/g, '<span style="color:#5bf5a3;font-weight:700;">$1</span>');
    result = result.replace(/(Cliente(?:\\s*\\d*)?)/g, '<span style="color:#f5a35b;font-weight:700;">$1</span>');
    return result;
}

function toggleResaltarPalabras() {
    const btn = document.getElementById('btnResaltarPalabras');
    const printBtn = document.getElementById('btnImprimirResaltado');
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    const textarea = document.getElementById('textInput');
    const wrapper = document.getElementById('textareaWrapper');
    if (!overlay || !textarea) return;

    if (window._resaltarActivo) {
        // Turn OFF
        closeHighlightOverlay();
        window._resaltarActivo = false;
        if (btn) { btn.style.background = 'linear-gradient(135deg,#2a2d3a,#1a1d27)'; btn.style.color = '#e0e0e0'; }
        if (printBtn) printBtn.style.display = 'none';
        return;
    }

    // Turn ON
    const text = textarea.value;
    if (!text) return;
    const html = buildAllHighlightedText(text);
    if (!html) {
        // Nothing detected — brief feedback
        if (btn) { btn.textContent = 'Sin palabras detectadas'; setTimeout(function(){ btn.innerHTML = '\\u{1F308} Resaltar palabras'; }, 1500); }
        return;
    }
    overlay.innerHTML = html;
    overlay.classList.add('active');
    if (closeBtn) closeBtn.classList.add('active');
    window._resaltarActivo = true;
    if (btn) { btn.style.background = 'linear-gradient(135deg,#4a6cf7,#3a5ae0)'; btn.style.color = '#fff'; }
    if (printBtn) printBtn.style.display = 'inline-flex';

    // Scroll/focus the transcript box
    if (wrapper) wrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function imprimirTextoResaltado() {
    const overlay = document.getElementById('highlightOverlay');
    if (!overlay || !overlay.innerHTML) return;
    const styledHtml = overlay.innerHTML;
    const w = window.open('', '_blank');
    if (!w) return;
    w.document.write('<html><head><title>Texto Resaltado</title><style>');
    // CRITICAL: force browsers to actually PRINT the background colors even when
    // the user has "Background graphics" turned off. Without this the highlights
    // are invisible on paper/PDF.
    w.document.write('* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; color-adjust: exact !important; }');
    w.document.write('@page { size: A4; margin: 2cm; }');
    w.document.write('body { font-family: "Segoe UI", sans-serif; line-height: 1.8; font-size: 12px; color: #111; white-space: pre-wrap; word-wrap: break-word; -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }');
    w.document.write('h1 { font-size: 16px; font-weight: 600; margin-bottom: 4px; }');
    w.document.write('.sub { font-size: 11px; color: #666; margin-bottom: 12px; }');
    w.document.write('.legend { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 16px; padding:10px; border:1px solid #ccc; border-radius:6px; }');
    w.document.write('.legend span { font-size:10px; padding:2px 8px; border-radius:3px; }');
    // Highlight classes with printable colors (backgrounds tuned for white paper).
    // Each rule forces the background to print via print-color-adjust:exact.
    const hlCss = 'padding:0 2px;border-radius:3px;-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;';
    w.document.write('.hl-palabras_positivas{background:#fff17a !important;' + hlCss + '}');
    w.document.write('.hl-respuestas_afirmativas{background:#8ce6a6 !important;' + hlCss + '}');
    w.document.write('.hl-indicios_cierre{background:#ffc266 !important;' + hlCss + '}');
    w.document.write('.hl-escasez_comercial{background:#f39cf3 !important;' + hlCss + '}');
    w.document.write('.hl-pedidos_referidos{background:#c7aef9 !important;' + hlCss + '}');
    w.document.write('.hl-objeciones{background:#f79a9a !important;' + hlCss + '}');
    w.document.write('.hl-indicios_prospeccion{background:#93d9f7 !important;' + hlCss + '}');
    w.document.write('</style></head><body>');
    w.document.write('<h1>Texto Resaltado — Analisis de Indicadores</h1>');
    const nowStr = new Date().toLocaleDateString('es-AR', { day:'2-digit', month:'2-digit', year:'numeric' });
    w.document.write('<div class="sub">Mi Primer Casa S.A. — ' + nowStr + '</div>');
    // Color legend so whoever works on paper knows what each color means
    w.document.write('<div class="legend">');
    w.document.write('<span class="hl-palabras_positivas">Positivas</span>');
    w.document.write('<span class="hl-respuestas_afirmativas">Induccion al Si</span>');
    w.document.write('<span class="hl-indicios_cierre">Cierre</span>');
    w.document.write('<span class="hl-escasez_comercial">Escasez</span>');
    w.document.write('<span class="hl-pedidos_referidos">Referidos</span>');
    w.document.write('<span class="hl-objeciones">Objeciones</span>');
    w.document.write('<span class="hl-indicios_prospeccion">Prospeccion</span>');
    w.document.write('</div>');
    // Darken the role colors (Vendedor/Cliente) so they are readable on white paper.
    let printHtml = styledHtml
        .replace(/color:#5bf5a3;font-weight:700;/g, 'color:#1a7a3a;font-weight:700;')
        .replace(/color:#f5a35b;font-weight:700;/g, 'color:#b05a10;font-weight:700;');
    w.document.write('<div>' + printHtml + '</div>');
    w.document.write('</body></html>');
    w.document.close();
    setTimeout(function() { w.print(); }, 300);
}

// ═══════════════════════════════════════════════════════════════════════
// Stubs for highlight-define (overridden in DOMContentLoaded)
function trackTextSelection() {}
function openCategoryPopover() { var p = document.getElementById('categoryPopover'); if (p && window._selectedTextForHighlight) p.classList.toggle('active'); }
function closeCategoryPopover() { var p = document.getElementById('categoryPopover'); if (p) p.classList.remove('active'); }
function assignCategory(k) {}
function applyManualHighlights() {}
function clearManualHighlights() { window._manualHighlights = []; }

function toggleDetail(detailId, cardEl) {
    const panel = document.getElementById(detailId);
    if (!panel) return;
    const isOpen = panel.classList.contains('open');
    panel.classList.toggle('open', !isOpen);
    cardEl.classList.toggle('expanded', !isOpen);
}

function toggleMissingPanel(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    const isVisible = panel.style.display !== 'none';
    // Close all other missing panels first
    document.querySelectorAll('[id^="missing-"]').forEach(p => { p.style.display = 'none'; });
    if (!isVisible) {
        panel.style.display = 'block';
    }
}

// Safe closest(): returns null when the event target is not an Element
// (e.g. a text node or the document). Prevents "e.target.closest is not a
// function" errors that were crashing delegated handlers on every mouse move.
function _closest(e, selector) {
    let t = e && e.target;
    if (t && t.nodeType === 3) t = t.parentElement;  // text node -> parent element
    if (!t || typeof t.closest !== 'function') return null;
    return t.closest(selector);
}

// Delegated click handler for pie charts (avoids inline onclick quote issues)
document.addEventListener('click', function(e) {
    const pie = _closest(e, '.pie-chart-click');
    if (pie) {
        e.stopPropagation();
        const panelId = pie.getAttribute('data-missing');
        if (panelId) toggleMissingPanel(panelId);
        return;
    }
    // Delegated click for phrase chips — highlight word in text
    const chip = _closest(e, '.phrase-chip');
    if (chip) {
        e.stopPropagation();
        const word = chip.getAttribute('data-word');
        const group = chip.getAttribute('data-group');
        if (word && group) highlightSingleWord(word, group);
        return;
    }
    // Delegated click for source toggles — show/hide text fragment
    const srcTog = _closest(e, '.source-toggle');
    if (srcTog) {
        const targetId = srcTog.getAttribute('data-target');
        if (targetId) {
            const frag = document.getElementById(targetId);
            if (frag) {
                frag.classList.toggle('open');
                const arrow = srcTog.querySelector('.src-arrow');
                if (arrow) arrow.textContent = frag.classList.contains('open') ? '▲' : '▼';
            }
        }
    }
    // Delegated click for inline source toggles (violet arrows)
    const inlineTog = _closest(e, '.src-toggle-inline');
    if (inlineTog) {
        const section = inlineTog.getAttribute('data-section');
        const fragEl = inlineTog.nextElementSibling;
        if (fragEl && fragEl.classList.contains('src-fragment-inline')) {
            if (fragEl.style.display === 'none') {
                // Populate with relevant fragments
                const fragments = getRelevantFragments(section);
                fragEl.innerHTML = fragments.map(f => '<span class="src-phrase phrase-chip" data-word="' + f.replace(/"/g, '&quot;') + '" data-group="intent">' + f.replace(/</g, '&lt;') + '</span>').join('');
                fragEl.style.display = 'block';
                inlineTog.textContent = '▲';
            } else {
                fragEl.style.display = 'none';
                inlineTog.textContent = '▼';
            }
        }
    }
});

// Hover tooltip for pie charts (desktop: mouseenter/mouseleave)
document.addEventListener('mouseenter', function(e) {
    const pie = _closest(e, '.pie-chart-click');
    if (pie) {
        const tooltipId = pie.getAttribute('data-tooltip');
        if (tooltipId) {
            const tooltip = document.getElementById(tooltipId);
            if (tooltip) tooltip.style.display = 'block';
        }
    }
}, true);

document.addEventListener('mouseleave', function(e) {
    const pie = _closest(e, '.pie-chart-click');
    if (pie) {
        const tooltipId = pie.getAttribute('data-tooltip');
        if (tooltipId) {
            const tooltip = document.getElementById(tooltipId);
            if (tooltip) tooltip.style.display = 'none';
        }
    }
}, true);

// Long-press tooltip for pie charts (mobile: touchstart/touchend)
let _pieTooltipTimer = null;
document.addEventListener('touchstart', function(e) {
    const pie = _closest(e, '.pie-chart-click');
    if (pie) {
        const tooltipId = pie.getAttribute('data-tooltip');
        if (tooltipId) {
            _pieTooltipTimer = setTimeout(function() {
                const tooltip = document.getElementById(tooltipId);
                if (tooltip) {
                    tooltip.style.display = 'block';
                    tooltip.style.pointerEvents = 'auto';
                }
            }, 400);
        }
    }
}, {passive: true});

document.addEventListener('touchend', function(e) {
    if (_pieTooltipTimer) {
        clearTimeout(_pieTooltipTimer);
        _pieTooltipTimer = null;
    }
    // Hide all pie tooltips after a short delay
    setTimeout(function() {
        document.querySelectorAll('.pie-tooltip').forEach(function(t) {
            t.style.display = 'none';
            t.style.pointerEvents = 'none';
        });
    }, 2000);
}, {passive: true});

// Allow Ctrl+Enter to submit, and auto-analyze after 2s of inactivity
// Motion Design entrance: fade+lift the main containers within `scope` in a
// staggered cascade, so content reveals fluidly instead of appearing at once.
// Reusable for page load AND for freshly rendered results.
function animateEntrance(scope) {
    // Respect users who prefer reduced motion.
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const root = scope || document;
    const blocks = root.querySelectorAll(
        '.input-section, .card, .commercial-section, .analysis-block, .result-grid > *, .history-entry'
    );
    let i = 0;
    blocks.forEach(function(el) {
        if (el.dataset.entered === '1') return;
        el.dataset.entered = '1';
        el.style.opacity = '0';
        el.style.transform = 'translateY(10px)';
        var _ad = (window.innerWidth <= 480) ? '2.4s' : '6.4s';  // phones x1.5, else x4
        el.style.transition = 'opacity ' + _ad + ' cubic-bezier(0.22,0.61,0.36,1), transform ' + _ad + ' cubic-bezier(0.22,0.61,0.36,1)';
        i++;
        // Uniform: all blocks reveal together with the same duration (no stagger).
        setTimeout(function() {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 20);
    });
}

// ── UI SOUND ENGINE (XMB-style, synthesized) ────────────────────────────────
// Sounds are generated on the fly with the Web Audio API (oscillators +
// envelopes) — no external audio files. This gives zero-latency playback and
// avoids any third-party/copyrighted assets. Respects a persisted mute pref and
// never blocks screen readers or app logic (pure audio side-effect).
var UISound = (function() {
    var ctx = null, master = null, verb = null;
    var muted = false;
    try { muted = localStorage.getItem('uiSoundMuted') === '1'; } catch (e) {}

    function ac() {
        if (ctx) return ctx;
        try {
            var AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return null;
            ctx = new AC();
            master = ctx.createGain();
            master.gain.value = 0.85;
            master.connect(ctx.destination);
            // Longer, lush synthesized reverb tail for a soft, spacious feel.
            verb = ctx.createConvolver();
            var len = Math.floor(ctx.sampleRate * 1.1);   // ~1.1s tail
            var buf = ctx.createBuffer(2, len, ctx.sampleRate);
            for (var ch = 0; ch < 2; ch++) {
                var d = buf.getChannelData(ch);
                for (var i = 0; i < len; i++) {
                    d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.2);
                }
            }
            verb.buffer = buf;
            // Soften the reverb with a low-pass so it isn't harsh.
            var vlp = ctx.createBiquadFilter();
            vlp.type = 'lowpass'; vlp.frequency.value = 3200;
            var vgain = ctx.createGain();
            vgain.gain.value = 0.55;   // more present reverb
            verb.connect(vlp); vlp.connect(vgain); vgain.connect(master);
        } catch (e) { ctx = null; }
        return ctx;
    }

    // Bell/glass voice: a fundamental + inharmonic partials give an organic,
    // struck-bell timbre (not a flat/square beep). Percussive envelope with a
    // long exponential tail; a portion is sent to the reverb bus for space.
    // Partials at non-integer ratios (2.76, 5.4) evoke metal bars / glass.
    var PARTIALS = [
        { r: 1.0,  a: 1.0 },
        { r: 2.76, a: 0.42 },
        { r: 5.40, a: 0.16 }
    ];
    function tone(f0, f1, dur, peak, verbAmt) {
        if (muted) return;
        var c = ac();
        if (!c || !master) return;
        try {
            if (c.state === 'suspended') c.resume();
            var now = c.currentTime;
            var out = c.createGain();
            out.gain.value = 1;
            out.connect(master);
            if (verb && verbAmt > 0) {
                var send = c.createGain(); send.gain.value = verbAmt;
                out.connect(send); send.connect(verb);
            }
            // Subtle vibrato so the tone breathes instead of sitting static.
            var lfo = c.createOscillator();
            var lfoGain = c.createGain();
            lfo.frequency.value = 5.5;
            lfoGain.gain.value = f0 * 0.006;
            lfo.connect(lfoGain);
            lfo.start(now); lfo.stop(now + dur + 0.1);

            PARTIALS.forEach(function(p, idx) {
                var osc = c.createOscillator();
                var g = c.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(f0 * p.r, now);
                if (f1 && f1 !== f0) osc.frequency.exponentialRampToValueAtTime(Math.max(1, f1 * p.r), now + dur);
                lfoGain.connect(osc.frequency);
                // Higher partials decay faster — natural bell behavior.
                var pd = dur * (1 - idx * 0.22);
                var pk = peak * p.a;
                g.gain.setValueAtTime(0.0001, now);
                g.gain.exponentialRampToValueAtTime(pk, now + 0.008);          // soft strike
                g.gain.exponentialRampToValueAtTime(0.0001, now + Math.max(0.05, pd));
                osc.connect(g); g.connect(out);
                osc.start(now); osc.stop(now + dur + 0.08);
            });
        } catch (e) { /* audio must never break the UI */ }
    }

    return {
        // Soft glassy navigation tick.
        tick: function() { tone(1660, 1660, 0.09, 0.03, 0.4); },
        // Warm bell selection cue with generous echo.
        click: function() { tone(1046, 1046, 0.5, 0.06, 0.85); },
        // Back / dismiss — lower bell that fades.
        cancel: function() { tone(560, 420, 0.5, 0.05, 0.9); },
        // Rising initialization chime — two struck bells a fifth apart.
        startup: function() {
            tone(660, 660, 0.9, 0.045, 1.0);
            setTimeout(function() { tone(990, 990, 1.1, 0.04, 1.0); }, 130);
        },
        // Create/resume the AudioContext after a user gesture (autoplay policy).
        unlock: function() {
            var c = ac();
            if (c && c.state === 'suspended') { try { c.resume(); } catch (e) {} }
        },
        isMuted: function() { return muted; },
        setMuted: function(m) {
            muted = !!m;
            try { localStorage.setItem('uiSoundMuted', muted ? '1' : '0'); } catch (e) {}
        },
        toggle: function() { this.setMuted(!muted); return muted; }
    };
})();

// Global mute toggle wired to the header button. Updates label + a11y state.
function toggleUISound() {
    const nowMuted = UISound.toggle();
    if (!nowMuted) UISound.click();  // audible confirmation when turning ON
    refreshSoundToggleBtn();
}
function refreshSoundToggleBtn() {
    const btn = document.getElementById('soundToggleBtn');
    if (!btn) return;
    const m = UISound.isMuted();
    btn.innerHTML = m ? '&#128263; Sonido' : '&#128266; Sonido';  // muted vs speaker
    btn.style.color = m ? '#666' : '#7b9cff';
    btn.style.borderColor = m ? '#3a3d4a' : '#4a6cf7';
    btn.setAttribute('aria-pressed', m ? 'false' : 'true');
}

// Progressive word-by-word reveal of a transcript, tinting each word by the
// detected speaker role (Vendedor -> celeste, Cliente -> naranja). Non-blocking:
// uses CSS animation-delay per word, so the UI stays responsive.
function streamTranscript(targetEl, rawText) {
    if (!targetEl || !rawText) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        targetEl.textContent = rawText;
        return;
    }
    // Detect role per line via "Vendedor:" / "Cliente:" prefixes (case-insensitive).
    const lines = rawText.split(/\\n/);
    let html = '';
    let wordIndex = 0;
    const stepMs = 90;           // delay between words
    const maxDelay = 8000;       // cap so long texts don't take forever
    lines.forEach(function(line) {
        let role = '';
        const m = line.match(/^\\s*(vendedor|cliente|asesor|agente)\\s*:/i);
        if (m) {
            const r = m[1].toLowerCase();
            role = (r === 'cliente') ? 'role-cliente' : 'role-vendedor';
        }
        const words = line.split(/(\\s+)/);  // keep spaces
        words.forEach(function(w) {
            if (/^\\s+$/.test(w) || w === '') { html += w; return; }
            const d = Math.min(wordIndex * stepMs, maxDelay);
            wordIndex++;
            const cls = 'stream-word' + (role ? ' ' + role : '');
            html += '<span class="' + cls + '" style="--d:' + d + 'ms;">' +
                    w.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span>';
        });
        html += '<br>';
    });
    targetEl.classList.add('text-swap-enter');
    targetEl.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', () => {
    // Page entrance is handled by CSS (pageBlockIn) for reliability.
    // animateEntrance() is still used for dynamically rendered results/report.

    // Reflect the saved mute preference on the header sound button.
    refreshSoundToggleBtn();

    // Browsers block audio until the first user gesture. Unlock the AudioContext
    // on the first pointer/keyboard interaction.
    function unlockAudioOnce() {
        UISound.unlock();
        // Play the rising startup cue once, right after audio is unlocked.
        setTimeout(function() { UISound.startup(); }, 40);
        document.removeEventListener('pointerdown', unlockAudioOnce);
        document.removeEventListener('keydown', unlockAudioOnce);
    }
    document.addEventListener('pointerdown', unlockAudioOnce);
    document.addEventListener('keydown', unlockAudioOnce);

    // GLOBAL acoustic feedback: a tick fires each time the cursor ENTERS a new
    // interactive element. Tracking the last element (not a time throttle) makes
    // "gliding across the page" reliably audible without machine-gunning.
    var HOVER_SEL = '.card, .input-section, .commercial-section, .analysis-block, ' +
        '.indicator-item, .history-entry, .category-option, .pie-legend-row, ' +
        '.stats-legend-item, .report-section, .lead-badge, .card-title-collapsible, ' +
        '.phrase-chip, .ext-data-row, .intent-detail-section, button, select, input, a, circle';
    var _lastHoverEl = null;
    document.addEventListener('mouseover', function(e) {
        var t = e.target;
        if (!t || !t.closest) return;
        var el = (t.tagName && t.tagName.toLowerCase() === 'circle') ? t : t.closest(HOVER_SEL);
        if (el && el !== _lastHoverEl) {
            _lastHoverEl = el;
            UISound.tick();
        }
    });
    document.addEventListener('mouseout', function(e) {
        // Allow the same element to tick again after the pointer leaves it.
        if (e.target === _lastHoverEl) _lastHoverEl = null;
    });
    document.addEventListener('click', function(e) {
        var t = e.target;
        if (!t || !t.closest) return;
        if (t.closest('button, .category-option, .indicator-item, .pie-legend-row, .lead-badge, .card-title-collapsible, .pie-chart-click, .stats-legend-item, a')) {
            UISound.click();
        }
    });
    // Selectors (month, text, year, user, informe filters...) click on change.
    document.addEventListener('change', function(e) {
        if (e.target && e.target.tagName === 'SELECT') UISound.click();
    });

    let debounceTimer = null;
    const textarea = document.getElementById('textInput');

    textarea.addEventListener('keydown', e => {
        if (e.ctrlKey && e.key === 'Enter') {
            clearTimeout(debounceTimer);
            analyze();
        }
    });

    textarea.addEventListener('input', () => {
        closeHighlightOverlay();
    });

    // Update the preview title when the entry name input changes
    const entryNameInput = document.getElementById('entryNameInput');
    if (entryNameInput) {
        entryNameInput.addEventListener('input', () => {
            window._currentEntryName = entryNameInput.value.trim();
            const previewEl = document.querySelector('.input-preview');
            if (previewEl) {
                const title = entryNameInput.value.trim();
                if (title) {
                    previewEl.textContent = '"' + title + '"';
                }
            }
        });
    }

    // Load on page load
    if (document.getElementById('selectUser')) {
        // Admin: users already in HTML via Jinja2, just load stats
        loadAdminStats();
        // Data-protection: check for possible data loss and warn the admin
        checkBackupStatus();
    } else {
        // Regular user: load their texts
        loadSavedTexts();
    }

    // ── RESALTAR Y DEFINIR (inside DOMContentLoaded for safety) ──
    try {
        const hlCategories = [
            { key: 'palabras_positivas', label: 'Positivas', color: '#FFFF00' },
            { key: 'respuestas_afirmativas', label: 'Induccion al Si', color: '#008000' },
            { key: 'indicios_cierre', label: 'Cierre', color: '#FFA500' },
            { key: 'escasez_comercial', label: 'Escasez', color: '#FF00FF' },
            { key: 'pedidos_referidos', label: 'Referidos', color: '#b38bff' },
            { key: 'objeciones', label: 'Objeciones', color: '#FF0000' },
            { key: 'indicios_prospeccion', label: 'Prospeccion', color: '#00BFFF' }
        ];
        const hlGrid = document.getElementById('categoryGrid');
        const hlBtn = document.getElementById('btnHighlightDefine');
        const hlInfo = document.getElementById('highlightSelectionInfo');
        const hlPopover = document.getElementById('categoryPopover');
        const hlWrapper = document.getElementById('textareaWrapper');
        const hlOverlay = document.getElementById('highlightOverlay');
        const hlTextarea = document.getElementById('textInput');

        // Visible diagnostic: show init status in the info span
        if (hlInfo) {
            const missing = [];
            if (!hlGrid) missing.push('grid');
            if (!hlBtn) missing.push('btn');
            if (!hlPopover) missing.push('popover');
            if (!hlTextarea) missing.push('textarea');
            if (missing.length > 0) {
                hlInfo.textContent = '[RyD] Faltan elementos: ' + missing.join(', ');
                hlInfo.style.color = '#f55b5b';
            }
        }

        if (hlGrid && hlBtn && hlInfo && hlPopover && hlTextarea) {
            // Build grid
            hlGrid.innerHTML = hlCategories.map(c =>
                '<div class="category-option" style="--cat-color:' + c.color + ';" data-cat="' + c.key + '">' +
                '<div class="cat-dot" style="background:' + c.color + ';"></div>' +
                '<span class="cat-label">' + c.label + '</span></div>'
            ).join('');

            // Selection detection
            function hlGetSel() {
                const s = window.getSelection();
                if (s && s.toString().trim()) {
                    let node = s.anchorNode;
                    while (node) {
                        if (node === hlWrapper) return s.toString().trim();
                        node = node.parentElement;
                    }
                }
                if (hlTextarea.selectionStart !== hlTextarea.selectionEnd) {
                    return hlTextarea.value.substring(hlTextarea.selectionStart, hlTextarea.selectionEnd).trim();
                }
                return '';
            }

            function hlUpdate() {
                const sel = hlGetSel();
                if (sel) {
                    window._selectedTextForHighlight = sel;
                    hlBtn.disabled = false;
                    const d = sel.length > 35 ? sel.substring(0, 32) + '...' : sel;
                    hlInfo.textContent = 'Seleccion: "' + d + '"';
                } else {
                    window._selectedTextForHighlight = '';
                    hlBtn.disabled = true;
                    hlInfo.textContent = '';
                }
            }

            hlTextarea.addEventListener('mouseup', function() { setTimeout(hlUpdate, 10); });
            if (hlOverlay) hlOverlay.addEventListener('mouseup', function() { setTimeout(hlUpdate, 10); });
            if (hlWrapper) hlWrapper.addEventListener('mouseup', function() { setTimeout(hlUpdate, 10); });
            // Also listen for keyboard selection
            hlTextarea.addEventListener('keyup', hlUpdate);
            // selectionchange fires reliably on textareas in modern browsers
            document.addEventListener('selectionchange', function() {
                if (document.activeElement === hlTextarea) hlUpdate();
            });

            // Button is ALWAYS enabled — reads selection on click
            hlBtn.disabled = false;
            hlBtn.onclick = function() {
                // Re-read selection at click time
                hlUpdate();
                const sel = window._selectedTextForHighlight;
                if (!sel) {
                    hlInfo.textContent = 'Primero selecciona texto en el recuadro';
                    hlInfo.style.color = '#f5a35b';
                    UISound.cancel();
                    return;
                }
                hlInfo.style.color = '';
                const willOpen = !hlPopover.classList.contains('active');
                hlPopover.classList.toggle('active');
                if (willOpen) UISound.click(); else UISound.cancel();
            };

            // XMB-style tick when hovering each color option in the grid.
            hlGrid.querySelectorAll('.category-option').forEach(function(opt) {
                opt.addEventListener('mouseenter', function() { UISound.tick(); });
            });

            hlGrid.addEventListener('click', function(e) {
                const opt = _closest(e, '[data-cat]');
                if (!opt) return;
                const cat = opt.getAttribute('data-cat');
                const txt = window._selectedTextForHighlight;
                if (!txt || !cat) return;
                window._manualHighlights.push({ text: txt, category: cat });
                UISound.click();  // color selected
                hlPopover.classList.remove('active');
                window._selectedTextForHighlight = '';
                hlBtn.disabled = true;
                hlInfo.textContent = '';
                // Apply visual highlight
                const ov = document.getElementById('highlightOverlay');
                const cb = document.getElementById('highlightCloseBtn');
                const raw = hlTextarea.value;
                if (!raw) return;
                let html = raw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                window._manualHighlights.forEach(function(h) {
                    const p = h.text.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
                    try { html = html.replace(new RegExp('(' + p + ')', 'gi'), '<span class="hl-manual-' + h.category + '">$1</span>'); } catch(x) {}
                });
                ov.innerHTML = html;
                ov.classList.add('active');
                cb.classList.add('active');
            });

            // Close popover on outside click
            document.addEventListener('mousedown', function(e) {
                if (hlPopover.classList.contains('active') && !hlPopover.contains(e.target) && e.target !== hlBtn) {
                    hlPopover.classList.remove('active');
                    UISound.cancel();  // dismissed by clicking outside
                }
            });
        }
    } catch(hlErr) { console.warn('Resaltar y Definir error:', hlErr); }
});

// ── Informe de Seguimiento ────────────────────────────────────────────────

// Apply a quick period preset that adjusts the month/week selectors, then reload.
function applyInformePreset() {
    const preset = document.getElementById('informePreset');
    if (!preset) return;
    const v = preset.value;
    const monthSel = document.getElementById('informeMonth');
    const weekSel = document.getElementById('informeWeek');
    const now = new Date();
    const curMonth = now.getMonth() + 1;  // 1-12
    window._informeWeekUpto = 0;  // reset cumulative-week filter

    if (v === 'anual') {
        // Enero a la fecha: all months, all weeks
        if (monthSel) monthSel.value = '0';
        if (weekSel) weekSel.value = '0';
    } else if (v === 'mes_actual') {
        if (monthSel) monthSel.value = String(curMonth);
        if (weekSel) weekSel.value = '0';
    } else if (v === 's1' || v === 's2' || v === 's3' || v === 's4') {
        if (monthSel) monthSel.value = String(curMonth);
        if (weekSel) weekSel.value = v.substring(1);  // exact week
    } else if (v === 's12') {
        if (monthSel) monthSel.value = String(curMonth);
        if (weekSel) weekSel.value = '0';
        window._informeWeekUpto = 2;  // weeks 1..2
    } else if (v === 's123') {
        if (monthSel) monthSel.value = String(curMonth);
        if (weekSel) weekSel.value = '0';
        window._informeWeekUpto = 3;  // weeks 1..3
    } else if (v === 'custom') {
        // leave selectors as they are; user drives them manually
    }
    loadInforme();
}

// If the user changes month/week manually, switch the preset to "Personalizado"
function _informeManualChange() {
    const preset = document.getElementById('informePreset');
    if (preset) preset.value = 'custom';
    window._informeWeekUpto = 0;
    loadInforme();
}

async function loadInforme() {
    const year = document.getElementById('informeYear') ? document.getElementById('informeYear').value : '2026';
    const month = document.getElementById('informeMonth') ? document.getElementById('informeMonth').value : '0';
    const week = document.getElementById('informeWeek') ? document.getElementById('informeWeek').value : '0';
    const seller = document.getElementById('informeSeller') ? document.getElementById('informeSeller').value : '_all';
    const container = document.getElementById('informeContent');
    if (!container) return;
    container.innerHTML = '<div style="color:#555;">Cargando informe...</div>';

    try {
        const weekUpto = window._informeWeekUpto || 0;
        const resp = await fetch('/admin/informe?year=' + year + '&month=' + month + '&week=' + week + '&week_upto=' + weekUpto + '&seller=' + seller + '&_t=' + Date.now(), { cache: 'no-store' });
        if (!resp.ok) { container.innerHTML = '<div style="color:#f55b5b;">Error ' + resp.status + '</div>'; return; }
        const data = await resp.json();
        if (data.error) { container.innerHTML = '<div style="color:#f55b5b;">' + data.error + '</div>'; return; }

        const months = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
        const users = Object.keys(data.matrix).filter(u => data.user_totals[u] > 0).sort((a, b) => data.user_totals[b] - data.user_totals[a]);
        const meta = data.meta_mensual;

        // Table header
        let tableHtml = '<div class="seller-table-frame" style="overflow-x:auto;max-height:400px;border-radius:8px;">';
        tableHtml += '<table style="width:100%;border-collapse:collapse;font-size:0.72rem;">';
        tableHtml += '<thead><tr style="background:#111828;position:sticky;top:0;">';
        tableHtml += '<th style="padding:6px 8px;text-align:left;color:#888;border-bottom:1px solid #2a2d3a;">Vendedor</th>';
        for (let m = 1; m <= 12; m++) {
            tableHtml += '<th style="padding:6px 4px;text-align:center;color:#888;border-bottom:1px solid #2a2d3a;">' + months[m] + '</th>';
        }
        tableHtml += '<th style="padding:6px 8px;text-align:center;color:#fff;border-bottom:1px solid #2a2d3a;font-weight:700;">Total</th>';
        tableHtml += '</tr></thead><tbody>';

        // Rows
        users.forEach(u => {
            tableHtml += '<tr style="border-bottom:1px solid #1e2130;">';
            tableHtml += '<td style="padding:5px 8px;color:#e0e0e0;font-weight:500;white-space:nowrap;">' + u + '</td>';
            for (let m = 1; m <= 12; m++) {
                const val = data.matrix[u][m] || 0;
                let color = '#555';
                if (val >= meta) color = '#5bf5a3';
                else if (val >= meta * 0.7) color = '#f5d75b';
                else if (val >= meta * 0.3) color = '#f5a35b';
                else if (val > 0) color = '#f55b5b';
                tableHtml += '<td style="padding:5px 4px;text-align:center;color:' + color + ';font-weight:600;">' + val + '</td>';
            }
            tableHtml += '<td style="padding:5px 8px;text-align:center;color:#fff;font-weight:700;">' + data.user_totals[u] + '</td>';
            tableHtml += '</tr>';
        });

        tableHtml += '</tbody></table></div>';

        // Monthly totals
        let totalsHtml = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;">';
        for (let m = 1; m <= 12; m++) {
            const t = data.totals_per_month[m] || 0;
            if (t > 0) totalsHtml += '<span style="background:#0d0f18;border:1px solid #2a2d3a;border-radius:6px;padding:3px 8px;font-size:0.68rem;color:#aaa;">' + months[m] + ': <strong style="color:#e0e0e0;">' + t + '</strong></span>';
        }
        totalsHtml += '<span style="background:#1a3a2a;border:1px solid #2a5a3a;border-radius:6px;padding:3px 10px;font-size:0.68rem;color:#5bf5a3;font-weight:700;">Total ' + year + ': ' + data.total_general + '</span>';
        totalsHtml += '</div>';

        // Pie chart (monthly distribution)
        const monthsWithData = [];
        for (let m = 1; m <= 12; m++) {
            if ((data.totals_per_month[m] || 0) > 0) monthsWithData.push(m);
        }
        const pieColors = ['#4a6cf7', '#f5a35b', '#7b9cff', '#f5d75b', '#5bf5a3', '#f55b5b', '#b38bff', '#5bd4f5', '#ff8c00', '#a35bf5', '#88cc88', '#cc8888'];
        let pieGradient = [];
        let pieLegend = '';
        let currentDeg = 0;
        const totalForPie = data.total_general || 1;
        const pieId = 'pie_' + Math.random().toString(36).slice(2, 8);
        monthsWithData.forEach((m, i) => {
            const val = data.totals_per_month[m];
            const pct = (val / totalForPie * 100).toFixed(1);
            const deg = val / totalForPie * 360;
            const col = pieColors[i % pieColors.length];
            pieGradient.push(col + ' ' + currentDeg + 'deg ' + (currentDeg + deg) + 'deg');
            // Interactive legend row: hover/click focuses that month on the donut.
            pieLegend += '<div class="' + pieId + '-leg" data-i="' + i + '" data-start="' + currentDeg.toFixed(2) + '" data-end="' + (currentDeg + deg).toFixed(2) + '" data-col="' + col + '" style="display:flex;align-items:center;gap:5px;font-size:0.65rem;cursor:pointer;padding:2px 5px;border-radius:5px;transition:background 0.15s;">' +
                '<div style="width:9px;height:9px;border-radius:2px;background:' + col + ';flex:none;"></div>' +
                '<span style="color:#aaa;">' + months[m] + ': ' + pct + '% (' + val + ')</span></div>';
            currentDeg += deg;
        });

        let pieHtml = '<div style="display:flex;align-items:center;gap:20px;justify-content:center;margin-top:14px;flex-wrap:wrap;">';
        pieHtml += '<div id="' + pieId + '" class="pie-chart-expand" style="width:140px;height:140px;border-radius:50%;background:conic-gradient(' + pieGradient.join(',') + ');box-shadow:0 4px 12px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;transition:transform 0.2s;">';
        pieHtml += '<div style="width:60px;height:60px;border-radius:50%;background:#0f1117;display:flex;align-items:center;justify-content:center;pointer-events:none;"><span id="' + pieId + '-center" style="font-size:0.6rem;color:#aaa;text-align:center;line-height:1.1;">' + data.total_general + '</span></div></div>';
        pieHtml += '<div style="display:flex;flex-direction:column;gap:2px;">' + pieLegend + '</div></div>';
        // Store base gradient so we can restore it after focusing a slice.
        window._pieInteractive = window._pieInteractive || {};
        window._pieInteractive[pieId] = {
            base: 'conic-gradient(' + pieGradient.join(',') + ')',
            total: data.total_general
        };

        // ── LINE CHART (trend) — rendered ABOVE the pie chart ──
        // Levels of detail, responding to the active filters:
        //   • Month + Week selected  -> DAILY trend for the days of that week
        //   • Month selected (no week)-> WEEKLY trend (S1-S4) of that month
        //   • No month                -> MONTHLY trend (Jan-Dec)
        // Always reflects the active seller filter.
        let lineLabels = [];
        let lineValues = [];
        let lineTitle = '';
        if (data.filter_month > 0 && data.filter_week > 0) {
            // DAILY breakdown for the selected week
            const wk = data.filter_week;
            const startDay = (wk - 1) * 7 + 1;
            const endDay = (wk === 4) ? 31 : wk * 7;  // week 4 covers 22-31
            lineTitle = 'Tendencia diaria — ' + months[data.filter_month] + ' · Dias ' + startDay + ' al ' + endDay;
            const dusers = (data.filter_seller && data.filter_seller !== '_all')
                ? [data.filter_seller] : Object.keys(data.daily || {});
            for (let d = startDay; d <= endDay; d++) {
                let dayTotal = 0;
                dusers.forEach(u => {
                    const dd = data.daily[u] || {};
                    dayTotal += (dd[d] || dd[String(d)] || 0);
                });
                lineLabels.push(String(d));
                lineValues.push(dayTotal);
            }
        } else if (data.filter_month > 0) {
            // DAILY trend for the WHOLE month (more informative than 4 weeks)
            lineTitle = 'Tendencia diaria — ' + months[data.filter_month] + ' ' + year;
            const dusers = (data.filter_seller && data.filter_seller !== '_all')
                ? [data.filter_seller] : Object.keys(data.daily || {});
            const daysInMonth = new Date(parseInt(year), parseInt(data.filter_month), 0).getDate();
            for (let d = 1; d <= daysInMonth; d++) {
                let dayTotal = 0;
                dusers.forEach(u => {
                    const dd = data.daily[u] || {};
                    dayTotal += (dd[d] || dd[String(d)] || 0);
                });
                lineLabels.push(String(d));
                lineValues.push(dayTotal);
            }
        } else {
            // MONTHLY trend for the year
            lineTitle = 'Tendencia mensual — ' + year;
            for (let m = 1; m <= 12; m++) {
                lineLabels.push(months[m]);
                lineValues.push(data.totals_per_month[m] || 0);
            }
        }

        // Build an SVG line chart
        const lcW = 640, lcH = 180, lcPadL = 34, lcPadR = 14, lcPadT = 16, lcPadB = 26;
        const plotW = lcW - lcPadL - lcPadR;
        const plotH = lcH - lcPadT - lcPadB;
        const maxV = Math.max(1, ...lineValues);
        const n = lineValues.length;
        const stepX = n > 1 ? plotW / (n - 1) : plotW;
        let points = [];
        for (let i = 0; i < n; i++) {
            const x = lcPadL + (n > 1 ? i * stepX : plotW / 2);
            const y = lcPadT + plotH - (lineValues[i] / maxV) * plotH;
            points.push([x, y]);
        }
        // Grid lines (4 horizontal)
        let gridSvg = '';
        for (let g = 0; g <= 4; g++) {
            const gy = lcPadT + (plotH / 4) * g;
            const gv = Math.round(maxV - (maxV / 4) * g);
            gridSvg += '<line x1="' + lcPadL + '" y1="' + gy + '" x2="' + (lcW - lcPadR) + '" y2="' + gy + '" stroke="#1e2130" stroke-width="1"/>';
            gridSvg += '<text x="' + (lcPadL - 6) + '" y="' + (gy + 3) + '" text-anchor="end" font-size="9" fill="#666">' + gv + '</text>';
        }
        // Polyline path + area
        const linePath = points.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
        let areaPath = '';
        if (n > 0) {
            areaPath = 'M' + points[0][0].toFixed(1) + ',' + (lcPadT + plotH);
            points.forEach(p => { areaPath += ' L' + p[0].toFixed(1) + ',' + p[1].toFixed(1); });
            areaPath += ' L' + points[n - 1][0].toFixed(1) + ',' + (lcPadT + plotH) + ' Z';
        }
        // Unique id so multiple renders / interactivity don't collide.
        const lcId = 'lc_' + Math.random().toString(36).slice(2, 8);

        // Per-segment paths (i-1 -> i) so we can highlight the trend BACKWARD
        // from a hovered/tapped node to all previous nodes.
        let segsSvg = '';
        for (let i = 1; i < n; i++) {
            const a = points[i - 1], b = points[i];
            segsSvg += '<path class="' + lcId + '-seg" data-seg="' + i + '" d="M' + a[0].toFixed(1) + ',' + a[1].toFixed(1) +
                       ' L' + b[0].toFixed(1) + ',' + b[1].toFixed(1) +
                       '" fill="none" stroke="#4a6cf7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>';
        }
        // Dots + x labels + value labels + big transparent hit targets (touch-friendly)
        let dotsSvg = '', xlabelsSvg = '', vlabelsSvg = '', hitSvg = '';
        points.forEach((p, i) => {
            dotsSvg += '<circle class="' + lcId + '-dot" data-idx="' + i + '" cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="3.5" fill="#4a6cf7" stroke="#0a0c14" stroke-width="1.5"/>';
            xlabelsSvg += '<text x="' + p[0].toFixed(1) + '" y="' + (lcH - 8) + '" text-anchor="middle" font-size="9" fill="#888">' + lineLabels[i] + '</text>';
            if (lineValues[i] > 0) {
                vlabelsSvg += '<text class="' + lcId + '-vlbl" data-idx="' + i + '" x="' + p[0].toFixed(1) + '" y="' + (p[1] - 7).toFixed(1) + '" text-anchor="middle" font-size="9" fill="#e0e0e0" font-weight="600">' + lineValues[i] + '</text>';
            }
            // Large invisible hit area for comfortable hover/tap on mobile
            hitSvg += '<circle class="' + lcId + '-hit" data-idx="' + i + '" cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="16" fill="transparent" style="cursor:pointer;"/>';
        });
        // Value readout box (updates on hover/tap)
        const lineHead = lineTitle + (data.filter_seller && data.filter_seller !== '_all' ? ' · ' + data.filter_seller : '');
        let lineHtml = '<div class="fade-in-smooth" style="margin-top:14px;padding:12px 10px;background:#0a0c14;border:1px solid #1e2130;border-radius:10px;">';
        lineHtml += '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:8px;">';
        lineHtml += '<div style="font-size:0.72rem;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;">' + lineHead + '</div>';
        lineHtml += '<div id="' + lcId + '-readout" style="font-size:0.7rem;color:#7b9cff;font-weight:600;min-height:0.9rem;"></div>';
        lineHtml += '</div>';
        lineHtml += '<div style="width:100%;overflow-x:auto;"><svg id="' + lcId + '" viewBox="0 0 ' + lcW + ' ' + lcH + '" style="width:100%;min-width:420px;height:auto;display:block;touch-action:pan-y;">';
        lineHtml += gridSvg;
        if (areaPath) lineHtml += '<path d="' + areaPath + '" fill="rgba(74,108,247,0.12)"/>';
        lineHtml += segsSvg;
        lineHtml += dotsSvg + vlabelsSvg + xlabelsSvg + hitSvg;
        lineHtml += '</svg></div></div>';

        // Interactivity: hovering/tapping a node highlights the trend backward.
        // Registered after innerHTML is set (see the setTimeout at the end).
        window._lcInteractive = window._lcInteractive || {};
        window._lcInteractive[lcId] = { labels: lineLabels, values: lineValues };

        // Compliance summary
        let complianceHtml = '<div style="margin-top:12px;padding:10px;background:#0a0c14;border:1px solid #1e2130;border-radius:8px;font-size:0.72rem;">';
        complianceHtml += '<div style="color:#888;margin-bottom:6px;">Meta mensual: <strong style="color:#5bf5a3;">' + meta + ' audios/vendedor</strong></div>';
        if (data.cumplen.length > 0) {
            complianceHtml += '<div style="color:#5bf5a3;margin-bottom:4px;">Cumplen (' + data.cumplen.length + '): ' + data.cumplen.join(', ') + '</div>';
        }
        if (data.no_cumplen.length > 0) {
            complianceHtml += '<div style="color:#f55b5b;">No cumplen (' + data.no_cumplen.length + '): ' + data.no_cumplen.join(', ') + '</div>';
        }
        complianceHtml += '</div>';

        // --- Synthesis Text (auto-generated narrative) ---
        const cm = data.current_month;
        const cmName = months[cm] || 'mes actual';
        const cmTotal = data.totals_per_month[cm] || 0;
        const activeUsers = users.length;

        // Build a readable label of the ACTIVE period so the whole report reflects
        // exactly what is being filtered (professional presentation requirement).
        const monthFullNames = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
        let periodLabel;
        const _fm = data.filter_month || 0;
        const _fw = data.filter_week || 0;
        const _wu = data.week_upto || 0;
        const _weekRanges = { 1: '1 al 7', 2: '8 al 14', 3: '15 al 21', 4: '22 al 31' };
        if (_fm === 0) {
            periodLabel = 'Enero a la fecha · ' + year;
        } else if (_fw > 0) {
            periodLabel = monthFullNames[_fm] + ' ' + year + ' · Semana ' + _fw + ' (dias ' + (_weekRanges[_fw] || '') + ')';
        } else if (_wu > 0) {
            periodLabel = monthFullNames[_fm] + ' ' + year + ' · Primeras ' + _wu + ' semanas (dias 1 al ' + (_wu * 7) + ')';
        } else {
            periodLabel = monthFullNames[_fm] + ' ' + year + ' · mes completo';
        }
        const sellerLabel = (data.filter_seller && data.filter_seller !== '_all')
            ? data.filter_seller : 'todo el equipo';
        const cumpleCount = data.cumplen.length;
        const noCumpleCount = data.no_cumplen.length;
        const cumplePct = activeUsers > 0 ? Math.round((cumpleCount / activeUsers) * 100) : 0;
        const noCumplePct = 100 - cumplePct;

        // Find top performer this month
        let topUser = '';
        let topCount = 0;
        users.forEach(u => {
            const val = data.matrix[u][cm] || 0;
            if (val > topCount) { topCount = val; topUser = u; }
        });

        // Find worst performers
        const lowPerformers = users.filter(u => (data.matrix[u][cm] || 0) < meta && (data.matrix[u][cm] || 0) > 0);
        const zeroPerformers = users.filter(u => (data.matrix[u][cm] || 0) === 0);

        const _todayStr = new Date().toLocaleDateString('es-AR', { day: '2-digit', month: 'long', year: 'numeric' });
        let synthesisHtml = '<div style="margin-top:14px;padding:22px;background:#0a0c14;border:1px solid #1e2130;border-radius:10px;border-left:3px solid #4a6cf7;">';
        synthesisHtml += '<div style="font-size:0.95rem;color:#fff;font-weight:700;letter-spacing:0.02em;margin-bottom:4px;">Mi Primer Casa S.A.</div>';
        synthesisHtml += '<div style="font-size:0.72rem;color:#aaa;margin-bottom:2px;">Informe de Auditoria de Grabaciones y Transcripciones Comerciales</div>';
        synthesisHtml += '<div style="font-size:0.7rem;color:#5bd4f5;margin-bottom:2px;font-weight:600;">Periodo analizado: ' + periodLabel + '</div>';
        synthesisHtml += '<div style="font-size:0.66rem;color:#777;margin-bottom:2px;">Alcance: ' + sellerLabel + ' &nbsp;·&nbsp; Vendedores con actividad: ' + activeUsers + ' &nbsp;·&nbsp; Registros en el periodo: ' + data.total_general + '</div>';
        synthesisHtml += '<div style="font-size:0.64rem;color:#666;margin-bottom:14px;">Emitido el ' + _todayStr + ' &nbsp;·&nbsp; Auditor responsable: Bernardo Strauss</div>';
        synthesisHtml += '<hr style="border:none;border-top:1px solid #2a2d3a;margin-bottom:14px;">';

        // Section heading: 1. Objeto del informe
        synthesisHtml += '<div class="rep-sec-title" style="font-size:0.72rem;color:#7b9cff;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">1. Objeto del informe</div>';
        synthesisHtml += '<p style="font-size:0.76rem;color:#ccc;line-height:1.8;margin-bottom:12px;text-align:justify;">';
        synthesisHtml += 'El presente documento tiene por finalidad documentar de manera formal el proceso de seguimiento, evaluacion y analisis de las grabaciones de audio y transcripciones comerciales incorporadas al sistema de autoevaluacion durante el periodo <strong style="color:#e0e0e0;">' + periodLabel + '</strong>. A traves de esta auditoria se procura determinar el nivel de calidad de las interacciones comerciales, comunicacionales y operativas registradas, identificando fortalezas consolidadas, oportunidades concretas de mejora y patrones de desempeno relevantes para el desarrollo profesional de los vendedores. El informe se circunscribe estrictamente al alcance seleccionado (' + sellerLabel + '), de modo que las cifras, graficos y conclusiones aqui expuestos corresponden unica y exclusivamente al recorte temporal y de personal definido en los filtros activos.';
        synthesisHtml += '</p>';

        // Section heading: 2. Metodologia
        synthesisHtml += '<div class="rep-sec-title" style="font-size:0.72rem;color:#7b9cff;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">2. Metodologia de evaluacion</div>';
        synthesisHtml += '<p style="font-size:0.76rem;color:#ccc;line-height:1.8;margin-bottom:12px;text-align:justify;">';
        synthesisHtml += 'El sistema realiza un analisis integral de cada grabacion considerando las respuestas emitidas, la estructura de la conversacion, la capacidad de deteccion de necesidades, el manejo de objeciones, la claridad del mensaje, el nivel de escucha activa, el grado de vinculacion con el interlocutor y demas indicadores previamente definidos dentro de los criterios de evaluacion establecidos. Cada registro es procesado de forma independiente y sus metricas se consolidan luego a nivel individual y grupal, garantizando trazabilidad y comparabilidad entre periodos.';
        synthesisHtml += '</p>';

        // Section heading: 3. Analisis de resultados
        synthesisHtml += '<div class="rep-sec-title" style="font-size:0.72rem;color:#7b9cff;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">3. Analisis de resultados del periodo</div>';
        // Paragraph 4: Data-driven analysis
        synthesisHtml += '<p style="font-size:0.76rem;color:#ccc;line-height:1.8;margin-bottom:12px;text-align:justify;">';
        synthesisHtml += 'En el periodo analizado (<strong style="color:#e0e0e0;">' + periodLabel + '</strong>) se contabilizaron <strong style="color:#5bd4f5;">' + data.total_general + '</strong> registros correspondientes a ' + activeUsers + ' vendedor(es) con actividad. El volumen consolidado de audios y transcripciones cargados al sistema ';
        if (cmTotal >= meta * activeUsers * 0.7) {
            synthesisHtml += 'muestra un cumplimiento <strong style="color:#5bf5a3;">satisfactorio</strong> frente a las metas institucionales.';
        } else if (cmTotal >= meta * activeUsers * 0.3) {
            synthesisHtml += 'muestra un cumplimiento <strong style="color:#f5d75b;">parcial</strong> frente a las metas institucionales.';
        } else {
            synthesisHtml += 'muestra un cumplimiento <strong style="color:#f55b5b;">Insuficiente</strong> frente a las metas institucionales.';
        }
        synthesisHtml += ' Considerando que la metrica minima exigida para el cierre mensual es de <strong style="color:#5bf5a3;">' + meta + '</strong> audios por vendedor, ';
        if (cumpleCount > 0) {
            synthesisHtml += 'se constata que el <strong style="color:#5bf5a3;">' + cumplePct + '%</strong> (' + cumpleCount + ' de ' + activeUsers + ') del equipo auditado logro alcanzar y superar el objetivo establecido.';
        } else {
            synthesisHtml += 'se constata que <strong style="color:#f55b5b;">ningun vendedor</strong> del equipo auditado logro alcanzar el objetivo establecido dentro del recorte seleccionado.';
        }
        synthesisHtml += '</p>';

        synthesisHtml += '<p style="font-size:0.76rem;color:#ccc;line-height:1.8;margin-bottom:12px;text-align:justify;">';
        synthesisHtml += 'Complementariamente, este documento expone los resultados obtenidos a partir de la informacion procesada, proporcionando observaciones objetivas, metricas de desempeno y conclusiones fundamentadas que permiten comprender la situacion actual del equipo, medir su evolucion a lo largo del tiempo y disenar estrategias concretas de mejora continua. La lectura combinada de la tabla mensual, el grafico de tendencia y la distribucion porcentual habilita una interpretacion tanto cuantitativa como cualitativa del desempeno.';
        synthesisHtml += '</p>';

        // Retained legacy variable to avoid breaking downstream references
        // Section heading: 4. Desempeno individual
        synthesisHtml += '<div class="rep-sec-title" style="font-size:0.72rem;color:#7b9cff;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">4. Desempeno individual</div>';
        // Paragraph 5: Top performer detail
        if (topUser && topCount > 0) {
            synthesisHtml += '<p style="font-size:0.76rem;color:#ccc;line-height:1.8;margin-bottom:12px;text-align:justify;">';
            if (topCount >= meta) {
                synthesisHtml += 'Este desempeno positivo corresponde a <strong style="color:#4a6cf7;">' + topUser + '</strong>, quien lidero la gestion comercial con un total de <strong style="color:#5bf5a3;">' + topCount + '</strong> grabaciones acumuladas. ';
            } else {
                synthesisHtml += 'El mayor aporte del periodo corresponde a <strong style="color:#4a6cf7;">' + topUser + '</strong> con <strong style="color:#f5d75b;">' + topCount + '</strong> grabaciones acumuladas, aun por debajo de la meta de ' + meta + '. ';
            }
            synthesisHtml += '</p>';
        }

        // Paragraph 6: Non-compliance detail
        if (noCumpleCount > 0 || zeroPerformers.length > 0) {
            synthesisHtml += '<p style="font-size:0.76rem;color:#ccc;line-height:1.8;margin-bottom:12px;text-align:justify;">';
            synthesisHtml += 'Por el contrario, el <strong style="color:#f55b5b;">' + noCumplePct + '%</strong> restante del equipo presenta un incumplimiento severo de la cuota mensual. ';
            if (lowPerformers.length > 0) {
                const secondBest = lowPerformers.sort((a, b) => (data.matrix[b][cm] || 0) - (data.matrix[a][cm] || 0))[0];
                const secondCount = data.matrix[secondBest] ? data.matrix[secondBest][cm] || 0 : 0;
                if (secondCount > 0) {
                    synthesisHtml += 'A excepcion de <strong style="color:#4a6cf7;">' + secondBest + '</strong>, quien finalizo con <strong style="color:#f5d75b;">' + secondCount + '</strong> cargas, ';
                }
                synthesisHtml += 'el resto de los colaboradores registro un volumen critico y marcadamente insuficiente que oscila entre <strong style="color:#f55b5b;">0</strong> y <strong style="color:#f55b5b;">' + Math.max(...lowPerformers.map(u => data.matrix[u][cm] || 0)) + '</strong> audios totales al concluir el mes.';
            }
            synthesisHtml += '</p>';
        }

        // Section heading: 5. Conclusiones
        synthesisHtml += '<div class="rep-sec-title" style="font-size:0.72rem;color:#7b9cff;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:6px;">5. Conclusiones del periodo</div>';
        // Paragraph 7: Conclusion
        synthesisHtml += '<p style="font-size:0.76rem;color:#ccc;line-height:1.8;margin-bottom:12px;text-align:justify;">';
        synthesisHtml += 'Del analisis del periodo <strong style="color:#e0e0e0;">' + periodLabel + '</strong> se desprende que ';
        if (cumplePct >= 70) {
            synthesisHtml += 'el equipo mantiene un ritmo de carga acorde a los objetivos institucionales, lo que permite sostener una evaluacion de calidad continua y confiable. ';
        } else if (cumplePct >= 30) {
            synthesisHtml += 'el equipo presenta un cumplimiento heterogeneo: mientras algunos vendedores sostienen el ritmo esperado, otros requieren acompanamiento para alcanzar la meta. ';
        } else {
            synthesisHtml += 'existe una brecha significativa respecto a los indicadores de seguimiento definidos por la organizacion. La falta de registros por parte de la mayoria del personal impacta de forma directa en los procesos de evaluacion de calidad, limitando la disponibilidad de informacion para la mejora continua. ';
        }
        synthesisHtml += '</p>';

        // Evaluation box
        synthesisHtml += '<p style="font-size:0.76rem;line-height:1.8;margin-top:12px;padding:10px 14px;border-radius:6px;text-align:justify;';
        if (cumplePct >= 70) {
            synthesisHtml += 'color:#5bf5a3;background:#0d1a0d;border-left:3px solid #5bf5a3;">';
            synthesisHtml += '<strong>Evaluacion Final:</strong> El equipo demuestra un compromiso adecuado con el sistema de carga de audios. Se recomienda mantener el ritmo actual y reforzar el seguimiento a los vendedores que presentan rezago para consolidar el cumplimiento pleno.';
        } else if (cumplePct >= 30) {
            synthesisHtml += 'color:#f5d75b;background:#1a1a0d;border-left:3px solid #f5d75b;">';
            synthesisHtml += '<strong>Evaluacion Final:</strong> El cumplimiento es parcial. Se requiere la implementacion de seguimiento activo, reuniones de retroalimentacion y capacitaciones orientadas a elevar la tasa de carga del equipo en el proximo periodo.';
        } else {
            synthesisHtml += 'color:#f5a35b;background:#1a0d0d;border-left:3px solid #f55b5b;">';
            synthesisHtml += '<strong>Evaluacion Final:</strong> Se requiere la aplicacion urgente de planes de contingencia y capacitaciones para revertir este comportamiento en el proximo ciclo. La auditoria de grabaciones constituye una herramienta de retroalimentacion sistematica orientada al fortalecimiento de habilidades comunicacionales y comerciales, promoviendo procesos de aprendizaje basados en evidencia, autoanalisis y seguimiento permanente del desempeno individual.';
        }
        synthesisHtml += '</p>';
        synthesisHtml += '</div>';

        // --- Card 2: Detailed Observations & Recommendations ---
        let card2Html = '<div style="margin-top:14px;padding:14px;background:#0a0c14;border:1px solid #1e2130;border-radius:10px;border-left:3px solid #b38bff;">';
        card2Html += '<div style="font-size:0.75rem;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:10px;">Observaciones y Recomendaciones</div>';

        // Observation 1: Volume analysis
        card2Html += '<p style="font-size:0.76rem;color:#ccc;line-height:1.7;margin-bottom:10px;text-align:justify;">';
        card2Html += 'A traves de la presente auditoria se busca determinar el nivel de calidad de las interacciones comerciales, comunicacionales y operativas registradas en los audios cargados al sistema, permitiendo identificar fortalezas, oportunidades de mejora y patrones de desempeno relevantes para el desarrollo profesional de los Vendedores.';
        card2Html += '</p>';

        // Observation 2: Methodology
        card2Html += '<p style="font-size:0.76rem;color:#ccc;line-height:1.7;margin-bottom:10px;text-align:justify;">';
        card2Html += 'El sistema realiza un analisis integral de cada grabacion considerando las respuestas emitidas, la estructura de la conversacion, la capacidad de deteccion de necesidades, el manejo de objeciones, la claridad del mensaje, el nivel de escucha activa, el grado de vinculacion con el interlocutor y otros indicadores previamente definidos dentro de los criterios de evaluacion establecidos.';
        card2Html += '</p>';

        // Observation 3: Dynamic based on data
        card2Html += '<p style="font-size:0.76rem;color:#ccc;line-height:1.7;margin-bottom:10px;text-align:justify;">';
        if (data.total_general > 200) {
            card2Html += 'El volumen total de <strong style="color:#5bf5a3;">' + data.total_general + '</strong> registros acumulados en el periodo ' + year + ' permite establecer una base estadistica solida para la generacion de conclusiones objetivas. La muestra es representativa y permite identificar tendencias claras de comportamiento comercial a nivel individual y grupal.';
        } else if (data.total_general > 50) {
            card2Html += 'Con <strong style="color:#f5d75b;">' + data.total_general + '</strong> registros acumulados en ' + year + ', la muestra permite identificar patrones iniciales de comportamiento. Se recomienda incrementar el volumen de cargas para consolidar conclusiones estadisticamente robustas.';
        } else {
            card2Html += 'El volumen de <strong style="color:#f55b5b;">' + data.total_general + '</strong> registros en ' + year + ' resulta insuficiente para generar conclusiones estadisticas definitivas. Se requiere un compromiso urgente del equipo para aumentar el numero de grabaciones cargadas al sistema.';
        }
        card2Html += '</p>';

        // Observation 4: Purpose and next steps
        card2Html += '<p style="font-size:0.76rem;color:#ccc;line-height:1.7;margin-bottom:10px;text-align:justify;">';
        card2Html += 'Los hallazgos aqui desarrollados deberan interpretarse como un insumo de apoyo para la toma de decisiones, la optimizacion de procesos de atencion y ventas, y la consolidacion de estandares de calidad en las interacciones evaluadas. La auditoria de grabaciones constituye una herramienta de retroalimentacion sistematica orientada al fortalecimiento de habilidades comunicacionales y comerciales.';
        card2Html += '</p>';

        card2Html += '</div>';

        container.innerHTML = tableHtml + totalsHtml + lineHtml + pieHtml + complianceHtml + synthesisHtml + card2Html;
        // Wire up chart interactivity now that the SVG/pie are in the DOM.
        setTimeout(function() { attachLineChartInteractivity(); attachPieInteractivity(); attachReportSectionInteractivity(); }, 0);
        // Fluid staggered entrance for the report blocks.
        setTimeout(function() { animateEntrance(container); }, 20);
    } catch (e) {
        container.innerHTML = '<div style="color:#f55b5b;">Error: ' + e.message + '</div>';
    }
}

// Line-chart interactivity: hovering (desktop) or tapping (mobile) a data point
// highlights the trend line BACKWARD from that node to all previous ones, dims
// the rest, and shows a readout (label + value). Fully re-entrant per render.
function attachLineChartInteractivity() {
    const reg = window._lcInteractive || {};
    Object.keys(reg).forEach(function(lcId) {
        const svg = document.getElementById(lcId);
        if (!svg || svg.dataset.wired === '1') return;
        svg.dataset.wired = '1';
        const info = reg[lcId];
        const segs = Array.prototype.slice.call(svg.querySelectorAll('.' + lcId + '-seg'));
        const dots = Array.prototype.slice.call(svg.querySelectorAll('.' + lcId + '-dot'));
        const hits = Array.prototype.slice.call(svg.querySelectorAll('.' + lcId + '-hit'));
        const readout = document.getElementById(lcId + '-readout');

        function highlight(idx) {
            // Segments up to idx (backward path) get the neon accent; rest dim.
            segs.forEach(function(s) {
                const seg = parseInt(s.getAttribute('data-seg'), 10); // segment i connects i-1 -> i
                if (seg <= idx) {
                    s.setAttribute('stroke', '#7b9cff');
                    s.setAttribute('stroke-width', '3.5');
                    s.style.filter = 'drop-shadow(0 0 4px rgba(123,156,255,0.8))';
                } else {
                    s.setAttribute('stroke', '#33384a');
                    s.setAttribute('stroke-width', '2');
                    s.style.filter = 'none';
                }
            });
            dots.forEach(function(d) {
                const di = parseInt(d.getAttribute('data-idx'), 10);
                if (di <= idx) {
                    d.setAttribute('r', di === idx ? '5.5' : '4');
                    d.setAttribute('fill', '#7b9cff');
                } else {
                    d.setAttribute('r', '3');
                    d.setAttribute('fill', '#33384a');
                }
            });
            if (readout) {
                const lbl = info.labels[idx];
                const val = info.values[idx];
                let txt = lbl + ': ' + val;
                if (idx > 0) {
                    const prev = info.values[idx - 1];
                    const diff = val - prev;
                    const arrow = diff > 0 ? '▲ +' + diff : (diff < 0 ? '▼ ' + diff : '● 0');
                    txt += '  (' + arrow + ' vs ' + info.labels[idx - 1] + ')';
                }
                readout.textContent = txt;
            }
        }

        function reset() {
            segs.forEach(function(s) {
                s.setAttribute('stroke', '#4a6cf7');
                s.setAttribute('stroke-width', '2');
                s.style.filter = 'none';
            });
            dots.forEach(function(d) {
                d.setAttribute('r', '3.5');
                d.setAttribute('fill', '#4a6cf7');
            });
            if (readout) readout.textContent = '';
        }

        hits.forEach(function(h) {
            const idx = parseInt(h.getAttribute('data-idx'), 10);
            h.addEventListener('mouseenter', function() { highlight(idx); });
            h.addEventListener('mouseleave', reset);
            h.addEventListener('touchstart', function(ev) {
                ev.preventDefault();
                highlight(idx);
            }, { passive: false });
            h.addEventListener('click', function() { highlight(idx); });
        });
    });
}

// Pie interactivity: hovering/tapping a legend row focuses that month's slice
// on the donut (the rest is dimmed) and shows its value in the center hole.
function attachPieInteractivity() {
    const reg = window._pieInteractive || {};
    const DUR = (window.innerWidth <= 480) ? '2.4s' : '6.4s';  // phones x1.5, else x4
    Object.keys(reg).forEach(function(pieId) {
        const donut = document.getElementById(pieId);
        if (!donut || donut.dataset.wired === '1') return;
        donut.dataset.wired = '1';
        const info = reg[pieId];
        const center = document.getElementById(pieId + '-center');
        const rows = Array.prototype.slice.call(document.querySelectorAll('.' + pieId + '-leg'));
        donut.style.transition = 'background ' + DUR + ' cubic-bezier(0.22,0.61,0.36,1), transform ' + DUR + ' cubic-bezier(0.22,0.61,0.36,1)';

        function focusRow(row) {
            const start = parseFloat(row.getAttribute('data-start'));
            const end = parseFloat(row.getAttribute('data-end'));
            const col = row.getAttribute('data-col');
            donut.style.background = 'conic-gradient(#20232e 0deg ' + start + 'deg, ' +
                col + ' ' + start + 'deg ' + end + 'deg, #20232e ' + end + 'deg 360deg)';
            donut.style.transform = 'scale(1.04)';
            rows.forEach(function(r) { r.style.background = (r === row) ? 'rgba(255,255,255,0.08)' : ''; });
            if (center) {
                center.style.fontSize = '0.5rem';
                center.textContent = row.textContent.trim();
            }
        }
        function resetPie() {
            donut.style.background = info.base;
            donut.style.transform = 'scale(1)';
            rows.forEach(function(r) { r.style.background = ''; });
            if (center) { center.style.fontSize = '0.6rem'; center.textContent = info.total; }
        }
        // Find the legend row whose start-end range contains the pointer angle.
        function rowAtPointer(clientX, clientY) {
            const rect = donut.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const dx = clientX - cx, dy = clientY - cy;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < rect.width * 0.21 || dist > rect.width * 0.52) return null;
            let angle = Math.atan2(dy, dx) * 180 / Math.PI + 90;
            if (angle < 0) angle += 360;
            for (let k = 0; k < rows.length; k++) {
                const s = parseFloat(rows[k].getAttribute('data-start'));
                const e = parseFloat(rows[k].getAttribute('data-end'));
                if (angle >= s && angle < e && (e - s) > 0.01) return rows[k];
            }
            return null;
        }

        // Interact by pointing/tapping the FIGURE itself.
        donut.addEventListener('mousemove', function(e) {
            const row = rowAtPointer(e.clientX, e.clientY);
            if (row) focusRow(row); else resetPie();
        });
        donut.addEventListener('mouseleave', resetPie);
        donut.addEventListener('touchstart', function(e) {
            const t = e.touches[0];
            const row = rowAtPointer(t.clientX, t.clientY);
            if (row) { e.preventDefault(); focusRow(row); }
        }, { passive: false });

        // Legend rows still work too.
        rows.forEach(function(row) {
            row.addEventListener('mouseenter', function() { focusRow(row); });
            row.addEventListener('mouseleave', resetPie);
            row.addEventListener('touchstart', function(ev) { ev.preventDefault(); focusRow(row); }, { passive: false });
            row.addEventListener('click', function() { focusRow(row); });
        });
    });
}

// Indicator donut: hovering/tapping a % label inside the donut OR a legend row
// makes that slice stand out above the others (rest dimmed to grey).
function attachIndicatorPieInteractivity() {
    const reg = window._indPieInteractive || {};
    // Mirror of --anim-duration in seconds; phones use the shorter x1.5 base.
    const DUR = (window.innerWidth <= 480) ? '2.4s' : '6.4s';
    Object.keys(reg).forEach(function(id) {
        const donut = document.getElementById(id);
        if (!donut || donut.dataset.wired === '1') return;
        donut.dataset.wired = '1';
        const info = reg[id];
        const legs = Array.prototype.slice.call(document.querySelectorAll('.' + id + '-leg'));
        const pcts = Array.prototype.slice.call(document.querySelectorAll('.' + id + '-pct'));
        // Slow, uniform transitions on the donut itself.
        donut.style.transition = 'background ' + DUR + ' cubic-bezier(0.22,0.61,0.36,1), transform ' + DUR + ' cubic-bezier(0.22,0.61,0.36,1), box-shadow ' + DUR + ' cubic-bezier(0.22,0.61,0.36,1)';

        function focusIndex(i) {
            const seg = info.segments[i];
            if (!seg || seg.end - seg.start < 0.01) return;  // skip empty slices
            // Rebuild the gradient: active slice keeps its color, the rest go grey.
            const parts = info.segments.map(function(s) {
                const col = (s.i === i) ? s.color : '#24272f';
                return col + ' ' + s.start.toFixed(2) + 'deg ' + s.end.toFixed(2) + 'deg';
            });
            donut.style.background = 'conic-gradient(' + parts.join(',') + ')';
            donut.style.transform = 'scale(1.05)';
            donut.style.boxShadow = '0 6px 20px rgba(0,0,0,0.5), 0 0 22px -3px ' + seg.color + 'cc';
            legs.forEach(function(l) {
                l.style.background = (parseInt(l.getAttribute('data-i'), 10) === i) ? 'rgba(255,255,255,0.10)' : '';
                l.style.opacity = (parseInt(l.getAttribute('data-i'), 10) === i) ? '1' : '0.5';
            });
            pcts.forEach(function(p) {
                const pi = parseInt(p.getAttribute('data-i'), 10);
                p.style.opacity = (pi === i) ? '1' : '0.35';
                p.style.transform = (pi === i) ? 'translate(-50%,-50%) scale(1.35)' : 'translate(-50%,-50%)';
            });
        }
        function resetInd() {
            donut.style.background = info.base;
            donut.style.transform = 'scale(1)';
            donut.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
            legs.forEach(function(l) { l.style.background = ''; l.style.opacity = ''; });
            pcts.forEach(function(p) { p.style.opacity = ''; p.style.transform = 'translate(-50%,-50%)'; });
        }

        // Detect which slice the pointer is over, by the angle from the center.
        // conic-gradient starts at the top and goes clockwise.
        function sliceAtPointer(clientX, clientY) {
            const rect = donut.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const dx = clientX - cx, dy = clientY - cy;
            const dist = Math.sqrt(dx * dx + dy * dy);
            // Ignore the center hole and anything outside the donut.
            if (dist < rect.width * 0.21 || dist > rect.width * 0.52) return -1;
            let angle = Math.atan2(dy, dx) * 180 / Math.PI + 90;  // 0deg at top
            if (angle < 0) angle += 360;
            for (let k = 0; k < info.segments.length; k++) {
                const s = info.segments[k];
                if (angle >= s.start && angle < s.end && (s.end - s.start) > 0.01) return s.i;
            }
            return -1;
        }

        // "Explode": nudge the whole donut a few px toward the slice's mid-angle
        // and keep that slice focused, giving a detach/pop-out impression.
        function explodeSlice(i) {
            const seg = info.segments[i];
            if (!seg || seg.end - seg.start < 0.01) return;
            focusIndex(i);
            const rad = (seg.mid - 90) * Math.PI / 180;
            const dx = Math.cos(rad) * 6, dy = Math.sin(rad) * 6;  // ~6px pop-out
            donut.style.transform = 'translate(' + dx.toFixed(1) + 'px,' + dy.toFixed(1) + 'px) scale(1.06)';
        }

        // Cross-filter: clicking a SLICE highlights that category's keywords in
        // the text box and scrolls to them. Uses the existing highlightInText().
        function crossFilter(i) {
            const seg = info.segments[i];
            if (!seg || typeof highlightInText !== 'function') return;
            explodeSlice(i);
            highlightInText(seg.key);
        }

        // Pointer over the FIGURE itself (not just the legend).
        donut.addEventListener('mousemove', function(e) {
            const i = sliceAtPointer(e.clientX, e.clientY);
            if (i >= 0) focusIndex(i); else resetInd();
        });
        donut.addEventListener('mouseleave', resetInd);
        donut.addEventListener('touchstart', function(e) {
            const t = e.touches[0];
            const i = sliceAtPointer(t.clientX, t.clientY);
            if (i >= 0) { e.preventDefault(); focusIndex(i); }
        }, { passive: false });
        // Click on a slice -> cross-filter keywords into the text + scroll.
        donut.style.cursor = 'pointer';
        donut.addEventListener('click', function(e) {
            const i = sliceAtPointer(e.clientX, e.clientY);
            if (i >= 0) crossFilter(i);
        });

        // Legend rows: hover focuses; CLICK explodes the slice out a few px.
        function bind(el) {
            const i = parseInt(el.getAttribute('data-i'), 10);
            el.style.transition = 'opacity ' + DUR + ' ease, background ' + DUR + ' ease';
            el.addEventListener('mouseenter', function() { focusIndex(i); });
            el.addEventListener('mouseleave', resetInd);
            el.addEventListener('touchstart', function(ev) { ev.preventDefault(); explodeSlice(i); }, { passive: false });
            el.addEventListener('click', function() { explodeSlice(i); });
        }
        legs.forEach(bind);
        pcts.forEach(bind);
    });
}

// Report sections interactivity: each section (title + its following paragraphs)
// gets highlighted when the cursor hovers it or the user taps it on touch. We
// group each .rep-sec-title with the sibling <p>/content until the next title,
// wrapping them into a .report-section box that reacts on hover/tap.
function attachReportSectionInteractivity() {
    const titles = Array.prototype.slice.call(document.querySelectorAll('.rep-sec-title'));
    titles.forEach(function(title) {
        // Skip if already wrapped.
        if (title.parentElement && title.parentElement.classList.contains('report-section')) return;
        const wrap = document.createElement('div');
        wrap.className = 'report-section';
        const parent = title.parentNode;
        parent.insertBefore(wrap, title);
        // Move the title and following siblings (until next title) into the wrap.
        let node = title;
        while (node && !(node !== title && node.classList && node.classList.contains('rep-sec-title'))) {
            const next = node.nextSibling;
            wrap.appendChild(node);
            node = next;
            if (node && node.classList && node.classList.contains('rep-sec-title')) break;
        }
        // Touch: tap toggles the highlight (hover handles desktop via CSS).
        wrap.addEventListener('touchstart', function() {
            const wasActive = wrap.classList.contains('rep-active');
            document.querySelectorAll('.report-section.rep-active').forEach(function(s) { s.classList.remove('rep-active'); });
            if (!wasActive) wrap.classList.add('rep-active');
        }, { passive: true });
        wrap.addEventListener('click', function() {
            const wasActive = wrap.classList.contains('rep-active');
            document.querySelectorAll('.report-section.rep-active').forEach(function(s) { s.classList.remove('rep-active'); });
            if (!wasActive) wrap.classList.add('rep-active');
        });
    });
}

function printInforme() {
    const content = document.getElementById('informeContent');
    if (!content) return;
    const now = new Date();
    const dateStr = now.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: '2-digit' });
    const monthNames = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    const periodo = monthNames[now.getMonth() + 1] + ' ' + now.getFullYear();

    const printWindow = window.open('', '_blank');
    printWindow.document.write('<html><head><title>Informe Mi Primer Casa S.A.</title>');
    printWindow.document.write('<style>');
    printWindow.document.write('@page { size: A4; margin: 2cm 2.5cm; }');
    // CRITICAL: force browsers to print colors and backgrounds at full saturation
    // even when "Background graphics" is off. Without this the line chart, the
    // blue numbers and the SVG fills print washed-out / pale.
    printWindow.document.write('* { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; color-adjust: exact !important; }');
    printWindow.document.write('body { font-family: "Segoe UI", -apple-system, sans-serif; color: #222; line-height: 1.7; font-size: 12px; max-width: 100%; }');
    printWindow.document.write('.header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }');
    printWindow.document.write('.header h1 { font-size: 18px; font-weight: 400; color: #333; margin: 0; }');
    printWindow.document.write('.header .date { font-size: 12px; color: #888; }');
    printWindow.document.write('.subtitle { font-size: 11px; color: #666; margin-bottom: 6px; text-decoration: underline; }');
    printWindow.document.write('.auditor { font-size: 10px; color: #888; margin-bottom: 16px; text-decoration: underline; }');
    printWindow.document.write('hr { border: none; border-top: 1px solid #4a6cf7; margin: 12px 0; }');
    printWindow.document.write('table { width: 100%; border-collapse: collapse; font-size: 11px; margin: 12px 0; }');
    printWindow.document.write('th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: center; }');
    printWindow.document.write('th { background: #f5f5f5 !important; font-weight: 600; }');
    printWindow.document.write('p { text-align: justify; font-size: 12px; margin-bottom: 10px; }');
    printWindow.document.write('strong { color: #111; }');
    printWindow.document.write('.green { color: #1a7a3a; } .red { color: #c03030; } .yellow { color: #b08000; } .blue { color: #2a5af5; }');
    // Keep SVG line-chart strokes/fills vivid on paper.
    printWindow.document.write('svg { max-width: 100%; }');
    printWindow.document.write('svg text { fill: #333 !important; }');
    printWindow.document.write('</style></head><body>');
    printWindow.document.write('<div class="header"><h1>Mi Primer Casa S.A.</h1><span class="date">' + dateStr + '</span></div>');
    printWindow.document.write('<div class="auditor">Auditor: Bernardo Strauss.</div>');
    printWindow.document.write('<div class="subtitle">Informe de Auditoria de Grabacion y Transcripciones ' + periodo + '.</div>');
    printWindow.document.write('<hr>');
    // Adapt the dark-UI colors to WHITE PAPER. Goal: sheet stays white, and only
    // the meaningful content (numbers, the blue line chart, highlighted words with
    // their category colors) shows color — dark theme backgrounds become white and
    // light-grey body text becomes dark so nothing prints pale or invisible.
    let cleanHtml = content.innerHTML;

    // Step 0 (PRINT-ONLY re-skin). These specific pieces keep their dark colors
    // on screen but get print-friendly colors here. Done BEFORE the generic
    // passes so the shared hex codes (#aaa, #5bf5a3...) are already resolved.

    // 0.1 Monthly cells: dark box -> light-blue box with black text (Ene: 92 ...)
    //     The inner <strong style="color:#e0e0e0"> number becomes dark via Step C,
    //     so it prints crisp/black on the light-blue cell.
    cleanHtml = cleanHtml.split('background:#0d0f18;border:1px solid #2a2d3a;border-radius:6px;padding:3px 8px;font-size:0.68rem;color:#aaa;')
                         .join('background:#bfe3f5;border:1px solid #7fc4e6;border-radius:6px;padding:3px 8px;font-size:0.68rem;color:#0d0d0d;');

    // 0.2 "Total AAAA: N" pill: dark green -> lighter green with yellow text
    cleanHtml = cleanHtml.split('background:#1a3a2a;border:1px solid #2a5a3a;border-radius:6px;padding:3px 10px;font-size:0.68rem;color:#5bf5a3;font-weight:700;')
                         .join('background:#2e9e58;border:1px solid #248048;border-radius:6px;padding:3px 10px;font-size:0.68rem;color:#fff23d;font-weight:700;');

    // 0.3 Donut center hole: dark disc -> white disc with dark number (no black heart)
    cleanHtml = cleanHtml.split('width:60px;height:60px;border-radius:50%;background:#0f1117;display:flex;align-items:center;justify-content:center;"><span style="font-size:0.6rem;color:#aaa;')
                         .join('width:60px;height:60px;border-radius:50%;background:#ffffff;display:flex;align-items:center;justify-content:center;"><span style="font-size:0.62rem;color:#222;font-weight:700;');

    // Step A. All dark container/box backgrounds -> white sheet
    const darkBgs = ['#0a0c14', '#0d1017', '#12141c', '#151823',
                     '#0d1a0d', '#1a1a0d', '#1a0d0d'];
    darkBgs.forEach(function(c) {
        cleanHtml = cleanHtml.split('background:' + c).join('background:#ffffff');
        cleanHtml = cleanHtml.split(c).join('#ffffff');
    });

    // Step B. Dark borders / grid strokes -> light grey, visible on white
    ['#1e2130', '#232838', '#2a2d3a'].forEach(function(c) {
        cleanHtml = cleanHtml.split(c).join('#d5d8e0');
    });

    // Step C. Light-grey body text meant for dark UI -> dark so it reads on paper
    const grayText = { '#fff': '#111', '#ffffff': '#111', '#ccc': '#222',
                       '#e0e0e0': '#222', '#aaa': '#555', '#888': '#555',
                       '#777': '#666', '#666': '#666' };
    Object.keys(grayText).forEach(function(g) {
        cleanHtml = cleanHtml.split('color:' + g).join('color:' + grayText[g]);
    });

    // Step D. Semantic accents: keep them but darken the too-bright green/blue/yellow
    //         so they contrast against white, staying vivid and print-safe.
    const accentFix = { '#5bf5a3': '#1a7a3a', '#5bd4f5': '#1668a8',
                        '#7b9cff': '#3a5ad6', '#f5d75b': '#a87f00' };
    Object.keys(accentFix).forEach(function(a) {
        cleanHtml = cleanHtml.split(a).join(accentFix[a]);
    });
    // Blue #4a6cf7, red #f55b5b and violet #b38bff already contrast on white so kept.

    printWindow.document.write(cleanHtml);
    printWindow.document.write('</body></html>');
    printWindow.document.close();
    setTimeout(function() { printWindow.print(); }, 300);
}

// ── DATA-LOSS ALERT ──────────────────────────────────────────────────────
// Checks the backup status and, if a significant loss of saved texts is
// detected vs the last backup, shows a fixed banner at the top with a
// "Restaurar" button so the admin fixes it BEFORE continuing.
async function checkBackupStatus() {
    try {
        const resp = await fetch('/admin/backup-status?_t=' + Date.now(), { cache: 'no-store' });
        if (!resp.ok) return;
        const s = await resp.json();
        if (s && s.alert) {
            showBackupAlert(s);
        }
    } catch (e) { /* silent — never break the page */ }
}

function showBackupAlert(s) {
    if (document.getElementById('backupAlertBanner')) return;
    const lost = (s.last_backup_total || 0) - (s.current_total || 0);
    const banner = document.createElement('div');
    banner.id = 'backupAlertBanner';
    banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:#3a0d0d;border-bottom:2px solid #f55b5b;color:#fff;padding:12px 16px;font-size:0.85rem;display:flex;align-items:center;gap:12px;flex-wrap:wrap;box-shadow:0 4px 16px rgba(0,0,0,0.6);';
    let drops = '';
    if (s.per_user_drops && s.per_user_drops.length) {
        drops = ' — ' + s.per_user_drops.slice(0, 5).map(function(d) {
            return d.username + ' (' + d.before + '→' + d.now + ')';
        }).join(', ');
    }
    banner.innerHTML =
        '<span style="font-size:1.1rem;">&#9888;</span>' +
        '<strong style="color:#f88;">Posible perdida de textos detectada.</strong>' +
        '<span style="color:#ddd;">Actual: ' + (s.current_total||0) + ' · Ultimo backup: ' + (s.last_backup_total||0) +
        ' (faltan ~' + (lost > 0 ? lost : 0) + ')' + drops + '</span>' +
        '<button onclick="restoreBackupNow()" style="margin-left:auto;background:#2a8a4a;border:none;color:#fff;padding:8px 16px;border-radius:6px;font-weight:600;cursor:pointer;">Restaurar textos</button>' +
        '<button onclick="dismissBackupAlert()" style="background:transparent;border:1px solid #f55b5b;color:#f88;padding:8px 12px;border-radius:6px;cursor:pointer;">Ignorar</button>';
    document.body.appendChild(banner);
    document.body.style.paddingTop = '56px';
}

function dismissBackupAlert() {
    const b = document.getElementById('backupAlertBanner');
    if (b) b.remove();
    document.body.style.paddingTop = '0';
}

async function restoreBackupNow() {
    if (!confirm('Auto Fix comparara todos los backups y restaurara UNO POR UNO los textos que falten. Solo agrega, nunca borra. Continuar?')) return;
    const banner = document.getElementById('backupAlertBanner');
    if (banner) banner.innerHTML = '<span style="padding:4px;">Auto Fix en curso: comparando backups y restaurando textos faltantes...</span>';
    try {
        // Auto Fix: entry-by-entry reconciliation across ALL backups (most precise)
        const resp = await fetch('/admin/auto-fix', { method: 'POST' });
        const r = await resp.json();
        if (r.ok) {
            if (r.restored > 0) {
                if (banner) banner.innerHTML = '<span style="color:#5bf5a3;padding:4px;">&#10003; Auto Fix: restaurados ' + r.restored + ' de ' + r.missing_count + ' textos faltantes. Recargando...</span>';
                setTimeout(function() { location.reload(); }, 1800);
            } else {
                if (banner) banner.innerHTML = '<span style="color:#5bf5a3;padding:4px;">&#10003; Auto Fix: no faltaba ningun texto recuperable. Todo en orden.</span>';
                setTimeout(function() { const b = document.getElementById('backupAlertBanner'); if (b) b.remove(); document.body.style.paddingTop = '0'; }, 2500);
            }
        } else {
            if (banner) banner.innerHTML = '<span style="color:#f88;padding:4px;">Error en Auto Fix: ' + (r.reason || 'desconocido') + '</span>';
        }
    } catch (e) {
        if (banner) banner.innerHTML = '<span style="color:#f88;padding:4px;">Error de conexion al restaurar.</span>';
    }
}

// Manual Auto Fix trigger (can be called from console or a button): previews first
async function runAutoFix() {
    try {
        const prev = await (await fetch('/admin/auto-fix?dry_run=1')).json();
        if (!prev.ok) { alert('Auto Fix no disponible: ' + (prev.reason || '')); return; }
        if (prev.missing_count === 0) { alert('Auto Fix: no faltan textos. Todo en orden (' + prev.live_count + ' textos).'); return; }
        if (!confirm('Auto Fix detecto ' + prev.missing_count + ' textos faltantes. Restaurarlos ahora?')) return;
        const r = await (await fetch('/admin/auto-fix', { method: 'POST' })).json();
        alert('Auto Fix: restaurados ' + r.restored + ' textos. La pagina se recargara.');
        location.reload();
    } catch (e) { alert('Error en Auto Fix: ' + e.message); }
}

// Load informe on page load if admin
if (document.getElementById('informePanel')) {
    loadInforme();
}

// ── Sales Simulator ──────────────────────────────────────────────────────
let simOpen = false;
let simActive = false;
let simDifficulty = '';
let simMessages = [];

function toggleSimulator() {
    simOpen = !simOpen;
    document.getElementById('simulatorPanel').style.display = simOpen ? 'block' : 'none';
    document.getElementById('simToggleIcon').textContent = simOpen ? '\u25B2 Cerrar simulador' : '\u25BC Abrir simulador';
}

function selectDifficulty(level) {
    simDifficulty = level;
    document.querySelectorAll('.sim-diff-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-level="${level}"]`).classList.add('active');
    document.getElementById('simStartBtn').disabled = false;
}

async function startSimulation() {
    if (!simDifficulty) return;
    simActive = true;
    simMessages = [];
    document.getElementById('simSetup').style.display = 'none';
    document.getElementById('simChat').style.display = 'block';
    document.getElementById('simFeedback').style.display = 'none';
    addSimMessage('system', 'Simulaci\u00f3n iniciada. Nivel: ' + simDifficulty.replace('_', ' ') + '. Eres el vendedor, el cliente IA te responder\u00e1.');
    // Get initial client greeting
    await sendToSimulator('[INICIO]');
}

function addSimMessage(role, text) {
    simMessages.push({role, text});
    const container = document.getElementById('simMessages');
    const div = document.createElement('div');
    div.className = 'sim-msg sim-msg-' + (role === 'client' ? 'client' : role === 'vendor' ? 'vendor' : 'system');
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

async function sendSimMessage() {
    const input = document.getElementById('simInput');
    const text = input.value.trim();
    if (!text || !simActive) return;
    input.value = '';
    addSimMessage('vendor', text);
    await sendToSimulator(text);
}

async function sendToSimulator(message) {
    const container = document.getElementById('simMessages');
    const typing = document.createElement('div');
    typing.className = 'sim-typing';
    typing.textContent = 'Cliente escribiendo...';
    typing.id = 'simTyping';
    container.appendChild(typing);
    container.scrollTop = container.scrollHeight;

    try {
        const resp = await fetch('/api/simulator/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message, difficulty: simDifficulty, history: simMessages})
        });
        const data = await resp.json();
        const typingEl = document.getElementById('simTyping');
        if (typingEl) typingEl.remove();
        if (data.response) {
            addSimMessage('client', data.response);
        }
        if (data.ended) {
            endSimulation();
        }
    } catch(e) {
        const typingEl = document.getElementById('simTyping');
        if (typingEl) typingEl.remove();
        addSimMessage('system', 'Error de conexi\u00f3n. Intenta de nuevo.');
    }
}

function endSimulation() {
    simActive = false;
    addSimMessage('system', '\u2014 Simulaci\u00f3n finalizada \u2014');
    document.getElementById('simFeedback').style.display = 'block';
}

async function submitFeedback() {
    const text = document.getElementById('simFeedbackText').value.trim();
    try {
        await fetch('/api/simulator/feedback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({feedback: text, difficulty: simDifficulty, messages_count: simMessages.length})
        });
    } catch(e) {}
    document.getElementById('simFeedbackText').value = '';
    document.getElementById('simFeedback').style.display = 'none';
    addSimMessage('system', '\u00a1Gracias por tu feedback!');
    // Reset for new session
    setTimeout(() => {
        document.getElementById('simChat').style.display = 'none';
        document.getElementById('simSetup').style.display = 'block';
        document.getElementById('simMessages').innerHTML = '';
        simMessages = [];
        simDifficulty = '';
        document.querySelectorAll('.sim-diff-btn').forEach(b => b.classList.remove('active'));
        document.getElementById('simStartBtn').disabled = true;
    }, 2000);
}

// Keep loadHistory as no-op for backward compatibility
function loadHistory() {}
function toggleHistory() { toggleSimulator(); }
</script>
</body>
</html>
"""


LOGIN_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analizador de Textos - Acceso</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f1117;
            color: #e0e0e0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .auth-container {
            width: 100%;
            max-width: 420px;
        }

        .auth-header {
            text-align: center;
            margin-bottom: 32px;
        }

        .auth-header h1 {
            font-size: 1.6rem;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 6px;
        }

        .auth-header p {
            color: #666;
            font-size: 0.9rem;
        }

        /* Entrance animations: reveal top-to-bottom, fluidly. */
        @keyframes authDropIn {
            from { opacity: 0; transform: translateY(-18px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes fieldSlideIn {
            from { opacity: 0; transform: translateX(-14px); }
            to   { opacity: 1; transform: translateX(0); }
        }
        .auth-card {
            background: #1a1d27;
            border: 1px solid #2a2d3a;
            border-radius: 12px;
            padding: 28px;
            animation: authDropIn 6400ms cubic-bezier(0.22, 0.61, 0.36, 1) both;
        }
        /* All fields fade in with the SAME uniform duration (no stagger). */
        .form-group {
            animation: fieldSlideIn 6400ms cubic-bezier(0.22, 0.61, 0.36, 1) both;
        }
        /* Phones: shorten login entrance to x1.5 (2400ms) to match the app. */
        @media (max-width: 480px) {
            .auth-card { animation-duration: 2400ms; }
            .form-group { animation-duration: 2400ms; }
            .text-swap-exit { animation-duration: 900ms; }
            .text-swap-enter { animation-duration: 1050ms; }
            .stream-word { animation-duration: 900ms; }
        }
        @media (prefers-reduced-motion: reduce) {
            .auth-card, .form-group { animation: none !important; opacity: 1 !important; transform: none !important; }
        }

        .tabs {
            display: flex;
            gap: 4px;
            background: #0f1117;
            border-radius: 8px;
            padding: 4px;
            margin-bottom: 24px;
        }

        .tab-btn {
            flex: 1;
            padding: 8px;
            border: none;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 600;
            cursor: pointer;
            background: transparent;
            color: #666;
            transition: all 0.2s;
        }

        .tab-btn.active {
            background: #4a6cf7;
            color: white;
        }

        .form-group {
            margin-bottom: 16px;
        }

        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        label {
            display: block;
            font-size: 0.78rem;
            font-weight: 600;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            margin-bottom: 6px;
        }

        input[type="text"],
        input[type="password"],
        input[type="email"] {
            width: 100%;
            background: #0f1117;
            border: 1px solid #2a2d3a;
            border-radius: 7px;
            color: #e0e0e0;
            font-size: 0.9rem;
            padding: 10px 12px;
            outline: none;
            font-family: inherit;
            transition: border-color 0.2s;
        }

        input:focus { border-color: #4a6cf7; }

        .remember-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 20px;
        }

        .remember-row input[type="checkbox"] {
            width: 16px;
            height: 16px;
            accent-color: #4a6cf7;
            cursor: pointer;
        }

        .remember-row label {
            font-size: 0.82rem;
            color: #888;
            text-transform: none;
            letter-spacing: 0;
            margin-bottom: 0;
            cursor: pointer;
        }

        .btn-submit {
            width: 100%;
            padding: 12px;
            background: #4a6cf7;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }

        .btn-submit:hover { opacity: 0.85; }

        .error-msg {
            background: #2a1a1a;
            border: 1px solid #5a2a2a;
            border-radius: 8px;
            padding: 10px 14px;
            color: #f55b5b;
            font-size: 0.85rem;
            margin-bottom: 16px;
        }

        .success-msg {
            background: #1a2a1a;
            border: 1px solid #2a5a2a;
            border-radius: 8px;
            padding: 10px 14px;
            color: #5bf5a3;
            font-size: 0.85rem;
            margin-bottom: 16px;
        }

        .section-divider {
            font-size: 0.7rem;
            text-transform: uppercase;
            color: #444;
            letter-spacing: 0.08em;
            margin: 16px 0 12px;
            border-top: 1px solid #2a2d3a;
            padding-top: 16px;
        }

        .tab-panel { display: none; }
        .tab-panel.active { display: block; }
    </style>
</head>
<body>
<div class="auth-container">
    <div class="auth-header">
        <h1>Analizador de Textos</h1>
        <p>Ventas y Bienes Raices &mdash; Analisis con Machine Learning</p>
    </div>

    <div class="auth-card">
        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('login')">Iniciar Sesion</button>
            <button class="tab-btn" onclick="switchTab('register')">Registrarse</button>
        </div>

        {% if error %}
        <div class="error-msg">{{ error }}</div>
        {% endif %}
        {% if success %}
        <div class="success-msg">{{ success }}</div>
        {% endif %}

        <!-- LOGIN PANEL -->
        <div class="tab-panel active" id="panel-login">
            <form method="POST" action="/login" id="login-form">
                <input type="hidden" name="action" value="login">
                <div class="form-group">
                    <label for="login-user">Usuario</label>
                    <input type="text" id="login-user" name="username"
                           autocomplete="username"
                           value="{{ saved_username }}"
                           placeholder="Tu nombre de usuario" required>
                </div>
                <div class="form-group">
                    <label for="login-pass">Contrasena</label>
                    <input type="password" id="login-pass" name="password"
                           autocomplete="current-password"
                           placeholder="Tu contrasena" required>
                </div>
                <div class="remember-row">
                    <input type="checkbox" id="remember" name="remember" value="1"
                           {% if saved_username %}checked{% endif %}>
                    <label for="remember">Recordar usuario y contrasena</label>
                </div>
                <button type="submit" class="btn-submit">Ingresar</button>
            </form>
        </div>

        <!-- REGISTER PANEL -->
        <div class="tab-panel" id="panel-register">
            <form method="POST" action="/login" id="register-form">
                <input type="hidden" name="action" value="register">

                <div class="section-divider">Datos de acceso</div>
                <div class="form-group">
                    <label for="reg-user">Usuario <span style="color:#f55b5b">*</span></label>
                    <input type="text" id="reg-user" name="username"
                           autocomplete="username"
                           placeholder="Min. 8 caracteres, una mayuscula">
                    <div style="font-size:0.72rem; color:#555; margin-top:4px;">Letras, numeros, puntos y guiones. Al menos una mayuscula.</div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label for="reg-pass">Contrasena <span style="color:#f55b5b">*</span></label>
                        <input type="password" id="reg-pass" name="password"
                               autocomplete="new-password"
                               placeholder="Min. 8 caracteres, una mayuscula">
                    </div>
                    <div class="form-group">
                        <label for="reg-pass2">Confirmar <span style="color:#f55b5b">*</span></label>
                        <input type="password" id="reg-pass2" name="password2"
                               autocomplete="new-password"
                               placeholder="Repetir contrasena">
                    </div>
                </div>

                <div class="section-divider">Datos personales</div>
                <div class="form-row">
                    <div class="form-group">
                        <label for="reg-nombre">Nombre <span style="color:#f55b5b">*</span></label>
                        <input type="text" id="reg-nombre" name="nombre" placeholder="Primer nombre">
                    </div>
                    <div class="form-group">
                        <label for="reg-nombre2">Segundo nombre</label>
                        <input type="text" id="reg-nombre2" name="segundo_nombre" placeholder="Opcional">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label for="reg-nombre3">Tercer nombre</label>
                        <input type="text" id="reg-nombre3" name="tercer_nombre" placeholder="Opcional">
                    </div>
                    <div class="form-group">
                        <label for="reg-apellido">Apellido <span style="color:#f55b5b">*</span></label>
                        <input type="text" id="reg-apellido" name="apellido" placeholder="Primer apellido">
                    </div>
                </div>
                <div class="form-group">
                    <label for="reg-apellido2">Segundo apellido</label>
                    <input type="text" id="reg-apellido2" name="segundo_apellido" placeholder="Opcional">
                </div>

                <div class="section-divider">Datos de contacto</div>
                <div class="form-row">
                    <div class="form-group">
                        <label for="reg-cel">Celular <span style="color:#f55b5b">*</span></label>
                        <input type="text" id="reg-cel" name="celular" placeholder="Numero de celular">
                    </div>
                    <div class="form-group">
                        <label for="reg-email">Correo <span style="color:#f55b5b">*</span></label>
                        <input type="email" id="reg-email" name="email" placeholder="correo@ejemplo.com">
                    </div>
                </div>
                <div class="form-group">
                    <label for="reg-dir">Direccion <span style="color:#f55b5b">*</span></label>
                    <input type="text" id="reg-dir" name="direccion" placeholder="Direccion completa">
                </div>

                <div class="section-divider">Datos profesionales (opcional)</div>
                <div class="form-row">
                    <div class="form-group">
                        <label for="reg-empresa">Empresa</label>
                        <input type="text" id="reg-empresa" name="empresa" placeholder="Nombre empresa">
                    </div>
                    <div class="form-group">
                        <label for="reg-cargo">Cargo</label>
                        <input type="text" id="reg-cargo" name="cargo" placeholder="Tu cargo">
                    </div>
                </div>

                <div style="font-size:0.72rem; color:#555; margin-bottom:12px;">
                    <span style="color:#f55b5b">*</span> Campos obligatorios
                </div>

                <button type="submit" class="btn-submit">Crear Cuenta</button>
            </form>
        </div>
    </div>
</div>

<script>
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach((b, i) => {
        b.classList.toggle('active', (i === 0 && tab === 'login') || (i === 1 && tab === 'register'));
    });
    document.getElementById('panel-login').classList.toggle('active', tab === 'login');
    document.getElementById('panel-register').classList.toggle('active', tab === 'register');
}

// If arriving after a register error, show register tab
{% if active_tab == 'register' %}
switchTab('register');
{% endif %}

// Autoguardado: save username to localStorage on login submit
document.getElementById('login-form').addEventListener('submit', function() {
    const remember = document.getElementById('remember').checked;
    const username = document.getElementById('login-user').value;
    if (remember) {
        localStorage.setItem('saved_username', username);
    } else {
        localStorage.removeItem('saved_username');
    }
});

// On load: prefill from localStorage if not already prefilled from server
window.addEventListener('DOMContentLoaded', function() {
    const loginInput = document.getElementById('login-user');
    if (!loginInput.value) {
        const saved = localStorage.getItem('saved_username');
        if (saved) {
            loginInput.value = saved;
            document.getElementById('remember').checked = true;
        }
    }
});

// ── UI SOUND ENGINE (login page) — synthesized, no external assets ──
var UISound = (function() {
    var ctx = null, master = null, verb = null, muted = false;
    try { muted = localStorage.getItem('uiSoundMuted') === '1'; } catch (e) {}
    function ac() {
        if (ctx) return ctx;
        try {
            var AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return null;
            ctx = new AC();
            master = ctx.createGain(); master.gain.value = 0.85; master.connect(ctx.destination);
            verb = ctx.createConvolver();
            var len = Math.floor(ctx.sampleRate * 1.1);
            var b = ctx.createBuffer(2, len, ctx.sampleRate);
            for (var ch = 0; ch < 2; ch++) {
                var d = b.getChannelData(ch);
                for (var i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.2);
            }
            verb.buffer = b;
            var vlp = ctx.createBiquadFilter(); vlp.type = 'lowpass'; vlp.frequency.value = 3200;
            var vg = ctx.createGain(); vg.gain.value = 0.55; verb.connect(vlp); vlp.connect(vg); vg.connect(master);
        } catch (e) { ctx = null; }
        return ctx;
    }
    var PARTIALS = [{ r: 1.0, a: 1.0 }, { r: 2.76, a: 0.42 }, { r: 5.40, a: 0.16 }];
    function tone(f0, f1, dur, peak, verbAmt) {
        if (muted) return;
        var c = ac(); if (!c || !master) return;
        try {
            if (c.state === 'suspended') c.resume();
            var now = c.currentTime;
            var out = c.createGain(); out.gain.value = 1; out.connect(master);
            if (verb && verbAmt > 0) { var send = c.createGain(); send.gain.value = verbAmt; out.connect(send); send.connect(verb); }
            var lfo = c.createOscillator(), lfoGain = c.createGain();
            lfo.frequency.value = 5.5; lfoGain.gain.value = f0 * 0.006; lfo.connect(lfoGain);
            lfo.start(now); lfo.stop(now + dur + 0.1);
            PARTIALS.forEach(function(p, idx) {
                var osc = c.createOscillator(), g = c.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(f0 * p.r, now);
                if (f1 && f1 !== f0) osc.frequency.exponentialRampToValueAtTime(Math.max(1, f1 * p.r), now + dur);
                lfoGain.connect(osc.frequency);
                var pd = dur * (1 - idx * 0.22), pk = peak * p.a;
                g.gain.setValueAtTime(0.0001, now);
                g.gain.exponentialRampToValueAtTime(pk, now + 0.008);
                g.gain.exponentialRampToValueAtTime(0.0001, now + Math.max(0.05, pd));
                osc.connect(g); g.connect(out);
                osc.start(now); osc.stop(now + dur + 0.08);
            });
        } catch (e) {}
    }
    return {
        tick: function() { tone(1660, 1660, 0.09, 0.03, 0.4); },
        click: function() { tone(1046, 1046, 0.5, 0.06, 0.85); },
        cancel: function() { tone(560, 420, 0.5, 0.05, 0.9); },
        startup: function() { tone(660, 660, 0.9, 0.045, 1.0); setTimeout(function() { tone(990, 990, 1.1, 0.04, 1.0); }, 130); },
        unlock: function() { var c = ac(); if (c && c.state === 'suspended') { try { c.resume(); } catch (e) {} } }
    };
})();
window.addEventListener('DOMContentLoaded', function() {
    function unlockOnce() {
        UISound.unlock();
        setTimeout(function() { UISound.startup(); }, 40);
        document.removeEventListener('pointerdown', unlockOnce);
        document.removeEventListener('keydown', unlockOnce);
    }
    document.addEventListener('pointerdown', unlockOnce);
    document.addEventListener('keydown', unlockOnce);
    var _lastHoverEl = null;
    document.addEventListener('mouseover', function(e) {
        var t = e.target;
        if (!t || !t.closest) return;
        var el = t.closest('button, input, .tab-btn, a, label, .form-group');
        if (el && el !== _lastHoverEl) { _lastHoverEl = el; UISound.tick(); }
    });
    document.addEventListener('mouseout', function(e) {
        if (e.target === _lastHoverEl) _lastHoverEl = null;
    });
    document.addEventListener('click', function(e) {
        var t = e.target;
        if (t && t.closest && t.closest('button, .tab-btn, a')) UISound.click();
    });
});
</script>
</body>
</html>
"""


@app.route("/login", methods=["GET", "POST"])
def login_page():
    # Already logged in
    if session.get("username"):
        return redirect(url_for("index"))

    error = None
    success = None
    active_tab = "login"
    saved_username = ""

    if request.method == "POST":
        action = request.form.get("action", "login")

        if action == "login":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            result = user_manager.login(username, password)
            if result["ok"]:
                session["username"] = username
                return redirect(url_for("index"))
            else:
                error = result["error"]
                saved_username = username

        elif action == "register":
            active_tab = "register"
            username       = request.form.get("username", "").strip()
            password       = request.form.get("password", "")
            password2      = request.form.get("password2", "")
            nombre         = request.form.get("nombre", "").strip()
            segundo_nombre = request.form.get("segundo_nombre", "").strip()
            tercer_nombre  = request.form.get("tercer_nombre", "").strip()
            apellido       = request.form.get("apellido", "").strip()
            segundo_apellido = request.form.get("segundo_apellido", "").strip()
            celular        = request.form.get("celular", "").strip()
            email          = request.form.get("email", "").strip()
            direccion      = request.form.get("direccion", "").strip()
            empresa        = request.form.get("empresa", "").strip()
            cargo          = request.form.get("cargo", "").strip()

            if password != password2:
                error = "Las contrasenas no coinciden."
            else:
                result = user_manager.register(
                    username=username, password=password,
                    nombre=nombre, segundo_nombre=segundo_nombre,
                    tercer_nombre=tercer_nombre,
                    apellido=apellido, segundo_apellido=segundo_apellido,
                    celular=celular, email=email, direccion=direccion,
                    empresa=empresa, cargo=cargo
                )
                if result["ok"]:
                    success = f"Cuenta creada exitosamente. Ya puedes iniciar sesion, {nombre}."
                    active_tab = "login"
                else:
                    error = result["error"]

    return render_template_string(
        LOGIN_HTML,
        error=error,
        success=success,
        active_tab=active_tab,
        saved_username=saved_username
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/")
def index():
    if not session.get("username"):
        return redirect(url_for("login_page"))
    html = render_template_string(HTML, username=session["username"], indicador_categorias_json=_INDICADOR_CATEGORIAS_JSON, all_users=[u for u in user_manager.list_users() if u not in ('admin', 'Vanesa_Admin', 'FedericoCeballos', 'MartinianoSosa', 'GarciaTania', 'Berna.Strauss')])
    # Prevent the browser from serving a stale cached page after each deploy.
    resp = app.make_response(html)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/analyze", methods=["POST"])
def analyze():
    if not session.get("username"):
        return jsonify({"error": True, "error_code": "UNAUTHORIZED",
                        "error_message": "Sesion no iniciada"}), 401

    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": True, "error_code": "BAD_REQUEST",
                        "error_message": "No text provided"}), 400

    # Filter out consecutive repeated words/phrases from transcription artifacts
    clean_text = _dedup_transcription(data["text"])

    # The old in-memory dedup cache (_last_save_cache) doesn't work with gunicorn
    # multi-worker mode (each worker has a separate process/memory space).
    # The real guard against duplicates is: entry_name is REQUIRED to save
    # (enforced below), and ON CONFLICT DO NOTHING in PostgreSQL.
    # So _should_save is simply True here — the DB handles idempotency.
    _should_save = True

    result = analyzer.analyze(clean_text)

    if isinstance(result, AnalysisError):
        print(f"[ANALYSIS_ERROR] code={result.error_code} msg={result.error_message}")
        return jsonify({
            "error": True,
            "error_code": result.error_code,
            "error_message": result.error_message
        })

    # Run commercial analysis in parallel
    ca = commercial_analyzer.analyze(clean_text)

    analysis_dict = {
        "intent": result.intent,
        "intent_confidence": result.intent_confidence,
        "sentiment": result.sentiment,
        "sentiment_confidence": result.sentiment_confidence,
        "sales_concepts": [
            {"concept": c.concept, "confidence": c.confidence, "source_text": c.source_text}
            for c in result.sales_concepts
        ],
        "real_estate_concepts": [
            {"concept": c.concept, "confidence": c.confidence, "source_text": c.source_text}
            for c in result.real_estate_concepts
        ],
        "entities": [
            {"concept": e.concept, "raw_value": e.raw_value,
             "numeric_value": e.numeric_value, "unit": e.unit}
            for e in result.entities
        ],
        "commercial": _build_commercial_dict(ca)
    }

    # Save to history
    year = data.get("year")
    month = data.get("month")
    entry_name = data.get("entry_name", "").strip()
    fecha_str = data.get("fecha", "").strip()  # YYYY-MM-DD from date input
    existing_entry_id = data.get("existing_entry_id", "").strip()  # ID of entry being updated
    # Admin can save to another user's account
    target_user = data.get("target_user", "").strip() or session["username"]
    if target_user != session["username"] and not _is_admin():
        target_user = session["username"]  # Non-admins can only save to themselves

    # If fecha is provided, override year/month/day from it
    day = None
    if fecha_str and len(fecha_str) == 10:
        try:
            from datetime import datetime as _dt_parse
            parsed_fecha = _dt_parse.strptime(fecha_str, "%Y-%m-%d")
            year = parsed_fecha.year
            month = parsed_fecha.month
            day = parsed_fecha.day
        except Exception:
            pass

    # Only save if entry_name is provided (mandatory) AND user is admin
    if entry_name and _should_save and _is_admin():
        # Save the NEW entry FIRST. Only after it is safely stored do we delete
        # the old one. This prevents data loss if the save fails mid-way
        # (previously it deleted first, so a failed add left NOTHING).
        add_entry(
            username=target_user,
            text=clean_text,
            analysis=analysis_dict,
            source="text",
            audio_filename=entry_name,
            year=year,
            month=month,
            day=day,
            entry_name=entry_name,
        )
        # New entry stored OK — now remove the old version being replaced.
        if existing_entry_id:
            from src.users.history_manager import delete_entry
            delete_entry(target_user, existing_entry_id)

    return jsonify({
        "error": False,
        "input_text": clean_text,
        "analyzed_at": result.analyzed_at,
        "year": year,
        "month": month,
        **analysis_dict,
    })


@app.route("/saved-texts")
def saved_texts():
    """Return entries filtered by year/month/fecha for the saved texts panel."""
    if not session.get("username"):
        return jsonify({"entries": []}), 401

    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    fecha = request.args.get("fecha", "").strip()  # format: YYYY-MM-DD

    username = session["username"]

    from src.users.history_manager import get_all_entries, resolve_entry_date
    entries = get_all_entries(username)

    result = []
    for e in entries:
        e_year, e_month, _ = resolve_entry_date(e)
        year_ok = (not year) or (e_year == year) or (e_year is None)
        month_ok = (not month) or (e_month == month) or (e_month is None)
        if year_ok and month_ok:
            result.append({
                "id": e.get("id", ""),
                "entry_name": e.get("entry_name", "") or e.get("audio_filename", ""),
                "text": (e.get("text", "") or "")[:60],
                "intent": e.get("intent", ""),
                "timestamp": (str(e.get("timestamp", "")) or "")[:10],
                "source": e.get("source", ""),
            })

    return jsonify({"entries": result})


@app.route("/delete-last-entry", methods=["POST"])
def delete_last_entry():
    """Delete the most recent entry from the user's history."""
    if not session.get("username"):
        return jsonify({"success": False, "message": "No autorizado"}), 401

    try:
        from src.users.history_manager import delete_entry
        entries = get_flat_entries(session["username"], limit=1)
        if entries:
            entry_id = entries[0].get("id")
            if entry_id:
                delete_entry(session["username"], entry_id)
                return jsonify({"success": True})
        return jsonify({"success": False, "message": "No hay entradas para eliminar"})
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)})


@app.route("/saved-text/<entry_id>")
def saved_text(entry_id):
    """Return the full text of a saved entry."""
    if not session.get("username"):
        return jsonify({"error": "unauthorized"}), 401

    from src.users.history_manager import get_entry_by_id

    # First try the logged-in user
    entry = get_entry_by_id(session["username"], entry_id)

    # If admin and not found, search across all users
    if not entry and _is_admin():
        for u in user_manager.list_users():
            entry = get_entry_by_id(u, entry_id)
            if entry:
                break

    if entry:
        name = entry.get("entry_name", "") or entry.get("audio_filename", "")
        return jsonify({"text": entry.get("text_full", entry.get("text", "")), "entry_name": name})

    return jsonify({"text": ""}), 404


@app.route("/delete-entry/<entry_id>", methods=["DELETE"])
def delete_entry_route(entry_id):
    """Delete a saved entry by ID."""
    if not session.get("username"):
        return jsonify({"error": "unauthorized"}), 401

    from src.users.history_manager import delete_entry

    # Try deleting from logged-in user first
    success = delete_entry(session["username"], entry_id)

    # If admin and not found, search across all users
    if not success and _is_admin():
        for u in user_manager.list_users():
            if u == session["username"]:
                continue
            success = delete_entry(u, entry_id)
            if success:
                break

    if success:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Entry not found"}), 404


@app.route("/update-entry-date/<entry_id>", methods=["PUT"])
def update_entry_date(entry_id):
    """Update the timestamp of an existing entry (move it to another date)."""
    if not session.get("username"):
        return jsonify({"error": "unauthorized"}), 401
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403

    data = request.get_json()
    new_date = data.get("date", "").strip() if data else ""
    if not new_date or len(new_date) != 10:
        return jsonify({"success": False, "error": "Fecha invalida"}), 400

    try:
        from datetime import datetime as _dt, timezone as _tz
        # Parse date: YYYY-MM-DD
        parsed = _dt.strptime(new_date, "%Y-%m-%d").replace(tzinfo=_tz.utc)

        # Update in PostgreSQL directly
        import psycopg2
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            return jsonify({"success": False, "error": "No database configured"})
        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://"):]

        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE analysis_history SET timestamp = %s WHERE id = %s",
                (parsed, entry_id)
            )
            conn.commit()
            updated = cur.rowcount > 0
        conn.close()

        if updated:
            return jsonify({"success": True, "new_date": new_date})
        return jsonify({"success": False, "error": "Entry not found"}), 404
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/upload-audio", methods=["POST"])
def upload_audio():
    """
    Receive an audio file, transcribe it with Whisper,
    run the full analysis pipeline, save to history and return results.
    """
    if not session.get("username"):
        return jsonify({"error": True, "error_code": "UNAUTHORIZED",
                        "error_message": "Sesion no iniciada"}), 401

    if "audio" not in request.files:
        return jsonify({"error": True, "error_code": "NO_FILE",
                        "error_message": "No se recibio ningun archivo de audio"}), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        return jsonify({"error": True, "error_code": "NO_FILE",
                        "error_message": "Nombre de archivo vacio"}), 400

    # Read bytes and get extension
    audio_bytes = audio_file.read()
    original_name = audio_file.filename
    ext = os.path.splitext(original_name)[1].lower() or ".wav"

    # Transcribe
    transcription = audio_transcriber.transcribe_bytes(audio_bytes, suffix=ext)
    if not transcription["ok"]:
        return jsonify({
            "error": True,
            "error_code": "TRANSCRIPTION_ERROR",
            "error_message": transcription["error"]
        }), 500

    transcribed_text = transcription["text"]
    detected_language = transcription.get("language", "unknown")

    if not transcribed_text.strip():
        return jsonify({
            "error": True,
            "error_code": "EMPTY_TRANSCRIPTION",
            "error_message": "No se pudo extraer texto del audio. Verifica que el audio tenga voz clara."
        }), 422

    # Run analysis pipeline
    result = analyzer.analyze(transcribed_text)

    if isinstance(result, AnalysisError):
        return jsonify({
            "error": True,
            "error_code": result.error_code,
            "error_message": result.error_message
        })

    ca = commercial_analyzer.analyze(transcribed_text)

    analysis_dict = {
        "intent": result.intent,
        "intent_confidence": result.intent_confidence,
        "sentiment": result.sentiment,
        "sentiment_confidence": result.sentiment_confidence,
        "sales_concepts": [
            {"concept": c.concept, "confidence": c.confidence, "source_text": c.source_text}
            for c in result.sales_concepts
        ],
        "real_estate_concepts": [
            {"concept": c.concept, "confidence": c.confidence, "source_text": c.source_text}
            for c in result.real_estate_concepts
        ],
        "entities": [
            {"concept": e.concept, "raw_value": e.raw_value,
             "numeric_value": e.numeric_value, "unit": e.unit}
            for e in result.entities
        ],
        "commercial": _build_commercial_dict(ca)
    }

    # Save to history
    add_entry(
        username=session["username"],
        text=transcribed_text,
        analysis=analysis_dict,
        source="audio",
        audio_filename=original_name,
    )

    return jsonify({
        "error": False,
        "transcription": transcribed_text,
        "language": detected_language,
        "audio_filename": original_name,
        "analyzed_at": result.analyzed_at,
        **analysis_dict,
    })


@app.route("/history")
def history():
    """Return the full history tree for the logged-in user."""
    if not session.get("username"):
        return jsonify({"error": True, "error_code": "UNAUTHORIZED"}), 401
    return jsonify(get_history(session["username"]))


@app.route("/history/flat")
def history_flat():
    """Return the most recent 100 entries as a flat list."""
    if not session.get("username"):
        return jsonify({"error": True, "error_code": "UNAUTHORIZED"}), 401
    limit = int(request.args.get("limit", 100))
    return jsonify(get_flat_entries(session["username"], limit=limit))


@app.route("/status")
def status():
    """Health check — returns component availability."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    users_dir = os.path.join(base_dir, "usuarios")
    cath_path = os.path.join(users_dir, "ContrerasCath", "history.json")
    return jsonify({
        "ok": True,
        "whisper_available": audio_transcriber.is_available,
        "whisper_model": audio_transcriber.model_name,
        "analyzer_loaded": analyzer is not None,
        "sync_configured": _mpc_configured,
        "base_dir": base_dir,
        "users_dir_exists": os.path.exists(users_dir),
        "cath_history_exists": os.path.exists(cath_path),
        "usuarios_contents": os.listdir(users_dir) if os.path.exists(users_dir) else [],
    })


# ── Sales Simulator Endpoints ──────────────────────────────────────────────

@app.route("/api/simulator/chat", methods=["POST"])
def simulator_chat():
    """Handle chat messages for the AI sales simulator."""
    if not session.get("username"):
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json()
    message = data.get("message", "")
    difficulty = data.get("difficulty", "mediano")
    history = data.get("history", [])

    # Build system prompt based on difficulty
    difficulty_prompts = {
        "facil": "Eres un cliente interesado en comprar un lote/terreno. Eres receptivo, haces pocas objeciones (max 2) y avanzas rapido al cierre. Responde de forma breve y natural.",
        "mediano": "Eres un cliente evaluando comprar un lote/terreno. Haces objeciones moderadas sobre precio y caracteristicas (3-5 objeciones). Necesitas que te convenzan con una buena propuesta de valor. Responde de forma breve.",
        "dificil": "Eres un cliente esceptico evaluando un lote/terreno. Eres sensible al precio, comparas con la competencia, y pides datos especificos (5-8 objeciones). Responde de forma breve y directa.",
        "muy_dificil": "Eres un cliente muy exigente evaluando un lote/terreno. Negocias agresivamente, pides descuentos, cuestionas el ROI, y rechazas al menos 2 propuestas (8-12 objeciones). Responde breve y cortante.",
        "veterano": "Eres un comprador experto de bienes raices evaluando un lote. Usas objeciones complejas, citas normativas, haces preguntas tecnicas detalladas, y rechazas al menos 3 propuestas (10-15 objeciones). Responde breve, incisivo y desafiante."
    }

    system_prompt = difficulty_prompts.get(difficulty, difficulty_prompts["mediano"])
    system_prompt += "\n\nREGLAS:\n- Responde SIEMPRE en espanol.\n- Maximo 60 palabras por respuesta.\n- Nunca rompas el personaje.\n- Si el vendedor logra convencerte genuinamente, acepta la compra.\n- Si detectas que el vendedor no maneja objeciones, muestra mas resistencia."

    # Build messages for OpenAI
    openai_messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        if msg.get("role") == "vendor":
            openai_messages.append({"role": "user", "content": msg["text"]})
        elif msg.get("role") == "client":
            openai_messages.append({"role": "assistant", "content": msg["text"]})

    if message and message != "[INICIO]":
        openai_messages.append({"role": "user", "content": message})
    elif message == "[INICIO]":
        openai_messages.append({"role": "user", "content": "Hola, buenas tardes."})

    try:
        import openai
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=openai_messages,
            max_tokens=150,
            temperature=0.8,
        )
        reply = response.choices[0].message.content.strip()
        return jsonify({"response": reply, "ended": False})
    except Exception as exc:
        app.logger.error(f"Simulator error: {exc}")
        return jsonify({"response": "Lo siento, no pude generar una respuesta. Verifica que OPENAI_API_KEY este configurada.", "ended": False})


@app.route("/api/simulator/feedback", methods=["POST"])
def simulator_feedback():
    """Store simulator session feedback."""
    if not session.get("username"):
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json()
    feedback = data.get("feedback", "")
    difficulty = data.get("difficulty", "")
    app.logger.info(f"Simulator feedback from {session['username']}: difficulty={difficulty}, feedback={feedback[:100]}")
    return jsonify({"success": True})


@app.route("/debug/entries/<username>")
def debug_entries(username):
    """Temporary debug endpoint to check what entries exist for a user."""
    import traceback
    errors = []

    # Check PG connection
    pg_ok = False
    pg_entries = []
    try:
        from src.users.history_manager import _is_pg_available, _get_pg_conn
        pg_ok = _is_pg_available()
        if pg_ok:
            conn = _get_pg_conn()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(*) FROM analysis_history WHERE username = %s", (username,))
                        total_count = cur.fetchone()[0]
                        cur.execute("SELECT id, timestamp, audio_filename FROM analysis_history WHERE username = %s ORDER BY timestamp DESC LIMIT 5", (username,))
                        sample = cur.fetchall()
                    from src.users.history_manager import _return_pg_conn
                    _return_pg_conn(conn)
                except Exception as e:
                    errors.append(f"PG query error: {e}")
                    traceback.print_exc()
                    try:
                        conn.rollback()
                    except:
                        pass
                    from src.users.history_manager import _return_pg_conn
                    _return_pg_conn(conn, close=True)
                    total_count = -1
                    sample = []
            else:
                errors.append("PG conn is None")
                total_count = -1
                sample = []
        else:
            total_count = -1
            sample = []
    except Exception as e:
        errors.append(f"PG check error: {e}")
        total_count = -1
        sample = []

    # Try get_flat_entries
    try:
        pg_entries = get_flat_entries(username, limit=50)
    except Exception as e:
        errors.append(f"get_flat_entries error: {e}")

    pg_summary = [{"id": e.get("id","")[:12], "year": e.get("year"), "month": e.get("month"),
                   "ts": str(e.get("timestamp",""))[:19], "name": e.get("entry_name","") or e.get("audio_filename","")}
                  for e in pg_entries]

    # Check JSON file
    import json as _json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    users_dir = os.path.join(base_dir, "usuarios")
    json_path = os.path.join(users_dir, username, "history.json")
    json_exists = os.path.exists(json_path)
    json_count = 0
    if json_exists:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                h = _json.load(f)
            for yd in h.values():
                if isinstance(yd, dict):
                    for md in yd.values():
                        if isinstance(md, dict):
                            for wd in md.values():
                                if isinstance(wd, dict):
                                    for dd in wd.values():
                                        if isinstance(dd, dict):
                                            json_count += len(dd.get("entries", []))
        except Exception:
            pass

    return jsonify({
        "username": username,
        "pg_available": pg_ok,
        "pg_total_count": total_count,
        "pg_sample": [{"id": r[0][:12], "ts": str(r[1])[:19], "name": r[2]} for r in sample] if sample else [],
        "pg_flat_count": len(pg_entries),
        "pg_entries": pg_summary[:20],
        "json_path": json_path,
        "json_exists": json_exists,
        "json_count": json_count,
        "errors": errors,
    })


# Admin usernames
_ADMIN_USERS = {"admin", "Vanesa.Admin", "Berna.Strauss", "FedericoCeballos", "MartinianoSosa"}


def _is_admin():
    """Check if current session user is an admin."""
    return session.get("username") in _ADMIN_USERS


@app.route("/admin/users-list")
def admin_users_list():
    """Return list of all registered users (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    users = user_manager.list_users()
    return jsonify({"users": users})


@app.route("/admin/full-diag")
def admin_full_diag():
    """
    One-shot live diagnostic: DB connectivity, total counts, per-user counts,
    what the saved-texts pipeline returns for a given user, and backup status.
    Open: /admin/full-diag?user=FernandezCeci
    """
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    import os as _os
    from src.users.history_manager import (_is_pg_available, _get_pg_conn,
                                            _return_pg_conn, get_all_entries,
                                            resolve_entry_date)
    out = {
        "DATABASE_URL_set": bool(_os.environ.get("DATABASE_URL")),
        "RAILWAY_ENVIRONMENT": _os.environ.get("RAILWAY_ENVIRONMENT", "NOT SET"),
        "pg_available": _is_pg_available(),
    }
    # Raw DB counts
    conn = _get_pg_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM analysis_history")
                out["db_total_entries"] = cur.fetchone()[0]
                cur.execute("SELECT username, COUNT(*) FROM analysis_history GROUP BY username ORDER BY 2 DESC")
                out["db_per_user"] = {r[0]: r[1] for r in cur.fetchall()}
            _return_pg_conn(conn)
        except Exception as exc:
            out["db_error"] = str(exc)
            _return_pg_conn(conn, close=True)
    else:
        out["db_error"] = "no PG connection"

    # What the read pipeline returns for the requested user
    user = request.args.get("user", "").strip()
    if user:
        try:
            entries = get_all_entries(user)
            out["pipeline_user"] = user
            out["pipeline_total_read"] = len(entries)
            months = {}
            for e in entries:
                y, m, d = resolve_entry_date(e)
                key = f"{y}-{m:02d}" if (y and m) else f"{y}-??"
                months[key] = months.get(key, 0) + 1
            out["pipeline_by_year_month"] = months
            out["pipeline_sample"] = [
                {"id": (e.get("id") or "")[:16],
                 "name": (e.get("entry_name") or e.get("audio_filename") or "")[:30],
                 "day_label": e.get("day_label", ""),
                 "ts": str(e.get("timestamp", ""))[:19]}
                for e in entries[:5]
            ]
        except Exception as exc:
            out["pipeline_error"] = str(exc)

    # Backup status
    try:
        from src.users.backup_manager import get_backup_status
        out["backup"] = get_backup_status()
    except Exception as exc:
        out["backup_error"] = str(exc)

    return jsonify(out)


@app.route("/admin/db-status")
def admin_db_status():
    """Diagnostic endpoint to check database connectivity and entry counts."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from src.users.history_manager import _is_pg_available, _get_pg_conn, _return_pg_conn
    import os
    status = {
        "DATABASE_URL_set": bool(os.environ.get("DATABASE_URL")),
        "pg_available": _is_pg_available(),
        "RAILWAY_ENVIRONMENT": os.environ.get("RAILWAY_ENVIRONMENT", "NOT SET"),
    }
    conn = _get_pg_conn()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT username, COUNT(*) as cnt FROM analysis_history GROUP BY username ORDER BY cnt DESC LIMIT 20")
                rows = cur.fetchall()
                status["entries_by_user"] = {r[0]: r[1] for r in rows}
                cur.execute("SELECT COUNT(*) FROM analysis_history")
                status["total_entries"] = cur.fetchone()[0]
            _return_pg_conn(conn)
        except Exception as exc:
            status["db_error"] = str(exc)
            _return_pg_conn(conn, close=True)
    else:
        status["db_error"] = "Could not get connection from pool"
    return jsonify(status)


@app.route("/admin/backup-status")
def admin_backup_status():
    """Report whether a data-loss is detected vs the last backup (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from src.users.backup_manager import get_backup_status
    return jsonify(get_backup_status())


@app.route("/admin/backup-now", methods=["POST", "GET"])
def admin_backup_now():
    """Force an immediate full backup (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from src.users.backup_manager import take_backup
    return jsonify(take_backup(reason="manual"))


@app.route("/admin/restore-backup", methods=["POST"])
def admin_restore_backup():
    """Restore all entries from the most recent backup (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from src.users.backup_manager import restore_latest_backup
    return jsonify(restore_latest_backup())


@app.route("/admin/auto-fix", methods=["POST", "GET"])
def admin_auto_fix():
    """
    Auto Fix: compare the live table entry-by-entry against the UNION of all
    backups and re-insert exactly the missing entries, one by one. Only adds.
    Pass ?dry_run=1 to preview what would be restored without writing. Admin only.
    """
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from src.users.backup_manager import auto_fix
    dry = request.args.get("dry_run", "0") == "1"
    return jsonify(auto_fix(dry_run=dry))


@app.route("/admin/compare-backups")
def admin_compare_backups():
    """Compare consecutive backups to see exactly when entries were lost (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from src.users.backup_manager import compare_backups
    return jsonify(compare_backups())


@app.route("/admin/dedup-all-texts")
def admin_dedup_all_texts():
    """Re-apply deduplication to ALL saved texts across ALL users (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403

    from src.users.history_manager import update_entry_text

    all_users = user_manager.list_users()
    summary = {"users_scanned": 0, "entries_scanned": 0, "entries_cleaned": 0, "details": []}

    for u in all_users:
        summary["users_scanned"] += 1
        try:
            entries = get_flat_entries(u, limit=1000)
        except Exception:
            continue
        user_cleaned = 0
        for e in entries:
            summary["entries_scanned"] += 1
            eid = e.get("id")
            if not eid:
                continue
            orig_short = e.get("text", "") or ""
            orig_full = e.get("text_full", "") or orig_short
            new_short = _dedup_transcription(orig_short)
            new_full = _dedup_transcription(orig_full)
            # Only update if something actually changed
            if new_short != orig_short or new_full != orig_full:
                if update_entry_text(u, eid, new_short, new_full):
                    user_cleaned += 1
                    summary["entries_cleaned"] += 1
        if user_cleaned > 0:
            summary["details"].append({"username": u, "cleaned": user_cleaned})

    return jsonify(summary)


@app.route("/admin/fix-dates/<username>")
def admin_fix_dates(username):
    """
    Fix entries whose timestamp month/day does not match their day_label
    (the DD/MM/YYYY the user actually assigned). Uses day_label as source of truth.
    Only touches month and day — year is kept from day_label too. Admin only.
    """
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403

    from src.users.history_manager import fix_entry_date
    from datetime import datetime as _dt, timezone as _tz

    dry_run = request.args.get("dry_run", "0") == "1"
    entries = get_flat_entries(username, limit=1000)

    fixed = []
    skipped_no_label = 0
    already_ok = 0

    for e in entries:
        eid = e.get("id")
        day_label = (e.get("day_label", "") or "").strip()
        ts_str = str(e.get("timestamp", ""))

        # day_label expected format: DD/MM/YYYY
        if not day_label or "/" not in day_label:
            skipped_no_label += 1
            continue
        try:
            parts = day_label.split("/")
            if len(parts) != 3:
                skipped_no_label += 1
                continue
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        except Exception:
            skipped_no_label += 1
            continue

        # Parse current timestamp to compare and preserve time-of-day
        try:
            cur_ts = _dt.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            cur_ts = _dt.now(_tz.utc)

        # If the timestamp already matches the day_label date, skip
        if cur_ts.year == y and cur_ts.month == m and cur_ts.day == d:
            already_ok += 1
            continue

        # Build corrected timestamp: date from day_label, time from original ts
        try:
            new_ts = _dt(y, m, d, cur_ts.hour, cur_ts.minute, cur_ts.second,
                         cur_ts.microsecond, tzinfo=_tz.utc)
        except Exception:
            skipped_no_label += 1
            continue

        entry_info = {
            "id": eid,
            "entry_name": (e.get("entry_name", "") or e.get("audio_filename", ""))[:30],
            "old_ts": ts_str[:19],
            "day_label": day_label,
            "new_ts": new_ts.isoformat()[:19],
        }

        if not dry_run:
            if fix_entry_date(username, eid, new_ts):
                fixed.append(entry_info)
        else:
            fixed.append(entry_info)

    return jsonify({
        "username": username,
        "dry_run": dry_run,
        "total_entries": len(entries),
        "fixed_count": len(fixed),
        "already_correct": already_ok,
        "skipped_no_label": skipped_no_label,
        "fixed": fixed,
    })


@app.route("/admin/test-texts/<username>")
def admin_test_texts(username):
    """Test endpoint - returns entries without any year/month filter (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    entries = get_flat_entries(username, limit=10)
    result = []
    for e in entries[:10]:
        result.append({
            "id": e.get("id", ""),
            "entry_name": e.get("entry_name", "") or e.get("audio_filename", ""),
            "year": e.get("year"),
            "month": e.get("month"),
            "timestamp": str(e.get("timestamp", ""))[:20],
            "text_preview": (e.get("text", "") or "")[:40],
        })
    return jsonify({"total_in_db": len(entries), "sample": result})


@app.route("/admin/diagnose-days/<username>")
def admin_diagnose_days(username):
    """Show the resolved (year,month,day) of each entry for a given month (admin only).
    Helps diagnose why the daily line chart misses some days."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from src.users.history_manager import get_all_entries, resolve_entry_date
    year = request.args.get("year", type=int) or 2026
    month = request.args.get("month", type=int) or 0

    entries = get_all_entries(username)
    rows = []
    day_counts = {}
    for e in entries:
        ey, em, ed = resolve_entry_date(e)
        if ey == year and (month == 0 or em == month):
            day_counts[ed] = day_counts.get(ed, 0) + 1
            rows.append({
                "name": (e.get("entry_name", "") or e.get("audio_filename", ""))[:30],
                "resolved_day": ed,
                "resolved_month": em,
                "day_label": e.get("day_label", ""),
                "timestamp": str(e.get("timestamp", ""))[:19],
                "meta_year": e.get("year"),
                "meta_month": e.get("month"),
            })
    rows.sort(key=lambda r: (r["resolved_day"] or 0))
    return jsonify({
        "username": username, "year": year, "month": month,
        "total_in_month": len(rows),
        "day_counts": {str(k): v for k, v in sorted(day_counts.items(), key=lambda x: (x[0] or 0))},
        "entries": rows,
    })


@app.route("/admin/diagnose-count/<username>")
def admin_diagnose_count(username):
    """Diagnose why list count differs from informe count (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from datetime import datetime as _dt
    year = request.args.get("year", type=int) or 2026

    entries = get_flat_entries(username, limit=1000)

    total = len(entries)
    con_year_valido = 0
    con_month_valido = 0
    sin_year = 0
    sin_month = 0
    year_distinto = 0
    problematicas = []

    for e in entries:
        e_year = e.get("year")
        e_month = e.get("month")
        # Replicar extraccion desde timestamp
        if e_year is None and e.get("timestamp"):
            try:
                ts_str = str(e["timestamp"])
                if hasattr(e["timestamp"], "year"):
                    e_year = e["timestamp"].year
                    e_month = e["timestamp"].month
                elif "T" in ts_str or "-" in ts_str:
                    ts = _dt.fromisoformat(ts_str.replace("Z", "+00:00"))
                    e_year = ts.year
                    e_month = ts.month
            except Exception:
                pass

        if e_year is None:
            sin_year += 1
        elif e_year != year:
            year_distinto += 1
        else:
            con_year_valido += 1

        if not e_month or not (1 <= (e_month or 0) <= 12):
            sin_month += 1
        else:
            con_month_valido += 1

        # Entradas que aparecen en lista pero NO en informe
        # Lista: (not year or e_year == year) and (not month or e_month is None or e_month == month)
        # Informe: e_year == year and e_month and 1<=e_month<=12
        en_lista = (e_year == year)  # con year=2026, month=todos
        en_informe = (e_year == year and e_month and 1 <= (e_month or 0) <= 12)
        if en_lista and not en_informe:
            problematicas.append({
                "id": e.get("id", ""),
                "entry_name": (e.get("entry_name", "") or e.get("audio_filename", ""))[:30],
                "year": e_year,
                "month": e_month,
                "timestamp": str(e.get("timestamp", ""))[:20],
            })

    return jsonify({
        "username": username,
        "total_entries": total,
        "con_year_valido": con_year_valido,
        "year_distinto": year_distinto,
        "sin_year": sin_year,
        "con_month_valido": con_month_valido,
        "sin_month_valido": sin_month,
        "en_lista_pero_no_en_informe": len(problematicas),
        "problematicas": problematicas,
    })


@app.route("/admin/dump-entries/<username>")
def admin_dump_entries(username):
    """Dump ALL entries with their date fields for full diagnosis (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403
    from datetime import datetime as _dt
    entries = get_flat_entries(username, limit=1000)
    # Count by year and by (year,month)
    by_year = {}
    by_year_month = {}
    dump = []
    for e in entries:
        e_year = e.get("year")
        e_month = e.get("month")
        ts_str = str(e.get("timestamp", ""))
        if (e_year is None or not e_month) and ts_str:
            try:
                ts = _dt.fromisoformat(ts_str.replace("Z", "+00:00"))
                e_year = e_year or ts.year
                e_month = e_month or ts.month
            except Exception:
                pass
        yk = str(e_year)
        ymk = f"{e_year}-{e_month:02d}" if (e_year and e_month) else f"{e_year}-??"
        by_year[yk] = by_year.get(yk, 0) + 1
        by_year_month[ymk] = by_year_month.get(ymk, 0) + 1
        dump.append({
            "name": (e.get("entry_name", "") or e.get("audio_filename", ""))[:25],
            "year": e_year,
            "month": e_month,
            "ts": ts_str[:19],
            "day_label": e.get("day_label", ""),
        })
    return jsonify({
        "username": username,
        "total": len(entries),
        "by_year": by_year,
        "by_year_month": by_year_month,
        "entries": dump,
    })


@app.route("/admin/user-texts/<username>")
def admin_user_texts(username):
    """Return texts for a specific user filtered by year/month/fecha (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403

    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    fecha = request.args.get("fecha", "").strip()  # format: YYYY-MM-DD

    from src.users.history_manager import get_all_entries, resolve_entry_date
    entries = get_all_entries(username)

    filtered = []
    for e in entries:
        e_year, e_month, _ = resolve_entry_date(e)
        # Include the entry if year/month match (unknown values pass through so
        # nothing is ever silently dropped). Same rule used by every endpoint.
        year_ok = (not year) or (e_year == year) or (e_year is None)
        month_ok = (not month) or (e_month == month) or (e_month is None)
        if year_ok and month_ok:
            filtered.append({
                "id": e.get("id", ""),
                "entry_name": e.get("entry_name", "") or e.get("audio_filename", ""),
                "text": (e.get("text", "") or "")[:60],
                "intent": e.get("intent", ""),
                "timestamp": (str(e.get("timestamp", "")) or "")[:10],
                "source": e.get("source", ""),
            })

    return jsonify({"entries": filtered})


@app.route("/admin/stats/<username>")
def admin_stats(username):
    """Return commercial indicator stats for a user over a period (admin only)."""
    if not _is_admin():
        return jsonify({"error": "unauthorized", "message": "No eres admin"}), 403

    period = request.args.get("period", "mensual")
    year = request.args.get("year", type=int) or 2026

    from src.users.history_manager import get_all_entries, resolve_entry_date
    # If _all, aggregate across all users
    if username == "_all":
        all_users = user_manager.list_users()
        entries = []
        for u in all_users:
            try:
                entries.extend(get_all_entries(u))
            except Exception:
                pass
        display_name = "General (todos)"
    else:
        entries = get_all_entries(username)
        display_name = username

    # Determine which months to include based on period
    from datetime import datetime as _dt
    current_month = _dt.now().month

    period_months = {
        "mensual": [current_month],
        "bimestral": list(range(max(1, current_month - 1), current_month + 1)),
        "trimestral": list(range(max(1, current_month - 2), current_month + 1)),
        "cuatrimestral": list(range(max(1, current_month - 3), current_month + 1)),
        "semestral": list(range(max(1, current_month - 5), current_month + 1)),
        "anual": list(range(1, current_month + 1)),
    }

    # Handle specific month selection
    specific_month = request.args.get("month", type=int)
    if period == "specific" and specific_month:
        months_to_include = [specific_month]
    else:
        months_to_include = period_months.get(period, [current_month])

    # Aggregate commercial indicators
    totals = {
        "palabras_positivas": 0,
        "respuestas_afirmativas": 0,
        "indicios_cierre": 0,
        "escasez_comercial": 0,
        "pedidos_referidos": 0,
        "objeciones": 0,
        "indicios_prospeccion": 0,
    }
    word_detail = {}
    entry_count = 0

    for e in entries:
        e_year, e_month, _ = resolve_entry_date(e)

        if e_year == year and e_month in months_to_include:
            # Count the entry regardless of whether it has commercial data,
            # so entry_count matches the list/report counts.
            entry_count += 1
            commercial = e.get("commercial") or {}
            if commercial:
                for key in totals:
                    totals[key] += commercial.get(key, 0)
                # Aggregate word-level detail
                detalle = commercial.get("detalle") or {}
                for cat, words in detalle.items():
                    if cat not in word_detail:
                        word_detail[cat] = {}
                    if isinstance(words, dict):
                        for word, count in words.items():
                            word_detail[cat][word] = word_detail[cat].get(word, 0) + count

    return jsonify({
        "username": display_name if username == "_all" else username,
        "period": period,
        "year": year,
        "months": months_to_include,
        "entry_count": entry_count,
        "totals": totals,
        "word_detail": word_detail,
    })


@app.route("/admin/sync", methods=["POST"])
def admin_sync():
    """Dispara una sincronización manual (solo admin)."""
    if not _is_admin():
        return jsonify({"error": True, "error_message": "No autorizado"}), 403

    historical = request.json.get("historical", False) if request.is_json else False
    try:
        summary = sync_pipeline.run(historical=historical)
        return jsonify({"ok": True, "summary": summary})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/admin/sync/log")
def admin_sync_log():
    """Retorna el log de sincronizaciones (solo admin)."""
    if not _is_admin():
        return jsonify({"error": True, "error_message": "No autorizado"}), 403

    import json as _json
    log_file = os.path.join("config", "sync_log.json")
    if not os.path.exists(log_file):
        return jsonify([])
    with open(log_file, "r", encoding="utf-8") as f:
        return jsonify(_json.load(f))


@app.route("/debug-sync-one")
def debug_sync_one():
    """
    Debug endpoint: cleans ALL entries for the logged-in user.
    ADMIN ONLY — protegido para evitar borrado accidental.
    """
    if not session.get("username"):
        return jsonify({"error": "not logged in"}), 401
    if not _is_admin():
        return jsonify({"error": "unauthorized — solo admins pueden usar este endpoint"}), 403

    username = session["username"]
    import traceback

    try:
        import psycopg2
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            return jsonify({"success": False, "error": "DATABASE_URL not set"})

        if db_url.startswith("postgres://"):
            db_url = "postgresql://" + db_url[len("postgres://"):]

        conn = psycopg2.connect(db_url)
        conn.autocommit = True

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM analysis_history WHERE username = %s", (username,))
            count_before = cur.fetchone()[0]

            # Delete ALL entries for this user
            cur.execute("DELETE FROM analysis_history WHERE username = %s", (username,))
            deleted = cur.rowcount

        conn.close()

        return jsonify({
            "success": True,
            "message": f"Eliminadas {deleted} entradas para {username}.",
            "username": username,
            "entries_before": count_before,
            "entries_deleted": deleted,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        })


@app.route("/admin/informe")
def admin_informe():
    """
    Return aggregated report data for the informe panel.
    Groups entries by username and month for annual tracking.
    Supports filters: year, month, week, seller.
    Admin only.
    """
    if not _is_admin():
        return jsonify({"error": "unauthorized"}), 403

    year = request.args.get("year", type=int) or 2026
    meta_mensual = request.args.get("meta", type=int) or 30
    filter_month = request.args.get("month", type=int) or 0  # 0 = all months
    filter_week = request.args.get("week", type=int) or 0    # 0 = all weeks (exact week)
    week_upto = request.args.get("week_upto", type=int) or 0  # >0 = weeks 1..N inclusive
    filter_seller = request.args.get("seller", "") or "_all"

    from src.users.history_manager import get_flat_entries
    from datetime import datetime as _dt

    all_users = user_manager.list_users()
    if filter_seller != "_all" and filter_seller in all_users:
        target_users = [filter_seller]
    else:
        target_users = all_users

    # Build matrix: {username: {month: count}}
    # Also build weekly breakdown: {username: {month: {week: count}}}
    # And a daily breakdown for the selected week: {username: {day: count}}
    matrix = {}
    weekly = {}
    daily = {}  # per-user day-of-month counts, only populated when a week is selected

    from src.users.history_manager import get_all_entries, resolve_entry_date

    for u in target_users:
        entries = get_all_entries(u)
        matrix[u] = {m: 0 for m in range(1, 13)}
        weekly[u] = {m: {1: 0, 2: 0, 3: 0, 4: 0} for m in range(1, 13)}
        daily[u] = {}
        for e in entries:
            e_year, e_month, e_day = resolve_entry_date(e)
            # Count the entry if it belongs to the requested year.
            # If month is still unknown but the year matches, assign it to month 1
            # so it is NOT silently dropped (keeps list count == report count).
            if e_year == year:
                if not e_month or not (1 <= e_month <= 12):
                    e_month = 1  # fallback bucket so the entry is still counted
                # Week filter
                if e_day:
                    w = min(4, (e_day - 1) // 7 + 1)
                else:
                    w = 1  # default to week 1 if no day info
                # Apply week filter: exact week, or "up to week N" (cumulative)
                if filter_week > 0 and w != filter_week:
                    continue
                if week_upto > 0 and w > week_upto:
                    continue
                # Apply month filter
                if filter_month > 0 and e_month != filter_month:
                    continue
                matrix[u][e_month] = matrix[u].get(e_month, 0) + 1
                weekly[u][e_month][w] = weekly[u][e_month].get(w, 0) + 1
                # Daily breakdown: populated whenever a month is selected (with or
                # without a week filter) so the line chart can show a per-day trend.
                if filter_month > 0 and e_day:
                    daily[u][e_day] = daily[u].get(e_day, 0) + 1

    # Totals per month
    totals_per_month = {}
    for m in range(1, 13):
        totals_per_month[m] = sum(matrix[u].get(m, 0) for u in target_users)

    # Per-user total
    user_totals = {u: sum(matrix[u].values()) for u in target_users}

    # Compliance stats (based on filter_month or current_month)
    eval_month = filter_month if filter_month > 0 else _dt.now().month
    cumplen = [u for u in target_users if matrix[u].get(eval_month, 0) >= meta_mensual]
    no_cumplen = [u for u in target_users if matrix[u].get(eval_month, 0) < meta_mensual and user_totals[u] > 0]

    return jsonify({
        "year": year,
        "meta_mensual": meta_mensual,
        "matrix": matrix,
        "weekly": weekly,
        "daily": daily,
        "totals_per_month": totals_per_month,
        "user_totals": user_totals,
        "current_month": eval_month,
        "cumplen": cumplen,
        "no_cumplen": no_cumplen,
        "total_general": sum(totals_per_month.values()),
        "filter_month": filter_month,
        "filter_week": filter_week,
        "week_upto": week_upto,
        "filter_seller": filter_seller,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 50)
    print(f"  Abre tu navegador en: http://localhost:{port}")
    print("=" * 50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)
