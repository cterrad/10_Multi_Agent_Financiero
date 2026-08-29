import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Fundamental Thresholds (Gatekeeper)
MIN_REVENUE_GROWTH = float(os.getenv("MIN_REVENUE_GROWTH", "0.05"))  # 5% YoY
MIN_NET_MARGIN = float(os.getenv("MIN_NET_MARGIN", "0.03"))          # 3% Net Margin
MAX_DEBT_TO_EQUITY = float(os.getenv("MAX_DEBT_TO_EQUITY", "3.5"))    # Debt-to-Equity limit

# System Paths
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# APIs & Tokens
SEC_EDGAR_USER_AGENT = os.getenv("SEC_EDGAR_USER_AGENT", "MultiAgentFinanciero/1.0 (contact@financialagent.org)")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
HUGGINGFACEHUB_API_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN", "")

# LLM Provider Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "huggingface").lower()
HUGGINGFACE_PROVIDER = os.getenv("HUGGINGFACE_PROVIDER", "featherless-ai")
HUGGINGFACE_MODEL = os.getenv("HUGGINGFACE_MODEL", "Qwen/Qwen2.5-7B-Instruct")
HUGGINGFACE_MODEL_TASK = os.getenv("HUGGINGFACE_MODEL_TASK", "text-generation")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def get_llm():
    """
    Retorna el modelo de lenguaje configurado (Hugging Face, OpenAI, Gemini u Ollama).
    Si no hay llaves disponibles o la API falla, retorna None y los agentes usarán el motor heurístico determinista.
    """
    provider = LLM_PROVIDER
    
    if provider == "huggingface" and HUGGINGFACEHUB_API_TOKEN:
        try:
            from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
            
            endpoint_kwargs = {
                "repo_id": HUGGINGFACE_MODEL,
                "huggingfacehub_api_token": HUGGINGFACEHUB_API_TOKEN,
                "temperature": 0.2,
                "max_new_tokens": 512
            }
            
            if HUGGINGFACE_PROVIDER and HUGGINGFACE_PROVIDER.lower() not in ["auto", "none", "featherless-ai"]:
                endpoint_kwargs["provider"] = HUGGINGFACE_PROVIDER

            llm_endpoint = HuggingFaceEndpoint(**endpoint_kwargs)
            return ChatHuggingFace(llm=llm_endpoint)
        except Exception as e:
            print(f"[Config] Advertencia al inicializar HuggingFace LLM ({HUGGINGFACE_MODEL}): {e}. Usando fallback heurístico.")
            return None

    elif provider == "openai" and os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model=OPENAI_MODEL, temperature=0.2)
        except Exception as e:
            print(f"[Config] Error al inicializar OpenAI LLM: {e}. Usando fallback heurístico.")
            return None

    elif provider == "gemini" and os.getenv("GOOGLE_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite")
        except Exception as e:
            print(f"[Config] Error al inicializar Gemini LLM: {e}. Usando fallback heurístico.")
            return None

    return None


def texto_de_respuesta_llm(llm_res) -> Optional[str]:
    """
    Extrae texto plano de la respuesta de `get_llm()`.

    Los proveedores modernos devuelven `content` como LISTA de bloques
    (`[{"type": "text", "text": "..."}]`) en vez de como cadena. Asignar ese
    `content` directamente a `summary` mete una lista de diccionarios en el
    informe y en `daily_selection.json`, que es exactamente lo que ocurría
    antes de existir esta función.

    Devuelve None cuando no hay texto utilizable; el agente que la llama debe
    conservar entonces su resumen determinista. Esa es la razón de que devuelva
    None en vez de cadena vacía: un `summary` vacío perdería información que sí
    estaba calculada.

    No interviene en ninguna decisión — solo da forma a texto.
    """
    if isinstance(llm_res, str):
        return llm_res or None

    contenido = getattr(llm_res, "content", None)
    if isinstance(contenido, str):
        return contenido or None
    if isinstance(contenido, list):
        partes = [
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in contenido
            if not isinstance(b, dict) or b.get("type", "text") == "text"
        ]
        texto = "\n".join(p for p in partes if p).strip()
        return texto or None
    return None


# ==========================================================================
# Analista de Noticias
# ==========================================================================
# Todas las constantes de esta sección son variables de DECISIÓN del
# `NewsAnalystAgent`. Se declaran aquí, junto a MIN_NET_MARGIN y
# MAX_DEBT_TO_EQUITY, para que el scorer sea auditable de un vistazo y
# ajustable sin tocar código. El LLM no interviene en ninguna de ellas.

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# --- Búsqueda -------------------------------------------------------------
NEWS_WINDOW_DAYS = int(os.getenv("NEWS_WINDOW_DAYS", "30"))          # antigüedad máxima admitida
NEWS_MAX_ITEMS_PER_SOURCE = int(os.getenv("NEWS_MAX_ITEMS_PER_SOURCE", "12"))
NEWS_HTTP_TIMEOUT = float(os.getenv("NEWS_HTTP_TIMEOUT", "12"))      # por petición HTTP
NEWS_TOTAL_TIMEOUT = float(os.getenv("NEWS_TOTAL_TIMEOUT", "30"))    # presupuesto del nodo entero
NEWS_USER_AGENT = os.getenv("NEWS_USER_AGENT", "Mozilla/5.0 (compatible; MultiAgentFinanciero/1.0)")
NEWS_LOCALE = {"hl": "en-US", "gl": "US", "ceid": "US:en"}

# Caché por (ticker, día): evita agotar la cuota de Tavily y machacar el RSS en
# ejecuciones repetidas. Sigue el espíritu de PriceStore: una descarga, servida
# desde disco. La clave incluye el día porque las noticias son datos "de hoy".
NEWS_CACHE_DIR = os.getenv("NEWS_CACHE_DIR", "data/cache/news")
NEWS_CACHE_ENABLED = os.getenv("NEWS_CACHE_ENABLED", "1").lower() not in ("0", "false", "no")

# --- Deduplicación --------------------------------------------------------
# Índice de Jaccard mínimo entre los conjuntos de palabras de dos titulares
# normalizados para considerarlos el MISMO hecho. Por encima se fusionan y la
# corroboración cuenta a favor del ítem; por debajo son noticias distintas.
NEWS_SIMILARITY_THRESHOLD = float(os.getenv("NEWS_SIMILARITY_THRESHOLD", "0.62"))

# --- Peso de impacto por categoría ---------------------------------------
# Cuánto mueve el precio, históricamente, cada tipo de anuncio.
NEWS_CATEGORY_WEIGHTS = {
    "RESULTADOS": 1.00,
    "GUIDANCE": 0.95,
    "REGULATORIO": 0.80,
    "CAPITAL": 0.75,
    "CORPORATIVO": 0.70,
    "ALIANZA": 0.55,
    "PRODUCTO": 0.50,
    "OTROS": 0.25,
}

# Orden de desempate cuando dos categorías empatan en número de coincidencias.
# Fijo y explícito: sin él la clasificación dependería del orden de un dict.
NEWS_CATEGORY_PRIORITY = [
    "RESULTADOS", "GUIDANCE", "REGULATORIO", "CAPITAL",
    "CORPORATIVO", "ALIANZA", "PRODUCTO", "OTROS",
]

# --- Peso de credibilidad por tipo de fuente ------------------------------
# 8-K/IR oficial > newswire tier-1 > medio financiero > agregador genérico.
# El 8-K es la única fuente con fecha `filed` exacta y contenido no editorial.
NEWS_SOURCE_CREDIBILITY = {
    "SEC_8K": 1.00,
    "IR_OFICIAL": 0.90,
    "NEWSWIRE": 0.80,
    "MEDIO_TIER1": 0.70,
    "AGREGADOR": 0.45,
    "DESCONOCIDA": 0.30,
}

# --- Decaimiento por antigüedad -------------------------------------------
# Decaimiento exponencial: peso = 0.5 ** (dias / semivida).
NEWS_HALFLIFE_DAYS = float(os.getenv("NEWS_HALFLIFE_DAYS", "7"))
# Antigüedad asumida cuando el ítem no trae fecha. Penaliza sin descartar, y es
# determinista (no depende de cuándo se ejecute).
NEWS_DAYS_IF_UNDATED = float(os.getenv("NEWS_DAYS_IF_UNDATED", "14"))

# --- Bonus por corroboración multi-fuente ---------------------------------
# Dos fuentes independientes reportando el mismo hecho refuerzan su credibilidad.
NEWS_CORROBORATION_BONUS = float(os.getenv("NEWS_CORROBORATION_BONUS", "0.15"))
NEWS_MAX_CORROBORATION_FACTOR = float(os.getenv("NEWS_MAX_CORROBORATION_FACTOR", "1.45"))

# --- Agregación a probabilidad --------------------------------------------
# Probabilidad máxima que puede aportar UN SOLO ítem perfecto (8-K de resultados
# publicado hoy). Que no sea 1.0 es deliberado: ninguna noticia aislada
# garantiza un movimiento de precio.
NEWS_ITEM_PROB_MAX = float(os.getenv("NEWS_ITEM_PROB_MAX", "0.45"))
# Los ítems se combinan con OR ruidoso (1 - Π(1-p)) sobre los K de mayor peso.
# Truncar en K evita que una cola larga de ruido sature la probabilidad a 1.
NEWS_TOP_K_ITEMS = int(os.getenv("NEWS_TOP_K_ITEMS", "6"))

# Cortes del bucket, en el estilo de `momentum_classification`.
NEWS_HIGH_IMPACT_THRESHOLD = float(os.getenv("NEWS_HIGH_IMPACT_THRESHOLD", "0.60"))
NEWS_MEDIUM_IMPACT_THRESHOLD = float(os.getenv("NEWS_MEDIUM_IMPACT_THRESHOLD", "0.30"))

# --- Dirección probable ---------------------------------------------------
# Margen mínimo del desequilibrio alcista/bajista normalizado a [-1, 1] para
# declarar una dirección. Por debajo, la lectura es MIXTA.
NEWS_DIRECTION_MARGIN = float(os.getenv("NEWS_DIRECTION_MARGIN", "0.25"))

# --- Léxicos de clasificación (diccionarios fijos, NO juicio del LLM) ------
# Se comparan contra el titular + extracto normalizados (minúsculas, sin
# acentos). Bilingües porque los feeds mezclan medios en inglés y español.
# La categoría se decide por número de coincidencias, con NEWS_CATEGORY_PRIORITY
# como desempate.
NEWS_CATEGORY_KEYWORDS = {
    "RESULTADOS": [
        "results of operations", "quarterly results", "fourth quarter", "third quarter",
        "second quarter", "first quarter", "full year results", "quarterly earnings", "earnings",
        "eps", "earnings per share", "revenue of", "beats estimates", "misses estimates",
        "financial results", "resultados trimestrales", "resultados del", "beneficio neto",
        "cuenta de resultados", "ingresos de", "presenta resultados",
    ],
    "GUIDANCE": [
        "guidance", "outlook", "forecast", "raises full-year", "lowers full-year",
        "cuts outlook", "raises outlook", "profit warning", "previsiones",
        "perspectivas", "revisa al alza", "revisa a la baja", "eleva su objetivo",
    ],
    "REGULATORIO": [
        "lawsuit", "class action", "sec investigation", "antitrust", "doj",
        "regulator", "regulatory", "fine", "penalty", "subpoena", "probe",
        "settlement", "recall", "fda approval", "fda rejects", "ftc",
        "demanda", "investigacion", "sancion", "multa", "regulador",
        "competencia", "retirada del mercado",
    ],
    "CAPITAL": [
        "buyback", "share repurchase", "dividend", "stock split", "secondary offering",
        "convertible notes", "debt offering", "capital raise", "equity offering",
        "recompra", "dividendo", "ampliacion de capital", "split", "emision de deuda",
    ],
    "CORPORATIVO": [
        "acquisition", "acquires", "merger", "to acquire", "spin-off", "divestiture",
        "ceo", "cfo", "steps down", "resigns", "appoints", "names new",
        "layoffs", "restructuring", "bankruptcy", "chapter 11",
        "adquisicion", "fusion", "dimite", "nombra", "despidos", "reestructuracion",
    ],
    "ALIANZA": [
        "partnership", "partners with", "collaboration", "joint venture",
        "strategic agreement", "signs deal", "contract award", "wins contract",
        "alianza", "acuerdo estrategico", "colaboracion", "adjudica", "firma un acuerdo",
    ],
    "PRODUCTO": [
        "launches", "unveils", "introduces", "new product", "availability",
        "general availability", "roadmap", "next-generation", "patent",
        "lanza", "presenta", "nuevo producto", "disponibilidad", "patente",
    ],
}

# Términos de severidad para inferir la dirección probable. Un ítem cuenta como
# alcista o bajista según el signo del balance de coincidencias en su texto.
NEWS_BULLISH_LEXICON = [
    "beats", "beat estimates", "tops", "record", "surges", "soars", "jumps", "rally",
    "upgrade", "raises", "raised", "strong demand", "outperform", "approval", "approved",
    "wins", "awarded", "expansion", "buyback", "dividend increase", "breakthrough",
    "better than expected", "accelerates", "all-time high", "profit rises",
    "supera", "record", "se dispara", "mejora", "aprueba", "aprobado", "gana",
    "adjudica", "amplia", "recompra", "impulsa", "crece", "al alza", "mejor de lo esperado",
]
NEWS_BEARISH_LEXICON = [
    "misses", "miss estimates", "falls short", "cuts", "slashes", "downgrade",
    "lawsuit", "investigation", "probe", "recall", "delay", "delayed", "warning",
    "layoffs", "resigns", "steps down", "subpoena", "fine", "penalty", "bankruptcy",
    "halt", "plunges", "tumbles", "sinks", "weak demand", "dilution", "offering priced",
    "worse than expected", "profit falls", "loss widens", "guidance cut",
    "incumple", "recorta", "rebaja", "demanda", "investigacion", "retirada", "retraso",
    "multa", "despidos", "dimite", "sancion", "se desploma", "debil",
    "ampliacion de capital", "peor de lo esperado", "perdidas",
]

# Dominios conocidos por tipo de fuente. La clasificación es por sufijo de
# dominio, así que "www.reuters.com" y "reuters.com" caen en el mismo cubo.
NEWS_DOMAIN_TYPES = {
    "NEWSWIRE": [
        "businesswire.com", "prnewswire.com", "globenewswire.com", "accesswire.com",
        "newsfilecorp.com", "prweb.com", "einpresswire.com",
    ],
    "MEDIO_TIER1": [
        "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com",
        "barrons.com", "marketwatch.com", "apnews.com", "nytimes.com",
        "economist.com", "axios.com", "theinformation.com", "expansion.com",
        "cincodias.elpais.com", "eleconomista.es",
    ],
    "AGREGADOR": [
        "news.google.com", "finance.yahoo.com", "yahoo.com", "seekingalpha.com",
        "benzinga.com", "zacks.com", "investing.com", "msn.com", "fool.com",
        "simplywall.st", "insidermonkey.com", "tipranks.com", "stocktwits.com",
        "247wallst.com", "gurufocus.com",
    ],
}

# --- Ruido promocional de los feeds ---------------------------------------
# Los avisos de bufetes captando demandantes ("investor alert", "lead
# plaintiff", "deadline reminder") saturan Google News y Tavily para cualquier
# empresa grande. Formalmente son REGULATORIO y llegan por newswire, así que
# sin una defensa explícita entrarían con credibilidad alta y contaminarían
# tanto la probabilidad como la dirección.
#
# El prototipo de `src/notebooks/agent_search_web.ipynb` los filtraba pidiéndole
# criterio al LLM. Aquí eso no es admisible —sería el LLM decidiendo—, así que
# se degradan con un diccionario cerrado y un multiplicador auditable. No se
# descartan: un litigio real puede esconderse detrás de uno de estos avisos.
NEWS_NOISE_LEXICON = [
    "investor alert", "shareholder alert", "lead plaintiff", "class action deadline",
    "deadline reminder", "reminds investors", "encourages investors", "investigating claims",
    "law firm announces", "law offices of", "rosen law", "pomerantz", "levi korsinsky",
    "bronstein gewirtz", "glancy prongay", "schall law", "portnoy law",
    "securities fraud lawsuit", "contact the firm", "no cost to you",
    "recuerda a los inversores", "bufete anuncia",
]
NEWS_NOISE_PENALTY = float(os.getenv("NEWS_NOISE_PENALTY", "0.20"))


# ==========================================================================
# Analista de Calidad y Valoración  (`src/agents/quality.py`)
# ==========================================================================
# Igual que en la sección de noticias, TODO lo que hay aquí es variable de
# decisión determinista. El LLM no interviene en ninguna.
#
# Las escuelas que se codifican y de dónde sale cada regla:
#   · Graham    — criterios defensivos y Número de Graham (margen de seguridad).
#   · Buffett   — ROIC sostenido, márgenes brutos altos, beneficio del
#                 propietario (CFO − capex) sobre capitalización.
#   · Lynch     — PEG y taxonomía por perfil de crecimiento.
#   · Greenblatt— fórmula mágica: rentabilidad del capital + rendimiento del
#                 beneficio sobre valor de empresa.
#   · Piotroski — F-Score de 9 puntos sobre rentabilidad, apalancamiento y
#                 eficiencia operativa.
#   · Altman    — Z-Score de solvencia (variante Z'' para no manufactureras).
#   · Sloan     — ratio de devengos: el beneficio que no es caja revierte.

# --- Piotroski F-Score ----------------------------------------------------
# Umbrales clásicos: >=8 excelente, <=3 débil.
PIOTROSKI_FUERTE = int(os.getenv("PIOTROSKI_FUERTE", "7"))
PIOTROSKI_DEBIL = int(os.getenv("PIOTROSKI_DEBIL", "3"))

# --- Altman Z-Score -------------------------------------------------------
# Z clásico (manufactureras) y Z'' (servicios / no manufactureras). El agente
# elige la variante por sector; ambas se reportan cuando hay datos.
ALTMAN_Z_SEGURO = float(os.getenv("ALTMAN_Z_SEGURO", "2.99"))
ALTMAN_Z_DISTRESS = float(os.getenv("ALTMAN_Z_DISTRESS", "1.81"))
ALTMAN_ZDD_SEGURO = float(os.getenv("ALTMAN_ZDD_SEGURO", "2.60"))
ALTMAN_ZDD_DISTRESS = float(os.getenv("ALTMAN_ZDD_DISTRESS", "1.10"))
# Sectores a los que se aplica el Z clásico; el resto usa Z''.
ALTMAN_SECTORES_MANUFACTURA = ("Industrials", "Basic Materials", "Energy", "Consumer Cyclical")

# --- Graham ---------------------------------------------------------------
GRAHAM_MULTIPLICADOR = float(os.getenv("GRAHAM_MULTIPLICADOR", "22.5"))  # 15 P/E × 1.5 P/B
GRAHAM_PE_MAXIMO = float(os.getenv("GRAHAM_PE_MAXIMO", "15.0"))
GRAHAM_PB_MAXIMO = float(os.getenv("GRAHAM_PB_MAXIMO", "1.5"))
GRAHAM_CURRENT_RATIO_MINIMO = float(os.getenv("GRAHAM_CURRENT_RATIO_MINIMO", "2.0"))
GRAHAM_DEUDA_PATRIMONIO_MAXIMA = float(os.getenv("GRAHAM_DEUDA_PATRIMONIO_MAXIMA", "1.0"))
# Margen de seguridad exigido sobre el Número de Graham para llamarlo «valor».
GRAHAM_MARGEN_SEGURIDAD_MINIMO = float(os.getenv("GRAHAM_MARGEN_SEGURIDAD_MINIMO", "0.25"))

# --- Buffett / calidad compuesta ------------------------------------------
ROIC_EXCELENTE = float(os.getenv("ROIC_EXCELENTE", "0.15"))
ROIC_ACEPTABLE = float(os.getenv("ROIC_ACEPTABLE", "0.09"))
MARGEN_BRUTO_FOSO = float(os.getenv("MARGEN_BRUTO_FOSO", "0.40"))
# Coste del capital de referencia. Constante y declarado a propósito: estimar un
# WACC por empresa exigiría beta, estructura de capital y prima de riesgo, y la
# dispersión del resultado sería mayor que la señal. Se documenta como umbral,
# no como valoración.
WACC_REFERENCIA = float(os.getenv("WACC_REFERENCIA", "0.09"))

# --- Greenblatt (fórmula mágica) ------------------------------------------
GREENBLATT_EY_ATRACTIVO = float(os.getenv("GREENBLATT_EY_ATRACTIVO", "0.08"))   # EBIT/EV
GREENBLATT_ROC_ATRACTIVO = float(os.getenv("GREENBLATT_ROC_ATRACTIVO", "0.25"))  # EBIT/capital tangible

# --- Lynch ----------------------------------------------------------------
PEG_MUY_ATRACTIVO = float(os.getenv("PEG_MUY_ATRACTIVO", "0.75"))
PEG_ATRACTIVO = float(os.getenv("PEG_ATRACTIVO", "1.25"))
PEG_CARO = float(os.getenv("PEG_CARO", "2.00"))
LYNCH_CRECIMIENTO_RAPIDO = float(os.getenv("LYNCH_CRECIMIENTO_RAPIDO", "0.20"))
LYNCH_CRECIMIENTO_SOLIDO = float(os.getenv("LYNCH_CRECIMIENTO_SOLIDO", "0.10"))

# --- Sloan (calidad del beneficio) ----------------------------------------
# Devengos = (Beneficio neto − Flujo de caja operativo) / Activos totales.
# Por encima del umbral, el beneficio se apoya en apuntes contables y no en
# caja; históricamente predice reversión.
DEVENGOS_ALERTA = float(os.getenv("DEVENGOS_ALERTA", "0.10"))

# --- Flujo de caja libre --------------------------------------------------
FCF_YIELD_ATRACTIVO = float(os.getenv("FCF_YIELD_ATRACTIVO", "0.06"))
FCF_YIELD_ACEPTABLE = float(os.getenv("FCF_YIELD_ACEPTABLE", "0.03"))

# --- Dilución -------------------------------------------------------------
# Crecimiento anual de acciones en circulación por encima del cual la dilución
# se descuenta de la rentabilidad del accionista.
DILUCION_ALERTA = float(os.getenv("DILUCION_ALERTA", "0.03"))

# --- Pesos de las cuatro puntuaciones -------------------------------------
# Cada bloque produce 0-100. `PESOS_CONVICCION` los combina en la convicción
# fundamental que el Fund Manager cruza con el momentum.
PESOS_CONVICCION = {
    "calidad": float(os.getenv("PESO_CALIDAD", "0.35")),
    "valoracion": float(os.getenv("PESO_VALORACION", "0.25")),
    "crecimiento": float(os.getenv("PESO_CRECIMIENTO", "0.20")),
    "solvencia": float(os.getenv("PESO_SOLVENCIA", "0.20")),
}

# --- Umbrales de estilo ---------------------------------------------------
# Fronteras del clasificador VALOR / CRECIMIENTO / GARP / CALIDAD / ... .
ESTILO_VALOR_MINIMO = float(os.getenv("ESTILO_VALOR_MINIMO", "60"))
ESTILO_CRECIMIENTO_MINIMO = float(os.getenv("ESTILO_CRECIMIENTO_MINIMO", "60"))
ESTILO_CALIDAD_MINIMA = float(os.getenv("ESTILO_CALIDAD_MINIMA", "65"))
ESTILO_SOLVENCIA_MINIMA = float(os.getenv("ESTILO_SOLVENCIA_MINIMA", "50"))
# Por debajo de esto una acción barata es sospechosa de trampa de valor.
ESTILO_TRAMPA_CALIDAD_MAXIMA = float(os.getenv("ESTILO_TRAMPA_CALIDAD_MAXIMA", "40"))

# Cobertura de datos mínima para emitir una etiqueta de estilo. Por debajo, el
# agente declara DATOS_INSUFICIENTES en vez de clasificar con huecos.
COBERTURA_MINIMA_ESTILO = float(os.getenv("COBERTURA_MINIMA_ESTILO", "0.45"))


# ==========================================================================
# Normas sectoriales de referencia
# ==========================================================================
# «P/E elevado» sin referencia no significa nada: 17x es caro en una minera y
# barato en software. Esta tabla da el punto de comparación que faltaba.
#
# LIMITACIÓN DECLARADA: son medianas estáticas de largo plazo del mercado
# estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y
# contextualizar, no para valorar. Sustituirlas por la mediana calculada sobre
# un conjunto de comparables es el paso siguiente natural (`NEXT_STEPS`).
# Revisadas por última vez: 2026-08.
SECTOR_DESCONOCIDO = "Desconocido"

SECTOR_NORMAS = {
    "Technology":             {"pe": 26.0, "margen_neto": 0.15, "deuda_patrimonio": 0.60, "crecimiento": 0.12},
    "Communication Services": {"pe": 19.0, "margen_neto": 0.12, "deuda_patrimonio": 0.80, "crecimiento": 0.08},
    "Healthcare":             {"pe": 22.0, "margen_neto": 0.08, "deuda_patrimonio": 0.60, "crecimiento": 0.08},
    "Financial Services":     {"pe": 13.0, "margen_neto": 0.20, "deuda_patrimonio": 1.60, "crecimiento": 0.06},
    "Consumer Cyclical":      {"pe": 20.0, "margen_neto": 0.06, "deuda_patrimonio": 1.00, "crecimiento": 0.07},
    "Consumer Defensive":     {"pe": 21.0, "margen_neto": 0.06, "deuda_patrimonio": 0.90, "crecimiento": 0.05},
    "Industrials":            {"pe": 20.0, "margen_neto": 0.08, "deuda_patrimonio": 0.90, "crecimiento": 0.07},
    "Energy":                 {"pe": 12.0, "margen_neto": 0.09, "deuda_patrimonio": 0.50, "crecimiento": 0.06},
    "Basic Materials":        {"pe": 15.0, "margen_neto": 0.08, "deuda_patrimonio": 0.50, "crecimiento": 0.06},
    "Utilities":              {"pe": 18.0, "margen_neto": 0.11, "deuda_patrimonio": 1.50, "crecimiento": 0.04},
    "Real Estate":            {"pe": 30.0, "margen_neto": 0.18, "deuda_patrimonio": 1.20, "crecimiento": 0.05},
    SECTOR_DESCONOCIDO:       {"pe": 20.0, "margen_neto": 0.08, "deuda_patrimonio": 1.00, "crecimiento": 0.07},
}

# Sectores donde el beneficio es cíclico y un P/E bajo puede señalar techo de
# ciclo en vez de ganga (la «trampa del P/E bajo» de Lynch en cíclicas).
SECTORES_CICLICOS = ("Energy", "Basic Materials", "Industrials", "Consumer Cyclical", "Real Estate")

# Sectores donde la relación deuda/patrimonio alta es estructural y no una
# señal de fragilidad: bancos, aseguradoras, utilities reguladas y REITs.
# Aplicar el mismo MAX_DEBT_TO_EQUITY a un banco que a una empresa de software
# es un error de categoría que el gatekeeper cometía.
GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR = {
    "Financial Services": float(os.getenv("MAX_DE_FINANCIERAS", "12.0")),
    "Real Estate":        float(os.getenv("MAX_DE_INMOBILIARIO", "5.0")),
    "Utilities":          float(os.getenv("MAX_DE_UTILITIES", "5.0")),
}

# Sectores donde exigir margen neto positivo descarta sistemáticamente el
# modelo de negocio (biotecnología en fase clínica). Se sustituye el filtro de
# margen por uno de solvencia y caja: se sigue filtrando, pero por lo que
# importa en ese sector.
GATEKEEPER_INDUSTRIAS_SIN_MARGEN = ("Biotechnology",)


# ==========================================================================
# Construcción de cartera  (`src/portfolio/construccion.py`)
# ==========================================================================
# El sistema emitía tamaños de posición como CADENAS de texto idénticas para
# todos los valores («2.0% - 3.0%»), lo que hacía imposible sumar exposición,
# escalar por volatilidad o presupuestar riesgo. Estas constantes definen la
# política numérica que las sustituye.

CAPITAL_BASE = float(os.getenv("CAPITAL_BASE", "100000"))

# Riesgo máximo del patrimonio comprometido en una sola posición si salta el
# stop. Es la regla que fija el tamaño: peso = riesgo_objetivo / distancia_stop.
RIESGO_POR_POSICION_PCT = float(os.getenv("RIESGO_POR_POSICION_PCT", "0.0075"))  # 0.75%
RIESGO_TOTAL_CARTERA_PCT = float(os.getenv("RIESGO_TOTAL_CARTERA_PCT", "0.05"))  # 5%

PESO_MAXIMO_POSICION = float(os.getenv("PESO_MAXIMO_POSICION", "0.10"))
PESO_MINIMO_OPERABLE = float(os.getenv("PESO_MINIMO_OPERABLE", "0.01"))
EXPOSICION_BRUTA_MAXIMA = float(os.getenv("EXPOSICION_BRUTA_MAXIMA", "0.95"))
LIMITE_POR_SECTOR = float(os.getenv("LIMITE_POR_SECTOR", "0.30"))
MAXIMO_POSICIONES = int(os.getenv("MAXIMO_POSICIONES", "20"))

# Volatilidad anualizada objetivo de cada posición antes de aplicar convicción.
# Escalar por volatilidad iguala la contribución al riesgo: sin esto, una
# posición del 3% en una acción con 80% de volatilidad aporta cuatro veces más
# riesgo que otra del 3% con 20%.
VOLATILIDAD_OBJETIVO = float(os.getenv("VOLATILIDAD_OBJETIVO", "0.25"))

# Penalización por correlación entre candidatos. Dos posiciones con correlación
# 0.9 no son dos apuestas, son una y media.
CORRELACION_ALTA = float(os.getenv("CORRELACION_ALTA", "0.70"))
CORRELACION_PENALIZACION_MAXIMA = float(os.getenv("CORRELACION_PENALIZACION_MAXIMA", "0.50"))
CORRELACION_VENTANA_DIAS = int(os.getenv("CORRELACION_VENTANA_DIAS", "120"))

# Rentabilidad del efectivo no invertido. El backtest documenta que el 72% de la
# cartera quedaba en liquidez al 0%: declararlo explícitamente evita repetir esa
# distorsión al comparar contra el índice.
RENDIMIENTO_LIQUIDEZ_ANUAL = float(os.getenv("RENDIMIENTO_LIQUIDEZ_ANUAL", "0.02"))


# ==========================================================================
# Gestión de riesgo y horizonte
# ==========================================================================
# El informe daba stop y objetivo por ATR sin decir a qué plazo aplican, y con
# el MISMO múltiplo para todos los valores. Ahora el múltiplo depende del
# estilo (una cíclica volátil necesita más aire que una compounder) y el
# horizonte se declara siempre.

ATR_MULTIPLO_STOP = float(os.getenv("ATR_MULTIPLO_STOP", "2.0"))
ATR_MULTIPLO_OBJETIVO = float(os.getenv("ATR_MULTIPLO_OBJETIVO", "3.5"))

# Ajustes por estilo sobre los múltiplos base.
ATR_AJUSTE_POR_ESTILO = {
    "CALIDAD_COMPUESTA": {"stop": 2.5, "objetivo": 5.0, "horizonte_dias": 252},
    # Buen negocio con defectos estructurales: se le da menos aire y menos
    # plazo que a una compounder limpia, porque la tesis depende de que esos
    # defectos se corrijan y eso hay que revisarlo antes.
    "CALIDAD_DETERIORADA": {"stop": 2.0, "objetivo": 3.5, "horizonte_dias": 126},
    "VALOR":             {"stop": 2.5, "objetivo": 4.5, "horizonte_dias": 189},
    "GARP":              {"stop": 2.2, "objetivo": 4.0, "horizonte_dias": 126},
    "CRECIMIENTO":       {"stop": 2.0, "objetivo": 3.5, "horizonte_dias": 63},
    "CICLICA":           {"stop": 2.2, "objetivo": 3.5, "horizonte_dias": 63},
    "TRAMPA_DE_VALOR":   {"stop": 1.5, "objetivo": 2.5, "horizonte_dias": 42},
    "ESPECULATIVA":      {"stop": 1.5, "objetivo": 3.0, "horizonte_dias": 42},
    "MIXTA":             {"stop": 2.0, "objetivo": 3.5, "horizonte_dias": 126},
}

# El horizonte del ATR se declara además en días de volatilidad: cuántas
# sesiones necesita el precio, a su ATR actual, para recorrer la distancia al
# objetivo. Es la traducción honesta de «take-profit ATR» a tiempo.
HORIZONTE_MINIMO_DIAS = int(os.getenv("HORIZONTE_MINIMO_DIAS", "21"))


# ==========================================================================
# Analista Técnico
# ==========================================================================
# Sustituyen al sistema de puntos enteros del clasificador anterior, que
# producía tres patologías verificadas:
#   1. Zona muerta: RSI 83.9 en NEM salía NEUTRAL porque SMA50 < SMA200 sumaba
#      2 puntos bajistas pese a cotizar un 27% POR ENCIMA de ambas medias.
#   2. No monotonía: con 4 puntos alcistas, pasar de 3 a 4 puntos bajistas
#      cambiaba la etiqueta de NEUTRAL a BAJISTA, pero con 5 alcistas el
#      bajismo se ignoraba por completo.
#   3. RSI sin escala: 70.1 y 95.0 penalizaban exactamente igual.
RSI_SOBRECOMPRA = float(os.getenv("RSI_SOBRECOMPRA", "70"))
RSI_SOBREVENTA = float(os.getenv("RSI_SOBREVENTA", "30"))
RSI_SOBRECOMPRA_EXTREMA = float(os.getenv("RSI_SOBRECOMPRA_EXTREMA", "80"))
RSI_SOBREVENTA_EXTREMA = float(os.getenv("RSI_SOBREVENTA_EXTREMA", "20"))

# Fronteras del `momentum_score` continuo (−100 a +100).
MOMENTUM_ALCISTA_FUERTE = float(os.getenv("MOMENTUM_ALCISTA_FUERTE", "45"))
MOMENTUM_ALCISTA = float(os.getenv("MOMENTUM_ALCISTA", "15"))
MOMENTUM_BAJISTA = float(os.getenv("MOMENTUM_BAJISTA", "-15"))
MOMENTUM_BAJISTA_FUERTE = float(os.getenv("MOMENTUM_BAJISTA_FUERTE", "-45"))

# Distancia sobre SMA200 a partir de la cual un cruce de la muerte se considera
# retardo del indicador y no tendencia bajista vigente (el caso NEM).
UMBRAL_TENDENCIA_RECUPERADA = float(os.getenv("UMBRAL_TENDENCIA_RECUPERADA", "0.10"))
