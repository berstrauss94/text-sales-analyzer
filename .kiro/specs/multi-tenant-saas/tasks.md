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
- [ ] 1.2 Sembrar el tenant real inicial (ej. `mpc` = "Mi Primer Casa S.A.") y el
  tenant `__legacy__` de tránsito. (Req 2.1, 4.2)
- [ ] 1.3 `dictionary_overrides`: agregar columna `tenant_id DEFAULT '__legacy__'`.
  (Req 3.1, 4.1)
- [ ] 1.4 Reemplazar el índice único global por uno por tenant
  `(tenant_id, lower(phrase), category)`. (Req 3.1)
- [ ] 1.5 `dictionary_store_pg`: propagar `tenant_id` a `add_phrase`,
  `list_phrases`, `phrases_by_category`, `delete_phrase`, `move_phrase`,
  `seed_from_base`. (Req 3.1, 3.3, 6.1)
- [ ] 1.6 Convertir el caché del diccionario (TTL 60s) a **por tenant**
  (`{tenant_id: frases}`) e invalidar solo el del tenant que escribe. (Req 3.2)
- [ ] 1.7 Endpoints `/dictionary/*`: usar el `tenant_id` de la sesión (no del
  request). (Req 3.3, 5.2)
- [ ] 1.8 `history_backups`: agregar columna `tenant_id DEFAULT '__legacy__'` e
  índice `(tenant_id, created_at DESC)`. (Req 3.4, 4.1)
- [ ] 1.9 `backup_manager`: `take_backup`, `_current_counts`, `_dump_all_entries`,
  restauración y `auto_fix` operan por tenant. Restaurar A no toca B. (Req 3.5)
- [ ] 1.10 Prueba de aislamiento: la empresa A no ve/edita diccionario ni backups
  de la empresa B. (Req 3.6)
- [ ] 1.11 Verificar: compilar + 106 tests en verde; el análisis del tenant
  existente da el mismo resultado que antes. (Req 8.1, 8.2)

---

## FASE 2 — Migración segura de datos existentes (regla de guardado)

- [ ] 2.1 Backup total previo (datos + tag de código) y registrar
  `/admin/full-diag`. (Req 4, 8.3)
- [ ] 2.2 `analysis_history` y `activity_log`: agregar `tenant_id DEFAULT
  '__legacy__'` (todas las filas quedan asignadas sin pérdida). (Req 4.1)
- [ ] 2.3 Ajustar PK/índices: `analysis_history` PK `(tenant_id, id, username)`,
  índice `(tenant_id, username, timestamp DESC)`; `activity_log` índice
  `(tenant_id, username, ts DESC)`. (Req 4.1)
- [ ] 2.4 Etiquetar datos legacy al tenant real con UPDATE por tabla
  (`SET tenant_id='mpc' WHERE tenant_id='__legacy__'`) en analysis_history,
  activity_log, dictionary_overrides, history_backups, app_users. (Req 4.2, 4.3)
- [ ] 2.5 VERIFICACIÓN OBLIGATORIA: `/admin/full-diag` después de migrar. El
  total y la distribución por mes DEBEN ser idénticos a 2.1. Si cambian,
  revertir. (Req 4.4)
- [ ] 2.6 Confirmar que ningún texto cambió de mes ni desapareció (distribución
  por mes idéntica). (Req 4.3, 8.2)

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
