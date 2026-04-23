# Requirements Document

## Introduction

El **Analizador de Textos de Ventas y Bienes Raíces** es un sistema que procesa textos en lenguaje natural para identificar, clasificar y extraer conceptos clave relacionados con ventas y bienes raíces. El sistema detecta entidades relevantes (propiedades, precios, ubicaciones, condiciones de venta), evalúa el tono y la intención del texto, y genera un reporte estructurado con los hallazgos. El objetivo es proporcionar a agentes inmobiliarios, vendedores y analistas una herramienta que acelere la comprensión y clasificación de textos comerciales del sector.

**Análisis independiente por texto (stateless):** Cada texto se analiza de forma completamente autónoma. El sistema no mantiene estado entre análisis sucesivos, no compara textos entre sí ni acumula contexto de ejecuciones anteriores. Cada llamada a `analyze` produce un resultado basado exclusivamente en el texto proporcionado en esa invocación.

**Enfoque de Machine Learning:** Las clasificaciones de intención, sentimiento y extracción de conceptos se realizan mediante modelos de Machine Learning entrenados sobre el dominio de ventas y bienes raíces. El pipeline de ML incluye vectorización del texto (transformación a representaciones numéricas) antes de la inferencia. Las clasificaciones son probabilísticas y se expresan mediante Confidence_Scores. El sistema está diseñado para generalizar a textos no vistos durante el entrenamiento, siendo capaz de analizar cualquier texto arbitrario que se le proporcione en tiempo de ejecución. El sistema es extensible, permitiendo la actualización o reentrenamiento de modelos sin modificar la interfaz pública.

## Glossary

- **Analyzer**: El componente principal del sistema que orquesta el análisis de textos.
- **Text**: Cadena de caracteres en lenguaje natural que representa una descripción, anuncio, contrato o comunicación relacionada con ventas o bienes raíces.
- **Concept**: Término o entidad reconocida dentro del dominio de ventas y bienes raíces (e.g., precio, tipo de propiedad, ubicación, condición de venta).
- **Entity**: Instancia concreta de un Concept extraída de un Text (e.g., "USD 250,000", "apartamento", "Zona Norte").
- **Sales_Concept**: Subconjunto de Concepts relacionados con el proceso de venta (e.g., oferta, descuento, comisión, cierre, prospecto, objeción).
- **Real_Estate_Concept**: Subconjunto de Concepts relacionados con bienes raíces (e.g., tipo de propiedad, metraje, habitaciones, amenidades, zonificación).
- **Intent**: Clasificación de la intención principal del Text (e.g., `OFFER`, `INQUIRY`, `NEGOTIATION`, `CLOSING`, `DESCRIPTION`).
- **Sentiment**: Evaluación del tono del Text (`POSITIVE`, `NEUTRAL`, `NEGATIVE`).
- **Analysis_Report**: Documento estructurado generado por el Analyzer que contiene Entities, Intent, Sentiment y métricas derivadas del Text.
- **Confidence_Score**: Valor numérico entre 0.0 y 1.0 que indica la certeza del Analyzer sobre una clasificación o extracción.
- **Parser**: Componente que transforma el Text en una representación interna procesable.
- **Pretty_Printer**: Componente que serializa un Analysis_Report en un formato legible (JSON o texto plano).
- **Validator**: Componente que verifica que un Text de entrada cumple los requisitos mínimos para ser analizado.
- **ML_Model**: Modelo de Machine Learning entrenado sobre el dominio de ventas y bienes raíces, utilizado por el Analyzer para realizar clasificaciones probabilísticas de Intent, Sentiment y Concepts. Diseñado para generalizar a textos no vistos durante el entrenamiento.
- **Vectorizer**: Componente del pipeline de ML que transforma un Text en una representación numérica densa o dispersa (e.g., TF-IDF, embeddings) utilizable por los ML_Models para inferencia.
- **Model_Registry**: Componente que gestiona las versiones de los ML_Models disponibles y permite su actualización o sustitución sin modificar la interfaz pública del Analyzer.
- **Stateless_Analysis**: Propiedad del sistema que garantiza que cada análisis se realiza de forma completamente independiente, sin compartir estado ni contexto con análisis anteriores o posteriores.
- **Arbitrary_Text**: Cualquier Text válido proporcionado al Analyzer en tiempo de ejecución, incluyendo textos no vistos durante el entrenamiento de los ML_Models.

---

## Requirements

### Requirement 1: Validación de Entrada

**User Story:** Como desarrollador que integra el analizador, quiero que el sistema valide el texto de entrada antes de procesarlo, para que los errores de entrada sean detectados temprano y no produzcan resultados incorrectos.

#### Acceptance Criteria

1. WHEN a Text with fewer than 3 characters is provided, THE Validator SHALL return an error with the message `"Input text is too short to analyze"`.
2. WHEN a Text exceeding 50,000 characters is provided, THE Validator SHALL return an error with the message `"Input text exceeds maximum allowed length"`.
3. WHEN a Text consisting entirely of whitespace or control characters is provided, THE Validator SHALL return an error with the message `"Input text contains no analyzable content"`.
4. WHEN a valid Text is provided, THE Validator SHALL pass the Text to the Parser without modification.

---

### Requirement 2: Parseo de Texto

**User Story:** Como sistema interno, quiero que el texto sea transformado en una representación estructurada, para que los componentes de análisis puedan operar sobre unidades semánticas bien definidas.

#### Acceptance Criteria

1. WHEN a valid Text is provided, THE Parser SHALL tokenize the Text into a list of normalized tokens (lowercase, without leading/trailing whitespace).
2. WHEN a valid Text is provided, THE Parser SHALL segment the Text into sentences using punctuation boundaries (`.`, `!`, `?`).
3. THE Pretty_Printer SHALL serialize a parsed representation back into a Text string that preserves all original tokens.
4. FOR ALL valid Text inputs, parsing the Text then printing then parsing again SHALL produce a token list equivalent to the first parse (round-trip property).

---

### Requirement 3: Extracción de Conceptos de Ventas

**User Story:** Como agente de ventas, quiero que el sistema identifique conceptos clave del proceso de ventas en el texto, para que pueda evaluar rápidamente el estado y la oportunidad de una negociación.

#### Acceptance Criteria

1. WHEN a Text is analyzed, THE Analyzer SHALL identify all Sales_Concepts present, including at minimum: `offer`, `discount`, `commission`, `closing`, `prospect`, `objection`, `follow_up`, `negotiation`.
2. WHEN a Sales_Concept is identified, THE Analyzer SHALL assign a Confidence_Score between 0.0 and 1.0 to each identified Sales_Concept.
3. WHEN no Sales_Concepts are found in a Text, THE Analyzer SHALL return an empty list for the `sales_concepts` field in the Analysis_Report.
4. THE Analyzer SHALL recognize Sales_Concepts expressed as synonyms or related phrases (e.g., "precio final" → `closing`, "rebaja" → `discount`).

---

### Requirement 4: Extracción de Conceptos de Bienes Raíces

**User Story:** Como agente inmobiliario, quiero que el sistema identifique conceptos específicos de bienes raíces en el texto, para que pueda clasificar y comparar propiedades de forma eficiente.

#### Acceptance Criteria

1. WHEN a Text is analyzed, THE Analyzer SHALL identify Real_Estate_Concepts including at minimum: `property_type`, `price`, `area_sqm`, `bedrooms`, `bathrooms`, `location`, `amenities`, `zoning`, `condition`.
2. WHEN a numeric value associated with a Real_Estate_Concept is found (e.g., price, area, room count), THE Analyzer SHALL extract the numeric value and its unit as a structured Entity.
3. WHEN a location reference is found in the Text, THE Analyzer SHALL extract it as a `location` Entity with the raw text value preserved.
4. WHEN no Real_Estate_Concepts are found in a Text, THE Analyzer SHALL return an empty list for the `real_estate_concepts` field in the Analysis_Report.

---

### Requirement 5: Clasificación de Intención

**User Story:** Como analista de marketing, quiero conocer la intención principal del texto, para que pueda segmentar comunicaciones y priorizar respuestas.

#### Acceptance Criteria

1. WHEN a Text is analyzed, THE Analyzer SHALL classify the Intent as exactly one of: `OFFER`, `INQUIRY`, `NEGOTIATION`, `CLOSING`, `DESCRIPTION`, `UNKNOWN`.
2. WHEN the Analyzer assigns an Intent, THE Analyzer SHALL include a Confidence_Score for that Intent classification.
3. WHEN the Confidence_Score for all Intent categories is below 0.3, THE Analyzer SHALL assign the Intent value `UNKNOWN`.
4. WHEN a Text contains signals for multiple Intent categories, THE Analyzer SHALL assign the Intent with the highest Confidence_Score.

---

### Requirement 6: Análisis de Sentimiento

**User Story:** Como gerente de ventas, quiero conocer el tono emocional del texto, para que pueda identificar oportunidades o riesgos en las comunicaciones con clientes.

#### Acceptance Criteria

1. WHEN a Text is analyzed, THE Analyzer SHALL classify the Sentiment as exactly one of: `POSITIVE`, `NEUTRAL`, `NEGATIVE`.
2. WHEN the Analyzer assigns a Sentiment, THE Analyzer SHALL include a Confidence_Score for that Sentiment classification.
3. WHEN a Text contains no sentiment-bearing words, THE Analyzer SHALL assign the Sentiment value `NEUTRAL` with a Confidence_Score of 1.0.

---

### Requirement 7: Generación del Reporte de Análisis

**User Story:** Como usuario del sistema, quiero recibir un reporte estructurado con todos los resultados del análisis, para que pueda consumir los datos de forma programática o visual.

#### Acceptance Criteria

1. WHEN an analysis is completed, THE Analyzer SHALL produce an Analysis_Report containing: `input_text`, `intent`, `sentiment`, `sales_concepts`, `real_estate_concepts`, `entities`, and `analyzed_at` (ISO 8601 timestamp).
2. THE Pretty_Printer SHALL serialize an Analysis_Report to a valid JSON string.
3. THE Pretty_Printer SHALL serialize an Analysis_Report to a human-readable plain text summary.
4. FOR ALL valid Analysis_Report objects, serializing to JSON then deserializing then serializing again SHALL produce an identical JSON string (round-trip property).

---

### Requirement 8: Manejo de Errores

**User Story:** Como desarrollador que integra el analizador, quiero que todos los errores sean reportados de forma estructurada y descriptiva, para que pueda manejarlos correctamente en mi aplicación.

#### Acceptance Criteria

1. IF the Validator returns an error, THEN THE Analyzer SHALL propagate the error as a structured object containing `error_code` and `error_message` fields, without raising an unhandled exception.
2. IF an internal processing error occurs during analysis, THEN THE Analyzer SHALL return a structured error with `error_code: "ANALYSIS_ERROR"` and a descriptive `error_message`.
3. THE Analyzer SHALL complete analysis or return a structured error for every Text input; THE Analyzer SHALL never produce an unhandled exception visible to the caller.

---

### Requirement 9: Interfaz de Programación (API)

**User Story:** Como desarrollador, quiero una interfaz de programación clara y consistente para invocar el analizador, para que pueda integrarlo en cualquier aplicación sin ambigüedad.

#### Acceptance Criteria

1. THE Analyzer SHALL expose a function `analyze(text: str) -> AnalysisReport | AnalysisError` as its primary public interface.
2. WHEN `analyze` is called with a valid Text, THE Analyzer SHALL return an Analysis_Report object.
3. WHEN `analyze` is called with an invalid Text, THE Analyzer SHALL return an AnalysisError object.
4. THE Analyzer SHALL complete the analysis of a Text of up to 5,000 characters within 2 seconds on standard hardware.

---

### Requirement 10: Modelos de Machine Learning y Extensibilidad

**User Story:** Como administrador del sistema, quiero que las clasificaciones se realicen mediante modelos de Machine Learning y que el sistema permita actualizar o reentrenar esos modelos, para que el analizador mejore con el tiempo y se adapte a nuevos patrones del dominio sin interrumpir el servicio.

#### Acceptance Criteria

1. THE Analyzer SHALL use ML_Models to perform Intent classification, Sentiment classification, and Concept extraction, rather than relying exclusively on static rules or keyword lists.
2. WHEN the Analyzer produces a classification (Intent, Sentiment, or Concept), THE Analyzer SHALL derive the associated Confidence_Score from the probabilistic output of the ML_Model, not from a fixed value.
3. THE Analyzer SHALL pass each Text through the Vectorizer before inference, transforming the Text into a numerical representation compatible with the active ML_Models.
4. THE Model_Registry SHALL allow a new version of an ML_Model to be registered and activated without modifying the public `analyze` interface.
5. WHEN a new ML_Model version is activated in the Model_Registry, THE Analyzer SHALL use the new version for all subsequent analysis calls without requiring a system restart.
6. THE Model_Registry SHALL expose metadata for each registered ML_Model, including at minimum: `model_id`, `model_version`, `domain` (e.g., `"sales"`, `"real_estate"`), and `registered_at` (ISO 8601 timestamp).
7. WHEN an ML_Model fails to produce a classification for a given Text, THE Analyzer SHALL fall back to returning `UNKNOWN` for Intent, `NEUTRAL` for Sentiment, and an empty list for Concepts, with Confidence_Scores of 0.0, rather than raising an unhandled exception.

---

### Requirement 11: Independencia de Análisis (Stateless)

**User Story:** Como desarrollador que integra el analizador, quiero que cada análisis sea completamente independiente de los anteriores, para que los resultados de un texto no se vean afectados por textos procesados previamente y el sistema sea predecible y escalable.

#### Acceptance Criteria

1. THE Analyzer SHALL perform each analysis as a Stateless_Analysis: the output of `analyze(text)` SHALL depend exclusively on the content of the provided Text and the current ML_Models, with no dependency on previously analyzed texts.
2. WHEN `analyze` is called multiple times with the same Text and the same active ML_Models, THE Analyzer SHALL return Analysis_Reports with identical Intent, Sentiment, and Concept classifications on every call.
3. THE Analyzer SHALL NOT persist, accumulate, or share any intermediate state derived from a Text between separate calls to `analyze`.
4. WHEN two calls to `analyze` are made concurrently with different texts, THE Analyzer SHALL produce independent Analysis_Reports for each Text without cross-contamination of results.

---

### Requirement 12: Análisis de Textos Arbitrarios en Tiempo de Ejecución

**User Story:** Como usuario del sistema, quiero poder proporcionar cualquier texto nuevo en tiempo de ejecución y recibir un análisis completo, para que el sistema sea útil con textos no previstos durante el desarrollo o el entrenamiento.

#### Acceptance Criteria

1. WHEN an Arbitrary_Text is provided to `analyze` at runtime, THE Analyzer SHALL produce a complete Analysis_Report containing Intent, Sentiment, Sales_Concepts, Real_Estate_Concepts, and Entities, regardless of whether the Text was seen during ML_Model training.
2. WHEN an Arbitrary_Text contains domain vocabulary not present in the training data, THE Analyzer SHALL still return a valid Analysis_Report with the best available classifications and Confidence_Scores reflecting the uncertainty.
3. THE Analyzer SHALL accept Arbitrary_Text inputs in Spanish, English, or a mixture of both languages and produce a valid Analysis_Report for each.
4. WHEN an Arbitrary_Text is provided, THE Analyzer SHALL complete the full analysis pipeline (validation → parsing → vectorization → ML inference → report generation) and return the Analysis_Report in a single call to `analyze`.
5. THE Analyzer SHALL NOT require prior registration, indexing, or preprocessing of a Text before it can be analyzed; any valid Text SHALL be analyzable on first submission.
