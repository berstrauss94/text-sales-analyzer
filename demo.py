# -*- coding: utf-8 -*-
"""
Demo script for the text sales and real estate analyzer.

Demonstrates:
1. Analyzing 5 different texts (Spanish, English, mixed, numeric entities, invalid)
2. Output in plain text and JSON formats
3. Model hot-swap via ModelRegistry

Run with:
    python demo.py
"""
from __future__ import annotations

import sys
import os
import io

# Force UTF-8 output on Windows to avoid cp1252 encoding errors
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.factory import create_analyzer
from src.components.pretty_printer import PrettyPrinter
from src.models.data_models import AnalysisReport, AnalysisError


def print_result(result: AnalysisReport | AnalysisError, printer: PrettyPrinter) -> None:
    """Print analysis result in plain text and JSON formats."""
    if isinstance(result, AnalysisError):
        print(printer.error_to_text(result))
    else:
        print(printer.to_text(result))
        print("\n[JSON Output]")
        print(printer.to_json(result))


def main() -> None:
    printer = PrettyPrinter()
    sep = "=" * 60
    thin = "-" * 60

    print("\n" + sep)
    print("  ANALIZADOR DE TEXTOS - VENTAS Y BIENES RAICES")
    print(sep)

    # Load analyzer (requires trained models)
    print("\nCargando modelos...")
    try:
        analyzer = create_analyzer()
        print("Modelos cargados correctamente.\n")
    except FileNotFoundError as e:
        print(str(e))
        sys.exit(1)

    # -----------------------------------------------------------
    # Test texts
    # -----------------------------------------------------------
    texts = [
        # 1. Offer in Spanish with price entity
        (
            "1. Oferta en espanol con entidades numericas",
            "Ofrezco un hermoso apartamento de 3 habitaciones en la Zona Norte "
            "por USD 180,000 negociable. El inmueble tiene 95 m2, piscina y "
            "estacionamiento cubierto. Precio final a convenir."
        ),
        # 2. Inquiry in English
        (
            "2. Consulta en ingles",
            "I am interested in the 4-bedroom house listed downtown. "
            "Could you please send me more details about the asking price "
            "and whether the property includes a garage?"
        ),
        # 3. Negotiation mixed Spanish/English
        (
            "3. Negociacion mixta (espanol/ingles)",
            "Estoy dispuesto a subir mi oferta a 210,000 USD if you include "
            "the appliances and cover the closing costs. "
            "Podemos negociar los terminos del contrato."
        ),
        # 4. Description with multiple numeric entities
        (
            "4. Descripcion con multiples entidades",
            "Espectacular penthouse de 300 m2 en piso 20, con terraza privada, "
            "jacuzzi y vista panoramica. 4 habitaciones, 3 banos completos. "
            "Precio de lista: USD 450,000. Edificio con seguridad 24h y gimnasio."
        ),
        # 5. Invalid text (too short)
        (
            "5. Texto invalido (muy corto)",
            "Hi"
        ),
    ]

    for label, text in texts:
        print("\n" + thin)
        print("CASO: " + label)
        print(thin)
        result = analyzer.analyze(text)
        print_result(result, printer)

    # -----------------------------------------------------------
    # Demonstrate model hot-swap
    # -----------------------------------------------------------
    print("\n\n" + sep)
    print("  DEMOSTRACION: HOT-SWAP DE MODELO")
    print(sep)

    from src.components.intent_classifier import IntentClassifier
    from src.models.data_models import ModelMetadata
    from datetime import datetime, timezone
    import joblib

    models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        # Load same model as "v2" to simulate a new version
        intent_clf_v2 = joblib.load(os.path.join(models_dir, "intent_classifier.joblib"))
        intent_classes_v2 = joblib.load(os.path.join(models_dir, "intent_classes.joblib"))
        intent_v2 = IntentClassifier(model=intent_clf_v2, classes=intent_classes_v2)

        registry = analyzer._registry
        registry.register(
            intent_v2,
            ModelMetadata(
                model_id="intent-v2",
                model_version="2.0.0",
                domain="intent",
                registered_at=now,
            ),
        )
        registry.activate("intent-v2", "2.0.0")

        print("\nModelo de intencion actualizado a v2.0.0")
        print("Modelos registrados:")
        for meta in registry.list_models():
            status = "ACTIVO" if meta.is_active else "inactivo"
            print("  - " + meta.model_id + " v" + meta.model_version +
                  " [" + meta.domain + "] - " + status)

        test_text = "Ofrezco la propiedad en USD 200,000, precio negociable."
        print("\nRe-analizando con modelo v2:")
        print("Texto: " + test_text)
        result = analyzer.analyze(test_text)
        print_result(result, printer)

    except Exception as e:
        print("Hot-swap demo error: " + str(e))

    print("\n" + sep)
    print("  Demo completado exitosamente.")
    print(sep + "\n")


if __name__ == "__main__":
    main()
