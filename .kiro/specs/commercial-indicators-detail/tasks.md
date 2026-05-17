# Implementation Plan

## Overview

Implementar detalle por categoría, gráfico de torta CSS (conic-gradient) y tooltip con frases faltantes para los 7 indicadores comerciales del analizador de conversaciones inmobiliarias. Afecta `src/components/commercial_analyzer.py` (backend) y `web_app.py` (frontend).

## Task Dependency Graph

```json
{
  "waves": [
    {"tasks": [1]},
    {"tasks": [2]},
    {"tasks": [3]},
    {"tasks": [4, 8]},
    {"tasks": [5, 7]},
    {"tasks": [6]},
    {"tasks": [9]}
  ]
}
```

## Tasks

- [x] 1. Crear diccionarios de categorías `_INDICADOR_CATEGORIAS` para los 6 indicadores planos en `src/components/commercial_analyzer.py`
  - [x] 1.1 Crear el diccionario `_INDICADOR_CATEGORIAS: dict[str, dict[str, list[str]]]` después de `_PROSPECCION_CATEGORIAS`
  - [x] 1.2 Definir subcategorías para `palabras_positivas`: "entusiasmo" (≥10 frases), "aprobacion" (≥10 frases), "satisfaccion" (≥10 frases)
  - [x] 1.3 Definir subcategorías para `respuestas_afirmativas`: "confirmacion_directa" (≥10 frases), "acuerdo" (≥10 frases), "disposicion" (≥10 frases)
  - [x] 1.4 Definir subcategorías para `indicios_cierre`: "accion_inmediata" (≥10 frases), "compromiso" (≥10 frases), "avance" (≥10 frases)
  - [x] 1.5 Definir subcategorías para `escasez_comercial`: "disponibilidad" (≥10 frases), "urgencia_temporal" (≥10 frases), "limitacion" (≥10 frases)
  - [x] 1.6 Definir subcategorías para `pedidos_referidos`: "solicitud_directa" (≥10 frases), "recomendacion" (≥10 frases), "red_contactos" (≥10 frases)
  - [x] 1.7 Definir subcategorías para `objeciones`: "precio" (≥10 frases), "indecision" (≥10 frases), "postergacion" (≥10 frases)
  - [x] 1.8 Verificar que TODAS las palabras de `_KEYWORDS` existente están incluidas en alguna subcategoría del indicador correspondiente

- [ ] 2. Extender dataclass `CommercialAnalysis` con nuevos campos en `src/components/commercial_analyzer.py`
  - [ ] 2.1 Agregar campo `indicadores_detalle_categorias: dict = field(default_factory=dict)`
  - [~] 2.2 Agregar campo `indicadores_total_frases: dict = field(default_factory=dict)`
  - [~] 2.3 Verificar que los nuevos campos no rompen la serialización existente

- [ ] 3. Implementar método `_analyze_indicador_categorias()` e integrar en `analyze()` en `src/components/commercial_analyzer.py`
  - [~] 3.1 Crear método `_analyze_indicador_categorias(self, normalized: str) -> tuple[dict, dict]`
  - [~] 3.2 Iterar sobre `_INDICADOR_CATEGORIAS` detectando frases por categoría usando `_count_keyword()`
  - [~] 3.3 Omitir categorías sin frases detectadas (no incluir categorías vacías)
  - [~] 3.4 Calcular totales por indicador (suma de frases en todas las subcategorías)
  - [~] 3.5 Incluir total de prospección desde `_PROSPECCION_CATEGORIAS`
  - [~] 3.6 Integrar en `analyze()`: invocar después de `_analyze_prospeccion()`, unificar prospección en la misma estructura
  - [~] 3.7 Asignar resultados a `ca.indicadores_detalle_categorias` y `ca.indicadores_total_frases`

- [ ] 4. Actualizar serialización JSON en `_build_commercial_dict()` de `web_app.py`
  - [~] 4.1 Agregar `"indicadores_detalle_categorias": ca.indicadores_detalle_categorias` al dict
  - [~] 4.2 Agregar `"indicadores_total_frases": ca.indicadores_total_frases` al dict
  - [~] 4.3 Verificar que el JSON resultante es válido y contiene los nuevos campos

- [ ] 5. Agregar funciones JavaScript de renderizado en `web_app.py`
  - [~] 5.1 Implementar `renderPieChart(detected, total, color)` — gráfico donut con `conic-gradient`, 48px diámetro, porcentaje centrado
  - [~] 5.2 Implementar `renderCategoryDetail(indicadorKey, detalleCategorias, color)` — panel con frases agrupadas por categoría como chips/pills
  - [~] 5.3 Implementar `renderMissingTooltip(indicadorKey, detalleCategorias, indicadorCategorias, color)` — tooltip con frases faltantes, scroll si >15
  - [~] 5.4 Agregar función `toggleMissingTooltip(id)` para mostrar/ocultar tooltip en hover

- [ ] 6. Modificar `renderCommercial()` para usar nuevas funciones en `web_app.py`
  - [~] 6.1 Modificar el loop de `indicators.map()` para incluir pie chart junto al valor numérico
  - [~] 6.2 Reemplazar panel de detalle actual (word counts) con `renderCategoryDetail()` para los 7 indicadores
  - [~] 6.3 Agregar ícono (!) con tooltip de frases faltantes en cada tarjeta de indicador
  - [~] 6.4 Aplicar borde lateral izquierdo con color del indicador al panel de detalle expandido
  - [~] 6.5 Mantener funcionalidad existente de highlight en texto al hacer click
  - [~] 6.6 Eliminar panel separado de "Detalle de Prospeccion por Categoria" (ahora integrado en la tarjeta)

- [ ] 7. Inyectar constante `INDICADOR_CATEGORIAS` como JavaScript en `web_app.py`
  - [~] 7.1 Importar `_INDICADOR_CATEGORIAS` y `_PROSPECCION_CATEGORIAS` desde commercial_analyzer
  - [~] 7.2 Generar JSON con `json.dumps({**_INDICADOR_CATEGORIAS, "indicios_prospeccion": _PROSPECCION_CATEGORIAS})`
  - [~] 7.3 Inyectar como `const INDICADOR_CATEGORIAS = {...};` en el bloque `<script>` del HTML

- [ ] 8. Escribir tests de propiedad con Hypothesis en `tests/test_commercial_indicators_properties.py`
  - [~] 8.1 Property 1: Verificar que cada indicador en `_INDICADOR_CATEGORIAS` tiene ≥3 subcategorías con ≥10 frases cada una
  - [~] 8.2 Property 2: Verificar que toda palabra de `_KEYWORDS[indicador]` existe en alguna subcategoría de `_INDICADOR_CATEGORIAS[indicador]`
  - [~] 8.3 Property 3: Para texto aleatorio, `indicadores_total_frases` contiene entero positivo para los 7 indicadores
  - [~] 8.4 Property 4: Si una frase del diccionario aparece en el texto, debe estar en el resultado del análisis
  - [~] 8.5 Property 5: Toda categoría presente en el resultado tiene lista no vacía
  - [~] 8.6 Property 6: Porcentaje = round((detected / total) * 100) para cualquier par válido
  - [~] 8.7 Property 7: Frases faltantes = set(todas) - set(detectadas)

- [ ] 9. Test de integración end-to-end en `tests/test_commercial_indicators_integration.py`
  - [~] 9.1 Test con texto conocido: verificar estructura completa del JSON con nuevos campos
  - [~] 9.2 Test que `_build_commercial_dict()` incluye `indicadores_detalle_categorias` e `indicadores_total_frases`
  - [~] 9.3 Test que el HTML generado contiene `conic-gradient`
  - [~] 9.4 Test que no se agregan dependencias externas (no `<script src=...>` nuevos)

## Notes

- El campo `detalle` existente (conteo por palabra) se mantiene intacto — los nuevos campos son adicionales
- `prospeccion_detalle` sigue existiendo por compatibilidad pero también se incluye en `indicadores_detalle_categorias["indicios_prospeccion"]`
- Performance: ~180 frases extra a buscar por análisis, impacto negligible en textos <5000 palabras
- Sin dependencias nuevas: todo CSS inline (conic-gradient) y JavaScript vanilla
