"""
Tool de reflexión: convierte el dosier de memoria en un factor de tamaño y una
señal de veto.

QUÉ PRODUCE Y POR QUÉ ESTÁ AQUÍ Y NO EN `src/memoria/`
------------------------------------------------------
`src/memoria/` almacena y respeta el point-in-time; este módulo hace el cálculo
puro que traduce ese almacén en dos números de decisión:

  · `factor_reflexion` ∈ [REFLEXION_FACTOR_MINIMO, 1.0] — multiplica el peso.
  · `desfavorable` — booleano que habilita un veto que SOLO BAJA el rating.

Ambos son variables de decisión, así que esta tool queda FUERA de
`TOOLS_LECTURA`: el agente investigador no puede alcanzarla, igual que no
alcanza `aplicar_vetos` ni `ajustar_precio_entrada`.

LAS TRES REGLAS QUE NO CONVIENE DESHACER
----------------------------------------
1. **El factor solo recorta.** 1.0 es a la vez el valor neutro y el máximo. Una
   celda con expectativa histórica excelente NO amplía el peso, porque premiar
   con tamaño lo que ya funcionó es la definición operativa de perseguir el
   rendimiento pasado. La reasignación del presupuesto liberado la hace
   `PortfolioConstructor`, que sí ve la cartera entera; esta tool ve un valor.

2. **Sin muestra no hay ajuste, y se dice.** Por debajo de
   `REFLEXION_MUESTRA_MINIMA` el factor es 1.0 con `evaluable=False` y un
   motivo. Un sistema recién instalado no penaliza a nadie durante su primer
   año, exactamente igual que los percentiles de opciones no se inventan un
   percentil 50 mientras acumulan histórico.

3. **Manda la peor dimensión, no el producto.** Estilo y momentum están
   correlacionados; multiplicar sus factores castigaría dos veces el mismo
   defecto y llevaría el peso al suelo por una única evidencia contada dos
   veces. `min()` es conservador sin ser acumulativo.

EL DÉFICIT SE MIDE CONTRA CERO, NO CONTRA LA MEDIA
--------------------------------------------------
La expectativa es una rentabilidad EN EXCESO sobre el índice, así que el punto
neutro natural es el cero: «esta configuración no batió al mercado». Medirlo
contra la media global obligaría a penalizar siempre a alguien —siempre hay una
mitad por debajo de la media— incluso en un sistema en el que todas las celdas
funcionan. La contracción sí es hacia la media global, que es lo correcto: sin
datos, la mejor estimación de una celda es el comportamiento del conjunto.
"""

from typing import Any, Dict, Optional

from langchain_core.tools import tool

from src.config import (
    REFLEXION_CONTRACCION_K,
    REFLEXION_DIMENSIONES,
    REFLEXION_ESCALA_DEFICIT,
    REFLEXION_FACTOR_MINIMO,
    REFLEXION_MUESTRA_MINIMA,
)

NEUTRO = 1.0


def _neutro(motivo: str) -> Dict[str, Any]:
    return {
        "factor": NEUTRO,
        "desfavorable": False,
        "evaluable": False,
        "motivo": motivo,
        "detalle": {},
    }


def _consultar(dosier: Optional[Dict[str, Any]], estilo: Optional[str],
               momentum: Optional[str]) -> Dict[str, Any]:
    if not dosier or not dosier.get("tabla"):
        return _neutro("Sin memoria de reflexión disponible: no se aplica ajuste.")
    if not dosier.get("evaluable"):
        return _neutro(dosier.get("motivo")
                       or "Memoria de reflexión sin muestra suficiente: no se aplica ajuste.")

    claves = {"estilo": estilo or "n/d", "momentum": momentum or "n/d"}
    media_global = float(dosier.get("media_global", 0.0) or 0.0)
    k = float(dosier.get("contraccion_k", REFLEXION_CONTRACCION_K) or REFLEXION_CONTRACCION_K)
    minima = int(dosier.get("muestra_minima", REFLEXION_MUESTRA_MINIMA) or REFLEXION_MUESTRA_MINIMA)

    detalle: Dict[str, Any] = {}
    factores = []
    desfavorable = False

    for dim in REFLEXION_DIMENSIONES:
        clave = claves.get(dim, "n/d")
        celda = (dosier["tabla"].get(dim) or {}).get(clave)
        if not celda or int(celda.get("n", 0)) < minima:
            detalle[dim] = {
                "clave": clave,
                "n": int((celda or {}).get("n", 0)),
                "evaluable": False,
                "factor": NEUTRO,
            }
            continue

        n = float(celda["n"])
        peso_celda = n / (n + k)
        # Contracción empírica de Bayes hacia la media global. Con n = k la
        # celda pesa la mitad: veinte observaciones afortunadas no dictan el
        # tamaño de una posición.
        esperado = peso_celda * float(celda["media"]) + (1.0 - peso_celda) * media_global
        error = peso_celda * float(celda.get("error_tipico", 0.0) or 0.0)

        deficit = max(0.0, -esperado)
        factor = max(REFLEXION_FACTOR_MINIMO, 1.0 - deficit / REFLEXION_ESCALA_DEFICIT)
        # Desfavorable exige que el intervalo de un error típico quede ENTERO por
        # debajo de cero. Sin esa condición, cualquier celda con media -0.01%
        # dispararía un veto sobre puro ruido.
        negativa = (esperado + error) <= 0.0

        detalle[dim] = {
            "clave": clave,
            "n": int(n),
            "media_cruda": round(float(celda["media"]), 5),
            "esperado_contraido": round(esperado, 5),
            "error_tipico": round(error, 5),
            "factor": round(factor, 3),
            "desfavorable": negativa,
            "evaluable": True,
        }
        factores.append(factor)
        desfavorable = desfavorable or negativa

    if not factores:
        return _neutro(
            f"Ninguna dimensión alcanza las {minima} observaciones exigidas "
            f"(estilo={claves['estilo']}, momentum={claves['momentum']}): no se aplica ajuste.")

    # La PEOR evidencia manda. Ver el encabezado: multiplicar castigaría dos
    # veces el mismo defecto.
    factor = min(factores)
    peor = min((d for d in detalle.values() if d.get("evaluable")),
               key=lambda d: d["factor"])
    motivo = (
        f"Las señales con {peor['clave']} rindieron {peor['esperado_contraido']:+.2%} "
        f"frente al índice a {dosier.get('horizonte_sesiones')} sesiones "
        f"({peor['n']} observaciones desenlazadas antes de {dosier.get('as_of')})"
    )
    if factor < NEUTRO:
        motivo += f": peso recortado a ×{factor:.2f}"
    else:
        motivo += ": sin evidencia en contra, peso íntegro"

    return {
        "factor": round(factor, 3),
        "desfavorable": desfavorable,
        "evaluable": True,
        "motivo": motivo,
        "detalle": detalle,
    }


# =========================================================================== #
# Fachadas @tool
# =========================================================================== #


@tool("consultar_reflexion")
def consultar_reflexion(dosier: Optional[Dict[str, Any]], estilo: Optional[str],
                        momentum: Optional[str]) -> Dict[str, Any]:
    """Calibra el tamaño de una posición con el desenlace de las señales pasadas.

    Recibe el dosier point-in-time de `src/memoria/reflexion.py` —la tabla de
    rentabilidad en exceso sobre el índice que siguió a cada configuración de
    señal, contando solo las observaciones ya desenlazadas— y devuelve el factor
    multiplicador del peso y si la evidencia es lo bastante negativa para
    habilitar un veto.

    El factor está acotado en [0.40, 1.00] y NUNCA supera 1.0: esta capa recorta
    lo que históricamente no funcionó, no amplía lo que sí. Sin muestra
    suficiente devuelve 1.0 con `evaluable=False` y el motivo, en lugar de una
    expectativa inventada.

    Devuelve `factor`, `desfavorable`, `evaluable`, `motivo` y el desglose por
    dimensión (estilo y momentum) con la muestra de cada celda.
    """
    return _consultar(dosier, estilo, momentum)


TOOLS_REFLEXION = [consultar_reflexion]

__all__ = ["consultar_reflexion", "TOOLS_REFLEXION", "_consultar", "NEUTRO"]
