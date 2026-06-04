---
inclusion: auto
---

# VERSION ESTABLE Y REGLAS DE PROTECCION

## Version estable de referencia

| Tipo | Nombre |
|------|--------|
| Git Tag | `STABLE-v3-2026-05-23` |
| Git Tag | `BACKUP-STABLE-001` |
| Git Branch | `backup/stable-v3-2026-05-23` |

## REGLAS OBLIGATORIAS para cualquier cambio en web_app.py

1. **NUNCA** usar emojis directamente en strings JS concatenados con `+`. Usar HTML entities (`&#128161;` en vez de 💡).
2. **NUNCA** usar `<script>` tags dentro de `innerHTML` — no se ejecutan y rompen el HTML.
3. **NUNCA** declarar funciones con `function` dentro de bloques `try`.
4. **NUNCA** usar IIFEs con MutationObserver.
5. **NUNCA** modificar `loadSavedTexts`, `loadAdminStats`, ni los endpoints `/saved-texts` o `/admin/user-texts` sin verificar que siguen devolviendo datos.
6. **SIEMPRE** validar JS con `node --check` antes de deployar (el test `test_js_syntax.py` lo hace automáticamente).
7. **SIEMPRE** que se modifique `renderTextReport` o cualquier función de renderizado, verificar que NO afecta la carga de textos.
8. **SIEMPRE** hacer deploy y esperar 5 minutos completos antes de verificar cambios en producción.
9. **NUNCA** usar `\s` sin escapar dentro de strings Python que contengan regex JS — usar `\\s` para evitar SyntaxWarning.
10. **NUNCA** agregar funciones nuevas en rutas admin sin agregar `_is_admin()` como primer guard.

## REGLAS OBLIGATORIAS para history_manager.py

1. **NUNCA** definir `_save_json` más de una vez — la segunda definición silenciosamente sobreescribe la primera (que tiene escritura atómica + lock).
2. **SIEMPRE** usar el pool de conexiones `_get_pg_conn()` / `_return_pg_conn()` — nunca crear conexiones directas con `psycopg2.connect()` en funciones del módulo.
3. **SIEMPRE** que se añada una función `_pg_*` nueva, seguir el patrón: `conn = None` en el `except` antes de `_return_pg_conn(conn, close=True)` para evitar doble-release al pool.
4. **NUNCA** liberar la conexión en un bloque `finally` si también se libera en `except` sin `conn = None` en el medio.

## REGLAS OBLIGATORIAS para rutas en web_app.py

1. **SIEMPRE** que se llame `add_entry()` en una ruta, incluir los 3 parámetros obligatorios: `username=`, `text=`, `analysis=`.
2. **SIEMPRE** que se cree una ruta `/admin/*`, agregar `if not _is_admin(): return ..., 403` como primera línea del handler.
3. **NUNCA** exponer `traceback.format_exc()` en endpoints accesibles a usuarios no-admin.

## Cómo restaurar si algo se rompe

```bash
git checkout STABLE-v3-2026-05-23 -- web_app.py src/users/history_manager.py src/components/commercial_analyzer.py src/components/concept_extractor.py
python deploy.py
```

## Tests de protección — ejecutar SIEMPRE antes de deploy

```bash
python -m pytest tests/ -q
```

Cobertura de los tests:

| Archivo | Qué protege |
|---------|-------------|
| `tests/test_js_syntax.py` | Sintaxis JS, sin surrogate pairs, `loadSavedTexts`, `loadAdminStats` |
| `tests/test_structural_integrity.py` | Sin SyntaxWarnings Python, sin funciones duplicadas, `upload_audio` completo, guards admin en todos los endpoints, no double-release de conexiones PG, SECRET_KEY estable, rutas críticas presentes, `add_entry` re-lanza errores |

Estos tests se ejecutan automáticamente en cada deploy via `deploy.py`.
