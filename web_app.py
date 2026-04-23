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
from src.components.commercial_analyzer import CommercialAnalyzer
from src.models.data_models import AnalysisReport, AnalysisError

app = Flask(__name__)
commercial_analyzer = CommercialAnalyzer()

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
        { label: 'Palabras Positivas', value: c.palabras_positivas, cls: c.palabras_positivas > 0 ? 'positive' : '' },
        { label: 'Respuestas Afirmativas', value: c.respuestas_afirmativas, cls: c.respuestas_afirmativas > 0 ? 'positive' : '' },
        { label: 'Indicios de Cierre', value: c.indicios_cierre, cls: c.indicios_cierre > 0 ? 'positive' : '' },
        { label: 'Escasez Comercial', value: c.escasez_comercial, cls: '' },
        { label: 'Pedidos de Referidos', value: c.pedidos_referidos, cls: '' },
        { label: 'Objeciones', value: c.objeciones, cls: c.objeciones > 2 ? 'highlight' : '' },
        { label: 'Prospeccion', value: c.indicios_prospeccion, cls: '' },
    ];

    const indicatorsHtml = indicators.map(i =>
        `<div class="indicator-item">
            <div class="indicator-label">${i.label}</div>
            <div class="indicator-value ${i.cls}">${i.value}</div>
        </div>`
    ).join('');

    return `
    <div class="commercial-section">
        <div class="commercial-title">Analisis Comercial Inmobiliario</div>

        <div style="display:flex; align-items:center; gap:16px; margin-bottom:16px; flex-wrap:wrap;">
            <span class="lead-badge lead-${c.tipo_lead}">LEAD ${c.tipo_lead}</span>
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

        <div class="indicators-grid">${indicatorsHtml}</div>

        <div style="font-size:0.75rem; color:#555; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.06em;">Recomendacion</div>
        <div class="recomendacion-box">${c.recomendacion}</div>

        <div style="font-size:0.7rem; color:#444; margin-top:10px; text-align:right;">
            Densidad comercial: ${c.densidad_comercial.toFixed(4)} &nbsp;|&nbsp; Total palabras: ${c.total_palabras}
        </div>
    </div>`;
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

    # Run commercial analysis in parallel
    ca = commercial_analyzer.analyze(data["text"])

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
        }
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 50)
    print(f"  Abre tu navegador en: http://localhost:{port}")
    print("=" * 50 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)
