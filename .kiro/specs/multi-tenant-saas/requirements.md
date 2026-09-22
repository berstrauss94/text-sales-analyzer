# Requisitos: Multi-Tenant (SaaS) + Seguridad de contraseñas

> Documento de requisitos del proyecto de transformación a multi-tenant. Deriva
> del diseño en `design.md`. No implementa código; define QUÉ debe cumplirse y
> cómo se verifica. Formato: historias de usuario + criterios de aceptación
> (EARS: "El sistema DEBE...").

## Contexto y objetivo

El sistema hoy es de un solo inquilino: un pool de usuarios, un diccionario
global y backups globales, con admin definido por un set hardcodeado. Se busca
convertirlo en SaaS multi-tenant: **varias empresas usando el mismo sistema con
aislamiento total de datos**, sin perder ni mover ningún dato existente, y
cerrando primero un agujero de seguridad conocido (contraseñas SHA-256 sin salt).

## Regla de guardado (invariante que atraviesa TODO el proyecto)

Cualquier cambio que toque guardado, fechas, lectura o conteo de datos DEBE:
- Medir ANTES con `/admin/full-diag` (`db_per_user`, `pipeline_by_year_month`).
- Medir DESPUÉS y comparar: el conteo por usuario y la distribución por mes NO
  deben cambiar salvo que sea el objetivo explícito.
- Distinguir pérdida de datos (baja el conteo) de reasignación de fecha (cambia
  la distribución por mes) — la segunda es un bug de código, no se arregla con
  backup.

---

## Requisito 1 — Seguridad de contraseñas (Fase 0, PRIORITARIO)

**Historia:** Como responsable del sistema, quiero que las contraseñas se
guarden con un hash seguro con salt, para que un acceso a la base de datos no
exponga las credenciales de los usuarios.

### Criterios de aceptación
1. El sistema DEBE hashear contraseñas nuevas con un algoritmo con salt
   (Werkzeug `generate_password_hash`, o bcrypt/argon2), NO con SHA-256 plano.
2. El sistema DEBE poder verificar contraseñas contra el nuevo formato de hash.
3. El sistema DEBE seguir aceptando el login de usuarios cuyo hash todavía está
   en el formato viejo (SHA-256), y al iniciar sesión con éxito DEBE re-hashear
   su contraseña al formato nuevo de forma transparente (migración perezosa).
4. El sistema NO DEBE invalidar ni bloquear ninguna cuenta existente durante la
   migración.
5. La tabla `app_users` DEBE migrarse de forma segura (sin borrar filas): el
   campo de hash admite ambos formatos durante la transición.
6. Verificación: todo usuario existente puede iniciar sesión antes y después del
   cambio; los 106 tests siguen pasando.

---

## Requisito 2 — Modelo de tenants

**Historia:** Como plataforma, quiero un registro de empresas (tenants) y que
cada usuario pertenezca a una, para poder separar sus datos.

### Criterios de aceptación
1. El sistema DEBE tener una tabla `tenants` (id, nombre, activo, plan,
   created_at).
2. La tabla `app_users` DEBE tener una columna `tenant_id` y una columna `rol`
   (`vendedor` | `admin` | `superadmin`).
3. La identidad de un usuario DEBE ser única dentro de su tenant (PK
   `(tenant_id, username)`), permitiendo a futuro que dos empresas repitan un
   nombre de usuario.
4. DEBE existir al menos un `superadmin` de plataforma capaz de ver y gestionar
   todos los tenants.

---

## Requisito 3 — Aislamiento crítico: diccionario y backups (Fase 1, PRIORITARIO)

**Historia:** Como cliente de una empresa, quiero que las frases del diccionario
y los respaldos de mi empresa sean exclusivamente míos, para que ninguna otra
empresa vea ni altere mi información ni mi análisis.

### Criterios de aceptación
1. `dictionary_overrides` DEBE tener `tenant_id`; el índice único de "frase
   repetida" DEBE ser por tenant (`(tenant_id, lower(phrase), category)`).
2. La lectura del diccionario (`phrases_by_category`) DEBE filtrar por
   `tenant_id`; su caché en memoria DEBE ser por tenant (no un único caché
   global).
3. Un usuario de la empresa A NO DEBE poder ver, agregar, mover ni borrar frases
   del diccionario de la empresa B.
4. `history_backups` DEBE tener `tenant_id`; cada snapshot pertenece a un tenant.
5. `take_backup`, la restauración y `auto_fix` DEBEN operar dentro de un tenant:
   restaurar la empresa A NO DEBE tocar los datos de la empresa B.
6. Verificación: prueba de aislamiento que confirme que A no ve datos de B en
   diccionario ni en backups.

---

## Requisito 4 — Migración segura de datos existentes (Fase 2, PRIORITARIO)

**Historia:** Como responsable del sistema, quiero convertir los datos actuales
a multi-tenant sin perder ni mover ningún texto, para no romper el historial en
producción.

### Criterios de aceptación
1. Las columnas `tenant_id` DEBEN agregarse con `DEFAULT '__legacy__'`, de modo
   que todas las filas existentes queden asignadas automáticamente sin pérdida.
2. El sistema DEBE crear el tenant real (ej. `mpc`) y reasignar los datos legacy
   con un UPDATE controlado por tabla.
3. La migración NO DEBE tocar `resolve_entry_date`, NO DEBE reasignar fechas y
   NO DEBE borrar filas: solo etiqueta a qué empresa pertenece cada fila.
4. Verificación OBLIGATORIA: `/admin/full-diag` antes y después DEBE mostrar el
   MISMO total y la MISMA distribución por mes. Si cambian, se revierte.

---

## Requisito 5 — Sesión y autorización por tenant

**Historia:** Como sistema, quiero saber a qué empresa pertenece cada sesión,
para que ningún usuario acceda a datos de otra empresa.

### Criterios de aceptación
1. Al iniciar sesión, el sistema DEBE guardar en la sesión `tenant_id` y `rol`
   además de `username`.
2. El `tenant_id` usado en cualquier operación DEBE salir SIEMPRE de la sesión,
   NUNCA de datos enviados por el cliente.
3. `_is_admin()` DEBE basarse en `rol` (`admin` o `superadmin`), reemplazando el
   set hardcodeado `_ADMIN_USERS`.
4. Las listas de admin duplicadas (en `index()` y en el JS `_actAdmins`) DEBEN
   unificarse en la lógica basada en rol.
5. Un `admin` común solo ve su tenant; solo el `superadmin` puede cruzar tenants.

---

## Requisito 6 — Capa de datos con tenant obligatorio

**Historia:** Como sistema, quiero que sea imposible leer o escribir datos de
negocio sin especificar el tenant, para que el aislamiento no dependa de recordar
un filtro en cada consulta.

### Criterios de aceptación
1. Toda función de lectura/escritura de datos de negocio DEBE recibir y aplicar
   `tenant_id` (add_entry, get_all_entries, get_report_entries_all, list_users,
   add_phrase, get_activity_summary, take_backup, etc.).
2. Ninguna consulta de datos de negocio DEBE ejecutarse sin `WHERE tenant_id`.
3. `list_users(tenant_id)` DEBE devolver solo los usuarios de esa empresa.
4. Los endpoints `/admin/*` DEBEN filtrar por el `tenant_id` de la sesión, salvo
   el panel de superadmin que elige tenant explícitamente.

---

## Requisito 7 — Gestión de tenants (superadmin)

**Historia:** Como superadmin de la plataforma, quiero dar de alta empresas y sus
administradores, para incorporar nuevos clientes.

### Criterios de aceptación
1. El superadmin DEBE poder crear un tenant y su primer usuario admin.
2. El superadmin DEBE poder ver el estado (conteos, actividad) por tenant.
3. Un tenant marcado `activo = false` NO DEBE permitir el login de sus usuarios.

---

## Requisito 8 — No regresión

### Criterios de aceptación
1. Los 106 tests existentes DEBEN seguir pasando en cada fase.
2. El comportamiento para el tenant existente (la empresa actual) DEBE ser
   idéntico al de hoy tras la migración: mismos textos, mismas fechas, mismos
   conteos.
3. Cada fase que toque datos DEBE crear un backup previo y verificar con
   `/admin/full-diag`.

---

## Fuera de alcance (explícito)
- Cobro/facturación por plan (el campo `plan` queda como gancho, sin lógica).
- Subdominio por empresa (`empresaA.tuapp.com`): evolución futura.
- El sistema de respaldo externo semanal (correo/OneDrive) es un proyecto aparte.
