# Requirements Document

## Introduction

Este documento define los requisitos para dos mejoras relacionadas al analizador de textos de ventas inmobiliarias:

1. **Acordeones expandibles en el Informe de Texto** (`renderTextReport`): Cada métrica del informe (Intención, Sentimiento, Lead, Etapa, etc.) tendrá una flecha ▼ que al expandirse mostrará argumentación detallada y fragmentos de texto fuente que justifican el resultado.

2. **Sistema de aprendizaje/sugerencias**: Utilizando los datos históricos almacenados en PostgreSQL (438+ entradas, 8 usuarios), el sistema generará sugerencias contextuales para el vendedor basadas en patrones previos exitosos.

### Restricciones del proyecto

- Se trabaja directamente en la rama `master`
- Railway realiza auto-deploy al hacer push a `master`
- Validar JS con `node --check` antes de cada push
- NO se debe modificar `loadSavedTexts` ni los endpoints de carga de textos
- Base de datos: PostgreSQL en `yamanote.proxy.rlwy.net:20022`

## Glossary

- **Informe_de_Texto**: Panel de resultados renderizado por la función `renderTextReport` que muestra el resumen del análisis de un texto (intención, sentimiento, lead, etapa, indicadores comerciales, conceptos, etc.)
- **Acordeón**: Componente UI colapsable que muestra un encabezado con flecha ▼/▲ y al hacer clic expande su contenido detallado
- **Métrica**: Cada indicador individual del informe (Intención, Sentimiento, Lead, Prob. Cierre, Etapa, Urgencia, Indicadores comerciales, Conceptos de venta, Conceptos inmobiliarios)
- **Fragmento_Fuente**: Porción del texto original analizado que justifica o evidencia la clasificación de una métrica
- **Argumentación**: Explicación textual generada que detalla por qué el sistema asignó determinado valor a una métrica
- **Sistema_de_Aprendizaje**: Módulo backend que consulta datos históricos en PostgreSQL para generar sugerencias contextuales al vendedor
- **Sugerencia_Contextual**: Recomendación específica basada en patrones históricos similares (textos con métricas parecidas que resultaron en cierres exitosos u otras acciones)
- **Historial_PostgreSQL**: Tabla de entradas de análisis almacenadas en PostgreSQL con 438+ registros de 8 usuarios, conteniendo texto analizado, resultados del análisis y metadatos
- **Patrón_Exitoso**: Combinación de métricas y acciones que en el historial resultaron en avance del lead (ej. paso de FRÍO a TIBIO, o cierre de venta)
- **Commercial_Analyzer**: Componente (`CommercialAnalyzer`) que calcula indicadores comerciales avanzados como probabilidad de cierre, etapa de funnel, señales de compra, etc.
- **Confidence_Score**: Valor numérico entre 0.0 y 1.0 que indica el nivel de certeza del clasificador en su resultado

## Requirements

### Requirement 1: Acordeones expandibles en métricas del informe

**User Story:** Como vendedor, quiero expandir cada métrica del informe para ver la argumentación detallada y los fragmentos del texto que justifican la clasificación, para entender mejor el análisis y tomar decisiones informadas.

#### Acceptance Criteria

1. WHEN el usuario visualiza el Informe_de_Texto, THE Informe_de_Texto SHALL renderizar cada Métrica con una flecha ▼ clickeable a la derecha del valor
2. WHEN el usuario hace clic en la flecha ▼ de una Métrica, THE Acordeón SHALL expandirse mostrando la Argumentación y los Fragmento_Fuente asociados a esa Métrica, sin colapsar los demás Acordeones que estén abiertos
3. WHEN el Acordeón de una Métrica está expandido, THE Informe_de_Texto SHALL mostrar la flecha como ▲ indicando que se puede colapsar
4. WHEN el usuario hace clic en la flecha ▲ de una Métrica expandida, THE Acordeón SHALL colapsarse ocultando la Argumentación y los Fragmento_Fuente
5. THE Informe_de_Texto SHALL renderizar todos los Acordeones en estado colapsado por defecto al cargar un nuevo análisis
6. WHEN el Acordeón de Intención está expandido, THE Argumentación SHALL mostrar la confianza del clasificador como Confidence_Score, las palabras clave que influyeron en la decisión, y el Fragmento_Fuente relevante del texto original
7. WHEN el Acordeón de Sentimiento está expandido, THE Argumentación SHALL mostrar la confianza del clasificador como Confidence_Score, indicadores de tono detectados (palabras positivas/negativas), y el Fragmento_Fuente relevante
8. WHEN el Acordeón de Lead está expandido, THE Argumentación SHALL mostrar la fórmula de cálculo con puntajes desglosados (indicios_cierre × 5 + afirmativas × 2 − objeciones × 3), el gap numérico para el siguiente nivel, y los Fragmento_Fuente de señales detectadas
9. WHEN el Acordeón de Etapa de Funnel está expandido, THE Argumentación SHALL mostrar los criterios que determinaron la etapa actual y los Fragmento_Fuente de señales de compra o compromiso detectadas
10. WHEN el Acordeón de Indicadores Comerciales está expandido, THE Argumentación SHALL mostrar el listado de frases detectadas por cada categoría (positivas, afirmativas, cierre, escasez, referidos, objeciones, prospección) con sus Fragmento_Fuente correspondientes
11. IF una Métrica no tiene Fragmento_Fuente asociados porque el análisis no detectó señales relevantes, THEN THE Acordeón SHALL mostrar la Argumentación disponible y un mensaje indicando que no se encontraron fragmentos fuente para esa métrica
12. WHEN un Acordeón está expandido, THE Informe_de_Texto SHALL mostrar cada Fragmento_Fuente con un máximo de 280 caracteres visibles, truncando con "..." los fragmentos que excedan esa longitud
13. WHEN el Acordeón de una Métrica se expande, THE Acordeón SHALL completar la transición visual de colapsado a expandido en no más de 300 milisegundos

### Requirement 2: Generación de argumentación por métrica

**User Story:** Como vendedor, quiero ver una explicación clara de por qué el sistema clasificó cada métrica con su valor actual, para confiar en el análisis y aprender de los indicadores.

#### Acceptance Criteria

1. WHEN se completa un análisis de texto, THE Commercial_Analyzer SHALL generar una estructura de datos de argumentación para cada Métrica que incluya: explicación textual de máximo 300 caracteres, Confidence_Score, y lista de Fragmento_Fuente
2. THE Argumentación de cada Métrica SHALL contener al menos un Fragmento_Fuente del texto original que respalde la clasificación
3. IF el análisis no encuentra ningún Fragmento_Fuente coincidente con las palabras clave o señales definidas para una Métrica, THEN THE Argumentación SHALL indicar "Sin evidencia clara en el texto" junto con el valor por defecto asignado a esa Métrica (UNKNOWN para Intención, NEUTRAL para Sentimiento, FRÍO para Lead, 0 para indicadores numéricos)
4. THE Fragmento_Fuente SHALL mostrarse con un borde lateral izquierdo de 3px de ancho con el color asociado a la Métrica correspondiente, diferenciando visualmente cada Fragmento_Fuente de su contexto circundante
5. WHEN el usuario hace clic en un Fragmento_Fuente dentro de un Acordeón, THE Informe_de_Texto SHALL desplazar el textarea principal hasta la posición del fragmento y aplicar un resaltado de fondo temporal (duración de 2 segundos) sobre la porción exacta del texto correspondiente

### Requirement 3: Consulta de patrones históricos

**User Story:** Como sistema, quiero consultar el historial de análisis en PostgreSQL para identificar patrones que precedieron resultados exitosos, para poder sugerir acciones al vendedor.

#### Acceptance Criteria

1. WHEN se completa un análisis de texto, THE Sistema_de_Aprendizaje SHALL consultar el Historial_PostgreSQL buscando entradas con métricas similares (mismo tipo_lead, misma etapa_funnel, y probabilidad_cierre dentro de un rango de ±15 puntos)
2. WHEN la consulta al Historial_PostgreSQL retorna más de 50 entradas coincidentes, THE Sistema_de_Aprendizaje SHALL seleccionar las 50 entradas más recientes ordenadas por fecha de registro descendente y completar la consulta en un tiempo máximo de 2 segundos
3. WHEN se encuentran entradas históricas similares, THE Sistema_de_Aprendizaje SHALL identificar las acciones o patrones que precedieron avances positivos, definidos como un incremento de al menos 5 puntos en probabilidad_cierre o un cambio de tipo_lead a un nivel superior según la jerarquía (frío < tibio < caliente < cerrado)
4. WHEN se identifican patrones de éxito en las entradas históricas, THE Sistema_de_Aprendizaje SHALL retornar una lista de sugerencias donde cada sugerencia contiene: la acción recomendada, la frecuencia con que dicha acción precedió un avance positivo (expresada como porcentaje sobre el total de entradas analizadas), y la etapa_funnel en que se aplicó
5. IF no existen entradas históricas similares, THEN THE Sistema_de_Aprendizaje SHALL retornar una lista vacía de sugerencias sin generar error
6. THE Sistema_de_Aprendizaje SHALL almacenar en caché los resultados de consulta durante la sesión del usuario, con un tiempo máximo de vida de 30 minutos, para evitar consultas repetidas al Historial_PostgreSQL con los mismos parámetros

### Requirement 4: Sugerencias contextuales al vendedor

**User Story:** Como vendedor, quiero recibir sugerencias específicas basadas en análisis previos similares, para saber qué acciones tomar con el lead actual.

#### Acceptance Criteria

1. WHEN el Sistema_de_Aprendizaje identifica al menos 1 Patrón_Exitoso con un porcentaje de éxito observado igual o superior al 50% y basado en un mínimo de 5 casos históricos similares, THE Informe_de_Texto SHALL mostrar una sección "💡 Sugerencias basadas en historial" debajo de la recomendación actual
2. THE Sugerencia_Contextual SHALL incluir: acción recomendada (texto descriptivo de hasta 200 caracteres), porcentaje de éxito observado en casos similares (valor entero entre 0 y 100 seguido del símbolo "%"), y número de casos analizados (valor entero mayor o igual a 5)
3. THE Informe_de_Texto SHALL mostrar un máximo de 3 Sugerencia_Contextual ordenadas por mayor porcentaje de éxito primero; IF dos sugerencias tienen el mismo porcentaje de éxito, THEN THE Informe_de_Texto SHALL ordenarlas por mayor número de casos analizados primero
4. WHEN no se encuentran patrones históricos que cumplan el umbral mínimo de 50% de éxito y 5 casos analizados, THE Informe_de_Texto SHALL omitir la sección de sugerencias sin mostrar mensaje de ausencia
5. WHEN el usuario hace clic en una Sugerencia_Contextual, THE Informe_de_Texto SHALL expandir un panel de detalle que muestre: la acción realizada en el caso histórico, el resultado obtenido (éxito o fracaso), el tipo de lead involucrado, y la cantidad de interacciones que llevó al resultado, sin incluir texto original ni datos identificables de otros usuarios
6. THE Sugerencia_Contextual SHALL anonimizar los datos del historial, mostrando solo métricas numéricas (porcentaje de éxito, número de casos, cantidad de interacciones) y descripciones de acciones genéricas, sin revelar texto original, nombres, datos de contacto ni identificadores de otros usuarios

### Requirement 5: Integración sin afectar funcionalidad existente

**User Story:** Como desarrollador, quiero que las nuevas funcionalidades se integren sin romper la carga de textos guardados ni los endpoints existentes, para mantener la estabilidad del sistema en producción.

#### Acceptance Criteria

1. THE Informe_de_Texto SHALL mantener el diseño visual actual (colores, tamaños, espaciado) para las métricas en estado colapsado, de forma que la salida HTML generada para las métricas sea idéntica a la versión sin la integración cuando no se expande ningún Acordeón
2. THE renderTextReport SHALL pasar validación con `node --check` sin errores de sintaxis antes de desplegarse a producción
3. IF el Sistema_de_Aprendizaje detecta un error de conexión a PostgreSQL, THEN THE Sistema_de_Aprendizaje SHALL retornar un objeto de sugerencias con listas vacías en un tiempo no mayor a 500 milisegundos, permitiendo que el Informe_de_Texto continúe su renderizado sin interrupción
4. IF la consulta al Historial_PostgreSQL excede 2 segundos de timeout, THEN THE Sistema_de_Aprendizaje SHALL cancelar la consulta y retornar un objeto de sugerencias con listas vacías, equivalente al comportamiento del criterio 3
5. WHEN el Informe_de_Texto se renderiza sin sugerencias históricas disponibles, THE Informe_de_Texto SHALL mostrar todas las métricas y secciones existentes con sus valores calculados, omitiendo únicamente la sección de sugerencias históricas sin mostrar errores ni espacios vacíos visibles al usuario
6. THE implementación SHALL no modificar la firma, el comportamiento de retorno ni los efectos secundarios de la función `loadSavedTexts` ni de los endpoints `/saved-texts` o `/admin/user-texts`, de forma que las respuestas HTTP de dichos endpoints sean idénticas antes y después de la integración para las mismas entradas
7. WHEN el Informe_de_Texto se renderiza con sugerencias históricas disponibles, THE Informe_de_Texto SHALL mostrar la sección de sugerencias históricas además de todas las métricas y secciones existentes, sin alterar la posición ni el contenido de las secciones preexistentes
