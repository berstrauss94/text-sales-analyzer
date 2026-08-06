# Requirements Document

## Introduction

El **Filtro Contextual de Palabras Clave** es un motor NLP/ML que mejora el sistema de análisis comercial existente (`commercial_analyzer.py`) incorporando sensibilidad al contexto conversacional y distinción por rol de hablante (Vendedor vs. Cliente). El sistema actual cuenta indicadores comerciales de forma global sin distinguir quién habla ni si una palabra clave se usa como respuesta directa o como parte incrustada de una oración mayor. Este nuevo componente resuelve tres problemas fundamentales: (1) filtrado contextual que descarta palabras clave embebidas en cláusulas mayores y solo registra respuestas directas, (2) asignación de métricas por rol con conteo de frecuencias por categoría para cada participante, y (3) corrección automática de roles invertidos cuando la transcripción atribuye lenguaje de vendedor al cliente o viceversa.

**Compatibilidad:** El sistema mantiene retrocompatibilidad total con el esquema de evaluación existente. Los endpoints de carga de texto (`loadSavedTexts`) y la interfaz de guardado no se modifican. Toda modificación al esquema de evaluación se valida mediante dry-run previo.

**Categorías objetivo:** 7 categorías de indicadores comerciales: Positivas, Afirmativas, Cierre, Escasez, Referidos, Objeciones, Prospección.

## Glossary

- **Filtro_Contextual**: Componente NLP que evalúa si una palabra clave aparece como respuesta directa independiente o como parte embebida de una cláusula mayor.
- **Respuesta_Directa**: Token o frase corta (4 palabras o menos) que constituye una respuesta autónoma del hablante a un prompt anterior, delimitada por signos de puntuación, inicio/fin de turno, o separadores de oración.
- **Palabra_Embebida**: Palabra clave que aparece como parte subordinada dentro de una cláusula mayor (más de 4 palabras), sin constituir una respuesta independiente del hablante.
- **Rol_Hablante**: Etiqueta asignada a cada segmento del transcrito que identifica al participante como Vendedor, Cliente, o Desconocido.
- **Vendedor**: Participante que ofrece, presenta o promueve un producto/servicio inmobiliario.
- **Cliente**: Participante que evalúa, pregunta, objeta o acepta una propuesta inmobiliaria.
- **Categoría_Métrica**: Una de las 7 clasificaciones de indicadores comerciales: Positivas, Afirmativas, Cierre, Escasez, Referidos, Objeciones, Prospección.
- **Asignación_Por_Rol**: Regla que define qué Categorías_Métricas se contabilizan para cada Rol_Hablante (Vendedor: Positivas, Afirmativas, Cierre, Prospección, Referidos; Cliente: Positivas, Afirmativas, Objeciones).
- **Frecuencia_Categoría**: Conteo numérico entero (≥0) de ocurrencias válidas de una Categoría_Métrica para un participante específico.
- **Inversión_De_Rol**: Corrección automática que reasigna un segmento del transcrito al Rol_Hablante correcto cuando el análisis semántico detecta que el lenguaje atribuido no corresponde al rol etiquetado.
- **Segmento_Diálogo**: Bloque continuo de texto atribuido a un mismo Rol_Hablante, delimitado por cambio de turno o etiqueta de rol.
- **Ajuste_Semántico**: Valor numérico entre 0.0 y 1.0 calculado como la proporción de keywords de rol contrario respecto al total de keywords en el segmento.
- **Dry_Run**: Ejecución de validación que simula cambios al esquema de evaluación sin aplicarlos, reportando diferencias y posibles incompatibilidades.
- **Transcripción**: Texto de una conversación de ventas inmobiliarias con etiquetas de rol (e.g., "Vendedor:", "Cliente:") que identifica turnos de habla.

## Requirements

### Requirement 1: Detección de Respuesta Directa vs. Palabra Embebida

**User Story:** Como analista de ventas, quiero que el sistema distinga entre palabras clave usadas como respuestas directas y palabras embebidas en cláusulas mayores, para que los conteos reflejen únicamente reacciones genuinas del interlocutor.

#### Acceptance Criteria

1. WHEN a keyword from any Categoría_Métrica appears as a standalone utterance of 4 words or fewer within a single Segmento_Diálogo, delimited by sentence boundaries (`.`, `!`, `?`), turn start, turn end, or comma followed by end of turn, THE Filtro_Contextual SHALL classify the keyword as Respuesta_Directa and increment the corresponding Frecuencia_Categoría by 1.
2. WHEN a keyword from any Categoría_Métrica appears as part of a clause containing more than 4 words, or is syntactically subordinate within a larger sentence (preceded by conjunctions such as "que", "porque", "aunque", "si bien", or embedded between subject and verb of an independent clause), THE Filtro_Contextual SHALL classify the keyword as Palabra_Embebida and exclude the keyword from the Frecuencia_Categoría count.
3. WHEN the keyword "Sí" appears within the same Segmento_Diálogo as a continuation clause that extends the turn beyond a standalone affirmation (i.e., the turn contains more than 4 words after "Sí" excluding filler words), THE Filtro_Contextual SHALL classify the occurrence as Palabra_Embebida and not count it as an affirmative response.
4. WHEN the keyword "Sí" appears as the sole substantive content of a Cliente Segmento_Diálogo (with at most trailing punctuation or filler words such as "sí", "claro", "ok") immediately following a Vendedor Segmento_Diálogo, THE Filtro_Contextual SHALL classify the occurrence as Respuesta_Directa and count it as an affirmative response.
5. THE Filtro_Contextual SHALL apply the Respuesta_Directa vs. Palabra_Embebida classification to all 7 Categoría_Métrica groups (Positivas, Afirmativas, Cierre, Escasez, Referidos, Objeciones, Prospección) using the same sentence boundary and token-count threshold rules defined in criteria 1 and 2.
6. IF the Filtro_Contextual cannot determine whether a keyword occurrence is Respuesta_Directa or Palabra_Embebida (e.g., due to missing punctuation or ambiguous turn boundaries), THEN THE Filtro_Contextual SHALL classify the occurrence as Palabra_Embebida and exclude it from Frecuencia_Categoría, preserving a conservative count.

### Requirement 2: Categorización de Tokens en 7 Categorías

**User Story:** Como analista de ventas, quiero que cada token de habla relevante se clasifique en una de las 7 categorías comerciales, para tener visibilidad granular del comportamiento comunicativo de cada participante.

#### Acceptance Criteria

1. THE Filtro_Contextual SHALL classify detected speech tokens into exactly 7 target categories: Positivas, Afirmativas, Cierre, Escasez, Referidos, Objeciones, Prospección.
2. WHEN a token matches keywords from the existing `training_data.py` keyword lists, THE Filtro_Contextual SHALL use those keyword definitions as the primary classification source.
3. WHEN a token does not match any category, THE Filtro_Contextual SHALL exclude the token from all Frecuencia_Categoría counts without generating an error.
4. THE Filtro_Contextual SHALL produce a frequency count dictionary with the structure `{rol: {categoría: count}}` for each analyzed Transcripción.

### Requirement 3: Asignación de Categorías Permitidas por Rol

**User Story:** Como coordinador de ventas, quiero que las métricas se filtren según el rol del hablante, para que cada participante solo acumule indicadores relevantes a su función en la conversación.

#### Acceptance Criteria

1. WHILE the Rol_Hablante is Vendedor, THE Filtro_Contextual SHALL count metrics only for the categories: Positivas, Afirmativas, Cierre, Prospección, Referidos, and SHALL initialize each of these categories with a Frecuencia_Categoría of 0 before processing.
2. WHILE the Rol_Hablante is Cliente, THE Filtro_Contextual SHALL count metrics only for the categories: Positivas, Afirmativas, Objeciones, and SHALL initialize each of these categories with a Frecuencia_Categoría of 0 before processing.
3. WHEN a keyword matching a category not allowed for the current Rol_Hablante is detected (including Escasez keywords for both roles), THE Filtro_Contextual SHALL exclude the match from that rol's frequency counts and SHALL NOT include the discarded match in any per-role totals.
4. THE Filtro_Contextual SHALL output separate frequency count reports for Vendedor and Cliente within the same Analysis_Report, each containing all allowed categories for that rol with their corresponding Frecuencia_Categoría values (including categories with a count of 0).
5. WHEN a keyword matching the Escasez category is detected in any Segmento_Diálogo, THE Filtro_Contextual SHALL exclude the match from both Vendedor and Cliente per-role frequency counts since Escasez is not assigned to either role, but SHALL include it in the global total count for backward compatibility.

### Requirement 4: Conteo de Frecuencias por Categoría y Participante

**User Story:** Como analista de ventas, quiero obtener el conteo exacto de ocurrencias por categoría para cada participante, para poder comparar el rendimiento comunicativo entre vendedor y cliente.

#### Acceptance Criteria

1. WHEN a Transcripción is analyzed, THE Filtro_Contextual SHALL produce a frequency table containing one row per participante with columns for each Categoría_Métrica allowed to that rol.
2. THE Filtro_Contextual SHALL count each valid keyword occurrence (classified as Respuesta_Directa) exactly once, without double-counting across categories.
3. WHEN a Transcripción contains no role labels ("Vendedor:" or "Cliente:"), THE Filtro_Contextual SHALL fall back to global counting behavior compatible with the existing CommercialAnalyzer output format.
4. FOR ALL valid Transcripciones, the sum of per-role frequency counts for a given category SHALL equal the total valid occurrences of that category detected in the full text when roles are correctly assigned.

### Requirement 5: Corrección Dinámica de Inversión de Roles

**User Story:** Como coordinador de ventas, quiero que el sistema detecte y corrija automáticamente roles invertidos en la transcripción, para que métricas no se distorsionen por errores de transcripción.

#### Acceptance Criteria

1. WHEN a Segmento_Diálogo labeled as Cliente contains 2 or more keywords from Vendedor-characteristic categories (Cierre, Prospección, Escasez, Referidos) within the same segment, THE Filtro_Contextual SHALL flag the segment as candidate for Inversión_De_Rol.
2. WHEN a Segmento_Diálogo labeled as Vendedor contains 2 or more keywords from Cliente-characteristic categories (Objeciones) or hesitation patterns (defined as: phrases expressing doubt such as "no sé", "tengo que pensarlo", "no estoy seguro", "me parece caro", "es mucho", "no puedo", or temporal hedging such as "después veo", "luego te confirmo", "dejame pensarlo") within the same segment, THE Filtro_Contextual SHALL flag the segment as candidate for Inversión_De_Rol.
3. WHEN a segment is flagged for Inversión_De_Rol and the Ajuste_Semántico confidence exceeds 0.7 on a scale of 0.0 to 1.0 (calculated as the ratio of mismatched-role keywords to total keywords in the segment), THE Filtro_Contextual SHALL invert the Rol_Hablante for that Segmento_Diálogo before computing frequency counts.
4. WHEN a segment is flagged for Inversión_De_Rol but the Ajuste_Semántico confidence is 0.7 or below, THE Filtro_Contextual SHALL retain the original Rol_Hablante assignment and include the segment in a warnings list containing: segment index, original role, confidence score, and detected mismatched keywords.
5. THE Filtro_Contextual SHALL log all Inversión_De_Rol corrections as a list of objects containing: original_role, corrected_role, segment_text (first 100 characters), confidence_score, and list of triggering keywords.
6. WHEN a Segmento_Diálogo contains keywords characteristic of BOTH roles in similar quantities (difference of 1 or fewer between Vendedor-characteristic and Cliente-characteristic keyword counts), THE Filtro_Contextual SHALL retain the original Rol_Hablante and add the segment to the warnings list as ambiguous.
7. IF a flagged Segmento_Diálogo contains 0 total category keywords (making the confidence ratio undefined), THEN THE Filtro_Contextual SHALL retain the original Rol_Hablante without flagging and exclude the segment from Inversión_De_Rol processing.

### Requirement 6: Validación Dry-Run de Cambios al Esquema

**User Story:** Como desarrollador, quiero ejecutar validaciones dry-run antes de aplicar cambios al esquema de evaluación, para garantizar retrocompatibilidad y evitar regresiones en producción.

#### Acceptance Criteria

1. WHEN a modification to the evaluation schema or state components is proposed, THE Filtro_Contextual SHALL execute a Dry_Run that compares the output of the new logic against the existing CommercialAnalyzer output for a set of reference texts.
2. WHEN the Dry_Run detects a field removal or type change in the output schema, THE Filtro_Contextual SHALL report the incompatibility and block the modification.
3. WHEN the Dry_Run completes without incompatibilities, THE Filtro_Contextual SHALL produce a diff report showing added fields and value changes.
4. THE Filtro_Contextual SHALL preserve all existing fields of CommercialAnalysis (palabras_positivas, respuestas_afirmativas, indicios_cierre, escasez_comercial, pedidos_referidos, objeciones, indicios_prospeccion) in their current format and semantics.

### Requirement 7: Restricciones de Integración y Despliegue

**User Story:** Como desarrollador, quiero que el nuevo componente se integre sin afectar endpoints existentes ni romper el flujo de despliegue, para mantener estabilidad del sistema en producción.

#### Acceptance Criteria

1. THE Filtro_Contextual SHALL not modify the `loadSavedTexts` endpoint nor any text loading endpoint of the web application.
2. THE Filtro_Contextual SHALL validate all JavaScript frontend changes using `node --check` before deployment.
3. THE Filtro_Contextual SHALL maintain compatibility with the existing PostgreSQL schema containing 438+ entries from 8 users.
4. WHEN the Filtro_Contextual is deployed, THE system SHALL auto-deploy on push to master branch without manual intervention.
5. IF a Dry_Run validation fails during deployment, THEN THE system SHALL abort the deployment and report the failure reason.

### Requirement 8: Parseo de Transcripción con Roles

**User Story:** Como sistema interno, quiero parsear transcripciones separando el texto por roles de hablante, para que el filtrado contextual opere sobre segmentos correctamente atribuidos.

#### Acceptance Criteria

1. WHEN a Transcripción contains role labels matching the pattern of "Vendedor" or "Cliente" appearing at the start of a line (optionally followed by ":"), THE Parser SHALL segment the text into a list of Segmento_Diálogo objects, each containing the Rol_Hablante ("Vendedor" or "Cliente") and the content text that follows until the next role label or end of input.
2. WHEN a Transcripción contains no recognized role labels on any line, THE Parser SHALL treat the entire text as a single Segmento_Diálogo with Rol_Hablante set to "Desconocido".
3. WHEN a Transcripción contains text preceding the first recognized role label, THE Parser SHALL include that text as an initial Segmento_Diálogo with Rol_Hablante set to "Desconocido".
4. THE Pretty_Printer SHALL format a list of Segmento_Diálogo objects back into a Transcripción string by concatenating each segment's Rol_Hablante label followed by a newline and its content, preserving the original role label format and content including any embedded timestamps.
5. FOR ALL valid Transcripciones with role labels, parsing then printing then parsing again SHALL produce a Segmento_Diálogo list with the same number of segments, identical Rol_Hablante values, and identical content strings as the first parse (round-trip property).
