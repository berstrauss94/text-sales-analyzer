---
inclusion: always
---

# Deploy a producción (Railway) — memoria del proyecto

Este documento es la fuente de verdad del flujo de despliegue del "Analizador
de Textos". Vale tanto para mí (Kiro) como para cualquier agente del proyecto.
Si algo del flujo cambia, actualizar este archivo.

## Datos clave

- **Repo:** `https://github.com/berstrauss94/text-sales-analyzer.git` (remoto `origin`).
- **Rama que despliega Railway:** `master`. **Railway redespliega automáticamente al hacer `git push origin master`.**
- **Rama de trabajo:** `develop`. Se trabaja acá y luego se mergea a `master`.
  - Aviso: el `origin/develop` remoto puede estar atrasado respecto al local; eso es normal. La verdad de producción es `master`.
- **App principal:** `web_app.py` (Flask monolítico, HTML/JS/CSS inline en strings `HTML` y `LOGIN_HTML`, renderizados con `render_template_string`).
- **Servidor de producción:** gunicorn en Railway, puerto 8080 (`RAILWAY_ENVIRONMENT=production`). Al arrancar, **entrena los modelos de ML frescos** ("Training models fresh..."), por eso el deploy tarda un par de minutos.
- **Base de datos:** en producción `DATABASE_URL` está seteada y **PostgreSQL está disponible**. En local NO (usa fallback JSON). Por eso cualquier estado que deba sobrevivir a los redeploys va en PostgreSQL, no en archivos (el disco de Railway es efímero).

## Entorno local (esta máquina Windows)

- `python`/`python3` en PATH son **alias del Microsoft Store** (no sirven).
- El Python real se invoca con el **`py` launcher**: `py web_app.py`, `py -m py_compile ...`. (Python 3.14, en `C:\Users\berst\AppData\Local\Python\pythoncore-3.14-64\python.exe`.)
- Los `.bat` del proyecto (`iniciar_servidor.bat`) usan `pythonw` y heredan el PATH del usuario; funcionan al doble clic pero no desde un shell que no tenga ese PATH.
- Servidor local de prueba: `py web_app.py` → http://localhost:5000. **`debug=False`, no hay recarga automática**: tras editar hay que reiniciar el proceso.

## Procedimiento de deploy (paso a paso)

1. **Verificar sintaxis:** `py -m py_compile web_app.py <otros_modulos_tocados>`.
2. **Probar en local** (`py web_app.py`, http://localhost:5000) antes de subir.
3. **Subir el número de versión visible** en `web_app.py` (el `<span id="versionBadge">vXX.YY`). Sirve de testigo: si en producción se ve la versión nueva, el deploy entró; si no, es caché o el deploy no terminó.
4. **Commit selectivo en `develop`** — agregar SOLO los archivos del cambio (nunca `git add .`). Hay archivos sin seguimiento que NO deben subirse: `*.docx`, `DIAGNOSTICO_SISTEMA.py`, `scripts/`, `src/backup/`, `usuarios/*_historial.json`, `config/system_lock.json`.
5. **Merge a master y push:**
   ```
   git checkout master
   git pull origin master --ff-only
   git merge develop --no-edit
   git push origin master
   ```
6. **Confirmar el push:** la línea `aaaaaaa..bbbbbbb master -> master` de git es la confirmación real. Verificar con `git rev-parse --short origin/master`.
7. **Esperar el redeploy** (un par de minutos). En producción recargar con **Ctrl + F5** para evitar caché.

## Gotchas (ya nos pasaron)

- **Editar archivos NO despliega nada.** Producción corre lo que está en `origin/master`. Hay que commitear + mergear + pushear.
- En PowerShell, `git` manda mensajes informativos por stderr; con `2>&1` PowerShell los pinta como "error" aunque el comando haya salido bien. Verificar el resultado real con un `git log`/`git rev-parse`, no por el color del texto.
- El error de consola del navegador `AudioContext was not allowed to start` es inofensivo (política de autoplay); no tiene que ver con el deploy.
- **JS inline en `web_app.py`:** el HTML/JS vive dentro de strings Python de triple comilla. Dentro de literales JS usar SIEMPRE `\\n` (doble barra), nunca `\n`: con una sola barra Python mete un salto de línea real y parte la cadena JS → `SyntaxError` que rompe todo el `<script>` y "mata" las funciones (p. ej. `X is not defined` en un `onclick`). Igual con `\\t`, `\\r`, etc. Para acentos/`¿`/`ñ` en JS, usar escapes `\uXXXX` evita problemas de codificación.
- El superadmin de la plataforma es **`Berna.Strauss`** (único con rol `superadmin`). Varios controles solo-admin se gatillan en el HTML con `{% if username == 'Berna.Strauss' %}` y se protegen en el servidor con `if session.get("username") != "Berna.Strauss": return 403`.

## Historial de cambios desplegados

- **v32.18** — Interruptor de bloqueo del sistema por falta de pago (solo Berna.Strauss), a la derecha del título "Analizador de Textos". Al activarlo, ningún otro usuario (común o admin) puede ingresar: ven un popup naranja "Sistema bloqueado por falta de pago". Persistencia en PostgreSQL (`src/users/system_lock_pg.py`, tabla `system_lock`) con fallback a JSON local (`src/users/system_lock.py` → `config/system_lock.json`). Endpoints `GET/POST /admin/system-lock`.
- **v32.19** — Intento de fix del click (knob `pointer-events:none`, `addEventListener`, función global). No era la causa real; se mantiene porque son mejoras válidas.
- **v32.20** — Fix REAL del interruptor que no reaccionaba. Causa raíz: el bloque JS vive dentro de un string Python de triple comilla, y yo había escrito los mensajes de `confirm(...)` con `\n` (una sola barra). Python los convertía en saltos de línea REALES, dejando una cadena JS partida en varias líneas → `Uncaught SyntaxError: Invalid or unexpected token`, que rompía TODO el `<script>` y dejaba `toggleSystemLock is not defined`. Solución: escapar como `\\n` (el resto del proyecto ya usa `\\n` en su JS inline). Lección: **en el JS inline de web_app.py, SIEMPRE usar `\\n`, nunca `\n`.**
