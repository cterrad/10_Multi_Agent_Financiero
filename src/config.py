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
