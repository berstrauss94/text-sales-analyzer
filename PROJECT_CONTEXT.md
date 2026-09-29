# PROJECT_CONTEXT.md
## Analizador de Textos de Ventas Inmobiliarias — Contexto integral del proyecto

> Documento de conocimiento único del sistema, pensado para dar contexto completo a personas nuevas y a herramientas de IA (Kiro AI, NotebookLM). Reúne el marco conceptual de negocio, el funcionamiento de cada herramienta y la arquitectura técnica. Versión del sistema: **v30.0**.

---

## 0. Marco conceptual: Empresa 4.0 — del "sobrevivir" al "diseñar la estrategia"

Este proyecto se inscribe en la idea de **Empresa 4.0**: el salto de una organización que reacciona (apaga incendios, decide por intuición, "sobrevive" mes a mes) a una que **diseña su estrategia con datos**. El sistema es una herramienta concreta de ese salto aplicada a una inmobiliaria:

- **De la intuición al dato**: cada conversación de venta se transforma en información medible (intención, sentimiento, probabilidad de cierre, conceptos).
- **Del esfuerzo individual al proceso repetible**: el conocimiento comercial deja de vivir solo en la cabeza de cada vendedor y queda en un sistema que lo estructura, lo mide y lo mejora.
- **De la corrección tardía a la mejora continua**: el equipo retroalimenta al sistema (votos de feedback), y la IA ajusta sus explicaciones. La organización aprende de sí misma.
- **De la supervivencia al diseño estratégico**: los paneles de seguimiento e informes permiten a la coordinación ver tendencias, cumplimiento de metas y uso real, y tomar decisiones de gestión en lugar de reaccionar.

En resumen: el sistema es un instrumento para pasar de "vender como se pueda" a **operar un proceso de ventas observable, medible y perfectible**.

---

## 1. Qué es el sistema

Aplicación web para inmobiliarias que **analiza conversaciones de venta** (texto o audio) y devuelve un diagnóstico comercial accionable, además de **herramientas de seguimiento del equipo**, historial, práctica y gestión de clientes.

**Dominio y lenguaje:** ventas inmobiliarias, español de Argentina (trato de "vos", tono rioplatense).

**Usuarios y roles:**
- **Vendedor**: analiza textos, ve resultados, usa el simulador, carga fichas de clientes (CRM/Lead) y consulta el chat de ayuda.
- **Administrador / Coordinador**: todo lo anterior + paneles de seguimiento, informes, estadísticas, notificaciones y gestión de usuarios.
- **Superadministrador**: rol de mayor privilegio para gestión global.

---

## 2. Flujo principal: analizar un texto

1. **Ingresar** la conversación: escribir/pegar texto, o **subir un audio** (se transcribe automáticamente).
2. Tocar **Analizar**: el sistema procesa y despliega los resultados en tarjetas.
3. (Admins) **Guardar** el texto en el historial con nombre y fecha.
4. **Limpiar** para empezar de cero.
5. **Selectores de año/mes/texto** arriba: permiten recuperar y reanalizar textos ya guardados.

---

## 3. Los filtros del análisis

Cada resultado se organiza en tarjetas ("filtros"):

| Filtro | Qué responde |
|---|---|
| **Intención del texto** | Oferta, consulta, negociación, cierre o descripción (etiquetas internas: OFFER, INQUIRY, NEGOTIATION, CLOSING, DESCRIPTION, UNKNOWN). |
| **Sentimiento** | Positivo, neutral o negativo (POSITIVE, NEUTRAL, NEGATIVE). |
| **Conceptos de ventas** | Oferta, descuento, comisión, cierre, prospecto, objeción, seguimiento, negociación. |
| **Conceptos de bienes raíces** | Tipo de propiedad, precio, metraje, ambientes, baños, ubicación, amenities, zonificación, estado. |
| **Datos extraídos del texto** | Valores concretos (precios, superficies, fechas, contactos) + bloque comercial (funnel, urgencia, compromiso, operación, financiamiento) + señales de compra, objeciones, keywords, alertas. |
| **Análisis comercial inmobiliario** | Tipo de lead, nivel de interés, probabilidad de cierre, nivel de riesgo, indicadores y recomendación. |

**Apartados dentro de cada filtro:** "Qué significa para la venta", "Para el vendedor", "Tips prácticos", "Siguiente paso" (o "Nivel de riesgo" en sentimiento). En el bloque comercial, cada indicador tiene su descripción y su "qué hacer".

---

## 4. La inteligencia artificial en los filtros

Dos motores combinados:

1. **Modelo propio (Machine Learning)**: detecta *qué* aparece (intención, sentimiento, conceptos). Es la fuente de verdad de la clasificación.
2. **IA generativa (Google Gemini)**: redacta las explicaciones *a medida* de cada texto, citando pistas concretas (lo que dijo el cliente, precios, plazos, objeciones), en una sola llamada (single-pass) que cubre **todos los filtros**.

Reglas clave:
- La IA **no inventa** categorías ni cambia lo detectado por el ML: solo lo explica mejor.
- **Fallback seguro**: si la IA no responde, se muestran las explicaciones estándar, sin errores.
- **No altera lo guardado**: las explicaciones de IA se muestran en pantalla; el análisis persistido para los informes históricos se respeta.

### Perilla de feedback (✓ / ✗) en dos pasos
Cada apartado tiene una perilla para calificar la explicación:
1. Se elige **✓** (acertado) o **✗** (poco acertado) — solo marca visual, no envía.
2. Aparece **Aceptar**; se puede cambiar de opción antes de confirmar (evita votos por error).
3. Al **Aceptar**, el voto se registra y el apartado queda confirmado ("Registrado").

Los votos negativos se reutilizan como ejemplos "a evitar" en el prompt de la IA (few-shot), para mejorar las próximas explicaciones.

---

## 5. Herramientas del vendedor

- **Resaltar y definir**: seleccionar una palabra/frase y agregarla al diccionario de filtros, eligiendo su categoría. Enseña vocabulario propio de la inmobiliaria.
- **Editar diccionario**: ver, eliminar o recategorizar las palabras del diccionario.
- **Ícono de ayuda (!)**: explicaciones breves al pasar el cursor, repartidas por la interfaz.
- **CRM y Lead del cliente** (panel plegable, triángulo naranja):
  - *CRM*: texto libre de seguimiento del cliente.
  - *Lead*: ficha estructurada (nombre, contacto, operación, presupuesto, zona, estado, notas).
  - Se guarda por vendedor y queda disponible al volver a entrar.
- **Simulador de ventas**: práctica contra un cliente simulado por IA, con niveles de dificultad y sugerencias de respuesta.
- **Chat de ayuda y sugerencias**:
  - *Ayuda con el sistema* → responde la IA, sin notificar al administrador.
  - *Sugerencia* → notifica al administrador (campana), permite adjuntar foto.

---

## 6. Herramientas del administrador / coordinador

- **Panel de seguimiento**: tendencias por vendedor, cumplimiento de metas, uso del sistema. Filtros por vendedor, mes y período (mensual, trimestral, anual, quincenal).
  - Tabla por vendedor (con colores según meta), gráfico de tendencia (por vendedor o total del equipo), tortas de distribución (por mes y por vendedor), seguimiento de uso (ingresos, tiempo, última vez, herramientas).
- **Informe de seguimiento**: filtrable por período/año/mes/semana/vendedor, con informe redactado automáticamente e impresión en hoja formal.
- **Campana de notificaciones**: sugerencias de los vendedores (pendientes/historial, copiar texto, ampliar fotos, marcar resuelto).
- **Gestión de usuarios**: crear vendedores (nombre, apellido, usuario, contraseña).
- **Diagnósticos** (por URL, solo admin):
  - Estado general de datos (conteos por vendedor, distribución por mes, backups).
  - Estado de la IA (verifica que la clave de Gemini responde).
  - Estado del feedback (resumen de votos ✓/✗ por filtro y apartado).

---

## 7. Arquitectura técnica (resumen)

- **Backend**: Python + **Flask**. Toda la interfaz (HTML/CSS/JS puro) está embebida en `web_app.py` como cadenas de texto (no usa React ni frameworks de frontend).
- **Base de datos**: **PostgreSQL** en Railway, con fallback a JSON en desarrollo local.
- **IA**: **Google Gemini** (modelo `gemini-3.5-flash`, configurable), accedido mediante la librería `openai` apuntada al endpoint compatible de Google. Clave en variable de entorno `GEMINI_API_KEY`.
- **Pipeline de análisis**: un analizador ML (intención, sentimiento, conceptos) + un analizador comercial por reglas/keywords. El resultado se afina con IA solo para la respuesta mostrada.
- **Despliegue**: rama `develop` para trabajo; se despliega mergeando a `master` y haciendo push (Railway redeploya automáticamente).
- **Pruebas**: suite de tests (actualmente 116) que incluye guardas de regresión y validación del JS embebido.

### Tablas principales (aisladas por empresa vía `tenant_id`)
- `analysis_history`: textos analizados y su análisis (fuente de los informes).
- `app_users`: usuarios, roles y contraseñas (hash seguro).
- `activity_store`: actividad y uso del sistema.
- `dictionary_store`: diccionario de filtros por empresa.
- `user_messages`: chat de sugerencias (con foto en base64).
- `lead_fichas`: fichas CRM/Lead por vendedor (una por vendedor, upsert).
- `filter_feedback`: votos ✓/✗ por apartado de cada filtro (tabla separada, no toca el historial).
- `ai_refine_cache`: caché de las explicaciones de IA por texto (ahorra costo/latencia; tabla separada).
- `tenant_config`: configuración por empresa, incluye el "rubro" del negocio (modo rubro).

### Variables de entorno relevantes
- `DATABASE_URL`: conexión a PostgreSQL.
- `GEMINI_API_KEY` (o `GOOGLE_API_KEY`): clave de la IA.
- `GEMINI_MODEL`: modelo de Gemini (por defecto `gemini-3.5-flash`).
- `AI_REFINE_PERSIST`: si vale `1`, la etiqueta afinada por IA también se guarda (solo en textos nuevos).

---

## 7-bis. Catálogo exacto de filtros (definiciones precisas)

Esta sección detalla, con las definiciones y umbrales reales del sistema, qué significa cada valor de cada filtro. Es la referencia para responder con exactitud.

### Intención del texto
Clasifica la etapa/propósito principal de la conversación. Valores posibles:
- **OFERTA (OFFER)**: se presenta una propiedad o servicio a la venta (precio, condiciones, disponibilidad).
- **CONSULTA (INQUIRY)**: hay preguntas o pedidos de información; el interlocutor evalúa y necesita más datos.
- **NEGOCIACIÓN (NEGOTIATION)**: se discuten términos, precios o condiciones. Señal de interés real y cercanía al cierre.
- **CIERRE (CLOSING)**: hay acuerdo o pasos finales (firma, confirmación).
- **DESCRIPCIÓN (DESCRIPTION)**: texto factual que detalla características de un inmueble/situación.
- **DESCONOCIDA (UNKNOWN)**: no hay intención comercial clara (texto ambiguo, corto o incompleto).

Cada intención viene acompañada de una **confianza** (0–100%) y de los apartados explicativos (qué significa, para el vendedor, tips, siguiente paso).

### Sentimiento
Tono emocional del texto:
- **POSITIVO (POSITIVE)**: satisfacción, entusiasmo, aprobación. Buen momento para avanzar.
- **NEUTRAL**: sin emociones fuertes; evaluación fría o comunicación profesional.
- **NEGATIVO (NEGATIVE)**: insatisfacción, preocupación o rechazo; probable objeción o mala experiencia.

El sentimiento también ajusta el **nivel de riesgo** comercial del texto.

### Conceptos de ventas detectados
Menciones comerciales que el sistema reconoce: **oferta, descuento, comisión, cierre, prospecto, objeción, seguimiento, negociación**. Cada concepto aparece con su confianza y con los fragmentos reales del texto donde fue detectado.

### Conceptos de bienes raíces detectados
Menciones propias del inmueble: **tipo de propiedad, precio, metraje (m²), habitaciones, baños, ubicación, amenities, zonificación, estado**. Igual que arriba: confianza + fragmentos citados del texto.

### Datos extraídos del texto
Valores concretos que el sistema extrae y agrupa: **precios, superficies, fechas, horarios, porcentajes, contactos, roles, acciones**. Se muestran como "chips" que resaltan la mención en el texto original.

### Bloque comercial (dentro de Datos extraídos)
- **Etapa del funnel**: `AWARENESS` (conocimiento inicial) → `CONSIDERATION` (evaluación activa) → `DECISION` (cerca de decidir) → `CLOSED` (cerrado/muy avanzado). Se determina por los indicios de cierre, respuestas afirmativas y probabilidad.
- **Urgencia**: `BAJA` | `MEDIA` | `ALTA` | `CRITICA`, según señales de tiempo/inmediatez.
- **Nivel de compromiso**: `BAJO` | `MEDIO` | `ALTO`, según confirmaciones vs. evasivas.
- **Tipo de operación**: `VENTA` | `ALQUILER` | `INVERSION` | `INDEFINIDO`.
- **Financiamiento**: `CONTADO` | `CREDITO` | `FINANCIAMIENTO_DIRECTO` | `NO_DETECTADO`.
- Además: señales de compra, objeciones específicas, técnicas de persuasión, preguntas abiertas, keywords, alertas para el vendedor, co-decisores, rango presupuestario y aviso de revisión del coordinador.

### Análisis comercial inmobiliario
Diagnóstico de cierre, con umbrales reales del sistema:
- **Probabilidad de cierre**: puntaje 0–100 calculado a partir de indicios de cierre, respuestas afirmativas, objeciones, señales de compra, compromiso, urgencia y prospección.
- **Tipo de lead**: `CALIENTE` (probabilidad > 60), `TIBIO` (> 30), `FRIO` (≤ 30).
- **Nivel de interés**: `ALTO` / `MEDIO` / `BAJO`, según la densidad comercial del texto.
- **Tendencia de cierre**: `FUERTE` (prob > 70), `MODERADA` (> 30), `DEBIL` (≤ 30).
- **Nivel de riesgo**: combina probabilidad de cierre y objeciones, y se ajusta con el sentimiento (un tono negativo eleva el riesgo).
- **Recomendación** y **acción siguiente**: sugerencias concretas según la etapa del funnel y las objeciones detectadas.

> Todos estos valores los calcula el modelo/analizador; la IA solo redacta la explicación a medida de cada uno. La lógica de clasificación no cambia por la IA ni por el feedback.

---

## 7-ter. Visión de producto: una herramienta factible para empresas de ventas en general

Aunque el sistema nació para inmobiliarias, su arquitectura y su propuesta de valor son **trasladables a cualquier empresa de ventas**. La razón es que el núcleo no es "inmobiliario": es un **motor de análisis de conversaciones de venta + seguimiento de equipo + mejora continua**.

**Qué lo hace factible para ventas en general:**
- **El diccionario y los conceptos son configurables**: cada empresa enseña su propio vocabulario (con "Resaltar y definir" y el editor de diccionario). Lo que hoy son conceptos inmobiliarios (precio, ubicación, metraje) puede ser el vocabulario de cualquier rubro.
- **Los filtros son universales del proceso de venta**: intención, sentimiento, etapa del funnel, urgencia, compromiso, probabilidad de cierre y tipo de lead existen en toda venta consultiva, no solo en inmuebles.
- **Arquitectura multi-empresa (multi-tenant)**: ya está preparada para dar servicio a varias organizaciones con datos totalmente aislados. Es la base de un producto SaaS vendible a múltiples clientes.
- **La IA explica en el idioma del negocio**: al generar textos a medida, adapta el consejo al contenido real de cada conversación, sea del rubro que sea.

**Propuesta de valor para una empresa de ventas:**
- Convierte conversaciones dispersas en **datos comparables y accionables**.
- Da a cada vendedor un **coach en tiempo real** (qué significa, qué hacer, siguiente paso).
- Da a la coordinación **visibilidad del proceso** (tendencias, metas, uso real del equipo).
- **Mejora sola con el uso**, gracias al feedback del propio equipo.

Este es el sentido "Empresa 4.0": no una herramienta que solo informa, sino una que **participa del proceso comercial y lo hace mejorar con el tiempo**.

---

## 7-quater. Ciclo de retroalimentación (cómo mejora el sistema con el feedback)

El feedback de los usuarios es parte del diseño, no un agregado. El ciclo es:

1. **La IA explica** cada filtro a medida del texto.
2. **El vendedor califica** cada apartado con la perilla ✓ / ✗ (en dos pasos: elige y confirma con "Aceptar", para no votar por error).
3. **El voto se guarda** en una tabla dedicada (`filter_feedback`), separada del historial de análisis, sin afectar los informes.
4. **La IA aprende del feedback**: los apartados marcados como poco acertados se reinyectan en su prompt como ejemplos "a evitar" (técnica de few-shot / aprendizaje en contexto). Así, las próximas explicaciones evitan repetir lo que el equipo señaló como débil.
5. **La coordinación mide**: un panel de diagnóstico resume los votos ✓/✗ por filtro y apartado, revelando qué explicaciones funcionan y cuáles conviene mejorar.

Importante sobre los límites reales: el sistema **no reentrena el modelo de IA en caliente**. La mejora se logra por *aprendizaje en contexto* (inyectar ejemplos y guía en el prompt) y por la medición humana, que es la forma robusta y de bajo costo de capitalizar el feedback sin infraestructura de entrenamiento.

---

## 7-quinquies. Novedades recientes (v28.0 – v30.0)

Esta sección resume las capacidades agregadas después de la v27.3, para que el contexto quede al día.

### Panel de feedback de filtros (v28.0)
Panel admin de solo lectura (`/admin/feedback`) que muestra cómo califican los vendedores las explicaciones de la IA: totales de votos, **tasa de acierto** global, tabla por filtro y apartado (ordenada por los que más votos negativos tienen) y ejemplos de las explicaciones marcadas como poco acertadas. Cierra el círculo del feedback: ahora los votos no solo alimentan a la IA, también se pueden ver y medir.

### Caché de explicaciones de IA (v28.1)
Las explicaciones que genera la IA se guardan en una tabla separada (`ai_refine_cache`) con una clave basada en el texto + etiquetas detectadas + modelo. Si un texto se reanaliza en las mismas condiciones, se reutiliza la explicación en vez de volver a llamar a Gemini. Beneficios: **ahorra costo** de IA, **responde al instante** en textos ya vistos y da **resiliencia** (si la IA está lenta/caída, un texto cacheado igual muestra sus explicaciones). Tiene vencimiento (30 días) y una versión de prompt para refrescar todo cuando se mejora el prompt.

### Exportar informe a Excel/CSV (v28.2)
El informe de seguimiento se exporta a CSV (se abre directo en Excel) con el botón **Exportar**, respetando los mismos filtros que se están viendo (año, mes, semana, vendedor). Descarga la matriz de cargas por vendedor y mes con sus totales.

### Alertas de leads sin seguimiento (v29.0)
Tarjeta admin que avisa qué leads **activos** (estado nuevo/seguimiento) llevan varios días sin tocarse, ordenados por urgencia, con umbral configurable (3/5/7/14 días). Convierte los datos del CRM en una acción concreta para no perder oportunidades.

### Resumen ejecutivo por lead con IA (v29.0)
Botón "Resumen IA" en cada lead: la IA junta la ficha del cliente + sus textos recientes y redacta un resumen accionable (estado del cliente, señales clave, próximo paso). Si la IA no responde, arma un resumen básico por reglas.

### Comparativa entre períodos (v29.0)
En el informe, al seleccionar un mes se muestra una comparación con el mes anterior: cantidad, diferencia y % de variación, con indicador visual de subida/bajada.

### Buscador global (v29.0)
Buscador admin que encuentra por palabra clave tanto en los **textos analizados** (contenido y título) como en las **fichas de lead** (nombre, contacto, zona, notas, CRM, etiquetas).

### Seguridad: rate limiting (v30.0)
Protección contra abuso y fuerza bruta: el acceso (login) y las funciones que usan IA (análisis, audio, simulador, chat) tienen límites de uso por período. Si se superan, el sistema pide esperar unos segundos. Es una defensa de robustez que también controla el costo de IA ante usos anómalos.

### Etiquetas (tags) en los leads (v30.0)
Cada lead puede tener etiquetas libres (ej. "urgente", "referido", "crédito") que se muestran como chips y sirven para segmentar y encontrar clientes desde el buscador.

### Modo rubro (v30.0)
Configuración por empresa que adapta el **contexto de la IA** al tipo de negocio (inmobiliaria, autos, seguros, tecnología, retail, servicios, genérico). No reentrena el modelo: cambia el lenguaje con el que la IA redacta las explicaciones. Por defecto es "inmobiliaria" (comportamiento actual). Es la base para ofrecer el producto a empresas de ventas de otros rubros.

### Limpieza de infraestructura (v30.0)
Se eliminó un servicio en desuso del entorno de despliegue (Railway). Hoy el sistema corre con dos servicios: la base de datos (PostgreSQL) y la aplicación web.

---

## 8. Regla de oro sobre los datos

Cualquier cambio que mejore cómo se muestran o explican los análisis **nunca** debe alterar los textos históricos ni su fecha. Se distingue siempre entre:
- **Pérdida de datos** (baja el conteo) → se resuelve restaurando backup.
- **Reasignación de fecha** (los datos están pero cambian de mes) → es un bug de código, no se arregla con backup.

Las mejoras de IA viven en la respuesta mostrada; lo persistido para informes se preserva. Antes y después de tocar el guardado, se mide con el diagnóstico de estado de datos.

---

## 9. Arquitectura multi-empresa (SaaS)

El sistema está preparado para servir a **varias inmobiliarias** manteniendo los datos de cada una completamente separados por `tenant_id`. Cada usuario pertenece a una empresa y solo ve lo suyo. Roles: vendedor, administrador, superadministrador.

---

## 10. Resumen en una frase

> Pegás una conversación de venta, el sistema te dice qué está pasando y qué hacer —con explicaciones escritas a medida por IA que mejoran con tu feedback—, y por detrás lleva el seguimiento completo del equipo, el historial, la práctica y la gestión de clientes; todo como parte del salto de una inmobiliaria hacia una operación de ventas medible y estratégica (Empresa 4.0).

---

*Documento generado como contexto integral del proyecto, con catálogo exacto de filtros, visión de producto para ventas en general, ciclo de retroalimentación y las novedades v28.0–v30.0 (panel de feedback, caché de IA, exportar informe, alertas y resumen de leads, comparativas, buscador, rate limiting, etiquetas y modo rubro). Versión del sistema: v30.0.*
