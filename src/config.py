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
