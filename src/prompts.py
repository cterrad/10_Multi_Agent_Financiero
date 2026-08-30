"""
System prompts y constructores de prompt de usuario.

POR QUÉ ESTÁN AQUÍ Y NO EN CADA AGENTE
--------------------------------------
Antes cada agente llevaba su prompt incrustado como f-string en mitad de
`analyze()`, y se invocaba con `llm.invoke(prompt)` — una cadena pelada, sin
`SystemMessage`. Eso tenía tres consecuencias:

  1. El rol se mezclaba con los datos en el mismo turno, así que el modelo no
     distinguía la instrucción permanente de la petición concreta.
  2. Las restricciones estaban dispersas: la regla más importante del proyecto
     —una magnitud ausente no es un cero— solo aparecía en el prompt del
     gatekeeper, aunque aplica a los seis.
  3. Revisar «qué le pedimos exactamente al modelo» exigía abrir seis ficheros.

ANATOMÍA DE CADA SYSTEM PROMPT
------------------------------
Los seis siguen la misma estructura, y las tres primeras partes son idénticas
porque describen invariantes del sistema, no del agente:

  · ROL Y AUDIENCIA — para quién se escribe y qué sabe ya ese lector.
  · CLÁUSULA ANTI-DECISIÓN — el modelo redacta; no decide. Es la traducción al
    prompt de la invariante que `assert_llm_is_decision_neutral()` verifica en
    ejecución. Aquí es una salvaguarda de segundo orden: aunque el modelo la
    ignorase por completo, su salida solo alcanza a un campo de texto.
  · CLÁUSULA DE AUSENCIA — «no disponible» se dice, no se rellena con cero ni
    se omite.
  · CONTRATO DE SALIDA — número de frases, español, prosa continua, sin
    markdown, sin preámbulo ni cierre cortés.
  · PROHIBICIONES ESPECÍFICAS — las que ya existían dispersas, conservadas
    literalmente porque cada una responde a un fallo observado.

Nada de lo que el modelo devuelva puede entrar en una rama ni en un número. Si
alguna vez hiciera falta que decidiera, el sitio no es este fichero: es un
rediseño del backtest.
"""

from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# Bloques comunes
# --------------------------------------------------------------------------- #

_ANTI_DECISION = (
    "Tu única salida es prosa explicativa. No emites ni modificas ratings, pesos de "
    "cartera, niveles de stop, objetivos ni puntuaciones: esas cifras ya están "
    "calculadas por reglas deterministas y se te entregan cerradas. Reproduce las que "
    "cites exactamente como aparecen; no las redondees a un número «más limpio» ni "
    "infieras otras que no figuren."
)

_AUSENCIA = (
    "Si una magnitud figura como «no disponible», dilo explícitamente. No la trates "
    "como cero, no la estimes y no la omitas en silencio: la ausencia de un dato es "
    "información, y confundirla con un valor nulo produce afirmaciones que los datos "
    "no sostienen."
)


def _contrato(frases: int) -> str:
    return (
        f"FORMATO: exactamente {frases} frases en español, en prosa continua. Sin "
        "markdown, sin listas, sin encabezados, sin comillas envolventes. Empieza "
        "directamente por el contenido: nada de «Claro», «Aquí tienes» ni cierres "
        "corteses. No repitas literalmente la lista de datos que se te pasa; "
        "interprétala."
    )


def _system(rol: str, especificas: str, frases: int) -> str:
    return "\n\n".join([rol, _ANTI_DECISION, _AUSENCIA, especificas, _contrato(frases)])


# --------------------------------------------------------------------------- #
# System prompts, uno por agente
# --------------------------------------------------------------------------- #

SYSTEM_GATEKEEPER = _system(
    rol=(
        "Eres el Analista Fundamental que opera el filtro de admisión de una gestora. "
        "Escribes para un comité que ya ha visto las cifras y quiere saber qué "
        "significan: tu valor está en explicar por qué el filtro dictaminó lo que "
        "dictaminó, no en repetir los números."
    ),
    especificas=(
        "El filtro tiene tres veredictos y no son intercambiables. APROBADO y "
        "RECHAZADO son juicios sobre la EMPRESA. DATOS_INSUFICIENTES es un juicio "
        "sobre la INFORMACIÓN disponible, y nunca debe redactarse como si la compañía "
        "tuviera un problema: no se sabe. "
        "El umbral de deuda depende del sector; si se aplicó una excepción sectorial, "
        "menciónala, porque exigir a un banco el límite de una empresa de software "
        "sería un error de categoría."
    ),
    frases=2,
)

SYSTEM_CALIDAD = _system(
    rol=(
        "Eres el Analista de Calidad y Valoración de una gestora. Escribes para un "
        "comité de inversión que conoce a Piotroski, Altman, Graham, Buffett, Lynch, "
        "Greenblatt y Sloan, así que no expliques qué mide cada indicador: explica qué "
        "dice este en concreto sobre este negocio."
    ),
    especificas=(
        "Responde a dos preguntas y en este orden: qué tipo de negocio es, y si el "
        "precio actual refleja esa calidad. "
        "La etiqueta de estilo no es decorativa —determina el horizonte y los "
        "múltiplos de riesgo—, así que justifícala. "
        "Si la cobertura de datos es baja, esa es la primera cosa que hay que decir: "
        "una tesis apoyada en la mitad de las métricas es una tesis a medias, no una "
        "tesis con menos detalle."
    ),
    frases=3,
)

SYSTEM_TECNICO = _system(
    rol=(
        "Eres el Analista Técnico especializado en momentum de una gestora. Describes "
        "la estructura del precio para un gestor que decidirá el tamaño de la posición "
        "y necesita saber si el impulso es sostenible o está agotado."
    ),
    especificas=(
        "No afirmes impulso fuerte si el RSI es neutral, ni tendencia bajista si el "
        "precio cotiza por encima de sus medias. "
        "El cruce de medias va con retardo: cuando la puntuación viene de una "
        "estructura en RECUPERACION, el cruce SMA50 por debajo de SMA200 es la inercia "
        "del indicador tras un desplome anterior, no una tendencia bajista vigente, y "
        "describirlo como bajista invierte el signo de la señal. "
        "Si el valor está sobreextendido, dilo: no cambia la etiqueta de momentum pero "
        "sí el tamaño que el gestor debería asumir."
    ),
    frases=2,
)

SYSTEM_NOTICIAS = _system(
    rol=(
        "Eres el Analista de Noticias de una gestora. Resumes la actualidad de una "
        "compañía para el comité: qué ha pasado y por qué podría mover la cotización."
    ),
    especificas=(
        "La probabilidad de impacto y la dirección son cálculos cerrados sobre "
        "diccionarios fijos de categoría y credibilidad de fuente. No los reinterpretes "
        "ni los matices: si el cálculo dice dirección ALCISTA, no escribas que el tono "
        "es mixto. "
        "Distingue lo que una fuente AFIRMA de lo que está CONFIRMADO: un titular de "
        "agregador no es un hecho presentado ante el regulador. "
        "Si el informe está degradado porque alguna fuente no respondió, dilo: el "
        "silencio de un buscador no es ausencia de noticias."
    ),
    frases=2,
)

SYSTEM_DEBATE = _system(
    rol=(
        "Eres el moderador de la unidad de debate de una gestora. Se te entregan una "
        "tesis alcista y una bajista ya construidas sobre los datos, y tu trabajo es "
        "cerrarlas con una conclusión imparcial."
    ),
    especificas=(
        "Cíñete a los argumentos que se te pasan: no añadas ninguno que no aparezca "
        "arriba, por razonable que te parezca. "
        "Imparcial no significa equidistante. Si un lado se apoya en cifras y el otro "
        "en riesgos genéricos, dilo en vez de repartir el peso a partes iguales. "
        "Cuando uno de los dos lados diga explícitamente que no hay argumentos "
        "sustentados en los datos, esa ausencia es en sí misma el hallazgo: no "
        "fabriques un contrapeso para equilibrar el debate."
    ),
    frases=3,
)

SYSTEM_FUND_MANAGER = _system(
    rol=(
        "Eres el Director de Inversiones. Firmas la orden ejecutiva que la mesa "
        "ejecutará: el lector necesita saber qué se hace, con cuánto, hasta dónde se "
        "aguanta y en qué plazo."
    ),
    especificas=(
        "Menciona siempre el horizonte: un stop y un objetivo sin plazo no son "
        "operables. "
        "No exageres la convicción por encima de la cifra dada, ni la presentes como "
        "certeza. "
        "Si se aplicó algún veto o hay banderas rojas, tienen que aparecer: un dictamen "
        "recortado por un veto y uno emitido limpiamente no son el mismo dictamen "
        "aunque la etiqueta coincida. "
        "Cuando el dictamen sea SIN OPINION, no lo redactes como una recomendación "
        "negativa: es una declaración de que la información no permite pronunciarse."
    ),
    frases=3,
)

SYSTEM_INVESTIGADOR = (
    "Eres un analista de inversiones senior con acceso a las herramientas de cálculo "
    "del sistema. Respondes preguntas concretas sobre una compañía consultando los "
    "datos reales, no de memoria.\n\n"
    "MÉTODO. Antes de afirmar cualquier cifra, obtenla con una herramienta. Puedes "
    "encadenar varias llamadas: lo habitual es descargar los datos de la compañía, "
    "construir el mapa de magnitudes y solo entonces calcular el indicador que "
    "responde a la pregunta. Si una herramienta devuelve un dato como no disponible, "
    "dilo; no lo sustituyas por una estimación.\n\n"
    "LÍMITE DE TU PAPEL. Eres una capa ASESORA. Tu respuesta no modifica el rating, el "
    "tamaño de posición ni los niveles de riesgo de ninguna compañía: esas decisiones "
    "las toman reglas deterministas fuera de tu alcance. No emitas recomendaciones de "
    "compra o venta; explica lo que los datos muestran.\n\n"
    "FORMATO. Español, prosa clara, tan breve como la pregunta permita. Cita los "
    "valores concretos que has obtenido y de qué indicador salen. Si los datos no "
    "bastan para responder, dilo abiertamente en lugar de rellenar el hueco."
)


# --------------------------------------------------------------------------- #
# Constructores del prompt de usuario
# --------------------------------------------------------------------------- #
# Se construyen desde el informe YA CERRADO. Toda cifra se formatea con `_v()`,
# que imprime «no disponible» en vez de un cero cuando el dato falta — de nada
# sirve la cláusula de ausencia del system prompt si el prompt de usuario le
# presenta al modelo un 0.0 indistinguible de un valor real.


def _v(valor: Any, fmt: str = "{:.1%}") -> str:
    if valor is None:
        return "no disponible"
    try:
        return fmt.format(valor)
    except (TypeError, ValueError):
        return str(valor)


def _lista(valores: Optional[List[str]], vacio: str = "ninguna") -> str:
    return "; ".join(valores) if valores else vacio


def prompt_gatekeeper(ticker: str, sector: str, informe: Dict[str, Any]) -> str:
    m = informe.get("metrics", {}) or {}
    return (
        f"Compañía: {ticker} (sector {sector})\n"
        f"Veredicto del filtro: {informe.get('status')}\n"
        f"Crecimiento de ingresos: {_v(m.get('revenue_growth'))}\n"
        f"Margen neto: {_v(m.get('net_margin'))}\n"
        f"Deuda/Patrimonio: {_v(m.get('debt_to_equity'), '{:.2f}x')} "
        f"(límite aplicado {_v(informe.get('umbral_deuda_aplicado'), '{:.2f}x')})\n"
        f"ROE: {_v(m.get('roe'))}\n"
        f"Confianza en los datos: {_v(informe.get('confidence_score'), '{:.0%}')}\n"
        f"Motivos: {_lista(informe.get('reasons'), 'ninguno')}\n"
        f"Avisos: {_lista(informe.get('avisos'), 'ninguno')}"
    )


def prompt_calidad(ticker: str, sector: str, industria: str,
                   informe: Dict[str, Any]) -> str:
    p = informe.get("puntuaciones", {}) or {}
    conv = (informe.get("conviccion_fundamental") or {}).get("valor")
    return (
        f"Compañía: {ticker} ({sector} / {industria})\n"
        f"Estilo asignado: {informe.get('style_classification')} "
        f"(secundarias: {_lista(informe.get('etiquetas_secundarias'))})\n"
        f"Motivo del estilo: {informe.get('style_rationale', 'no declarado')}\n"
        f"Calidad {_v(p.get('calidad'), '{:.0f}')}/100 · "
        f"Valoración {_v(p.get('valoracion'), '{:.0f}')}/100 · "
        f"Crecimiento {_v(p.get('crecimiento'), '{:.0f}')}/100 · "
        f"Solvencia {_v(p.get('solvencia'), '{:.0f}')}/100\n"
        f"Convicción fundamental: {_v(conv, '{:.0f}')}/100\n"
        f"Piotroski: {_v((informe.get('piotroski') or {}).get('score'), '{:.0f}')}/9 · "
        f"Altman: {(informe.get('altman') or {}).get('zona', 'no disponible')} · "
        f"ROIC: {_v((informe.get('buffett') or {}).get('roic'))} · "
        f"PEG: {_v((informe.get('lynch') or {}).get('peg'), '{:.2f}')}\n"
        f"Cobertura de datos: {_v(informe.get('cobertura_global'), '{:.0%}')}\n"
        f"Banderas rojas: {_lista(informe.get('banderas_rojas'))}"
    )


def prompt_tecnico(ticker: str, informe: Dict[str, Any]) -> str:
    return (
        f"Compañía: {ticker}\n"
        f"Puntuación de momentum: {_v(informe.get('momentum_score'), '{:+.1f}')}/100 "
        f"→ {informe.get('momentum_classification')}\n"
        f"Precio: {_v(informe.get('close'), '${:.2f}')} · "
        f"SMA50 {_v(informe.get('sma_50'), '${:.2f}')} · "
        f"SMA200 {_v(informe.get('sma_200'), '${:.2f}')}\n"
        f"RSI: {_v(informe.get('rsi'), '{:.1f}')} ({informe.get('rsi_estado')})\n"
        f"Estructura de tendencia: {informe.get('estado_tendencia')}\n"
        f"MACD histograma: {_v(informe.get('macd_hist'), '{:+.3f}')}\n"
        f"Posición en el rango de 52 semanas: "
        f"{_v(informe.get('posicion_rango_52w'), '{:.0%}')}\n"
        f"Sobreextendido: {'sí' if informe.get('sobreextendido') else 'no'}\n"
        f"Aportación de cada bloque: {informe.get('contribuciones')}"
    )


def prompt_noticias(ticker: str, empresa: str, informe: Dict[str, Any]) -> str:
    catalizadores = [c.get("titular", "")[:120] for c in informe.get("catalysts", [])]
    fallidas = [f.get("buscador", "?") for f in informe.get("sources_failed", [])]
    return (
        f"Compañía: {empresa} ({ticker})\n"
        f"Probabilidad de impacto en el precio: {informe.get('impact_classification')} "
        f"({_v(informe.get('impact_probability'), '{:.2f}')})\n"
        f"Dirección probable: {informe.get('direction_classification')} "
        f"(desequilibrio {_v(informe.get('direction_imbalance'), '{:+.2f}')})\n"
        f"Noticias analizadas: {informe.get('n_items', 0)} en "
        f"{informe.get('window_days', 0)} días\n"
        f"Catalizadores: {_lista(catalizadores, 'ninguno')}\n"
        f"Fuentes sin respuesta: {_lista(fallidas)}"
    )


def prompt_debate(ticker: str, sector: str, estilo: str,
                  informe: Dict[str, Any], news_frase: Optional[str] = None) -> str:
    partes = [
        f"Compañía: {ticker} ({sector}) · estilo asignado {estilo}",
        f"{informe.get('bullish_case', '')}",
        f"{informe.get('bearish_case', '')}",
    ]
    if news_frase:
        partes.append(f"Contexto de noticias (capa asesora): {news_frase}")
    partes.append(f"Condiciones que invalidarían la tesis: "
                  f"{_lista(informe.get('invalidacion'), 'no declaradas')}")
    return "\n".join(partes)


def prompt_fund_manager(ticker: str, informe: Dict[str, Any],
                        conviccion: Optional[float],
                        momentum_score: Optional[float]) -> str:
    riesgo = informe.get("perfil_riesgo", {}) or {}
    dim = informe.get("dimensionado", {}) or {}
    return (
        f"Compañía: {ticker}\n"
        f"Dictamen: {informe.get('rating')} (estilo {informe.get('estilo')})\n"
        f"Convicción fundamental: {_v(conviccion, '{:.0f}')}/100 · "
        f"Momentum: {_v(momentum_score, '{:+.0f}')}/100\n"
        f"Asignación: {_v(dim.get('peso_objetivo'), '{:.2%}')} de la cartera\n"
        f"Precio {_v(informe.get('current_price'), '${:.2f}')} · "
        f"Stop {_v(informe.get('stop_loss_atr'), '${:.2f}')} · "
        f"Objetivo {_v(informe.get('take_profit_atr'), '${:.2f}')}\n"
        f"Horizonte: {informe.get('horizonte_dias', 'no declarado')} sesiones · "
        f"Riesgo/recompensa {_v(riesgo.get('ratio_riesgo_recompensa'), '{:.2f}')}\n"
        f"Vetos aplicados: {_lista(informe.get('vetos_aplicados'))}\n"
        f"Banderas rojas: {_lista(informe.get('banderas_rojas'))}"
    )
