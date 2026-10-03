
"""
Etiquetado por triple barrera sobre las barreras QUE EL PROPIO SISTEMA EMITIÓ.

QUÉ PREGUNTA RESPONDE
---------------------
«Si el sistema hubiera abierto esta operación, ¿habría acabado en beneficio?»
Es la etiqueta del meta-etiquetado de López de Prado (AFML cap. 3): el modelo
primario —aquí, las reglas deterministas del anfitrión— da el LADO, y esta
etiqueta dice si acertó.

POR QUÉ LAS BARRERAS SON LAS DEL SISTEMA Y NO MÚLTIPLOS GENÉRICOS
------------------------------------------------------------------
Había dos formas de etiquetar y solo una responde a la pregunta:

  ❌ Triple barrera con múltiplos de volatilidad arbitrarios. Mediría si el
     momento era bueno para *alguna* operación, que no es lo que se pregunta.
  ✅ Triple barrera con el `stop_loss_atr`, el `take_profit_atr` y el
     `horizonte_dias` **que el Fund Manager publicó para esa señal concreta**.
     Mide exactamente la operación que el sistema habría abierto.

La segunda no inventa ninguna regla nueva: reutiliza tres variables de decisión
que el sistema ya emite y publica. Y es lo que hace que la etiqueta sea
interpretable — un 0 significa «esta operación, tal y como el sistema la
dimensionó, habría perdido».

LA RESOLUCIÓN ES LA MISMA QUE LA DEL MOTOR, Y ESO NO ES CASUAL
---------------------------------------------------------------
`process_intraday_exits` en `src/backtest/engine.py` resuelve stop y objetivo
contra el rango de cada barra, y **si los dos se tocan en la misma sesión asume
que saltó el stop**, porque sin datos intradía no se sabe cuál ocurrió antes y
equivocarse al alza infla el resultado.

Esta función aplica LA MISMA regla. Si divergiera, el modelo se entrenaría con
un desenlace distinto del que el backtest simula, y la comparación dejaría de
significar nada.

LA FECHA DE DESENLACE ES EL PUNTO DE CORTE, NO LA DE LA SEÑAL
--------------------------------------------------------------
`t1` —la fecha en que la barrera se resuelve— es lo que hace utilizable la
etiqueta. Una señal del 1 de junio con horizonte hasta julio **no se sabe cómo
terminó hasta julio**, y entrenar con ella en junio es mirar el futuro. Es el
mismo par `filed`/`end` del XBRL, `fecha_informe`/`fecha_publicacion` del COT y
`fecha_desenlace` de `src/memoria/`, aplicado por cuarta vez.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

# Motivos de cierre. Son los mismos nombres que usa `engine.py` en
# `exit_reason`, para que las dos capas hablen el mismo idioma.
STOP = "stop_loss"
OBJETIVO = "take_profit"
TIEMPO = "vertical"


def _etiquetar(barras: List[Dict[str, float]], entrada: float,
               stop: Optional[float], objetivo: Optional[float],
               horizonte: int) -> Dict[str, Any]:
    """
    Resuelve una operación contra las barras POSTERIORES a la señal.

    `barras` es la serie futura, cada elemento con `fecha`, `high` y `low`, y el
    llamante ya la ha cortado: esta función no conoce el calendario y no puede
    mirar más allá de lo que se le da. Que el corte lo haga quien llama es
    deliberado — la disciplina point-in-time vive en un solo sitio.

    Devuelve `etiqueta = None` cuando la operación **no ha terminado todavía**.
    Eso NO es un cero: un cero significa «acabó en pérdida», y confundirlos
    metería en el entrenamiento operaciones cuyo desenlace aún no se conoce, que
    es exactamente el look-ahead que este módulo existe para impedir.
    """
    if not entrada or entrada <= 0 or not barras:
        return {"etiqueta": None, "motivo": "sin precio de entrada o sin barras futuras",
                "fecha_desenlace": None, "salida": None, "retorno": None,
                "razon": None, "sesiones": None}

    ventana = barras[:horizonte] if horizonte and horizonte > 0 else barras
    for i, b in enumerate(ventana):
        bajo, alto = b.get("low"), b.get("high")
        if bajo is None or alto is None:
            continue
        # Orden PESIMISTA, idéntico al de `process_intraday_exits`: si en la
        # misma sesión se tocan las dos barreras, se asume que saltó el stop.
        if stop is not None and bajo <= stop:
            return {"etiqueta": 0, "salida": float(stop), "razon": STOP,
                    "fecha_desenlace": b.get("fecha"), "sesiones": i + 1,
                    "retorno": float(stop) / entrada - 1.0, "motivo": None}
        if objetivo is not None and alto >= objetivo:
            return {"etiqueta": 1, "salida": float(objetivo), "razon": OBJETIVO,
                    "fecha_desenlace": b.get("fecha"), "sesiones": i + 1,
                    "retorno": float(objetivo) / entrada - 1.0, "motivo": None}

    # Barrera vertical: ni stop ni objetivo dentro del horizonte.
    if horizonte and len(barras) < horizonte:
        return {"etiqueta": None, "salida": None, "razon": None,
                "fecha_desenlace": None, "sesiones": None, "retorno": None,
                "motivo": (f"la operación sigue abierta: {len(barras)} sesión(es) "
                           f"disponibles frente a las {horizonte} del horizonte")}

    ultima = ventana[-1]
    cierre = ultima.get("close")
    if cierre is None:
        return {"etiqueta": None, "salida": None, "razon": None,
                "fecha_desenlace": None, "sesiones": None, "retorno": None,
                "motivo": "la última barra del horizonte no tiene cierre"}
    ret = float(cierre) / entrada - 1.0
    return {"etiqueta": 1 if ret > 0 else 0, "salida": float(cierre), "razon": TIEMPO,
            "fecha_desenlace": ultima.get("fecha"), "sesiones": len(ventana),
            "retorno": ret, "motivo": None}


@tool("etiquetar_por_triple_barrera")
def etiquetar_por_triple_barrera(barras: List[Dict[str, float]], entrada: float,
                                 stop: Optional[float] = None,
                                 objetivo: Optional[float] = None,
                                 horizonte: int = 63) -> Dict[str, Any]:
    """Resuelve una operación contra stop, objetivo y horizonte, y la etiqueta 1 o 0.

    Las tres barreras son las que el propio Fund Manager emitió para esa señal,
    no múltiplos genéricos: la etiqueta mide la operación que el sistema HABRÍA
    ABIERTO, que es la única pregunta que el meta-etiquetado puede responder.

    La resolución usa el mismo orden pesimista que `process_intraday_exits` del
    motor de cartera: si stop y objetivo se tocan en la misma sesión, se asume
    que saltó el stop. Si divergiera, el modelo se entrenaría con un desenlace
    distinto del que el backtest simula.

    Devuelve `etiqueta = None` —nunca 0— cuando la operación no ha terminado
    todavía. Un cero significa «acabó en pérdida»; confundirlos metería en el
    entrenamiento operaciones cuyo desenlace aún no se conoce.
    """
    return _etiquetar(barras, entrada, stop, objetivo, horizonte)


TOOLS_ETIQUETADO = [etiquetar_por_triple_barrera]
