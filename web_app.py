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

from flask import Flask, request, jsonify, render_template_string
from src.factory import create_analyzer
from src.models.data_models import AnalysisReport, AnalysisError

app = Flask(__name__)

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
    </style>
</head>
<body>
<div class="container">
    <h1>Analizador de Textos</h1>
    <p class="subtitle">Ventas y Bienes Raices &mdash; Analisis con Machine Learning</p>

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
        <div class="timestamp">Analizado el: ${data.analyzed_at}</div>
    `;
    el.style.display = 'block';
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


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/analyze", methods=["POST"])
def analyze():
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

    return jsonify({
        "error": False,
        "input_text": result.input_text,
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
        "analyzed_at": result.analyzed_at,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 50)
    print(f"  Abre tu navegador en: http://localhost:{port}")
    print("=" * 50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)
