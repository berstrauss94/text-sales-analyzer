---
inclusion: always
---

# Regla permanente: Guardado, fechas y backups (CRÍTICO)

Esta app maneja datos de vendedores en PostgreSQL (producción) con fallback JSON.
Históricamente hubo problemas de "textos que desaparecen o se mueven de mes".
Estas reglas son OBLIGATORIAS y se aplican SIEMPRE, sin que el usuario deba pedirlo.

## Antes de CUALQUIER cambio que toque guardado, fechas, lectura o conteo de datos

1. **Simular / medir ANTES**: registrar el estado actual con `/admin/full-diag`
   (conteos `db_per_user`, `pipeline_by_year_month`). Guardar esos números.
2. **Crear backup de datos** antes de desplegar el cambio (el sistema de
   `backup_manager.py` ya lo hace, pero confirmar que corrió).
3. **Medir DESPUÉS** con el mismo `/admin/full-diag` y comparar: el conteo por
   usuario Y la distribución por mes NO deben cambiar salvo que sea el objetivo
   explícito del cambio.

## Distinguir SIEMPRE dos problemas distintos

- **Pérdida de datos** (borrado): el conteo total o por usuario baja. Se resuelve
  restaurando el backup de datos (`/admin/restore-backup`).
- **Reasignación de fecha** (los datos están, pero cambian de mes/año/día): el
  conteo total NO cambia, pero la distribución por mes sí. Esto es un bug de
  CÓDIGO (resolución de fecha), NO se arregla con backup de datos — se arregla
  revirtiendo/corrigiendo el código.

El `auto_fix` actual compara cantidades; NO detecta reasignación de fecha. Por eso
cualquier cambio a `resolve_entry_date`, `add_entry`, o al guardado de fechas debe
verificar la DISTRIBUCIÓN por mes, no solo el total.

## Regla de oro sobre resolución de fecha

`resolve_entry_date()` es la única fuente de verdad para (año, mes, día). Cambiar
su prioridad de campos (day_label vs year/month vs timestamp) puede MOVER todos
los textos históricos de mes. Antes de tocarla:
- Verificar contra datos reales cómo se resuelven las entradas existentes.
- Nunca asumir que `day_label` histórico es correcto o consistente.
- Preferir cambios que solo afecten entradas NUEVAS, no reinterpretar las viejas.

## Al terminar cualquier tarea

Correr `py -m pytest tests/ -q` (103 tests incl. regression guards) antes de desplegar.
