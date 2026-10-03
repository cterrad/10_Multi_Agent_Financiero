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
  2. Reflexión: recorte por expectativa histórica y REASIGNACIÓN del presupuesto
     liberado entre los candidatos sin evidencia en contra.
  3. Penalización por correlación con el resto de candidatos.
  4. Tope por sector.
  5. Tope de número de posiciones (se conservan las de mayor convicción).
  6. Presupuesto de riesgo agregado de la cartera.
  7. Tope de exposición bruta.

POR QUÉ LA REFLEXIÓN VA LA SEGUNDA Y NO LA ÚLTIMA
-------------------------------------------------
Porque modifica el peso BASE, igual que la penalización por correlación, y todos
los topes posteriores tienen que seguir mordiendo sobre el resultado. Colocarla
al final dejaría que un recorte por expectativa histórica reabriera hueco por
encima del límite sectorial o del presupuesto de riesgo, que es precisamente lo
que esos límites existen para impedir.

Y reasigna en lugar de solo recortar porque el sistema ya opera con una
exposición bruta media del 30%: una capa que solo restara empeoraría el
problema que el propio informe declara como su mayor limitación. El presupuesto
que sale de un perfil con mal historial va a los demás candidatos del mismo
rebalanceo, no a la liquidez.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.config import (
    CORRELACION_ALTA,
    CORRELACION_DENOISE,
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
    # Factor de la memoria de reflexión emitido por el Fund Manager, SIN aplicar:
    # lo aplica esta capa, que es la única que puede reasignar a otros
    # candidatos el presupuesto que el recorte libera.
    factor_reflexion: float = 1.0
    # Factor del meta-modelo, hermano exacto del anterior: publicado SIN aplicar
    # por el Fund Manager y aplicado aquí, porque solo esta capa ve el
    # rebalanceo entero y puede reasignar lo que el recorte libera.
    factor_meta: float = 1.0
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
            "factor_reflexion": self.factor_reflexion,
            "factor_meta": self.factor_meta,
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
                  posiciones_existentes: Optional[List[Dict[str, Any]]] = None,
                  drawdown: Optional[float] = None
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

        `drawdown` es la caída acumulada de la cartera desde su máximo, en tanto
        por uno y negativa. **Opcional y neutro por defecto**: producción no
        gestiona una cartera y nunca lo tiene, así que sin él esta capa se
        comporta exactamente igual que antes de que el freno existiera.
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
        # La reflexión va antes que todo lo demás porque modifica el peso BASE:
        # los topes posteriores tienen que morder sobre el resultado, no sobre
        # el peso original.
        # Los dos factores que solo recortan, en este orden y por el mismo motivo
        # que la reflexión va la segunda y no la última: modifican el peso BASE, y
        # todos los topes posteriores tienen que morder sobre el resultado.
        #
        # La reflexión va antes que el meta-modelo porque es la capa más
        # conservadora de las dos —una media condicionada frente a un modelo
        # entrenado— y porque así el meta-modelo reparte sobre un peso que ya ha
        # pasado el filtro histórico, y no al revés.
        self._penalizar_reflexion(candidatas, restricciones)
        self._penalizar_meta(candidatas, restricciones)

        matriz = self._correlaciones(candidatas + fijas, series_precios)
        self._penalizar_correlacion(candidatas, matriz, restricciones)
        self._limitar_por_sector(candidatas + fijas, restricciones)
        candidatas = self._limitar_numero(candidatas, excluidas, restricciones,
                                          n_fijas=len(fijas))
        self._calcular_riesgo(candidatas + fijas)
        self._limitar_riesgo_total(candidatas + fijas, restricciones)
        self._frenar_por_drawdown(candidatas + fijas, restricciones, drawdown)
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
                factor_reflexion=float(decision.get("factor_reflexion") or 1.0),
                factor_meta=float(decision.get("factor_meta") or 1.0),
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

        LA MATRIZ SE LIMPIA DE RUIDO ANTES DE USARSE
        ---------------------------------------------
        La versión anterior devolvía `rets.corr()` en crudo. Con las
        observaciones y el número de activos de un rebalanceo, la mayor parte del
        espectro de esa matriz es indistinguible del que produciría una matriz de
        rendimientos independientes, así que la penalización por correlación
        media estaba respondiendo en parte a estructura que no existe.

        `denoise_correlaciones` (Marchenko-Pastur) sustituye los autovalores de
        ruido por su media y renormaliza la diagonal. **No necesita ningún dato
        nuevo.** Si ningún autovalor cae bajo la frontera, la matriz se devuelve
        intacta: forzar la corrección ahí destruiría señal real.
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
        cruda = {a: {b: round(float(matriz.loc[a, b]), 3) for b in matriz.columns}
                 for a in matriz.index}

        if not CORRELACION_DENOISE:
            return cruda
        # Importación DIFERIDA: `src.tools.covarianza` dispara el `__init__` del
        # paquete de tools, que importa `src.tools.cartera`, que importa este
        # mismo paquete. Es el mismo ciclo —y la misma solución— que en
        # `DataFetcher._niveles_precio`.
        from src.tools.covarianza import _denoise
        limpia = _denoise(cruda, q=len(rets) / max(1, len(matriz.columns)))
        return limpia["matriz"]

    @staticmethod
    def _penalizar_reflexion(candidatas: List[PosicionPropuesta],
                             restricciones: List[str]) -> None:
        """
        Recorte por memoria de reflexión. Delega en `_penalizar_por_factor`.

        Conserva su nombre propio porque la intención se lee en el punto de
        llamada —y porque es la que los tests de la capa invocan directamente—,
        pero la mecánica de recortar y reasignar es compartida: dos copias serían
        dos sitios donde esa semántica podría divergir.
        """
        PortfolioConstructor._penalizar_por_factor(
            candidatas, restricciones, "factor_reflexion",
            nota_recorte=("por memoria de reflexión: las señales con este perfil "
                          "rindieron por debajo del índice."),
            nota_receptor=("Peso ampliado con el presupuesto liberado por candidatos "
                           "con peor historial de reflexión."),
            etiqueta="Memoria de reflexión")

    @staticmethod
    def _penalizar_meta(candidatas: List[PosicionPropuesta],
                        restricciones: List[str]) -> None:
        """
        Recorte por el meta-modelo. Hermano exacto del anterior.

        Va DESPUÉS de la reflexión porque ésta es la capa más conservadora de las
        dos —una media condicionada frente a un modelo entrenado— y así el
        meta-modelo reparte sobre un peso que ya ha pasado el filtro histórico.
        """
        PortfolioConstructor._penalizar_por_factor(
            candidatas, restricciones, "factor_meta",
            nota_recorte=("por el meta-modelo: la probabilidad de que esta operación "
                          "acabe en beneficio está por debajo de la tasa base del "
                          "sistema."),
            nota_receptor=("Peso ampliado con el presupuesto liberado por candidatos "
                           "con menor probabilidad estimada de acierto."),
            etiqueta="Meta-modelo")

    @staticmethod
    def _penalizar_por_factor(candidatas: List[PosicionPropuesta],
                              restricciones: List[str], atributo: str,
                              nota_recorte: str, nota_receptor: str,
                              etiqueta: str) -> None:
        """
        Recorta el peso de los candidatos con factor < 1 y REPARTE lo recortado
        entre los que no lo tienen.

        ESTA FUNCIÓN LA COMPARTEN LA MEMORIA DE REFLEXIÓN Y EL META-MODELO, y
        eso no es un ahorro de líneas: los dos factores tienen exactamente la
        misma semántica —solo recortan, y el presupuesto liberado se reasigna—
        así que dos implementaciones serían dos sitios donde esa semántica
        podría divergir sin que nada lo dijera. Es el mismo criterio por el que
        `COTStore` invoca `serie_semanal` en vez de reimplementarla.

        El factor lo calcula `src/tools/reflexion.py` y lo publica el Fund
        Manager sin aplicarlo, porque aplicarlo valor a valor solo sabría restar.
        Aquí se ve el rebalanceo entero, así que el presupuesto liberado va a los
        candidatos SIN evidencia en contra —los de factor 1.0— en proporción a
        su peso y hasta el tope de concentración. La exposición bruta del
        conjunto se conserva; lo que cambia es su reparto.

        Tres consecuencias que conviene tener presentes:

          · Los receptores son solo los NO penalizados. Reescalar también a los
            penalizados les devolvería parte del recorte y dejaría el ajuste en
            un cambio de orden sin efecto real sobre el riesgo asumido.
          · Con un único candidato penalizado no hay a quién reasignar y el
            presupuesto se queda sin usar. En ese caso el freno efectivo es el
            veto de `aplicar_vetos`, no el factor.
          · Si el tope de concentración impide colocar todo lo liberado, el
            resto se queda en liquidez y se declara. Sobrepasar
            `PESO_MAXIMO_POSICION` para conservar la exposición sería cambiar un
            riesgo por otro peor.
        """
        if not candidatas:
            return
        penalizadas = [p for p in candidatas if getattr(p, atributo) < 1.0]
        if not penalizadas:
            return

        presupuesto = sum(p.peso_final for p in candidatas)
        for p in penalizadas:
            factor = getattr(p, atributo)
            p.peso_final -= p.peso_final * (1.0 - factor)
            p.ajustes.append(f"Peso reducido un {1.0 - factor:.0%} {nota_recorte}")

        sobrante = presupuesto - sum(p.peso_final for p in candidatas)
        receptores = [p for p in candidatas if getattr(p, atributo) >= 1.0]

        reasignado = 0.0
        con_hueco = list(receptores)
        for _ in range(5):   # agua sobre agua: cinco pasadas bastan para converger
            con_hueco = [p for p in con_hueco if p.peso_final < PESO_MAXIMO_POSICION - 1e-9]
            base = sum(p.peso_final for p in con_hueco)
            if sobrante <= 1e-9 or not con_hueco or base <= 0:
                break
            repartido = 0.0
            for p in con_hueco:
                nuevo = min(PESO_MAXIMO_POSICION,
                            p.peso_final + sobrante * (p.peso_final / base))
                repartido += nuevo - p.peso_final
                p.peso_final = nuevo
            sobrante -= repartido
            reasignado += repartido

        if reasignado > 0:
            # La nota va a TODOS los receptores, no solo a los que quedaban con
            # hueco en la última pasada: los que llegaron al tope también
            # recibieron parte del presupuesto y su peso también está explicado.
            for p in receptores:
                p.ajustes.append(nota_receptor)

        restricciones.append(
            f"{etiqueta}: {len(penalizadas)} posición(es) recortada(s) y "
            f"{reasignado:.2%} de patrimonio reasignado a {len(receptores)} candidato(s) "
            f"sin evidencia en contra."
            + ("" if sobrante <= 1e-9 else
               f" Quedan {sobrante:.2%} sin colocar por el tope de concentración."))

    # ------------------------------------------------------------------ #
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
    def _frenar_por_drawdown(posiciones: List[PosicionPropuesta],
                             restricciones: List[str],
                             drawdown: Optional[float]) -> None:
        """
        Reduce la exposición del conjunto cuando la cartera acumula pérdidas.

        Es `drawdown_guard` del repositorio 03, traducido de excepción a factor.
        Se aplica AL FINAL, sobre los pesos ya recortados por todo lo demás,
        porque no compite con las otras restricciones: no dice qué comprar menos,
        dice cuánto menos comprar de todo.

        **Neutro por defecto, y ése es el punto.** Sin `drawdown` no hace nada, y
        producción nunca lo tiene: el sistema emite recomendaciones, no gestiona
        una cartera y no conoce su patrimonio. Cablearlo solo en el backtest
        sería una variable de decisión medida en el estudio y ausente en
        producción — la imagen especular de la limitación nº 5 y por el mismo
        motivo igual de mala. Queda declarado INERTE en `build_limitations()`.
        """
        if drawdown is None:
            return
        from src.tools.riesgo import _freno
        r = _freno(drawdown)
        factor = r["factor_drawdown"]
        if factor >= 1.0:
            return
        ajustables = [p for p in posiciones if not p.fija]
        for p in ajustables:
            p.peso_final *= factor
            p.riesgo_aportado *= factor
            p.ajustes.append(
                f"Peso escalado ×{factor:.2f} por el freno de drawdown "
                f"({r['drawdown']:.1%} desde el máximo).")
        restricciones.append(
            f"Freno por drawdown activado: la cartera acumula {r['drawdown']:.1%} desde "
            f"su máximo y la exposición nueva se reduce un {1 - factor:.0%}.")

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
