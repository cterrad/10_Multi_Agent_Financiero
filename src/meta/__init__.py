"""
Capa de meta-etiquetado: ¿acierta el sistema cuando dice comprar?

QUÉ ES Y DE DÓNDE VIENE
-----------------------
Meta-etiquetado de López de Prado (*Advances in Financial Machine Learning*,
cap. 3), levantado de `src/labeling/meta_labeling.py` del repositorio 03. El
modelo primario decide el **lado**; el meta-modelo decide **si tomar la apuesta
y con cuánto**.

Encaja en este sistema mejor que ningún otro candidato de los cuatro
repositorios, por tres razones concretas:

  · **No toca `rating`.** El dictamen sigue saliendo de
    `calcular_rating_compuesto` y `aplicar_vetos`, sin cambios. El meta-modelo
    solo modula `peso_objetivo`.
  · **El mecanismo ya existe.** `factor_reflexion` es un factor en
    `[mínimo, 1.0]` que el Fund Manager publica sin aplicar y que
    `PortfolioConstructor` aplica y reasigna. `factor_meta` es su gemelo.
  · **El patrón de capa con estado point-in-time ya existe.** `src/memoria/`
    anota, espera al desenlace, consolida y sirve. Esto hace lo mismo con
    etiquetas.

REPARTO DE RESPONSABILIDADES
----------------------------
    banco.py           almacén point-in-time: anota señales, resuelve desenlaces
    entrenamiento.py   walk-forward con CV purgada y pesos por unicidad
    artefacto.py       persistencia versionada y carga que FALLA RUIDOSAMENTE
    variables.py       qué mira el modelo, y por qué todo es point-in-time

La regla de decisión —probabilidad → factor— NO vive aquí: vive en
`src/tools/meta.py`, porque en este proyecto todas las reglas de cálculo viven
en `src/tools/`. Es el mismo reparto que hay entre `src/memoria/` y
`src/tools/reflexion.py`.

EL PELIGRO QUE JUSTIFICA TANTA CEREMONIA
-----------------------------------------
Un artefacto congelado es una función determinista, así que **no viola la
invariante nº 1**. Pero introduce un peligro point-in-time peor que un
look-ahead dentro de una variable, porque es invisible: un modelo entrenado con
2015-2025 y evaluado sobre 2016 es un examen de memoria, y **ningún test
existente de este repositorio lo detectaría**.

De ahí las tres barreras, cada una comprobable:

  1. El corte del conjunto de entrenamiento es la **fecha de desenlace**
     (`BancoDeEtiquetas.conjunto`), no la de emisión.
  2. El artefacto lleva dentro su ventana, y `cargar_para` **levanta excepción**
     si esa ventana alcanza la fecha de uso.
  3. Se reentrena walk-forward; no hay un artefacto único para todo el estudio.

DESACTIVADO POR DEFECTO
-----------------------
`META_HABILITADO=0`. Sin la bandera, `factor_meta` es 1.0 y la capa no decide
nada — el mismo trato que la memoria de reflexión, y por el mismo motivo: una
capa que modula el tamaño no se enciende hasta que su contraste lo justifique.
"""

from src.meta.artefacto import (
    ArtefactoAnacronico,
    ArtefactoIlegible,
    MetaArtefacto,
    cargar_para,
    guardar,
)
from src.meta.banco import BancoDeEtiquetas, Etiqueta
from src.meta.entrenamiento import entrenar, evaluar_cv
from src.meta.variables import VARIABLES_META, variables_de_senal

__all__ = [
    "ArtefactoAnacronico", "ArtefactoIlegible", "MetaArtefacto",
    "BancoDeEtiquetas", "Etiqueta",
    "cargar_para", "guardar", "entrenar", "evaluar_cv",
    "VARIABLES_META", "variables_de_senal",
]
