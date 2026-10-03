"""
Clasificación point-in-time de las fuentes que alcanzan la ruta de decisión.

POR QUÉ ESTO ES UN TEST Y NO UN PÁRRAFO
----------------------------------------
`output/FUENTES_DATOS.md` clasifica cada fuente en PIT-NATIVE, PIT-ARCHIVABLE o
NO-HISTORY, y la puerta del proyecto dice que solo las dos primeras pueden
alimentar una decisión — la segunda además solo cuando su archivo local cubre la
ventana del estudio. **Esa clasificación no puede vivir únicamente en prosa**:
un documento no impide que alguien conecte mañana una fuente de las que no
tienen historia, y el backtest dejaría de ser válido sin que nada fallara.

Aquí se afirma en código:

  1. El inventario de fuentes de decisión es CERRADO y explícito. Añadir una
     obliga a pasar por este fichero y a declarar su clase.
  2. Ninguna fuente `NO-HISTORY` toca una variable de decisión. Es lo que
     mantiene a las noticias como capa asesora.
  3. La única fuente `PIT-ARCHIVABLE` de la ruta de decisión —la cadena de
     opciones— **no cubre la ventana del estudio**, y por eso el backtest la
     declara ausente. Que ese hecho esté afirmado aquí impide que alguien la dé
     por buena sin archivo.
  4. El archivo de la serie de régimen SÍ cubre la ventana, y se comprueba
     contra el disco: si la caché no llegara a 2015, el veto de régimen estaría
     midiéndose sobre un tramo distinto del que el informe declara.

Offline: solo se lee `data/cache/`, nunca la red.
"""

from pathlib import Path

import pytest

from src.config import FRED_CACHE_DIR, SERIE_VOLATILIDAD, SERIE_VOLATILIDAD_3M
from src.data.fred import series_requeridas
from src.data.fred.cache import leer_serie

# Inventario CERRADO de las fuentes que alcanzan alguna variable de decisión,
# con su clase según `output/FUENTES_DATOS.md`. Añadir una fuente a la ruta de
# decisión sin añadirla aquí hace fallar `test_el_inventario_esta_completo`.
FUENTES_DE_DECISION = {
    "yfinance_precios":      "PIT-NATIVE",       # S4, ya protegida por PriceStore
    "sec_edgar_companyfacts": "PIT-NATIVE",      # S6, filed <= t
    "cftc_cot":              "PIT-NATIVE",       # S5, fecha_publicacion
    "fred_alfred_volatilidad": "PIT-NATIVE",     # S1/S2, realtime_start/end
    "yfinance_cadena_opciones": "PIT-ARCHIVABLE",  # S12, archivo acumulativo
}

# Fuentes que NO pueden tocar una decisión, por clase.
FUENTES_ASESORAS = {
    "google_news_rss": "NO-HISTORY",
    "tavily":          "NO-HISTORY",
    "sec_8k":          "PIT-NATIVE",   # reconstruible, pero la capa entera es asesora
}

VENTANA_ESTUDIO = (2015, 2025)


def test_ninguna_fuente_sin_historia_alcanza_la_decision():
    """
    LA PUERTA. Una fuente que solo sirve «hoy» no puede producir un número que
    entre en un dictamen: el backtest no podría reproducirlo y el estudio dejaría
    de medir lo que el sistema decide.
    """
    for nombre, clase in FUENTES_DE_DECISION.items():
        assert clase in ("PIT-NATIVE", "PIT-ARCHIVABLE"), (
            f"`{nombre}` está clasificada {clase} y alcanza la ruta de decisión")


def test_el_inventario_esta_completo():
    """
    Recordatorio en forma de test: el conjunto de fuentes de decisión es cerrado
    y este fichero es donde se declara. Si el sistema incorpora una fuente nueva
    a la decisión, aquí tiene que aparecer con su clase.
    """
    esperadas = {"yfinance_precios", "sec_edgar_companyfacts", "cftc_cot",
                 "fred_alfred_volatilidad", "yfinance_cadena_opciones"}
    assert set(FUENTES_DE_DECISION) == esperadas, (
        "el inventario de fuentes de decisión ha cambiado sin actualizar "
        "`output/FUENTES_DATOS.md` ni este test")


def test_la_cadena_de_opciones_no_cubre_la_ventana_y_por_eso_el_replay_la_omite():
    """
    La ÚNICA PIT-ARCHIVABLE de la ruta de decisión. Su archivo local empieza el
    día que se instaló el sistema, no en 2015, así que **no puede alimentar el
    estudio** y el replay la declara ausente con su motivo.

    Este test comprueba precisamente eso: que el replay NO la reconstruye. Si
    algún día alguien la conectara sin archivo que cubra la ventana, el estudio
    estaría midiendo una cadena inventada.
    """
    from src.backtest.replay import HistoricalReplayer
    import inspect
    fuente = inspect.getsource(HistoricalReplayer.build_state)
    assert '"disponible": False' in fuente, (
        "el replay ha dejado de declarar la cadena de opciones como ausente")
    assert "de pago" in fuente, (
        "el replay ha dejado de declarar el MOTIVO de la ausencia")


def test_el_archivo_de_volatilidad_cubre_la_ventana_del_estudio():
    """
    La serie de régimen SÍ alimenta la decisión, así que su archivo tiene que
    cubrir la ventana. Se comprueba contra el disco y no contra la documentación:
    si la caché no llegara a 2015, el veto se estaría midiendo sobre un tramo
    distinto del que el informe declara.

    Se omite —no falla— cuando no hay caché: una instalación recién clonada aún
    no ha ejecutado `python -m src.data.fred.backfill`, y eso no es un defecto.
    """
    base = Path(FRED_CACHE_DIR)
    if not base.exists() or not any(base.glob("*.json")):
        pytest.skip("sin caché de FRED: ejecuta `python -m src.data.fred.backfill`")

    inicio, fin = VENTANA_ESTUDIO
    for serie in series_requeridas():
        anios_ok = [a for a in range(inicio, fin + 1)
                    if (leer_serie(serie, a) or [])]
        faltan = sorted(set(range(inicio, fin + 1)) - set(anios_ok))
        assert not faltan, (
            f"el archivo de {serie} no cubre {faltan}; el veto de régimen se "
            f"estaría midiendo sobre una ventana distinta de la declarada")


def test_toda_observacion_archivada_lleva_su_fecha_de_publicacion():
    """
    Sin fecha de publicación por observación no hay selección point-in-time
    posible: es el par `filed`/`end`, y una fila que no lo lleve es una fila que
    no se puede filtrar.
    """
    base = Path(FRED_CACHE_DIR)
    if not base.exists() or not any(base.glob("*.json")):
        pytest.skip("sin caché de FRED")

    filas = leer_serie(SERIE_VOLATILIDAD, 2020) or []
    assert filas, "no hay archivo de 2020 para la serie de volatilidad"
    for f in filas[:50]:
        assert f.get("fecha") and f.get("fecha_publicacion"), (
            f"observación sin el par fecha/fecha_publicacion: {f}")
        assert f["fecha_publicacion"] >= f["fecha"], (
            f"una observación no puede publicarse antes de existir: {f}")


def test_la_serie_a_tres_meses_declara_su_frontera_de_archivo():
    """
    `VXVCLS` observa desde 2007 pero su ARCHIVO en ALFRED solo empieza en 2014:
    pedir 2013 devuelve «the series does not exist in ALFRED». Es una frontera de
    cobertura declarada, no un fallo, y afecta solo al componente de curva — que
    degrada a `ratio_curva = None` sin inventar nada.

    Se comprueba que el archivo NO tiene 2013, para que nadie asuma que sí.
    """
    base = Path(FRED_CACHE_DIR)
    if not base.exists() or not any(base.glob("*.json")):
        pytest.skip("sin caché de FRED")
    assert leer_serie(SERIE_VOLATILIDAD_3M, 2013) is None, (
        "si esto pasa a existir, actualiza la frontera declarada en "
        "`output/FUENTES_DATOS.md` y en `build_limitations()`")
