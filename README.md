# Analizador de Textos — Ventas y Bienes Raíces

Analiza textos en lenguaje natural (español, inglés o mixto) relacionados con ventas y bienes raíces. Cada texto se analiza de forma completamente independiente usando modelos de Machine Learning.

## Qué hace

Para cada texto recibido, el sistema produce:

- **Intención**: OFFER, INQUIRY, NEGOTIATION, CLOSING, DESCRIPTION, UNKNOWN
- **Sentimiento**: POSITIVE, NEUTRAL, NEGATIVE
- **Conceptos de ventas**: oferta, descuento, comisión, cierre, prospecto, objeción, seguimiento, negociación
- **Conceptos de bienes raíces**: tipo de propiedad, precio, metraje, habitaciones, baños, ubicación, amenidades, zonificación, condición
- **Entidades extraídas**: precios (USD 180,000), metrajes (95 m2), habitaciones (3 habitaciones), ubicaciones

## Requisitos

- Python 3.10 o superior
- pip

## Instalación

```bash
pip install -r requirements.txt
```

## Entrenamiento de modelos

Antes de usar el analizador, entrena los modelos ML:

```bash
python -m src.training.train_models
```

Esto crea los archivos de modelos en la carpeta `models/`.

## Ejecutar el demo

```bash
python demo.py
```

El demo analiza 5 textos de ejemplo y muestra los resultados en texto plano y JSON.

## Uso en código

```python
from src.factory import create_analyzer
from src.components.pretty_printer import PrettyPrinter
from src.models.data_models import AnalysisReport, AnalysisError

# Crear el analizador (carga los modelos entrenados)
analyzer = create_analyzer()
printer = PrettyPrinter()

# Analizar cualquier texto
text = "Ofrezco apartamento de 3 habitaciones en USD 180,000, negociable."
result = analyzer.analyze(text)

if isinstance(result, AnalysisReport):
    print(printer.to_text(result))   # Texto legible
    print(printer.to_json(result))   # JSON estructurado
else:
    print(f"Error: {result.error_message}")
```

## Ejecutar tests

```bash
pytest tests/ -v
```

## Estructura del proyecto

```
├── data/
│   └── training_data.py        # Corpus de entrenamiento etiquetado
├── models/                     # Modelos serializados (generados al entrenar)
├── src/
│   ├── analyzer.py             # Orquestador principal
│   ├── factory.py              # Crea el Analyzer listo para usar
│   ├── components/
│   │   ├── validator.py        # Valida el texto de entrada
│   │   ├── parser.py           # Tokeniza y segmenta el texto
│   │   ├── vectorizer.py       # TF-IDF vectorization
│   │   ├── intent_classifier.py
│   │   ├── sentiment_classifier.py
│   │   ├── concept_extractor.py
│   │   ├── model_registry.py   # Gestión de versiones de modelos
│   │   ├── report_builder.py   # Ensambla el reporte final
│   │   └── pretty_printer.py   # Serializa a JSON o texto plano
│   ├── models/
│   │   └── data_models.py      # Dataclasses del sistema
│   └── training/
│       └── train_models.py     # Script de entrenamiento
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
├── demo.py                     # Script de demostración ejecutable
├── requirements.txt
└── README.md
```

## Notas

- Cada análisis es completamente independiente (stateless). Los resultados de un texto no afectan a los demás.
- El sistema acepta textos en español, inglés o mezcla de ambos.
- Los modelos pueden actualizarse sin reiniciar el sistema (hot-swap via ModelRegistry).
- Para agregar más datos de entrenamiento, edita `data/training_data.py` y vuelve a ejecutar el script de entrenamiento.
