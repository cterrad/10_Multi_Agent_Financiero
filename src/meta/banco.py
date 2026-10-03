"""
Banco de etiquetas: qué señales emitió el sistema y cómo acabó cada operación.

HERMANO DE `src/memoria/`, Y DELIBERADAMENTE
---------------------------------------------
`MemoriaReflexion` anota señales, espera a que su desenlace sea conocible,
consolida medias y sirve un dosier. Esta clase hace lo mismo con **etiquetas**
en vez de con medias, y respeta la misma regla, que es la que hace válido todo:

> Una observación entra cuando su **fecha de desenlace** es anterior al corte,
> nunca cuando lo es su fecha de emisión.

Es el par `filed`/`end` del XBRL, el `fecha_informe`/`fecha_publicacion` del COT
y el `fecha_desenlace` de la reflexión, aplicado por cuarta vez. Con un
horizonte medio de 33 sesiones, **el modelo de enero de 2019 no puede usar
señales posteriores a noviembre de 2018**, y eso hay que decirlo en voz alta
porque es una restricción severa sobre una muestra que ya es pequeña.

SOLO SE ANOTAN LAS SEÑALES DE COMPRA
-------------------------------------
El meta-etiquetado se define sobre los POSITIVOS del modelo primario: la
pregunta es «dado que el sistema dice comprar, ¿acierta?». Entrenar sobre las
5.621 señales daría más muestra, pero mediría otra cosa —sería un segundo modelo
primario, no un meta-modelo— y se aplicaría a una población distinta de aquella
sobre la que se entrenó.

La contrapartida es dura y se declara: **944 señales de compra en once años**, y
tras el corte por desenlace y el reparto walk-forward, los primeros modelos ven
del orden de 200. Es lo que descarta un GBM profundo y obliga a un lineal
regularizado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from src.tools.etiquetado import _etiquetar

# Resolver: (ticker, fecha_señal) -> lista de barras futuras
# [{"fecha": "...", "high": .., "low": .., "close": ..}, ...]
# Se inyecta desde fuera porque el acceso a precios es responsabilidad de quien
# orquesta, no del banco. Mismo criterio que el `Resolver` de `src/memoria/`.
ResolverBarras = Callable[[str, pd.Timestamp], List[Dict[str, Any]]]


@dataclass
class Etiqueta:
    """Una señal de compra con sus variables y, cuando se sepa, su desenlace."""

    fecha: str
    ticker: str
    variables: Dict[str, Optional[float]]
    entrada: float
    stop: Optional[float]
    objetivo: Optional[float]
    horizonte: int
    # Se rellenan al resolver. `None` mientras la operación sigue abierta —
    # nunca 0, que significaría «acabó en pérdida».
    etiqueta: Optional[int] = None
    retorno: Optional[float] = None
    fecha_desenlace: Optional[str] = None
    razon: Optional[str] = None

    @property
    def resuelta(self) -> bool:
        return self.etiqueta is not None and self.fecha_desenlace is not None

    def a_dict(self) -> Dict[str, Any]:
        return {
            "fecha": self.fecha, "ticker": self.ticker, "entrada": self.entrada,
            "stop": self.stop, "objetivo": self.objetivo, "horizonte": self.horizonte,
            "etiqueta": self.etiqueta, "retorno": self.retorno,
            "fecha_desenlace": self.fecha_desenlace, "razon": self.razon,
            "variables": self.variables,
        }

    @staticmethod
    def desde_dict(d: Dict[str, Any]) -> "Etiqueta":
        return Etiqueta(
            fecha=d["fecha"], ticker=d["ticker"], variables=d.get("variables", {}),
            entrada=float(d["entrada"]), stop=d.get("stop"), objetivo=d.get("objetivo"),
            horizonte=int(d.get("horizonte", 63)), etiqueta=d.get("etiqueta"),
            retorno=d.get("retorno"), fecha_desenlace=d.get("fecha_desenlace"),
            razon=d.get("razon"))


class BancoDeEtiquetas:
    """
    Almacén point-in-time de etiquetas de meta-modelo.

    El orden del bucle es la propiedad, no una convención, y es el mismo que el
    de la memoria de reflexión:

        resolver(t) → conjunto(t) → decidir(t) → anotar(t)

    Anotar antes de decidir metería la señal de hoy en el conjunto de
    entrenamiento de hoy.
    """

    def __init__(self, resolver: Optional[ResolverBarras] = None) -> None:
        self.resolver = resolver
        self.etiquetas: List[Etiqueta] = []
        self._sin_resolver: List[int] = []

    # ------------------------------------------------------------------ #
    def anotar(self, fecha: Any, ticker: str, variables: Dict[str, Optional[float]],
               entrada: float, stop: Optional[float], objetivo: Optional[float],
               horizonte: int) -> None:
        self.etiquetas.append(Etiqueta(
            fecha=str(pd.Timestamp(fecha).date()), ticker=ticker.upper(),
            variables=dict(variables), entrada=float(entrada), stop=stop,
            objetivo=objetivo, horizonte=int(horizonte)))
        self._sin_resolver.append(len(self.etiquetas) - 1)

    def anotar_senales(self, senales: List[Any]) -> int:
        """
        Anota las señales de COMPRA de un rebalanceo. Devuelve cuántas.

        Las que no son de compra se ignoran: el meta-etiquetado se define sobre
        los positivos del modelo primario.
        """
        n = 0
        for s in senales:
            if not getattr(s, "is_buy", False):
                continue
            vars_ = getattr(s, "variables_meta", None) or {}
            if not vars_:
                continue
            self.anotar(fecha=s.date, ticker=s.ticker, variables=vars_,
                        entrada=float(s.close), stop=s.stop_loss,
                        objetivo=s.take_profit,
                        horizonte=int(getattr(s, "horizonte_dias", 63) or 63))
            n += 1
        return n

    # ------------------------------------------------------------------ #
    def resolver_hasta(self, fecha) -> int:
        """
        Resuelve las operaciones cuyo desenlace ya es conocible en `fecha`.

        Devuelve cuántas se resolvieron en esta llamada. Recorre solo las
        pendientes, así que el coste es O(pendientes) y no O(todas) — el mismo
        motivo por el que `MemoriaReflexion` mantiene un cursor.
        """
        if self.resolver is None:
            return 0
        tope = pd.Timestamp(fecha)
        resueltas, siguen = 0, []
        for i in self._sin_resolver:
            e = self.etiquetas[i]
            f0 = pd.Timestamp(e.fecha)
            if f0 >= tope:
                siguen.append(i)
                continue
            try:
                barras = self.resolver(e.ticker, f0)
            except Exception:
                siguen.append(i)
                continue
            # Solo barras ANTERIORES O IGUALES al tope: resolver con precios
            # posteriores a la fecha de consulta sería mirar el futuro dentro de
            # la propia construcción del conjunto de entrenamiento.
            visibles = [b for b in barras if str(b.get("fecha", "")) <= str(tope.date())]
            r = _etiquetar(visibles, e.entrada, e.stop, e.objetivo, e.horizonte)
            if r.get("etiqueta") is None:
                siguen.append(i)
                continue
            e.etiqueta = int(r["etiqueta"])
            e.retorno = float(r["retorno"])
            e.fecha_desenlace = str(r["fecha_desenlace"])
            e.razon = r["razon"]
            resueltas += 1
        self._sin_resolver = siguen
        return resueltas

    # ------------------------------------------------------------------ #
    def conjunto(self, corte) -> List[Etiqueta]:
        """
        Etiquetas utilizables para entrenar un modelo que decidirá en `corte`.

        **El filtro es por FECHA DE DESENLACE, no por fecha de señal.** Es la
        línea más importante del módulo: cambiarla por `e.fecha < corte`
        convertiría el backtest en un examen de memoria sin que ninguna cifra lo
        delatara.
        """
        tope = str(pd.Timestamp(corte).date())
        return [e for e in self.etiquetas
                if e.resuelta and e.fecha_desenlace < tope]

    # ------------------------------------------------------------------ #
    def guardar(self, ruta) -> int:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8") as fh:
            for e in self.etiquetas:
                fh.write(json.dumps(e.a_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        return len(self.etiquetas)

    def cargar(self, ruta) -> int:
        ruta = Path(ruta)
        if not ruta.exists():
            return 0
        self.etiquetas, self._sin_resolver = [], []
        with ruta.open(encoding="utf-8") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea:
                    continue
                try:
                    e = Etiqueta.desde_dict(json.loads(linea))
                except Exception:
                    continue
                self.etiquetas.append(e)
                if not e.resuelta:
                    self._sin_resolver.append(len(self.etiquetas) - 1)
        return len(self.etiquetas)
