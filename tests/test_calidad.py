"""
Analista de Calidad y Valoración: escuelas clásicas y etiqueta de estilo.

Cubre las reglas que decidieron incorporarse a la decisión —Piotroski, Altman,
Graham, Buffett, Lynch, Greenblatt, Sloan— y, sobre todo, la propiedad que
justifica que existan: que el sistema DISTINGA perfiles que antes recibían el
mismo dictamen.

Offline y determinista: el LLM se sustituye por `None`.
"""

import pytest

import src.agents.fund_manager as fm_mod
import src.agents.quality as quality_mod
from src.config import COBERTURA_MINIMA_ESTILO


@pytest.fixture(autouse=True)
def sin_llm(monkeypatch):
    monkeypatch.setattr(quality_mod, "get_llm", lambda: None)
    monkeypatch.setattr(fm_mod, "get_llm", lambda: None)


# --------------------------------------------------------------------------- #
# Constructores de estado
# --------------------------------------------------------------------------- #
def _serie(valor, factor=0.85, n=2):
    return [valor * (factor ** i) for i in range(n)]


def estados_financieros(*, activos=1.0e10, pasivos=4.0e9, patrimonio=6.0e9,
                        act_corr=3.0e9, pas_corr=1.2e9, retenidos=3.5e9,
                        deuda_lp=1.8e9, deuda=2.0e9, acciones=5.0e8, efectivo=1.0e9,
                        ingresos=5.0e9, bruto=2.75e9, ebit=1.25e9, neto=7.5e8,
                        intereses=8.0e7, impuestos=2.0e8, fco=9.0e8, capex=3.0e8,
                        factor=0.85):
    return {
        "disponible": True, "bloques_ok": ["balance", "resultados", "flujos"],
        "bloques_fallidos": [],
        "balance": {
            "activos_totales": _serie(activos, factor),
            "pasivos_totales": _serie(pasivos, factor),
            "patrimonio": _serie(patrimonio, factor),
            "activo_corriente": _serie(act_corr, factor),
            "pasivo_corriente": _serie(pas_corr, factor),
            "beneficios_retenidos": _serie(retenidos, factor),
            "deuda_largo_plazo": _serie(deuda_lp, factor),
            "deuda_total": _serie(deuda, factor),
            "acciones_emitidas": _serie(acciones, 1.005),
            "efectivo": _serie(efectivo, factor),
            "inmovilizado": _serie(activos * 0.3, factor),
            "fondo_comercio": [], "intangibles": [],
        },
        "resultados": {
            "ingresos": _serie(ingresos, factor), "beneficio_bruto": _serie(bruto, factor),
            "ebit": _serie(ebit, factor), "beneficio_neto": _serie(neto, factor),
            "gastos_financieros": _serie(intereses, factor),
            "impuestos": _serie(impuestos, factor),
            "beneficio_antes_impuestos": _serie(neto + impuestos, factor),
        },
        "flujos": {
            "flujo_operativo": _serie(fco, factor), "capex": _serie(-abs(capex), factor),
            "flujo_libre": _serie(fco - abs(capex), factor),
            "dividendos_pagados": [], "recompras": [],
        },
    }


def estado(sector="Technology", industria="Software", info=None, est=None,
           metricas=None, precio=100.0, confianza=1.0):
    info_base = {
        "revenue_growth": 0.20, "net_margin": 0.15, "gross_margin": 0.55,
        "operating_margin": 0.25, "roe": 0.30, "trailing_pe": 20.0, "pe_ratio": 20.0,
        "price_to_book": 3.0, "ev_to_ebitda": 12.0, "enterprise_value": 1.1e10,
        "market_cap": 1.0e10, "trailing_eps": 4.0, "book_value_per_share": 20.0,
        "current_ratio": 2.0, "earnings_growth": 0.22, "dividend_yield": 0.01,
        "free_cashflow": 6.0e8, "operating_cashflow": 9.0e8, "total_debt": 2.0e9,
        "debt_to_equity": 0.33,
    }
    info_base.update(info or {})
    met = {"revenue_growth": info_base["revenue_growth"],
           "net_margin": info_base["net_margin"],
           "debt_to_equity": info_base["debt_to_equity"],
           "roe": info_base["roe"], "pe_ratio": info_base["pe_ratio"]}
    met.update(metricas or {})
    return {
        "ticker": "T", "sector": sector, "industry": industria,
        "yfinance_data": {
            "fundamentals": info_base,
            "estados_financieros": est if est is not None else estados_financieros(),
            "technical": {"close": precio, "volatilidad_anual": 0.3, "atr": precio * 0.02},
            "price_history_summary": {"change_12m_pct": 0.2, "change_1m_pct": 0.01},
        },
        "sec_edgar_data": {"status": "NOT_USED"},
        "reconciliation_data": {"reconciled_metrics": met, "confidence_score": confianza,
                                "discrepancies": []},
    }


def analizar(**kw):
    return quality_mod.QualityAnalystAgent().analyze(estado(**kw))


# --------------------------------------------------------------------------- #
# 1. Piotroski
# --------------------------------------------------------------------------- #
def test_piotroski_solo_puntua_los_criterios_evaluables():
    """
    Un F-Score de 5/9 con siete criterios evaluables no es lo mismo que un 5/9
    completo. `score_normalizado` es la comparación honesta entre empresas con
    distinta cobertura.
    """
    completo = analizar()["piotroski"]
    assert completo["criterios_evaluables"] == 9
    assert 0 <= completo["score"] <= 9

    sin_flujos = estados_financieros()
    sin_flujos["flujos"] = {}
    parcial = analizar(est=sin_flujos)["piotroski"]
    assert parcial["criterios_evaluables"] < 9
    # Los criterios no evaluables se declaran, no se puntúan como suspenso.
    no_evaluables = [c for c in parcial["detalle"] if not c["evaluable"]]
    assert no_evaluables and all(c["cumple"] is None for c in no_evaluables)


def test_piotroski_detecta_la_mejora_interanual():
    """
    El F-Score mide VARIACIONES de ratios, no de magnitudes absolutas.

    Ojo al construir el escenario: escalar todas las partidas por el mismo
    factor deja los ratios idénticos entre ejercicios (ROA, margen bruto y
    rotación no se mueven) y el F-Score sale igual en los dos casos. Hay que
    mover el numerador y el denominador de forma distinta.
    """
    base = estados_financieros()

    def con_rentabilidad(neto_previo, bruto_previo, fco_previo, deuda_previa):
        e = estados_financieros()
        # El ejercicio actual se deja fijo y solo se altera el ANTERIOR: así la
        # comparación aísla la variación, que es lo que Piotroski puntúa.
        e["resultados"]["beneficio_neto"][1] = neto_previo
        e["resultados"]["beneficio_bruto"][1] = bruto_previo
        e["flujos"]["flujo_operativo"][1] = fco_previo
        e["balance"]["deuda_largo_plazo"][1] = deuda_previa
        return e

    # Mejora: el año anterior era peor en rentabilidad y peor en apalancamiento.
    mejora = analizar(est=con_rentabilidad(2.0e8, 1.5e9, 3.0e8, 3.0e9))["piotroski"]
    # Deterioro: el año anterior era mejor en todo.
    deterioro = analizar(est=con_rentabilidad(1.5e9, 4.0e9, 1.8e9, 5.0e8))["piotroski"]

    assert mejora["criterios_evaluables"] == deterioro["criterios_evaluables"] == 9
    assert mejora["score"] > deterioro["score"]


def test_sin_estados_financieros_piotroski_no_es_evaluable():
    vacio = {"disponible": False, "bloques_ok": [], "bloques_fallidos": [],
             "balance": {}, "resultados": {}, "flujos": {}}
    r = analizar(est=vacio)["piotroski"]
    assert r["score"] is None and r["lectura"] == "NO_EVALUABLE"


# --------------------------------------------------------------------------- #
# 2. Altman
# --------------------------------------------------------------------------- #
def test_altman_usa_la_variante_calibrada_para_el_sector():
    """
    Aplicar el Z de 1968 a una empresa de software da lecturas sistemáticamente
    pesimistas: la rotación de activos penaliza los modelos ligeros en capital.
    Altman calibró Z'' precisamente para eso.
    """
    software = analizar(sector="Technology")["altman"]
    industrial = analizar(sector="Industrials")["altman"]
    assert "Z''" in software["variante"]
    assert software["variante"] != industrial["variante"]
    assert "X5" not in software["componentes"]     # Z'' no usa rotación de activos
    assert "X5" in industrial["componentes"]


def test_altman_marca_insolvencia_con_balance_deteriorado():
    quebrada = estados_financieros(activos=1.6e9, pasivos=1.4e9, patrimonio=1.6e8,
                                   act_corr=4.0e8, pas_corr=3.6e8, retenidos=-6.0e8,
                                   ingresos=3.1e8, bruto=1.5e7, ebit=-1.4e8,
                                   neto=-1.5e8, fco=-1.2e8)
    r = analizar(sector="Utilities", est=quebrada,
                 info={"net_margin": -0.486, "debt_to_equity": 7.51, "roe": -1.78})
    assert r["altman"]["zona"] == "DISTRESS"
    assert any("insolvencia" in b for b in r["banderas_rojas"])


def test_el_veto_por_insolvencia_exige_corroboracion_de_caja():
    """
    Un Z'' bajo por patrimonio contable negativo NO es lo mismo que un riesgo
    de quiebra.

    Dos de los cuatro términos del Z'' —beneficios retenidos y fondos propios,
    ambos sobre activos— se vuelven muy negativos en compañías que han
    recomprado acciones por encima de su beneficio acumulado. Eso describe a
    buena parte del software rentable, que genera caja de sobra. Marcarlas
    ESPECULATIVAS por un ratio calibrado en 1968 sobre industriales sería un
    falso positivo sistemático de todo un sector.

    Caso real que lo motivó: DOCN, con Z''=0.04 por patrimonio neto negativo,
    flujo de caja libre holgadamente positivo y margen operativo del 25%.
    """
    # Déficit acumulado grande y patrimonio negativo por recompras, con
    # circulante ajustado: el Z'' se hunde por los términos contables. Pero el
    # negocio genera caja de sobra y cubre sus intereses 6 veces.
    comun = dict(patrimonio=-5.0e8, retenidos=-3.5e9, pasivos=3.5e9,
                 activos=3.0e9, act_corr=5.0e8, pas_corr=6.0e8)

    sano = analizar(est=estados_financieros(ebit=3.0e8, fco=6.0e8, capex=1.0e8,
                                            intereses=5.0e7, **comun),
                    info={"free_cashflow": 5.0e8, "operating_margin": 0.25})
    assert sano["altman"]["zona"] == "DISTRESS"
    assert sano["style_classification"] != "ESPECULATIVA"
    # Pero el hecho se declara, y con el matiz que lo hace interpretable.
    bandera = next(b for b in sano["banderas_rojas"] if "Altman" in b)
    assert "patrimonio contable negativo" in bandera

    # Mismo Z bajo, pero ahora el negocio consume caja: el veto sí aplica.
    enfermo = analizar(est=estados_financieros(ebit=-1.0e8, fco=-3.0e8, capex=2.0e8,
                                               intereses=2.0e8, **comun),
                       info={"free_cashflow": -5.0e8, "operating_margin": -0.05})
    assert enfermo["altman"]["zona"] == "DISTRESS"
    assert enfermo["style_classification"] == "ESPECULATIVA"
    assert "CORROBORADO" in enfermo["style_rationale"]


def test_patrimonio_negativo_se_declara_como_bandera():
    """
    Sin esta bandera, una empresa con fondos propios negativos pasaría sin
    dejar rastro: los ratios que lo llevan en el denominador se declaran
    ausentes precisamente para no propagar un −45x sin sentido económico.
    """
    r = analizar(est=estados_financieros(patrimonio=-5.0e8, retenidos=-2.0e9))
    assert any("Patrimonio neto negativo" in b for b in r["banderas_rojas"])


def test_altman_declara_los_componentes_que_faltan():
    sin_balance = estados_financieros()
    sin_balance["balance"]["beneficios_retenidos"] = []
    r = analizar(est=sin_balance)["altman"]
    assert r["zona"] == "NO_EVALUABLE"
    assert "X2" in r["componentes_ausentes"]


# --------------------------------------------------------------------------- #
# 3. Graham
# --------------------------------------------------------------------------- #
def test_numero_de_graham_no_se_calcula_con_beneficio_negativo():
    """
    Con BPA negativo no se devuelve un número imaginario ni un cero: una
    empresa en pérdidas está fuera del universo que Graham describía.
    """
    r = analizar(info={"trailing_eps": -1.15})["graham"]
    assert r["numero_graham"] is None
    assert "NO_APLICABLE" in r["estado_numero"]


def test_margen_de_seguridad_es_la_distancia_al_valor_conservador():
    barata = analizar(info={"trailing_eps": 8.0, "book_value_per_share": 40.0},
                      precio=50.0)["graham"]
    cara = analizar(info={"trailing_eps": 8.0, "book_value_per_share": 40.0},
                    precio=400.0)["graham"]
    assert barata["margen_seguridad"] > 0 > cara["margen_seguridad"]
    assert barata["cumple_margen"] is True


# --------------------------------------------------------------------------- #
# 4. Buffett, Lynch, Sloan
# --------------------------------------------------------------------------- #
def test_roic_se_compara_contra_el_coste_del_capital():
    r = analizar()["buffett"]
    assert r["roic"] is not None
    assert r["roic_menos_wacc"] == pytest.approx(r["roic"] - r["wacc_referencia"], abs=1e-4)
    assert r["crea_valor"] is (r["roic"] > r["wacc_referencia"])


def test_peg_declara_sobre_que_crecimiento_se_calcula():
    """
    Presentar el PEG sobre ingresos como si fuera sobre beneficio produce
    lecturas engañosamente bajas en empresas que crecen en ventas sin ganar
    dinero.
    """
    con_bpa = analizar(info={"earnings_growth": 0.25})["lynch"]
    sin_bpa = analizar(info={"earnings_growth": None})["lynch"]
    assert con_bpa["base_del_crecimiento"] == "beneficio"
    assert sin_bpa["base_del_crecimiento"] == "ingresos"


def test_devengos_detectan_beneficio_sin_caja():
    """Sloan: el beneficio que no es caja revierte."""
    con_caja = analizar(est=estados_financieros(neto=7.5e8, fco=1.5e9))["devengos"]
    sin_caja = analizar(est=estados_financieros(neto=2.0e9, fco=1.0e8))["devengos"]
    assert con_caja["alerta"] is False
    assert sin_caja["alerta"] is True
    assert sin_caja["ratio_devengos"] > con_caja["ratio_devengos"]


def test_dilucion_se_mide_y_se_reporta():
    """Un ROE alto financiado emitiendo acciones no llega al accionista existente."""
    r = analizar()["buffett"]
    assert r["dilucion_anual"] is not None


# --------------------------------------------------------------------------- #
# 5. Contexto sectorial
# --------------------------------------------------------------------------- #
def test_el_pe_se_juzga_contra_la_norma_del_sector():
    """
    17x es caro en una minera y barato en software. «P/E elevado» sin punto de
    referencia era una afirmación vacía.
    """
    mismo_pe = {"pe_ratio": 17.0, "trailing_pe": 17.0}
    minera = analizar(sector="Basic Materials", info=mismo_pe,
                      metricas={"pe_ratio": 17.0})["contexto_sectorial"]
    software = analizar(sector="Technology", info=mismo_pe,
                        metricas={"pe_ratio": 17.0})["contexto_sectorial"]

    assert minera["comparaciones"]["pe"]["ratio"] > software["comparaciones"]["pe"]["ratio"]
    assert minera["es_ciclico"] is True and software["es_ciclico"] is False


# --------------------------------------------------------------------------- #
# 6. Clasificación de estilo — la propiedad central
# --------------------------------------------------------------------------- #
def test_barato_sin_calidad_es_trampa_de_valor_no_valor():
    """
    La distinción crítica de la escuela de Graham: barato con calidad es valor;
    barato sin calidad es, la mayoría de las veces, barato por un motivo.
    """
    mala_calidad = estados_financieros(bruto=1.0e8, ebit=5.0e7, neto=3.0e7,
                                       fco=1.0e7, ingresos=5.0e9)
    r = analizar(est=mala_calidad,
                 info={"pe_ratio": 5.0, "trailing_pe": 5.0, "price_to_book": 0.5,
                       "ev_to_ebitda": 3.0, "gross_margin": 0.02,
                       "operating_margin": 0.01, "net_margin": 0.006, "roe": 0.02,
                       "trailing_eps": 0.5, "earnings_growth": -0.20},
                 metricas={"pe_ratio": 5.0, "net_margin": 0.006, "roe": 0.02,
                           "revenue_growth": -0.05})
    assert r["style_classification"] in ("TRAMPA_DE_VALOR", "ESPECULATIVA")


def test_solvencia_comprometida_manda_sobre_cualquier_lectura():
    quebrada = estados_financieros(activos=1.6e9, pasivos=1.5e9, patrimonio=1.0e8,
                                   act_corr=3.0e8, pas_corr=4.0e8, retenidos=-8.0e8,
                                   ingresos=3.0e8, bruto=1.0e7, ebit=-1.5e8,
                                   neto=-1.6e8, fco=-1.3e8, deuda=1.2e9, deuda_lp=1.0e9)
    r = analizar(sector="Utilities", est=quebrada,
                 info={"net_margin": -0.5, "debt_to_equity": 7.5, "roe": -1.6,
                       "pe_ratio": -20.0, "trailing_eps": -1.2, "current_ratio": 0.75},
                 metricas={"net_margin": -0.5, "debt_to_equity": 7.5, "roe": -1.6,
                           "pe_ratio": -20.0})
    assert r["style_classification"] == "ESPECULATIVA"
    assert len(r["banderas_rojas"]) >= 3


def test_cobertura_insuficiente_no_produce_etiqueta_inventada():
    """
    Una etiqueta de estilo apoyada en dos de doce métricas es peor que ninguna
    etiqueta.
    """
    vacio = {"disponible": False, "bloques_ok": [], "bloques_fallidos": [],
             "balance": {}, "resultados": {}, "flujos": {}}
    r = quality_mod.QualityAnalystAgent().analyze({
        "ticker": "X", "sector": "Technology", "industry": "Software",
        "yfinance_data": {"fundamentals": {}, "estados_financieros": vacio,
                          "technical": {"close": 10.0}, "price_history_summary": {}},
        "sec_edgar_data": {}, "reconciliation_data": {"reconciled_metrics": {},
                                                      "confidence_score": 0.5},
    })
    assert r["status"] == "DATOS_INSUFICIENTES"
    assert r["style_classification"] == "DATOS_INSUFICIENTES"
    assert r["cobertura_global"] < COBERTURA_MINIMA_ESTILO


def test_perfiles_distintos_reciben_convicciones_distintas():
    """
    LA propiedad que motivó todo el módulo.

    En el informe del 2026-08-21, GOOGL (P/E 17, margen 55%, deuda 19%) y BE
    (P/E 270, margen 8%, deuda 172%) recibieron el MISMO dictamen y el MISMO
    tamaño de posición. Eso ya no puede ocurrir.
    """
    excelente = analizar(
        est=estados_financieros(bruto=3.2e9, ebit=1.9e9, neto=1.4e9, fco=2.1e9),
        info={"pe_ratio": 17.3, "trailing_pe": 17.3, "gross_margin": 0.58,
              "operating_margin": 0.34, "net_margin": 0.55, "roe": 0.49,
              "price_to_book": 6.1, "debt_to_equity": 0.19},
        metricas={"pe_ratio": 17.3, "net_margin": 0.55, "roe": 0.49,
                  "debt_to_equity": 0.19, "revenue_growth": 0.24})
    caro = analizar(
        sector="Industrials",
        est=estados_financieros(bruto=6.2e8, ebit=1.3e8, neto=1.7e8, fco=1.0e8,
                                deuda=1.6e9, deuda_lp=1.3e9, patrimonio=1.9e9),
        info={"pe_ratio": 270.0, "trailing_pe": 270.0, "gross_margin": 0.28,
              "operating_margin": 0.06, "net_margin": 0.079, "roe": 0.22,
              "price_to_book": 22.0, "debt_to_equity": 1.72, "trailing_eps": 0.75,
              "ev_to_ebitda": 140.0},
        metricas={"pe_ratio": 270.0, "net_margin": 0.079, "roe": 0.22,
                  "debt_to_equity": 1.72, "revenue_growth": 1.65})

    conv_exc = excelente["conviccion_fundamental"]["valor"]
    conv_caro = caro["conviccion_fundamental"]["valor"]
    assert conv_exc > conv_caro + 15, (
        f"Perfiles muy distintos deberían separarse: {conv_exc} vs {conv_caro}")
    assert excelente["puntuaciones"]["valoracion"] > caro["puntuaciones"]["valoracion"]


# --------------------------------------------------------------------------- #
# 7. Convicción y degradación por datos
# --------------------------------------------------------------------------- #
def test_menos_confianza_en_los_datos_es_menos_conviccion():
    """La traducción operativa de «no sé, luego arriesgo menos»."""
    alta = analizar(confianza=1.0)["conviccion_fundamental"]["valor"]
    baja = analizar(confianza=0.6)["conviccion_fundamental"]["valor"]
    assert baja < alta


def test_las_banderas_rojas_descuentan_conviccion():
    limpia = analizar()
    con_devengos = analizar(est=estados_financieros(neto=2.5e9, fco=1.0e8))
    assert len(con_devengos["banderas_rojas"]) > len(limpia["banderas_rojas"])
    assert con_devengos["conviccion_fundamental"]["descuento_banderas"] > 0


def test_una_bandera_roja_exige_que_el_dato_exista():
    """Un dato ausente no es una bandera roja: se refleja en la cobertura."""
    sin_flujos = estados_financieros()
    sin_flujos["flujos"] = {}
    r = analizar(est=sin_flujos, info={"free_cashflow": None, "operating_cashflow": None})
    assert not any("flujo de caja libre negativo" in b.lower() for b in r["banderas_rojas"])


# --------------------------------------------------------------------------- #
# 8. Integración con el Fund Manager
# --------------------------------------------------------------------------- #
def test_estilo_especulativo_limita_el_dictamen():
    """Ninguna condición puede MEJORAR un rating; los vetos solo bajan."""
    st = estado()
    st["quality_report"] = {
        "style_classification": "ESPECULATIVA",
        "conviccion_fundamental": {"valor": 95.0},
        "banderas_rojas": [],
    }
    st["technical_report"] = {"momentum_classification": "ALCISTA_FUERTE",
                              "momentum_score": 80.0, "volatilidad_anual": 0.3,
                              "sobreextendido": False, "rsi": 60.0}
    st["passed_fundamental_gatekeeper"] = True
    st["fundamental_report"] = {"status": "APROBADO", "metrics": {}}

    fd = fm_mod.FundManagerAgent().analyze(st)
    assert fd["rating"] == "MANTENER"
    assert fd["peso_objetivo"] == 0.0
    assert any("ESPECULATIVA" in v for v in fd["vetos_aplicados"])


def test_sobreextension_recorta_la_compra_fuerte():
    st = estado()
    st["quality_report"] = {"style_classification": "CALIDAD_COMPUESTA",
                            "conviccion_fundamental": {"valor": 85.0},
                            "banderas_rojas": []}
    st["technical_report"] = {"momentum_classification": "ALCISTA_FUERTE",
                              "momentum_score": 60.0, "volatilidad_anual": 0.3,
                              "sobreextendido": True, "rsi": 84.0}
    st["passed_fundamental_gatekeeper"] = True
    st["fundamental_report"] = {"status": "APROBADO", "metrics": {}}

    fd = fm_mod.FundManagerAgent().analyze(st)
    assert fd["rating"] == "COMPRA"
    assert any("sobreextendido" in v for v in fd["vetos_aplicados"])
    assert fd["dimensionado"]["factores"]["factor_sobreextension"] < 1.0


def test_gatekeeper_sin_datos_produce_sin_opinion_no_venta():
    """
    Emitir VENTA contra una empresa de la que no se sabe nada es afirmar algo
    que ninguna fuente respalda.
    """
    st = estado()
    st["passed_fundamental_gatekeeper"] = False
    st["fundamental_report"] = {"status": "DATOS_INSUFICIENTES", "metrics": {},
                                "summary": "no evaluable"}
    fd = fm_mod.FundManagerAgent().analyze(st)
    assert fd["rating"] == "SIN OPINION"
    assert fd["peso_objetivo"] == 0.0


def test_el_tamano_es_un_numero_y_escala_con_la_volatilidad():
    """
    El tamaño era una CADENA literal idéntica para todos («2.0% - 3.0%»), así
    que no se podía sumar, ni escalar por volatilidad, ni presupuestar.
    """
    def decidir(volatilidad):
        st = estado()
        st["quality_report"] = {"style_classification": "CALIDAD_COMPUESTA",
                                "conviccion_fundamental": {"valor": 80.0},
                                "banderas_rojas": []}
        st["technical_report"] = {"momentum_classification": "ALCISTA",
                                  "momentum_score": 40.0,
                                  "volatilidad_anual": volatilidad,
                                  "sobreextendido": False, "rsi": 60.0}
        st["passed_fundamental_gatekeeper"] = True
        st["fundamental_report"] = {"status": "APROBADO", "metrics": {}}
        return fm_mod.FundManagerAgent().analyze(st)

    tranquila = decidir(0.20)
    volatil = decidir(0.90)

    assert isinstance(tranquila["peso_objetivo"], float)
    assert isinstance(tranquila["position_size_pct"], (int, float))
    assert volatil["peso_objetivo"] < tranquila["peso_objetivo"]


def test_el_horizonte_y_el_ratio_riesgo_recompensa_se_declaran():
    """
    Un R:R sin la tasa de acierto que exige y sin el plazo en que se espera es
    ininterpretable — la carencia que señalaba la revisión.
    """
    st = estado()
    st["quality_report"] = {"style_classification": "VALOR",
                            "conviccion_fundamental": {"valor": 70.0},
                            "banderas_rojas": []}
    st["technical_report"] = {"momentum_classification": "ALCISTA",
                              "momentum_score": 35.0, "volatilidad_anual": 0.25,
                              "sobreextendido": False, "rsi": 58.0}
    st["passed_fundamental_gatekeeper"] = True
    st["fundamental_report"] = {"status": "APROBADO", "metrics": {}}

    riesgo = fm_mod.FundManagerAgent().analyze(st)["perfil_riesgo"]
    assert riesgo["ratio_riesgo_recompensa"] > 0
    assert 0 < riesgo["tasa_acierto_equilibrio"] < 1
    assert riesgo["horizonte_dias"] > 0
    assert riesgo["tasa_acierto_equilibrio"] == pytest.approx(
        1.0 / (1.0 + riesgo["ratio_riesgo_recompensa"]), abs=1e-4)
