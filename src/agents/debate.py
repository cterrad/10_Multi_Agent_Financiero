"""
Capa de Debate y Mitigación de Sesgos.

QUÉ SE ARREGLA AQUÍ
-------------------
La tesis alcista se construía con una lista fija de tres frases, y la tercera
era literal:

    f"Estructura técnica con clasificación {momentum} y RSI de {rsi:.1f} "
    f"en zona de fuerte impulso."

«En zona de fuerte impulso» se imprimía SIEMPRE, independientemente del valor
del RSI. En el informe del 2026-08-21 apareció en DOCN (RSI 47.7), BE (48.6) y
GOOGL (39.3) —los tres en zona neutral o débil— acompañando además a la
clasificación «NEUTRAL» en la misma frase. El texto contradecía al dato que él
mismo citaba, y el LLM aguas abajo amplificaba la contradicción porque recibía
esa frase como insumo.

Lo mismo ocurría con las tres primeras: «Excelente crecimiento de ingresos» se
afirmaba con cualquier cifra, incluida una negativa.

Ahora cada argumento tiene una CONDICIÓN de activación y un calificativo
derivado del propio número. Si no hay nada que decir en una dirección, no se
dice: un debate honesto puede ser asimétrico, y forzar tres puntos por bando
fabrica argumentos que no existen.

Además el debate incorpora los dictámenes del Analista de Calidad —valoración
frente a sector, banderas rojas, estilo— que antes no llegaban aquí.

El Analista de Noticias sigue siendo capa ASESORA: aporta un argumento y nada
más. No toca `rating` ni `position_size_pct`, y `test_news_report_does_not_alter_decision`
protege esa premisa porque de ella depende la validez del backtest.
"""

from typing import Any, Dict, List, Optional

from src.config import (
    MARGEN_BRUTO_FOSO,
    PEG_ATRACTIVO,
    ROIC_EXCELENTE,
    SECTOR_DESCONOCIDO,
    get_llm,
    texto_de_respuesta_llm,
)
from src.state import FinancialAnalysisState


def _argumento_de_noticias(news_report: Dict[str, Any]) -> Optional[str]:
    """
    Traduce el informe del Analista de Noticias a una frase para el debate.

    Es un ARGUMENTO, no una decisión: la probabilidad y la dirección ya vienen
    calculadas y aquí solo se redactan. Devuelve None cuando no hay noticias,
    y en ese caso el debate produce exactamente el mismo texto que antes de
    existir esta capa — que es lo que mantiene el backtest comparable.
    """
    if not news_report or not news_report.get("n_items"):
        return None

    catalizador = (news_report.get("catalysts") or [{}])[0].get("titular", "")
    return (
        f"Flujo de noticias con probabilidad de impacto "
        f"{news_report.get('impact_classification', 'N/A')} "
        f"({news_report.get('impact_probability', 0.0):.2f}) y sesgo "
        f"{news_report.get('direction_classification', 'N/A')} sobre "
        f"{news_report.get('n_items', 0)} nota(s); principal catalizador: "
        f"\"{catalizador[:120]}\" (capa asesora: no altera el dictamen)."
    )


def _calificar(valor: float, tramos: List[tuple]) -> str:
    """
    Adjetivo derivado del número, no de una plantilla.

    `tramos` es una lista de (umbral, adjetivo) ordenada de mayor a menor. La
    función existe para que ningún calificativo pueda escribirse sin haber
    comprobado antes la cifra que describe.
    """
    for umbral, adjetivo in tramos:
        if valor >= umbral:
            return adjetivo
    return tramos[-1][1]


class DebateUnitAgent:
    """
    Debate entre el investigador alcista y el bajista (abogado del diablo).

    Ambas tesis se construyen con argumentos condicionados a los datos. La
    síntesis determinista pondera las dos y declara qué tendría que ocurrir
    para invalidar la posición.
    """

    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        sector = state.get("sector") or SECTOR_DESCONOCIDO
        fund = state.get("fundamental_report", {}) or {}
        tech = state.get("technical_report", {}) or {}
        quality = state.get("quality_report", {}) or {}
        rec = state.get("reconciliation_data", {}) or {}
        metrics = fund.get("metrics", {}) or {}

        news = state.get("news_report", {}) or {}
        news_frase = _argumento_de_noticias(news)
        news_direccion = news.get("direction_classification")

        alcistas = self._tesis_alcista(metrics, tech, quality, sector)
        bajistas = self._tesis_bajista(metrics, tech, quality, rec, sector)

        if news_frase and news_direccion == "ALCISTA":
            alcistas.append(news_frase)
        if news_frase and news_direccion == "BAJISTA":
            bajistas.append(news_frase)

        if not alcistas:
            alcistas.append(
                "Sin argumentos alcistas sustentados en los datos disponibles. La ausencia de "
                "tesis positiva es en sí misma información: no se fabrica un argumento para "
                "equilibrar el debate.")
        if not bajistas:
            bajistas.append(
                "Sin banderas rojas identificadas en los datos disponibles. Riesgo residual de "
                "desaceleración macroeconómica sectorial y de compresión de múltiplos.")

        bullish_case = f"TESIS ALCISTA ({ticker}): " + " ".join(alcistas)
        bearish_case = f"TESIS BAJISTA ({ticker}): " + " ".join(bajistas)

        synthesis = self._sintesis(ticker, quality, tech, alcistas, bajistas, news_frase)

        informe = {
            "bullish_case": bullish_case,
            "bearish_case": bearish_case,
            "argumentos_alcistas": alcistas,
            "argumentos_bajistas": bajistas,
            "n_alcistas": len(alcistas),
            "n_bajistas": len(bajistas),
            "invalidacion": self._condiciones_de_invalidacion(quality, tech, metrics),
            "resumen_determinista": synthesis,
            "synthesis": synthesis,
        }

        llm = get_llm()
        if llm:
            try:
                prompt = (
                    f"Realiza la síntesis de un debate de inversión sobre {ticker} ({sector}):\n"
                    f"- Argumentos alcistas: {bullish_case}\n"
                    f"- Argumentos bajistas: {bearish_case}\n"
                    + (f"- Contexto de noticias (asesor): {news_frase}\n" if news_frase else "")
                    + f"- Estilo asignado: {quality.get('style_classification', 'n/d')}\n"
                    f"Escribe una conclusión imparcial de 3 frases ponderando ambas posturas. "
                    f"Cíñete a las cifras citadas: no describas como fuerte un impulso que los "
                    f"datos no muestran, ni añadas argumentos que no aparezcan arriba."
                )
                texto = texto_de_respuesta_llm(llm.invoke(prompt))
                if texto:
                    informe["synthesis"] = texto
            except Exception as e:
                print(f"[DebateUnit] Error LLM: {e}")

        return informe

    # ------------------------------------------------------------------ #
    def _tesis_alcista(self, metrics: Dict[str, Any], tech: Dict[str, Any],
                       quality: Dict[str, Any], sector: str) -> List[str]:
        """Cada argumento se activa solo si la cifra que lo sostiene lo justifica."""
        args: List[str] = []
        contexto = (quality.get("contexto_sectorial") or {}).get("comparaciones", {})
        buffett = quality.get("buffett", {}) or {}
        lynch = quality.get("lynch", {}) or {}
        graham = quality.get("graham", {}) or {}
        piotroski = quality.get("piotroski", {}) or {}
        puntuaciones = quality.get("puntuaciones", {}) or {}

        crec = metrics.get("revenue_growth")
        if crec is not None and crec > 0.05:
            adjetivo = _calificar(crec, [(0.30, "excepcional"), (0.15, "sólido"), (0.05, "moderado")])
            ref = contexto.get("crecimiento_ingresos", {})
            comparativa = (f", {ref.get('lectura')} (mediana de {sector}: "
                           f"{ref.get('referencia_sector', 0):.0%})") if ref.get("ratio") else ""
            args.append(f"Crecimiento de ingresos {adjetivo} del {crec:.1%}{comparativa}.")

        margen = metrics.get("net_margin")
        if margen is not None and margen > 0.05:
            adjetivo = _calificar(margen, [(0.30, "muy alto"), (0.15, "sólido"), (0.05, "aceptable")])
            ref = contexto.get("margen_neto", {})
            comparativa = f", {ref.get('lectura')}" if ref.get("ratio") else ""
            args.append(f"Margen neto {adjetivo} del {margen:.1%}{comparativa}.")

        roic = buffett.get("roic")
        if roic is not None and roic >= ROIC_EXCELENTE:
            args.append(f"ROIC del {roic:.1%}, por encima del coste de capital de referencia "
                        f"({buffett.get('wacc_referencia'):.0%}): el negocio crea valor con cada "
                        f"euro reinvertido.")

        mb = buffett.get("margen_bruto")
        if mb is not None and mb >= MARGEN_BRUTO_FOSO:
            args.append(f"Margen bruto del {mb:.0%}, indicio de poder de fijación de precios.")

        if piotroski.get("lectura") == "FUERTE":
            args.append(f"F-Score de Piotroski {piotroski.get('score')}/"
                        f"{piotroski.get('criterios_evaluables')}: la calidad contable mejora "
                        f"en rentabilidad, apalancamiento y eficiencia a la vez.")

        peg = lynch.get("peg")
        if peg is not None and peg <= PEG_ATRACTIVO:
            args.append(f"PEG de {peg} sobre crecimiento de {lynch.get('base_del_crecimiento')}: "
                        f"el múltiplo no se ha adelantado al crecimiento.")

        ms = graham.get("margen_seguridad")
        if ms is not None and ms > 0:
            args.append(f"Cotiza un {ms:.0%} por debajo del Número de Graham "
                        f"(${graham.get('numero_graham')}), margen de seguridad sobre una "
                        f"valoración conservadora.")

        fcf = buffett.get("fcf_yield")
        if fcf is not None and fcf >= 0.05:
            args.append(f"Rendimiento del flujo de caja libre del {fcf:.1%}.")

        # --- técnico: solo lo que el dato sostiene ------------------------
        estado_tendencia = tech.get("estado_tendencia")
        rsi = tech.get("rsi")
        rsi_estado = tech.get("rsi_estado")
        score = tech.get("momentum_score")
        if estado_tendencia in ("ALCISTA_CONFIRMADA", "RECUPERACION") and score is not None and score > 0:
            args.append(f"Estructura técnica {estado_tendencia.lower().replace('_', ' ')} con "
                        f"puntuación de momentum {score:+.1f}/100 y RSI de {rsi:.1f} "
                        f"({rsi_estado.lower().replace('_', ' ')}).")
        elif score is not None and score > 20:
            args.append(f"Momentum favorable ({score:+.1f}/100), RSI {rsi:.1f} "
                        f"({rsi_estado.lower().replace('_', ' ')}).")

        if puntuaciones.get("solvencia") is not None and puntuaciones["solvencia"] >= 70:
            args.append(f"Solvencia {puntuaciones['solvencia']}/100: el balance aguanta un "
                        f"escenario adverso sin comprometer la tesis.")

        return args

    def _tesis_bajista(self, metrics: Dict[str, Any], tech: Dict[str, Any],
                       quality: Dict[str, Any], rec: Dict[str, Any],
                       sector: str) -> List[str]:
        """El abogado del diablo, con las mismas exigencias de evidencia."""
        args: List[str] = []
        contexto = (quality.get("contexto_sectorial") or {}).get("comparaciones", {})
        altman = quality.get("altman", {}) or {}
        devengos = quality.get("devengos", {}) or {}
        buffett = quality.get("buffett", {}) or {}
        lynch = quality.get("lynch", {}) or {}

        # El P/E se juzga CONTRA EL SECTOR, no contra un 30 universal. Decir
        # que 17x es caro en una minera de oro y barato en software con el
        # mismo umbral era lo que hacía la versión anterior.
        pe = metrics.get("pe_ratio")
        ref_pe = contexto.get("pe", {})
        if pe is not None and pe > 0 and ref_pe.get("ratio"):
            if ref_pe["ratio"] >= 1.5:
                args.append(f"P/E de {pe:.1f}x frente a una mediana sectorial de "
                            f"{ref_pe['referencia_sector']:.0f}x ({ref_pe['ratio']:.1f} veces la "
                            f"norma de {sector}): la valoración descuenta una ejecución impecable.")
            elif ref_pe["ratio"] >= 1.1:
                args.append(f"P/E de {pe:.1f}x, {ref_pe['lectura']} "
                            f"(mediana de {sector}: {ref_pe['referencia_sector']:.0f}x).")
        elif pe is not None and pe < 0:
            args.append(f"P/E negativo ({pe:.1f}x): la compañía no genera beneficio contable.")

        deuda = metrics.get("debt_to_equity")
        ref_de = contexto.get("deuda_patrimonio", {})
        if deuda is not None and deuda > 1.0:
            adjetivo = _calificar(deuda, [(4.0, "muy elevada"), (2.0, "elevada"), (1.0, "moderada")])
            comparativa = (f", {ref_de.get('lectura')} (mediana de {sector}: "
                           f"{ref_de.get('referencia_sector', 0):.1f}x)") if ref_de.get("ratio") else ""
            args.append(f"Carga financiera {adjetivo}: deuda/patrimonio de {deuda:.2f}x{comparativa}.")

        margen = metrics.get("net_margin")
        if margen is not None and margen < 0:
            args.append(f"Margen neto negativo ({margen:.1%}): cada venta adicional amplía la "
                        f"pérdida mientras no cambie la estructura de costes.")

        if altman.get("zona") == "DISTRESS":
            args.append(f"Altman {altman.get('variante')} en {altman.get('z')}, por debajo del "
                        f"umbral de insolvencia ({altman.get('umbral_distress')}).")
        elif altman.get("zona") == "GRIS":
            args.append(f"Altman {altman.get('variante')} en zona gris ({altman.get('z')}): "
                        f"solvencia sin margen cómodo.")

        if devengos.get("alerta"):
            args.append(f"Devengos del {devengos['ratio_devengos']:.1%} de los activos: el "
                        f"beneficio contable no está respaldado por caja operativa.")

        if buffett.get("dilucion_excesiva"):
            args.append(f"Dilución del {buffett['dilucion_anual']:.1%} anual: el accionista "
                        f"existente captura menos crecimiento del que muestra el agregado.")

        fcf = buffett.get("fcf_yield")
        if fcf is not None and fcf < 0:
            args.append("Flujo de caja libre negativo: el crecimiento se financia con capital "
                        "externo, no con el propio negocio.")

        peg = lynch.get("peg")
        if peg is not None and peg > 2.0:
            args.append(f"PEG de {peg}: el precio se ha adelantado al crecimiento esperado.")

        # --- técnico ------------------------------------------------------
        rsi = tech.get("rsi")
        if tech.get("rsi_estado") in ("SOBRECOMPRA_EXTREMA", "SOBRECOMPRA"):
            args.append(f"RSI en {rsi:.1f} ({tech['rsi_estado'].lower().replace('_', ' ')}): "
                        f"la entrada en este nivel asume riesgo de reversión a corto plazo.")
        if tech.get("estado_tendencia") in ("BAJISTA_CONFIRMADA", "DETERIORO"):
            args.append(f"Estructura técnica en {tech['estado_tendencia'].lower().replace('_', ' ')}: "
                        f"el precio cotiza por debajo de su media de 200 sesiones.")

        if rec.get("discrepancies"):
            args.append(f"{len(rec['discrepancies'])} discrepancia(s) entre proveedores de datos; "
                        f"confianza del {rec.get('confidence_score', 1.0):.0%}.")

        estilo = quality.get("style_classification")
        if estilo == "TRAMPA_DE_VALOR":
            args.append("El descuento sobre múltiplos convive con una calidad deteriorada: el "
                        "patrón típico de trampa de valor, no de oportunidad.")
        if quality.get("contexto_sectorial", {}).get("es_ciclico") and pe is not None and 0 < pe < 12:
            args.append("En un sector cíclico, un P/E bajo con beneficios en máximos suele señalar "
                        "techo de ciclo y no una ganga (la trampa del múltiplo bajo en cíclicas).")

        return args

    # ------------------------------------------------------------------ #
    @staticmethod
    def _sintesis(ticker: str, quality: Dict[str, Any], tech: Dict[str, Any],
                  alcistas: List[str], bajistas: List[str],
                  news_frase: Optional[str]) -> str:
        puntuaciones = quality.get("puntuaciones", {}) or {}
        estilo = quality.get("style_classification", "n/d")
        conviccion = (quality.get("conviccion_fundamental") or {}).get("valor")

        texto = (
            f"DEBATE ({ticker}) — estilo {estilo}, convicción fundamental "
            f"{conviccion if conviccion is not None else 'no evaluable'}/100 "
            f"(calidad {puntuaciones.get('calidad')}, valoración {puntuaciones.get('valoracion')}, "
            f"crecimiento {puntuaciones.get('crecimiento')}, solvencia {puntuaciones.get('solvencia')}). "
            f"{len(alcistas)} argumento(s) alcista(s) frente a {len(bajistas)} bajista(s). "
            f"{quality.get('style_rationale', '')}"
        )
        if news_frase:
            texto += f" Lectura del Analista de Noticias: {news_frase}"
        return texto

    @staticmethod
    def _condiciones_de_invalidacion(quality: Dict[str, Any], tech: Dict[str, Any],
                                     metrics: Dict[str, Any]) -> List[str]:
        """
        Qué tendría que ocurrir para que la tesis deje de sostenerse.

        Un memorando de inversión sin condiciones de invalidación no es una
        tesis, es una opinión. Se derivan de los mismos umbrales que
        produjeron la clasificación, así que son comprobables en el siguiente
        ciclo de análisis.
        """
        condiciones: List[str] = []
        estilo = quality.get("style_classification")
        buffett = quality.get("buffett", {}) or {}

        crec = metrics.get("revenue_growth")
        if crec is not None:
            condiciones.append(
                f"Que el crecimiento de ingresos caiga por debajo del "
                f"{max(0.0, crec * 0.5):.0%} en dos trimestres consecutivos.")
        margen = metrics.get("net_margin")
        if margen is not None and margen > 0:
            condiciones.append(f"Que el margen neto baje del {margen * 0.6:.1%}.")
        roic = buffett.get("roic")
        if roic is not None:
            condiciones.append(
                f"Que el ROIC caiga por debajo del coste de capital de referencia "
                f"({buffett.get('wacc_referencia'):.0%}).")
        if estilo in ("CRECIMIENTO", "GARP"):
            condiciones.append("Que el PEG supere 2.0 sin una revisión al alza del crecimiento.")
        if estilo in ("VALOR", "CALIDAD_COMPUESTA"):
            condiciones.append("Que aparezca deterioro en el F-Score de Piotroski o en el "
                               "ratio de devengos, señal de que el descuento estaba justificado.")
        stop = tech.get("sma_200")
        if stop:
            condiciones.append(f"Que el precio pierda la media de 200 sesiones (${stop}) "
                               f"con volumen creciente.")
        return condiciones
