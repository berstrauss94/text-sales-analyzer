# Bugfix Requirements Document

## Introduction

Se han identificado dos defectos interrelacionados en el sistema de persistencia de archivos/entradas y en el manejo de fechas:

1. **Duplicación de registros**: Cuando un usuario guarda un texto existente (editando nombre, fecha o contenido), el sistema crea un registro NUEVO en lugar de actualizar el registro original. Esto se debe a que `add_entry()` genera un ID nuevo basado en timestamp (`%Y%m%d%H%M%S%f`) en cada invocación, y la cláusula `ON CONFLICT (id, username) DO NOTHING` nunca se activa porque el ID siempre es distinto. El resultado es la proliferación de entradas duplicadas en la base de datos (438+ entradas, 8 usuarios).

2. **Formato de fecha inconsistente**: Los selectores de año en la UI, los parsers de fecha, y los atributos de timestamp almacenados no aplican estrictamente un formato de año de 4 dígitos (YYYY). Esto puede causar datos mal categorizados o errores de parseo.

3. **Seguridad de datos**: No existe verificación previa (dry-run) antes de operaciones de mutación que asegure la integridad del esquema y prevenga pérdida de datos durante operaciones de sobreescritura.

## Bug Analysis

### Current Behavior (Defect)

1.1 CUANDO un usuario edita el nombre, la fecha o el contenido de una entrada existente y presiona "Guardar", ENTONCES el sistema crea un registro NUEVO con un ID diferente en lugar de actualizar el registro original

1.2 CUANDO se invoca `saveWithName()` para reubicar/renombrar una entrada ya guardada, ENTONCES el sistema llama a `/analyze` que ejecuta `add_entry()` generando un nuevo ID basado en timestamp, resultando en un duplicado

1.3 CUANDO `_pg_add_entry()` ejecuta el INSERT con `ON CONFLICT (id, username) DO NOTHING`, ENTONCES la cláusula de conflicto nunca se activa porque cada invocación genera un ID único nuevo, impidiendo cualquier actualización in-place

1.4 CUANDO un usuario selecciona un año en los selectores de fecha de la UI, ENTONCES el sistema no valida ni garantiza que el valor sea un año de 4 dígitos en formato YYYY

1.5 CUANDO se almacena un timestamp o `day_label` en la base de datos, ENTONCES no existe validación que asegure el formato de año de 4 dígitos (DD/MM/YYYY) antes de la persistencia

1.6 CUANDO se ejecuta una operación de sobreescritura/actualización en la base de datos, ENTONCES no existe un mecanismo de verificación previa (dry-run) que confirme la integridad del esquema y la no-pérdida de datos

### Expected Behavior (Correct)

2.1 CUANDO un usuario edita el nombre, la fecha o el contenido de una entrada existente y presiona "Guardar", ENTONCES el sistema DEBERÁ actualizar el registro original in-place (UPSERT) sin crear un registro duplicado

2.2 CUANDO se invoca `saveWithName()` para reubicar/renombrar una entrada ya guardada, ENTONCES el sistema DEBERÁ identificar la entrada existente por su ID original y actualizar sus campos (nombre, año, mes, texto) mediante una operación UPDATE o UPSERT

2.3 CUANDO `_pg_add_entry()` recibe una entrada que ya existe en la base de datos (mismo `audio_filename`/nombre y `username`), ENTONCES DEBERÁ ejecutar `ON CONFLICT DO UPDATE` actualizando todos los campos relevantes (timestamp, text_short, text_full, day_label, etc.)

2.4 CUANDO un usuario selecciona o introduce un año en cualquier campo de fecha de la UI, ENTONCES el sistema DEBERÁ validar y garantizar que el valor sea un entero de 4 dígitos en formato YYYY (rango válido: 2020-2099)

2.5 CUANDO se almacena un timestamp o `day_label` en la base de datos, ENTONCES el sistema DEBERÁ validar que el formato sea estrictamente DD/MM/YYYY con año de 4 dígitos antes de persistir

2.6 CUANDO se ejecuta una operación de sobreescritura/actualización, ENTONCES el sistema DEBERÁ realizar una verificación previa (dry-run) que confirme: (a) el registro objetivo existe, (b) el esquema se mantiene íntegro, y (c) no se pierden campos obligatorios

### Unchanged Behavior (Regression Prevention)

3.1 CUANDO un usuario guarda una entrada completamente NUEVA (texto nunca antes guardado con ese nombre para ese usuario), ENTONCES el sistema DEBERÁ CONTINUAR creando un registro nuevo con un ID único

3.2 CUANDO se consultan textos guardados mediante `loadSavedTexts` o los endpoints `/saved-texts` y `/saved-text/<entry_id>`, ENTONCES el sistema DEBERÁ CONTINUAR retornando los datos correctamente sin modificación en la lógica de lectura

3.3 CUANDO se eliminan entradas mediante `deleteLastEntry` o el endpoint de eliminación, ENTONCES el sistema DEBERÁ CONTINUAR eliminando correctamente el registro solicitado

3.4 CUANDO las fechas ya almacenadas en la base de datos tienen formato correcto (DD/MM/YYYY con 4 dígitos), ENTONCES el sistema DEBERÁ CONTINUAR leyéndolas y mostrándolas sin alteración

3.5 CUANDO se ejecuta la migración JSON→PostgreSQL, ENTONCES el sistema DEBERÁ CONTINUAR usando `ON CONFLICT DO NOTHING` para no sobreescribir datos existentes durante la migración

3.6 CUANDO se utiliza el backend JSON (modo local/fallback), ENTONCES el sistema DEBERÁ CONTINUAR funcionando con la misma lógica de lectura/escritura de archivos JSON existente
