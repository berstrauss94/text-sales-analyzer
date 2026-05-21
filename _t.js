
const INDICADOR_CATEGORIAS = {"palabras_positivas": {"entusiasmo": ["excelente", "excelentes", "genial", "fantastico", "fantastica", "increible", "espectacular", "barbaro", "impecable", "extraordinario", "fenomenal", "brillante", "maravilloso", "maravillosa", "estupendo"], "aprobacion": ["bueno", "buena", "buenos", "buenas", "perfecto", "perfecta", "perfectos", "perfectas", "bien", "muy bien", "esta bien", "me gusta", "me encanta", "ideal", "justo lo que buscaba"], "satisfaccion": ["great", "perfect", "excellent", "wonderful", "amazing", "contento", "contenta", "satisfecho", "satisfecha", "conforme", "encantado", "encantada", "feliz", "comodo", "comoda"]}, "respuestas_afirmativas": {"confirmacion_directa": ["si", "claro", "ok", "dale", "listo", "correcto", "exacto", "afirmativo", "yes", "sure", "absolutely", "agreed", "asi es", "tal cual", "efectivamente"], "acuerdo": ["por supuesto", "con gusto", "of course", "sin problema", "como no", "desde luego", "naturalmente", "obvio", "sin duda", "totalmente", "completamente de acuerdo"], "disposicion": ["me parece bien", "estoy de acuerdo", "vamos", "hagamoslo", "cuando quieras", "estoy listo", "estoy lista", "adelante", "perfecto dale", "buenisimo", "genial dale", "va"]}, "indicios_cierre": {"accion_inmediata": ["reservar", "reserva", "bloquear", "bloqueo", "firmar", "firma", "cerrar", "cierre", "reserve", "book", "close", "sign", "quiero reservar", "vamos a firmar"], "compromiso": ["confirmar", "confirmamos", "acordamos", "trato", "deal", "confirm", "cerramos", "lo tomo", "me quedo con", "acepto", "lo compro", "es mio", "quiero ese"], "avance": ["avanzar", "proceder", "proceed", "seguir adelante", "dar el siguiente paso", "como seguimos", "que sigue", "cuando empezamos", "como arrancamos", "vamos adelante", "quiero avanzar", "sigamos", "continuemos"]}, "escasez_comercial": {"disponibilidad": ["disponible", "disponibles", "available", "quedan pocos", "quedan pocas", "hay pocos", "hay pocas", "solo quedan", "unidades disponibles", "lotes disponibles", "todavia hay"], "urgencia_temporal": ["ultimos", "ultima", "ultimo", "last", "urgent", "urgente", "se termina", "se acaba", "no va a durar", "por tiempo limitado", "hasta agotar stock", "oferta por hoy", "solo hoy"], "limitacion": ["limitado", "limitada", "pocas", "pocos", "only", "limited", "exclusivo", "exclusiva", "unico", "unica", "escaso", "pocas unidades", "edicion limitada", "cupos limitados"]}, "pedidos_referidos": {"solicitud_directa": ["conoces", "conoce", "alguien", "know", "someone", "tenes alguien", "sabes de alguien", "conoces a alguien", "hay alguien que", "alguien mas", "alguien interesado"], "recomendacion": ["recomendar", "recomiendas", "recommend", "referral", "nos recomiendes", "pasanos el contacto", "compartir", "decile que", "contale a", "avisale a", "mencionanos"], "red_contactos": ["referido", "referidos", "contacto", "familiar", "amigo", "vecino", "companero", "conocido", "colega", "socio", "pareja", "hermano"]}, "objeciones": {"precio": ["precio", "caro", "cara", "costoso", "costosa", "cuota", "expensive", "price", "muy caro", "fuera de presupuesto", "no me alcanza", "es mucho", "no puedo pagar", "sale mucho"], "indecision": ["duda", "dudas", "pensar", "pensarlo", "doubt", "think", "no se", "no estoy", "tengo que consultarlo", "no estoy seguro", "no estoy segura", "dejame pensarlo", "lo tengo que evaluar"], "postergacion": ["esperar", "despues", "wait", "later", "mas adelante", "otro momento", "la semana que viene", "el mes que viene", "ahora no puedo", "no es el momento", "todavia no", "cuando pueda", "en otro momento"]}, "indicios_prospeccion": {"apertura": ["en que lo puedo ayudar", "en que puedo ayudar", "como puedo asesorar", "que informacion esta buscando", "como puedo orientar", "que estas buscando", "que te gustaria conocer", "en que te doy una mano", "que tipo de inversion", "que andas buscando", "que te interesa ver", "que necesitas saber", "como te puedo ayudar", "como conocio la empresa", "como supo de la empresa", "como nos conociste", "por donde viste", "quien te recomendo", "como llegaste a nosotros", "donde viste nuestros terrenos", "te aparecio una publicidad", "te recomendaron", "como llego hasta nosotros"], "interes": ["esta interesado en invertir", "interesado en invertir", "asegurar su capital", "resguardar su capital", "inversion inmobiliaria", "inversion segura", "invertir y hacer crecer", "invertir en algo seguro", "asegurar tu capital", "poner tu plata en algo seguro", "pensando en invertir", "tener algo propio", "hace cuanto busca invertir", "viene evaluando", "tiene pensado realizar", "viene analizando", "hace cuanto venis buscando", "hace tiempo estas viendo", "cuando empezo tu interes", "andas viendo terrenos", "recien empezas a buscar", "tenes ganas de invertir"], "situacion": ["es propietario o alquila", "vivienda propia o alquilada", "cuenta con vivienda propia", "situacion habitacional", "la casa donde vivis es propia", "estan alquilando", "como estan viviendo", "pagando alquiler", "la casa es de ustedes", "tenes vivienda propia", "a que se dedica", "cual es su ocupacion", "en que rubro trabaja", "en que trabajas", "a que te dedicas", "que actividad realizas", "que haces laboralmente", "de que trabajas"], "familia": ["como se compone su familia", "tiene pareja o hijos", "como esta conformada su familia", "convive con su familia", "tenes familia formada", "vivis con pareja", "como se compone tu familia", "tenes chicos", "estas en pareja", "con quien vivis", "como se llama su pareja", "a que se dedica tu pareja", "como se llama tu hija", "como le va en el colegio", "como se llama la nena", "cuantos anos tiene"], "objetivo": ["busca invertir a futuro", "posesion inmediata", "invertir a futuro o construir", "inversion patrimonial", "resguardo de capital", "comenzar a construir", "la idea es invertir o ya construir", "guardar el terreno o empezar a edificar", "algo para el futuro", "queres invertir o ya hacer tu casa", "construir rapido o guardar", "algo para vivir o como inversion"], "ubicacion_barrio": ["barrios en promocion", "cual le gustaria saber", "que proyecto le gustaria", "que barrio llamo su atencion", "cual te gustaria conocer", "que barrio te interesa", "sobre cual queres que te cuente", "cual de estos barrios", "que zona te interesa", "por cual queres arrancar", "lotes sobre avenida", "mitad de barrio", "ubicacion sobre avenida", "dentro del barrio", "preferis sobre avenida", "mas visible o mas tranquilo", "avenida o media cuadra", "mas tranquilo o con mas movimiento", "donde te imaginas mejor"], "modalidad_pago": ["cuotas fijas y cuotas variables", "cuotas fijas o variables", "modalidad de financiacion", "cuotas fijas o actualizables", "preferis cuotas fijas", "que opcion te resulta mas comoda", "se adapta mejor a tu economia", "te sirven mas cuotas fijas", "que modalidad preferis", "alguna dimension en especial", "dimension especifica", "que tamano de lote", "que medida te interesa", "tenemos varias dimensiones", "algo grande o mas estandar", "que tamano te gusta", "lote mas chico o mas amplio", "que medida tenias en mente", "esquina o un lote a mitad", "lote en esquina o interno", "ubicacion en esquina", "esquina o mitad de cuadra", "mas visibilidad o algo mas reservado", "capacidad de pago mensual", "cuanto se permite pagar", "presupuesto mensual", "valor de cuota", "monto mensual", "cuota te sentirias comodo", "cuanto pensas destinar", "presupuesto mensual manejas", "cuanto te gustaria pagar", "cuota te queda comoda", "cuanto podes invertir mensualmente"]}};
let _lastCommercialData = null;

async function analyze() {
    const text = document.getElementById('textInput').value.trim();
    if (!text) return;

    const year = document.getElementById('selectYear').value;
    const month = document.getElementById('selectMonth').value;

    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, year: parseInt(year), month: parseInt(month) })
        });
        const data = await response.json();
        _lastCommercialData = data.commercial || null;
        // Update textarea with cleaned text (deduped)
        if (!data.error && data.input_text) {
            document.getElementById('textInput').value = data.input_text;
        }
        renderResults(data, data.input_text || text);
    } catch (e) {
        document.getElementById('results').innerHTML =
            '<div class="error-card">Error de conexion: ' + e.message + '</div>';
        document.getElementById('results').style.display = 'block';
    }

    document.getElementById('loading').style.display = 'none';
}

async function saveEntry() {
    const text = document.getElementById('textInput').value.trim();
    const entryName = document.getElementById('entryNameInput').value.trim();

    if (!text) { alert('Pega o escribe un texto primero.'); return; }
    if (!entryName) { alert('El titulo es obligatorio para guardar.'); return; }

    const year = document.getElementById('selectYear').value;
    const month = document.getElementById('selectMonth').value;

    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';

    try {
        // If admin has a user selected, save to that user
        const userSelect = document.getElementById('selectUser');
        const targetUser = userSelect ? userSelect.value : '';

        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, year: parseInt(year), month: parseInt(month), entry_name: entryName, target_user: targetUser })
        });
        const data = await response.json();
        _lastCommercialData = data.commercial || null;
        if (!data.error && data.input_text) {
            document.getElementById('textInput').value = data.input_text;
        }
        renderResults(data, data.input_text || text);

        // Scroll to top after saving
        window.scrollTo({ top: 0, behavior: 'smooth' });
        // Clear the title input
        document.getElementById('entryNameInput').value = '';
        // Refresh saved texts count
        loadSavedTexts();
    } catch (e) {
        document.getElementById('results').innerHTML =
            '<div class="error-card">Error de conexion: ' + e.message + '</div>';
        document.getElementById('results').style.display = 'block';
    }

    document.getElementById('loading').style.display = 'none';
}

function clearAll() {
    document.getElementById('textInput').value = '';
    document.getElementById('results').style.display = 'none';
    closeHighlightOverlay();
    _lastCommercialData = null;
}

function confBar(value) {
    const pct = Math.round(value * 100);
    return `<div class="confidence">${pct}% confianza</div>
            <div class="conf-bar"><div class="conf-fill" style="width:${pct}%"></div></div>`;
}

// Translations for concept names
const SALES_CONCEPTS_ES = {
    'offer': 'Oferta',
    'discount': 'Descuento / Rebaja',
    'commission': 'Comision',
    'closing': 'Cierre de Venta',
    'prospect': 'Prospecto / Cliente',
    'objection': 'Objecion',
    'follow_up': 'Seguimiento',
    'negotiation': 'Negociacion'
};

const RE_CONCEPTS_ES = {
    'property_type': 'Tipo de Propiedad',
    'price': 'Precio',
    'area_sqm': 'Metraje / Area',
    'bedrooms': 'Habitaciones',
    'bathrooms': 'Banos',
    'location': 'Ubicacion',
    'amenities': 'Amenidades',
    'zoning': 'Zonificacion',
    'condition': 'Estado / Condicion'
};

const INTENT_ES = {
    'OFFER': 'OFERTA',
    'INQUIRY': 'CONSULTA',
    'NEGOTIATION': 'NEGOCIACION',
    'CLOSING': 'CIERRE',
    'DESCRIPTION': 'DESCRIPCION',
    'UNKNOWN': 'DESCONOCIDO'
};

const SENTIMENT_ES = {
    'POSITIVE': 'POSITIVO',
    'NEUTRAL': 'NEUTRAL',
    'NEGATIVE': 'NEGATIVO'
};

const ENTITY_ES = {
    'price': 'Precio',
    'area_sqm': 'Metraje',
    'bedrooms': 'Habitaciones',
    'bathrooms': 'Baños',
    'location': 'Ubicacion',
    'date': 'Fecha/Plazo',
    'schedule': 'Horario/Disponibilidad',
    'percentage': 'Porcentaje',
    'contact': 'Contacto',
    'action': 'Accion comprometida',
    'role': 'Persona/Rol',
    'condition': 'Condicion/Requisito'
};

const ENTITY_ICONS = {
    'price': '💰',
    'area_sqm': '📐',
    'bedrooms': '🛏️',
    'bathrooms': '🚿',
    'location': '📍',
    'date': '📅',
    'schedule': '🕐',
    'percentage': '📊',
    'contact': '📞',
    'action': '✅',
    'role': '👤',
    'condition': '📋'
};

function translateConcept(key, map) {
    return map[key] || key;
}

function renderResults(data, inputText) {
    const el = document.getElementById('results');
    window._lastInputText = inputText || '';

    if (data.error) {
        const errorMessages = {
            'INPUT_TOO_SHORT': 'El texto es demasiado corto para analizar.',
            'INPUT_TOO_LONG': 'El texto supera el limite maximo permitido.',
            'INPUT_EMPTY': 'El texto no contiene contenido analizable.',
            'ANALYSIS_ERROR': 'Ocurrio un error durante el analisis.'
        };
        const msg = errorMessages[data.error_code] || data.error_message;
        el.innerHTML = `<div class="error-card"><strong>Error:</strong> ${msg}</div>`;
        el.style.display = 'block';
        return;
    }

    const preview = inputText.length > 100 ? inputText.substring(0, 100) + '...' : inputText;
    const intentEs = INTENT_ES[data.intent] || data.intent;
    const sentimentEs = SENTIMENT_ES[data.sentiment] || data.sentiment;

    let salesHtml = '';
    if (data.sales_concepts && data.sales_concepts.length > 0) {
        salesHtml = '<ul class="concept-list">' +
            data.sales_concepts.map(c =>
                `<li class="concept-item">
                    <span class="concept-name">${translateConcept(c.concept, SALES_CONCEPTS_ES)}</span>
                    <span class="concept-conf">${Math.round(c.confidence*100)}%</span>
                </li>`
            ).join('') + '</ul>';
    } else {
        salesHtml = '<span class="empty-msg">Ninguno detectado</span>';
    }

    let reHtml = '';
    if (data.real_estate_concepts && data.real_estate_concepts.length > 0) {
        reHtml = '<ul class="concept-list">' +
            data.real_estate_concepts.map(c =>
                `<li class="concept-item">
                    <span class="concept-name">${translateConcept(c.concept, RE_CONCEPTS_ES)}</span>
                    <span class="concept-conf">${Math.round(c.confidence*100)}%</span>
                </li>`
            ).join('') + '</ul>';
    } else {
        reHtml = '<span class="empty-msg">Ninguno detectado</span>';
    }

    let entitiesHtml = '';
    if (data.entities && data.entities.length > 0) {
        // Group entities by concept
        const grouped = {};
        data.entities.forEach(e => {
            if (!grouped[e.concept]) grouped[e.concept] = [];
            grouped[e.concept].push(e);
        });

        // Render order: core first, then extended
        const order = ['price', 'area_sqm', 'bedrooms', 'bathrooms', 'location', 'date', 'schedule', 'percentage', 'contact', 'action', 'role', 'condition'];
        const sortedKeys = Object.keys(grouped).sort((a, b) => {
            const ia = order.indexOf(a), ib = order.indexOf(b);
            return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
        });

        entitiesHtml = sortedKeys.map(concept => {
            const items = grouped[concept];
            const icon = ENTITY_ICONS[concept] || '📎';
            const label = translateConcept(concept, ENTITY_ES);

            // Group duplicate raw_values and count them
            const valueCounts = {};
            items.forEach(e => {
                const key = e.raw_value.toLowerCase().trim();
                if (!valueCounts[key]) {
                    valueCounts[key] = { entity: e, count: 0 };
                }
                valueCounts[key].count++;
            });

            const valuesHtml = Object.values(valueCounts).map(({entity: e, count}) => {
                let numStr = '';
                if (e.numeric_value !== null) {
                    numStr = ` → <span class="entity-numeric">${e.numeric_value.toLocaleString()}${e.unit ? ' ' + e.unit : ''}</span>`;
                }
                const countBadge = count > 1 ? ` <span class="entity-count-badge">${count}x</span>` : '';
                const safeValue = e.raw_value.replace(/'/g, "\\'");
                return `<span class="entity-value-chip entity-clickable" onclick="highlightEntityInText('${safeValue}')">"${e.raw_value}"${numStr}${countBadge}</span>`;
            }).join('');
            return `<div class="entity-group">
                <div class="entity-group-header">${icon} ${label}</div>
                <div class="entity-group-values">${valuesHtml}</div>
            </div>`;
        }).join('');
    } else {
        entitiesHtml = '<span class="empty-msg">Ninguna detectada</span>';
    }

    // Build extended data section
    const c = data.commercial || {};
    let extDataHtml = '';
    if (c) {
        const funnelLabels = {
            'AWARENESS': '🔍 Conocimiento', 'CONSIDERATION': '⚖️ Evaluacion',
            'DECISION': '🎯 Decision', 'CLOSED': '✅ Cerrado'
        };
        const urgLabels = {
            'BAJA': '🟢 Baja', 'MEDIA': '🟡 Media', 'ALTA': '🟠 Alta', 'CRITICA': '🔴 Critica'
        };
        const compLabels = {
            'BAJO': '⬜ Bajo', 'MEDIO': '🟨 Medio', 'ALTO': '🟩 Alto'
        };
        const opLabels = {
            'VENTA': '🏷️ Compra-Venta', 'ALQUILER': '🔑 Alquiler',
            'INVERSION': '📈 Inversion', 'INDEFINIDO': '—'
        };
        const finLabels = {
            'CONTADO': '💵 Contado', 'CREDITO': '🏦 Credito',
            'FINANCIAMIENTO_DIRECTO': '🤝 Directo', 'NO_DETECTADO': '—'
        };

        // Build detailed explanations for each pill
        const funnelDetail = {
            'AWARENESS': {
                desc: 'El cliente esta en la etapa inicial. Aun no conoce bien la oferta ni ha mostrado interes concreto.',
                signals: 'No hay indicios de cierre ni respuestas afirmativas claras.',
                action: 'Presentar la propuesta de valor, generar interes y calificar al prospecto.',
                progress: 10
            },
            'CONSIDERATION': {
                desc: 'El cliente esta evaluando opciones activamente. Muestra interes pero aun no decide.',
                signals: 'Se detectan indicios de prospeccion, objeciones o respuestas positivas iniciales.',
                action: 'Resolver dudas, enviar comparables, mostrar beneficios diferenciadores.',
                progress: 50
            },
            'DECISION': {
                desc: 'El cliente esta muy cerca de tomar una decision. Las senales de cierre son claras.',
                signals: 'Indicios de cierre presentes, respuestas afirmativas y/o alta probabilidad.',
                action: 'Presentar propuesta final, crear urgencia y facilitar el cierre.',
                progress: 80
            },
            'CLOSED': {
                desc: 'La operacion esta cerrada o practicamente cerrada.',
                signals: 'Acuerdo alcanzado, firma realizada o precio final acordado.',
                action: 'Gestionar post-venta, solicitar referidos y mantener la relacion.',
                progress: 100
            }
        };

        const urgenciaDetail = {
            'BAJA': {
                desc: 'No se detectan senales de urgencia en el texto. El cliente no tiene prisa.',
                signals: 'Sin menciones de tiempo, plazos o inmediatez.',
                action: 'Crear urgencia con escasez o beneficios por tiempo limitado.',
                progress: 15
            },
            'MEDIA': {
                desc: 'Hay alguna senal de urgencia moderada. El cliente tiene cierta prisa.',
                signals: 'Menciones aisladas de tiempo o plazos.',
                action: 'Reforzar la urgencia y facilitar el proceso para no perder momentum.',
                progress: 45
            },
            'ALTA': {
                desc: 'Multiples senales de urgencia. El cliente necesita resolver pronto.',
                signals: 'Varias menciones de inmediatez, plazos cortos o necesidad rapida.',
                action: 'Actuar rapido, simplificar pasos y ofrecer solucion inmediata.',
                progress: 75
            },
            'CRITICA': {
                desc: 'Urgencia maxima. El cliente necesita una solucion ya.',
                signals: 'Multiples palabras de urgencia: hoy, ahora, urgente, inmediato.',
                action: 'Priorizar este lead. Responder de inmediato y cerrar hoy si es posible.',
                progress: 95
            }
        };

        const compromisoDetail = {
            'BAJO': {
                desc: 'El cliente muestra poco compromiso. Hay mas evasivas que confirmaciones.',
                signals: 'Frases como "tengo que pensar", "despues", "no estoy seguro".',
                action: 'No presionar. Nutrir con informacion y hacer seguimiento suave.',
                progress: 20
            },
            'MEDIO': {
                desc: 'Compromiso moderado. Hay senales positivas pero tambien dudas.',
                signals: 'Mezcla de confirmaciones y evasivas. Interes real pero con reservas.',
                action: 'Resolver las dudas especificas y reforzar los beneficios clave.',
                progress: 55
            },
            'ALTO': {
                desc: 'Alto compromiso. El cliente esta decidido y muestra disposicion clara.',
                signals: 'Multiples confirmaciones: "acepto", "listo", "de acuerdo", "vamos".',
                action: 'Aprovechar el momento. Facilitar el cierre y no agregar friccion.',
                progress: 90
            }
        };

        const operacionDetail = {
            'VENTA': {
                desc: 'Se trata de una operacion de compra-venta de inmueble.',
                signals: 'Palabras detectadas: venta, vender, comprar, adquirir.',
                action: 'Enfocar en precio, condiciones de pago y documentacion legal.',
                icon: '🏷️'
            },
            'ALQUILER': {
                desc: 'Se trata de una operacion de alquiler o arrendamiento.',
                signals: 'Palabras detectadas: alquiler, renta, arrendamiento, inquilino.',
                action: 'Enfocar en plazo, condiciones del contrato y garantias.',
                icon: '🔑'
            },
            'INVERSION': {
                desc: 'El cliente busca una oportunidad de inversion inmobiliaria.',
                signals: 'Palabras detectadas: inversion, invertir, rentabilidad, retorno.',
                action: 'Presentar numeros: ROI, rentabilidad, plusvalia y proyecciones.',
                icon: '📈'
            },
            'INDEFINIDO': {
                desc: 'No se pudo determinar el tipo de operacion con claridad.',
                signals: 'No se detectaron palabras clave de ningun tipo de operacion.',
                action: 'Preguntar directamente al cliente que tipo de operacion busca.',
                icon: '❓'
            }
        };

        const financDetail = {
            'CONTADO': {
                desc: 'El cliente menciona pago de contado o en efectivo.',
                signals: 'Palabras detectadas: contado, cash, efectivo, pago completo.',
                action: 'Ofrecer descuento por pago de contado. Agilizar el cierre.',
                icon: '💵'
            },
            'CREDITO': {
                desc: 'Se menciona financiamiento bancario o hipotecario.',
                signals: 'Palabras detectadas: credito, hipoteca, banco, prestamo, pre-aprobado.',
                action: 'Verificar pre-aprobacion, coordinar con el banco y ajustar plazos.',
                icon: '🏦'
            },
            'FINANCIAMIENTO_DIRECTO': {
                desc: 'Se menciona financiamiento directo del vendedor o pago en cuotas.',
                signals: 'Palabras detectadas: cuotas, facilidades de pago, plan de pago.',
                action: 'Definir condiciones: enganche, plazo, tasa y garantias.',
                icon: '🤝'
            },
            'NO_DETECTADO': {
                desc: 'No se detecto mencion de forma de pago o financiamiento.',
                signals: 'Sin palabras clave de financiamiento en el texto.',
                action: 'Preguntar al cliente como planea financiar la operacion.',
                icon: '—'
            }
        };

        const fd = funnelDetail[c.etapa_funnel] || funnelDetail['AWARENESS'];
        const ud = urgenciaDetail[c.urgencia] || urgenciaDetail['BAJA'];
        const cd = compromisoDetail[c.nivel_compromiso] || compromisoDetail['BAJO'];
        const od = operacionDetail[c.tipo_operacion] || operacionDetail['INDEFINIDO'];
        const fid = financDetail[c.financiamiento] || financDetail['NO_DETECTADO'];

        extDataHtml = `
            <div class="ext-data-grid">
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-funnel')">
                    <span class="ext-pill-label">Funnel</span>
                    <span class="ext-pill-value">${funnelLabels[c.etapa_funnel] || c.etapa_funnel || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-urgencia')">
                    <span class="ext-pill-label">Urgencia</span>
                    <span class="ext-pill-value">${urgLabels[c.urgencia] || c.urgencia || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-compromiso')">
                    <span class="ext-pill-label">Compromiso</span>
                    <span class="ext-pill-value">${compLabels[c.nivel_compromiso] || c.nivel_compromiso || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-operacion')">
                    <span class="ext-pill-label">Operacion</span>
                    <span class="ext-pill-value">${opLabels[c.tipo_operacion] || c.tipo_operacion || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
                <div class="ext-data-pill ext-pill-clickable" onclick="toggleExtDetail('ext-detail-financ')">
                    <span class="ext-pill-label">Financiamiento</span>
                    <span class="ext-pill-value">${finLabels[c.financiamiento] || c.financiamiento || '—'}</span>
                    <span class="ext-pill-arrow">&#9660;</span>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-funnel">
                <div class="ext-detail-header">🎯 Etapa del Funnel: <strong>${c.etapa_funnel}</strong></div>
                <div class="ext-detail-progress"><div class="ext-detail-progress-fill" style="width:${fd.progress}%"></div></div>
                <div class="ext-detail-stages">
                    <span class="${c.etapa_funnel === 'AWARENESS' ? 'stage-active' : ''}">Awareness</span>
                    <span class="${c.etapa_funnel === 'CONSIDERATION' ? 'stage-active' : ''}">Consideration</span>
                    <span class="${c.etapa_funnel === 'DECISION' ? 'stage-active' : ''}">Decision</span>
                    <span class="${c.etapa_funnel === 'CLOSED' ? 'stage-active' : ''}">Closed</span>
                </div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${fd.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${fd.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${fd.action}</div>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-urgencia">
                <div class="ext-detail-header">⏱️ Nivel de Urgencia: <strong>${c.urgencia}</strong></div>
                <div class="ext-detail-progress"><div class="ext-detail-progress-fill ext-progress-urgencia" style="width:${ud.progress}%"></div></div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${ud.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${ud.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${ud.action}</div>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-compromiso">
                <div class="ext-detail-header">🤝 Nivel de Compromiso: <strong>${c.nivel_compromiso}</strong></div>
                <div class="ext-detail-progress"><div class="ext-detail-progress-fill ext-progress-compromiso" style="width:${cd.progress}%"></div></div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${cd.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${cd.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${cd.action}</div>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-operacion">
                <div class="ext-detail-header">${od.icon} Tipo de Operacion: <strong>${c.tipo_operacion}</strong></div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${od.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${od.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${od.action}</div>
                </div>
            </div>

            <div class="ext-detail-panel" id="ext-detail-financ">
                <div class="ext-detail-header">${fid.icon} Financiamiento: <strong>${c.financiamiento.replace('_', ' ')}</strong></div>
                <div class="ext-detail-body">
                    <div class="ext-detail-desc">${fid.desc}</div>
                    <div class="ext-detail-item"><strong>Senales detectadas:</strong> ${fid.signals}</div>
                    <div class="ext-detail-item"><strong>Que hacer:</strong> ${fid.action}</div>
                </div>
            </div>
        `;

        // Señales de compra
        if (c.senales_compra && c.senales_compra.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">🛒 Senales de compra</span>
                <div class="ext-row-tags">${c.senales_compra.map(s => `<span class="ext-tag ext-tag-green">${s}</span>`).join('')}</div>
            </div>`;
        }

        // Objeciones específicas
        if (c.objeciones_especificas && c.objeciones_especificas.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">⚠️ Objeciones</span>
                <div class="ext-row-tags">${c.objeciones_especificas.map(o => `<span class="ext-tag ext-tag-red">${o}</span>`).join('')}</div>
            </div>`;
        }

        // Técnicas de persuasión
        if (c.tecnicas_persuasion && c.tecnicas_persuasion.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">🧠 Persuasion</span>
                <div class="ext-row-tags">${c.tecnicas_persuasion.map(t => `<span class="ext-tag ext-tag-purple">${t}</span>`).join('')}</div>
            </div>`;
        }

        // Preguntas abiertas
        if (c.preguntas_abiertas && c.preguntas_abiertas.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">❓ Preguntas abiertas</span>
                <div class="ext-row-questions">${c.preguntas_abiertas.map(q => `<div class="ext-question">"${q}"</div>`).join('')}</div>
            </div>`;
        }

        // Keywords
        if (c.keywords && c.keywords.length > 0) {
            extDataHtml += `<div class="ext-data-row">
                <span class="ext-row-label">🔑 Keywords</span>
                <div class="ext-row-tags">${c.keywords.map(k => `<span class="ext-tag ext-tag-blue">${k}</span>`).join('')}</div>
            </div>`;
        }

        // Resumen
        if (c.resumen) {
            extDataHtml += `<div class="ext-data-row ext-summary-row">
                <span class="ext-row-label">📋 Resumen del analisis</span>
                <div class="ext-summary-text">${c.resumen}</div>
            </div>`;
        }

        // Acción siguiente
        if (c.accion_siguiente) {
            extDataHtml += `<div class="ext-data-row ext-action-row">
                <span class="ext-row-label">▶️ Accion siguiente</span>
                <div class="ext-action-text">${c.accion_siguiente}</div>
            </div>`;
        }
    }

    // Build intent detail panel
    const intentDetail = {
        'OFFER': {
            icon: '🏷️',
            desc: 'El texto contiene una oferta activa. Alguien esta presentando una propiedad o servicio para la venta.',
            meaning: 'El emisor esta en modo de venta activa, presentando precio, condiciones o disponibilidad de un inmueble.',
            forSeller: 'Si eres el vendedor: tu mensaje esta bien posicionado como oferta. Asegurate de incluir precio, ubicacion y diferenciadores. Si eres el comprador: evalua si la oferta se ajusta a tus necesidades.',
            tips: ['Incluir precio claro y condiciones', 'Destacar beneficios unicos de la propiedad', 'Crear sentido de urgencia si es posible', 'Facilitar el siguiente paso (visita, llamada)'],
            nextStep: 'Esperar respuesta del prospecto. Si no responde en 24-48hs, hacer seguimiento.'
        },
        'INQUIRY': {
            icon: '❓',
            desc: 'El texto contiene preguntas o solicitudes de informacion. Alguien quiere saber mas.',
            meaning: 'El emisor esta interesado pero necesita mas datos antes de avanzar. Esta en etapa de evaluacion.',
            forSeller: 'El prospecto esta mostrando interes real. Cada pregunta es una oportunidad para acercarlo al cierre. Responde rapido y con informacion completa.',
            tips: ['Responder todas las preguntas de forma clara y completa', 'Agregar informacion adicional que anticipe futuras dudas', 'Incluir fotos, planos o documentos relevantes', 'Proponer una visita o llamada para profundizar'],
            nextStep: 'Responder con toda la informacion solicitada y proponer una accion concreta (visita, llamada).'
        },
        'NEGOTIATION': {
            icon: '⚖️',
            desc: 'El texto contiene elementos de negociacion. Se estan discutiendo terminos, precios o condiciones.',
            meaning: 'Las partes estan activamente negociando. Esto indica interes real y cercania al cierre.',
            forSeller: 'La negociacion es una senal muy positiva: el cliente quiere comprar, solo esta ajustando condiciones. No pierdas este momentum.',
            tips: ['Mantener firmeza en los puntos clave pero mostrar flexibilidad en secundarios', 'Ofrecer alternativas en vez de solo decir no', 'Crear urgencia: "esta oferta es valida hasta..."', 'Buscar el win-win para cerrar mas rapido'],
            nextStep: 'Presentar contraoferta o aceptar condiciones. No dejar pasar mas de 24hs sin responder.'
        },
        'CLOSING': {
            icon: '✅',
            desc: 'El texto indica que se esta cerrando o ya se cerro una operacion. Hay acuerdo entre las partes.',
            meaning: 'La venta esta practicamente cerrada. Se mencionan firmas, acuerdos finales o confirmaciones.',
            forSeller: 'Felicidades, estas en la recta final. Asegurate de que todos los documentos esten en orden y no haya sorpresas de ultimo momento.',
            tips: ['Confirmar todos los terminos por escrito', 'Coordinar firma y entrega de documentos', 'Preparar la documentacion legal necesaria', 'Planificar el seguimiento post-venta y solicitar referidos'],
            nextStep: 'Coordinar firma, verificar documentacion y planificar entrega. Solicitar referidos.'
        },
        'DESCRIPTION': {
            icon: '📝',
            desc: 'El texto es principalmente descriptivo. Detalla caracteristicas de una propiedad o situacion.',
            meaning: 'Se esta presentando informacion factual sobre un inmueble: metraje, habitaciones, ubicacion, amenidades.',
            forSeller: 'Las descripciones son la base de la venta. Asegurate de que sean atractivas, completas y destaquen los diferenciadores.',
            tips: ['Destacar los 3-5 beneficios principales primero', 'Usar numeros concretos (m2, habitaciones, precio)', 'Incluir la ubicacion y sus ventajas', 'Mencionar amenidades y valor agregado'],
            nextStep: 'Compartir la descripcion con prospectos calificados y medir el interes generado.'
        },
        'UNKNOWN': {
            icon: '🔍',
            desc: 'No se pudo determinar una intencion clara del texto con suficiente confianza.',
            meaning: 'El texto puede ser ambiguo, muy corto, o no encaja claramente en ninguna categoria de venta.',
            forSeller: 'El texto no tiene una intencion comercial clara. Puede ser una conversacion casual o un mensaje incompleto.',
            tips: ['Revisar si el texto esta completo', 'Buscar el contexto de la conversacion', 'Hacer preguntas para clarificar la intencion del interlocutor'],
            nextStep: 'Solicitar mas contexto o informacion al interlocutor.'
        }
    };

    const iDetail = intentDetail[data.intent] || intentDetail['UNKNOWN'];

    el.innerHTML = `
        <div class="input-preview">"${preview}"</div>
        <div class="result-grid">
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('intencion-content')">
                    Intencion del Texto &nbsp;<span class="card-arrow" id="intencion-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Clasifica la intencion principal del texto: si es una oferta, consulta, negociacion, cierre o descripcion. Ayuda a entender en que etapa de la venta esta la conversacion.</div>
                </div>
                <div class="card-collapsible-content" id="intencion-content">
                    <span class="badge badge-${data.intent}">${intentEs}</span>
                    ${confBar(data.intent_confidence)}
                    <div class="intent-detail-panel">
                        <div class="intent-detail-header">${iDetail.icon} ${intentEs}</div>
                        <div class="intent-detail-desc">${iDetail.desc}</div>
                        <div class="intent-detail-section">
                            <div class="intent-section-title">Que significa para la venta</div>
                            <div class="intent-section-text">${iDetail.meaning}</div>
                            <div class="src-toggle-inline" data-section="meaning">▼</div>
                            <div class="src-fragment-inline" style="display:none;"></div>
                        </div>
                        <div class="intent-detail-section intent-seller-box">
                            <div class="intent-section-title">👤 Para el vendedor</div>
                            <div class="intent-section-text">${iDetail.forSeller}</div>
                            <div class="src-toggle-inline" data-section="seller">▼</div>
                            <div class="src-fragment-inline" style="display:none;"></div>
                        </div>
                        <div class="intent-detail-section">
                            <div class="intent-section-title">💡 Tips practicos</div>
                            <ul class="intent-tips-list">
                                ${iDetail.tips.map(t => `<li>${t}</li>`).join('')}
                            </ul>
                            <div class="src-toggle-inline" data-section="tips">▼</div>
                            <div class="src-fragment-inline" style="display:none;"></div>
                        </div>
                        <div class="intent-detail-section intent-next-step">
                            <div class="intent-section-title">▶️ Siguiente paso</div>
                            <div class="intent-section-text">${iDetail.nextStep}</div>
                            <div class="src-toggle-inline" data-section="next">▼</div>
                            <div class="src-fragment-inline" style="display:none;"></div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('sentimiento-content')">
                    Sentimiento &nbsp;<span class="card-arrow" id="sentimiento-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Evalua el tono emocional del texto: positivo, neutral o negativo. Indica si el cliente esta contento, indiferente o insatisfecho con la propuesta.</div>
                </div>
                <div class="card-collapsible-content" id="sentimiento-content">
                    <span class="badge badge-${data.sentiment}">${sentimentEs}</span>
                    ${confBar(data.sentiment_confidence)}
                    ${renderSentimentDetail(data.sentiment)}
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('ventas-content')">
                    Conceptos de Ventas Detectados &nbsp;<span class="card-arrow" id="ventas-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Detecta conceptos del proceso de venta: ofertas, descuentos, comisiones, cierres, prospectos, objeciones, seguimiento y negociacion. Muestra los fragmentos del texto donde se identificaron.</div>
                </div>
                <div class="card-collapsible-content" id="ventas-content">
                    ${salesHtml}
                    ${renderSalesConceptsDetail(data.sales_concepts)}
                </div>
            </div>
            <div class="card">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('bienes-raices-content')">
                    Conceptos de Bienes Raices Detectados &nbsp;<span class="card-arrow" id="bienes-raices-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Identifica conceptos inmobiliarios: tipo de propiedad, precio, metraje, habitaciones, ubicacion, amenidades, zonificacion y estado. Extrae los fragmentos relevantes del texto.</div>
                </div>
                <div class="card-collapsible-content" id="bienes-raices-content">
                    ${reHtml}
                    ${renderRealEstateConceptsDetail(data.real_estate_concepts)}
                </div>
            </div>
            <div class="card full-width">
                <div class="card-title card-title-collapsible" onclick="toggleCardContent('datos-extraidos-content')">
                    Datos Extraidos del Texto &nbsp;<span class="card-arrow" id="datos-extraidos-arrow">&#9660;</span>
                    <span class="card-info-icon" onclick="event.stopPropagation()">!</span>
                    <div class="card-info-tooltip">Extrae datos concretos del texto: precios, metrajes, ubicaciones, fechas, horarios, porcentajes, acciones comprometidas y personas mencionadas. Haz clic en cada dato para verlo resaltado en el texto.</div>
                </div>
                <div class="card-collapsible-content" id="datos-extraidos-content">
                    ${entitiesHtml}
                    ${extDataHtml}
                </div>
            </div>
        </div>
        ${renderCommercial(data.commercial)}
        <div class="timestamp">Analizado el: ${data.analyzed_at}</div>
        ${renderSaveConfirmation(data)}
    `;
    el.style.display = 'block';
}

function renderCommercial(c) {
    if (!c) return '';

    const pct = c.probabilidad_cierre;
    const fillClass = pct > 70 ? 'prob-fill-hot' : pct > 40 ? 'prob-fill-warm' : 'prob-fill-cold';

    const indicators = [
        { key: 'palabras_positivas',    label: 'Palabras Positivas',     value: c.palabras_positivas,    cls: c.palabras_positivas > 0 ? 'positive' : '', color: '#5bf5a3' },
        { key: 'respuestas_afirmativas',label: 'Respuestas Afirmativas', value: c.respuestas_afirmativas, cls: c.respuestas_afirmativas > 0 ? 'positive' : '', color: '#7b9cff' },
        { key: 'indicios_cierre',       label: 'Indicios de Cierre',     value: c.indicios_cierre,       cls: c.indicios_cierre > 0 ? 'positive' : '', color: '#f5d75b' },
        { key: 'escasez_comercial',     label: 'Escasez Comercial',      value: c.escasez_comercial,     cls: '', color: '#f5a35b' },
        { key: 'pedidos_referidos',     label: 'Pedidos de Referidos',   value: c.pedidos_referidos,     cls: '', color: '#b38bff' },
        { key: 'objeciones',            label: 'Objeciones',             value: c.objeciones,            cls: c.objeciones > 2 ? 'highlight' : '', color: '#f55b5b' },
        { key: 'indicios_prospeccion',  label: 'Prospeccion',            value: c.indicios_prospeccion,  cls: '', color: '#5bd4f5' },
    ];

    const indicatorsHtml = indicators.map((ind, idx) => {
        const detail = c.detalle ? c.detalle[ind.key] : {};
        const hasDetail = detail && Object.keys(detail).length > 0;
        const detailId = 'detail-' + idx;
        const missingPanelId = 'missing-' + idx;

        // Pie chart data
        const totalFrases = (c.indicadores_total_frases || {})[ind.key] || 0;
        const catDetail = (c.indicadores_detalle_categorias || {})[ind.key] || {};
        const detectedCount = Object.values(catDetail).reduce((sum, arr) => sum + arr.length, 0);

        // Pie chart HTML — clickeable para mostrar frases faltantes
        let pieHtml = '';
        if (totalFrases > 0) {
            const piePct = Math.round((detectedCount / totalFrases) * 100);
            const deg = Math.round((piePct / 100) * 360);
            pieHtml = '<div class="pie-chart-click" data-missing="' + missingPanelId + '" style="position:relative;width:40px;height:40px;border-radius:50%;background:conic-gradient(' + ind.color + ' 0deg ' + deg + 'deg, #2a2a2a ' + deg + 'deg 360deg);display:flex;align-items:center;justify-content:center;margin:4px auto;cursor:pointer;" title="Click para ver frases faltantes"><div style="width:26px;height:26px;border-radius:50%;background:#0f1117;display:flex;align-items:center;justify-content:center;"><span style="font-size:0.55rem;color:#fff;font-weight:600;">' + piePct + '%</span></div></div>';
        }

        // Category detail panel — chips clickeables que resaltan en el texto
        let detailHtml = '';
        if (Object.keys(catDetail).length > 0) {
            const catRows = Object.entries(catDetail).map(([cat, phrases]) =>
                '<div style="margin-bottom:5px;"><div style="font-size:0.65rem;color:#aaa;font-weight:600;margin-bottom:2px;">' + cat.replace(/_/g, ' ') + ' (' + phrases.length + ')</div><div style="display:flex;flex-wrap:wrap;gap:3px;">' + phrases.map(p => '<span class="phrase-chip" data-word="' + p.replace(/"/g, '&quot;') + '" data-group="' + ind.key + '" style="background:#0d1a2a;border:1px solid #1a3a5c;color:' + ind.color + ';padding:1px 6px;border-radius:8px;font-size:0.6rem;cursor:pointer;">' + p + '</span>').join('') + '</div></div>'
            ).join('');
            detailHtml = '<div class="indicator-detail" id="' + detailId + '" style="border-left:3px solid ' + ind.color + ';">' + catRows + '</div>';
        } else if (hasDetail) {
            const rows = Object.entries(detail)
                .sort((a, b) => b[1] - a[1])
                .map(([word, count]) => {
                    return '<div class="detail-word-row phrase-chip" data-word="' + word.replace(/"/g, '&quot;') + '" data-group="' + ind.key + '" style="cursor:pointer;"><span class="detail-word">' + word + '</span><span class="detail-count">' + count + 'x</span></div>';
                }).join('');
            detailHtml = '<div class="indicator-detail" id="' + detailId + '" style="border-left:3px solid ' + ind.color + ';">' + rows + '</div>';
        } else {
            detailHtml = '<div class="indicator-detail" id="' + detailId + '"><span class="detail-empty">Ninguna detectada</span></div>';
        }

        // Missing phrases panel (shown on pie chart click)
        const allCats = INDICADOR_CATEGORIAS[ind.key] || {};
        let missingHtml = '';
        let totalMissing = 0;
        Object.entries(allCats).forEach(([cat, allPhrases]) => {
            const found = catDetail[cat] || [];
            const missing = allPhrases.filter(p => !found.includes(p));
            if (missing.length > 0) {
                totalMissing += missing.length;
                missingHtml += '<div style="margin-bottom:4px;"><div style="font-size:0.6rem;color:#888;font-weight:600;">' + cat.replace(/_/g, ' ') + '</div><div style="display:flex;flex-wrap:wrap;gap:3px;">' + missing.map(p => '<span style="background:#1a0d0d;border:1px solid #3a1a1a;color:#f55b5b;padding:1px 6px;border-radius:8px;font-size:0.55rem;">' + p + '</span>').join('') + '</div></div>';
            }
        });
        if (totalMissing === 0) {
            missingHtml = '<div style="font-size:0.6rem;color:#5bf5a3;">Todas las frases detectadas</div>';
        }
        const scrollStyle = totalMissing > 15 ? 'max-height:200px;overflow-y:auto;' : '';
        const missingPanel = '<div id="' + missingPanelId + '" style="display:none;margin-top:4px;padding:8px;background:#0a0c14;border:1px solid #2a1a1a;border-radius:8px;border-left:3px solid #f55b5b;' + scrollStyle + '"><div style="font-size:0.62rem;color:#f55b5b;font-weight:600;margin-bottom:4px;">Frases no detectadas (' + totalMissing + ')</div>' + missingHtml + '</div>';

        return `
        <div>
            <div class="indicator-item has-detail"
                 style="border-top: 2px solid ${ind.color}; position:relative;"
                 onclick="toggleDetail('${detailId}', this); highlightInText('${ind.key}');">
                <div class="indicator-label">${ind.label}</div>
                <div class="indicator-value ${ind.cls}">${ind.value}</div>
                ${pieHtml}
            </div>
            ${detailHtml}
            ${missingPanel}
        </div>`;
    }).join('');

    return `
    <div class="commercial-section">
        <div class="commercial-title" style="position:relative;">Analisis Comercial Inmobiliario
            <span class="card-info-icon" style="position:absolute; top:2px; right:0;">!</span>
            <div class="card-info-tooltip" style="top:22px; right:0;">Analiza indicadores comerciales de la conversacion: palabras positivas, respuestas afirmativas, indicios de cierre, objeciones y mas. Calcula la probabilidad de cierre y clasifica el lead.</div>
        </div>

        <div style="margin-bottom:4px;">
            <span class="lead-badge lead-${c.tipo_lead}" style="cursor:pointer;"
                  onclick="toggleLeadDetail('lead-detail-panel')">
                LEAD ${c.tipo_lead} &nbsp;&#9660;
            </span>
        </div>

        <div class="lead-detail-panel" id="lead-detail-panel">
            ${renderLeadDetail(c)}
        </div>

        <div style="display:flex; align-items:center; gap:16px; margin:12px 0; flex-wrap:wrap;">
            <div>
                <div style="font-size:0.75rem; color:#666; margin-bottom:2px;">Nivel de interes: <strong style="color:#aaa">${c.nivel_interes}</strong></div>
                <div style="font-size:0.75rem; color:#666;">Tendencia de cierre: <strong style="color:#aaa">${c.tendencia_cierre}</strong></div>
            </div>
        </div>

        <div class="prob-bar-container">
            <div class="prob-label">
                <span>Probabilidad de Cierre</span>
                <span class="prob-value">${pct.toFixed(1)}%</span>
            </div>
            <div class="prob-bar">
                <div class="prob-fill ${fillClass}" style="width:${pct}%"></div>
            </div>
        </div>

        <div style="font-size:0.7rem; color:#555; margin-bottom:8px;">
            Haz clic en cada indicador para ver el detalle y resaltar las palabras en el texto.
        </div>

        <div class="indicators-grid">${indicatorsHtml}</div>

        <div style="font-size:0.75rem; color:#555; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.06em;">Recomendacion</div>
        <div class="recomendacion-box">${c.recomendacion}</div>

        <div style="font-size:0.7rem; color:#444; margin-top:10px; text-align:right;">
            Densidad comercial: ${c.densidad_comercial.toFixed(4)} &nbsp;|&nbsp; Total palabras: ${c.total_palabras}
        </div>
    </div>`;
}

function renderLeadDetail(c) {
    if (!c.formula) return '';
    const f = c.formula;
    const pct = c.probabilidad_cierre;

    let gapHtml = '';
    if (c.tipo_lead === 'CALIENTE') {
        gapHtml = `<div class="lead-gap lead-gap-caliente">
            Este lead ya es CALIENTE. Proceder al cierre inmediatamente.
        </div>`;
    } else if (c.tipo_lead === 'TIBIO') {
        gapHtml = `<div class="lead-gap lead-gap-tibio">
            Para ser CALIENTE necesita superar 70%. Le faltan <strong>${f.para_caliente} puntos</strong>.
            Reforzar indicios de cierre y respuestas afirmativas.
        </div>`;
    } else {
        const gapTibio = f.para_tibio > 0
            ? `Para ser TIBIO necesita superar 40%. Le faltan <strong>${f.para_tibio} puntos</strong>.`
            : `Ya esta cerca del nivel TIBIO.`;
        gapHtml = `<div class="lead-gap lead-gap-frio">
            ${gapTibio} Nutrir con informacion y seguimiento activo.
        </div>`;
    }

    // Extended analysis sections
    const funnelLabels = {
        'AWARENESS': '🔍 Conocimiento inicial',
        'CONSIDERATION': '⚖️ Evaluando opciones',
        'DECISION': '🎯 Cerca de decidir',
        'CLOSED': '✅ Operacion cerrada'
    };
    const urgenciaLabels = {
        'BAJA': '🟢 Baja', 'MEDIA': '🟡 Media', 'ALTA': '🟠 Alta', 'CRITICA': '🔴 Critica'
    };
    const compromisoLabels = {
        'BAJO': '⬜ Bajo', 'MEDIO': '🟨 Medio', 'ALTO': '🟩 Alto'
    };
    const operacionLabels = {
        'VENTA': '🏷️ Compra-Venta', 'ALQUILER': '🔑 Alquiler',
        'INVERSION': '📈 Inversion', 'INDEFINIDO': '❓ No identificado'
    };
    const financLabels = {
        'CONTADO': '💵 Contado', 'CREDITO': '🏦 Credito/Hipoteca',
        'FINANCIAMIENTO_DIRECTO': '🤝 Financiamiento directo', 'NO_DETECTADO': '—'
    };

    let senalesHtml = '';
    if (c.senales_compra && c.senales_compra.length > 0) {
        senalesHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">🛒 Senales de compra</span>
            <div class="lead-ext-tags">${c.senales_compra.map(s => `<span class="tag-green">${s}</span>`).join('')}</div>
        </div>`;
    }

    let objeccionesEspHtml = '';
    if (c.objeciones_especificas && c.objeciones_especificas.length > 0) {
        objeccionesEspHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">⚠️ Objeciones detectadas</span>
            <div class="lead-ext-tags">${c.objeciones_especificas.map(o => `<span class="tag-red">${o}</span>`).join('')}</div>
        </div>`;
    }

    let persuasionHtml = '';
    if (c.tecnicas_persuasion && c.tecnicas_persuasion.length > 0) {
        persuasionHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">🧠 Tecnicas de persuasion</span>
            <div class="lead-ext-tags">${c.tecnicas_persuasion.map(t => `<span class="tag-purple">${t}</span>`).join('')}</div>
        </div>`;
    }

    let preguntasHtml = '';
    if (c.preguntas_abiertas && c.preguntas_abiertas.length > 0) {
        preguntasHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">❓ Preguntas abiertas</span>
            <div class="lead-ext-list">${c.preguntas_abiertas.map(q => `<div class="lead-question">"${q}"</div>`).join('')}</div>
        </div>`;
    }

    let keywordsHtml = '';
    if (c.keywords && c.keywords.length > 0) {
        keywordsHtml = `<div class="lead-extended-item">
            <span class="lead-ext-label">🔑 Keywords principales</span>
            <div class="lead-ext-tags">${c.keywords.map(k => `<span class="tag-blue">${k}</span>`).join('')}</div>
        </div>`;
    }

    return `
        <div class="lead-extended-grid">
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Etapa del Funnel</div>
                <div class="lead-ext-card-value">${funnelLabels[c.etapa_funnel] || c.etapa_funnel}</div>
            </div>
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Urgencia</div>
                <div class="lead-ext-card-value">${urgenciaLabels[c.urgencia] || c.urgencia}</div>
            </div>
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Compromiso</div>
                <div class="lead-ext-card-value">${compromisoLabels[c.nivel_compromiso] || c.nivel_compromiso}</div>
            </div>
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Tipo Operacion</div>
                <div class="lead-ext-card-value">${operacionLabels[c.tipo_operacion] || c.tipo_operacion}</div>
            </div>
            <div class="lead-ext-card">
                <div class="lead-ext-card-title">Financiamiento</div>
                <div class="lead-ext-card-value">${financLabels[c.financiamiento] || c.financiamiento}</div>
            </div>
        </div>

        ${senalesHtml}
        ${objeccionesEspHtml}
        ${persuasionHtml}
        ${preguntasHtml}
        ${keywordsHtml}

        ${c.resumen ? `<div class="lead-extended-item">
            <span class="lead-ext-label">📋 Resumen</span>
            <div class="lead-ext-summary">${c.resumen}</div>
        </div>` : ''}

        ${c.accion_siguiente ? `<div class="lead-extended-item lead-next-action">
            <span class="lead-ext-label">▶️ Accion siguiente recomendada</span>
            <div class="lead-ext-action">${c.accion_siguiente}</div>
        </div>` : ''}

        <div class="lead-formula-section">
            <div class="lead-ext-label" style="margin-bottom:8px;">📊 Formula de probabilidad</div>
            <div style="font-size:0.75rem; color:#666; margin-bottom:10px;">
                <code style="color:#4a6cf7; font-size:0.8rem;">(Indicios_Cierre x 5 + Respuestas_Afirm x 2 - Objeciones x 3) / Total_Palabras x 100</code>
            </div>
            <table class="formula-table">
                <tr class="positive-row">
                    <td>Indicios de Cierre</td>
                    <td>${c.indicios_cierre} x 5</td>
                    <td>+${f.indicios_cierre_pts}</td>
                </tr>
                <tr class="positive-row">
                    <td>Respuestas Afirmativas</td>
                    <td>${c.respuestas_afirmativas} x 2</td>
                    <td>+${f.respuestas_afirmativas_pts}</td>
                </tr>
                <tr class="negative-row">
                    <td>Objeciones</td>
                    <td>${c.objeciones} x 3</td>
                    <td>-${f.objeciones_pts}</td>
                </tr>
                <tr class="total-row">
                    <td colspan="2">Puntaje neto</td>
                    <td>${f.puntaje_neto}</td>
                </tr>
            </table>
            <div class="formula-result">
                <strong>(${f.puntaje_neto} / ${f.total_palabras} palabras) x 100 = ${pct.toFixed(2)}%</strong>
                <br>
                <span style="font-size:0.75rem;">
                    Umbral CALIENTE: &gt;70% &nbsp;|&nbsp; Umbral TIBIO: &gt;40% &nbsp;|&nbsp; FRIO: &lt;40%
                </span>
            </div>
            ${gapHtml}
        </div>
    `;
}

function toggleLeadDetail(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    panel.classList.toggle('open');
}

function toggleExtDetail(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    // Close other ext-detail panels
    document.querySelectorAll('.ext-detail-panel').forEach(p => {
        if (p.id !== panelId) p.classList.remove('open');
    });
    panel.classList.toggle('open');
}

function toggleCardContent(contentId) {
    const content = document.getElementById(contentId);
    if (!content) return;
    content.classList.toggle('closed');
    const arrow = document.getElementById(contentId.replace('-content', '-arrow'));
    if (arrow) arrow.classList.toggle('open');
}

function renderSaveConfirmation(data) {
    const months = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    const savedYear = data.year || new Date().getFullYear();
    const savedMonth = data.month || (new Date().getMonth() + 1);
    const monthName = months[savedMonth] || '';

    // Generate a default name from the first words of the text
    const defaultName = (data.input_text || '').substring(0, 40).replace(/[^a-zA-Z0-9áéíóúñÁÉÍÓÚÑ\s]/g, '').trim() + '...';

    let yearOptions = '';
    for (let y = 2026; y <= 2030; y++) {
        yearOptions += `<option value="${y}" ${y == savedYear ? 'selected' : ''}>${y}</option>`;
    }
    let monthOptions = '';
    for (let m = 1; m <= 12; m++) {
        monthOptions += `<option value="${m}" ${m == savedMonth ? 'selected' : ''}>${months[m]}</option>`;
    }

    return `
        <div class="save-confirmation">
            <div class="save-conf-main">
                <span class="save-conf-icon">📁</span>
                <span class="save-conf-text">Guardado en: <strong>${monthName} ${savedYear}</strong></span>
                <button class="save-conf-btn" onclick="toggleRelocate()">&#9998; Editar</button>
            </div>
            <div class="save-relocate-panel" id="relocatePanel">
                <div class="save-relocate-desc">Nombre del texto (para identificarlo):</div>
                <div class="save-name-row">
                    <input type="text" id="entryName" class="save-name-input" value="${defaultName}" placeholder="Nombre del texto...">
                </div>
                <div class="save-relocate-desc" style="margin-top:8px;">Periodo:</div>
                <div class="save-relocate-selects">
                    <select id="relocateYear">${yearOptions}</select>
                    <select id="relocateMonth">${monthOptions}</select>
                    <button class="save-relocate-confirm" onclick="saveWithName()">💾 Guardar</button>
                    <button class="save-delete-btn" onclick="deleteLastEntry()">🗑️ Eliminar</button>
                </div>
            </div>
        </div>
    `;
}

function toggleRelocate() {
    const panel = document.getElementById('relocatePanel');
    if (panel) panel.classList.toggle('open');
}

async function saveWithName() {
    const year = parseInt(document.getElementById('relocateYear').value);
    const month = parseInt(document.getElementById('relocateMonth').value);
    const name = document.getElementById('entryName').value.trim() || 'Sin nombre';
    const months = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];

    // Update the selectors at the top to match
    document.getElementById('selectYear').value = year;
    document.getElementById('selectMonth').value = month;

    const text = document.getElementById('textInput').value.trim();
    if (!text) return;

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, year, month, entry_name: name })
        });
        const data = await response.json();
        if (!data.error) {
            const confText = document.querySelector('.save-conf-text');
            if (confText) confText.innerHTML = `Guardado en: <strong>${months[month]} ${year}</strong> como "<em>${name}</em>"`;
            const panel = document.getElementById('relocatePanel');
            if (panel) panel.classList.remove('open');
            const btn = document.querySelector('.save-relocate-confirm');
            if (btn) {
                btn.textContent = '✓ Guardado';
                btn.style.background = '#1a4a2a';
                setTimeout(() => { btn.textContent = '💾 Guardar'; btn.style.background = ''; }, 2000);
            }
            if (typeof loadHistory === 'function') loadHistory();
            loadSavedTexts();
        }
    } catch(e) {
        console.error('Error saving:', e);
    }
}

function toggleSavedTexts() {
    // Legacy — now using dropdown select
    loadSavedTexts();
}

async function loadSavedTexts() {
    const year = document.getElementById('selectYear').value;
    const month = document.getElementById('selectMonth').value;

    // If admin has a user selected, use admin endpoint
    const userSelect = document.getElementById('selectUser');
    const adminUser = userSelect ? userSelect.value : '';

    // For admin: if no user selected, can't load texts
    if (userSelect && !adminUser) {
        const select = document.getElementById('selectText');
        const count = document.getElementById('savedTextsCount');
        if (select) select.innerHTML = '<option value="">-- Seleccionar usuario primero --</option>';
        if (count) count.textContent = '';
        return;
    }

    const url = adminUser
        ? `/admin/user-texts/${adminUser}?year=${year}&month=${month}`
        : `/saved-texts?year=${year}&month=${month}`;

    try {
        const response = await fetch(url);
        const data = await response.json();
        const select = document.getElementById('selectText');
        const count = document.getElementById('savedTextsCount');
        if (!select) return;

        // Clear existing options except the first placeholder
        select.innerHTML = '<option value="">-- Seleccionar texto --</option>';

        if (data.entries && data.entries.length > 0) {
            count.textContent = `(${data.entries.length})`;
            data.entries.forEach((e, i) => {
                const rawName = e.entry_name || (e.text || '').substring(0, 16) || 'Texto #' + (i+1);
                const name = rawName.length > 16 ? rawName.substring(0, 16) + '...' : rawName;
                const opt = document.createElement('option');
                opt.value = e.id;
                opt.textContent = name;
                select.appendChild(opt);
            });
        } else {
            count.textContent = '(0)';
        }
    } catch(e) {
        console.error('Error loading saved texts:', e);
    }
}

function onTextSelected(entryId) {
    if (!entryId) {
        document.getElementById('deleteTextBtn').style.display = 'none';
        return;
    }
    document.getElementById('deleteTextBtn').style.display = 'inline-block';
    loadSavedText(entryId);
}

async function deleteSelectedText() {
    const select = document.getElementById('selectText');
    const entryId = select.value;
    if (!entryId) return;
    const name = select.options[select.selectedIndex].textContent;
    if (!confirm('¿Eliminar "' + name + '"?')) return;
    try {
        const response = await fetch('/delete-entry/' + entryId, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            document.getElementById('deleteTextBtn').style.display = 'none';
            loadSavedTexts();
        } else {
            alert('No se pudo eliminar.');
        }
    } catch(e) {
        alert('Error: ' + e.message);
    }
}

async function loadSavedText(entryId) {
    // Load a saved text into the textarea for re-analysis
    try {
        const response = await fetch(`/saved-text/${entryId}`);
        const data = await response.json();
        if (data.text) {
            document.getElementById('textInput').value = data.text;
        }
    } catch(e) {
        console.error('Error loading text:', e);
    }
}

// ── ADMIN FUNCTIONS ──
function onStatsMonthChange() {
    const monthSelect = document.getElementById('statsMonth');
    const periodSelect = document.getElementById('statsPeriod');
    if (monthSelect.value) {
        // Specific month selected — disable period selector
        periodSelect.disabled = true;
        periodSelect.style.opacity = '0.4';
    } else {
        // No specific month — enable period selector
        periodSelect.disabled = false;
        periodSelect.style.opacity = '1';
    }
    loadAdminStats();
}

async function loadAdminUsers() {
    try {
        const resp = await fetch('/admin/users-list');
        if (!resp.ok) { console.error('admin/users-list failed:', resp.status); return; }
        const data = await resp.json();
        const select = document.getElementById('selectUser');
        const vendorSelect = document.getElementById('statsVendor');
        if (!data.users || !data.users.length) { console.error('No users returned'); return; }
        if (select) {
            data.users.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u;
                opt.textContent = u;
                select.appendChild(opt);
            });
        }
        if (vendorSelect) {
            data.users.forEach(u => {
                const opt = document.createElement('option');
                opt.value = u;
                opt.textContent = u;
                vendorSelect.appendChild(opt);
            });
        }
    } catch(e) { console.error('Error loading users:', e); }
}

async function loadAdminStats() {
    const vendorSelect = document.getElementById('statsVendor');
    const periodSelect = document.getElementById('statsPeriod');
    const monthSelect = document.getElementById('statsMonth');
    if (!vendorSelect || !periodSelect) return;

    const vendor = vendorSelect.value;
    const period = periodSelect.value;
    const specificMonth = monthSelect ? monthSelect.value : '';
    const container = document.getElementById('adminStatsContent');
    if (!container) return;

    // Build URL — _all means aggregate all users
    let url;
    if (vendor === '_all') {
        url = `/admin/stats/_all?period=${period}&year=2026`;
    } else {
        url = `/admin/stats/${vendor}?period=${period}&year=2026`;
    }
    if (specificMonth) {
        url += `&month=${specificMonth}`;
        url = url.replace(`period=${period}`, 'period=specific');
    }

    try {
        const resp = await fetch(url);
        if (!resp.ok) {
            container.innerHTML = '<div style="color:#f55b5b;font-size:0.8rem;">Error: ' + resp.status + ' - Verifica que estas logueado como admin.</div>';
            return;
        }
        const data = await resp.json();

        if (data.error) {
            container.innerHTML = '<div style="color:#f55b5b;font-size:0.8rem;">Error: ' + (data.error || 'desconocido') + '</div>';
            return;
        }

        if (data.entry_count === 0) {
            container.innerHTML = '<div style="color:#555;font-size:0.8rem;">No hay datos para este periodo.</div>';
            return;
        }

        const totals = data.totals;
        const total = Object.values(totals).reduce((s, v) => s + v, 0) || 1;
        const indicators = [
            { key: 'palabras_positivas', label: 'Positivas', color: '#5bf5a3' },
            { key: 'respuestas_afirmativas', label: 'Afirmativas', color: '#7b9cff' },
            { key: 'indicios_cierre', label: 'Cierre', color: '#f5d75b' },
            { key: 'escasez_comercial', label: 'Escasez', color: '#f5a35b' },
            { key: 'pedidos_referidos', label: 'Referidos', color: '#b38bff' },
            { key: 'objeciones', label: 'Objeciones', color: '#f55b5b' },
            { key: 'indicios_prospeccion', label: 'Prospeccion', color: '#5bd4f5' },
        ];

        // Build conic-gradient for 3D-style pie chart
        let gradientParts = [];
        let currentDeg = 0;
        indicators.forEach(ind => {
            const pct = (totals[ind.key] / total) * 360;
            gradientParts.push(`${ind.color} ${currentDeg}deg ${currentDeg + pct}deg`);
            currentDeg += pct;
        });

        const pieChart = `
            <div style="position:relative;width:180px;height:180px;border-radius:50%;background:conic-gradient(${gradientParts.join(',')});box-shadow:0 8px 20px rgba(0,0,0,0.4), inset 0 -4px 8px rgba(0,0,0,0.3);transform:rotateX(20deg);margin:0 auto;">
                <div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:80px;height:80px;border-radius:50%;background:#0f1117;display:flex;align-items:center;justify-content:center;">
                    <span style="font-size:0.7rem;color:#aaa;">${data.entry_count} textos</span>
                </div>
            </div>
        `;

        const legend = indicators.map(ind => {
            const pct = Math.round((totals[ind.key] / total) * 100);
            return `<div style="display:flex;align-items:center;gap:6px;font-size:0.7rem;">
                <div style="width:10px;height:10px;border-radius:2px;background:${ind.color};"></div>
                <span style="color:#aaa;">${ind.label}: ${totals[ind.key]} (${pct}%)</span>
            </div>`;
        }).join('');

        container.innerHTML = `
            <div style="text-align:center;">
                <div style="font-size:0.72rem;color:#888;margin-bottom:8px;">${username} — ${period} (${data.months.length} meses, ${data.entry_count} textos)</div>
                ${pieChart}
                <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:12px;">
                    ${legend}
                </div>
            </div>
        `;
    } catch(e) {
        container.innerHTML = '<div style="color:#f55b5b;font-size:0.8rem;">Error cargando estadisticas.</div>';
    }
}

async function deleteSavedText(entryId) {
    if (!confirm('Eliminar este texto del historial?')) return;
    try {
        const response = await fetch(`/delete-entry/${entryId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            loadSavedTexts();
            if (typeof loadHistory === 'function') loadHistory();
        }
    } catch(e) {
        console.error('Error deleting:', e);
    }
}

async function deleteLastEntry() {
    if (!confirm('¿Eliminar este texto del historial? Esta accion no se puede deshacer.')) return;

    try {
        const response = await fetch('/delete-last-entry', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.success) {
            // Hide the save confirmation
            const conf = document.querySelector('.save-confirmation');
            if (conf) {
                conf.innerHTML = '<div style="color:#f55b5b; font-size:0.8rem; padding:8px;">🗑️ Texto eliminado del historial.</div>';
                setTimeout(() => { conf.style.display = 'none'; }, 3000);
            }
            // Refresh history and saved texts
            if (typeof loadHistory === 'function') loadHistory();
            loadSavedTexts();
        } else {
            alert('No se pudo eliminar: ' + (data.message || 'Error desconocido'));
        }
    } catch(e) {
        console.error('Error deleting:', e);
    }
}

function srcToggle(section) {
    // Not used inline anymore — kept for compatibility
    return '';
}

function getRelevantFragments(section) {
    var text = window._lastInputText || '';
    if (!text || text.length < 50) return [];
    var keywords = [];
    if (section === 'meaning') keywords = ['precio', 'cuota', 'entrega', 'pesos', 'dolares', 'usd', 'oferta', 'promocion', 'descuento', 'negociar', 'condicion', 'monto', 'valor', 'costo'];
    else if (section === 'seller') keywords = ['vendedor', 'le ofrezco', 'tenemos', 'le puedo', 'podemos', 'le sugiero', 'le recomiendo', 'nuestra empresa', 'nuestro compromiso'];
    else if (section === 'tips') keywords = ['no se', 'pensar', 'duda', 'caro', 'lejos', 'problema', 'pero', 'no puedo', 'dificil', 'objecion', 'esperar'];
    else if (section === 'next') keywords = ['reserva', 'firma', 'cierre', 'agenda', 'coordin', 'miercoles', 'manana', 'visita', 'compromet', 'acepto', 'dale', 'perfecto'];
    else keywords = ['precio', 'cuota', 'terreno', 'lote', 'barrio'];

    var sentences = text.split(/[.!?]+/).filter(function(s) { return s.trim().length > 20; });
    var matches = [];
    for (var i = 0; i < sentences.length && matches.length < 3; i++) {
        var lower = sentences[i].toLowerCase();
        for (var j = 0; j < keywords.length; j++) {
            if (lower.indexOf(keywords[j]) >= 0) {
                var trimmed = sentences[i].trim().substring(0, 100);
                if (matches.indexOf(trimmed) < 0) matches.push(trimmed);
                break;
            }
        }
    }
    return matches;
}

function renderSentimentDetail(sentiment) {
    const details = {
        'POSITIVE': {
            icon: '😊',
            desc: 'El tono del texto es positivo. El emisor expresa satisfaccion, entusiasmo o aprobacion.',
            meaning: 'Un sentimiento positivo indica que el cliente esta contento, interesado o satisfecho con la propuesta. Es el mejor momento para avanzar.',
            forSeller: 'El cliente esta receptivo. Aprovecha este momento para proponer el siguiente paso: visita, oferta formal o cierre.',
            tips: ['Reforzar los puntos que generan entusiasmo', 'Proponer accion inmediata mientras el animo es alto', 'No sobre-vender: el cliente ya esta convencido', 'Solicitar referidos aprovechando la buena disposicion'],
            risk: 'Bajo. El cliente esta en buena disposicion.'
        },
        'NEUTRAL': {
            icon: '😐',
            desc: 'El tono del texto es neutral. No hay emociones fuertes ni positivas ni negativas.',
            meaning: 'Un sentimiento neutral puede indicar que el cliente esta evaluando friamente, es profesional en su comunicacion, o aun no se ha formado una opinion.',
            forSeller: 'El cliente no esta ni entusiasmado ni molesto. Necesitas generar emocion positiva: mostrar beneficios, crear urgencia o conectar emocionalmente.',
            tips: ['Hacer preguntas para descubrir motivaciones emocionales', 'Presentar beneficios que conecten con sus necesidades', 'Usar testimonios o casos de exito similares', 'No asumir desinteres: neutral no es negativo'],
            risk: 'Medio. Puede ir hacia cualquier lado. Necesita estimulo.'
        },
        'NEGATIVE': {
            icon: '😟',
            desc: 'El tono del texto es negativo. El emisor expresa insatisfaccion, preocupacion o rechazo.',
            meaning: 'Un sentimiento negativo indica problemas: objeciones no resueltas, expectativas no cumplidas o mala experiencia previa.',
            forSeller: 'Atencion: el cliente esta insatisfecho. Antes de vender, necesitas resolver el problema. Escucha activamente y valida sus preocupaciones.',
            tips: ['Escuchar sin interrumpir ni justificar', 'Validar la preocupacion del cliente', 'Ofrecer solucion concreta al problema planteado', 'No presionar la venta hasta resolver la objecion', 'Si es necesario, ofrecer alternativas o compensaciones'],
            risk: 'Alto. Riesgo de perder al cliente si no se maneja bien.'
        }
    };
    const d = details[sentiment] || details['NEUTRAL'];
    return `
        <div class="intent-detail-panel">
            <div class="intent-detail-header">${d.icon} Sentimiento: ${sentiment}</div>
            <div class="intent-detail-desc">${d.desc}</div>
            <div class="intent-detail-section">
                <div class="intent-section-title">Que significa para la venta</div>
                <div class="intent-section-text">${d.meaning}</div>
                <div class="src-toggle-inline" data-section="meaning">▼</div>
                <div class="src-fragment-inline" style="display:none;"></div>
            </div>
            <div class="intent-detail-section intent-seller-box">
                <div class="intent-section-title">👤 Para el vendedor</div>
                <div class="intent-section-text">${d.forSeller}</div>
                <div class="src-toggle-inline" data-section="seller">▼</div>
                <div class="src-fragment-inline" style="display:none;"></div>
            </div>
            <div class="intent-detail-section">
                <div class="intent-section-title">💡 Tips practicos</div>
                <ul class="intent-tips-list">
                    ${d.tips.map(t => `<li>${t}</li>`).join('')}
                </ul>
                <div class="src-toggle-inline" data-section="tips">▼</div>
                <div class="src-fragment-inline" style="display:none;"></div>
            </div>
            <div class="intent-detail-section" style="border-left:3px solid ${sentiment === 'NEGATIVE' ? '#f55b5b' : sentiment === 'POSITIVE' ? '#5bf5a3' : '#f5a35b'}">
                <div class="intent-section-title">⚠️ Nivel de riesgo</div>
                <div class="intent-section-text">${d.risk}</div>
                <div class="src-toggle-inline" data-section="tips">▼</div>
                <div class="src-fragment-inline" style="display:none;"></div>
            </div>
        </div>
    `;
}

function renderSalesConceptsDetail(concepts) {
    if (!concepts || concepts.length === 0) return '';
    const conceptInfo = {
        'offer': { icon: '🏷️', label: 'Oferta', desc: 'Se detecto una oferta comercial activa.', tip: 'Asegurate de que la oferta sea clara, con precio y condiciones. Facilita el siguiente paso.' },
        'discount': { icon: '🔖', label: 'Descuento', desc: 'Se menciona un descuento o reduccion de precio.', tip: 'Los descuentos crean urgencia. Establece un plazo limite para maximizar el efecto.' },
        'commission': { icon: '💼', label: 'Comision', desc: 'Se habla de comisiones o honorarios del agente.', tip: 'Transparencia en comisiones genera confianza. Deja claro quien paga que.' },
        'closing': { icon: '✅', label: 'Cierre', desc: 'Hay indicios de cierre de operacion.', tip: 'No agregues friccion. Facilita la firma y coordina todos los pasos finales.' },
        'prospect': { icon: '🎯', label: 'Prospecto', desc: 'Se menciona un prospecto o comprador potencial.', tip: 'Califica al prospecto: presupuesto, plazo, necesidades. No pierdas tiempo con no calificados.' },
        'objection': { icon: '🚫', label: 'Objecion', desc: 'Se detecto una objecion o preocupacion del cliente.', tip: 'Escucha la objecion completa, valida y responde con datos. Nunca ignores una objecion.' },
        'follow_up': { icon: '📞', label: 'Seguimiento', desc: 'Se menciona seguimiento o contacto futuro.', tip: 'El seguimiento es clave. Programa recordatorios y cumple siempre lo prometido.' },
        'negotiation': { icon: '⚖️', label: 'Negociacion', desc: 'Se estan negociando terminos o condiciones.', tip: 'Negocia con margen. Ten claro tu precio minimo y ofrece valor en vez de solo bajar precio.' }
    };
    let html = '<div class="concepts-detail-panel">';
    html += '<div class="concepts-detail-title">Detalle de conceptos detectados</div>';
    concepts.forEach(c => {
        const info = conceptInfo[c.concept] || { icon: '📎', label: c.concept, desc: 'Concepto detectado.', tip: 'Evaluar en contexto.' };
        const confPct = (c.confidence * 100).toFixed(0);
        html += `<div class="concept-detail-item">
            <div class="concept-detail-head">
                <span>${info.icon} <strong>${info.label}</strong></span>
                <span class="concept-conf">${confPct}%</span>
            </div>
            <div class="concept-detail-desc">${info.desc}</div>
            <div class="concept-detail-source">${c.source_text ? c.source_text.split(' /// ').map(f => '<div style="margin:3px 0; padding:3px 8px; background:#0a0c14; border-left:2px solid #4a6cf7; border-radius:3px;"><em>"' + f + '"</em></div>').join('') : '<em>Sin fragmento</em>'}</div>
            <div class="concept-detail-tip">💡 ${info.tip}</div>
        </div>`;
    });
    html += '</div>';
    return html;
}

function renderRealEstateConceptsDetail(concepts) {
    if (!concepts || concepts.length === 0) return '';
    const conceptInfo = {
        'property_type': { icon: '🏠', label: 'Tipo de propiedad', desc: 'Se identifica el tipo de inmueble.', tip: 'Adapta tu discurso al tipo de propiedad. Un apartamento se vende diferente a un terreno.' },
        'price': { icon: '💰', label: 'Precio', desc: 'Se menciona precio o valor del inmueble.', tip: 'Justifica el precio con comparables del mercado. Ten datos listos para respaldar.' },
        'area_sqm': { icon: '📐', label: 'Metraje', desc: 'Se menciona el area o superficie.', tip: 'Relaciona el metraje con el precio por m2 de la zona para mostrar valor.' },
        'bedrooms': { icon: '🛏️', label: 'Habitaciones', desc: 'Se menciona cantidad de habitaciones.', tip: 'Las habitaciones definen el perfil del comprador. Adapta tu pitch al tipo de familia.' },
        'bathrooms': { icon: '🚿', label: 'Banos', desc: 'Se menciona cantidad de banos.', tip: 'Banos adicionales agregan valor. Destaca si tiene bano en suite o de servicio.' },
        'location': { icon: '📍', label: 'Ubicacion', desc: 'Se menciona la ubicacion del inmueble.', tip: 'La ubicacion es el factor #1. Destaca cercanias: colegios, transporte, comercios.' },
        'amenities': { icon: '🏊', label: 'Amenidades', desc: 'Se mencionan amenidades o servicios.', tip: 'Las amenidades justifican precio premium. Calcula el ahorro vs. pagar gym/pool aparte.' },
        'zoning': { icon: '📋', label: 'Zonificacion', desc: 'Se menciona zonificacion o uso de suelo.', tip: 'La zonificacion define el potencial. Comercial = mas valor. Verifica restricciones.' },
        'condition': { icon: '🔧', label: 'Estado', desc: 'Se menciona el estado o condicion del inmueble.', tip: 'Se honesto con el estado. Si necesita arreglos, presenta presupuesto y descuenta del precio.' }
    };
    let html = '<div class="concepts-detail-panel">';
    html += '<div class="concepts-detail-title">Detalle de conceptos detectados</div>';
    concepts.forEach(c => {
        const info = conceptInfo[c.concept] || { icon: '📎', label: c.concept, desc: 'Concepto detectado.', tip: 'Evaluar en contexto.' };
        const confPct = (c.confidence * 100).toFixed(0);
        html += `<div class="concept-detail-item">
            <div class="concept-detail-head">
                <span>${info.icon} <strong>${info.label}</strong></span>
                <span class="concept-conf">${confPct}%</span>
            </div>
            <div class="concept-detail-desc">${info.desc}</div>
            <div class="concept-detail-source">${c.source_text ? c.source_text.split(' /// ').map(f => '<div style="margin:3px 0; padding:3px 8px; background:#0a0c14; border-left:2px solid #4a6cf7; border-radius:3px;"><em>"' + f + '"</em></div>').join('') : '<em>Sin fragmento</em>'}</div>
            <div class="concept-detail-tip">💡 ${info.tip}</div>
        </div>`;
    });
    html += '</div>';
    return html;
}

function highlightSingleWord(word, indicatorKey) {
    const textarea = document.getElementById('textInput');
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    const text = textarea.value;

    if (!text) return;

    // Build highlighted HTML for just this one word
    const highlightedHtml = buildHighlightedText(text, [word], indicatorKey);

    overlay.innerHTML = highlightedHtml;
    overlay.classList.add('active');
    closeBtn.classList.add('active');

    // Scroll to the textarea area only when clicking a specific word
    const wrapper = document.getElementById('textareaWrapper');
    wrapper.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function highlightEntityInText(rawValue) {
    const textarea = document.getElementById('textInput');
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    const text = textarea.value;

    if (!text) return;

    // Use a generic entity highlight class
    const highlightedHtml = buildHighlightedText(text, [rawValue], 'indicios_cierre');

    overlay.innerHTML = highlightedHtml;
    overlay.classList.add('active');
    closeBtn.classList.add('active');

    // Scroll to the textarea area
    const wrapper = document.getElementById('textareaWrapper');
    wrapper.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function highlightInText(indicatorKey) {
    const textarea = document.getElementById('textInput');
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    const text = textarea.value;

    if (!text || !_lastCommercialData || !_lastCommercialData.detalle) return;

    const detail = _lastCommercialData.detalle[indicatorKey];
    if (!detail || Object.keys(detail).length === 0) return;

    // Get the words to highlight for this indicator
    const words = Object.keys(detail);

    // Build highlighted HTML
    const highlightedHtml = buildHighlightedText(text, words, indicatorKey);

    overlay.innerHTML = highlightedHtml;
    overlay.classList.add('active');
    closeBtn.classList.add('active');

    // No scroll here — only scroll when clicking a specific word in the detail
}

function buildHighlightedText(text, words, indicatorKey) {
    // Normalize function to remove accents for matching
    function normalize(str) {
        return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    }

    const normalizedText = normalize(text);
    const hlClass = 'hl-' + indicatorKey;

    // Find all match positions
    let matches = [];
    for (const word of words) {
        // Special handling for "si" in respuestas_afirmativas:
        // Only highlight affirmative "si" (at sentence start + comma/period/exclamation)
        if (indicatorKey === 'respuestas_afirmativas' && word === 'si') {
            const affirmativePatterns = [
                /(?:^|[.!?\n]\s*)si(?:\s*[,.]|\s*$)/gim,
                /(?:^|[.!?\n]\s*)si,\s/gim,
                /(?:^|[.!?\n]\s*)si[.!]/gim,
            ];
            for (const pattern of affirmativePatterns) {
                let match;
                while ((match = pattern.exec(normalizedText)) !== null) {
                    // Find the actual "si" position within the match
                    const siIdx = match[0].toLowerCase().indexOf('si');
                    const start = match.index + siIdx;
                    matches.push({ start: start, end: start + 2 });
                }
            }
            continue;
        }

        const normalizedWord = normalize(word);
        // Use word boundary matching for short words, substring for long phrases
        const escapedWord = normalizedWord.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        let regex;
        if (normalizedWord.split(' ').length > 3) {
            // Long phrase: search as substring (no word boundaries)
            regex = new RegExp(escapedWord, 'gi');
        } else {
            regex = new RegExp('(?<![a-z])' + escapedWord + '(?![a-z])', 'gi');
        }
        let match;
        while ((match = regex.exec(normalizedText)) !== null) {
            matches.push({ start: match.index, end: match.index + match[0].length });
        }
    }

    // Sort by position and merge overlapping
    matches.sort((a, b) => a.start - b.start);
    const merged = [];
    for (const m of matches) {
        if (merged.length > 0 && m.start <= merged[merged.length - 1].end) {
            merged[merged.length - 1].end = Math.max(merged[merged.length - 1].end, m.end);
        } else {
            merged.push({ ...m });
        }
    }

    // Build HTML with highlights using original text characters
    let result = '';
    let lastIdx = 0;
    for (const m of merged) {
        // Add text before this match
        result += escapeHtml(text.substring(lastIdx, m.start));
        // Add highlighted match (use original text casing)
        result += `<span class="${hlClass}">${escapeHtml(text.substring(m.start, m.end))}</span>`;
        lastIdx = m.end;
    }
    result += escapeHtml(text.substring(lastIdx));

    return result;
}

function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function closeHighlightOverlay() {
    const overlay = document.getElementById('highlightOverlay');
    const closeBtn = document.getElementById('highlightCloseBtn');
    overlay.classList.remove('active');
    closeBtn.classList.remove('active');
}

function toggleDetail(detailId, cardEl) {
    const panel = document.getElementById(detailId);
    if (!panel) return;
    const isOpen = panel.classList.contains('open');
    panel.classList.toggle('open', !isOpen);
    cardEl.classList.toggle('expanded', !isOpen);
}

function toggleMissingPanel(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    const isVisible = panel.style.display !== 'none';
    // Close all other missing panels first
    document.querySelectorAll('[id^="missing-"]').forEach(p => { p.style.display = 'none'; });
    if (!isVisible) {
        panel.style.display = 'block';
    }
}

// Delegated click handler for pie charts (avoids inline onclick quote issues)
document.addEventListener('click', function(e) {
    const pie = e.target.closest('.pie-chart-click');
    if (pie) {
        e.stopPropagation();
        const panelId = pie.getAttribute('data-missing');
        if (panelId) toggleMissingPanel(panelId);
        return;
    }
    // Delegated click for phrase chips — highlight word in text
    const chip = e.target.closest('.phrase-chip');
    if (chip) {
        e.stopPropagation();
        const word = chip.getAttribute('data-word');
        const group = chip.getAttribute('data-group');
        if (word && group) highlightSingleWord(word, group);
        return;
    }
    // Delegated click for source toggles — show/hide text fragment
    const srcTog = e.target.closest('.source-toggle');
    if (srcTog) {
        const targetId = srcTog.getAttribute('data-target');
        if (targetId) {
            const frag = document.getElementById(targetId);
            if (frag) {
                frag.classList.toggle('open');
                const arrow = srcTog.querySelector('.src-arrow');
                if (arrow) arrow.textContent = frag.classList.contains('open') ? '▲' : '▼';
            }
        }
    }
    // Delegated click for inline source toggles (violet arrows)
    const inlineTog = e.target.closest('.src-toggle-inline');
    if (inlineTog) {
        const section = inlineTog.getAttribute('data-section');
        const fragEl = inlineTog.nextElementSibling;
        if (fragEl && fragEl.classList.contains('src-fragment-inline')) {
            if (fragEl.style.display === 'none') {
                // Populate with relevant fragments
                const fragments = getRelevantFragments(section);
                fragEl.innerHTML = fragments.map(f => '<span class="src-phrase phrase-chip" data-word="' + f.replace(/"/g, '&quot;') + '" data-group="intent">' + f.replace(/</g, '&lt;') + '</span>').join('');
                fragEl.style.display = 'block';
                inlineTog.textContent = '▲';
            } else {
                fragEl.style.display = 'none';
                inlineTog.textContent = '▼';
            }
        }
    }
});

// Allow Ctrl+Enter to submit, and auto-analyze after 2s of inactivity
document.addEventListener('DOMContentLoaded', () => {
    let debounceTimer = null;
    const textarea = document.getElementById('textInput');

    textarea.addEventListener('keydown', e => {
        if (e.ctrlKey && e.key === 'Enter') {
            clearTimeout(debounceTimer);
            analyze();
        }
    });

    textarea.addEventListener('input', () => {
        closeHighlightOverlay();
    });

    // Load on page load
    if (document.getElementById('selectUser')) {
        // Admin: users already in HTML via Jinja2, just load stats
        loadAdminStats();
    } else {
        // Regular user: load their texts
        loadSavedTexts();
    }
});

// ── History ───────────────────────────────────────────────────────────────

let historyOpen = false;

function toggleHistory() {
    historyOpen = !historyOpen;
    document.getElementById('historyTree').classList.toggle('open', historyOpen);
    document.getElementById('historyToggleIcon').textContent =
        historyOpen ? '▲ Ocultar historial' : '▼ Ver historial';
    if (historyOpen) loadHistory();
}

async function loadHistory() {
    try {
        const resp = await fetch('/history');
        const data = await resp.json();
        renderHistoryTree(data);
    } catch (e) {
        document.getElementById('historyEmpty').textContent = 'Error al cargar historial.';
    }
}

function renderHistoryTree(history) {
    const container = document.getElementById('historyTree');
    const emptyEl = document.getElementById('historyEmpty');

    const years = Object.keys(history).sort().reverse();
    if (years.length === 0) {
        emptyEl.style.display = 'block';
        emptyEl.textContent = 'Aun no hay analisis guardados.';
        return;
    }
    emptyEl.style.display = 'none';

    // Remove old rendered nodes (keep emptyEl)
    Array.from(container.children).forEach(c => {
        if (c.id !== 'historyEmpty') c.remove();
    });

    years.forEach(year => {
        const yearDiv = document.createElement('div');
        yearDiv.className = 'history-year';

        const months = Object.keys(history[year]).sort().reverse();
        let totalYear = 0;
        months.forEach(m => {
            Object.values(history[year][m]).forEach(w => {
                Object.values(w).forEach(d => { totalYear += (d.entries || []).length; });
            });
        });

        const yearLabel = document.createElement('div');
        yearLabel.className = 'history-year-label';
        yearLabel.innerHTML = `<span>&#128197; ${year}</span><span style="color:#555">${totalYear} analisis &#9660;</span>`;
        let yearOpen = true;
        const yearContent = document.createElement('div');

        yearLabel.onclick = () => {
            yearOpen = !yearOpen;
            yearContent.style.display = yearOpen ? '' : 'none';
            yearLabel.querySelector('span:last-child').innerHTML =
                `${totalYear} analisis ${yearOpen ? '&#9650;' : '&#9660;'}`;
        };

        yearDiv.appendChild(yearLabel);
        yearDiv.appendChild(yearContent);

        months.forEach(monthKey => {
            const monthDiv = document.createElement('div');
            monthDiv.className = 'history-month';

            const weeks = Object.keys(history[year][monthKey]).sort().reverse();
            let totalMonth = 0;
            weeks.forEach(w => {
                Object.values(history[year][monthKey][w]).forEach(d => {
                    totalMonth += (d.entries || []).length;
                });
            });

            const monthLabel = document.createElement('div');
            monthLabel.className = 'history-month-label';
            const mName = monthKey.split('-').slice(1).join('-');
            monthLabel.innerHTML = `<span>&#128198; ${mName}</span><span style="color:#444">${totalMonth} &#9660;</span>`;
            let monthOpen = false;
            const monthContent = document.createElement('div');
            monthContent.style.display = 'none';

            monthLabel.onclick = () => {
                monthOpen = !monthOpen;
                monthContent.style.display = monthOpen ? '' : 'none';
                monthLabel.querySelector('span:last-child').innerHTML =
                    `${totalMonth} ${monthOpen ? '&#9650;' : '&#9660;'}`;
            };

            monthDiv.appendChild(monthLabel);
            monthDiv.appendChild(monthContent);

            weeks.forEach(weekKey => {
                const weekDiv = document.createElement('div');
                weekDiv.className = 'history-week';

                const days = Object.keys(history[year][monthKey][weekKey]).sort().reverse();
                let totalWeek = 0;
                days.forEach(d => { totalWeek += (history[year][monthKey][weekKey][d].entries || []).length; });

                const weekLabel = document.createElement('div');
                weekLabel.className = 'history-week-label';
                weekLabel.innerHTML = `<span>&#128336; ${weekKey.replace('-', ' ')}</span><span style="color:#333">${totalWeek} &#9660;</span>`;
                let weekOpen = false;
                const weekContent = document.createElement('div');
                weekContent.style.display = 'none';

                weekLabel.onclick = () => {
                    weekOpen = !weekOpen;
                    weekContent.style.display = weekOpen ? '' : 'none';
                    weekLabel.querySelector('span:last-child').innerHTML =
                        `${totalWeek} ${weekOpen ? '&#9650;' : '&#9660;'}`;
                };

                weekDiv.appendChild(weekLabel);
                weekDiv.appendChild(weekContent);

                days.forEach(dayKey => {
                    const dayData = history[year][monthKey][weekKey][dayKey];
                    const dayDiv = document.createElement('div');
                    dayDiv.className = 'history-day';

                    const dayLabel = document.createElement('div');
                    dayLabel.className = 'history-day-label';
                    dayLabel.textContent = '📅 ' + (dayData.label || dayKey) +
                        ' — ' + (dayData.entries || []).length + ' analisis';
                    dayDiv.appendChild(dayLabel);

                    (dayData.entries || []).forEach(entry => {
                        const entryEl = document.createElement('div');
                        entryEl.className = 'history-entry';

                        const time = entry.timestamp
                            ? new Date(entry.timestamp).toLocaleTimeString('es', {hour:'2-digit', minute:'2-digit'})
                            : '';

                        const intentEs = INTENT_ES[entry.intent] || entry.intent || '';
                        const sentEs   = SENTIMENT_ES[entry.sentiment] || entry.sentiment || '';
                        const srcClass = entry.source === 'audio' ? 'source-audio' : 'source-text';
                        const srcLabel = entry.source === 'audio' ? '&#127908; Audio' : '&#128221; Texto';

                        entryEl.innerHTML = `
                            <div class="history-entry-header">
                                <div class="history-entry-badges">
                                    <span class="source-badge ${srcClass}">${srcLabel}</span>
                                    <span class="badge badge-${entry.intent}" style="font-size:0.7rem;padding:2px 8px;">${intentEs}</span>
                                    <span class="badge badge-${entry.sentiment}" style="font-size:0.7rem;padding:2px 8px;">${sentEs}</span>
                                </div>
                                <span class="history-entry-time">${time}</span>
                            </div>
                            <div class="history-entry-text">${entry.text || ''}</div>
                            <div class="history-entry-detail" id="hdet-${entry.id}">
                                ${entry.audio_filename ? '<div style="font-size:0.72rem;color:#a35bf5;margin-bottom:4px;">&#127908; ' + entry.audio_filename + '</div>' : ''}
                                <div style="margin-bottom:4px;"><strong style="color:#888">Texto completo:</strong><br>${entry.text_full || entry.text || ''}</div>
                                ${entry.commercial ? '<div style="font-size:0.72rem;color:#666;">Prob. cierre: <strong style="color:#e0e0e0">' + (entry.commercial.probabilidad_cierre || 0).toFixed(1) + '%</strong> &nbsp;|&nbsp; Lead: <strong style="color:#e0e0e0">' + (entry.commercial.tipo_lead || '') + '</strong></div>' : ''}
                            </div>
                        `;

                        entryEl.onclick = () => {
                            const det = document.getElementById('hdet-' + entry.id);
                            if (det) det.classList.toggle('open');
                        };

                        dayDiv.appendChild(entryEl);
                    });

                    weekContent.appendChild(dayDiv);
                });

                monthContent.appendChild(weekDiv);
            });

            yearContent.appendChild(monthDiv);
        });

        container.appendChild(yearDiv);
    });
}
