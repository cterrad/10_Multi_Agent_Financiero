"""
Construcción de cartera a partir de los dictámenes individuales.

POR QUÉ ESTA CAPA NO EXISTÍA Y HACÍA FALTA
------------------------------------------
`cli.py` recorría los tickers uno a uno y nadie miraba nunca el conjunto. Las
consecuencias eran visibles tanto en el informe diario como en el backtest:

  · El informe recomendaba cuatro posiciones del «2.0% - 3.0%» sin decir si esas
    cuatro eran cuatro apuestas o una sola repetida. Dos valores con correlación
    0.9 no diversifican: concentran.
  · Nadie sumaba la exposición. El backtest documenta una exposición bruta media
    del 27.8%, con el 72% del capital parado al 0% — y eso no era una decisión
    de asignación, sino el residuo aritmético de cuántas señales de compra
    aparecían. Buena parte de la diferencia contra el índice era, simplemente,
    no estar invertido.
  · No había límite por sector ni presupuesto de riesgo agregado.

Esta capa no decide QUÉ comprar —eso ya está resuelto cuando llega aquí— sino
CUÁNTO de cada cosa, dado todo lo demás.

ORDEN DE LAS RESTRICCIONES
--------------------------
Se aplican de la menos a la más agresiva, y cada paso deja constancia de lo que
recortó. El orden importa: recortar por correlación antes de aplicar el tope
sectorial produce una cartera distinta que al revés, y hacerlo explícito es lo
que permite auditar el resultado.

  1. Peso deseado por el Fund Manager (ya escalado por riesgo y volatilidad).
  2. Penalización por correlación con el resto de candidatos.
  3. Tope por sector.
  4. Tope de número de posiciones (se conservan las de mayor convicción).
  5. Presupuesto de riesgo agregado de la cartera.
  6. Tope de exposición bruta.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.config import (
    CORRELACION_ALTA,
    CORRELACION_PENALIZACION_MAXIMA,
    CORRELACION_VENTANA_DIAS,
    EXPOSICION_BRUTA_MAXIMA,
    LIMITE_POR_SECTOR,
    MAXIMO_POSICIONES,
    PESO_MAXIMO_POSICION,
    PESO_MINIMO_OPERABLE,
    RENDIMIENTO_LIQUIDEZ_ANUAL,
    RIESGO_TOTAL_CARTERA_PCT,
)


@dataclass
class PosicionPropuesta:
    ticker: str
    empresa: str
    sector: str
    rating: str
    estilo: str
    conviccion: Optional[float]
    peso_solicitado: float          # el que pidió el Fund Manager
    peso_final: float = 0.0
    precio: Optional[float] = None
    stop: Optional[float] = None
    objetivo: Optional[float] = None
    volatilidad: Optional[float] = None
    correlacion_media: Optional[float] = None
    riesgo_aportado: float = 0.0    # peso × distancia al stop
    ajustes: List[str] = field(default_factory=list)
    # Una posición ya abierta consume presupuesto —de sector, de riesgo y de
    # exposición— pero NO se reescala: reajustar cada cartera entera en cada
    # rebalanceo generaría rotación constante cuyo coste se comería cualquier
    # ventaja del ajuste. Las restricciones se aplican, por tanto, solo sobre
    # las candidatas nuevas, contra el presupuesto que dejan libre las fijas.
    fija: bool = False

    def a_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "empresa": self.empresa,
            "sector": self.sector,
            "rating": self.rating,
            "estilo": self.estilo,
            "conviccion": self.conviccion,
            "peso_solicitado_pct": round(self.peso_solicitado * 100, 2),
            "peso_final_pct": round(self.peso_final * 100, 2),
            "precio": self.precio,
            "stop": self.stop,
            "objetivo": self.objetivo,
            "volatilidad_anual": self.volatilidad,
            "correlacion_media": self.correlacion_media,
            "riesgo_aportado_pct": round(self.riesgo_aportado * 100, 3),
            "ajustes": self.ajustes,
            "ya_en_cartera": self.fija,
        }


@dataclass
class CarteraPropuesta:
    posiciones: List[PosicionPropuesta]
    excluidas: List[Dict[str, Any]]
    exposicion_bruta: float
    liquidez: float
    riesgo_total: float
    por_sector: Dict[str, float]
    correlaciones: Optional[Dict[str, Dict[str, float]]]
    diagnostico: Dict[str, Any]
    restricciones_activadas: List[str]

    def a_dict(self) -> Dict[str, Any]:
        return {
            "posiciones": [p.a_dict() for p in self.posiciones],
            "excluidas": self.excluidas,
            "exposicion_bruta_pct": round(self.exposicion_bruta * 100, 2),
            "liquidez_pct": round(self.liquidez * 100, 2),
            "riesgo_total_pct": round(self.riesgo_total * 100, 3),
            "por_sector_pct": {k: round(v * 100, 2) for k, v in self.por_sector.items()},
            "correlaciones": self.correlaciones,
            "diagnostico": self.diagnostico,
            "restricciones_activadas": self.restricciones_activadas,
        }


class PortfolioConstructor:
    """Traduce dictámenes individuales en una cartera con presupuesto de riesgo."""

    def __init__(self, capital: float = 100000.0):
        self.capital = capital

    # ------------------------------------------------------------------ #
    def construir(self, resultados: List[Dict[str, Any]],
                  series_precios: Optional[Dict[str, pd.Series]] = None,
                  posiciones_existentes: Optional[List[Dict[str, Any]]] = None
                  ) -> CarteraPropuesta:
        """
        Cartera objetivo a partir de los dictámenes individuales.

        `posiciones_existentes` permite usar esta capa desde el motor histórico,
        donde en cada rebalanceo ya hay posiciones abiertas. Se incorporan como
        peso FIJO —no se reescalan— pero consumen presupuesto sectorial, de
        riesgo y de exposición, de modo que los límites se aplican sobre la
        cartera completa y no solo sobre las incorporaciones. Sin esto, cada
        rebalanceo podría respetar el tope del 30% por sector y aun así acabar
        con el 90% en un solo sector tras tres rebalanceos.
        """
        candidatas, excluidas = self._candidatas(resultados)
        fijas = self._existentes(posiciones_existentes or [])
        restricciones: List[str] = []

        if not candidatas and not fijas:
            return CarteraPropuesta(
                posiciones=[], excluidas=excluidas, exposicion_bruta=0.0, liquidez=1.0,
                riesgo_total=0.0, por_sector={}, correlaciones=None,
                diagnostico=self._diagnostico([], None),
                restricciones_activadas=["Ninguna señal de compra: cartera íntegramente en liquidez."],
            )

        # Las correlaciones se calculan sobre TODAS las posiciones —abiertas y
        # candidatas— porque lo que importa es el solapamiento de la cartera
        # resultante, no el de las incorporaciones entre sí.
        matriz = self._correlaciones(candidatas + fijas, series_precios)
        self._penalizar_correlacion(candidatas, matriz, restricciones)
        self._limitar_por_sector(candidatas + fijas, restricciones)
        candidatas = self._limitar_numero(candidatas, excluidas, restricciones,
                                          n_fijas=len(fijas))
        self._calcular_riesgo(candidatas + fijas)
        self._limitar_riesgo_total(candidatas + fijas, restricciones)
        self._limitar_exposicion(candidatas + fijas, restricciones)

        # Descarte final de residuos por debajo del mínimo operable.
        vivas: List[PosicionPropuesta] = []
        for p in candidatas:
            if p.fija:
                vivas.append(p)
                continue
            if p.peso_final < PESO_MINIMO_OPERABLE:
                excluidas.append({
                    "ticker": p.ticker, "rating": p.rating,
                    "motivo": (f"peso final {p.peso_final:.2%} por debajo del mínimo operable "
                               f"{PESO_MINIMO_OPERABLE:.2%} tras aplicar las restricciones de cartera"),
                })
            else:
                vivas.append(p)

        # Las posiciones ya abiertas forman parte de la cartera resultante y de
        # todos sus agregados; solo se distinguen por la marca `ya_en_cartera`.
        todas = vivas + fijas
        exposicion = sum(p.peso_final for p in todas)
        por_sector: Dict[str, float] = {}
        for p in todas:
            por_sector[p.sector] = por_sector.get(p.sector, 0.0) + p.peso_final

        return CarteraPropuesta(
            posiciones=sorted(todas, key=lambda x: x.peso_final, reverse=True),
            excluidas=excluidas,
            exposicion_bruta=exposicion,
            liquidez=max(0.0, 1.0 - exposicion),
            riesgo_total=sum(p.riesgo_aportado for p in todas),
            por_sector=por_sector,
            correlaciones=matriz,
            diagnostico=self._diagnostico(todas, matriz),
            restricciones_activadas=restricciones,
        )

    # ------------------------------------------------------------------ #
    @staticmethod
    def _existentes(posiciones: List[Dict[str, Any]]) -> List[PosicionPropuesta]:
        """Traduce las posiciones abiertas del motor a la representación interna."""
        fijas = []
        for p in posiciones:
            peso = float(p.get("peso") or 0.0)
            if peso <= 0:
                continue
            fijas.append(PosicionPropuesta(
                ticker=p.get("ticker", "?"),
                empresa=p.get("empresa", p.get("ticker", "?")),
                sector=p.get("sector") or "Desconocido",
                rating=p.get("rating", "EN CARTERA"),
                estilo=p.get("estilo", "n/d"),
                conviccion=p.get("conviccion"),
                peso_solicitado=peso,
                peso_final=peso,
                precio=p.get("precio"),
                stop=p.get("stop"),
                objetivo=p.get("objetivo"),
                volatilidad=p.get("volatilidad"),
                fija=True,
            ))
        return fijas

    @staticmethod
    def _candidatas(resultados: List[Dict[str, Any]]):
        candidatas: List[PosicionPropuesta] = []
        excluidas: List[Dict[str, Any]] = []

        for res in resultados:
            decision = res.get("final_decision", {}) or {}
            calidad = res.get("quality_report", {}) or {}
            tecnico = res.get("technical_report", {}) or {}
            peso = decision.get("peso_objetivo", 0.0) or 0.0
            ticker = res.get("ticker", "?")

            if peso <= 0:
                excluidas.append({
                    "ticker": ticker,
                    "rating": decision.get("rating", "N/A"),
                    "motivo": decision.get("dimensionado", {}).get(
                        "motivo", "sin asignación de cartera"),
                })
                continue

            candidatas.append(PosicionPropuesta(
                ticker=ticker,
                empresa=res.get("company_name", ticker),
                sector=res.get("sector") or "Desconocido",
                rating=decision.get("rating", "N/A"),
                estilo=calidad.get("style_classification", "n/d"),
                conviccion=(calidad.get("conviccion_fundamental") or {}).get("valor"),
                peso_solicitado=peso,
                peso_final=peso,
                precio=decision.get("current_price"),
                stop=decision.get("stop_loss_atr"),
                objetivo=decision.get("take_profit_atr"),
                volatilidad=tecnico.get("volatilidad_anual"),
            ))

        return candidatas, excluidas

    # ------------------------------------------------------------------ #
    @staticmethod
    def _correlaciones(candidatas: List[PosicionPropuesta],
                       series: Optional[Dict[str, pd.Series]]):
        """
        Matriz de correlación de rentabilidades diarias.

        Devuelve None si no hay series suficientes. En ese caso la penalización
        por correlación no se aplica y se declara en el informe: es preferible
        no corregir a corregir con una matriz inventada.
        """
        if not series:
            return None
        disponibles = {p.ticker: series[p.ticker] for p in candidatas if p.ticker in series}
        if len(disponibles) < 2:
            return None

        df = pd.DataFrame(disponibles).dropna()
        if len(df) < 30:
            return None
        rets = df.pct_change().dropna().tail(CORRELACION_VENTANA_DIAS)
        if len(rets) < 20:
            return None

        matriz = rets.corr()
        return {a: {b: round(float(matriz.loc[a, b]), 3) for b in matriz.columns}
                for a in matriz.index}

    @staticmethod
    def _penalizar_correlacion(candidatas: List[PosicionPropuesta],
                               matriz: Optional[Dict[str, Dict[str, float]]],
                               restricciones: List[str]) -> None:
        """
        Recorta el peso de los valores que replican el riesgo de sus compañeros.

        La penalización es proporcional al exceso de correlación media sobre
        `CORRELACION_ALTA` y está acotada: no se elimina una posición por estar
        correlacionada, se reduce. Dos valores con correlación 0.9 no son dos
        apuestas, son una y media.
        """
        if not matriz:
            restricciones.append(
                "Sin matriz de correlaciones disponible: no se aplicó penalización por "
                "solapamiento de riesgo. La diversificación declarada es nominal, no efectiva.")
            return

        aplicadas = 0
        for p in candidatas:
            fila = matriz.get(p.ticker)
            if not fila:
                continue
            otros = [v for k, v in fila.items() if k != p.ticker]
            if not otros:
                continue
            media = sum(otros) / len(otros)
            p.correlacion_media = round(media, 3)
            if media <= CORRELACION_ALTA:
                continue
            exceso = (media - CORRELACION_ALTA) / max(1.0 - CORRELACION_ALTA, 1e-6)
            penalizacion = min(CORRELACION_PENALIZACION_MAXIMA, exceso * CORRELACION_PENALIZACION_MAXIMA)
            p.peso_final *= (1.0 - penalizacion)
            p.ajustes.append(
                f"Peso reducido un {penalizacion:.0%} por correlación media de {media:.2f} "
                f"con el resto de candidatos (umbral {CORRELACION_ALTA:.2f}).")
            aplicadas += 1

        if aplicadas:
            restricciones.append(
                f"Penalización por correlación aplicada a {aplicadas} posición(es).")

    @staticmethod
    def _limitar_por_sector(candidatas: List[PosicionPropuesta],
                            restricciones: List[str]) -> None:
        """Escala proporcionalmente los pesos de cada sector que supere el tope."""
        por_sector: Dict[str, List[PosicionPropuesta]] = {}
        for p in candidatas:
            por_sector.setdefault(p.sector, []).append(p)

        for sector, posiciones in por_sector.items():
            total = sum(p.peso_final for p in posiciones)
            if total <= LIMITE_POR_SECTOR:
                continue
            ajustables = [p for p in posiciones if not p.fija]
            comprometido = sum(p.peso_final for p in posiciones if p.fija)
            disponible = max(0.0, LIMITE_POR_SECTOR - comprometido)
            total_ajustable = sum(p.peso_final for p in ajustables)
            factor = (disponible / total_ajustable) if total_ajustable > 0 else 0.0
            for p in ajustables:
                p.peso_final *= factor
                p.ajustes.append(
                    f"Peso escalado ×{factor:.2f}: el sector {sector} sumaba {total:.1%} "
                    f"frente al tope del {LIMITE_POR_SECTOR:.0%}"
                    + (f", de los que {comprometido:.1%} ya estaban en cartera"
                       if comprometido else "") + ".")
            restricciones.append(
                f"Tope sectorial activado en {sector}: {total:.1%} → "
                f"{comprometido + total_ajustable * factor:.1%}.")

    @staticmethod
    def _limitar_numero(candidatas: List[PosicionPropuesta], excluidas: List[Dict[str, Any]],
                        restricciones: List[str],
                        n_fijas: int = 0) -> List[PosicionPropuesta]:
        # Los huecos disponibles son los que dejan libres las posiciones ya
        # abiertas: el tope es de la cartera, no de las incorporaciones.
        huecos = max(0, MAXIMO_POSICIONES - n_fijas)
        if len(candidatas) <= huecos:
            return candidatas
        ordenadas = sorted(candidatas,
                           key=lambda p: (p.conviccion if p.conviccion is not None else 0.0,
                                          p.peso_final),
                           reverse=True)
        conservadas, descartadas = ordenadas[:huecos], ordenadas[huecos:]
        for p in descartadas:
            excluidas.append({
                "ticker": p.ticker, "rating": p.rating,
                "motivo": (f"fuera de las {MAXIMO_POSICIONES} posiciones máximas por convicción "
                           f"({p.conviccion})"),
            })
        restricciones.append(
            f"Límite de {MAXIMO_POSICIONES} posiciones ({n_fijas} ya en cartera): "
            f"{len(descartadas)} candidata(s) descartada(s).")
        return conservadas

    @staticmethod
    def _calcular_riesgo(posiciones: List[PosicionPropuesta]) -> None:
        """
        Riesgo aportado = peso × distancia relativa al stop.

        Es cuánto patrimonio se pierde si esa posición toca su stop. Sin stop
        conocido se asume un 10%, que es deliberadamente conservador: presumir
        una distancia menor infravaloraría el riesgo justo donde hay menos
        información.
        """
        for p in posiciones:
            if p.precio and p.stop and p.precio > 0:
                distancia = max(0.0, (p.precio - p.stop) / p.precio)
            else:
                distancia = 0.10
            p.riesgo_aportado = p.peso_final * distancia

    @staticmethod
    def _limitar_riesgo_total(posiciones: List[PosicionPropuesta],
                              restricciones: List[str]) -> None:
        """
        Presupuesto de riesgo agregado.

        La suma de los riesgos aportados es la pérdida si TODAS las posiciones
        tocan su stop a la vez — el escenario que importa, porque las
        correlaciones tienden a 1 en las caídas.
        """
        total = sum(p.riesgo_aportado for p in posiciones)
        if total <= RIESGO_TOTAL_CARTERA_PCT or total <= 0:
            return

        ajustables = [p for p in posiciones if not p.fija]
        comprometido = sum(p.riesgo_aportado for p in posiciones if p.fija)
        disponible = max(0.0, RIESGO_TOTAL_CARTERA_PCT - comprometido)
        total_ajustable = sum(p.riesgo_aportado for p in ajustables)
        factor = (disponible / total_ajustable) if total_ajustable > 0 else 0.0

        for p in ajustables:
            p.peso_final *= factor
            p.riesgo_aportado *= factor
            p.ajustes.append(
                f"Peso escalado ×{factor:.2f} por el presupuesto de riesgo agregado "
                f"({RIESGO_TOTAL_CARTERA_PCT:.1%} del patrimonio).")
        restricciones.append(
            f"Presupuesto de riesgo agregado activado: riesgo simultáneo de {total:.2%} "
            f"reducido al {comprometido + total_ajustable * factor:.2%}.")

    @staticmethod
    def _limitar_exposicion(posiciones: List[PosicionPropuesta],
                            restricciones: List[str]) -> None:
        total = sum(p.peso_final for p in posiciones)
        if total <= EXPOSICION_BRUTA_MAXIMA or total <= 0:
            return
        ajustables = [p for p in posiciones if not p.fija]
        comprometido = sum(p.peso_final for p in posiciones if p.fija)
        disponible = max(0.0, EXPOSICION_BRUTA_MAXIMA - comprometido)
        total_ajustable = sum(p.peso_final for p in ajustables)
        factor = (disponible / total_ajustable) if total_ajustable > 0 else 0.0

        for p in ajustables:
            p.peso_final *= factor
            p.riesgo_aportado *= factor
            p.ajustes.append(f"Peso escalado ×{factor:.2f} por el tope de exposición bruta.")
        restricciones.append(
            f"Tope de exposición bruta activado: {total:.1%} → "
            f"{comprometido + total_ajustable * factor:.1%}.")

    # ------------------------------------------------------------------ #
    def _diagnostico(self, posiciones: List[PosicionPropuesta],
                     matriz: Optional[Dict[str, Dict[str, float]]]) -> Dict[str, Any]:
        """
        Métricas de la cartera resultante.

        `posiciones_efectivas` es el inverso del índice de Herfindahl: cuántas
        posiciones equiponderadas producirían la misma concentración. Junto al
        ratio de diversificación responde a la pregunta que el informe anterior
        no se hacía: ¿estas posiciones son apuestas distintas o la misma?
        """
        n = len(posiciones)
        exposicion = sum(p.peso_final for p in posiciones)
        liquidez = max(0.0, 1.0 - exposicion)

        base: Dict[str, Any] = {
            "n_posiciones": n,
            "exposicion_bruta_pct": round(exposicion * 100, 2),
            "liquidez_pct": round(liquidez * 100, 2),
            "rendimiento_liquidez_supuesto_pct": round(RENDIMIENTO_LIQUIDEZ_ANUAL * 100, 2),
            "aportacion_liquidez_anual_pct": round(liquidez * RENDIMIENTO_LIQUIDEZ_ANUAL * 100, 2),
            "peso_maximo_pct": round(max((p.peso_final for p in posiciones), default=0.0) * 100, 2),
            "tope_por_posicion_pct": round(PESO_MAXIMO_POSICION * 100, 2),
        }

        if not posiciones or exposicion <= 0:
            base["nota"] = "Cartera sin posiciones: el 100% permanece en liquidez."
            return base

        pesos = np.array([p.peso_final for p in posiciones])
        relativos = pesos / pesos.sum()
        hhi = float((relativos ** 2).sum())
        base["posiciones_efectivas"] = round(1.0 / hhi, 2) if hhi > 0 else None
        base["indice_herfindahl"] = round(hhi, 4)

        vols = [p.volatilidad for p in posiciones if p.volatilidad]
        if vols and matriz:
            # Volatilidad de la cartera: w'Σw con Σ reconstruida desde la
            # correlación y las volatilidades individuales.
            tickers = [p.ticker for p in posiciones]
            sigma = np.zeros((len(tickers), len(tickers)))
            completa = True
            for i, a in enumerate(tickers):
                for j, b in enumerate(tickers):
                    va = posiciones[i].volatilidad
                    vb = posiciones[j].volatilidad
                    rho = (matriz.get(a, {}) or {}).get(b)
                    if va is None or vb is None or rho is None:
                        completa = False
                        break
                    sigma[i, j] = va * vb * rho
                if not completa:
                    break
            if completa:
                vol_cartera = float(np.sqrt(pesos @ sigma @ pesos))
                vol_ponderada = float(sum(p.peso_final * p.volatilidad for p in posiciones))
                base["volatilidad_cartera_anual_pct"] = round(vol_cartera * 100, 2)
                base["volatilidad_suma_ponderada_pct"] = round(vol_ponderada * 100, 2)
                base["ratio_diversificacion"] = (
                    round(vol_ponderada / vol_cartera, 2) if vol_cartera > 0 else None)
                base["nota_diversificacion"] = (
                    "Ratio de diversificación 1.0 significa que las posiciones se mueven como una "
                    "sola; por encima de 1.3 la cartera aporta diversificación real.")
        elif not matriz:
            base["nota_diversificacion"] = (
                "Sin matriz de correlaciones: no se puede afirmar que estas posiciones sean "
                "apuestas independientes.")

        pares_altos = []
        if matriz:
            tickers = [p.ticker for p in posiciones]
            for i, a in enumerate(tickers):
                for b in tickers[i + 1:]:
                    rho = (matriz.get(a, {}) or {}).get(b)
                    if rho is not None and rho >= CORRELACION_ALTA:
                        pares_altos.append({"par": f"{a}/{b}", "correlacion": rho})
        base["pares_muy_correlacionados"] = sorted(
            pares_altos, key=lambda x: x["correlacion"], reverse=True)

        return base
