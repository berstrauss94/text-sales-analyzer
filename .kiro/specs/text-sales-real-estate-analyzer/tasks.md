# Implementation Plan: Analizador de Textos de Ventas y Bienes Raíces

## Overview

Implementación incremental del pipeline de análisis de textos en Python con scikit-learn. Cada tarea construye sobre la anterior, comenzando por la estructura del proyecto y los modelos de datos, avanzando por los componentes del pipeline, el entrenamiento ML, los tests y finalizando con el script de demostración ejecutable.

## Tasks

- [x] 1. Estructura del proyecto y modelos de datos
  - Crear la estructura de directorios del proyecto: `src/`, `src/models/`, `src/components/`, `tests/`, `tests/unit/`, `tests/integration/`, `tests/smoke/`, `data/`
  - Crear `src/__init__.py`, `src/models/__init__.py`, `src/components/__init__.py`
  - Crear `src/models/data_models.py` con todos los dataclasses: `ValidationResult`, `ParsedText`, `IntentResult`, `SentimentResult`, `ConceptMatch`, `Entity`, `ConceptResult`, `AnalysisReport`, `AnalysisError`, `ModelMetadata`
  - Incluir métodos de fábrica `ValidationResult.success()` y `ValidationResult.failure()`
  - Crear `requirements.txt` con dependencias pinneadas: `scikit-learn==1.4.2`, `scipy==1.13.0`, `hypothesis==6.100.0`, `pytest==8.2.0`
  - _Requirements: 7.1, 8.1, 9.1, 10.6_

- [x] 2. Componente Validator
  - [x] 2.1 Implementar `src/components/validator.py` con la clase `Validator`
    - Constantes `MIN_LENGTH = 3` y `MAX_LENGTH = 50_000`
    - Método `validate(text: str) -> ValidationResult` con las cuatro reglas en orden: longitud mínima, longitud máxima, solo-whitespace, válido
    - Códigos de error: `INPUT_TOO_SHORT`, `INPUT_TOO_LONG`, `INPUT_EMPTY`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 2.2 Escribir property test para Validator — Property 1: Validación de longitud
    - **Property 1: Validación de longitud — rechazo de textos fuera de rango**
    - Usar `st.text(max_size=2)` y `st.text(min_size=50_001)` para generar textos fuera de rango
    - Verificar que `validate()` retorna `ok=False` con `error_code` no nulo
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 2.3 Escribir property test para Validator — Property 2: Rechazo whitespace
    - **Property 2: Rechazo de textos vacíos o solo-whitespace**
    - Usar `st.text(alphabet=st.sampled_from([" ", "\t", "\n", "\r"]), min_size=1)`
    - Verificar que `validate()` retorna `ok=False` y `error_code="INPUT_EMPTY"`
    - **Validates: Requirements 1.3**

  - [ ]* 2.4 Escribir property test para Validator — Property 3: Preservación en validación exitosa
    - **Property 3: Preservación del texto en validación exitosa**
    - Usar `st.text(min_size=3, max_size=5000).filter(lambda t: t.strip() != "")`
    - Verificar que el texto que llega al Parser es idéntico al original (sin modificaciones)
    - **Validates: Requirements 1.4**

- [x] 3. Componente Parser
  - [x] 3.1 Implementar `src/components/parser.py` con la clase `Parser`
    - Método `parse(text: str) -> ParsedText` siguiendo el algoritmo: strip, segmentar por `.!?`, tokenizar por espacios y puntuación no-sentencia, lowercase, filtrar vacíos
    - Método `print(parsed: ParsedText) -> str` que serializa de vuelta a string
    - Garantizar que `parse(print(parse(text))).tokens == parse(text).tokens`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 3.2 Escribir property test para Parser — Property 4: Normalización de tokens
    - **Property 4: Invariante de normalización de tokens**
    - Para cualquier texto válido, verificar que todos los tokens cumplen `token == token.strip().lower()`
    - **Validates: Requirements 2.1**

  - [ ]* 3.3 Escribir property test para Parser — Property 5: Round-trip de parseo
    - **Property 5: Round-trip de parseo**
    - Para cualquier texto válido `t`, verificar que `parse(print(parse(t))).tokens == parse(t).tokens`
    - **Validates: Requirements 2.3, 2.4**

- [ ] 4. Checkpoint — Validar componentes base
  - Asegurar que todos los tests de Validator y Parser pasan. Preguntar al usuario si hay dudas antes de continuar.

- [x] 5. Datos de entrenamiento y entrenamiento de modelos ML
  - [x] 5.1 Crear `data/training_data.py` con corpus de entrenamiento del dominio
    - Definir listas de textos etiquetados para intención: `OFFER`, `INQUIRY`, `NEGOTIATION`, `CLOSING`, `DESCRIPTION` (mínimo 20 ejemplos por clase, en español e inglés)
    - Definir listas de textos etiquetados para sentimiento: `POSITIVE`, `NEUTRAL`, `NEGATIVE` (mínimo 15 ejemplos por clase)
    - Definir listas de textos etiquetados para conceptos de ventas: `offer`, `discount`, `commission`, `closing`, `prospect`, `objection`, `follow_up`, `negotiation`
    - Definir listas de textos etiquetados para conceptos de bienes raíces: `property_type`, `price`, `area_sqm`, `bedrooms`, `bathrooms`, `location`, `amenities`, `zoning`, `condition`
    - Incluir sinónimos y frases relacionadas (e.g., `"precio final"` → `closing`, `"rebaja"` → `discount`)
    - _Requirements: 3.1, 3.4, 4.1, 5.1, 6.1, 10.1_

  - [x] 5.2 Crear `src/components/vectorizer.py` con la clase `Vectorizer`
    - Envolver `TfidfVectorizer` de scikit-learn con parámetros: `ngram_range=(1,2)`, `max_features=5000`, `sublinear_tf=True`
    - Método `fit(corpus: list[str]) -> None` para entrenamiento
    - Método `vectorize(parsed_text: ParsedText) -> FeatureVector` que llama `transform()` (nunca `fit_transform()` en inferencia)
    - _Requirements: 10.3_

  - [x] 5.3 Crear `src/training/train_models.py` con script de entrenamiento
    - Entrenar `TfidfVectorizer` sobre el corpus completo del dominio
    - Entrenar `LogisticRegression` para clasificación de intención (multi-clase, `max_iter=1000`)
    - Entrenar `LogisticRegression` para clasificación de sentimiento (multi-clase)
    - Entrenar `LogisticRegression` con `multi_class='ovr'` para extracción de conceptos de ventas (multi-label)
    - Entrenar `LogisticRegression` con `multi_class='ovr'` para extracción de conceptos de bienes raíces (multi-label)
    - Serializar todos los modelos con `joblib.dump()` en `models/` directory
    - Crear `src/training/__init__.py`
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 6. Clasificadores ML
  - [x] 6.1 Implementar `src/components/intent_classifier.py` con la clase `IntentClassifier`
    - Constantes `INTENTS` y `UNKNOWN_THRESHOLD = 0.3`
    - Método `predict(feature_vector: FeatureVector) -> IntentResult`
    - Lógica: `probabilities = model.predict_proba(fv)[0]`; si `max(probabilities) < 0.3` → `UNKNOWN, 0.0`; si no → `INTENTS[argmax], max_prob`
    - Manejo de excepciones internas con fallback a `IntentResult(intent="UNKNOWN", confidence=0.0)`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 10.2, 10.7_

  - [x] 6.2 Implementar `src/components/sentiment_classifier.py` con la clase `SentimentClassifier`
    - Constante `SENTIMENTS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]`
    - Método `predict(feature_vector: FeatureVector) -> SentimentResult`
    - Manejo de excepciones internas con fallback a `SentimentResult(sentiment="NEUTRAL", confidence=0.0)`
    - _Requirements: 6.1, 6.2, 6.3, 10.2, 10.7_

  - [x] 6.3 Implementar `src/components/concept_extractor.py` con la clase `ConceptExtractor`
    - Método `extract(feature_vector: FeatureVector, parsed_text: ParsedText) -> ConceptResult`
    - Clasificadores multi-label para `sales_concepts` y `real_estate_concepts` con confidence scores del modelo
    - Post-procesado con regex para extraer entidades numéricas: precios (`USD \d[\d,\.]*`), metrajes (`\d+\s*m2`), habitaciones (`\d+\s*(hab|cuartos|rooms|bedrooms)`)
    - Extracción de ubicaciones mediante lista de términos geográficos del dominio
    - Garantizar que `raw_value` de cada `Entity` sea subcadena del texto original
    - Manejo de excepciones con fallback a `ConceptResult([], [], [])`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 10.2, 10.7_

- [x] 7. ModelRegistry
  - [x] 7.1 Implementar `src/components/model_registry.py` con la clase `ModelRegistry`
    - Método `register(model, metadata: ModelMetadata) -> None` — registra sin activar
    - Método `activate(model_id: str, version: str) -> None` — activa atómicamente para inferencia
    - Método `get_active(domain: str) -> tuple[BaseEstimator, ModelMetadata]` — thread-safe por lectura atómica
    - Método `list_models() -> list[ModelMetadata]` — lista todos los modelos registrados
    - Lanzar `KeyError` si se solicita un dominio sin modelo activo
    - _Requirements: 10.4, 10.5, 10.6_

  - [ ]* 7.2 Escribir property test para ModelRegistry — Property 13: Metadatos completos
    - **Property 13: Independencia de metadatos del Model Registry**
    - Generar conjuntos arbitrarios de `ModelMetadata` y registrarlos
    - Verificar que `list_models()` retorna entradas con todos los campos requeridos no nulos: `model_id`, `model_version`, `domain`, `registered_at`
    - **Validates: Requirements 10.6**

- [x] 8. ReportBuilder y PrettyPrinter
  - [x] 8.1 Implementar `src/components/report_builder.py` con la clase `ReportBuilder`
    - Método `build(original_text, parsed_text, intent_result, sentiment_result, concept_result) -> AnalysisReport`
    - Generar timestamp `analyzed_at` en formato ISO 8601 UTC (`datetime.utcnow().isoformat() + "Z"`)
    - Poblar todos los campos del `AnalysisReport`; ningún campo debe ser `None`
    - _Requirements: 7.1, 12.1, 12.4_

  - [x] 8.2 Implementar `src/components/pretty_printer.py` con la clase `PrettyPrinter`
    - Método `to_json(report: AnalysisReport) -> str` — serialización JSON válida usando `dataclasses.asdict` + `json.dumps`
    - Método `from_json(json_str: str) -> AnalysisReport` — deserialización inversa exacta
    - Método `to_text(report: AnalysisReport) -> str` — resumen legible que incluye intent, sentiment, conceptos y entidades
    - _Requirements: 7.2, 7.3, 7.4_

  - [ ]* 8.3 Escribir property test para PrettyPrinter — Property 9: Round-trip JSON
    - **Property 9: Round-trip de serialización JSON del reporte**
    - Generar `AnalysisReport` arbitrarios con `st.builds(AnalysisReport, ...)`
    - Verificar que `to_json(from_json(to_json(r))) == to_json(r)`
    - **Validates: Requirements 7.2, 7.4**

- [ ] 9. Checkpoint — Validar componentes individuales
  - Asegurar que todos los tests unitarios y de propiedades pasan hasta este punto. Preguntar al usuario si hay dudas antes de continuar.

- [x] 10. Analyzer (orquestador principal)
  - [x] 10.1 Implementar `src/analyzer.py` con la clase `Analyzer`
    - Constructor `__init__(self, registry: ModelRegistry)` que instancia `Validator`, `Parser`, `ReportBuilder`, `PrettyPrinter`
    - Método `analyze(text: str) -> AnalysisReport | AnalysisError` con el pipeline completo:
      1. `Validator.validate(text)` → retornar `AnalysisError` si inválido
      2. `Parser.parse(text)` → `ParsedText`
      3. `registry.get_active("vectorizer")` → `Vectorizer`
      4. `Vectorizer.vectorize(parsed_text)` → `FeatureVector`
      5. `IntentClassifier.predict(fv)`, `SentimentClassifier.predict(fv)`, `ConceptExtractor.extract(fv, parsed)`
      6. `ReportBuilder.build(...)` → `AnalysisReport`
    - Bloque `try/except Exception` global que captura cualquier error y retorna `AnalysisError(error_code="ANALYSIS_ERROR", ...)`
    - Nunca lanzar excepciones al caller
    - _Requirements: 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 12.4, 12.5_

  - [x] 10.2 Crear `src/factory.py` con función `create_analyzer() -> Analyzer`
    - Cargar modelos serializados desde `models/` con `joblib.load()`
    - Instanciar y registrar `Vectorizer`, `IntentClassifier`, `SentimentClassifier`, `ConceptExtractor` en el `ModelRegistry`
    - Activar todos los modelos en el registry
    - Retornar `Analyzer` listo para usar
    - _Requirements: 10.4, 10.5, 12.5_

- [ ] 11. Tests de integración del pipeline completo
  - [ ] 11.1 Crear `tests/integration/test_analyzer_pipeline.py`
    - Property test 6: vocabulario de clasificaciones — verificar que `intent` ∈ `{"OFFER","INQUIRY","NEGOTIATION","CLOSING","DESCRIPTION","UNKNOWN"}` y `sentiment` ∈ `{"POSITIVE","NEUTRAL","NEGATIVE"}` para cualquier texto válido
    - Property test 7: confidence scores en [0,1] — verificar que `intent_confidence`, `sentiment_confidence` y todos los `ConceptMatch.confidence` están en `[0.0, 1.0]`
    - Property test 8: preservación de `raw_value` — verificar que cada `Entity.raw_value` es subcadena del texto original
    - Property test 10: estructura completa del reporte — verificar que todos los campos requeridos están presentes y no son `None`, y que `analyzed_at` es ISO 8601 válido
    - Property test 11: ausencia de excepciones — para cualquier string (incluyendo vacíos, muy largos, caracteres especiales), `analyze()` retorna `AnalysisReport` o `AnalysisError` sin lanzar excepción
    - Property test 12: determinismo y statelessness — `analyze(t)` múltiples veces produce `intent`, `sentiment` y conceptos idénticos; `analyze(tA), analyze(tB), analyze(tA)` produce resultados idénticos para `tA`
    - **Validates: Requirements 5.1, 6.1, 3.1, 4.1, 3.2, 5.2, 6.2, 10.2, 4.2, 4.3, 7.1, 12.1, 12.4, 8.1, 8.3, 12.2, 12.3, 11.1, 11.2, 11.3**

  - [ ] 11.2 Crear `tests/integration/test_performance.py`
    - Test de performance: `analyze()` sobre texto de 5,000 caracteres completa en < 2 segundos
    - _Requirements: 9.4_

  - [ ] 11.3 Crear `tests/integration/test_model_hotswap.py`
    - Test de hot-swap: registrar y activar modelo v2 en el registry, verificar que `analyze()` usa el nuevo modelo sin reinicio
    - _Requirements: 10.4, 10.5_

  - [ ] 11.4 Crear `tests/integration/test_concurrency.py`
    - Test de concurrencia: 10 llamadas concurrentes con textos distintos usando `concurrent.futures.ThreadPoolExecutor`
    - Verificar que cada resultado es independiente (sin cross-contamination)
    - _Requirements: 11.4_

- [ ] 12. Tests de ejemplo (unit tests)
  - [ ] 12.1 Crear `tests/unit/test_examples.py` con pruebas de ejemplo específicas
    - Test de sinónimos: `"precio final"` → concepto `closing`, `"rebaja"` → concepto `discount`
    - Test de umbral UNKNOWN: mock del modelo con todas las probabilidades < 0.3 → `intent = "UNKNOWN"`
    - Test de sentimiento NEUTRAL con confianza 1.0: texto factual sin carga emocional
    - Test de fallback de modelo: mock que lanza excepción → valores de fallback correctos (`UNKNOWN`, `NEUTRAL`, listas vacías)
    - Test de confidence derivada del modelo: mock con probabilidades conocidas → confidence scores coinciden exactamente
    - Test de `to_text()`: verificar que el output contiene intent y sentiment
    - _Requirements: 3.4, 5.3, 6.3, 10.2, 10.7, 7.3_

  - [ ] 12.2 Crear `tests/smoke/test_smoke.py` con pruebas de smoke
    - Verificar que `analyze` existe y tiene la firma correcta `(text: str) -> AnalysisReport | AnalysisError`
    - Verificar que el pipeline llama a `vectorizer.vectorize()` antes de `model.predict()` (usando mock/spy)
    - Verificar que `analyze()` con un texto nuevo retorna resultado válido sin setup previo
    - _Requirements: 9.1, 10.3, 12.5_

- [ ] 13. Checkpoint — Asegurar que todos los tests pasan
  - Ejecutar la suite completa de tests con `pytest tests/ -v`. Asegurar que todos los tests pasan. Preguntar al usuario si hay dudas antes de continuar.

- [ ] 14. Script de demostración ejecutable
  - [x] 14.1 Crear `demo.py` en la raíz del proyecto
    - Importar y usar `create_analyzer()` de `src/factory.py`
    - Demostrar análisis de al menos 5 textos de ejemplo: oferta en español, consulta en inglés, negociación mixta, texto con entidades numéricas (precio + metraje), texto inválido (muy corto)
    - Imprimir resultados con `PrettyPrinter.to_text()` y `PrettyPrinter.to_json()` para cada texto
    - Demostrar hot-swap de modelo: registrar modelo v2, activarlo, re-analizar un texto y mostrar que el resultado usa el nuevo modelo
    - El script debe ser ejecutable directamente con `python demo.py`
    - _Requirements: 9.1, 9.2, 9.3, 10.4, 10.5, 12.3_

  - [x] 14.2 Crear `README.md` con instrucciones de instalación y uso
    - Instrucciones de instalación: `pip install -r requirements.txt`
    - Instrucciones de entrenamiento: `python -m src.training.train_models`
    - Instrucciones de ejecución del demo: `python demo.py`
    - Instrucciones de ejecución de tests: `pytest tests/ -v`
    - _Requirements: 9.1_

- [x] 15. Checkpoint final — Verificación completa del sistema
  - Ejecutar `python -m src.training.train_models` para entrenar y serializar todos los modelos
  - Ejecutar `python demo.py` para verificar que el script de demostración funciona end-to-end
  - Ejecutar `pytest tests/ -v` para confirmar que todos los tests pasan
  - Asegurar que todos los tests pasan, preguntar al usuario si hay dudas.

## Notes

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido
- Cada tarea referencia requisitos específicos para trazabilidad
- Los checkpoints garantizan validación incremental antes de avanzar
- Los property tests usan Hypothesis con `@settings(max_examples=100)` mínimo
- Los unit tests cubren casos borde y comportamientos específicos del dominio
- El sistema es ejecutable directamente con Python estándar + scikit-learn, sin dependencias de GPU
- El `ModelRegistry` garantiza thread-safety mediante lectura atómica de referencias
- El `Analyzer` nunca propaga excepciones al caller; todos los errores se devuelven como `AnalysisError`
