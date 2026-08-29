"""
Reconciliación multi-proveedor con procedencia explícita.

QUÉ HACÍA MAL LA VERSIÓN ANTERIOR
---------------------------------
Se llamaba «reconciliador», pero `reconciled_metrics` copiaba las cinco
magnitudes de yfinance sin excepción. SEC EDGAR y Finnhub solo servían para
encender una luz de aviso; jamás corregían ni completaban un número. Era
yfinance con un semáforo, no una reconciliación.

Y el `confidence_score` solo bajaba cuando dos fuentes que SÍ habían respondido
discrepaban. Si la SEC fallaba y Finnhub no estaba configurado, el resultado era
`status="SINGLE_VENDOR_FALLBACK"` con `confidence_score=1.0`: el estado decía
«una sola fuente» y la puntuación decía «confianza total». El gatekeeper solo
avisa por debajo de 0.5, así que ese aviso era inalcanzable.

QUÉ HACE AHORA
--------------
1. Construye cada magnitud desde TODAS las fuentes que la aportan y elige por
   jerarquía declarada, dejando constancia del origen en `procedencia`.
2. Completa huecos: si yfinance no trae el margen pero la SEC sí, el margen se
   deriva de la SEC en vez de quedarse en `None` — que es lo que significa
   reconciliar.
3. Penaliza la AUSENCIA de fuentes y la cobertura incompleta, no solo el
   desacuerdo. Menos información es menos confianza, siempre.
4. Mide la discrepancia de forma continua (desviación relativa), no con un
   umbral binario que trataba igual un 16% de diferencia que un 300%.
"""

from typing import Any, Dict, List, Optional

from src.data.magnitudes import (
    Cobertura,
    Magnitud,
    division,
    magnitud,
    primera_disponible,
    suma,
)

# Confianza mínima. Se conserva el suelo de 0.4 de la versión anterior: por
# debajo de eso la señal ya no es utilizable y el número exacto no aporta.
CONFIANZA_MINIMA = 0.4

# Penalizaciones por fuente que no responde. La SEC pesa más que Finnhub porque
# es la fuente auditada y la única con fecha de publicación fiable.
PENALIZACION_SIN_SEC = 0.15
PENALIZACION_SIN_FINNHUB = 0.05
# Peso de la cobertura de campos sobre la confianza final.
PESO_COBERTURA = 0.30

# Magnitudes centrales: las que consume el gatekeeper. La cobertura se mide
# sobre estas, no sobre el catálogo completo, para que añadir un campo nuevo y
# opcional no degrade artificialmente la confianza de todos los tickers.
MAGNITUDES_CENTRALES = ("revenue_growth", "net_margin", "debt_to_equity", "roe", "pe_ratio")


class DataReconciler:
    """Cruza SEC EDGAR, Finnhub y yfinance y publica un estado único auditable."""

    def reconcile(self, ticker: str, yf_data: Dict[str, Any], sec_data: Dict[str, Any],
                  finnhub_data: Dict[str, Any]) -> Dict[str, Any]:
        yf_fund = yf_data.get("fundamentals", {}) or {}
        sec_ok = sec_data.get("status") == "SUCCESS"
        fh_ok = finnhub_data.get("status") == "SUCCESS"

        sources_used = ["yfinance"]
        if sec_ok:
            sources_used.append("SEC EDGAR (Oficial)")
        if fh_ok:
            sources_used.append("Finnhub")

        candidatas = self._candidatas(yf_fund, sec_data, finnhub_data, sec_ok, fh_ok)
        elegidas, procedencia = self._elegir(candidatas)

        discrepancias, penalizacion_discrepancia = self._discrepancias(candidatas)
        cobertura = Cobertura()
        for nombre in MAGNITUDES_CENTRALES:
            cobertura.registrar(nombre, elegidas.get(nombre, Magnitud(None)))

        confianza = self._confianza(sec_ok, fh_ok, cobertura, penalizacion_discrepancia)

        # `reconciled_metrics` mantiene el contrato de siempre —claves planas—
        # pero un campo desconocido vale None, nunca 0.0. Quien lo consuma debe
        # decidir explícitamente qué hacer con la ausencia.
        reconciled_metrics = {k: (m.valor if m.disponible else None)
                              for k, m in elegidas.items()}

        status = "HIGH_CONFIDENCE"
        if len(sources_used) == 1:
            status = "SINGLE_VENDOR_FALLBACK"
        elif discrepancias:
            status = "RECONCILED_WITH_DISCREPANCIES"
        if cobertura.ratio < 0.6:
            status = "COBERTURA_INSUFICIENTE"

        return {
            "status": status,
            "ticker": ticker.upper(),
            "confidence_score": confianza,
            "sources_consulted": sources_used,
            "sources_failed": self._fuentes_fallidas(sec_data, finnhub_data, sec_ok, fh_ok),
            "discrepancies": discrepancias,
            "reconciled_metrics": reconciled_metrics,
            "procedencia": procedencia,
            "cobertura": cobertura.a_dict(),
            "campos_ausentes_yfinance": yf_data.get("campos_ausentes", []),
        }

    # ------------------------------------------------------------------ #
    # Construcción de candidatas por fuente
    # ------------------------------------------------------------------ #
    def _candidatas(self, yf_fund: Dict[str, Any], sec_data: Dict[str, Any],
                    fh_data: Dict[str, Any], sec_ok: bool,
                    fh_ok: bool) -> Dict[str, List[Magnitud]]:
        """
        Para cada magnitud, la lista de valores que aporta cada fuente, EN ORDEN
        DE PREFERENCIA.

        La jerarquía no es la misma para todas las magnitudes y esa es la parte
        que importa:

          · Márgenes y crecimiento → primero yfinance, porque su `info` es TTM y
            recoge los últimos cuatro trimestres; la SEC anual va por detrás del
            ciclo. La SEC entra como respaldo cuando yfinance no trae el dato.
          · Balance (deuda, patrimonio) → primero la SEC: es la cifra auditada.
          · P/E y capitalización → solo yfinance; dependen del precio de mercado
            y la SEC no publica precios.
        """
        def yf(clave: str, unidad: str = "ratio") -> Magnitud:
            return magnitud(yf_fund.get(clave), fuente="yfinance", unidad=unidad,
                            periodo="TTM")

        def sec(clave: str, unidad: str = "usd") -> Magnitud:
            if not sec_ok:
                return Magnitud(None, fuente="SEC EDGAR")
            serie = (sec_data.get("series") or {}).get(clave) or []
            periodo = serie[0].get("end") if serie else None
            filed = serie[0].get("filed") if serie else None
            return magnitud(sec_data.get(clave), fuente="SEC EDGAR (Oficial)",
                            unidad=unidad, periodo=periodo, filed=filed)

        def fh(clave: str, escala: float = 1.0, unidad: str = "ratio") -> Magnitud:
            if not fh_ok:
                return Magnitud(None, fuente="Finnhub")
            v = fh_data.get(clave)
            m = magnitud(v, fuente="Finnhub", unidad=unidad, periodo="TTM")
            if m.disponible and escala != 1.0:
                return Magnitud(m.valor * escala, fuente="Finnhub", unidad=unidad,
                                periodo="TTM")
            return m

        # Magnitudes derivadas de la SEC ---------------------------------
        sec_ingresos = sec("revenues")
        sec_beneficio = sec("net_income")
        sec_patrimonio = sec("stockholders_equity")
        sec_margen = division(sec_beneficio, sec_ingresos,
                              fuente="SEC EDGAR (derivado)", unidad="ratio")

        # Con patrimonio neto NEGATIVO —habitual tras años de recompras— los
        # ratios que lo llevan en el denominador dejan de significar lo que su
        # nombre dice. Un deuda/patrimonio de −45x no es «poco apalancada»: es
        # una división sin sentido económico, y dejarla pasar hacía que el
        # gatekeeper la aprobara por ser «menor que 3.0». Se declara ausente y
        # el Analista de Calidad levanta la bandera correspondiente.
        patrimonio_valido = (sec_patrimonio if (sec_patrimonio.disponible
                                                and float(sec_patrimonio.valor) > 0)
                             else Magnitud(None, fuente="SEC EDGAR (derivado)",
                                           nota="patrimonio neto no positivo"))
        sec_roe = division(sec_beneficio, patrimonio_valido,
                           fuente="SEC EDGAR (derivado)", unidad="ratio")
        # `exigir_todas=False`: una empresa sin deuda a corto no reporta el
        # concepto, y ahí la ausencia sí significa cero.
        sec_deuda = suma(sec("short_term_debt"), sec("long_term_debt"),
                         fuente="SEC EDGAR (derivado)", exigir_todas=False)
        sec_de = division(sec_deuda, patrimonio_valido,
                          fuente="SEC EDGAR (derivado)", unidad="veces")
        sec_crecimiento = self._crecimiento_desde_serie(sec_data, "revenues") if sec_ok \
            else Magnitud(None, fuente="SEC EDGAR")

        return {
            "revenue_growth": [yf("revenue_growth", "pct"),
                               fh("revenue_growth_5y", 0.01, "pct"),
                               sec_crecimiento],
            "net_margin": [yf("net_margin", "pct"),
                           fh("net_margin_ttm", 0.01, "pct"),
                           sec_margen],
            # yfinance PRIMERO en deuda/patrimonio, al contrario que en el
            # resto del balance. El motivo no es la calidad del dato sino la
            # DEFINICIÓN: `MAX_DEBT_TO_EQUITY` y sus excepciones sectoriales se
            # calibraron contra `debtToEquity` de yfinance, que incluye
            # arrendamientos y otras obligaciones que la suma de conceptos XBRL
            # de deuda financiera no recoge. Anteponer la cifra de la SEC
            # cambiaba en silencio dónde cae el umbral —se observaron
            # divergencias de 1.72x a 3.41x en el mismo valor— y eso vuelca
            # veredictos del gatekeeper sin que nadie haya tocado el umbral.
            # La SEC entra como respaldo y como contraste de discrepancia.
            "debt_to_equity": [yf("debt_to_equity", "veces"), sec_de],
            "roe": [yf("roe", "pct"), fh("roe_ttm", 0.01, "pct"), sec_roe],
            "pe_ratio": [yf("pe_ratio", "veces"), fh("pe_ratio", 1.0, "veces")],
        }

    @staticmethod
    def _crecimiento_desde_serie(sec_data: Dict[str, Any], clave: str) -> Magnitud:
        """Crecimiento interanual de ingresos a partir de los dos últimos 10-K."""
        serie = (sec_data.get("series") or {}).get(clave) or []
        if len(serie) < 2:
            return Magnitud(None, fuente="SEC EDGAR (derivado)",
                            nota="serie anual insuficiente")
        actual, anterior = serie[0], serie[1]
        if not anterior.get("val"):
            return Magnitud(None, fuente="SEC EDGAR (derivado)", nota="base nula")
        return Magnitud(actual["val"] / anterior["val"] - 1.0,
                        fuente="SEC EDGAR (derivado)", unidad="pct",
                        periodo=actual.get("end"), filed=actual.get("filed"))

    @staticmethod
    def _elegir(candidatas: Dict[str, List[Magnitud]]):
        elegidas: Dict[str, Magnitud] = {}
        procedencia: Dict[str, Any] = {}
        for nombre, opciones in candidatas.items():
            m = primera_disponible(*opciones)
            elegidas[nombre] = m
            procedencia[nombre] = {
                "fuente_elegida": m.fuente if m.disponible else None,
                "periodo": m.periodo,
                "filed": m.filed,
                "fuentes_con_dato": [o.fuente for o in opciones if o.disponible],
            }
        return elegidas, procedencia

    # ------------------------------------------------------------------ #
    # Desacuerdo entre fuentes
    # ------------------------------------------------------------------ #
    @staticmethod
    def _discrepancias(candidatas: Dict[str, List[Magnitud]]):
        """
        Desviación relativa entre las fuentes que sí aportaron cada magnitud.

        Continua, no binaria: la versión anterior aplicaba la misma penalización
        a una diferencia del 16% que a una del 300%. Se normaliza por el mayor
        valor absoluto para que magnitudes cercanas a cero no exploten.
        """
        detalles: List[Dict[str, Any]] = []
        penalizacion = 0.0

        for nombre, opciones in candidatas.items():
            con_dato = [o for o in opciones if o.disponible]
            if len(con_dato) < 2:
                continue
            valores = [float(o.valor) for o in con_dato]
            escala = max(abs(v) for v in valores)
            if escala < 1e-9:
                continue
            dispersion = (max(valores) - min(valores)) / escala
            if dispersion <= 0.15:
                continue
            detalles.append({
                "magnitud": nombre,
                "dispersion_relativa": round(dispersion, 3),
                "valores": {o.fuente: round(float(o.valor), 6) for o in con_dato},
                "texto": (f"{nombre}: dispersión del {dispersion:.0%} entre "
                          + " vs ".join(f"{o.fuente} ({float(o.valor):.4g})" for o in con_dato)),
            })
            # Tope por magnitud: una sola discrepancia no debe hundir la
            # confianza entera, pero varias sí deben acumularse.
            penalizacion += min(0.12, 0.06 * dispersion)

        return detalles, min(0.35, penalizacion)

    @staticmethod
    def _confianza(sec_ok: bool, fh_ok: bool, cobertura: Cobertura,
                   penalizacion_discrepancia: float) -> float:
        """
        Confianza en [0.4, 1.0].

        Tres sumandos, todos en la misma dirección: menos fuentes, menos campos
        o más desacuerdo bajan la puntuación. La versión anterior solo
        contemplaba el tercero.
        """
        score = 1.0
        if not sec_ok:
            score -= PENALIZACION_SIN_SEC
        if not fh_ok:
            score -= PENALIZACION_SIN_FINNHUB
        score -= PESO_COBERTURA * (1.0 - cobertura.ratio)
        score -= penalizacion_discrepancia
        return max(CONFIANZA_MINIMA, round(score, 3))

    @staticmethod
    def _fuentes_fallidas(sec_data: Dict[str, Any], fh_data: Dict[str, Any],
                          sec_ok: bool, fh_ok: bool) -> List[Dict[str, str]]:
        fallidas = []
        if not sec_ok:
            fallidas.append({"fuente": "SEC EDGAR",
                             "motivo": str(sec_data.get("status", "sin respuesta"))})
        if not fh_ok:
            fallidas.append({"fuente": "Finnhub",
                             "motivo": str(fh_data.get("status", "no configurado"))})
        return fallidas
