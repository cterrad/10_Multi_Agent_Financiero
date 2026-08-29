"""
Tests del Analista de Noticias.

Todos son deterministas y offline: los ítems son sintéticos, con fecha,
categoría y tipo de fuente fijos, y `as_of` es una constante. Nada aquí toca la
red ni depende del día en que se ejecute.

Los dos que de verdad importan son `test_llm_no_altera_el_dictamen_de_noticias`
y `test_news_report_does_not_alter_decision`: el primero protege la invariante
del proyecto (ninguna variable de decisión depende del LLM) y el segundo protege
la premisa que permite excluir las noticias del backtest (son una capa asesora,
no un input de decisión). Si el segundo falla, el backtest ha dejado de medir la
lógica de producción — ver el encabezado de `src/backtest/replay.py`.
"""

import copy

import pytest

import src.agents.news as news_mod
from src.agents.fund_manager import FundManagerAgent
from src.agents.news import (
    NewsAnalystAgent, agregar_probabilidad, clasificar_categoria, clasificar_impacto,
    decaimiento, dias_de_antiguedad, direccion_agregada, factor_corroboracion,
    inferir_direccion_item, puntuar_item,
)
from src.backtest.replay import assert_llm_is_decision_neutral, disable_llm
from src.config import (
    NEWS_HIGH_IMPACT_THRESHOLD, NEWS_ITEM_PROB_MAX, NEWS_MAX_CORROBORATION_FACTOR,
    NEWS_MEDIUM_IMPACT_THRESHOLD, NEWS_TOP_K_ITEMS,
)
from src.data.news.aggregator import deduplicar
from src.data.news.schema import clasificar_tipo_fuente, fecha_iso, normalizar_item

disable_llm()

HOY = "2024-03-15"


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def item(titulo, fecha="2024-03-14", tipo="MEDIO_TIER1", url=None, extracto="",
         corroboraciones=1, buscador="google_news_rss", forzada=None):
    """Ítem ya agregado, con la forma que produce `deduplicar()`."""
    datos = {
        "titulo": titulo,
        "url": url if url is not None else f"https://ejemplo.com/{abs(hash(titulo)) % 10**8}",
        "fuente": "Fuente de prueba",
        "fecha": fecha,
        "extracto": extracto,
        "tipo_fuente": tipo,
        "buscadores": [buscador],
        "n_corroboraciones": corroboraciones,
    }
    if forzada:
        datos["categoria_forzada"] = forzada
    return datos


def estado(items, **extra):
    base = {
        "ticker": "TEST",
        "company_name": "Test Corp",
        "news_data": {
            "status": "SUCCESS", "ticker": "TEST", "empresa": "Test Corp",
            "as_of": HOY, "ventana_dias": 30, "items": items,
            "fuentes_ok": ["sec_8k", "google_news_rss"], "fuentes_fallidas": [],
            "desde_cache": False, "n_brutos": len(items), "n_items": len(items),
        },
    }
    base.update(extra)
    return base


# --------------------------------------------------------------------------- #
# 1. Neutralidad del LLM — la invariante del proyecto
# --------------------------------------------------------------------------- #
def test_llm_no_altera_el_dictamen_de_noticias():
    """
    Con y sin LLM falso, el agente debe producir el MISMO score, categoría y
    dirección. Solo `summary` puede cambiar.
    """
    class _FakeLLM:
        def invoke(self, prompt):  # noqa: ARG002
            class _R:
                content = "TEXTO_FALSO_DE_VERIFICACION"
            return _R()

    s = estado([
        item("Test Corp presenta el formulario 8-K (Item 2.02: Results of Operations)",
             tipo="SEC_8K", forzada="RESULTADOS"),
        item("Test Corp beats estimates and raises full-year guidance",
             fecha="2024-03-13", corroboraciones=2),
        item("Test Corp faces SEC investigation over accounting", fecha="2024-03-01"),
    ])

    original = news_mod.get_llm
    try:
        news_mod.get_llm = lambda: None
        sin_llm = NewsAnalystAgent().analyze(copy.deepcopy(s))
        news_mod.get_llm = lambda: _FakeLLM()
        con_llm = NewsAnalystAgent().analyze(copy.deepcopy(s))
    finally:
        news_mod.get_llm = original

    decisorios = ("impact_probability", "impact_classification", "direction_classification",
                  "direction_imbalance", "catalysts", "scored_items", "n_items",
                  "category_counts")
    for clave in decisorios:
        assert sin_llm[clave] == con_llm[clave], f"El LLM alteró `{clave}`"

    # Y el LLM sí ha actuado: si no, el test no probaría nada.
    assert con_llm["summary"] == "TEXTO_FALSO_DE_VERIFICACION"
    assert sin_llm["summary"] != con_llm["summary"]


def test_assert_llm_is_decision_neutral_cubre_noticias():
    """La verificación que ejecuta `backtest_cli.py` incluye las claves de noticias."""
    res = assert_llm_is_decision_neutral()
    assert res["neutral"], f"El LLM altera decisiones: {res['divergences']}"
    for clave in ("news_impact_probability", "news_impact_classification",
                  "news_direction_classification", "news_catalysts"):
        assert clave in res["heuristic"]


def test_news_report_does_not_alter_decision():
    """
    Premisa que permite excluir el nodo de noticias del backtest: el Fund
    Manager produce el MISMO dictamen con y sin `news_report` en el estado.

    Si este test falla, las noticias han pasado de capa asesora a input de
    decisión y el backtest ha dejado de medir la lógica de producción.
    """
    tech = {"close": 100.0, "rsi": 60.0, "atr": 2.0}
    base = {
        "ticker": "TEST",
        "passed_fundamental_gatekeeper": True,
        "fundamental_report": {"metrics": {"net_margin": 0.15}, "summary": "ok"},
        "technical_report": {"momentum_classification": "ALCISTA_FUERTE", "rsi": 60.0},
        "debate_report": {"synthesis": "sintesis"},
        "yfinance_data": {"technical": tech},
    }
    sin_noticias = FundManagerAgent().analyze(copy.deepcopy(base))

    con = copy.deepcopy(base)
    con["news_report"] = NewsAnalystAgent().analyze(estado([
        item("Test Corp faces SEC investigation, shares plunge on lawsuit", fecha=HOY,
             tipo="SEC_8K", corroboraciones=4),
    ]))
    assert con["news_report"]["direction_classification"] == "BAJISTA"
    con_noticias = FundManagerAgent().analyze(con)

    for clave in ("rating", "position_size_pct", "stop_loss_atr", "take_profit_atr"):
        assert sin_noticias[clave] == con_noticias[clave], (
            f"`{clave}` cambió al añadir noticias: la capa ha dejado de ser asesora")


def test_marca_de_capa_asesora_presente():
    """El informe declara explícitamente que no entra en la decisión."""
    assert NewsAnalystAgent().analyze(estado([item("Cualquier cosa")]))["advisory_only"] is True


# --------------------------------------------------------------------------- #
# 2. Clasificación por categoría (diccionario, no LLM)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("titulo,esperada", [
    ("Acme reports fourth quarter financial results", "RESULTADOS"),
    ("Acme raises full-year guidance on strong outlook", "GUIDANCE"),
    ("Acme faces SEC investigation and class action lawsuit", "REGULATORIO"),
    ("Acme announces $10B share repurchase program", "CAPITAL"),
    ("Acme CEO steps down; board appoints successor", "CORPORATIVO"),
    ("Acme partners with Globex in a joint venture", "ALIANZA"),
    ("Acme launches next-generation platform", "PRODUCTO"),
    ("Analistas debaten sobre el mercado en general", "OTROS"),
])
def test_categoria_por_palabras_clave(titulo, esperada):
    assert clasificar_categoria(titulo)[0] == esperada


def test_categoria_forzada_gana_al_lexico():
    """Un 8-K con Ítem 2.02 es RESULTADOS por definición de la SEC, no por su titular."""
    assert clasificar_categoria("Un titular sobre lanzamientos de producto",
                                categoria_forzada="RESULTADOS")[0] == "RESULTADOS"


def test_coincidencia_por_palabra_completa():
    """"eps" no debe casar dentro de otra palabra."""
    assert clasificar_categoria("Acme epsilon project update")[0] == "OTROS"
    assert clasificar_categoria("Acme eps came in above consensus")[0] == "RESULTADOS"


def test_desempate_de_categoria_por_prioridad():
    """
    Con el mismo número de coincidencias manda `NEWS_CATEGORY_PRIORITY`, no el
    orden de iteración del diccionario.

    Aquí hay exactamente un acierto por categoría ("quarterly results" en
    RESULTADOS y "availability" en PRODUCTO), y RESULTADOS gana por prioridad.
    """
    titulo = "Acme quarterly results and platform availability"
    categoria, aciertos = clasificar_categoria(titulo)
    assert aciertos == 1, "el caso ha dejado de ser un empate: revisa el léxico"
    assert categoria == "RESULTADOS"


def test_mas_coincidencias_gana_a_la_prioridad():
    """La prioridad solo desempata; no anula el recuento."""
    # PRODUCTO suma "launches" y "new product"; RESULTADOS solo "quarterly results".
    assert clasificar_categoria("Acme quarterly results and new product launches")[0] == "PRODUCTO"


# --------------------------------------------------------------------------- #
# 3. Dirección por léxico de severidad
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("titulo,esperada", [
    ("Acme beats estimates, shares surge to record high", "ALCISTA"),
    ("Acme misses estimates, cuts guidance, stock plunges", "BAJISTA"),
    ("Acme publica su informe anual", "NEUTRA"),
])
def test_direccion_de_un_item(titulo, esperada):
    assert inferir_direccion_item(titulo)[0] == esperada


def test_direccion_agregada_pondera_por_impacto():
    """
    Una nota bajista de fuente primaria pesa más que varias alcistas de un
    agregador: la dirección la marca el peso, no el recuento.
    """
    puntuados = [
        puntuar_item(item("Acme misses estimates and cuts guidance", fecha=HOY,
                          tipo="SEC_8K", forzada="RESULTADOS"), HOY),
        puntuar_item(item("Acme wins award", fecha="2024-02-20", tipo="AGREGADOR"), HOY),
        puntuar_item(item("Acme record hiring surge", fecha="2024-02-19", tipo="AGREGADOR"), HOY),
    ]
    assert direccion_agregada(puntuados)[0] == "BAJISTA"


def test_sin_terminos_del_lexico_la_direccion_es_incierta():
    """Hay noticias, pero no dicen en qué sentido. INCIERTA no es MIXTA."""
    puntuados = [puntuar_item(item("Acme publica su calendario corporativo"), HOY)]
    assert direccion_agregada(puntuados)[0] == "INCIERTA"


def test_direccion_mixta_cuando_se_compensan():
    puntuados = [
        puntuar_item(item("Acme beats estimates", fecha=HOY, tipo="MEDIO_TIER1"), HOY),
        puntuar_item(item("Acme misses estimates", fecha=HOY, tipo="MEDIO_TIER1"), HOY),
    ]
    assert direccion_agregada(puntuados)[0] == "MIXTA"


# --------------------------------------------------------------------------- #
# 4. Ponderación: credibilidad, antigüedad y corroboración
# --------------------------------------------------------------------------- #
def test_la_fuente_primaria_pesa_mas_que_el_agregador():
    """Mismo titular, misma fecha: solo cambia el tipo de fuente."""
    titulo = "Acme reports fourth quarter results"
    p_sec = puntuar_item(item(titulo, fecha=HOY, tipo="SEC_8K"), HOY)["probabilidad_impacto"]
    p_wire = puntuar_item(item(titulo, fecha=HOY, tipo="NEWSWIRE"), HOY)["probabilidad_impacto"]
    p_agg = puntuar_item(item(titulo, fecha=HOY, tipo="AGREGADOR"), HOY)["probabilidad_impacto"]
    assert p_sec > p_wire > p_agg


def test_la_noticia_vieja_pesa_menos():
    titulo = "Acme reports fourth quarter results"
    reciente = puntuar_item(item(titulo, fecha=HOY), HOY)["probabilidad_impacto"]
    vieja = puntuar_item(item(titulo, fecha="2024-02-15"), HOY)["probabilidad_impacto"]
    assert reciente > vieja


def test_decaimiento_por_semivida():
    """A una semivida exacta el peso es la mitad."""
    from src.config import NEWS_HALFLIFE_DAYS
    assert decaimiento(0) == pytest.approx(1.0)
    assert decaimiento(NEWS_HALFLIFE_DAYS) == pytest.approx(0.5)
    assert decaimiento(2 * NEWS_HALFLIFE_DAYS) == pytest.approx(0.25)


def test_item_sin_fecha_se_penaliza_de_forma_determinista():
    """Sin fecha se asume una antigüedad fija: no depende del reloj."""
    from src.config import NEWS_DAYS_IF_UNDATED
    assert dias_de_antiguedad(None, HOY) == NEWS_DAYS_IF_UNDATED
    assert dias_de_antiguedad("fecha-invalida", HOY) == NEWS_DAYS_IF_UNDATED


def test_fecha_futura_no_produce_antiguedad_negativa():
    """Los husos horarios de los feeds adelantan fechas; se recorta a 0 días."""
    assert dias_de_antiguedad("2024-03-20", HOY) == 0


def test_corroboracion_sube_el_peso_pero_con_tope():
    titulo = "Acme reports fourth quarter results"
    una = puntuar_item(item(titulo, fecha=HOY), HOY)["probabilidad_impacto"]
    tres = puntuar_item(item(titulo, fecha=HOY, corroboraciones=3), HOY)["probabilidad_impacto"]
    assert tres > una
    assert factor_corroboracion(50) == pytest.approx(NEWS_MAX_CORROBORATION_FACTOR)


def test_el_ruido_promocional_de_bufetes_se_degrada():
    """
    Los avisos de bufetes captando demandantes saturan estos feeds. Sin la
    penalización entrarían como REGULATORIO por newswire, y cualquier megacap
    tendría noticias "de alto impacto" todas las semanas.
    """
    ruido = puntuar_item(
        item("Portnoy Law Firm Announces Class Action on Behalf of Acme Investors",
             fecha=HOY, tipo="NEWSWIRE"), HOY)
    litigio_real = puntuar_item(
        item("Acme faces antitrust probe from the DOJ over cloud licensing",
             fecha=HOY, tipo="NEWSWIRE"), HOY)

    assert ruido["ruido_promocional"] is True
    assert litigio_real["ruido_promocional"] is False
    # Ambos son REGULATORIO: lo que los separa es la penalización, no la categoría.
    assert ruido["categoria"] == litigio_real["categoria"] == "REGULATORIO"
    assert ruido["probabilidad_impacto"] < litigio_real["probabilidad_impacto"] / 3


def test_el_ruido_se_degrada_pero_no_se_descarta():
    """Un litigio real puede esconderse detrás de un aviso: sigue puntuando."""
    ruido = puntuar_item(
        item("Rosen Law reminds investors of the class action deadline", fecha=HOY,
             tipo="NEWSWIRE"), HOY)
    assert ruido["probabilidad_impacto"] > 0


def test_ningun_item_supera_la_probabilidad_maxima():
    """Ninguna noticia aislada garantiza un movimiento de precio."""
    perfecto = puntuar_item(
        item("Acme reports fourth quarter results", fecha=HOY, tipo="SEC_8K",
             forzada="RESULTADOS", corroboraciones=10), HOY)
    assert perfecto["probabilidad_impacto"] <= NEWS_ITEM_PROB_MAX


# --------------------------------------------------------------------------- #
# 5. Agregación a probabilidad y bucket
# --------------------------------------------------------------------------- #
def test_or_ruidoso_es_monotono_y_acotado():
    puntuados = [puntuar_item(item(f"Acme reports results {i}", fecha=HOY), HOY)
                 for i in range(3)]
    p1 = agregar_probabilidad(puntuados[:1])
    p2 = agregar_probabilidad(puntuados[:2])
    p3 = agregar_probabilidad(puntuados)
    assert 0.0 <= p1 < p2 < p3 < 1.0


def test_la_cola_de_ruido_no_satura_la_probabilidad():
    """Solo los NEWS_TOP_K_ITEMS más relevantes entran en la agregación."""
    muchos = [puntuar_item(item(f"Acme reports results {i}", fecha=HOY), HOY)
              for i in range(NEWS_TOP_K_ITEMS + 20)]
    truncado = agregar_probabilidad(muchos)
    solo_k = agregar_probabilidad(muchos[:NEWS_TOP_K_ITEMS])
    assert truncado == pytest.approx(solo_k)


def test_sin_noticias_la_probabilidad_es_cero():
    rep = NewsAnalystAgent().analyze(estado([]))
    assert rep["impact_probability"] == 0.0
    assert rep["impact_classification"] == "BAJA"
    assert rep["direction_classification"] == "INCIERTA"
    assert rep["catalysts"] == []
    assert rep["n_items"] == 0


@pytest.mark.parametrize("probabilidad,bucket", [
    (0.0, "BAJA"),
    (NEWS_MEDIUM_IMPACT_THRESHOLD - 0.01, "BAJA"),
    (NEWS_MEDIUM_IMPACT_THRESHOLD, "MEDIA"),
    (NEWS_HIGH_IMPACT_THRESHOLD - 0.01, "MEDIA"),
    (NEWS_HIGH_IMPACT_THRESHOLD, "ALTA"),
    (1.0, "ALTA"),
])
def test_umbrales_del_bucket(probabilidad, bucket):
    assert clasificar_impacto(probabilidad) == bucket


def test_los_catalizadores_estan_ordenados_por_impacto():
    rep = NewsAnalystAgent().analyze(estado([
        item("Acme analistas opinan del sector", fecha="2024-02-10", tipo="AGREGADOR"),
        item("Acme reports fourth quarter results", fecha=HOY, tipo="SEC_8K",
             forzada="RESULTADOS"),
        item("Acme launches new widget", fecha="2024-03-10", tipo="NEWSWIRE"),
    ]))
    probabilidades = [c["probabilidad_impacto"] for c in rep["catalysts"]]
    assert probabilidades == sorted(probabilidades, reverse=True)
    assert rep["catalysts"][0]["categoria"] == "RESULTADOS"


def test_el_agente_es_reproducible():
    """Dos ejecuciones sobre el mismo payload dan exactamente lo mismo."""
    s = estado([
        item("Acme reports fourth quarter results", fecha=HOY, tipo="SEC_8K",
             forzada="RESULTADOS"),
        item("Acme beats estimates", fecha="2024-03-12", corroboraciones=2),
        item("Acme sin fecha conocida", fecha=None, tipo="DESCONOCIDA"),
    ])
    a = NewsAnalystAgent().analyze(copy.deepcopy(s))
    b = NewsAnalystAgent().analyze(copy.deepcopy(s))
    assert a == b


# --------------------------------------------------------------------------- #
# 6. Deduplicación y normalización (capa de datos)
# --------------------------------------------------------------------------- #
def test_dos_medios_sobre_el_mismo_hecho_se_fusionan_y_corroboran():
    a = normalizar_item("Acme Announces Record Second Quarter Results",
                        "https://www.businesswire.com/a", "Business Wire", "2024-03-14",
                        "x", "google_news_rss")
    b = normalizar_item("Acme announces record second-quarter results",
                        "https://www.reuters.com/b", "Reuters", "2024-03-15",
                        "y", "tavily")
    fusionados = deduplicar([a, b])
    assert len(fusionados) == 1
    assert fusionados[0]["n_corroboraciones"] == 2
    # El canónico es el más creíble de los dos y la fecha, la primera publicación.
    assert fusionados[0]["tipo_fuente"] == "NEWSWIRE"
    assert fusionados[0]["fecha"] == "2024-03-14"


def test_el_mismo_articulo_hallado_por_dos_buscadores_no_infla_la_corroboracion():
    """Que Tavily y Google encuentren el mismo enlace no son dos fuentes."""
    url = "https://www.cnbc.com/misma-noticia"
    a = normalizar_item("Acme unveils new platform", url, "CNBC", "2024-03-14", "", "tavily")
    b = normalizar_item("Acme unveils new platform", url, "CNBC", "2024-03-14", "",
                        "google_news_rss")
    fusionados = deduplicar([a, b])
    assert len(fusionados) == 1
    assert fusionados[0]["n_corroboraciones"] == 1
    assert fusionados[0]["buscadores"] == ["google_news_rss", "tavily"]


def test_noticias_distintas_no_se_fusionan():
    a = normalizar_item("Acme reports fourth quarter results", "https://a.com/1", "A",
                        "2024-03-14", "", "tavily")
    b = normalizar_item("Acme opens a new factory in Ohio", "https://b.com/2", "B",
                        "2024-03-14", "", "tavily")
    assert len(deduplicar([a, b])) == 2


def test_deduplicacion_es_independiente_del_orden_de_llegada():
    """Los hilos terminan en cualquier orden; el resultado no puede depender de eso."""
    items = [
        normalizar_item("Acme reports fourth quarter results", "https://a.com/1", "A",
                        "2024-03-14", "", "tavily"),
        normalizar_item("Acme reports fourth-quarter results", "https://b.com/2", "B",
                        "2024-03-13", "", "google_news_rss"),
        normalizar_item("Acme opens new factory in Ohio", "https://c.com/3", "C",
                        "2024-03-12", "", "sec_8k"),
    ]
    directo = deduplicar(items)
    invertido = deduplicar(list(reversed(items)))
    assert [i["titulo"] for i in directo] == [i["titulo"] for i in invertido]
    assert [i["n_corroboraciones"] for i in directo] == \
           [i["n_corroboraciones"] for i in invertido]


def test_item_sin_titular_se_descarta():
    assert normalizar_item("", "https://a.com", "A", "2024-03-14", "x", "tavily") is None


@pytest.mark.parametrize("url,tipo", [
    ("https://www.sec.gov/Archives/edgar/data/1/x.htm", "SEC_8K"),
    ("https://investor.acme.com/news/2024", "IR_OFICIAL"),
    ("https://www.businesswire.com/news/x", "NEWSWIRE"),
    ("https://www.reuters.com/business/x", "MEDIO_TIER1"),
    ("https://finance.yahoo.com/news/x", "AGREGADOR"),
    ("https://un-blog-cualquiera.io/x", "DESCONOCIDA"),
])
def test_clasificacion_del_tipo_de_fuente(url, tipo):
    assert clasificar_tipo_fuente(url) == tipo


@pytest.mark.parametrize("url,empresa,tipo", [
    # La sala de prensa de la propia empresa es comunicación directa del emisor.
    ("https://www.apple.com/newsroom/2024/x", "Apple Inc.", "IR_OFICIAL"),
    ("https://nvidianews.nvidia.com/x", "NVIDIA Corporation", "IR_OFICIAL"),
    ("https://www.bankofamerica.com/press/x", "Bank of America Corporation", "IR_OFICIAL"),
    # Un medio no se convierte en fuente oficial por hablar de la empresa.
    ("https://www.reuters.com/x", "Apple Inc.", "MEDIO_TIER1"),
    ("https://finance.yahoo.com/x", "Apple Inc.", "AGREGADOR"),
    ("https://un-blog-cualquiera.io/x", "Apple Inc.", "DESCONOCIDA"),
    # Sin nombre de empresa no se puede afirmar: se mantiene lo conservador.
    ("https://www.apple.com/x", None, "DESCONOCIDA"),
])
def test_dominio_propio_de_la_empresa_es_fuente_oficial(url, empresa, tipo):
    assert clasificar_tipo_fuente(url, empresa=empresa) == tipo


def test_los_mapas_explicitos_ganan_a_la_heuristica_de_subdominio():
    """`media.msn.com` es un agregador, no la sala de prensa de nadie."""
    assert clasificar_tipo_fuente("https://media.msn.com/x") == "AGREGADOR"


@pytest.mark.parametrize("valor,esperado", [
    ("Mon, 17 Aug 2026 12:38:06 GMT", "2026-08-17"),
    ("2026-08-17T10:00:00Z", "2026-08-17"),
    ("2026-08-17", "2026-08-17"),
    ("no es una fecha", None),
    (None, None),
])
def test_normalizacion_de_fechas(valor, esperado):
    assert fecha_iso(valor) == esperado


# --------------------------------------------------------------------------- #
# 7. Degradación: ninguna fuente caída puede tumbar el nodo
# --------------------------------------------------------------------------- #
def test_informe_degradado_cuando_falla_una_fuente():
    s = estado([item("Acme reports fourth quarter results", fecha=HOY)])
    s["news_data"]["status"] = "DEGRADADO"
    s["news_data"]["fuentes_ok"] = ["google_news_rss"]
    s["news_data"]["fuentes_failed"] = None  # clave inexistente: no debe consultarse
    s["news_data"]["fuentes_fallidas"] = [
        {"buscador": "tavily", "motivo": "TAVILY_API_KEY no está definida en el entorno"},
        {"buscador": "sec_8k", "motivo": "tiempo agotado (30s)"},
    ]
    rep = NewsAnalystAgent().analyze(s)

    assert rep["status"] == "DEGRADADO"
    assert rep["impact_probability"] > 0  # sigue emitiendo dictamen con lo que llegó
    assert [f["buscador"] for f in rep["sources_failed"]] == ["tavily", "sec_8k"]
    assert "DEGRADADO" in rep["summary"]


def test_sin_news_data_el_agente_no_revienta():
    """Estado sin dosier (p. ej. fallo total del agregador): informe vacío, no excepción."""
    rep = NewsAnalystAgent().analyze({"ticker": "TEST"})
    assert rep["n_items"] == 0
    assert rep["impact_classification"] == "BAJA"
    assert rep["status"] == "SIN_DATOS"


def test_tavily_sin_clave_no_lanza_al_agregador():
    """La ausencia de clave es una capacidad ausente declarada, no un fallo de red."""
    from src.data.news import tavily as tavily_mod
    if tavily_mod.TAVILY_API_KEY:
        pytest.skip("Hay TAVILY_API_KEY en el entorno: este caso no aplica")
    with pytest.raises(tavily_mod.TavilyNoDisponible):
        tavily_mod.buscar("Test Corp", "TEST", 5)
    assert tavily_mod.disponible() is False
