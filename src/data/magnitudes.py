"""
Tipos y utilidades para magnitudes financieras con procedencia.

MOTIVO DE EXISTIR
-----------------
Antes de este módulo el sistema colapsaba «no hay dato» y «el dato vale cero»
en el mismo `0.0`:

    revenue_growth = info.get("revenueGrowth", 0.0)      # fetcher.py
    revenue_growth = metrics.get("revenue_growth", 0.0)  # fundamental.py

Consecuencia observada en producción (informe del 2026-08-21): una empresa sin
cobertura de datos y una empresa realmente sin ingresos producían el MISMO
veredicto y los MISMOS motivos — «Margen Neto (0.0%) por debajo del umbral
mínimo». El gatekeeper afirmaba un hecho contable cuando en realidad estaba
describiendo un vacío de información.

La ausencia de dato es una condición distinta que exige una acción distinta
(no operar, o degradar la convicción), no un suspenso fundamental.

`Magnitud` obliga a declarar las dos cosas por separado y arrastra de dónde
salió el número, para que el informe pueda auditarse línea a línea.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

# Etiqueta que se muestra en los informes cuando una magnitud no está disponible.
SIN_DATO = "n/d"


@dataclass(frozen=True)
class Magnitud:
    """
    Un número financiero junto con su procedencia y su estado de cobertura.

    `valor is None` significa SIEMPRE «no se conoce», nunca «vale cero».
    """

    valor: Optional[float]
    fuente: str = "desconocida"
    unidad: str = "ratio"          # ratio | pct | usd | veces | dias | puntos
    periodo: Optional[str] = None  # p. ej. "TTM", "FY2025", "2026-06-30"
    filed: Optional[str] = None    # fecha de publicación, cuando la fuente la da
    nota: Optional[str] = None

    @property
    def disponible(self) -> bool:
        if self.valor is None:
            return False
        try:
            v = float(self.valor)
        except (TypeError, ValueError):
            return False
        return not (math.isnan(v) or math.isinf(v))

    def o(self, defecto: float) -> float:
        """Valor si está disponible; si no, el defecto EXPLÍCITO que pide quien llama."""
        return float(self.valor) if self.disponible else float(defecto)

    def texto(self, decimales: int = 2) -> str:
        if not self.disponible:
            return SIN_DATO
        v = float(self.valor)
        if self.unidad == "pct":
            return f"{v:.{decimales}%}"
        if self.unidad == "usd":
            return f"${v:,.{decimales}f}"
        if self.unidad == "veces":
            return f"{v:.{decimales}f}x"
        return f"{v:.{decimales}f}"

    def a_dict(self) -> Dict[str, Any]:
        return {
            "valor": self.valor if self.disponible else None,
            "disponible": self.disponible,
            "fuente": self.fuente,
            "unidad": self.unidad,
            "periodo": self.periodo,
            "filed": self.filed,
            "nota": self.nota,
        }


def magnitud(
    valor: Any,
    fuente: str = "desconocida",
    unidad: str = "ratio",
    periodo: Optional[str] = None,
    filed: Optional[str] = None,
    nota: Optional[str] = None,
) -> Magnitud:
    """Construye una `Magnitud` saneando None, NaN, infinitos y cadenas vacías."""
    v: Optional[float]
    if valor is None or valor == "":
        v = None
    else:
        try:
            v = float(valor)
            if math.isnan(v) or math.isinf(v):
                v = None
        except (TypeError, ValueError):
            v = None
    return Magnitud(valor=v, fuente=fuente, unidad=unidad, periodo=periodo,
                    filed=filed, nota=nota)


NO_DISPONIBLE = Magnitud(valor=None, fuente="ninguna")


def primera_disponible(*candidatas: Magnitud) -> Magnitud:
    """
    Primera magnitud con dato de una lista de preferencia.

    Es la primitiva de reconciliación: el orden de los argumentos ES la
    jerarquía de fuentes (normalmente SEC EDGAR antes que un agregador
    comercial).
    """
    for m in candidatas:
        if m is not None and m.disponible:
            return m
    return Magnitud(valor=None, fuente="ninguna", nota="ninguna fuente aportó el dato")


def division(
    numerador: Magnitud,
    denominador: Magnitud,
    fuente: str = "derivada",
    unidad: str = "ratio",
    minimo_denominador: float = 1e-9,
) -> Magnitud:
    """
    División que propaga la indisponibilidad en lugar de inventar un cero.

    Un denominador nulo o casi nulo devuelve «no disponible», no infinito: un
    ratio infinito recorriendo un scorer produce clasificaciones absurdas.
    """
    if not numerador.disponible or not denominador.disponible:
        return Magnitud(None, fuente=fuente, unidad=unidad,
                        nota="falta numerador o denominador")
    d = float(denominador.valor)
    if abs(d) < minimo_denominador:
        return Magnitud(None, fuente=fuente, unidad=unidad, nota="denominador nulo")
    return Magnitud(float(numerador.valor) / d, fuente=fuente, unidad=unidad)


def resta(a: Magnitud, b: Magnitud, fuente: str = "derivada",
          unidad: str = "usd") -> Magnitud:
    if not a.disponible or not b.disponible:
        return Magnitud(None, fuente=fuente, unidad=unidad, nota="falta un operando")
    return Magnitud(float(a.valor) - float(b.valor), fuente=fuente, unidad=unidad)


def suma(*partes: Magnitud, fuente: str = "derivada", unidad: str = "usd",
         exigir_todas: bool = True) -> Magnitud:
    """
    Suma de magnitudes.

    `exigir_todas=True` es el comportamiento correcto para agregados contables
    (deuda corriente + no corriente): si falta un sumando, el total es
    desconocido, no la suma de lo que había. Con `False` se suma lo disponible,
    lo que solo es admisible cuando la ausencia significa de verdad «cero» —
    por ejemplo, un concepto XBRL que la empresa no reporta porque no aplica.
    """
    declaradas = [p for p in partes if p is not None]
    presentes = [p for p in declaradas if p.disponible]
    if exigir_todas and len(presentes) != len(declaradas):
        return Magnitud(None, fuente=fuente, unidad=unidad,
                        nota="falta al menos un sumando")
    if not presentes:
        return Magnitud(None, fuente=fuente, unidad=unidad,
                        nota="ningún sumando disponible")
    return Magnitud(sum(float(p.valor) for p in presentes), fuente=fuente, unidad=unidad)


@dataclass
class Cobertura:
    """
    Inventario de qué se conoce y qué no para un ticker.

    El `ratio` alimenta el `confidence_score` del reconciliador y, a través de
    él, el recorte de convicción del Fund Manager. Es la traducción operativa
    de «no sé, luego arriesgo menos».
    """

    presentes: List[str] = field(default_factory=list)
    ausentes: List[str] = field(default_factory=list)

    def registrar(self, nombre: str, m: Magnitud) -> Magnitud:
        (self.presentes if m.disponible else self.ausentes).append(nombre)
        return m

    def registrar_muchas(self, magnitudes: Dict[str, Magnitud]) -> Dict[str, Magnitud]:
        for nombre, m in magnitudes.items():
            self.registrar(nombre, m)
        return magnitudes

    @property
    def total(self) -> int:
        return len(self.presentes) + len(self.ausentes)

    @property
    def ratio(self) -> float:
        return len(self.presentes) / self.total if self.total else 0.0

    def a_dict(self) -> Dict[str, Any]:
        return {
            "campos_presentes": sorted(self.presentes),
            "campos_ausentes": sorted(self.ausentes),
            "n_presentes": len(self.presentes),
            "n_total": self.total,
            "ratio_cobertura": round(self.ratio, 3),
        }


def a_dict_magnitudes(magnitudes: Dict[str, Magnitud]) -> Dict[str, Any]:
    """Serializa un mapa de magnitudes a JSON plano (valor o None), para el estado."""
    return {k: (v.valor if v.disponible else None) for k, v in magnitudes.items()}


def detalle_magnitudes(magnitudes: Dict[str, Magnitud]) -> Dict[str, Any]:
    """Serializa un mapa de magnitudes con toda su procedencia, para auditoría."""
    return {k: v.a_dict() for k, v in magnitudes.items()}


def desde_dict(datos: Dict[str, Any], claves: Iterable[str], fuente: str,
               unidad: str = "ratio",
               periodo: Optional[str] = None) -> Dict[str, Magnitud]:
    """Convierte un dict plano en magnitudes, sin defaults silenciosos."""
    return {
        k: magnitud(datos.get(k), fuente=fuente, unidad=unidad, periodo=periodo)
        for k in claves
    }
