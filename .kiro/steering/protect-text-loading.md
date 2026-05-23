---
inclusion: auto
---

# REGLA CRITICA: Proteger la carga de textos

## NUNCA modificar estos componentes sin verificar que siguen funcionando:

1. **`loadSavedTexts()`** — Función JavaScript que carga textos en el dropdown. NUNCA agregar código JavaScript que pueda causar SyntaxError antes de esta función.

2. **`loadAdminStats()`** — Función que carga la torta gráfica del panel de seguimiento.

3. **Endpoint `/saved-texts`** — Devuelve los textos guardados filtrados por año/mes.

4. **Endpoint `/admin/user-texts/<username>`** — Devuelve textos de un usuario específico.

5. **Endpoint `/admin/stats/<username>`** — Devuelve estadísticas para la torta gráfica.

## Reglas para evitar romper la carga:

- **NUNCA** usar `<script>` tags dentro de `innerHTML` — los browsers no los ejecutan y rompen el HTML.
- **NUNCA** usar surrogate pairs Unicode (`\ud83d\udccb`) en strings JavaScript — causan SyntaxError.
- **NUNCA** declarar funciones con `function` dentro de bloques `try` — causa SyntaxError en modo estricto.
- **NUNCA** usar IIFEs con MutationObserver que puedan fallar y romper el script.
- **SIEMPRE** usar event listeners delegados simples (document.addEventListener) para interactividad dinámica.
- **SIEMPRE** verificar con `node --check` que el JavaScript no tiene errores de sintaxis antes de deployar.
- **SIEMPRE** que se agregue código JavaScript nuevo, verificar que `loadSavedTexts()` y `loadAdminStats()` siguen ejecutándose correctamente.

## Verificación obligatoria antes de deploy:

Extraer el JavaScript del HTML y validarlo:
```
python -c "f=open('web_app.py','r',encoding='utf-8'); c=f.read(); js=c.split('<script>')[1].split('</script>')[0].replace('{{ indicador_categorias_json | safe }}', '{}'); open('_test.js','w',encoding='utf-8').write(js)"
node --check _test.js
```

## Base de datos:

- Los textos se guardan en **PostgreSQL** (Railway) en la tabla `analysis_history`.
- La migración JSON→PG se ejecuta al arrancar pero usa `ON CONFLICT DO NOTHING` — no borra datos existentes.
- Si los textos no cargan, verificar la conexión a PG con el endpoint `/debug-db`.
