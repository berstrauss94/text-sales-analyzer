---
inclusion: manual
name: analisis-sistema
description: Cómo regenerar el Análisis General Completo del sistema (inventario intensivo con conteos exactos). Usar cuando el usuario pida "el análisis del sistema", "regenerá el análisis", "análisis intensivo" o similar.
---

# Instrucción: Análisis General Completo del Sistema

Cuando el usuario pida regenerar el análisis del sistema (en esta o en cualquier
versión futura del proyecto), hacer EXACTAMENTE esto, sin pedirle que especifique
qué incluir. El objetivo es un documento Word intensivo y 100% completo.

## Paso 1 — Relevar con números reales (NO contar a mano)
Ejecutar el script de relevamiento, que saca los conteos del código real:

```
py scripts/analisis_sistema.py          # resumen
py scripts/analisis_sistema.py --json   # inventario completo (incluye lista de endpoints)
```

Usar esos números tal cual (endpoints, tablas, modelos ML, componentes, módulos
`*_pg`, proveedores de IA, API pública, agentes/hooks/specs/steering de Kiro,
versión visible). Nunca inventar ni estimar un conteo: siempre del script.

## Paso 2 — El documento DEBE cubrir TODO esto (sin omitir nada)
1. **Inventario en números** (tabla con todos los conteos del script).
2. **Endpoints** — catálogo por grupo (núcleo/análisis, simulador, Kanban, bloqueo, CRM/lead, chat/buzón, estadísticas/reportes/inteligencia, diccionario, administración de usuarios, multi-tenant/superadmin, API pública, backups/diagnóstico/sync, PWA).
3. **Base de datos** — las tablas con nombre y para qué sirve cada una.
4. **Inteligencia Artificial** — (a) modelos de ML propios (joblib); (b) IA generativa: proveedores Gemini + OpenAI con sus variables de entorno (GEMINI_API_KEY/GOOGLE_API_KEY, OPENAI_API_KEY) y fallback por reglas; (c) claves de API propias (`api_keys`, hash SHA-256, prefijo `ak_`).
5. **Componentes de análisis** (src/components).
6. **Módulos de datos PostgreSQL** (`*_pg`, patrón best-effort con fallback JSON).
7. **Roles** (vendedor/admin/superadmin) y multi-tenant.
8. **Chat de consultas / notificaciones** — aclarar que es un BUZÓN vendedor↔admin (no un chatbot con IA), con parafraseo IA; campana del admin.
9. **Pipeline Kanban** — 7 etapas, máquina de estados, drag&drop, permisos, inventario anti-doble-venta, historial, sincronía bidireccional CRM↔Kanban con anti-retroceso, migración dry-run, resumen del pipeline, editar tarjetas.
10. **Interruptor de bloqueo** — general/selectivo, popup animado, persistencia PG+JSON.
11. **Estadísticas y reportes** — paneles admin, volumen real (consultar `/admin/db-status` en vivo si se puede).
12. **API pública** (`/api/v1/analyze` con `X-API-Key`).
13. **Infraestructura** — Railway, Gunicorn, Nixpacks/Python 3.12, PostgreSQL, GitHub (`github.com/berstrauss94/text-sales-analyzer`), flujo git push master → deploy, PWA.
14. **Kiro como herramienta de desarrollo** — agentes, hooks, specs y steering (cantidades del script).
15. **Seguridad** — login/sesión, hash de contraseñas, rate limiting, credenciales en env, aislamiento por tenant, errores no expuestos al cliente.
16. **Estado y honestidad técnica** — versión en producción; nota explícita de que "cero bugs garantizado" no existe; los conteos salen del código a la fecha.

## Paso 3 — Generar el Word
Generar `Analisis_General_Completo.docx` en la raíz del proyecto con `python-docx`
(ya instalado): portada, títulos, tablas para los inventarios, viñetas para los
detalles. Borrar cualquier versión anterior del documento para no duplicar.

## Reglas de honestidad (obligatorias)
- Verificar SIEMPRE contra el código real antes de afirmar algo. No describir de memoria.
- Los conteos salen del script; las descripciones funcionales son lectura del código.
- Marcar claramente lo que no se puede verificar desde el código (p. ej. volumen en vivo de la base).
- Limpiar los scripts temporales de generación al terminar.
