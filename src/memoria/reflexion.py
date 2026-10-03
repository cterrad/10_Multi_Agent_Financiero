"""
Memoria de reflexión: qué hizo el precio DESPUÉS de cada señal que el sistema
emitió, y qué se deduce de ello para las señales de hoy.

QUÉ ES Y DE DÓNDE VIENE
-----------------------
Es la traducción determinista de la «low-level reflection» de FinAgent (Zhang et
al., 2024, arXiv:2402.18485), el componente al que su propia ablación atribuye
el mayor salto de rendimiento —de solo-M a M+L, +68% de ARR en AAPL y +101% en
ETH— y el mismo mecanismo que FinVision (Fatemi & Hu, 2024, arXiv:2411.08899)
identifica como el que más aporta en su único estudio de ablación.

En los dos papers ese vínculo lo redacta un LLM mirando un gráfico. Aquí es una
media condicionada sobre observaciones ya desenlazadas. La forma es la misma
—«qué precedió a qué»—; la sustancia es una función pura, así que la invariante
del proyecto se mantiene: ninguna variable de decisión depende del modelo.

POR QUÉ EL BAJO NIVEL Y NO EL ALTO
----------------------------------
La reflexión de ALTO nivel de FinAgent mira las decisiones ejecutadas; la de
BAJO nivel mira todo lo observado. Aquí la diferencia es de un orden de
magnitud: cada rebalanceo evalúa ~50 valores y compra 4 o 5. Medir sobre las
563 operaciones cerradas daría celdas de veinte observaciones; medir sobre las
~6.600 señales emitidas da celdas con las que se puede decir algo. Es
exactamente el motivo por el que la ablación de FinAgent premia a L sobre H.

LA MEDIDA ES TRANSVERSAL, Y ESO NO ES UN DETALLE
------------------------------------------------
El desenlace se mide en dos pasos: retorno del valor menos retorno del índice, y
después **menos la media de las demás señales del mismo rebalanceo**.

La primera versión se quedaba en el paso uno, y sobre el histórico real la capa
recortó 62 de 5.621 señales con un factor medio de x0.99: no hizo nada. El
motivo, que el propio diagnóstico del informe deja ver, es que este universo de
grandes capitalizaciones bate al SPY, así que el exceso medio de TODAS las
señales era +0.46% a 21 sesiones y casi ninguna celda llegaba a caer por debajo
de cero.

Contra el índice, la memoria mide «universo menos índice», que es EXPOSICIÓN.
Contra la propia cohorte mide «este perfil menos los demás perfiles que el
sistema tenía delante ese día», que es SELECCIÓN — la única pregunta que esta
capa puede responder y la que el percentil frente a selección aleatoria juzga.

Restar la media de la cohorte no introduce look-ahead: una cohorte madura
entera y a la vez, porque el desplazamiento del calendario es constante, de modo
que cuando la primera observación es utilizable las demás también lo son.

DISCIPLINA POINT-IN-TIME
------------------------
Una observación entra en el dosier cuando su **fecha de desenlace** es anterior o
igual a `as_of`, nunca cuando lo es su fecha de emisión. Es el mismo par
`filed`/`end` de los hechos XBRL y el mismo `fecha_publicacion` del COT: la
señal del 1 de junio con horizonte de 21 sesiones no se sabe cómo terminó hasta
julio, y usarla en junio sería mirar el futuro. `test_la_memoria_respeta_la_fecha_de_desenlace`
fija esa propiedad y es el test más importante de este módulo — si se relaja, el
backtest deja de medir nada.

CONSOLIDACIÓN INCREMENTAL
-------------------------
Las consultas del backtest avanzan en el tiempo, así que los agregados se
mantienen con un cursor: O(1) por consulta en vez de recorrer 6.600
observaciones en cada una de las 6.600 llamadas. Si alguna vez se pregunta por
una fecha ANTERIOR a la última consolidada, se reconstruye desde cero en lugar
de devolver un agregado contaminado con el futuro.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from src.config import (
    REFLEXION_COHORTE_MINIMA,
    REFLEXION_CONTRACCION_K,
    REFLEXION_DIMENSIONES,
    REFLEXION_HORIZONTE_SESIONES,
    REFLEXION_MUESTRA_MINIMA,
)

# Resolver: (ticker, fecha_señal, fecha_desenlace) -> retorno en exceso, o None
# si no hay precios suficientes. Se inyecta desde fuera porque el acceso a
# precios es responsabilidad de la capa que orquesta, no de la memoria.
Resolver = Callable[[str, pd.Timestamp, pd.Timestamp], Optional[float]]


@dataclass
class Observacion:
    """Una señal emitida y, cuando madura, lo que el precio hizo después."""

    fecha_senal: pd.Timestamp
    fecha_desenlace: pd.Timestamp
    ticker: str
    estilo: str
    momentum: str
    # Retorno del valor menos el del índice. None mientras no ha madurado.
    retorno_exceso: Optional[float] = None
    # El anterior menos la media de su cohorte. Es lo que agrega la memoria; se
    # guarda APARTE en vez de sobrescribir `retorno_exceso` para que consolidar
    # dos veces no reste la media dos veces. Se recalcula en cada
    # reconstrucción, así que la persistencia solo necesita el dato crudo.
    retorno_relativo: Optional[float] = None

    def a_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("retorno_relativo", None)   # derivado: se recalcula al consolidar
        d["fecha_senal"] = str(pd.Timestamp(self.fecha_senal).date())
        d["fecha_desenlace"] = str(pd.Timestamp(self.fecha_desenlace).date())
        return d

    @staticmethod
    def desde_dict(d: Dict[str, Any]) -> "Observacion":
        return Observacion(
            fecha_senal=pd.Timestamp(d["fecha_senal"]),
            fecha_desenlace=pd.Timestamp(d["fecha_desenlace"]),
            ticker=d["ticker"],
            estilo=d.get("estilo") or "n/d",
            momentum=d.get("momentum") or "n/d",
            retorno_exceso=d.get("retorno_exceso"),
        )


class _Agregado:
    """Acumulador de media y desviación típica sin guardar la muestra."""

    __slots__ = ("n", "suma", "suma2")

    def __init__(self) -> None:
        self.n = 0
        self.suma = 0.0
        self.suma2 = 0.0

    def anadir(self, x: float) -> None:
        self.n += 1
        self.suma += x
        self.suma2 += x * x

    @property
    def media(self) -> float:
        return self.suma / self.n if self.n else 0.0

    @property
    def desviacion(self) -> float:
        if self.n < 2:
            return 0.0
        var = (self.suma2 - self.suma * self.suma / self.n) / (self.n - 1)
        return math.sqrt(max(0.0, var))

    @property
    def error_tipico(self) -> float:
        return self.desviacion / math.sqrt(self.n) if self.n else 0.0


class MemoriaReflexion:
    """
    Almacén point-in-time de señales y sus desenlaces.

    Uso desde el motor histórico (el orden importa y es el único correcto):

        memoria.consolidar_hasta(fecha)          # incorpora lo ya desenlazado
        dosier = memoria.dosier(fecha)           # foto del conocimiento en `fecha`
        senales = replayer.signals_for_date(...)  # decide CON ese dosier
        memoria.anotar_senales(senales, calendario)   # registra para el futuro

    Anotar DESPUÉS de decidir no es cosmético: anotar antes metería la señal de
    hoy en el dosier de hoy, que es la forma más silenciosa de look-ahead.
    """

    def __init__(self, resolver: Optional[Resolver] = None,
                 horizonte: int = REFLEXION_HORIZONTE_SESIONES) -> None:
        self.resolver = resolver
        self.horizonte = horizonte
        self.observaciones: List[Observacion] = []
        self._orden: List[Observacion] = []          # ordenadas por desenlace
        self._cursor = 0
        self._ultima_consolidacion: Optional[pd.Timestamp] = None
        self._celdas: Dict[str, Dict[str, _Agregado]] = {d: {} for d in REFLEXION_DIMENSIONES}
        self._global = _Agregado()

    # ------------------------------------------------------------------ #
    # Alta de observaciones
    # ------------------------------------------------------------------ #
    def anotar(self, fecha_senal, ticker: str, estilo: Optional[str],
               momentum: Optional[str], fecha_desenlace) -> None:
        self.observaciones.append(Observacion(
            fecha_senal=pd.Timestamp(fecha_senal),
            fecha_desenlace=pd.Timestamp(fecha_desenlace),
            ticker=ticker.upper(),
            estilo=estilo or "n/d",
            momentum=momentum or "n/d",
        ))
        self._orden = []          # invalida el índice; se reconstruye al consolidar

    def anotar_senales(self, senales: List[Any], calendario: pd.DatetimeIndex) -> int:
        """
        Registra las señales de un rebalanceo con su fecha de desenlace.

        La fecha de desenlace se toma del CALENDARIO real, no sumando días
        naturales: 21 sesiones y 21 días no son lo mismo, y usar días naturales
        desplazaría el desenlace a un festivo en el que no hay precio.

        Las señales cuyo horizonte cae más allá del final del calendario no se
        anotan: nunca podrán desenlazarse y solo ensuciarían el almacén.
        """
        if not len(senales) or calendario is None or not len(calendario):
            return 0
        cal = pd.DatetimeIndex(calendario)
        anotadas = 0
        for s in senales:
            fecha = pd.Timestamp(getattr(s, "date", None) or getattr(s, "fecha", None))
            pos = cal.searchsorted(fecha)
            destino = pos + self.horizonte
            if destino >= len(cal):
                continue
            self.anotar(fecha, s.ticker, getattr(s, "estilo", None),
                        getattr(s, "momentum", None), cal[destino])
            anotadas += 1
        return anotadas

    # ------------------------------------------------------------------ #
    # Consolidación
    # ------------------------------------------------------------------ #
    def _reindexar(self) -> None:
        self._orden = sorted(self.observaciones, key=lambda o: o.fecha_desenlace)
        self._cursor = 0
        self._ultima_consolidacion = None
        self._celdas = {d: {} for d in REFLEXION_DIMENSIONES}
        self._global = _Agregado()
        for obs in self._orden:
            obs.retorno_relativo = None   # derivado: se recalcula por cohorte

    def _incorporar(self, obs: Observacion) -> None:
        if obs.retorno_relativo is None:
            return
        valor = float(obs.retorno_relativo)
        self._global.anadir(valor)
        for dim in REFLEXION_DIMENSIONES:
            clave = getattr(obs, dim, None) or "n/d"
            self._celdas[dim].setdefault(clave, _Agregado()).anadir(valor)

    def consolidar_hasta(self, fecha) -> int:
        """
        Incorpora a los agregados todas las observaciones ya desenlazadas.

        Se procesa POR COHORTES —todas las observaciones que vencen el mismo
        día— porque la medida es transversal: a cada una se le resta la media de
        las demás señales de su propio rebalanceo. Ver el encabezado del módulo:
        contra el índice esta capa mide exposición, contra la cohorte mide
        selección.

        Resolver el retorno es perezoso: solo se pide el precio cuando la
        observación vence, de modo que el almacén no arrastra llamadas.

        Devuelve cuántas observaciones se incorporaron en esta llamada.
        """
        fecha = pd.Timestamp(fecha)
        if not self._orden or (self._ultima_consolidacion is not None
                               and fecha < self._ultima_consolidacion):
            # Hacia atrás en el tiempo no se puede avanzar el cursor: los
            # agregados ya contendrían observaciones posteriores a `fecha`.
            self._reindexar()

        incorporadas = 0
        while self._cursor < len(self._orden):
            if self._orden[self._cursor].fecha_desenlace > fecha:
                break

            # Cohorte completa: mismo vencimiento, así que madura entera y a la
            # vez. Es lo que permite restarle su media sin mirar el futuro.
            fin = self._cursor
            vence = self._orden[self._cursor].fecha_desenlace
            while fin < len(self._orden) and self._orden[fin].fecha_desenlace == vence:
                fin += 1
            cohorte = self._orden[self._cursor:fin]

            for obs in cohorte:
                if obs.retorno_exceso is None and self.resolver is not None:
                    try:
                        obs.retorno_exceso = self.resolver(
                            obs.ticker, obs.fecha_senal, obs.fecha_desenlace)
                    except Exception:
                        obs.retorno_exceso = None

            resueltas = [o for o in cohorte if o.retorno_exceso is not None]
            # Con menos de `REFLEXION_COHORTE_MINIMA` la media no describe «lo
            # que el sistema veía ese día», solo repite el ruido de esas pocas.
            media = (sum(o.retorno_exceso for o in resueltas) / len(resueltas)
                     if len(resueltas) >= REFLEXION_COHORTE_MINIMA else 0.0)
            for obs in resueltas:
                obs.retorno_relativo = obs.retorno_exceso - media
                self._incorporar(obs)
                incorporadas += 1

            self._cursor = fin

        self._ultima_consolidacion = fecha
        return incorporadas

    # ------------------------------------------------------------------ #
    # Consulta
    # ------------------------------------------------------------------ #
    def dosier(self, as_of) -> Dict[str, Any]:
        """
        Foto del conocimiento disponible en `as_of`, lista para viajar en el
        estado.

        Es un dict serializable y NO por ticker: la tabla completa cabe en unas
        pocas decenas de entradas y cada agente busca su propia celda. Mismo
        patrón que `futures_data` y `benchmark_data`, y por el mismo motivo:
        resolverlo una vez por ejecución en lugar de una vez por valor.
        """
        as_of = pd.Timestamp(as_of)
        self.consolidar_hasta(as_of)

        tabla: Dict[str, Dict[str, Any]] = {}
        for dim in REFLEXION_DIMENSIONES:
            tabla[dim] = {
                clave: {
                    "n": agg.n,
                    "media": round(agg.media, 6),
                    "error_tipico": round(agg.error_tipico, 6),
                }
                for clave, agg in self._celdas[dim].items()
                if agg.n > 0
            }

        return {
            "as_of": str(as_of.date()),
            "horizonte_sesiones": self.horizonte,
            "n_total": self._global.n,
            "media_global": round(self._global.media, 6),
            "muestra_minima": REFLEXION_MUESTRA_MINIMA,
            "contraccion_k": REFLEXION_CONTRACCION_K,
            "tabla": tabla,
            "evaluable": self._global.n >= REFLEXION_MUESTRA_MINIMA,
            # Sin historia suficiente la capa se declara inaplicable en lugar de
            # emitir un factor neutro indistinguible de «no hay nada que
            # penalizar». Es la misma distinción que separa un ajuste de entrada
            # de 0.0 de uno ausente.
            "motivo": (None if self._global.n >= REFLEXION_MUESTRA_MINIMA else
                       f"solo {self._global.n} observación(es) desenlazada(s) a {as_of.date()}; "
                       f"se requieren {REFLEXION_MUESTRA_MINIMA}"),
        }

    # ------------------------------------------------------------------ #
    # Persistencia
    # ------------------------------------------------------------------ #
    def guardar(self, ruta) -> int:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8") as fh:
            for obs in self.observaciones:
                fh.write(json.dumps(obs.a_dict(), ensure_ascii=False) + "\n")
        return len(self.observaciones)

    def cargar(self, ruta) -> int:
        """Lee el almacén persistido. Una línea corrupta se salta, no aborta."""
        ruta = Path(ruta)
        if not ruta.exists():
            return 0
        leidas = 0
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea:
                continue
            try:
                self.observaciones.append(Observacion.desde_dict(json.loads(linea)))
                leidas += 1
            except Exception:
                continue
        self._orden = []
        return leidas


# --------------------------------------------------------------------------- #
def resolver_desde_precios(price_data: Dict[str, pd.DataFrame],
                           benchmark: str = "SPY") -> Resolver:
    """
    Resolver de retorno EN EXCESO sobre el índice a partir de OHLCV cacheado.

    Lee el cierre de la fecha de la señal y el de la fecha de desenlace, y resta
    lo que hizo el índice en la misma ventana. Devuelve None —nunca cero— si
    falta cualquiera de los cuatro precios: una observación sin desenlace medible
    no es una observación de rentabilidad nula.
    """
    bench = price_data.get(benchmark.upper())

    def _cierre(df: Optional[pd.DataFrame], fecha: pd.Timestamp) -> Optional[float]:
        if df is None:
            return None
        serie = df.loc[df.index <= fecha, "Close"]
        return float(serie.iloc[-1]) if len(serie) else None

    def _resolver(ticker: str, f0: pd.Timestamp, f1: pd.Timestamp) -> Optional[float]:
        df = price_data.get(ticker.upper())
        p0, p1 = _cierre(df, f0), _cierre(df, f1)
        if not p0 or not p1:
            return None
        ret = p1 / p0 - 1.0
        b0, b1 = _cierre(bench, f0), _cierre(bench, f1)
        if b0 and b1:
            ret -= (b1 / b0 - 1.0)
        return ret

    return _resolver


__all__ = ["MemoriaReflexion", "Observacion", "resolver_desde_precios", "Resolver"]
