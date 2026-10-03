"""
Capa de ingesta de FRED/ALFRED: dosier de régimen de volatilidad.

Hermana de `src/data/futuros/` y con el mismo reparto de responsabilidades: aquí
se recolecta y se normaliza; quien decide es `src/agents/regimen.py`. Este
paquete **no** es una excepción al «un solo módulo toca la red»: su tool de red
es `obtener_contexto_regimen`, que vive en `src/tools/extraccion.py` como todas
las demás, exactamente igual que `obtener_noticias` delega en `src/data/news/`.

EL DOSIER NO ES POR TICKER
---------------------------
El nivel del VIX del 3 de marzo es el mismo para las cincuenta empresas del
lote. Por eso `recolectar_regimen()` se resuelve **una vez por ejecución** desde
quien orquesta el bucle —`cli.py`, `src/web/app.py`, `backtest_cli.py`— y viaja
en el estado inicial como `regimen_data`, igual que `benchmark_data` y
`futures_data`. Descargarlo dentro del grafo sería pedir la misma serie de FRED
una vez por valor analizado.
"""

from typing import Any, Dict, List, Optional

from src.config import (
    REGIMEN_DIAS_HISTORICO,
    SERIE_VOLATILIDAD,
    SERIE_VOLATILIDAD_3M,
)
from src.data.fred.serie import FredNoConfigurado, serie_diaria

__all__ = ["recolectar_regimen", "series_requeridas", "serie_diaria",
           "FredNoConfigurado"]


def series_requeridas() -> List[str]:
    """
    Conjunto cerrado de series del dosier.

    Es cerrado a propósito, igual que `SECTOR_A_FUTURO`: cada serie añadida es
    una responsabilidad permanente de mantenimiento y de reproducibilidad, y una
    serie sin uso en la decisión no debe descargarse «por si acaso».
    """
    return [SERIE_VOLATILIDAD, SERIE_VOLATILIDAD_3M]


def recolectar_regimen(as_of: Optional[str] = None, offline: bool = False,
                       dias: int = REGIMEN_DIAS_HISTORICO,
                       directorio: Optional[Any] = None) -> Dict[str, Any]:
    """
    Dosier de régimen conocible en `as_of`.

    `as_of` filtra por **fecha de publicación** en `serie_diaria`, que es la
    única selección point-in-time del módulo. Producción lo omite.

    Un fallo de una serie no tumba el dosier: se declara en `fallos` y el agente
    degrada. Que falten las dos sí deja el dosier inservible, y el agente lo
    dirá con `NO_APLICABLE` en lugar de inventar un régimen de calma.
    """
    series: Dict[str, Any] = {}
    fallos: List[str] = []
    for nombre in series_requeridas():
        try:
            datos = serie_diaria(nombre, as_of=as_of, dias=dias,
                                 offline=offline, directorio=directorio)
        except FredNoConfigurado as exc:
            fallos.append(f"{nombre}: {exc}")
            continue
        except Exception as exc:  # pragma: no cover - red
            fallos.append(f"{nombre}: {type(exc).__name__}: {exc}")
            continue
        series[nombre] = datos
        fallos.extend(datos.get("fallos", []))

    disponible = any(s.get("n_observaciones", 0) > 0 for s in series.values())
    return {
        "disponible": disponible,
        "as_of": as_of,
        "series": series,
        "fallos": fallos,
        "serie_volatilidad": SERIE_VOLATILIDAD,
        "serie_volatilidad_3m": SERIE_VOLATILIDAD_3M,
    }
