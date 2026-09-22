# Plan de tareas: Multi-Tenant (SaaS) + Seguridad

> Ejecutar en orden, fase por fase. Cada casilla se marca `- [x]` al completarse.
> Cada fase que toque datos exige backup previo y verificación con
> `/admin/full-diag` (regla de guardado). Referencias entre paréntesis apuntan a
> los requisitos de `requirements.md`.
>
> Comandos de verificación del proyecto:
> - Compilar: `py -m py_compile web_app.py`
> - Tests: `py -m pytest tests/ -q` (106 deben pasar)
> - Diagnóstico de datos: abrir `/admin/full-diag` como admin

---

## FASE 0 — Seguridad de contraseñas (PRIORITARIA, antes de multi-tenant)

- [ ] 0.1 Registrar estado inicial: correr `/admin/full-diag` y guardar
  `db_per_user` y `pipeline_by_year_month`. Crear backup de datos y tag de
  código estable. (Req 8.3) — **PENDIENTE: lo hace el usuario en producción antes de desplegar.**
- [x] 0.2 Elegir librería de hashing con salt (Werkzeug `generate_password_hash`
  / `check_password_hash`, o bcrypt) y agregarla a las dependencias. (Req 1.1)
  — Werkzeug (viene con Flask, sin dependencia nueva); usa scrypt con salt.
- [x] 0.3 En `UserManager`: agregar `_hash_password_secure()` y
  `_verify_password()` que soporten el formato nuevo. NO borrar aún el SHA-256.
  (Req 1.1, 1.2) — También `_is_legacy_hash()` para distinguir formatos.
- [x] 0.4 Implementar verificación con doble formato: si el hash guardado es
  SHA-256 (viejo), validar con SHA-256; si es del formato nuevo, validar con la
  librería nueva. (Req 1.3) — En `_verify_password()`, usado por `login()`.
- [x] 0.5 Migración perezosa: al hacer login OK contra un hash viejo, re-hashear
  la contraseña al formato nuevo y actualizar `app_users` (y el `.txt`). (Req 1.3)
  — `_migrate_password()`, best-effort, no bloquea el login si falla.
- [x] 0.6 `register()` y `/admin/crear-usuario`: generar el hash nuevo para
  cuentas nuevas. (Req 1.1) — `register()` usa `_hash_password_secure()`;
  `/admin/crear-usuario` llama a `register()`, así que hereda el hash seguro.
- [x] 0.7 Ajustar `app_users` si hace falta (el campo de hash admite ambos
  formatos; no se borra ninguna fila). (Req 1.5) — El campo `password_hash` (TEXT)
  ya admite ambos formatos sin cambios de esquema; `upsert_user` sobrescribe al migrar.
- [x] 0.8 Verificar: usuarios existentes inician sesión antes y después; una
  cuenta migrada vuelve a loguear con su misma contraseña; `py -m pytest tests/ -q`
  en verde. (Req 1.4, 1.6, 8.1) — Probado el ciclo completo (nueva, legacy,
  migración, re-login, rechazo de clave mala); 106 tests en verde.

---

## FASE 1 — Aislamiento crítico: diccionario y backups (PRIORITARIA)

> Se prioriza cerrar la fuga cruzada de información ANTES de tocar el resto.

- [ ] 1.1 Crear tabla `tenants` (id, nombre, activo, plan, created_at). (Req 2.1)
  — **Diferida a Fase 3** (se crea junto con la sesión/rol por tenant; no es
  necesaria para aislar el diccionario, que ya usa `tenant_id` string).
- [ ] 1.2 Sembrar el tenant real inicial (ej. `mpc`) y el `__legacy__`. (Req 2.1, 4.2)
  — **Diferida a Fase 2/3** (etiquetado de datos). Hoy todo vive en `__legacy__`.
- [x] 1.3 `dictionary_overrides`: agregar columna `tenant_id DEFAULT '__legacy__'`.
  (Req 3.1, 4.1) — Con `ALTER TABLE ADD COLUMN IF NOT EXISTS` (migración segura).
- [x] 1.4 Reemplazar el índice único global por uno por tenant
  `(tenant_id, lower(phrase), category)`. (Req 3.1) — Nuevo índice creado y el
  viejo global descartado (`DROP INDEX IF EXISTS`).
- [x] 1.5 `dictionary_store_pg`: propagar `tenant_id` a `add_phrase`,
  `list_phrases`, `phrases_by_category`, `delete_phrase`, `move_phrase`,
  `seed_from_base`, `count_phrases`. (Req 3.1, 3.3, 6.1) — Todas con default
  `__legacy__` (compatibilidad); `delete`/`move` verifican pertenencia al tenant.
- [x] 1.6 Convertir el caché del diccionario a **por tenant**
  (`{tenant_id: frases}`) e invalidar solo el del tenant que escribe. (Req 3.2)
- [x] 1.7 Endpoints `/dictionary/*`: usar el `tenant_id` de la sesión (no del
  request), vía `_current_tenant()`. (Req 3.3, 5.2)
- [x] 1.8 `history_backups`: agregar columna `tenant_id DEFAULT '__legacy__'` e
  índice `(tenant_id, created_at DESC)`. (Req 3.4, 4.1)
- [ ] 1.9 `backup_manager`: lógica de backup por tenant. (Req 3.5)
  — **Diferida a Fase 4 a propósito:** particionar la lógica de backup ANTES de
  que `analysis_history` tenga `tenant_id` (Fase 2) arriesgaría la detección de
  pérdidas que protege los datos. El ESQUEMA ya quedó listo (1.8).
- [x] 1.10 Aislamiento del diccionario: `delete_phrase`/`move_phrase` solo actúan
  si el id pertenece al tenant; `list`/`phrases_by_category` filtran por tenant.
  (Req 3.6) — Aislamiento del diccionario garantizado a nivel de datos.
- [x] 1.11 Verificar: compilar + 106 tests en verde; el análisis del tenant
  existente da el mismo resultado que antes (todo en `__legacy__`). (Req 8.1, 8.2)

---

## FASE 2 — Migración segura de datos existentes (regla de guardado)

> **Enfoque de dos pasos (acordado):** la Fase 2 se divide en 2a (segura, ahora)
> y 2b (cuando entre un segundo tenant real). 2a agrega `tenant_id` SIN tocar la
> PK; 2b cambia la PK a `(tenant_id, id, username)` y renombra `__legacy__` al
> tenant real. Mientras haya un solo tenant, la PK `(id, username)` es suficiente
> y evita reescribir la clave de una tabla de producción.

- [ ] 2.1 Backup total previo (datos + tag de código) y registrar
  `/admin/full-diag`. (Req 4, 8.3) — **PENDIENTE: lo hace el usuario en producción
  antes de desplegar.**
- [x] 2.2 `analysis_history` y `activity_log`: agregar `tenant_id DEFAULT
  '__legacy__'` (todas las filas quedan asignadas sin pérdida). (Req 4.1)
  — Con `ALTER TABLE ADD COLUMN IF NOT EXISTS` (no reescribe datos, no toca fechas).
- [x] 2.3 Índices por tenant: `analysis_history` índice
  `(tenant_id, username, timestamp DESC)`; `activity_log` índice
  `(tenant_id, username, ts DESC)`. (Req 4.1)
  — **PK NO cambiada (queda en 2b):** cambiar la PK de una tabla de producción con
  un solo tenant agrega riesgo sin beneficio. Índices nuevos ya creados.
- [ ] 2.4 (2b) Etiquetar datos legacy al tenant real con UPDATE por tabla.
  (Req 4.2, 4.3) — **DIFERIDA a 2b:** con un solo tenant todo vive en `__legacy__`
  de forma coherente; renombrar a `mpc` es cosmético y se hace cuando entre el 2º
  cliente, junto con el cambio de PK. Las entradas nuevas caen en `__legacy__` por
  el DEFAULT de la columna.
- [ ] 2.5 VERIFICACIÓN OBLIGATORIA: `/admin/full-diag` después de desplegar 2a.
  El total y la distribución por mes DEBEN ser idénticos a 2.1. (Req 4.4)
  — **PENDIENTE: lo hace el usuario en producción tras el deploy.**
- [x] 2.6 A nivel de código: la migración 2a es puro etiquetado (ADD COLUMN con
  DEFAULT). NO toca `resolve_entry_date`, NO reasigna fechas, NO cambia PK, NO
  borra. Por diseño no puede cambiar conteo ni distribución. 106 tests en verde.
  (Req 4.3, 8.2)

---

## FASE 3 — Sesión y autorización por tenant

- [ ] 3.1 `app_users`: agregar columnas `tenant_id` y `rol` (default
  `vendedor`); ajustar PK a `(tenant_id, username)`. (Req 2.2, 2.3)
- [ ] 3.2 Asignar `rol='admin'` a los usuarios hoy en `_ADMIN_USERS` y
  `rol='superadmin'` al dueño de la plataforma. (Req 2.4, 5.3)
- [ ] 3.3 Login: leer `tenant_id` y `rol` de `app_users` y guardarlos en la
  sesión junto a `username`. (Req 5.1)
- [ ] 3.4 Reescribir `_is_admin()` para basarse en `session["rol"]`. (Req 5.3)
- [ ] 3.5 Unificar las listas de admin duplicadas (`index()`, JS `_actAdmins`) en
  la lógica por rol/tenant. (Req 5.4)
- [ ] 3.6 Garantizar que el `tenant_id` sale siempre de la sesión, nunca del
  request. (Req 5.2)
- [ ] 3.7 Verificar: login de vendedor/admin/superadmin correcto; 106 tests en
  verde. (Req 8.1)

---

## FASE 4 — Capa de datos con tenant obligatorio

- [ ] 4.1 `history_manager`: propagar `tenant_id` a `add_entry`,
  `get_all_entries`, `get_flat_entries`, `get_history`, `get_entry_by_id`,
  `get_entries_by_month`, `delete_entry`, `update_entry_text`,
  `get_report_entries_all`, `get_all_usernames_with_entries`. (Req 6.1, 6.2)
- [ ] 4.2 `activity_store_pg`: propagar `tenant_id` a `log_event` y
  `get_activity_summary`. (Req 6.1)
- [ ] 4.3 `UserManager.list_users(tenant_id)`: devolver solo usuarios del tenant.
  (Req 6.3)
- [ ] 4.4 Endpoints `/admin/*` (informe, stats, actividad, user-texts,
  full-diag): filtrar por el `tenant_id` de la sesión. (Req 6.4)
- [ ] 4.5 Endpoints de usuario (analyze, saved-texts, saved-text, delete):
  aplicar `tenant_id` de la sesión. (Req 6.1, 6.2)
- [ ] 4.6 Revisión de barrido: confirmar que NINGÚN `SELECT`/`INSERT`/`UPDATE` de
  datos de negocio queda sin `tenant_id`. (Req 6.2)
- [ ] 4.7 Verificar: compilar + 106 tests; full-diag por tenant coherente.
  (Req 8.1)

---

## FASE 5 — Gestión de tenants (superadmin)

- [ ] 5.1 Endpoint/panel para que el superadmin cree un tenant y su primer admin.
  (Req 7.1)
- [ ] 5.2 Vista de estado por tenant (conteos, actividad) para el superadmin.
  (Req 7.2)
- [ ] 5.3 Bloquear login de usuarios de un tenant con `activo=false`. (Req 7.3)
- [ ] 5.4 Verificar: un admin común no puede cruzar a otro tenant; el superadmin
  sí. (Req 5.5, 7)

---

## FASE 6 — Verificación integral y despliegue

- [ ] 6.1 Tests de aislamiento: crear dos tenants de prueba y confirmar que
  ninguno ve datos del otro (textos, diccionario, backups, actividad, informes).
  (Req 3.6, 6, 8)
- [ ] 6.2 Correr toda la suite `py -m pytest tests/ -q` (106+). (Req 8.1)
- [ ] 6.3 `/admin/full-diag` del tenant existente idéntico al estado pre-proyecto
  (total y distribución por mes). (Req 8.2, 8.3)
- [ ] 6.4 Despliegue por fases a producción con backup previo en cada una;
  desplegar develop→master solo tras verde. (Req 8.3)

---

## Notas de ejecución
- Ninguna fase avanza si la anterior no quedó verificada (tests + full-diag).
- Las Fases 0, 1 y 2 son las prioritarias y se hacen primero, en ese orden.
- Cada cambio que toque guardado/fechas se mide antes y después con full-diag y
  se acompaña de backup. Un cambio de distribución por mes = revertir.
