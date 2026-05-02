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

# Load analyzer once at startup
print("Loading models...")
try:
    analyzer = create_analyzer()
    print("Models loaded successfully.")
except FileNotFoundError:
    print("Models not found. Training now...")
    import subprocess
    subprocess.run(["python", "-m", "src.training.train_models"], check=True)
    analyzer = create_analyzer()
    print("Models trained and loaded.")

# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analizador de Textos - Ventas y Bienes Raices</title>
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
            height: 130px;
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

        .empty-msg { color: #555; font-size: 0.85rem; font-style: italic; }

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
        <textarea id="textInput"
            placeholder="Escribe o pega aqui el texto que quieres analizar...&#10;&#10;Ejemplo: Ofrezco apartamento de 3 habitaciones en USD 180,000 negociable, zona norte, 95 m2."></textarea>
        <div class="btn-row">
            <button class="btn-primary" onclick="analyze()">Analizar</button>
            <button class="btn-secondary" onclick="clearAll()">Limpiar</button>
        </div>
        <div class="loading" id="loading">Analizando texto...</div>
    </div>

    <div class="results" id="results"></div>
</div>

<script>
async function analyze() {
    const text = document.getElementById('textInput').value.trim();
    if (!text) return;

    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const data = await response.json();
        renderResults(data, text);
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
    'bathrooms': 'Banos',
    'location': 'Ubicacion'
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
        entitiesHtml = data.entities.map(e => {
            let numStr = '';
            if (e.numeric_value !== null) {
                numStr = ` &rarr; <span class="entity-numeric">${e.numeric_value.toLocaleString()}${e.unit ? ' ' + e.unit : ''}</span>`;
            }
            return `<div class="entity-item">
                <div class="entity-concept">${translateConcept(e.concept, ENTITY_ES)}</div>
                <div class="entity-value">"${e.raw_value}"${numStr}</div>
            </div>`;
        }).join('');
    } else {
        entitiesHtml = '<span class="empty-msg">Ninguna detectada</span>';
    }

    el.innerHTML = `
        <div class="input-preview">"${preview}"</div>
        <div class="result-grid">
            <div class="card">
                <div class="card-title">Intencion del Texto</div>
                <span class="badge badge-${data.intent}">${intentEs}</span>
                ${confBar(data.intent_confidence)}
            </div>
            <div class="card">
                <div class="card-title">Sentimiento</div>
                <span class="badge badge-${data.sentiment}">${sentimentEs}</span>
                ${confBar(data.sentiment_confidence)}
            </div>
            <div class="card">
                <div class="card-title">Conceptos de Ventas Detectados</div>
                ${salesHtml}
            </div>
            <div class="card">
                <div class="card-title">Conceptos de Bienes Raices Detectados</div>
                ${reHtml}
            </div>
            <div class="card full-width">
                <div class="card-title">Datos Extraidos del Texto</div>
                ${entitiesHtml}
            </div>
        </div>
        ${renderCommercial(data.commercial)}
        <div class="timestamp">Analizado el: ${data.analyzed_at}</div>
    `;
    el.style.display = 'block';
}

function renderCommercial(c) {
    if (!c) return '';

    const pct = c.probabilidad_cierre;
    const fillClass = pct > 70 ? 'prob-fill-hot' : pct > 40 ? 'prob-fill-warm' : 'prob-fill-cold';

    const indicators = [
        { key: 'palabras_positivas',    label: 'Palabras Positivas',     value: c.palabras_positivas,    cls: c.palabras_positivas > 0 ? 'positive' : '' },
        { key: 'respuestas_afirmativas',label: 'Respuestas Afirmativas', value: c.respuestas_afirmativas, cls: c.respuestas_afirmativas > 0 ? 'positive' : '' },
        { key: 'indicios_cierre',       label: 'Indicios de Cierre',     value: c.indicios_cierre,       cls: c.indicios_cierre > 0 ? 'positive' : '' },
        { key: 'escasez_comercial',     label: 'Escasez Comercial',      value: c.escasez_comercial,     cls: '' },
        { key: 'pedidos_referidos',     label: 'Pedidos de Referidos',   value: c.pedidos_referidos,     cls: '' },
        { key: 'objeciones',            label: 'Objeciones',             value: c.objeciones,            cls: c.objeciones > 2 ? 'highlight' : '' },
        { key: 'indicios_prospeccion',  label: 'Prospeccion',            value: c.indicios_prospeccion,  cls: '' },
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
                    `<div class="detail-word-row">
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
                 onclick="toggleDetail('${detailId}', this)">
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
            Haz clic en cada indicador para ver el detalle de palabras detectadas.
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

    return `
        <div style="font-size:0.75rem; color:#666; margin-bottom:10px;">
            La probabilidad de cierre se calcula con esta formula:
            <br><code style="color:#4a6cf7; font-size:0.8rem;">(Indicios_Cierre x 5 + Respuestas_Afirm x 2 - Objeciones x 3) / Total_Palabras x 100</code>
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
    `;
}

function toggleLeadDetail(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    panel.classList.toggle('open');
}

function toggleDetail(detailId, cardEl) {
    const panel = document.getElementById(detailId);
    if (!panel) return;
    const isOpen = panel.classList.contains('open');
    panel.classList.toggle('open', !isOpen);
    cardEl.classList.toggle('expanded', !isOpen);
}

// Allow Ctrl+Enter to submit
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('textInput').addEventListener('keydown', e => {
        if (e.ctrlKey && e.key === 'Enter') analyze();
    });
});
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

    result = analyzer.analyze(data["text"])

    if isinstance(result, AnalysisError):
        return jsonify({
            "error": True,
            "error_code": result.error_code,
            "error_message": result.error_message
        })

    # Run commercial analysis in parallel
    ca = commercial_analyzer.analyze(data["text"])

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
        "commercial": {
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
            }
        }
    }

    # Save to history
    add_entry(
        username=session["username"],
        text=data["text"],
        analysis=analysis_dict,
        source="text",
    )

    return jsonify({
        "error": False,
        "input_text": result.input_text,
        "analyzed_at": result.analyzed_at,
        **analysis_dict,
    })


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
        "commercial": {
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
            }
        }
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 50)
    print(f"  Abre tu navegador en: http://localhost:{port}")
    print("=" * 50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)
