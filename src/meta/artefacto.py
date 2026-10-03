"""
Artefacto del meta-modelo: persistencia versionada y carga que FALLA RUIDOSAMENTE.

EL PELIGRO QUE ESTE MÓDULO EXISTE PARA IMPEDIR
-----------------------------------------------
Un artefacto de modelo congelado ES una función determinista, así que no viola
la invariante nº 1 del proyecto: ejecutar dos veces produce el mismo número y el
LLM sigue sin tocar ninguna rama.

Pero introduce un peligro point-in-time **estrictamente peor que un look-ahead
dentro de una variable, porque es invisible**:

> Un modelo entrenado con 2015-2025 y evaluado sobre 2016 no es un backtest, es
> un examen de memoria.

**Ningún test de este repositorio lo detectaría.** `test_no_lookahead_*` mira
precios; `test_fundamentals_respect_filed_not_end` mira `filed`;
`test_serie_semanal_filtra_por_publicacion` mira la fecha de publicación del
COT. Ninguno mira de qué años salieron los coeficientes de un modelo.

De ahí las dos propiedades de este módulo, y ninguna es opcional:

1. **El artefacto lleva DENTRO su ventana de entrenamiento** (`entrenado_hasta`),
   no en el nombre del fichero ni en una convención.
2. **`cargar_para()` levanta `ArtefactoAnacronico` si esa ventana alcanza o
   supera la fecha en la que se pretende usar.** No degrada, no avisa, no
   devuelve `None`: rompe. Un modelo que ha visto el futuro produciría un
   backtest excelente y sin valor, y fallar ruidosamente es la única forma de
   que eso no ocurra en silencio.

POR QUÉ JSON Y NO PICKLE
-------------------------
El artefacto es un JSON legible con los coeficientes, no un `pickle`. Tres
motivos, en orden de importancia:

  · Un `pickle` es código ejecutable: cargarlo es ejecutar lo que contenga.
  · Se puede leer, revisar y meter en un diff. Un modelo cuya única auditoría es
    «confía en el fichero binario» no encaja en un proyecto cuyo informe explica
    de dónde sale cada cifra.
  · Sobrevive a un cambio de versión de scikit-learn. Un `pickle` no.

La contrapartida es que solo se serializan modelos **lineales** —coeficientes,
intercepto y escalado—, y eso es una restricción deliberada: con las 944 señales
de compra del estudio, un modelo con más parámetros que eso memoriza.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

VERSION_FORMATO = 1


class ArtefactoAnacronico(RuntimeError):
    """
    El artefacto vio datos posteriores a la fecha en que se pretende usarlo.

    Se levanta en lugar de degradar porque el fallo es SILENCIOSO por
    naturaleza: un modelo entrenado sobre el futuro produce un backtest
    excelente y sin ningún valor, y nada en las cifras lo delataría.
    """


class ArtefactoIlegible(RuntimeError):
    """El fichero no existe, no es JSON válido o le falta un campo obligatorio."""


@dataclass
class MetaArtefacto:
    """
    Modelo lineal serializable, con su procedencia dentro.

    `entrenado_hasta` es la fecha de DESENLACE más tardía que entró en el
    entrenamiento, no la de emisión de la última señal. Es la distinción que
    hace válido todo lo demás: una señal de junio resuelta en julio aporta
    información de julio, y el artefacto tiene que declararlo así.
    """

    variables: List[str]
    coeficientes: List[float]
    intercepto: float
    media: List[float]
    escala: List[float]
    entrenado_hasta: str          # fecha de desenlace más tardía usada
    entrenado_desde: str
    n_muestras: int
    tasa_base: float              # proporción de etiquetas positivas
    modelo: str = "logistica_l2"
    version_formato: int = VERSION_FORMATO
    metricas_cv: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    def probabilidad(self, x: Dict[str, Optional[float]]) -> Optional[float]:
        """
        P(la operación acaba en beneficio), o `None` si faltan variables.

        Devuelve `None` y no una probabilidad por defecto cuando una variable
        obligatoria está ausente. Sustituirla por la media del entrenamiento
        sería inventar un dato, que es el defecto que `src/data/magnitudes.py`
        corrige en todo el resto del sistema; aquí además tendría el agravante
        de que el número resultante parecería una predicción.
        """
        vals = []
        for nombre in self.variables:
            v = x.get(nombre)
            if v is None or not np.isfinite(float(v)):
                return None
            vals.append(float(v))
        z = (np.asarray(vals) - np.asarray(self.media)) / np.asarray(self.escala)
        logit = float(np.dot(z, np.asarray(self.coeficientes)) + self.intercepto)
        # `expit` acotado: con |logit| grande, `exp` desborda y devolvería nan.
        logit = max(-30.0, min(30.0, logit))
        return float(1.0 / (1.0 + np.exp(-logit)))

    def a_dict(self) -> Dict[str, Any]:
        d = {
            "version_formato": self.version_formato,
            "modelo": self.modelo,
            "entrenado_desde": self.entrenado_desde,
            "entrenado_hasta": self.entrenado_hasta,
            "n_muestras": self.n_muestras,
            "tasa_base": round(self.tasa_base, 6),
            "variables": list(self.variables),
            "coeficientes": [round(float(c), 8) for c in self.coeficientes],
            "intercepto": round(float(self.intercepto), 8),
            "media": [round(float(m), 8) for m in self.media],
            "escala": [round(float(s), 8) for s in self.escala],
            "metricas_cv": self.metricas_cv,
        }
        # La huella va la última y se calcula sobre todo lo anterior: permite
        # detectar que dos ejecuciones produjeron modelos distintos sin comparar
        # coeficiente a coeficiente.
        d["huella"] = hashlib.sha256(
            json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        return d

    @staticmethod
    def desde_dict(d: Dict[str, Any]) -> "MetaArtefacto":
        obligatorios = ("variables", "coeficientes", "intercepto", "media", "escala",
                        "entrenado_hasta", "entrenado_desde", "n_muestras", "tasa_base")
        faltan = [k for k in obligatorios if k not in d]
        if faltan:
            raise ArtefactoIlegible(f"al artefacto le faltan campos: {faltan}")
        return MetaArtefacto(
            variables=list(d["variables"]), coeficientes=list(d["coeficientes"]),
            intercepto=float(d["intercepto"]), media=list(d["media"]),
            escala=list(d["escala"]), entrenado_hasta=str(d["entrenado_hasta"]),
            entrenado_desde=str(d["entrenado_desde"]), n_muestras=int(d["n_muestras"]),
            tasa_base=float(d["tasa_base"]), modelo=d.get("modelo", "logistica_l2"),
            version_formato=int(d.get("version_formato", VERSION_FORMATO)),
            metricas_cv=d.get("metricas_cv", {}))


# --------------------------------------------------------------------------- #
def guardar(artefacto: MetaArtefacto, ruta: Path) -> Path:
    """Persiste el artefacto como JSON legible. No sobrescribe en silencio."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(artefacto.a_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return ruta


def cargar_para(ruta: Path, fecha_uso: str) -> MetaArtefacto:
    """
    Carga el artefacto y **verifica que no vio el futuro de `fecha_uso`**.

    Levanta `ArtefactoAnacronico` si `entrenado_hasta >= fecha_uso`. La
    comparación es `>=` y no `>` a propósito: un artefacto entrenado con
    etiquetas resueltas *el mismo día* en que se pretende decidir ya conoce el
    desenlace de operaciones que en ese momento seguían abiertas.

    Levanta `ArtefactoIlegible` si el fichero no existe o está incompleto. **No
    devuelve `None`.** Quien quiera degradar limpiamente ante la ausencia de
    modelo debe capturar la excepción explícitamente — así la degradación es una
    decisión escrita y no un efecto secundario de un `if` olvidado.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise ArtefactoIlegible(f"no existe el artefacto {ruta}")
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ArtefactoIlegible(f"{ruta} no es JSON válido: {exc}") from None

    art = MetaArtefacto.desde_dict(d)
    if art.entrenado_hasta >= str(fecha_uso):
        raise ArtefactoAnacronico(
            f"el artefacto {ruta.name} se entrenó con etiquetas resueltas hasta "
            f"{art.entrenado_hasta} y se pretende usar el {fecha_uso}: habría visto "
            f"el desenlace de operaciones aún abiertas en esa fecha. Un modelo así "
            f"produce un backtest excelente y sin ningún valor.")
    return art
