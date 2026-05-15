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
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
# Allow large audio uploads (no size limit enforced here — handled by gunicorn/nginx)
app.config["MAX_CONTENT_LENGTH"] = None
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

    # Pass 1: Remove consecutive repeated single words (any number of repetitions)
    for _ in range(3):
        prev = result
        result = re.sub(r'\b(\w+)(\s+\1)+\b', r'\1', result, flags=re.IGNORECASE)
        if result == prev:
            break

    # Pass 2: Remove consecutive repeated two-word phrases
    for _ in range(3):
        prev = result
        result = re.sub(r'\b(\w+\s+\w+)(\s+\1)+\b', r'\1', result, flags=re.IGNORECASE)
        if result == prev:
            break

    # Pass 3: Remove consecutive repeated three-word phrases
    for _ in range(2):
        prev = result
        result = re.sub(r'\b(\w+\s+\w+\s+\w+)(\s+\1)+\b', r'\1', result, flags=re.IGNORECASE)
        if result == prev:
            break

    # Pass 4: Remove repeated short sentences/phrases separated by punctuation
    # Handles: "Si, si. Si, si. Si, si." → "Si, si."
    # Handles: "Ah, ese modelo, sí. Si, si. Si, si." repeated patterns
    for _ in range(3):
        prev = result
        # Match a short phrase (up to ~30 chars) followed by itself with optional space/punctuation
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
    from src.users.history_manager import migrate_json_to_pg
    _migration = migrate_json_to_pg()
    if not _migration.get("skipped"):
        print(f"Migración JSON→PG: {_migration.get('migrated', 0)} entradas migradas, "
              f"{_migration.get('errors', 0)} errores.")
except Exception as _mig_exc:
    print(f"Warning: migración JSON→PG falló: {_mig_exc}")

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

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analizador de Textos - Ventas y Bienes Raices v2</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

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
            cursor: pointer;
            box-sizing: border-box;
        }

        .highlight-overlay.active {
            display: block;
        }

        .highlight-close-btn {
            display: none;
            position: absolute;
            top: 6px;
            right: 8px;
            background: #1a1d27;
            border: 1px solid #3a3d4a;
            color: #aaa;
            border-radius: 50%;
            width: 22px;
            height: 22px;
            font-size: 0.7rem;
            cursor: pointer;
            z-index: 11;
            line-height: 1;
        }

        .highlight-close-btn.active {
            display: block;
        }

        .highlight-close-btn:hover {
            background: #2a2d3a;
            color: #fff;
        }

        .hl-palabras_positivas { background: rgba(91, 245, 163, 0.25); color: #5bf5a3; border-radius: 3px; padding: 0 2px; }
        .hl-respuestas_afirmativas { background: rgba(74, 108, 247, 0.25); color: #7b9cff; border-radius: 3px; padding: 0 2px; }
        .hl-indicios_cierre { background: rgba(245, 215, 91, 0.25); color: #f5d75b; border-radius: 3px; padding: 0 2px; }
        .hl-escasez_comercial { background: rgba(245, 163, 91, 0.25); color: #f5a35b; border-radius: 3px; padding: 0 2px; }
        .hl-pedidos_referidos { background: rgba(163, 91, 245, 0.25); color: #b38bff; border-radius: 3px; padding: 0 2px; }
        .hl-objeciones { background: rgba(245, 91, 91, 0.25); color: #f55b5b; border-radius: 3px; padding: 0 2px; }
        .hl-indicios_prospeccion { background: rgba(91, 212, 245, 0.25); color: #5bd4f5; border-radius: 3px; padding: 0 2px; }

        /* Date selectors */
        .date-selectors {
            display: flex;
            gap: 12px;
            margin-bottom: 10px;
        }
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
        }

        .card-title {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #666;
            margin-bottom: 10px;
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
            animation: slideDown 0.2s ease-out;
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
            animation: slideDown 0.25s ease-out;
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

        .indicator-detail.open { display: block; }

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

        .lead-detail-panel.open { display: block; }

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
    </style>
</head>
<body>
<div class="container">
    <div class="top-bar">
        <div>
            <h1>Analizador de Textos</h1>
            <p class="subtitle">Ventas y Bienes Raices &mdash; Analisis con Machine Learning</p>
        </div>
        <div style="text-align:right;">
            <div class="user-info" style="margin-bottom:4px;">Usuario: <strong>{{ username }}</strong></div>
            <a href="/logout" class="btn-logout">Cerrar sesion</a>
        </div>
    </div>

    <div class="input-section">
        <div class="date-selectors">
            <div class="date-select-group">
                <label for="selectYear">Año</label>
                <select id="selectYear" onchange="loadSavedTexts()">
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
                <label>Textos</label>
                <button class="saved-texts-btn" onclick="toggleSavedTexts()">📄 Ver textos <span id="savedTextsCount">(0)</span></button>
            </div>
        </div>

        <div class="saved-texts-panel" id="savedTextsPanel">
            <div class="saved-texts-header">
                <span>📄 Textos guardados en este periodo</span>
                <button class="saved-texts-close" onclick="toggleSavedTexts()">✕</button>
            </div>
            <div class="saved-texts-list" id="savedTextsList">
                <div class="saved-texts-empty">Selecciona un periodo para ver los textos guardados.</div>
            </div>
        </div>

        <div class="textarea-wrapper" id="textareaWrapper">
            <textarea id="textInput"
                placeholder="O escribe / pega aqui el texto que quieres analizar...&#10;&#10;Ejemplo: Ofrezco apartamento de 3 habitaciones en USD 180,000 negociable, zona norte, 95 m2."></textarea>
            <div class="highlight-overlay" id="highlightOverlay" onclick="closeHighlightOverlay()"></div>
            <button class="highlight-close-btn" id="highlightCloseBtn" onclick="closeHighlightOverlay()" title="Cerrar resaltado">✕</button>
        </div>
        <div class="btn-row">
            <button class="btn-primary" onclick="analyze()">&#128269; Analizar</button>
            <button class="btn-secondary" onclick="clearAll()">Limpiar</button>
            <input type="text" id="entryNameInput" class="save-name-input" placeholder="Titulo del texto (obligatorio para guardar)..." style="flex:1; margin-left:8px;">
            <button class="btn-save" onclick="saveEntry()">&#128190; Guardar</button>
        </div>
        <div class="loading" id="loading" style="margin-top:10px;">Analizando texto...</div>
    </div>

    <div class="results" id="results"></div>

    <!-- ── HISTORY ── -->
    <div class="history-section" id="historySection">
        <div class="history-header" onclick="toggleHistory()">
            <div class="history-title">&#128197; Historial de Analisis</div>
            <div class="history-toggle" id="historyToggleIcon">&#9660; Ver historial</div>
        </div>
        <div class="history-tree" id="historyTree">
            <div class="history-empty" id="historyEmpty">Cargando historial...</div>
        </div>
    </div>
</div>

<script>
let _lastCommercialData = null;

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
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, year: parseInt(year), month: parseInt(month), entry_name: entryName })
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
                <span class="ext-row-label">▶️ Accion siguiente</span>
                <div class="ext-action-text">${c.accion_siguiente}</div>
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

    el.innerHTML = `
        <div class="input-preview">"${preview}"</div>
        <div class="result-grid">
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('intencion-content')">
                    Intencion del Texto &nbsp;<span class="card-arrow" id="intencion-arrow">&#9660;</span>
                </div>
                <div class="card-collapsible-content" id="intencion-content">
                    <span class="badge badge-${data.intent}">${intentEs}</span>
                    ${confBar(data.intent_confidence)}
                    <div class="intent-detail-panel">
                        <div class="intent-detail-header">${iDetail.icon} ${intentEs}</div>
                        <div class="intent-detail-desc">${iDetail.desc}</div>
                        <div class="intent-detail-section">
                            <div class="intent-section-title">Que significa para la venta</div>
                            <div class="intent-section-text">${iDetail.meaning}</div>
                        </div>
                        <div class="intent-detail-section intent-seller-box">
                            <div class="intent-section-title">👤 Para el vendedor</div>
                            <div class="intent-section-text">${iDetail.forSeller}</div>
                        </div>
                        <div class="intent-detail-section">
                            <div class="intent-section-title">💡 Tips practicos</div>
                            <ul class="intent-tips-list">
                                ${iDetail.tips.map(t => `<li>${t}</li>`).join('')}
                            </ul>
                        </div>
                        <div class="intent-detail-section intent-next-step">
                            <div class="intent-section-title">▶️ Siguiente paso</div>
                            <div class="intent-section-text">${iDetail.nextStep}</div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('sentimiento-content')">
                    Sentimiento &nbsp;<span class="card-arrow" id="sentimiento-arrow">&#9660;</span>
                </div>
                <div class="card-collapsible-content" id="sentimiento-content">
                    <span class="badge badge-${data.sentiment}">${sentimentEs}</span>
                    ${confBar(data.sentiment_confidence)}
                    ${renderSentimentDetail(data.sentiment)}
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('ventas-content')">
                    Conceptos de Ventas Detectados &nbsp;<span class="card-arrow" id="ventas-arrow">&#9660;</span>
                </div>
                <div class="card-collapsible-content" id="ventas-content">
                    ${salesHtml}
                    ${renderSalesConceptsDetail(data.sales_concepts)}
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('bienes-raices-content')">
                    Conceptos de Bienes Raices Detectados &nbsp;<span class="card-arrow" id="bienes-raices-arrow">&#9660;</span>
                </div>
                <div class="card-collapsible-content" id="bienes-raices-content">
                    ${reHtml}
                    ${renderRealEstateConceptsDetail(data.real_estate_concepts)}
                </div>
            </div>
            <div class="card full-width">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('datos-extraidos-content')">
                    Datos Extraidos del Texto &nbsp;<span class="card-arrow" id="datos-extraidos-arrow">&#9660;</span>
                </div>
                <div class="card-collapsible-content" id="datos-extraidos-content">
                    ${entitiesHtml}
                    ${extDataHtml}
                </div>
            </div>
        </div>
        ${renderCommercial(data.commercial)}
        <div class="timestamp">Analizado el: ${data.analyzed_at}</div>
        ${renderSaveConfirmation(data)}
    `;
    el.style.display = 'block';
}

function renderCommercial(c) {
    if (!c) return '';

    const pct = c.probabilidad_cierre;
    const fillClass = pct > 70 ? 'prob-fill-hot' : pct > 40 ? 'prob-fill-warm' : 'prob-fill-cold';

    const indicators = [
        { key: 'palabras_positivas',    label: 'Palabras Positivas',     value: c.palabras_positivas,    cls: c.palabras_positivas > 0 ? 'positive' : '', color: '#5bf5a3' },
        { key: 'respuestas_afirmativas',label: 'Respuestas Afirmativas', value: c.respuestas_afirmativas, cls: c.respuestas_afirmativas > 0 ? 'positive' : '', color: '#7b9cff' },
        { key: 'indicios_cierre',       label: 'Indicios de Cierre',     value: c.indicios_cierre,       cls: c.indicios_cierre > 0 ? 'positive' : '', color: '#f5d75b' },
        { key: 'escasez_comercial',     label: 'Escasez Comercial',      value: c.escasez_comercial,     cls: '', color: '#f5a35b' },
        { key: 'pedidos_referidos',     label: 'Pedidos de Referidos',   value: c.pedidos_referidos,     cls: '', color: '#b38bff' },
        { key: 'objeciones',            label: 'Objeciones',             value: c.objeciones,            cls: c.objeciones > 2 ? 'highlight' : '', color: '#f55b5b' },
        { key: 'indicios_prospeccion',  label: 'Prospeccion',            value: c.indicios_prospeccion,  cls: '', color: '#5bd4f5' },
    ];

    const indicatorsHtml = indicators.map((ind, idx) => {
        const detail = c.detalle ? c.detalle[ind.key] : {};
        const hasDetail = detail && Object.keys(detail).length > 0;
        const detailId = 'detail-' + idx;

        let detailHtml = '';
        if (hasDetail) {
            const rows = Object.entries(detail)
                .sort((a, b) => b[1] - a[1])
                .map(([word, count]) =>
                    `<div class="detail-word-row detail-word-clickable" onclick="event.stopPropagation(); highlightSingleWord('${word.replace(/'/g, "\\\\'")}', '${ind.key}');">
                        <span class="detail-word">${word}</span>
                        <span class="detail-count">${count}x</span>
                    </div>`
                ).join('');
            detailHtml = `<div class="indicator-detail" id="${detailId}">${rows}</div>`;
        } else {
            detailHtml = `<div class="indicator-detail" id="${detailId}"><span class="detail-empty">Ninguna detectada</span></div>`;
        }

        return `
        <div>
            <div class="indicator-item ${hasDetail ? 'has-detail' : ''}"
                 style="border-top: 2px solid ${ind.color};"
                 onclick="toggleDetail('${detailId}', this); highlightInText('${ind.key}');">
                <div class="indicator-label">${ind.label}</div>
                <div class="indicator-value ${ind.cls}">${ind.value}</div>
            </div>
            ${detailHtml}
        </div>`;
    }).join('');

    return `
    <div class="commercial-section">
        <div class="commercial-title">Analisis Comercial Inmobiliario</div>

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
    </div>`;
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
    const defaultName = (data.input_text || '').substring(0, 40).replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ\s]/g, '').trim() + '...';

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
            body: JSON.stringify({ text, year, month, entry_name: name })
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
    const panel = document.getElementById('savedTextsPanel');
    if (panel) {
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) loadSavedTexts();
    }
}

async function loadSavedTexts() {
    const year = document.getElementById('selectYear').value;
    const month = document.getElementById('selectMonth').value;
    const months = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

    try {
        const response = await fetch(`/saved-texts?year=${year}&month=${month}`);
        const data = await response.json();
        const list = document.getElementById('savedTextsList');
        const count = document.getElementById('savedTextsCount');

        if (data.entries && data.entries.length > 0) {
            count.textContent = `(${data.entries.length})`;
            list.innerHTML = data.entries.map(e => {
                const preview = (e.text || '').substring(0, 60) + '...';
                const intentBadge = e.intent ? `<span class="st-badge">${e.intent}</span>` : '';
                return `<div class="saved-text-item">
                    <div class="saved-text-row" onclick="loadSavedText('${e.id}')">
                        <div class="saved-text-name">${e.entry_name || preview}</div>
                        <div class="saved-text-meta">${intentBadge} <span class="saved-text-time">${e.timestamp || ''}</span></div>
                    </div>
                    <button class="saved-text-delete" onclick="deleteSavedText('${e.id}')" title="Eliminar">🗑️</button>
                </div>`;
            }).join('');
        } else {
            count.textContent = '(0)';
            list.innerHTML = `<div class="saved-texts-empty">No hay textos guardados en ${months[month]} ${year}.</div>`;
        }
    } catch(e) {
        console.error('Error loading saved texts:', e);
    }
}

async function loadSavedText(entryId) {
    // Load a saved text into the textarea for re-analysis
    try {
        const response = await fetch(`/saved-text/${entryId}`);
        const data = await response.json();
        if (data.text) {
            document.getElementById('textInput').value = data.text;
            toggleSavedTexts();
        }
    } catch(e) {
        console.error('Error loading text:', e);
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
            </div>
            <div class="intent-detail-section intent-seller-box">
                <div class="intent-section-title">👤 Para el vendedor</div>
                <div class="intent-section-text">${d.forSeller}</div>
            </div>
            <div class="intent-detail-section">
                <div class="intent-section-title">💡 Tips practicos</div>
                <ul class="intent-tips-list">
                    ${d.tips.map(t => `<li>${t}</li>`).join('')}
                </ul>
            </div>
            <div class="intent-detail-section" style="border-left:3px solid ${sentiment === 'NEGATIVE' ? '#f55b5b' : sentiment === 'POSITIVE' ? '#5bf5a3' : '#f5a35b'}">
                <div class="intent-section-title">⚠️ Nivel de riesgo</div>
                <div class="intent-section-text">${d.risk}</div>
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
            <div class="concept-detail-source">Fragmento: <em>"${c.source_text}"</em></div>
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
            <div class="concept-detail-source">Fragmento: <em>"${c.source_text}"</em></div>
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

    // Scroll to the textarea area only when clicking a specific word
    const wrapper = document.getElementById('textareaWrapper');
    wrapper.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
    wrapper.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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

    // No scroll here — only scroll when clicking a specific word in the detail
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
        // Use word boundary matching
        const escapedWord = normalizedWord.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
        const regex = new RegExp('(?<![a-z])' + escapedWord + '(?![a-z])', 'gi');
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

    return result;
}

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function closeHighlightOverlay() {
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    overlay.classList.remove('active');
    closeBtn.classList.remove('active');
}

function toggleDetail(detailId, cardEl) {
    const panel = document.getElementById(detailId);
    if (!panel) return;
    const isOpen = panel.classList.contains('open');
    panel.classList.toggle('open', !isOpen);
    cardEl.classList.toggle('expanded', !isOpen);
}

// Allow Ctrl+Enter to submit, and auto-analyze after 2s of inactivity
document.addEventListener('DOMContentLoaded', () => {
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
        // Auto-analyze disabled — only analyze when user clicks the button
    });

    loadHistory();
});

// ── History ───────────────────────────────────────────────────────────────

let historyOpen = false;

function toggleHistory() {
    historyOpen = !historyOpen;
    document.getElementById('historyTree').classList.toggle('open', historyOpen);
    document.getElementById('historyToggleIcon').textContent =
        historyOpen ? '▲ Ocultar historial' : '▼ Ver historial';
    if (historyOpen) loadHistory();
}

async function loadHistory() {
    try {
        const resp = await fetch('/history');
        const data = await resp.json();
        renderHistoryTree(data);
    } catch (e) {
        document.getElementById('historyEmpty').textContent = 'Error al cargar historial.';
    }
}

function renderHistoryTree(history) {
    const container = document.getElementById('historyTree');
    const emptyEl = document.getElementById('historyEmpty');

    const years = Object.keys(history).sort().reverse();
    if (years.length === 0) {
        emptyEl.style.display = 'block';
        emptyEl.textContent = 'Aun no hay analisis guardados.';
        return;
    }
    emptyEl.style.display = 'none';

    // Remove old rendered nodes (keep emptyEl)
    Array.from(container.children).forEach(c => {
        if (c.id !== 'historyEmpty') c.remove();
    });

    years.forEach(year => {
        const yearDiv = document.createElement('div');
        yearDiv.className = 'history-year';

        const months = Object.keys(history[year]).sort().reverse();
        let totalYear = 0;
        months.forEach(m => {
            Object.values(history[year][m]).forEach(w => {
                Object.values(w).forEach(d => { totalYear += (d.entries || []).length; });
            });
        });

        const yearLabel = document.createElement('div');
        yearLabel.className = 'history-year-label';
        yearLabel.innerHTML = `<span>&#128197; ${year}</span><span style="color:#555">${totalYear} analisis &#9660;</span>`;
        let yearOpen = true;
        const yearContent = document.createElement('div');

        yearLabel.onclick = () => {
            yearOpen = !yearOpen;
            yearContent.style.display = yearOpen ? '' : 'none';
            yearLabel.querySelector('span:last-child').innerHTML =
                `${totalYear} analisis ${yearOpen ? '&#9650;' : '&#9660;'}`;
        };

        yearDiv.appendChild(yearLabel);
        yearDiv.appendChild(yearContent);

        months.forEach(monthKey => {
            const monthDiv = document.createElement('div');
            monthDiv.className = 'history-month';

            const weeks = Object.keys(history[year][monthKey]).sort().reverse();
            let totalMonth = 0;
            weeks.forEach(w => {
                Object.values(history[year][monthKey][w]).forEach(d => {
                    totalMonth += (d.entries || []).length;
                });
            });

            const monthLabel = document.createElement('div');
            monthLabel.className = 'history-month-label';
            const mName = monthKey.split('-').slice(1).join('-');
            monthLabel.innerHTML = `<span>&#128198; ${mName}</span><span style="color:#444">${totalMonth} &#9660;</span>`;
            let monthOpen = false;
            const monthContent = document.createElement('div');
            monthContent.style.display = 'none';

            monthLabel.onclick = () => {
                monthOpen = !monthOpen;
                monthContent.style.display = monthOpen ? '' : 'none';
                monthLabel.querySelector('span:last-child').innerHTML =
                    `${totalMonth} ${monthOpen ? '&#9650;' : '&#9660;'}`;
            };

            monthDiv.appendChild(monthLabel);
            monthDiv.appendChild(monthContent);

            weeks.forEach(weekKey => {
                const weekDiv = document.createElement('div');
                weekDiv.className = 'history-week';

                const days = Object.keys(history[year][monthKey][weekKey]).sort().reverse();
                let totalWeek = 0;
                days.forEach(d => { totalWeek += (history[year][monthKey][weekKey][d].entries || []).length; });

                const weekLabel = document.createElement('div');
                weekLabel.className = 'history-week-label';
                weekLabel.innerHTML = `<span>&#128336; ${weekKey.replace('-', ' ')}</span><span style="color:#333">${totalWeek} &#9660;</span>`;
                let weekOpen = false;
                const weekContent = document.createElement('div');
                weekContent.style.display = 'none';

                weekLabel.onclick = () => {
                    weekOpen = !weekOpen;
                    weekContent.style.display = weekOpen ? '' : 'none';
                    weekLabel.querySelector('span:last-child').innerHTML =
                        `${totalWeek} ${weekOpen ? '&#9650;' : '&#9660;'}`;
                };

                weekDiv.appendChild(weekLabel);
                weekDiv.appendChild(weekContent);

                days.forEach(dayKey => {
                    const dayData = history[year][monthKey][weekKey][dayKey];
                    const dayDiv = document.createElement('div');
                    dayDiv.className = 'history-day';

                    const dayLabel = document.createElement('div');
                    dayLabel.className = 'history-day-label';
                    dayLabel.textContent = '📅 ' + (dayData.label || dayKey) +
                        ' — ' + (dayData.entries || []).length + ' analisis';
                    dayDiv.appendChild(dayLabel);

                    (dayData.entries || []).forEach(entry => {
                        const entryEl = document.createElement('div');
                        entryEl.className = 'history-entry';

                        const time = entry.timestamp
                            ? new Date(entry.timestamp).toLocaleTimeString('es', {hour:'2-digit', minute:'2-digit'})
                            : '';

                        const intentEs = INTENT_ES[entry.intent] || entry.intent || '';
                        const sentEs   = SENTIMENT_ES[entry.sentiment] || entry.sentiment || '';
                        const srcClass = entry.source === 'audio' ? 'source-audio' : 'source-text';
                        const srcLabel = entry.source === 'audio' ? '&#127908; Audio' : '&#128221; Texto';

                        entryEl.innerHTML = `
                            <div class="history-entry-header">
                                <div class="history-entry-badges">
                                    <span class="source-badge ${srcClass}">${srcLabel}</span>
                                    <span class="badge badge-${entry.intent}" style="font-size:0.7rem;padding:2px 8px;">${intentEs}</span>
                                    <span class="badge badge-${entry.sentiment}" style="font-size:0.7rem;padding:2px 8px;">${sentEs}</span>
                                </div>
                                <span class="history-entry-time">${time}</span>
                            </div>
                            <div class="history-entry-text">${entry.text || ''}</div>
                            <div class="history-entry-detail" id="hdet-${entry.id}">
                                ${entry.audio_filename ? '<div style="font-size:0.72rem;color:#a35bf5;margin-bottom:4px;">&#127908; ' + entry.audio_filename + '</div>' : ''}
                                <div style="margin-bottom:4px;"><strong style="color:#888">Texto completo:</strong><br>${entry.text_full || entry.text || ''}</div>
                                ${entry.commercial ? '<div style="font-size:0.72rem;color:#666;">Prob. cierre: <strong style="color:#e0e0e0">' + (entry.commercial.probabilidad_cierre || 0).toFixed(1) + '%</strong> &nbsp;|&nbsp; Lead: <strong style="color:#e0e0e0">' + (entry.commercial.tipo_lead || '') + '</strong></div>' : ''}
                            </div>
                        `;

                        entryEl.onclick = () => {
                            const det = document.getElementById('hdet-' + entry.id);
                            if (det) det.classList.toggle('open');
                        };

                        dayDiv.appendChild(entryEl);
                    });

                    weekContent.appendChild(dayDiv);
                });

                monthContent.appendChild(weekDiv);
            });

            yearContent.appendChild(monthDiv);
        });

        container.appendChild(yearDiv);
    });
}
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

        .auth-card {
            background: #1a1d27;
            border: 1px solid #2a2d3a;
            border-radius: 12px;
            padding: 28px;
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
    return render_template_string(HTML, username=session["username"])


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

    # Prevent duplicate saves (same user + same text within 10 seconds)
    import hashlib
    _text_hash = hashlib.md5(f"{session['username']}:{clean_text[:200]}".encode()).hexdigest()
    _now_ts = __import__('time').time()
    if not hasattr(app, '_last_save_cache'):
        app._last_save_cache = {}
    if _text_hash in app._last_save_cache and (_now_ts - app._last_save_cache[_text_hash]) < 10:
        # Skip save, just return the analysis
        pass
    else:
        app._last_save_cache[_text_hash] = _now_ts
    _should_save = _text_hash not in app._last_save_cache or app._last_save_cache[_text_hash] == _now_ts

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

    # Only save if entry_name is provided (mandatory)
    if entry_name and _should_save:
        add_entry(
            username=session["username"],
            text=clean_text,
            analysis=analysis_dict,
            source="text",
            audio_filename=entry_name,
            year=year,
            month=month,
            entry_name=entry_name,
        )

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
    """Return entries filtered by year/month for the saved texts panel."""
    if not session.get("username"):
        return jsonify({"entries": []}), 401

    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    entries = get_flat_entries(session["username"], limit=200)

    # Filter by year/month — compare using timestamp if year/month fields missing
    filtered = []
    for e in entries:
        e_year = e.get("year")
        e_month = e.get("month")

        # Fallback: extract from timestamp string if year/month not set
        if e_year is None and e.get("timestamp"):
            try:
                from datetime import datetime as _dt
                ts = _dt.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
                e_year = ts.year
                e_month = ts.month
            except Exception:
                pass

        if e_year == year and e_month == month:
            filtered.append({
                "id": e.get("id", ""),
                "entry_name": e.get("entry_name", "") or e.get("audio_filename", ""),
                "text": (e.get("text", "") or "")[:60],
                "intent": e.get("intent", ""),
                "timestamp": e.get("timestamp", "")[:10],
                "source": e.get("source", ""),
            })

    return jsonify({"entries": filtered})


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

    entries = get_flat_entries(session["username"], limit=200)
    for e in entries:
        if e.get("id") == entry_id:
            return jsonify({"text": e.get("text_full", e.get("text", ""))})

    return jsonify({"text": ""}), 404


@app.route("/delete-entry/<entry_id>", methods=["DELETE"])
def delete_entry_route(entry_id):
    """Delete a saved entry by ID."""
    if not session.get("username"):
        return jsonify({"error": "unauthorized"}), 401

    from src.users.history_manager import delete_entry
    success = delete_entry(session["username"], entry_id)
    if success:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Entry not found"}), 404


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
    return jsonify({
        "ok": True,
        "whisper_available": audio_transcriber.is_available,
        "whisper_model": audio_transcriber.model_name,
        "analyzer_loaded": analyzer is not None,
        "sync_configured": _mpc_configured,
    })


@app.route("/admin/sync", methods=["POST"])
def admin_sync():
    """Dispara una sincronización manual (solo admin)."""
    if not session.get("username") or session["username"] != "admin":
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
    if not session.get("username") or session["username"] != "admin":
        return jsonify({"error": True, "error_message": "No autorizado"}), 403

    import json as _json
    log_file = os.path.join("config", "sync_log.json")
    if not os.path.exists(log_file):
        return jsonify([])
    with open(log_file, "r", encoding="utf-8") as f:
        return jsonify(_json.load(f))


@app.route("/debug-entries")
def debug_entries():
    """Temporary debug endpoint to see what's in the database for a user."""
    if not session.get("username"):
        return jsonify({"error": "not logged in"}), 401
    username = session["username"]
    entries = get_flat_entries(username, limit=10)
    # Return raw entry data for debugging
    debug_data = []
    for e in entries:
        debug_data.append({
            "id": e.get("id", "")[:20],
            "timestamp": e.get("timestamp", ""),
            "year": e.get("year"),
            "month": e.get("month"),
            "source": e.get("source", ""),
            "text_preview": (e.get("text", "") or "")[:50],
            "intent": e.get("intent", ""),
        })
    return jsonify({"username": username, "total_returned": len(entries), "entries": debug_data})


@app.route("/debug-sync-one")
def debug_sync_one():
    """
    Debug endpoint: cleans ALL entries for the logged-in user.
    """
    if not session.get("username"):
        return jsonify({"error": "not logged in"}), 401

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 50)
    print(f"  Abre tu navegador en: http://localhost:{port}")
    print("=" * 50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)
