# Documento de Requisitos

## Introducción

Esta especificación define las mejoras al panel de indicadores comerciales del analizador de conversaciones inmobiliarias. Actualmente, el indicador "Prospección" cuenta con un panel detallado por categorías, pero los otros 6 indicadores solo muestran un conteo plano de palabras clave. Además, ninguno de los 7 indicadores tiene gráfico de torta CSS ni tooltip con frases faltantes.

El objetivo es enriquecer los 7 indicadores comerciales con: diccionarios de frases organizados por categorías, panel de detalle por categoría, gráfico de torta CSS (conic-gradient) mostrando porcentaje de uso, y tooltip informativo con frases no detectadas.

## Glosario

- **Indicador_Comercial**: Cada uno de los 7 indicadores del análisis comercial (Palabras Positivas, Respuestas Afirmativas, Indicios de Cierre, Escasez Comercial, Pedidos de Referidos, Objeciones, Prospección)
- **Diccionario_Categorias**: Estructura de datos tipo diccionario que organiza frases en subcategorías temáticas para un indicador
- **Panel_Detalle**: Sección expandible dentro de la tarjeta de un indicador que muestra las frases detectadas agrupadas por categoría
- **Grafico_Torta_CSS**: Elemento visual circular implementado con CSS `conic-gradient` que muestra el porcentaje de frases utilizadas vs no utilizadas
- **Tooltip_Faltantes**: Elemento emergente activado por hover sobre un ícono (!) que lista las frases del diccionario que no fueron detectadas en la conversación
- **CommercialAnalyzer**: Clase Python en `src/components/commercial_analyzer.py` que ejecuta el análisis comercial
- **Frase_Detectada**: Frase del diccionario de categorías que fue encontrada en el texto de la conversación analizada
- **Frase_Faltante**: Frase del diccionario de categorías que NO fue encontrada en el texto de la conversación analizada

## Requisitos

### Requisito 1: Diccionarios de categorías para los 6 indicadores planos

**Historia de Usuario:** Como analista de ventas, quiero que cada indicador comercial tenga frases organizadas por subcategorías temáticas, para poder entender mejor qué aspectos de la conversación están cubiertos.

#### Criterios de Aceptación

1. THE CommercialAnalyzer SHALL define un Diccionario_Categorias para cada uno de los 6 indicadores que actualmente solo tienen listas planas (Palabras Positivas, Respuestas Afirmativas, Indicios de Cierre, Escasez Comercial, Pedidos de Referidos, Objeciones)
2. WHEN se define un Diccionario_Categorias, THE CommercialAnalyzer SHALL organizar las frases en un mínimo de 3 subcategorías por indicador
3. WHEN se define un Diccionario_Categorias, THE CommercialAnalyzer SHALL incluir un mínimo de 10 frases por subcategoría
4. THE CommercialAnalyzer SHALL mantener compatibilidad con el diccionario `_KEYWORDS` existente, incluyendo todas las palabras clave actuales dentro de las nuevas categorías

### Requisito 2: Análisis por categorías para todos los indicadores

**Historia de Usuario:** Como analista de ventas, quiero que el análisis detecte frases por categoría para cada indicador, para obtener un desglose detallado del rendimiento comercial.

#### Criterios de Aceptación

1. WHEN el CommercialAnalyzer ejecuta el método `analyze()`, THE CommercialAnalyzer SHALL producir un detalle por categoría para cada uno de los 7 indicadores comerciales
2. WHEN se analiza un texto, THE CommercialAnalyzer SHALL retornar para cada indicador un diccionario con la estructura `{categoria: [lista_de_frases_detectadas]}`
3. WHEN una frase del Diccionario_Categorias aparece en el texto analizado, THE CommercialAnalyzer SHALL incluir esa frase en la lista de frases detectadas de su categoría correspondiente
4. WHEN ninguna frase de una categoría es detectada, THE CommercialAnalyzer SHALL omitir esa categoría del resultado (no incluir categorías vacías)

### Requisito 3: Panel de detalle por categoría en la interfaz

**Historia de Usuario:** Como analista de ventas, quiero ver las frases detectadas agrupadas por categoría cuando expando un indicador, para identificar rápidamente qué áreas de la conversación fueron cubiertas.

#### Criterios de Aceptación

1. WHEN el usuario expande un Indicador_Comercial, THE Panel_Detalle SHALL mostrar las frases detectadas agrupadas por categoría
2. WHEN se muestra una categoría en el Panel_Detalle, THE Panel_Detalle SHALL mostrar el nombre de la categoría, el conteo de frases detectadas, y cada frase como un elemento tipo chip/pill
3. WHEN un Indicador_Comercial no tiene frases detectadas, THE Panel_Detalle SHALL mostrar el mensaje "Ninguna detectada"
4. THE Panel_Detalle SHALL utilizar el borde lateral izquierdo con el color asignado al indicador (verde para Palabras Positivas, azul para Respuestas Afirmativas, amarillo para Indicios de Cierre, naranja para Escasez Comercial, púrpura para Pedidos de Referidos, rojo para Objeciones, cian para Prospección)

### Requisito 4: Gráfico de torta CSS con conic-gradient

**Historia de Usuario:** Como analista de ventas, quiero ver un gráfico circular que muestre qué porcentaje de las frases disponibles fueron utilizadas en la conversación, para evaluar rápidamente la cobertura del indicador.

#### Criterios de Aceptación

1. THE Grafico_Torta_CSS SHALL mostrarse dentro de cada tarjeta de Indicador_Comercial
2. WHEN se renderiza el Grafico_Torta_CSS, THE Grafico_Torta_CSS SHALL calcular el porcentaje como (cantidad de frases detectadas / cantidad total de frases en el Diccionario_Categorias) × 100
3. THE Grafico_Torta_CSS SHALL implementarse usando la propiedad CSS `conic-gradient` con estilo donut (hueco central)
4. THE Grafico_Torta_CSS SHALL usar el color asignado al indicador para la porción "utilizada" y un color gris oscuro (#2a2a2a) para la porción "no utilizada"
5. THE Grafico_Torta_CSS SHALL mostrar el porcentaje numérico en el centro del gráfico

### Requisito 5: Tooltip con frases faltantes

**Historia de Usuario:** Como analista de ventas, quiero ver qué frases del diccionario NO fueron detectadas en la conversación, para poder identificar oportunidades de mejora en el discurso comercial.

#### Criterios de Aceptación

1. THE Tooltip_Faltantes SHALL activarse al hacer hover sobre un ícono (!) ubicado en la tarjeta del Indicador_Comercial
2. WHEN el usuario hace hover sobre el ícono (!), THE Tooltip_Faltantes SHALL mostrar la lista de Frases_Faltantes organizadas por categoría
3. WHEN todas las frases del diccionario fueron detectadas, THE Tooltip_Faltantes SHALL mostrar el mensaje "Todas las frases fueron detectadas"
4. THE Tooltip_Faltantes SHALL tener un fondo oscuro (#1a1a2e) con texto claro y bordes redondeados, consistente con el tema visual existente
5. IF el Tooltip_Faltantes contiene más de 15 frases faltantes, THEN THE Tooltip_Faltantes SHALL limitar la altura visible con scroll interno

### Requisito 6: Integración visual coherente

**Historia de Usuario:** Como usuario de la aplicación, quiero que los nuevos elementos visuales se integren de forma coherente con el diseño existente, para mantener una experiencia de usuario consistente.

#### Criterios de Aceptación

1. THE Panel_Detalle SHALL usar el mismo esquema de colores del tema oscuro existente (fondo #0f1117, bordes #1e2a40)
2. THE Grafico_Torta_CSS SHALL tener un tamaño máximo de 48px de diámetro para no desbalancear la tarjeta del indicador
3. THE Tooltip_Faltantes SHALL posicionarse de forma que no se corte por los bordes del viewport
4. WHEN se renderizan los nuevos elementos, THE Sistema SHALL generar todo el HTML, CSS y JavaScript inline desde Python, sin dependencias externas adicionales
