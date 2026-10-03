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
# Memoria de reflexión (capa de calibración por resultados realizados)
# ==========================================================================
# Traducción determinista de la «low-level reflection» de FinAgent (Zhang et
# al., 2024): relacionar lo que el sistema OBSERVÓ con lo que el precio hizo
# DESPUÉS, y usar esa relación para calibrar el tamaño de las posiciones
# futuras. En el paper original ese vínculo lo redacta un LLM; aquí es una
# media condicionada sobre observaciones ya desenlazadas, así que la invariante
# del proyecto se mantiene intacta.
#
# Las cuatro constantes siguientes son las MISMAS defensas que el proyecto ya
# aplica en otros bloques, y no son opcionales: sin ellas esto sería un lazo de
# ajuste sobre el propio histórico.

# Horizonte en sesiones sobre el que se mide el desenlace de una señal. Coincide
# con el periodo de rebalanceo mensual: una señal madura justo cuando el sistema
# vuelve a decidir, que es el máximo de datos disponible sin solapar ventanas.
REFLEXION_HORIZONTE_SESIONES = int(os.getenv("REFLEXION_HORIZONTE_SESIONES", "21"))

# Observaciones mínimas por celda antes de emitir un ajuste. Por debajo, factor
# neutro y `evaluable=False` — nunca una expectativa inventada. Es el mismo
# criterio de `COBERTURA_MINIMA_ESTILO` y de `OPCIONES_MINIMO_DIAS_HISTORICO`.
REFLEXION_MUESTRA_MINIMA = int(os.getenv("REFLEXION_MUESTRA_MINIMA", "40"))

# Constante de contracción bayesiana hacia la media global. Con n = K la celda
# pesa la mitad; con n >> K manda la celda. Evita que veinte observaciones
# afortunadas dicten el tamaño de las posiciones.
REFLEXION_CONTRACCION_K = float(os.getenv("REFLEXION_CONTRACCION_K", "40"))

# Suelo del factor. El ajuste RECORTA, nunca amplía: 1.0 es «sin evidencia en
# contra» y es también el valor máximo posible, igual que los vetos solo bajan.
REFLEXION_FACTOR_MINIMO = float(os.getenv("REFLEXION_FACTOR_MINIMO", "0.40"))

# Escala del déficit. Una celda con -5% de rentabilidad relativa esperada a 21
# sesiones se lleva el recorte completo; una con -1%, un 20%.
REFLEXION_ESCALA_DEFICIT = float(os.getenv("REFLEXION_ESCALA_DEFICIT", "0.05"))

# Observaciones mínimas de un rebalanceo para restarle su media transversal. Por
# debajo, la cohorte se incorpora en bruto: la media de tres señales no describe
# «lo que el sistema veía ese día», solo repite el ruido de esas tres.
#
# LA RESTA TRANSVERSAL NO ES UN DETALLE, ES LA MEDIDA. La primera versión medía
# el exceso contra el SPY y el resultado, sobre el histórico real, fue que la
# capa recortó 62 de 5.621 señales con un factor medio de x0.99 — es decir, no
# hizo nada. El motivo: este universo de grandes capitalizaciones bate al SPY,
# así que el exceso medio de TODAS las señales era +0.46% a 21 sesiones y casi
# ninguna celda caía por debajo de cero. Contra el SPY, la memoria medía
# «universo menos índice», que es exposición; contra la propia cohorte mide
# «este perfil menos los demás perfiles que el sistema tenía delante ese día»,
# que es selección, y es la única pregunta que esta capa puede responder.
REFLEXION_COHORTE_MINIMA = int(os.getenv("REFLEXION_COHORTE_MINIMA", "5"))

# Dimensiones de la memoria. Se consultan POR SEPARADO y manda la peor, nunca su
# producto: estilo y momentum están correlacionados, y multiplicar dos
# penalizaciones parcialmente redundantes castigaría dos veces el mismo defecto.
# Cruzarlas produciría celdas de tres observaciones, que es ruido con formato de
# tabla.
REFLEXION_DIMENSIONES = ("estilo", "momentum")

MEMORIA_DIR = os.getenv("MEMORIA_DIR", "data/memoria")


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


# ==========================================================================
# Analista de Posicionamiento y Precio de Entrada
# ==========================================================================
# Capa de DECISION: el precio de entrada que emite alimenta
# `calcular_niveles_riesgo`, y por esa via el stop, el objetivo y el tamano de
# la posicion. Como todo lo demas en este fichero, son variables deterministas
# y el LLM no interviene en ninguna.
#
# Dos familias de senales con origenes distintos:
#   - MACRO    : posicionamiento de especuladores en futuros (informes COT de la
#                CFTC). Da DIRECCION, no nivel de precio.
#   - OPCIONES : cadena del propio ticker. Da NIVEL de precio (open interest,
#                max pain, punto de inflexion de la exposicion gamma).
#
# El nivel sale EXCLUSIVAMENTE de la cadena de opciones. Esa asimetria es la
# razon de que el backtest solo pueda medir la mitad macro (ver
# `build_limitations()` en backtest_cli.py).

# Tipo libre de riesgo para las Griegas de Black-Scholes. Constante y declarado,
# igual que WACC_REFERENCIA: estimar una curva por fecha anadiria dispersion sin
# cambiar el signo de la gamma, que es lo unico que se usa.
TIPO_LIBRE_RIESGO = float(os.getenv("TIPO_LIBRE_RIESGO", "0.04"))

# --- Mapeo sector -> contrato de futuros ----------------------------------
# Un sector que NO esta aqui no esta por decision, no por olvido: forzar un
# proxy para "Technology" produciria un numero donde no hay relacion, que es
# peor que declarar NO_APLICABLE. Misma logica que
# GATEKEEPER_INDUSTRIAS_SIN_MARGEN: lista corta y explicita.
#
# `signo` es el sentido de la relacion: +1 si el subyacente al alza es viento a
# favor (una petrolera con el crudo caro), -1 si es viento en contra. Para
# financieras e inmobiliario el contrato es el bono a 10 anos y el signo es -1
# porque el precio del bono se mueve al reves que el tipo.
#
# LIMITACION DECLARADA: la granularidad correcta seria la industria, no el
# sector. Bancos y REITs comparten entrada aqui y no responden igual al mismo
# contrato; "Basic Materials" mezcla mineras de metales industriales con
# quimicas. Ordena y contextualiza; no es una estimacion de beta sectorial.
#
# Los nombres de `cot` son PATRONES verificados contra el fichero real de la
# CFTC (deacot2025.zip, comprobado el 2026-08-30). No son inventados ni
# aproximados: "NATURAL GAS" y "10 YEAR NOTE" no casan con nada en el fichero,
# donde los mercados se llaman "NAT GAS NYME" y "UST 10Y NOTE". Si un patron
# deja de casar, `serie_semanal` devuelve cero semanas y el z-score sale None
# —la pata se declara no evaluable— en vez de fallar en silencio; pero conviene
# revisar el patron antes que aceptar la degradacion.
SECTOR_A_FUTURO = {
    # WTI en ICE Europe: es la serie de posicionamiento mas profunda del crudo
    # ligero (40M de contratos de interes abierto acumulado en 2025 frente a
    # 8M del contrato financiero de NYMEX). Lo que se mide es el
    # posicionamiento en WTI, no el mercado donde se liquida.
    "Energy":             {"contrato": "CL=F", "cot": "CRUDE OIL, LIGHT SWEET-WTI", "signo": +1},
    "Basic Materials":    {"contrato": "HG=F", "cot": "COPPER- #1",   "signo": +1},
    # Henry Hub en NYMEX, que es el subyacente de NG=F. El contrato de ICE
    # (NAT GAS ICE LD1) tiene mas interes abierto, y por eso el patron es
    # especifico: un patron generico lo elegiria por el desempate de tamano y
    # estariamos midiendo el posicionamiento de otro contrato.
    "Utilities":          {"contrato": "NG=F", "cot": "NAT GAS NYME", "signo": +1},
    "Financial Services": {"contrato": "ZN=F", "cot": "UST 10Y NOTE", "signo": -1},
    "Real Estate":        {"contrato": "ZN=F", "cot": "UST 10Y NOTE", "signo": -1},
}

# Contrato de indice, aplicable a TODOS los sectores: mide apetito de riesgo
# agregado, no exposicion sectorial. Es la unica pata del bloque macro que nunca
# es NO_APLICABLE.
FUTURO_INDICE = {"contrato": "ES=F", "cot": "E-MINI S&P 500", "signo": +1}

# --- Informes COT (Commitments of Traders, CFTC) ---------------------------
# Categoria de trader: NO COMERCIAL (especulador). Los comerciales cubren
# produccion o inventario, asi que su posicion la dicta el negocio y no una
# opinion; los no comerciales son el flujo direccional marginal y su
# posicionamiento revierte a la media. La posicion comercial se reporta en el
# informe, pero no entra en el numero.
COT_VENTANA_SEMANAS = int(os.getenv("COT_VENTANA_SEMANAS", "156"))   # 3 anos
COT_MINIMO_SEMANAS = int(os.getenv("COT_MINIMO_SEMANAS", "52"))

# Escala del z-score al pasar por tanh. Con 1.5, un z de +1.5 da sesgo +0.76.
COT_ESCALA = float(os.getenv("COT_ESCALA", "1.5"))

# Por encima de este |z| el posicionamiento esta hacinado. NO invierte el signo
# —invertirlo produciria un clasificador no monotono, la misma patologia que
# tenia el momentum por puntos enteros— sino que prohibe perseguir el precio.
COT_Z_EXTREMO = float(os.getenv("COT_Z_EXTREMO", "2.0"))

# Retardo entre la fecha del informe (martes) y su publicacion (viernes 15:30
# ET). Es el `filed` frente a `end` del COT: filtrar por la fecha del informe en
# un backtest permite operar el miercoles con datos que nadie tenia.
COT_RETARDO_PUBLICACION_DIAS = int(os.getenv("COT_RETARDO_PUBLICACION_DIAS", "3"))

COT_URL_ANUAL = "https://www.cftc.gov/files/dea/history/deacot{anio}.zip"
COT_HTTP_TIMEOUT = float(os.getenv("COT_HTTP_TIMEOUT", "30"))

# Caches del dosier macro. La clave del COT es la FECHA DEL INFORME, no el dia
# de la ejecucion: cada informe es inmutable una vez publicado, asi que la cache
# queda ordenada point-in-time por construccion y el backtest la reutiliza.
MACRO_CACHE_DIR = os.getenv("MACRO_CACHE_DIR", "data/cache/futuros")
COT_CACHE_DIR = os.getenv("COT_CACHE_DIR", "data/cache/cot")
MACRO_CACHE_ENABLED = os.getenv("MACRO_CACHE_ENABLED", "1").lower() not in ("0", "false", "no")

# Cortes del sesgo macro continuo [-1, +1] sobre las cinco etiquetas. Mismo
# mecanismo que MOMENTUM_*: cortes sobre un numero, monotonos por construccion.
MACRO_VIENTO_FAVOR_FUERTE = float(os.getenv("MACRO_VIENTO_FAVOR_FUERTE", "0.45"))
MACRO_VIENTO_FAVOR = float(os.getenv("MACRO_VIENTO_FAVOR", "0.15"))
MACRO_VIENTO_CONTRA = float(os.getenv("MACRO_VIENTO_CONTRA", "-0.15"))
MACRO_VIENTO_CONTRA_FUERTE = float(os.getenv("MACRO_VIENTO_CONTRA_FUERTE", "-0.45"))

# --- Cadena de opciones ----------------------------------------------------
OPCIONES_VENTANA_DIAS = int(os.getenv("OPCIONES_VENTANA_DIAS", "45"))

# Open interest agregado minimo para que la cadena se considere utilizable. Por
# debajo, todo el bloque es NO_APLICABLE: un cero se leeria como "sin sesgo de
# posicionamiento", que es una afirmacion fuerte sobre una empresa cuya cadena
# nadie negocia.
OPCIONES_OI_MINIMO = int(os.getenv("OPCIONES_OI_MINIMO", "1000"))
OPCIONES_OI_MINIMO_STRIKE = int(os.getenv("OPCIONES_OI_MINIMO_STRIKE", "50"))
OPCIONES_MULTIPLICADOR = int(os.getenv("OPCIONES_MULTIPLICADOR", "100"))

# El percentil del put/call ratio y del skew se calcula sobre la cache
# ACUMULATIVA de cadenas diarias. Una instalacion nueva no puede emitirlos hasta
# acumular estas observaciones; hasta entonces se declara DATOS_INSUFICIENTES,
# NO el percentil 50. Mismo criterio que COBERTURA_MINIMA_ESTILO.
OPCIONES_MINIMO_DIAS_HISTORICO = int(os.getenv("OPCIONES_MINIMO_DIAS_HISTORICO", "60"))

# El max pain solo gravita cerca del vencimiento. Mas alla de este plazo no es
# candidato a nivel de referencia: a noventa dias es aritmetica, no una fuerza.
OPCIONES_MAXPAIN_DIAS_MAXIMO = int(os.getenv("OPCIONES_MAXPAIN_DIAS_MAXIMO", "21"))

# Percentil del put/call por debajo del cual la lectura es de complacencia, que
# es una forma de sobreextension y prohibe perseguir el precio.
OPCIONES_PCT_COMPLACENCIA = float(os.getenv("OPCIONES_PCT_COMPLACENCIA", "0.10"))

# Pesos de los CUATRO componentes del sesgo de opciones. Se normalizan sobre los
# DISPONIBLES, igual que PESOS_CONVICCION: imputar un cero a un componente
# ausente convertiria una ausencia en una lectura neutra.
#
# POR QUE EL CANAL DE OPEN INTEREST PESA MAS QUE NADA
# ---------------------------------------------------
# Este bloque no puntua la tendencia —de eso ya se encarga el Analista
# Tecnico—, puntua la CALIDAD DEL PRECIO al que se compraria. La posicion del
# precio entre el soporte y la resistencia de open interest responde
# exactamente a esa pregunta y esta disponible desde el primer dia, sin
# historico.
#
# La version anterior repartia el peso entre put/call, skew y distancia al
# punto de inflexion de la gamma. Los dos primeros exigian 60 dias de historico
# acumulado, asi que durante los primeros tres meses de vida del sistema NO
# VOTABAN: el sesgo de opciones era identico al termino de gamma, que crece
# cuanto mas ha subido el valor y por tanto duplicaba la pata tecnica. El
# resultado observado el 2026-08-30 fue AAPL cotizando en el percentil 98 de su
# canal de open interest —pegado a la resistencia— y recibiendo PERSEGUIR con
# entrada a mercado, que es el peor precio posible para una compra en largo.
PESO_CANAL_OI = float(os.getenv("PESO_CANAL_OI", "0.35"))
PESO_SKEW = float(os.getenv("PESO_SKEW", "0.25"))
PESO_PCR = float(os.getenv("PESO_PCR", "0.20"))
PESO_GEX = float(os.getenv("PESO_GEX", "0.20"))

# Posicion en el canal de open interest por encima de la cual comprar es
# comprar contra la oferta pendiente. Cuenta como SOBREEXTENSION, en la misma
# familia que el RSI extremo: no cambia la direccion, prohibe perseguir.
OPCIONES_CANAL_SOBREEXTENDIDO = float(os.getenv("OPCIONES_CANAL_SOBREEXTENDIDO", "0.85"))

# Asimetria del componente de gamma. Estar POR DEBAJO del punto de inflexion es
# una advertencia real —las coberturas de los creadores de mercado aceleran el
# movimiento en contra— pero estar muy por encima no es proporcionalmente
# alcista: solo dice que el colchon de amortiguacion queda lejos. Sin esta
# asimetria el termino es una funcion creciente de "cuanto ha subido el valor",
# es decir un proxy de momentum que duplica la pata tecnica.
GEX_ASIMETRIA_POSITIVA = float(os.getenv("GEX_ASIMETRIA_POSITIVA", "0.25"))

# Escala del skew normalizado (skew / IV at-the-money) al pasar por tanh. Con
# 0.15, un skew que valga el 15% de la volatilidad ATM da una lectura de 0.76.
SKEW_ESCALA = float(os.getenv("SKEW_ESCALA", "0.15"))

OPCIONES_CACHE_DIR = os.getenv("OPCIONES_CACHE_DIR", "data/cache/opciones")
OPCIONES_CACHE_ENABLED = os.getenv("OPCIONES_CACHE_ENABLED", "1").lower() not in ("0", "false", "no")

# --- Combinacion y ajuste de entrada ---------------------------------------
# Modulo minimo para que un componente cuente como senal en la confluencia. Por
# debajo es ruido y no vota ni a favor ni en contra.
UMBRAL_SENAL = float(os.getenv("UMBRAL_SENAL", "0.15"))

# Fraccion del recorrido hasta el nivel que se exige segun la clasificacion.
FACTOR_ENTRADA = {"PERSEGUIR": 0.0, "ESCALONAR": 0.5, "ESPERAR_RETROCESO": 1.0}

# Tope del ajuste, en ATR. Esta en unidades de volatilidad y no en un porcentaje
# fijo porque un ajuste mas profundo que el stop dejaria la entrada objetivo por
# DEBAJO del propio stop, que es incoherente. Con ATR_AJUSTE_POR_ESTILO en
# [1.5, 2.5] multiplos, acotar en 1*ATR lo deja siempre por encima.
AJUSTE_MAXIMO_ATR = float(os.getenv("AJUSTE_MAXIMO_ATR", "1.0"))


# =========================================================================== #
# REGIMEN DE VOLATILIDAD (FRED/ALFRED) — Analista de Regimen
# =========================================================================== #
# El sistema no tenia ninguna medida de estres sistemico: el COT mide
# posicionamiento POR CONTRATO, no regimen de mercado. Este bloque lo cubre con
# la unica serie macro que la Fase 1 acredito como PIT-NATIVE de verdad.
#
# POR QUE ALFRED Y NO UNA DESCARGA CUALQUIERA DEL VIX
# ---------------------------------------------------
# `realtime_start` / `realtime_end` devuelven la serie TAL Y COMO SE CONOCIA en
# esa fecha, y `output_type=4` (solo primera publicacion) hace que cada
# observacion venga con SU PROPIA fecha de publicacion. Es el mismo par
# `end`/`filed` del XBRL y el mismo `fecha_informe`/`fecha_publicacion` del COT,
# pero impuesto por el proveedor en vez de modelado por nosotros.
#
# Verificado el 2026-09-06: WALCL del miercoles 2020-03-25 es INVISIBLE
# consultando el 2020-03-25 y aparece el 2020-03-26. El retardo no hay que
# modelarlo; hay que no estorbarlo.
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_URL_OBSERVACIONES = "https://api.stlouisfed.org/fred/series/observations"
FRED_HTTP_TIMEOUT = float(os.getenv("FRED_HTTP_TIMEOUT", "30"))

# Clave por ANIO DE LA OBSERVACION, nunca por dia de ejecucion: cada fila lleva
# su fecha de publicacion, asi que la cache queda ordenada point-in-time por
# construccion y produccion y backtest comparten los mismos ficheros. Es
# exactamente el patron de `data/cache/cot/`.
FRED_CACHE_DIR = os.getenv("FRED_CACHE_DIR", "data/cache/fred")
FRED_CACHE_ENABLED = os.getenv("FRED_CACHE_ENABLED", "1").lower() not in ("0", "false", "no")

# Manifiesto append-only de recuperaciones. Sin el, "el backtest es reproducible"
# es una afirmacion que nadie puede comprobar.
FRED_MANIFIESTO = os.getenv("FRED_MANIFIESTO", "data/cache/fred/_manifiesto.jsonl")

# La API rechaza un rango con mas de 2000 fechas de vintage, y VIXCLS acumula
# 3926 desde 1990. Se pide ano a ano (~250 vintages) con margen para capturar la
# publicacion tardia de las ultimas observaciones del ano.
FRED_MARGEN_PUBLICACION_DIAS = int(os.getenv("FRED_MARGEN_PUBLICACION_DIAS", "60"))

SERIE_VOLATILIDAD = os.getenv("SERIE_VOLATILIDAD", "VIXCLS")
SERIE_VOLATILIDAD_3M = os.getenv("SERIE_VOLATILIDAD_3M", "VXVCLS")

# Ventana del z-score del nivel de volatilidad. 60 sesiones es la del repo 07,
# conservada porque su granularidad ya es diaria y no hay brecha de frecuencia
# que corregir.
REGIMEN_VENTANA_ZSCORE = int(os.getenv("REGIMEN_VENTANA_ZSCORE", "60"))
REGIMEN_MINIMO_OBSERVACIONES = int(os.getenv("REGIMEN_MINIMO_OBSERVACIONES", "40"))
REGIMEN_DIAS_HISTORICO = int(os.getenv("REGIMEN_DIAS_HISTORICO", "400"))

# Cortes del regimen. Los de nivel salen del `gate` del repo 07
# (vix_level_max=35, vix_z_max=2.0); el corte intermedio se anade porque el
# anfitrion necesita distinguir "no perseguir" de "no comprar", que alli era una
# sola puerta binaria.
REGIMEN_VIX_PANICO = float(os.getenv("REGIMEN_VIX_PANICO", "35.0"))
REGIMEN_VIX_TENSION = float(os.getenv("REGIMEN_VIX_TENSION", "25.0"))
REGIMEN_VIX_CALMA = float(os.getenv("REGIMEN_VIX_CALMA", "14.0"))
REGIMEN_Z_PANICO = float(os.getenv("REGIMEN_Z_PANICO", "2.0"))
REGIMEN_Z_TENSION = float(os.getenv("REGIMEN_Z_TENSION", "1.0"))

# Curva de volatilidad invertida (VIX > VIX3M): el estres es INMEDIATO, no de
# fondo. Discrimina mejor que el nivel a secas, que es el unico insumo de la
# puerta del repo 07.
REGIMEN_INVERSION_CURVA = float(os.getenv("REGIMEN_INVERSION_CURVA", "1.0"))


# =========================================================================== #
# ESTRUCTURA DE PRECIO — Analista de Estructura
# =========================================================================== #
# Ventanas de los minimos previos. Se EXCLUYE la barra en curso: es la
# traduccion a barra diaria del `shift(1)` de `_causal_levels` del repo 07. Un
# minimo que incluya la sesion de hoy no es un soporte previo, es el minimo de
# hoy.
NIVELES_VENTANAS = (10, 21, 63)

# Por encima de esta distancia al soporte estructural mas cercano, el valor
# cotiza sin referencia debajo. Cuenta como SOBREEXTENSION —misma familia que el
# RSI extremo y que el techo del canal de open interest—: no cambia la
# direccion, prohibe perseguir el precio.
SOPORTE_LEJANO_ATR = float(os.getenv("SOPORTE_LEJANO_ATR", "2.0"))

# Sesiones minimas de ventana para que los niveles sean calculables. Por debajo
# de la ventana mas larga mas una, `_minimo_previo` devolveria None de todos
# modos; se declara explicito para que la degradacion sea legible.
NIVELES_MINIMO_SESIONES = int(os.getenv("NIVELES_MINIMO_SESIONES", "64"))


# =========================================================================== #
# EJECUCION DE ORDEN LIMITADA (backtest)
# =========================================================================== #
# Sesiones que vive una orden limitada antes de cancelarse. Sin este parametro
# el motor no podia simular una entrada al precio objetivo, y por eso el ajuste
# de entrada era inmedible: NEXT_STEPS #1.
ORDEN_LIMITADA_VIDA_SESIONES = int(os.getenv("ORDEN_LIMITADA_VIDA_SESIONES", "10"))


# Denoising de Marchenko-Pastur sobre la matriz de correlaciones de la capa de
# cartera (`src/tools/covarianza.py`).
#
# DESACTIVADO POR DEFECTO, Y ES UNA MEDICION, NO UNA DUDA DE DISENO.
# ------------------------------------------------------------------
# Era el candidato con mejor relacion coste/beneficio de todo el encargo: la
# matriz de correlacion muestral de un rebalanceo es mayoritariamente ruido
# segun Marchenko-Pastur, y limpiarla no necesita NINGUN dato nuevo. Contrastado
# sobre el regimen `pit` 2015-2025 contra su ablacion exacta:
#
#              CAGR    Sharpe   acierto    PF   expectativa   percentil
#   sin ella   3.95%    0.68     44.6%    1.38    +1.229%        7.4
#   con ella   3.83%    0.66     44.4%    1.37    +1.251%        6.5
#
# Mejora la expectativa por operacion en 0.02pp y empeora el percentil frente a
# seleccion aleatoria en 0.9 — un criterio de aceptacion arriba y el otro abajo,
# que es exactamente el patron por el que este proyecto rechaza un cambio. El
# numero de operaciones y el drawdown no se mueven, porque su unico canal son
# los PESOS: el efecto es limpio y limpiamente negativo.
#
# Se conserva implementado, probado y desactivable, igual que `src/memoria/`.
CORRELACION_DENOISE = os.getenv("CORRELACION_DENOISE", "0").lower() not in ("0", "false", "no")


# =========================================================================== #
# META-ETIQUETADO (src/meta/ + src/tools/meta.py)
# =========================================================================== #
# El modelo primario —las reglas deterministas de este sistema— da el LADO. El
# meta-modelo responde «dado que dice comprar, ¿acierta?», y su salida es un
# factor de TAMANO, nunca un rating.
#
# LA MUESTRA MANDA SOBRE LA ARQUITECTURA, Y HAY QUE DECIRLO
# ----------------------------------------------------------
#     senales de compra del estudio ................ 944
#     tras el corte por desenlace y walk-forward .... ~200 en los primeros modelos
#     tamano EFECTIVO tras ponderar por unicidad .... menor todavia
#
# Con eso, un GBM con valores por defecto memoriza. Por eso el modelo es una
# regresion logistica con L2 fuerte: pocos parametros, coeficientes auditables y
# una probabilidad calibrada de fabrica, que es lo que un factor de tamano
# necesita.
META_HABILITADO = os.getenv("META_HABILITADO", "0").lower() not in ("0", "false", "no")

# Reentrenamiento walk-forward. NO se congela un artefacto unico: eso dejaria los
# anos de entrenamiento fuera del estudio y reduciria a la mitad una muestra que
# ya es pequena.
META_REENTRENAR_CADA_DIAS = int(os.getenv("META_REENTRENAR_CADA_DIAS", "365"))

# Etiquetas resueltas minimas para entregar artefacto. Por debajo, `entrenar`
# devuelve None con su motivo y la capa degrada a factor 1.0 — el estado normal
# de una instalacion reciente, igual que la memoria de reflexion no penaliza a
# nadie durante su primer ano.
META_MUESTRA_MINIMA = int(os.getenv("META_MUESTRA_MINIMA", "150"))

# CV purgada con embargo. El embargo por defecto es el horizonte tipico de una
# operacion (~21 sesiones): es exactamente el tiempo que una etiqueta tarda en
# resolverse, y por tanto el tramo que puede filtrarse hacia el bloque de prueba.
META_CV_PARTICIONES = int(os.getenv("META_CV_PARTICIONES", "5"))
META_EMBARGO_DIAS = int(os.getenv("META_EMBARGO_DIAS", "21"))

# Inversa de la fuerza de regularizacion de la logistica. C pequeno = mas
# regularizacion. 0.1 es deliberadamente agresivo para el tamano de muestra.
META_REGULARIZACION_C = float(os.getenv("META_REGULARIZACION_C", "0.1"))

# Ventaja minima sobre el azar (AUC 0.5) exigida en CV purgada para entregar
# artefacto. Un modelo que no bate a "apostar siempre" no es un filtro: es ruido
# con apariencia de prediccion, y entregarlo seria peor que no tener modelo.
META_VENTAJA_MINIMA_AUC = float(os.getenv("META_VENTAJA_MINIMA_AUC", "0.02"))

# Traduccion de probabilidad a factor. El punto neutro es la TASA BASE del
# entrenamiento, no 0.5: si el sistema acierta el 47% de sus compras, exigirle a
# una senal un 50% para no recortarla la penalizaria por una constante
# arbitraria.
META_ESCALA_DEFICIT = float(os.getenv("META_ESCALA_DEFICIT", "0.30"))
META_FACTOR_MINIMO = float(os.getenv("META_FACTOR_MINIMO", "0.50"))

META_DIR = os.getenv("META_DIR", "data/meta")
META_ARTEFACTO = os.getenv("META_ARTEFACTO", "data/meta/artefacto.json")
META_BANCO = os.getenv("META_BANCO", "data/meta/etiquetas.jsonl")

# Diferenciacion fraccional (AFML cap. 5). El `d` se FIJA, no se busca:
# `find_min_ffd` necesita el test ADF de statsmodels, que esta descartado, y
# buscarlo sobre la misma ventana que despues se evalua seria un ensayo mas sin
# contar. 0.4 es el valor central del rango que LdP reporta como suficiente para
# estacionariedad en series de precios diarias.
FFD_D = float(os.getenv("FFD_D", "0.4"))

# Umbral de truncamiento de la serie de pesos. NO es un parametro libre: fija
# cuantos rezagos necesita cada punto, y ESE numero tiene que caber en la
# ventana disponible.
#
#   umbral 1e-4 -> 282 rezagos     umbral 5e-4 ->  90 rezagos
#   umbral 1e-3 ->  55 rezagos     umbral 5e-3 ->  18 rezagos
#
# La ventana del replay es de 365 dias naturales, es decir ~250 sesiones. Con
# 1e-4 la variable era `None` en TODAS las filas y el meta-modelo se negaba a
# entrenar — correctamente, porque descartar una fila con una variable ausente es
# la regla del proyecto, y el sintoma fue justo el que tenia que ser: "0
# etiquetas utilizables" en lugar de un modelo entrenado sobre datos imputados.
#
# 5e-4 deja 90 rezagos, holgadamente dentro de la ventana, y conserva mucha mas
# memoria que los 18 de 5e-3.
FFD_UMBRAL = float(os.getenv("FFD_UMBRAL", "5e-4"))


# =========================================================================== #
# FRENO POR DRAWDOWN (src/tools/riesgo.py)
# =========================================================================== #
# `drawdown_guard` del repositorio 03, traducido de excepcion a factor que solo
# recorta. INERTE EN PRODUCCION: el sistema emite recomendaciones, no gestiona
# una cartera, y no conoce su patrimonio. Declarado en `build_limitations()`.
DRAWDOWN_UMBRAL = float(os.getenv("DRAWDOWN_UMBRAL", "0.10"))
DRAWDOWN_ESCALA = float(os.getenv("DRAWDOWN_ESCALA", "0.20"))
DRAWDOWN_FACTOR_MINIMO = float(os.getenv("DRAWDOWN_FACTOR_MINIMO", "0.40"))
