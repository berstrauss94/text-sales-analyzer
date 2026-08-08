# Requirements Document

## Introduction

El **AI Sales Simulator** es un agente conversacional interno que simula compradores inmobiliarios con distintos niveles de dificultad. El sistema ingiere la totalidad de los datos históricos de ventas, scripts, manejo de objeciones y fichas de producto del proyecto para generar interacciones realistas mediante RAG (Retrieval-Augmented Generation) **adaptativo**. El RAG aprende continuamente de cada nueva transcripción que se sube al sistema, enriqueciendo el contexto sin necesidad de reconstrucción manual. El vendedor (usuario) practica sus habilidades de cierre en un entorno seguro y aislado, recibiendo retroalimentación cuantitativa y cualitativa al finalizar cada sesión.

**Categorías de datos ingeridos:** Datos históricos PostgreSQL (438+ entradas, 8 usuarios), scripts de objeciones, fichas de producto, training_data.py (keyword lists por categoría), y todas las transcripciones nuevas que se suban al sistema.

**Niveles de dificultad:** Fácil, Mediano, Difícil, Muy Difícil, Veterano.

**Estilo de respuesta IA:** Conciso, dinámico, orgánico y retador para el vendedor.

## Glossary

- **Simulador**: Módulo backend (Python/Flask) que orquesta la sesión de simulación, gestiona el estado de la conversación y coordina la generación de respuestas del cliente IA.
- **Base_de_Conocimiento**: Vector store o índice RAG adaptativo que contiene el 100% de los datos históricos de ventas, scripts de objeciones, fichas de producto, datos de entrenamiento y todas las transcripciones subidas al sistema. Se actualiza automáticamente con cada nueva transcripción.
- **Motor_IA**: Componente que genera respuestas de texto simulando un comprador, utilizando la Base_de_Conocimiento como contexto y el prompt de dificultad seleccionado. Las respuestas son concisas y desafiantes.
- **Interfaz_Chat**: Componente frontend (JavaScript) que presenta la conversación en tiempo real entre el usuario (vendedor) y el Motor_IA (cliente simulado).
- **Sesión_Simulación**: Instancia aislada de una conversación completa entre el vendedor y el cliente simulado, con estado de memoria independiente y tiempo máximo de inactividad de 5 minutos. El contexto de entrenamiento es exclusivo de cada sesión.
- **Nivel_Dificultad**: Parámetro configurable que ajusta el comportamiento del cliente simulado (Fácil, Mediano, Difícil, Muy Difícil, Veterano).
- **Reporte_Desempeño**: Informe generado al finalizar una sesión que evalúa las habilidades del vendedor en cierre (0-100), manejo de objeciones (0-100) y adherencia a scripts de venta (0-100).
- **Vendedor**: Usuario autenticado del sistema que actúa como vendedor en la simulación.
- **Cliente_Simulado**: Personaje generado por el Motor_IA que actúa como comprador con comportamiento determinado por el Nivel_Dificultad.
- **Módulo_Feedback**: Componente de UI que se despliega al finalizar una sesión para recopilar la opinión del vendedor sobre la simulación.
- **Transcripción**: Archivo de texto de ventas subido por cualquier usuario al sistema, que alimenta automáticamente la Base_de_Conocimiento para enriquecer futuras simulaciones.

## Requirements

### Requirement 1: Ingesta Adaptativa de Base de Conocimiento (RAG Continuo)

**User Story:** Como administrador del sistema, quiero que el Simulador ingiera toda la documentación de ventas existente y aprenda continuamente de cada nueva transcripción subida, para que las simulaciones reflejen escenarios reales y actualizados de la operación comercial.

#### Acceptance Criteria

1. WHEN el Simulador se inicializa, THE Base_de_Conocimiento SHALL indexar los datos históricos de ventas de PostgreSQL (438+ entradas de 8 usuarios), los scripts de objeciones, las fichas de producto y los datos de entrenamiento (training_data.py), y SHALL completar la indexación inicial en un plazo máximo de 120 segundos.
2. WHEN la indexación inicial se completa, THE Base_de_Conocimiento SHALL verificar que el número de fragmentos indexados es igual o superior al número total de registros disponibles en las fuentes, y SHALL registrar el conteo total de fragmentos indexados por fuente.
3. WHEN un usuario sube una nueva transcripción de ventas al sistema, THE Base_de_Conocimiento SHALL incorporar automáticamente la transcripción al índice RAG sin requerir intervención manual ni reconstrucción completa del índice, completando la incorporación en un plazo máximo de 30 segundos por cada 100 registros nuevos.
4. WHEN se incorpora una nueva transcripción, THE Motor_IA SHALL utilizar las personalidades, objeciones y patrones de comportamiento extraídos de la transcripción en futuras sesiones de simulación, enriqueciendo la variedad de respuestas del Cliente_Simulado.
5. THE Base_de_Conocimiento SHALL mantener la asociación entre cada fragmento indexado y su fuente original, incluyendo: tipo de fuente (tabla PostgreSQL, archivo, transcripción subida), identificador del registro de origen, y fecha de indexación.
6. IF la ingesta de un documento o transcripción falla, THEN THE Simulador SHALL registrar el error en el log de aplicación con la fuente específica fallida y el motivo del fallo, y SHALL continuar con los documentos restantes.
7. IF PostgreSQL no está accesible durante la inicialización, THEN THE Simulador SHALL reintentar la conexión un máximo de 3 veces con intervalos de 5 segundos, y si persiste la falla SHALL iniciar con las fuentes locales disponibles (scripts de objeciones, fichas de producto, training_data.py) y registrar la fuente inaccesible como pendiente de indexación.
8. WHILE la Base_de_Conocimiento no haya completado la indexación inicial, THE Simulador SHALL impedir el inicio de nuevas sesiones de simulación e indicar al Vendedor que el sistema está en proceso de carga.
9. THE Base_de_Conocimiento SHALL conectar con TODAS las transcripciones existentes y entrantes del sistema para simular personalidades, objeciones y patrones de comportamiento realistas del cliente.

### Requirement 2: Selección de Nivel de Dificultad

**User Story:** Como vendedor, quiero seleccionar un nivel de dificultad antes de iniciar la simulación, para que pueda practicar con escenarios adaptados a mi experiencia.

#### Acceptance Criteria

1. THE Interfaz_Chat SHALL presentar un selector con cinco niveles de dificultad: Fácil, Mediano, Difícil, Muy Difícil y Veterano, cada uno con una descripción visible de su comportamiento esperado.
2. WHEN el Vendedor selecciona el nivel "Fácil", THE Motor_IA SHALL simular un cliente con fricción mínima que presenta entre 0 y 2 objeciones durante toda la conversación, acepta propuestas sin requerir justificación extensa y avanza hacia el cierre en un máximo de 10 intercambios.
3. WHEN el Vendedor selecciona el nivel "Mediano", THE Motor_IA SHALL simular un cliente con fricción moderada que plantea entre 3 y 5 objeciones relacionadas con precio o características del producto, requiere al menos una propuesta de valor antes de avanzar y completa la conversación en un máximo de 20 intercambios.
4. WHEN el Vendedor selecciona el nivel "Difícil", THE Motor_IA SHALL simular un cliente con fricción alta que plantea entre 5 y 8 objeciones centradas en precio y comparativas con competencia, solicita datos específicos del producto antes de considerar la oferta y completa la conversación en un máximo de 25 intercambios.
5. WHEN el Vendedor selecciona el nivel "Muy Difícil", THE Motor_IA SHALL simular un cliente con fricción severa que plantea entre 8 y 12 objeciones incluyendo solicitudes de descuento, comparaciones de mercado y cuestionamientos de ROI, rechaza al menos 2 propuestas antes de considerar el cierre y completa la conversación en un máximo de 30 intercambios.
6. WHEN el Vendedor selecciona el nivel "Veterano", THE Motor_IA SHALL simular un cliente con fricción máxima que plantea entre 10 y 15 objeciones incluyendo escenarios hipotéticos, referencias a normativas del sector y preguntas técnicas detalladas sobre el producto, rechaza al menos 3 propuestas antes de considerar el cierre y completa la conversación en un máximo de 40 intercambios.
7. IF el Vendedor intenta iniciar una sesión de simulación sin haber seleccionado un Nivel_Dificultad, THEN THE Interfaz_Chat SHALL bloquear el inicio y mostrar un mensaje indicando que la selección de nivel es obligatoria.
8. WHEN el Vendedor selecciona un Nivel_Dificultad, THE Interfaz_Chat SHALL confirmar visualmente la selección activa y habilitar el botón de inicio de simulación.
9. WHILE una sesión de simulación está activa, THE Interfaz_Chat SHALL impedir el cambio del Nivel_Dificultad hasta que la sesión finalice o sea cancelada por el Vendedor.
10. THE Motor_IA SHALL ajustar la severidad de las objeciones y la hesitación de compra del Cliente_Simulado proporcionalmente al Nivel_Dificultad seleccionado.

### Requirement 3: Conversación en Tiempo Real (Concisa y Dinámica)

**User Story:** Como vendedor, quiero interactuar con el cliente simulado en una interfaz de chat en tiempo real con respuestas concisas y desafiantes, para que la experiencia se asemeje a una conversación comercial real y ágil.

#### Acceptance Criteria

1. THE Interfaz_Chat SHALL mostrar los mensajes del Vendedor alineados a la derecha y los mensajes del Cliente_Simulado alineados a la izquierda, diferenciando visualmente cada participante mediante un color de fondo distinto para cada tipo de mensaje.
2. WHEN el Vendedor envía un mensaje, THE Motor_IA SHALL generar una respuesta concisa (máximo 150 palabras por respuesta) que haga referencia a al menos un elemento mencionado previamente en la conversación actual, en un plazo máximo de 10 segundos.
3. THE Motor_IA SHALL generar respuestas dinámicas, orgánicas y desafiantes que eviten frases repetitivas, mantengan un flujo conversacional natural y presionen al Vendedor con objeciones proporcionales al Nivel_Dificultad.
4. IF el Motor_IA no genera una respuesta dentro de los 10 segundos, THEN THE Interfaz_Chat SHALL ocultar el indicador de "escribiendo...", mostrar un mensaje de error indicando que la respuesta no pudo generarse y permitir al Vendedor reenviar su último mensaje.
5. WHILE el Motor_IA genera una respuesta, THE Interfaz_Chat SHALL mostrar un indicador de "escribiendo..." visible al Vendedor.
6. THE Motor_IA SHALL generar respuestas en idioma español coherentes con el Nivel_Dificultad seleccionado, utilizando el vocabulario y las objeciones definidas en el perfil del cliente simulado para ese nivel.
7. WHEN el Cliente_Simulado responde, THE Motor_IA SHALL generar una respuesta que continúe la conversación incorporando referencias al contexto acumulado, pudiendo incluir preguntas, objeciones o afirmaciones según el perfil del Nivel_Dificultad.
8. THE Interfaz_Chat SHALL mantener el historial completo de la conversación visible con desplazamiento vertical durante toda la Sesión_Simulación, soportando hasta 200 mensajes con un máximo de 2000 caracteres por mensaje.
9. WHEN el Vendedor intenta enviar un mensaje vacío o compuesto únicamente por espacios en blanco, THE Interfaz_Chat SHALL impedir el envío y no transmitir el mensaje al Motor_IA.
10. WHEN un nuevo mensaje es agregado a la conversación, THE Interfaz_Chat SHALL desplazar automáticamente la vista al mensaje más reciente.

### Requirement 4: Aislamiento de Sesión y Seguridad

**User Story:** Como administrador del sistema, quiero que cada sesión de simulación opere con estado de memoria aislado y validaciones de seguridad pre-despliegue, para que las simulaciones no afecten los datos de producción ni interfieran entre sí.

#### Acceptance Criteria

1. THE Simulador SHALL crear un estado de memoria independiente para cada Sesión_Simulación que incluya el historial de conversación, el contexto del Motor_IA y las métricas parciales, sin compartir datos mutables con otras sesiones concurrentes.
2. THE Simulador SHALL mantener el contexto de entrenamiento aislado por cada Sesión_Simulación, de forma que los datos de RAG consultados durante una sesión no contaminen ni modifiquen el estado de otra sesión activa.
3. THE Simulador SHALL conservar sin modificaciones la firma, el comportamiento de retorno y los efectos secundarios de la función `loadSavedTexts` y de los endpoints `/saved-texts` y `/admin/user-texts`, de forma que las respuestas HTTP de dichos endpoints sean idénticas antes y después de la integración del Simulador para las mismas entradas.
4. IF el Vendedor cierra la sesión explícitamente, o si el Simulador no recibe mensajes del Vendedor durante un período de inactividad de 5 minutos, THEN THE Simulador SHALL liberar el estado de memoria de la Sesión_Simulación correspondiente en un plazo máximo de 60 segundos tras detectar el evento.
5. WHEN se despliega una actualización del Simulador, THE Simulador SHALL ejecutar una verificación dry-run previa a la escritura de archivos que confirme la ausencia de mutaciones en esquemas de base de datos, rutas de UI existentes o endpoints de carga de textos antes de aplicar los cambios.
6. IF la verificación dry-run detecta una mutación no autorizada en rutas existentes o esquemas de base de datos, THEN THE Simulador SHALL abortar el despliegue y registrar la mutación detectada en el log de aplicación.
7. IF el Vendedor no posee una sesión autenticada válida en el sistema de gestión de usuarios existente, THEN THE Simulador SHALL rechazar la solicitud de inicio de Sesión_Simulación e indicar al Vendedor que debe autenticarse.
8. IF el Simulador no puede asignar recursos de memoria para crear una nueva Sesión_Simulación, THEN THE Simulador SHALL rechazar la solicitud y retornar un mensaje de error indicando que el servicio no puede aceptar sesiones adicionales en ese momento, sin afectar las sesiones activas existentes.
9. THE Simulador SHALL permitir un máximo de 10 sesiones de simulación concurrentes por instancia del servidor, rechazando nuevas solicitudes que excedan este límite con un mensaje de error indicando capacidad alcanzada.
10. THE Simulador SHALL preservar las rutas de aplicación existentes, incluyendo la función `loadSavedTexts` y los endpoints de carga de textos, sin modificar su firma ni comportamiento.

### Requirement 5: Reporte de Desempeño Post-Sesión

**User Story:** Como vendedor, quiero recibir un reporte detallado al finalizar cada sesión de simulación, para que pueda identificar áreas de mejora en mi técnica de ventas.

#### Acceptance Criteria

1. WHEN el Vendedor finaliza una Sesión_Simulación (ya sea explícitamente o al alcanzar el límite de intercambios del Nivel_Dificultad), THE Simulador SHALL generar un Reporte_Desempeño dentro de los 15 segundos posteriores al cierre.
2. THE Reporte_Desempeño SHALL incluir una puntuación numérica entera (0-100) para cada una de las siguientes dimensiones: habilidad de cierre, manejo de objeciones y adherencia a scripts de venta.
3. THE Reporte_Desempeño SHALL incluir retroalimentación textual específica con al menos una fortaleza y una oportunidad de mejora identificadas en la conversación, referenciando mensajes concretos de la sesión.
4. WHEN el Vendedor solicita ver reportes anteriores, THE Simulador SHALL presentar el historial de reportes del Vendedor autenticado ordenado por fecha descendente, mostrando fecha, nivel de dificultad y puntuaciones.
5. THE Reporte_Desempeño SHALL identificar cada objeción planteada por el Cliente_Simulado y evaluar la efectividad de la respuesta del Vendedor frente a la guía de objeciones de la Base_de_Conocimiento, clasificando cada respuesta como "Efectiva", "Parcial" o "Inefectiva".
6. THE Reporte_Desempeño SHALL incluir una puntuación global ponderada (0-100) calculada como: cierre × 0.4 + objeciones × 0.35 + adherencia × 0.25.
7. WHEN el Vendedor completa al menos 3 sesiones de simulación, THE Simulador SHALL incluir en el Reporte_Desempeño una comparativa de progreso mostrando la tendencia de las puntuaciones globales de las últimas 3 sesiones.

### Requirement 6: Módulo de Feedback Post-Sesión

**User Story:** Como vendedor, quiero proporcionar retroalimentación sobre la simulación al finalizar cada sesión, para que el equipo pueda identificar áreas de mejora en el simulador.

#### Acceptance Criteria

1. WHEN una Sesión_Simulación finaliza (ya sea por cierre explícito del Vendedor o por pérdida de la venta simulada), THE Módulo_Feedback SHALL desplegarse automáticamente mostrando la pregunta "¿Qué te pareció la simulación?" como etiqueta visible.
2. THE Módulo_Feedback SHALL incluir un campo de texto abierto para que el Vendedor escriba su retroalimentación, con una altura fija de 16 cm y un ancho igual al de la caja de texto principal del chat (transcripción) posicionada arriba.
3. THE Módulo_Feedback SHALL incluir un botón de envío para confirmar la retroalimentación del Vendedor.
4. WHEN el Vendedor envía su retroalimentación, THE Simulador SHALL almacenar el texto junto con el identificador de la Sesión_Simulación, el identificador del Vendedor y la fecha de envío.
5. IF el Vendedor cierra el Módulo_Feedback sin escribir retroalimentación, THEN THE Simulador SHALL registrar la sesión como "sin feedback" y permitir al Vendedor continuar sin bloqueo.
6. THE Módulo_Feedback SHALL aparecer después del Reporte_Desempeño, permitiendo al Vendedor revisar sus puntuaciones antes de proporcionar retroalimentación.
7. THE Módulo_Feedback SHALL ser accesible y legible, utilizando un tamaño de fuente mínimo de 14px en la etiqueta y el campo de texto.

### Requirement 7: Validación de Despliegue

**User Story:** Como desarrollador, quiero que el código JavaScript del frontend se valide automáticamente antes del despliegue, para que no se introduzcan errores de sintaxis en producción.

#### Acceptance Criteria

1. WHEN se genera o modifica un archivo JavaScript del Simulador, THE Simulador SHALL ejecutar `node --check` sobre el archivo modificado y reportar errores de sintaxis antes de permitir el despliegue.
2. IF la validación con `node --check` falla, THEN THE Simulador SHALL bloquear el despliegue automático y registrar el archivo y la línea con error.
3. THE Simulador SHALL mantener compatibilidad con el flujo de auto-deploy existente (push a master dispara despliegue en Railway).
4. THE Simulador SHALL mantener compatibilidad con el esquema de PostgreSQL existente sin requerir migraciones destructivas.
