# Requirements Document

## Introduction

La feature **transcription-sync** integra el analizador de textos de ventas y bienes raíces con la página web externa `miprimercasa.ar/Administracion/GRABACIONAUDITORSUBE.aspx`. El sistema realiza scraping programado dos veces al día para extraer transcripciones de audios de vendedores, las vincula a usuarios del analizador mediante un mapeo configurable, las analiza automáticamente con el pipeline ML existente y las persiste en el historial del usuario con `source="sync"`. Todo esto ocurre sin modificar la interfaz pública del analizador ni los endpoints Flask existentes.

---

## Glossary

- **Sync_Scheduler**: Componente que programa y dispara las tareas de sincronización a las 9:00 y 18:00 (hora local del servidor).
- **Scraper**: Componente que realiza login y extrae transcripciones de la página externa.
- **Transcription**: Objeto que representa una transcripción extraída: texto, nombre de vendedor, timestamp de grabación e identificador único de la fuente externa.
- **Vendor_Name**: Cadena de texto tal como aparece en la página externa (ej. `"ROA ANGELES GISELLE"`).
- **Vendor_Mapping**: Configuración persistente que asocia un `Vendor_Name` a un `username` del analizador.
- **Sync_Pipeline**: Orquestador que coordina Scraper → Vendor_Mapping → Analyzer → HistoryManager para cada transcripción nueva.
- **Dedup_Store**: Almacén de identificadores de transcripciones ya procesadas, usado para evitar duplicados.
- **Sync_Log**: Registro de cada ejecución del Sync_Scheduler (éxitos, errores, cantidad de transcripciones procesadas).
- **External_Credentials**: Variables de entorno `MPC_USERNAME` y `MPC_PASSWORD` usadas para autenticarse en la página externa.
- **HistoryManager**: Módulo existente `src/users/history_manager.py` que persiste entradas de análisis por usuario.
- **Analyzer**: Módulo existente `src/analyzer.py` que ejecuta el pipeline ML sobre un texto.

---

## Requirements

### Requirement 1: Polling programado

**User Story:** Como administrador del sistema, quiero que el sistema extraiga automáticamente transcripciones nuevas dos veces al día, para que los análisis estén disponibles sin intervención manual.

#### Acceptance Criteria

1. THE Sync_Scheduler SHALL ejecutar el Sync_Pipeline a las 09:00 y a las 18:00 hora local del servidor todos los días.
2. WHEN el Sync_Scheduler dispara una ejecución, THE Sync_Pipeline SHALL completar el ciclo completo (scraping → mapeo → análisis → persistencia) antes de que finalice esa ejecución.
3. IF el Sync_Pipeline falla durante una ejecución programada, THEN THE Sync_Scheduler SHALL registrar el error en el Sync_Log y continuar programando la siguiente ejecución sin detener el servidor Flask.
4. THE Sync_Scheduler SHALL iniciarse automáticamente al arrancar la aplicación Flask y detenerse limpiamente al apagar el servidor.
5. WHEN el Sync_Scheduler ya tiene una ejecución en curso, THE Sync_Scheduler SHALL omitir el disparo siguiente para evitar ejecuciones concurrentes.

---

### Requirement 2: Scraping con autenticación

**User Story:** Como administrador del sistema, quiero que el sistema se autentique en la página externa y extraiga las transcripciones disponibles, para obtener los datos de los vendedores.

#### Acceptance Criteria

1. THE Scraper SHALL leer las credenciales de autenticación exclusivamente desde las variables de entorno `MPC_USERNAME` y `MPC_PASSWORD`.
2. WHEN las variables de entorno `MPC_USERNAME` o `MPC_PASSWORD` no están definidas, THEN THE Scraper SHALL lanzar un error de configuración y registrarlo en el Sync_Log sin intentar conectarse a la página externa.
3. WHEN el Scraper realiza el login en la página externa, THE Scraper SHALL mantener la sesión HTTP activa durante toda la extracción de transcripciones de esa ejecución.
4. WHEN el login falla por credenciales incorrectas o error HTTP, THEN THE Scraper SHALL registrar el error en el Sync_Log y abortar la ejecución actual sin reintentos automáticos.
5. WHEN el Scraper accede a la página de transcripciones, THE Scraper SHALL extraer todos los registros disponibles que contengan texto de transcripción, nombre de vendedor y timestamp de grabación.
6. IF la página externa devuelve un error HTTP (4xx o 5xx), THEN THE Scraper SHALL registrar el código de error en el Sync_Log y abortar la ejecución actual.
7. THE Scraper SHALL asignar a cada Transcription un identificador único derivado del nombre del vendedor y el timestamp de grabación.

---

### Requirement 3: Deduplicación de transcripciones

**User Story:** Como administrador del sistema, quiero que el sistema no procese dos veces la misma transcripción, para evitar duplicados en el historial de los usuarios.

#### Acceptance Criteria

1. THE Dedup_Store SHALL persistir los identificadores de todas las Transcriptions ya procesadas entre reinicios del servidor.
2. WHEN el Sync_Pipeline recibe una Transcription cuyo identificador ya existe en el Dedup_Store, THE Sync_Pipeline SHALL omitir esa Transcription sin registrar un error.
3. WHEN el Sync_Pipeline procesa exitosamente una Transcription nueva, THE Sync_Pipeline SHALL agregar su identificador al Dedup_Store antes de finalizar esa ejecución.
4. THE Dedup_Store SHALL soportar al menos 10.000 identificadores sin degradación de rendimiento en las operaciones de consulta e inserción.

---

### Requirement 4: Vinculación de vendedores a usuarios

**User Story:** Como administrador del sistema, quiero configurar el mapeo entre nombres de vendedores de la página externa y usuarios del analizador, para que las transcripciones se asignen al usuario correcto.

#### Acceptance Criteria

1. THE Vendor_Mapping SHALL persistirse en un archivo de configuración JSON en la ruta `config/vendor_mapping.json`.
2. THE Vendor_Mapping SHALL asociar cada `Vendor_Name` (cadena exacta tal como aparece en la página externa) con exactamente un `username` registrado en el analizador.
3. WHEN el Sync_Pipeline recibe una Transcription cuyo `Vendor_Name` no tiene entrada en el Vendor_Mapping, THE Sync_Pipeline SHALL omitir esa Transcription y registrar el `Vendor_Name` no mapeado en el Sync_Log.
4. WHEN el Sync_Pipeline recibe una Transcription cuyo `Vendor_Name` está mapeado a un `username` que no existe en el sistema de usuarios, THE Sync_Pipeline SHALL omitir esa Transcription y registrar el error en el Sync_Log.
5. THE Vendor_Mapping SHALL recargarse desde disco en cada ejecución del Sync_Pipeline para reflejar cambios sin reiniciar el servidor.
6. IF el archivo `config/vendor_mapping.json` no existe o contiene JSON inválido, THEN THE Sync_Pipeline SHALL registrar el error en el Sync_Log y abortar la ejecución actual.

---

### Requirement 5: Análisis automático y persistencia en historial

**User Story:** Como vendedor, quiero que mis transcripciones importadas sean analizadas automáticamente y aparezcan en mi historial, para revisar los resultados sin acción manual.

#### Acceptance Criteria

1. WHEN el Sync_Pipeline procesa una Transcription vinculada a un usuario, THE Sync_Pipeline SHALL invocar `Analyzer.analyze()` con el texto completo de la Transcription.
2. WHEN `Analyzer.analyze()` retorna un `AnalysisReport`, THE Sync_Pipeline SHALL invocar `HistoryManager.add_entry()` con `source="sync"` y el timestamp original de grabación de la Transcription.
3. WHEN `Analyzer.analyze()` retorna un `AnalysisError`, THEN THE Sync_Pipeline SHALL registrar el error en el Sync_Log y omitir la persistencia de esa Transcription, sin agregar su identificador al Dedup_Store.
4. THE Sync_Pipeline SHALL preservar el timestamp original de grabación de la Transcription como campo `timestamp` de la entrada del historial.
5. WHEN una entrada de historial es creada por el Sync_Pipeline, THE HistoryManager SHALL organizar esa entrada en la estructura año/mes/semana/día correspondiente al timestamp original de grabación.
6. THE Sync_Pipeline SHALL invocar `Analyzer.analyze()` y `HistoryManager.add_entry()` usando las mismas instancias ya inicializadas en la aplicación Flask, sin crear instancias adicionales.

---

### Requirement 6: Identificación de entradas sincronizadas en el historial

**User Story:** Como vendedor, quiero que las transcripciones importadas automáticamente estén diferenciadas en mi historial, para distinguirlas de los análisis que ingresé manualmente.

#### Acceptance Criteria

1. WHEN el Sync_Pipeline persiste una Transcription en el historial, THE HistoryManager SHALL almacenar la entrada con `source="sync"`.
2. THE HistoryManager SHALL aceptar el valor `"sync"` como valor válido del campo `source` sin modificaciones al esquema de datos existente.
3. WHEN se consulta el historial de un usuario, THE HistoryManager SHALL retornar las entradas con `source="sync"` junto con las entradas de otros orígenes, sin filtrado implícito.

---

### Requirement 7: Credenciales seguras

**User Story:** Como administrador del sistema, quiero que las credenciales de la página externa nunca estén en el código fuente ni en archivos versionados, para proteger la seguridad del sistema.

#### Acceptance Criteria

1. THE Scraper SHALL obtener las credenciales de autenticación únicamente desde las variables de entorno `MPC_USERNAME` y `MPC_PASSWORD`.
2. THE Sync_Pipeline SHALL registrar en el Sync_Log únicamente mensajes que no contengan los valores de `MPC_USERNAME` ni `MPC_PASSWORD`.
3. THE Vendor_Mapping y el Dedup_Store SHALL almacenarse en archivos que no contengan credenciales de autenticación.

---

### Requirement 8: No regresión de la interfaz existente

**User Story:** Como desarrollador, quiero que la integración de transcription-sync no modifique la interfaz pública del analizador ni los endpoints Flask existentes, para garantizar compatibilidad con los clientes actuales.

#### Acceptance Criteria

1. THE Sync_Pipeline SHALL invocar `Analyzer.analyze(text)` usando únicamente la firma pública existente sin modificar la clase `Analyzer`.
2. THE Sync_Pipeline SHALL invocar `HistoryManager.add_entry(username, text, analysis, source, audio_filename)` usando únicamente la firma pública existente sin modificar el módulo `history_manager`.
3. WHEN el Sync_Scheduler está activo, THE Flask application SHALL continuar respondiendo a todos los endpoints existentes con la misma latencia y comportamiento que sin el scheduler.
4. THE Sync_Scheduler SHALL registrarse en la aplicación Flask sin modificar ningún endpoint HTTP existente ni agregar nuevos endpoints visibles al exterior.
