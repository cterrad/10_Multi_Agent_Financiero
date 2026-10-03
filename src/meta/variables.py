"""
Qué mira el meta-modelo, y por qué todo es point-in-time por construcción.

NINGUNA FUENTE NUEVA
--------------------
Todas las variables salen del **estado de la propia señal en `t`**, que el
replay ya reconstruye point-in-time y que los tests de no-look-ahead ya
protegen. No hay una sola serie externa que no estuviera ya en el sistema, así
que el meta-modelo no puede introducir una fuga que las capas anteriores no
tuvieran.

EL ESTILO Y EL RÉGIMEN NO SE CODIFICAN CON `one-hot`
-----------------------------------------------------
Con 944 señales de compra y diez estilos posibles, diez columnas casi vacías son
diez formas de sobreajustar. Se codifican como **escalares ordinales** cuando el
orden significa algo (el régimen: calma < normal < tensión < pánico) y se
descartan cuando no (el estilo, cuyo efecto ya está capturado por las cuatro
puntuaciones de calidad que lo determinan).

Es la misma disciplina que impone el tamaño de muestra sobre la elección de
modelo: con esta cantidad de datos, cada grado de libertad hay que justificarlo.

DOS VARIABLES QUE NO ESTÁN, Y NO POR OLVIDO
--------------------------------------------
**`distancia_stop_pct`** sería circular: la produce el Fund Manager, que es justo
quien consumiría la predicción. Y además no aportaría nada — es
`múltiplo_stop · atr / precio`, una función determinista del estilo y del
`atr_pct`, que ya son variables.

**`confluencia`** es `None` por construcción siempre que el sesgo agregado no es
alcista, porque entonces no hay entrada que optimizar. Medido sobre las etiquetas
resueltas del estudio, eso ocurre en **el 34% de las señales de compra**, y como
una fila con cualquier variable ausente se descarta entera —no se imputa—
exigirla costaría un tercio de una muestra que ya es pequeña. Su información,
además, es en buena parte redundante: la confluencia se calcula a partir del
sesgo macro y del momentum, que sí están.

En una muestra de 944, cada grado de libertad hay que justificarlo, y una columna
que cuesta un tercio de las filas para repetir lo que ya dicen otras dos no se
justifica.

LA DIFERENCIACIÓN FRACCIONAL ENTRA AQUÍ Y SOLO AQUÍ
----------------------------------------------------
`frac_diff` (AFML cap. 5) busca el punto intermedio entre una serie de precios
—no estacionaria pero con memoria— y sus retornos —estacionarios pero sin
memoria. Tiene sentido **como variable de un modelo** y ninguno como entrada de
una regla determinista: el sistema no tiene ninguna regla que consuma un nivel
de precio transformado, y añadir una sería inventar una regla para justificar
una técnica.

Por eso el candidato nº 4 del inventario se cierra aquí: como una columna más,
cuya inclusión decide la CV purgada igual que la de cualquier otra.
"""

from typing import Any, Dict, List, Optional

# Orden de los regímenes de volatilidad. El orden ES la información: calma <
# normal < tensión < pánico. Codificarlo como escalar gasta un grado de libertad
# en vez de cuatro.
_ORDEN_REGIMEN = {"CALMA": 0.0, "NORMAL": 1.0, "TENSION": 2.0, "PANICO": 3.0}
_ORDEN_ESTRUCTURA = {"PEGADO_AL_SOPORTE": 0.0, "APOYADO": 1.0, "HOLGADO": 2.0}
_ORDEN_MACRO = {
    "VIENTO_EN_CONTRA_FUERTE": 0.0, "VIENTO_EN_CONTRA": 1.0, "NEUTRO": 2.0,
    "VIENTO_A_FAVOR": 3.0, "VIENTO_A_FAVOR_FUERTE": 4.0,
}

#: Conjunto CERRADO de variables. Añadir una es un ensayo más que contar en el
#: recuento del Sharpe deflactado, así que la lista es explícita y no se deriva
#: de las claves que casualmente traiga un estado.
VARIABLES_META: List[str] = [
    # Calidad
    "conviccion", "puntuacion_calidad", "puntuacion_valoracion",
    "puntuacion_crecimiento", "puntuacion_solvencia", "n_banderas",
    # Técnico
    "momentum_score", "rsi", "atr_pct", "dist_sma_50_pct", "dist_sma_200_pct",
    "posicion_rango_52w", "volatilidad_anual",
    # Estructura de precio
    "distancia_soporte_atr", "estructura_ord",
    # Régimen de volatilidad
    "nivel_volatilidad", "zscore_volatilidad", "ratio_curva", "volatilidad_relativa",
    "regimen_ord",
    # Posicionamiento
    "sesgo_macro_ord",
    # Datos
    "confianza_datos",
    # Memoria del precio (AFML cap. 5)
    "frac_diff",
]


def _num(v: Any) -> Optional[float]:
    """Convierte a float o devuelve None. **Nunca 0.0 por defecto.**"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and abs(f) != float("inf") else None


def variables_de_senal(estado: Dict[str, Any],
                       frac_diff: Optional[float] = None) -> Dict[str, Optional[float]]:
    """
    Extrae el vector de variables del estado ya reconstruido de una señal.

    Devuelve `None` en la variable que falte. Quien entrena descarta la fila
    entera —no imputa— porque rellenar con la media convertiría una ausencia en
    una observación, que es el defecto que `src/data/magnitudes.py` corrige en
    todo el resto del sistema.
    """
    q = estado.get("quality_report", {}) or {}
    t = estado.get("technical_report", {}) or {}
    e = estado.get("estructura_report", {}) or {}
    g = estado.get("regimen_report", {}) or {}
    p = estado.get("positioning_report", {}) or {}
    rec = estado.get("reconciliation_data", {}) or {}
    raw = (estado.get("yfinance_data", {}) or {}).get("technical", {}) or {}
    punt = q.get("puntuaciones", {}) or {}

    return {
        "conviccion": _num((q.get("conviccion_fundamental") or {}).get("valor")),
        "puntuacion_calidad": _num(punt.get("calidad")),
        "puntuacion_valoracion": _num(punt.get("valoracion")),
        "puntuacion_crecimiento": _num(punt.get("crecimiento")),
        "puntuacion_solvencia": _num(punt.get("solvencia")),
        "n_banderas": float(len(q.get("banderas_rojas", []) or [])),
        "momentum_score": _num(t.get("momentum_score")),
        "rsi": _num(raw.get("rsi")),
        "atr_pct": _num(raw.get("atr_pct")),
        "dist_sma_50_pct": _num(raw.get("dist_sma_50_pct")),
        "dist_sma_200_pct": _num(raw.get("dist_sma_200_pct")),
        "posicion_rango_52w": _num(raw.get("posicion_rango_52w")),
        "volatilidad_anual": _num(raw.get("volatilidad_anual")),
        "distancia_soporte_atr": _num(e.get("distancia_atr")),
        "estructura_ord": _ORDEN_ESTRUCTURA.get(e.get("estructura")),
        "nivel_volatilidad": _num(g.get("nivel_volatilidad")),
        "zscore_volatilidad": _num(g.get("zscore_volatilidad")),
        "ratio_curva": _num(g.get("ratio_curva")),
        "volatilidad_relativa": _num(g.get("volatilidad_relativa")),
        "regimen_ord": _ORDEN_REGIMEN.get(g.get("regimen_clasificacion")),
        "sesgo_macro_ord": _ORDEN_MACRO.get(p.get("sesgo_macro_clasificacion")),
        "confianza_datos": _num(rec.get("confidence_score")),
        "frac_diff": _num(frac_diff),
    }
