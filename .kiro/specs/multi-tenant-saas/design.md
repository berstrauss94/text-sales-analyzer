# Diseño arquitectónico: transformación a Multi-Tenant (SaaS)

> **Alcance de este documento:** es SOLO el diseño. No modifica código. Describe
> cómo está el sistema hoy, adónde se quiere llegar (aislamiento total de datos
> por cliente/empresa) y el plan detallado para lograrlo de forma segura,
> respetando la regla de guardado del proyecto (no perder datos, no reasignar
> fechas).

---

## 1. Sistema de autenticación actual (lo que hay hoy)

Antes de rediseñar, se documenta con fidelidad el estado actual, porque el plan
multi-tenant se construye sobre esto.

### 1.1 Inicio de sesión

- **Ruta:** `/login` → `login_page()` en `web_app.py`.
- **Validación de credenciales:** `UserManager.login(username, password)` en
  `src/users/user_manager.py`.
- **Sesión:** al autenticar, se guarda `session["username"] = username`. Es la
  **cookie firmada estándar de Flask** (no hay sesión del lado del servidor). La
  firma depende de `SECRET_KEY`.
- **Fuentes de credenciales (doble):**
  1. Archivo local `usuarios/{username}.txt` (rápido; **efímero en Railway**, se
     borra en cada redeploy).
  2. Tabla PostgreSQL `app_users` (persistente; sobrevive redeploys). Si el
     `.txt` no existe, el login cae a esta tabla.
- **Hash de contraseña:** SHA-256 **sin salt** (`_hash_password`).

### 1.2 Autorización

- **No hay decorador ni sistema de roles.** Cada endpoint repite manualmente:
  - Usuario logueado: `if not session.get("username"): return 401`.
  - Admin: `if not _is_admin(): return 403`.
- **Admin** se determina con un **set hardcodeado** en código:
  `_ADMIN_USERS = {"admin", "Vanesa.Admin", "Berna.Strauss", "FedericoCeballos", "MartinianoSosa"}`.
- Existen **listas de admin duplicadas** (en `index()` y en el JS del panel
  `_actAdmins`) que **no coinciden entre sí** — deuda técnica a unificar.
- La única distinción es **admin / no-admin**. No existe el concepto de empresa,
  rol intermedio, ni pertenencia a un grupo.

### 1.3 Modelo de datos actual (5 tablas PostgreSQL)

| Tabla | Clave | ¿Aislada por usuario hoy? | Notas |
|---|---|---|---|
| `analysis_history` | PK `(id, username)` | **Sí**, por `username` | Los textos analizados. Índice `(username, timestamp)`. |
| `activity_log` | PK `id` | Parcial: se filtra por `username` si se pide | Eventos de uso (login, herramientas). |
| `app_users` | PK `username` | Sí, por `username` | Cuentas (hash + ficha). |
| `dictionary_overrides` | PK `id` | **NO — es GLOBAL** | Frases del diccionario. Afectan el análisis de **todos**. |
| `history_backups` | PK `id` | **NO — es GLOBAL** | Cada backup mezcla las entradas de **todos** los usuarios en un blob. |

### 1.4 Puntos que hoy cruzan a todos los usuarios

Estos son los lugares que, en multi-tenant, tendrían que quedar acotados a la
empresa del usuario:

- `UserManager.list_users()` — une TODOS los usuarios de las 3 fuentes.
- `get_all_usernames_with_entries()` — `SELECT DISTINCT username` sin filtro.
- `get_report_entries_all(usernames)` — trae entradas de muchos usuarios.
- **Todos los endpoints `/admin/*`** — informe, stats, actividad, full-diag, etc.
- **`dictionary_overrides`** — global; cualquier usuario logueado edita el
  diccionario de todos. **Es el punto más crítico.**
- **`history_backups`** — snapshots globales; restauración global.

---

## 2. Objetivo: multi-tenant con aislamiento total

Permitir que **varias empresas (tenants) usen el mismo sistema** sin que ninguna
pueda ver ni afectar los datos de otra. Cada empresa tiene sus propios vendedores,
sus propios textos, su propio diccionario, sus propias estadísticas y sus propios
administradores.

### 2.1 Principio rector

**Toda fila de datos pertenece a exactamente un tenant.** Ninguna consulta puede
devolver datos de otro tenant. El aislamiento se garantiza en la capa de acceso a
datos (todas las consultas llevan `WHERE tenant_id = ?`), no solo en la interfaz.

### 2.2 Estrategia elegida: columna `tenant_id` (shared schema)

Se compara con las alternativas para justificar la elección:

| Estrategia | Qué es | Veredicto |
|---|---|---|
| **Columna `tenant_id`** (elegida) | Todas las tablas ganan una columna `tenant_id`; toda consulta filtra por ella. | **Recomendada.** Menor costo, un solo esquema, backups y despliegue simples. Es el estándar para SaaS que arranca. |
| Un esquema por tenant | Cada empresa tiene su propio conjunto de tablas. | Descartada por ahora: complica migraciones y backups; sobredimensionado para el volumen actual. |
| Una base por tenant | Cada empresa, su propia base. | Descartada: máximo aislamiento pero máximo costo operativo; recién tiene sentido con clientes muy grandes. |

Se usa **`tenant_id`** como nombre de columna (más genérico que `company_id`;
un tenant podría ser una empresa, una sucursal o un grupo).

---

## 3. Nuevo modelo de datos

### 3.1 Tabla nueva: `tenants`

Fuente de verdad de qué empresas existen.

```sql
CREATE TABLE tenants (
    id          TEXT PRIMARY KEY,          -- ej. "mpc" (slug corto y estable)
    nombre      TEXT NOT NULL,             -- "Mi Primer Casa S.A."
    activo      BOOLEAN NOT NULL DEFAULT true,
    plan        TEXT NOT NULL DEFAULT 'basico',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 3.2 Rediseño de `app_users` (cuentas)

Se agrega la pertenencia al tenant y un rol explícito (reemplaza al set
hardcodeado `_ADMIN_USERS`).

```sql
ALTER TABLE app_users ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '__legacy__';
ALTER TABLE app_users ADD COLUMN rol       TEXT NOT NULL DEFAULT 'vendedor'; -- 'vendedor' | 'admin' | 'superadmin'
-- La PK deja de ser username global y pasa a ser (tenant_id, username):
-- dos empresas podrían tener un usuario con el mismo nombre.
```

- **`rol`:** `vendedor` (usa el sistema), `admin` (ve el panel de su empresa),
  `superadmin` (rol de plataforma, ve/gestiona todos los tenants — para vos).
- El `__legacy__` es el tenant temporal donde caen los datos actuales durante la
  migración (ver sección 5).

### 3.3 Tablas de datos: agregar `tenant_id`

```sql
ALTER TABLE analysis_history    ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '__legacy__';
ALTER TABLE activity_log        ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '__legacy__';
ALTER TABLE dictionary_overrides ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '__legacy__';
ALTER TABLE history_backups     ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '__legacy__';
```

**Claves e índices nuevos (el aislamiento se apoya acá):**

```sql
-- analysis_history: la identidad de una entrada ahora es por tenant.
-- (id, username) sigue siendo único DENTRO de un tenant.
ALTER TABLE analysis_history DROP CONSTRAINT analysis_history_pkey;
ALTER TABLE analysis_history ADD PRIMARY KEY (tenant_id, id, username);
CREATE INDEX idx_ah_tenant_user_ts ON analysis_history (tenant_id, username, timestamp DESC);

-- dictionary_overrides: el diccionario pasa a ser POR TENANT.
-- El índice único de "frase repetida" ahora es por tenant.
DROP INDEX idx_dictov_phrase_cat;
CREATE UNIQUE INDEX idx_dictov_tenant_phrase_cat
    ON dictionary_overrides (tenant_id, lower(phrase), category);

-- activity_log
CREATE INDEX idx_activity_tenant_user_ts ON activity_log (tenant_id, username, ts DESC);

-- history_backups: cada backup pertenece a un tenant.
CREATE INDEX idx_backups_tenant ON history_backups (tenant_id, created_at DESC);
```

### 3.4 Diccionario por tenant (el cambio más importante)

Hoy `dictionary_overrides` es global: un vendedor de la empresa A puede alterar
el análisis de la empresa B. En multi-tenant:

- Cada frase pertenece a un `tenant_id`.
- `phrases_by_category()` debe recibir el `tenant_id` y filtrar por él. Su **caché
  en memoria (TTL 60s) debe pasar a ser por tenant** (un diccionario de cachés
  `{tenant_id: frases}`), no un único caché global.
- El diccionario base (el que viene en el código, `_INDICADOR_CATEGORIAS`) sigue
  siendo común a todos; lo que se aísla son las **frases agregadas** por cada
  empresa.

### 3.5 Backups por tenant

`history_backups` deja de ser un blob global. Cada snapshot pertenece a un tenant
y `take_backup` / `restore` / `auto_fix` operan **dentro de un tenant**. Esto es
importante para la regla de guardado: restaurar la empresa A no debe tocar a la B.

---

## 4. Cambios en autenticación y autorización

### 4.1 La sesión gana el tenant

Al hacer login, además de `session["username"]`, se guarda
`session["tenant_id"]` y `session["rol"]` (leídos de `app_users`). A partir de
ahí, **toda** operación usa el `tenant_id` de la sesión, nunca uno que venga del
cliente (para que nadie pueda pedir datos de otro tenant manipulando la request).

### 4.2 Login con tenant

Como la PK pasa a ser `(tenant_id, username)`, el login necesita saber a qué
tenant pertenece el usuario. Dos opciones de diseño (a decidir en implementación):

- **A — Usuario único global:** el `username` sigue siendo único en todo el
  sistema; el login busca su `tenant_id` en `app_users`. Más simple, menos
  flexible.
- **B — Usuario por tenant:** dos empresas pueden repetir nombre de usuario; el
  login pide también identificar la empresa (por un campo, o por subdominio tipo
  `empresaA.tuapp.com`). Más escalable.

**Recomendación:** empezar con **A** (usuario único global) por simplicidad, y
dejar el diseño de datos ya preparado para **B** (por eso la PK incluye
`tenant_id`).

### 4.3 Rol reemplaza al set hardcodeado

- `_is_admin()` deja de mirar `_ADMIN_USERS` y pasa a mirar
  `session["rol"] in ("admin", "superadmin")`.
- Se elimina la deuda de listas duplicadas (`_ADMIN_USERS`, el filtro en
  `index()`, el `_actAdmins` del JS): todas se derivan del `rol` y del `tenant_id`.
- **`superadmin`** (vos) es el único que puede ver/gestionar todos los tenants;
  un `admin` común solo ve el suyo.

### 4.4 Capa de acceso a datos con tenant obligatorio

Regla de diseño: **ninguna función de lectura/escritura de datos de negocio debe
poder ejecutarse sin un `tenant_id`.** Las firmas cambian, por ejemplo:

- `add_entry(tenant_id, username, ...)`
- `get_all_entries(tenant_id, username)`
- `get_report_entries_all(tenant_id, usernames)`
- `list_users(tenant_id)` → solo los usuarios de esa empresa
- `add_phrase(tenant_id, phrase, category, added_by)`
- `get_activity_summary(tenant_id, ...)`
- `take_backup(tenant_id, ...)`

Los endpoints `/admin/*` filtran por el `tenant_id` de la sesión, salvo un panel
de **superadmin** que puede elegir tenant explícitamente.

---

## 5. Plan de migración de los datos actuales (regla de guardado)

Este es el punto más delicado: **no se puede perder ni mover ningún dato
existente.** Estrategia de migración segura:

1. **Backup total previo** (dato Y código) antes de tocar nada. Registrar
   `/admin/full-diag` (conteos `db_per_user`, distribución por mes).
2. **Agregar columnas con `DEFAULT '__legacy__'`** (como en la sección 3). Al
   ponerles default, **todas las filas existentes quedan automáticamente
   asignadas al tenant `__legacy__`** sin perder nada ni cambiar fechas.
3. **Crear el tenant real** (ej. `mpc` = "Mi Primer Casa S.A.") en la tabla
   `tenants`.
4. **Reasignar los datos legacy al tenant real** con un UPDATE controlado:
   `UPDATE analysis_history SET tenant_id = 'mpc' WHERE tenant_id = '__legacy__';`
   (ídem en las otras tablas). Esto **no toca fechas ni conteos**, solo etiqueta a
   qué empresa pertenece cada fila.
5. **Verificar DESPUÉS** con el mismo `/admin/full-diag`: el total y la
   distribución por mes deben ser idénticos a los del paso 1. Si cambian, se
   revierte.
6. Recién entonces activar el filtrado por `tenant_id` en el código.

> **Distinción clave de la regla de guardado:** esta migración solo **etiqueta**
> filas (agrega a qué empresa pertenecen). NO toca `resolve_entry_date`, NO
> reasigna fechas, NO borra. Un fallo se detecta porque cambiaría el conteo o la
> distribución — no porque se muevan textos de mes.

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Una consulta se olvida el `WHERE tenant_id` y filtra datos entre empresas | Centralizar el acceso a datos: que ninguna función acepte omitir el tenant. Revisar cada `SELECT`. Tests que verifiquen aislamiento. |
| El diccionario global filtrado mal afecta a otra empresa | Caché de diccionario por tenant; índice único por tenant. |
| Migración mueve/pierde datos | Columnas con default legacy + UPDATE de etiquetado + verificación antes/después con full-diag. |
| Contraseñas SHA-256 sin salt (deuda existente) | Fuera del alcance de multi-tenant, pero se recomienda migrar a un hash con salt (bcrypt/argon2) en un cambio aparte. |
| `SECRET_KEY` con fallback en dev / no seteada en prod | Exigir `SECRET_KEY` fija en producción (si cambia, se cierran todas las sesiones de todos los tenants). |
| Un admin de una empresa ve datos de otra | El `tenant_id` sale SIEMPRE de la sesión, nunca del request. Solo `superadmin` cruza tenants. |

---

## 7. Fases de implementación sugeridas (cuando se apruebe)

1. **Fase 0 — Preparación:** backup total, registrar full-diag, crear rama.
2. **Fase 1 — Esquema:** crear tabla `tenants`; agregar `tenant_id` y `rol` con
   defaults legacy; crear índices nuevos. (Datos intactos, código aún no filtra.)
3. **Fase 2 — Migración de datos:** crear tenant real, etiquetar filas legacy,
   verificar full-diag antes/después.
4. **Fase 3 — Sesión y auth:** guardar `tenant_id`/`rol` en la sesión; reemplazar
   `_is_admin()` por rol; unificar listas de admin.
5. **Fase 4 — Capa de datos:** propagar `tenant_id` a todas las funciones de
   lectura/escritura (history, activity, dictionary, backups) y a los endpoints.
6. **Fase 5 — Diccionario y backups por tenant.**
7. **Fase 6 — Panel superadmin** para gestionar tenants y alta de empresas.
8. **Fase 7 — Verificación:** tests de aislamiento (empresa A no ve datos de B),
   correr toda la suite, comparar full-diag por tenant.

---

## 8. Qué queda fuera de este diseño (explícito)

- **No** se implementa código en este documento (solo diseño).
- **No** se resuelve el hashing de contraseñas ni el envío de mails (son mejoras
  separadas).
- El facturado/planes por tenant (`plan` en la tabla `tenants`) queda como
  gancho preparado, sin lógica de cobro.
- La opción de subdominio por empresa (`empresaA.tuapp.com`) queda documentada
  como evolución futura, no como requisito inicial.
