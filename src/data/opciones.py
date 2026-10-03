"""
Ingesta y normalizacion de la cadena de opciones (yfinance).

Que hace y que NO hace
----------------------
Descarga los contratos de los vencimientos dentro de la ventana, los normaliza
a una lista plana y calcula AGREGADOS ELEMENTALES (sumas de open interest y de
volumen por tipo, volatilidad implicita de los strikes de referencia fuera de
dinero). Nada mas.

El put/call ratio, sus percentiles, el max pain, la exposicion gamma y el skew
son reglas de decision y viven en `src/tools/opciones.py`. La frontera es la
misma que ya separa `_resumen_precios()` —que calcula rentabilidades a 1, 3 y
12 meses— del bloque de momentum que las puntua: agregar no es decidir.

LA CACHE ES ACUMULATIVA, Y ESO NO ES UN DESCUIDO
------------------------------------------------
`data/cache/opciones/{TICKER}_{YYYY-MM-DD}.json`, un fichero por ticker y dia,
y los de dias anteriores NO se borran. El percentil del put/call ratio y el del
skew se calculan frente al historico propio del valor —que es el criterio que
importa, no el nivel absoluto— y yfinance solo publica la cadena de HOY. Esta
cache es lo mas parecido a un almacen point-in-time de cadenas que se puede
construir sin pagar por los datos.

Consecuencia declarada: una instalacion nueva no puede emitir esos percentiles
hasta acumular `OPCIONES_MINIMO_DIAS_HISTORICO` observaciones. Hasta entonces
el subbloque se declara DATOS_INSUFICIENTES, nunca el percentil 50.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import (
    OPCIONES_CACHE_DIR,
    OPCIONES_CACHE_ENABLED,
    OPCIONES_MINIMO_DIAS_HISTORICO,
    OPCIONES_OI_MINIMO,
    OPCIONES_VENTANA_DIAS,
)

NOMBRE = "cadena_opciones"

# Moneyness de los strikes de referencia para el skew. Fijos y declarados: la
# seleccion por delta de 25 es la refinacion natural, pero exige calcular las
# Griegas aqui, y las Griegas son una regla de calculo que pertenece a las
# tools. Con moneyness fijo el agregado sigue siendo aritmetica.
MONEYNESS_PUT = 0.90
MONEYNESS_CALL = 1.10


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
def _ruta(ticker: str, dia: str, directorio: Optional[Path] = None) -> Path:
    base = Path(directorio) if directorio else Path(OPCIONES_CACHE_DIR)
    return base / f"{ticker.upper()}_{dia}.json"


def leer(ticker: str, dia: Optional[str] = None,
         directorio: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    if not OPCIONES_CACHE_ENABLED and directorio is None:
        return None
    ruta = _ruta(ticker, dia or date.today().isoformat(), directorio)
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return None


def escribir(ticker: str, payload: Dict[str, Any], dia: Optional[str] = None,
             directorio: Optional[Path] = None) -> None:
    if not OPCIONES_CACHE_ENABLED and directorio is None:
        return
    ruta = _ruta(ticker, dia or date.today().isoformat(), directorio)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        print(f"[CadenaOpciones] No se pudo escribir la cache de {ticker}: {exc}")


def historico_agregados(ticker: str, hasta: Optional[str] = None,
                        maximo: int = 400,
                        directorio: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Agregados diarios de las cadenas ya cacheadas, de la mas antigua a la mas
    reciente y SIN incluir `hasta`.

    Es el historico sobre el que la tool calcula los percentiles. Se excluye el
    dia en curso a proposito: un percentil que se compara consigo mismo esta
    sesgado hacia el centro.
    """
    base = Path(directorio) if directorio else Path(OPCIONES_CACHE_DIR)
    if not base.exists():
        return []
    tope = hasta or date.today().isoformat()
    filas: List[Dict[str, Any]] = []
    for ruta in sorted(base.glob(f"{ticker.upper()}_*.json")):
        dia = ruta.stem.split("_")[-1]
        if dia >= tope:
            continue
        try:
            payload = json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:
            continue
        agg = payload.get("agregados")
        if isinstance(agg, dict) and agg.get("oi_calls"):
            filas.append({"fecha": dia, **agg})
    return filas[-maximo:]


# --------------------------------------------------------------------------- #
# Normalizacion
# --------------------------------------------------------------------------- #
def _limpio(valor: Any) -> Optional[float]:
    if valor is None:
        return None
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _agregados(contratos: List[Dict[str, Any]], spot: Optional[float],
               vencimiento_ref: Optional[str]) -> Dict[str, Any]:
    """
    Sumas por tipo y volatilidad implicita de los strikes de referencia.

    El skew se mide sobre UN vencimiento —el de referencia— y no sobre toda la
    ventana: mezclar vencimientos mete la estructura temporal de la volatilidad
    dentro de una medida que pretende ser de asimetria, y las dos cosas se
    mueven por motivos distintos.
    """
    calls = [c for c in contratos if c["tipo"] == "call"]
    puts = [c for c in contratos if c["tipo"] == "put"]

    def iv_referencia(lote: List[Dict[str, Any]], objetivo: Optional[float]) -> Optional[float]:
        if not objetivo or not lote:
            return None
        candidatos = [c for c in lote
                      if c.get("iv") is not None
                      and (vencimiento_ref is None or c["vencimiento"] == vencimiento_ref)]
        if not candidatos:
            return None
        mejor = min(candidatos, key=lambda c: abs(c["strike"] - objetivo))
        return round(mejor["iv"], 6)

    # Volatilidad implicita at-the-money: es el DENOMINADOR que hace comparable
    # el skew entre valores y entre fechas sin necesidad de historico. Un skew
    # de 0.04 significa cosas distintas en un valor que cotiza al 25% de
    # volatilidad y en otro al 80%.
    iv_atm = iv_referencia(calls, spot) or iv_referencia(puts, spot)

    return {
        "oi_calls": sum(c["open_interest"] for c in calls),
        "oi_puts": sum(c["open_interest"] for c in puts),
        "vol_calls": sum(c["volumen"] for c in calls),
        "vol_puts": sum(c["volumen"] for c in puts),
        "iv_call_otm": iv_referencia(calls, spot * MONEYNESS_CALL if spot else None),
        "iv_put_otm": iv_referencia(puts, spot * MONEYNESS_PUT if spot else None),
        "iv_atm": iv_atm,
        "vencimiento_referencia": vencimiento_ref,
        "spot": round(spot, 4) if spot else None,
    }


def _no_disponible(ticker: str, dia: str, motivo: str) -> Dict[str, Any]:
    """Cadena inutilizable. Se declara con su motivo; nunca se rellena con ceros."""
    return {
        "disponible": False, "motivo": motivo, "ticker": ticker.upper(),
        "as_of": dia, "spot": None, "contratos": [], "vencimientos": [],
        "oi_total": 0, "agregados": {}, "historico": [], "n_dias_historico": 0,
        "minimo_dias_historico": OPCIONES_MINIMO_DIAS_HISTORICO,
        "desde_cache": False,
    }


def normalizar(cadenas_por_vencimiento: Dict[str, Any], spot: Optional[float],
               ticker: str, dia: str, ventana_dias: int) -> Dict[str, Any]:
    """
    Estructuras de yfinance a una lista plana de contratos.

    `cadenas_por_vencimiento` es `{fecha_iso: (df_calls, df_puts)}`. Se separa
    de la descarga para que los tests puedan construir cadenas a mano sin red.
    """
    hoy = date.fromisoformat(dia)
    contratos: List[Dict[str, Any]] = []
    vencimientos: List[Dict[str, Any]] = []

    for fecha_venc, (df_calls, df_puts) in sorted(cadenas_por_vencimiento.items()):
        try:
            dias = (date.fromisoformat(fecha_venc) - hoy).days
        except ValueError:
            continue
        if dias < 0 or dias > ventana_dias:
            continue
        n_venc = 0
        for tipo, df in (("call", df_calls), ("put", df_puts)):
            if df is None:
                continue
            for fila in df.to_dict("records") if hasattr(df, "to_dict") else df:
                strike = _limpio(fila.get("strike"))
                if strike is None or strike <= 0:
                    continue
                oi = _limpio(fila.get("openInterest")) or 0.0
                vol = _limpio(fila.get("volume")) or 0.0
                iv = _limpio(fila.get("impliedVolatility"))
                contratos.append({
                    "tipo": tipo, "strike": round(strike, 4), "vencimiento": fecha_venc,
                    "dias": dias, "open_interest": int(oi), "volumen": int(vol),
                    # Sin volatilidad implicita no hay Gamma. Viaja como None y
                    # el bloque que la necesita se declara NO_APLICABLE.
                    "iv": iv,
                })
                n_venc += 1
        if n_venc:
            vencimientos.append({"fecha": fecha_venc, "dias": dias, "n_contratos": n_venc})

    oi_total = sum(c["open_interest"] for c in contratos)
    if not contratos:
        return _no_disponible(ticker, dia,
                              f"sin contratos en los proximos {ventana_dias} dias")
    if oi_total < OPCIONES_OI_MINIMO:
        return _no_disponible(
            ticker, dia,
            f"open interest agregado {oi_total} por debajo del minimo "
            f"{OPCIONES_OI_MINIMO}: la cadena no es liquida")

    # Vencimiento de referencia: el de mayor open interest dentro de la ventana.
    # Regla fija y declarada; sin ella la eleccion dependeria del orden.
    oi_por_venc: Dict[str, int] = {}
    for c in contratos:
        oi_por_venc[c["vencimiento"]] = oi_por_venc.get(c["vencimiento"], 0) + c["open_interest"]
    venc_ref = sorted(oi_por_venc.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if oi_por_venc else None

    return {
        "disponible": True, "motivo": None, "ticker": ticker.upper(), "as_of": dia,
        "spot": round(spot, 4) if spot else None,
        "ventana_dias": ventana_dias,
        "vencimientos": vencimientos,
        "contratos": contratos,
        "oi_total": oi_total,
        "agregados": _agregados(contratos, spot, venc_ref),
        "desde_cache": False,
    }


# --------------------------------------------------------------------------- #
# Recoleccion
# --------------------------------------------------------------------------- #
def recolectar_cadena(ticker: str, ventana_dias: int = OPCIONES_VENTANA_DIAS,
                      dia: Optional[str] = None, offline: bool = False,
                      directorio: Optional[Path] = None) -> Dict[str, Any]:
    """
    Cadena del dia, de cache si existe, mas el historico para los percentiles.

    Nunca lanza: un fallo devuelve la cadena declarada como no disponible con su
    motivo, y el agente degrada el bloque de opciones a NO_APLICABLE.
    """
    dia = dia or date.today().isoformat()
    ticker = ticker.upper()

    payload = leer(ticker, dia, directorio)
    if payload is not None:
        payload["desde_cache"] = True
    elif offline:
        payload = _no_disponible(ticker, dia, f"modo offline y sin cache para {dia}")
    else:
        payload = _descargar(ticker, ventana_dias, dia)
        if payload.get("disponible"):
            escribir(ticker, payload, dia, directorio)

    historico = historico_agregados(ticker, hasta=dia, directorio=directorio)
    payload["historico"] = historico
    payload["n_dias_historico"] = len(historico)
    payload["minimo_dias_historico"] = OPCIONES_MINIMO_DIAS_HISTORICO
    return payload


def _descargar(ticker: str, ventana_dias: int, dia: str) -> Dict[str, Any]:
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        vencimientos = list(getattr(stock, "options", []) or [])
    except Exception as exc:  # pragma: no cover - depende de la red
        return _no_disponible(ticker, dia, f"{type(exc).__name__}: {exc}")

    if not vencimientos:
        return _no_disponible(ticker, dia, "yfinance no publica vencimientos para este valor")

    try:
        historial = stock.history(period="5d")
        spot = float(historial["Close"].dropna().iloc[-1]) if not historial.empty else None
    except Exception:
        spot = None

    hoy = date.fromisoformat(dia)
    cadenas: Dict[str, Any] = {}
    for fecha_venc in vencimientos:
        try:
            dias = (datetime.strptime(fecha_venc, "%Y-%m-%d").date() - hoy).days
        except ValueError:
            continue
        if dias < 0 or dias > ventana_dias:
            continue
        try:
            chain = stock.option_chain(fecha_venc)
            cadenas[fecha_venc] = (chain.calls, chain.puts)
        except Exception as exc:
            # Un vencimiento que falla no invalida los demas.
            print(f"[CadenaOpciones] {ticker} {fecha_venc}: {exc}")

    if not cadenas:
        return _no_disponible(ticker, dia,
                              f"ningun vencimiento utilizable en {ventana_dias} dias")
    return normalizar(cadenas, spot, ticker, dia, ventana_dias)
