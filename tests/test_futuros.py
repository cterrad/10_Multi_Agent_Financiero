"""
Tests del bloque macro: informes COT y sesgo de posicionamiento en futuros.

Qué protegen
------------
1. La DISCIPLINA POINT-IN-TIME del COT. El informe del martes no es público
   hasta el viernes, y confundir las dos fechas es la misma fuga que leer un
   cierre contable antes de su 10-K. `test_serie_semanal_filtra_por_publicacion`
   y `test_el_parseo_declara_las_dos_fechas` la fijan.
2. Que el z-score mida POSICIONAMIENTO y no el tamaño del mercado — de ahí la
   normalización por interés abierto.
3. Que una ausencia se declare y no se rellene: sin semanas suficientes el
   z-score es `None`, y un sector sin contrato correlato no recibe proxy.
4. Que el clasificador sea monótono, que es la propiedad que el momentum por
   puntos enteros no cumplía.

Offline y deterministas: no se descarga nada de la CFTC.
"""

import pytest

from src.config import COT_MINIMO_SEMANAS, COT_Z_EXTREMO, SECTOR_A_FUTURO
from src.data.futuros import cache as macro_cache
from src.data.futuros.cot import (
    _parsear,
    _resolver_columnas,
    fecha_de_publicacion,
    serie_semanal,
)
from src.tools.futuros import (
    _etiqueta_macro,
    _zscore,
    calcular_zscore_cot,
    clasificar_sesgo_macro,
    resolver_contrato_sectorial,
)

CABECERA = [
    "Market and Exchange Names",
    "As of Date in Form YYMMDD",
    "As of Date in Form YYYY-MM-DD",
    "Open Interest (All)",
    "Noncommercial Positions-Long (All)",
    "Noncommercial Positions-Short (All)",
    "Commercial Positions-Long (All)",
    "Commercial Positions-Short (All)",
]


def fila(fecha, largos, cortos, oi=1_000_000, mercado="CRUDE OIL - NYMEX"):
    """Una fila semanal en el formato normalizado del recolector."""
    from datetime import date
    f = date.fromisoformat(fecha)
    return {"mercado": mercado, "fecha_informe": fecha,
            "fecha_publicacion": fecha_de_publicacion(f).isoformat(),
            "no_comercial_largos": largos, "no_comercial_cortos": cortos,
            "comercial_largos": oi // 2, "comercial_cortos": oi // 2,
            "interes_abierto": oi}


def serie(n=80, base=200_000, amplitud=4_000, oi=1_000_000):
    """Serie semanal determinista de `n` semanas."""
    from datetime import date, timedelta
    d = date(2022, 1, 4)  # un martes
    filas = []
    for i in range(n):
        f = d + timedelta(weeks=i)
        desvio = amplitud * ((i % 7) - 3)
        filas.append(fila(f.isoformat(), base + desvio, base - desvio, oi))
    return filas


# --------------------------------------------------------------------------- #
# 1. Disciplina point-in-time
# --------------------------------------------------------------------------- #
def test_el_parseo_declara_las_dos_fechas():
    """
    El informe del martes se publica el viernes. Son dos fechas distintas y las
    dos tienen que viajar: usar la del informe en un estudio histórico permite
    operar el miércoles con datos que nadie tenía.
    """
    crudo = (",".join(f'"{c}"' for c in CABECERA) + "\n"
             '"CRUDE OIL, LIGHT SWEET - NYMEX",240305,2024-03-05,'
             '1500000,300000,120000,900000,1100000')
    filas, motivo = _parsear(crudo, 2024)
    assert motivo is None
    assert filas[0]["fecha_informe"] == "2024-03-05"     # martes
    assert filas[0]["fecha_publicacion"] == "2024-03-08"  # viernes
    assert filas[0]["fecha_publicacion"] > filas[0]["fecha_informe"]


def test_el_parseo_no_confunde_comercial_con_no_comercial():
    """
    "Commercial Positions-Long" es SUBCADENA de "Noncommercial Positions-Long".
    Si el resolutor de columnas no excluye explícitamente la segunda al buscar la
    primera, la posición especulativa y la de cobertura se intercambian en
    silencio y el sesgo sale con el signo invertido.
    """
    cols = _resolver_columnas(CABECERA)
    assert cols["no_comercial_largos"] == 4
    assert cols["no_comercial_cortos"] == 5
    assert cols["comercial_largos"] == 6
    assert cols["comercial_cortos"] == 7
    # La fecha elegida es la de cuatro dígitos, no la de seis.
    assert cols["fecha_informe"] == 2


def test_un_formato_sin_columnas_obligatorias_se_declara_no_utilizable():
    """
    Los nombres de columna de la CFTC han cambiado entre formatos históricos. Un
    fichero que no se sabe leer se declara con su motivo; devolver una serie de
    ceros sería peor, porque el z-score saldría igualmente.
    """
    crudo = '"Algo","Otra cosa"\n1,2'
    filas, motivo = _parsear(crudo, 2024)
    assert filas == []
    assert motivo and "columnas" in motivo


def test_serie_semanal_filtra_por_publicacion(tmp_path):
    """
    ESTA ES LA BARRERA point-in-time del bloque macro. Un informe cuya
    publicación es posterior a `as_of` no puede aparecer en la serie, aunque su
    fecha de informe sí lo sea.
    """
    filas = serie(n=60)
    macro_cache.escribir_cot("CRUDE OIL", 2022, filas, directorio=tmp_path)
    macro_cache.escribir_cot("CRUDE OIL", 2023, [], directorio=tmp_path)

    ultimo = filas[-1]
    # Un día ANTES de la publicación: ese informe todavía no existe para nadie.
    vispera = serie_semanal("CRUDE OIL", as_of=ultimo["fecha_informe"],
                            offline=True, directorio=tmp_path)
    fechas = [f["fecha_informe"] for f in vispera["serie"]]
    assert ultimo["fecha_informe"] not in fechas, (
        "un informe visible antes de su publicación es look-ahead")

    # El día de la publicación sí.
    despues = serie_semanal("CRUDE OIL", as_of=ultimo["fecha_publicacion"],
                            offline=True, directorio=tmp_path)
    assert ultimo["fecha_informe"] in [f["fecha_informe"] for f in despues["serie"]]


# --------------------------------------------------------------------------- #
# 2. El z-score mide posicionamiento, no tamaño de mercado
# --------------------------------------------------------------------------- #
def test_el_zscore_normaliza_por_interes_abierto():
    """
    Duplicar contratos e interés abierto a la vez no cambia el posicionamiento
    relativo, así que el z-score debe ser idéntico. Sin normalizar, el
    crecimiento secular del mercado de futuros entraría como señal — el mismo
    error de categoría que leer un histograma MACD sin normalizar por ATR.
    """
    pequena = serie(base=100_000, amplitud=2_000, oi=500_000)
    grande = [dict(f, no_comercial_largos=f["no_comercial_largos"] * 2,
                   no_comercial_cortos=f["no_comercial_cortos"] * 2,
                   interes_abierto=f["interes_abierto"] * 2) for f in pequena]
    assert _zscore(pequena)["z"] == pytest.approx(_zscore(grande)["z"])


def test_sin_semanas_suficientes_el_zscore_es_none():
    """
    Una desviación típica sobre veinte semanas no es una medida de extremo.
    `None` y el motivo, nunca un cero que se leería como posicionamiento neutro.
    """
    r = calcular_zscore_cot.invoke({"serie": serie(n=COT_MINIMO_SEMANAS - 1)})
    assert r["z"] is None
    assert r["disponible"] is False
    assert str(COT_MINIMO_SEMANAS) in r["motivo"]


def test_una_serie_plana_no_produce_zscore():
    """Sin dispersión no hay tipificación posible, y dividir por cero no vale."""
    plana = [fila("2022-01-04", 100, 100) for _ in range(80)]
    assert calcular_zscore_cot.invoke({"serie": plana})["z"] is None


def test_el_extremo_no_invierte_el_signo():
    """
    Un posicionamiento hacinado es una advertencia contraria, pero invertir el
    signo con |z| > 2 produciría un clasificador NO MONÓTONO — exactamente la
    patología que el momentum por puntos enteros tenía. El extremo se marca
    aparte y solo prohíbe perseguir el precio.
    """
    base = serie(n=80)
    # Última semana con un salto que la lleva a territorio extremo.
    disparada = base[:-1] + [dict(base[-1], no_comercial_largos=600_000,
                                  no_comercial_cortos=10_000)]
    r = calcular_zscore_cot.invoke({"serie": disparada})
    assert r["z"] > COT_Z_EXTREMO
    assert r["extremo"] is True

    sesgo = clasificar_sesgo_macro.invoke({"componentes": [
        {"contrato": "ES=F", "papel": "indice", "z": r["z"], "signo": 1,
         "extremo": True}]})
    assert sesgo["sesgo_macro"] > 0, "el extremo no puede invertir la dirección"
    assert sesgo["extremo"] is True


# --------------------------------------------------------------------------- #
# 3. Ausencia declarada, nunca rellenada
# --------------------------------------------------------------------------- #
def test_un_sector_fuera_del_mapa_no_recibe_pata_sectorial():
    """
    Forzar un contrato para «Technology» produciría un número donde no hay
    relación, que es peor que declarar NO_APLICABLE.
    """
    r = resolver_contrato_sectorial.invoke({"sector": "Technology"})
    assert r["es_aplicable"] is False
    assert r["contrato"] is None
    assert r["signo"] is None
    assert "correlato" in r["motivo"]
    # Pero el índice sí aplica a todos los sectores.
    assert r["indice"]["contrato"]


def test_un_sector_del_mapa_trae_contrato_y_signo():
    sector = next(iter(SECTOR_A_FUTURO))
    r = resolver_contrato_sectorial.invoke({"sector": sector})
    assert r["es_aplicable"] is True
    assert r["contrato"] == SECTOR_A_FUTURO[sector]["contrato"]
    assert r["signo"] in (1, -1)


def test_el_signo_sectorial_se_aplica():
    """
    Para financieras e inmobiliario el contrato es el bono y el signo es -1: el
    mismo z-score tiene que producir sesgos opuestos según el signo.
    """
    a = clasificar_sesgo_macro.invoke({"componentes": [
        {"contrato": "CL=F", "papel": "sectorial", "z": 1.2, "signo": 1}]})
    b = clasificar_sesgo_macro.invoke({"componentes": [
        {"contrato": "ZN=F", "papel": "sectorial", "z": 1.2, "signo": -1}]})
    assert a["sesgo_macro"] == pytest.approx(-b["sesgo_macro"])


def test_sin_ninguna_pata_evaluable_el_sesgo_es_none():
    """`None` y NO_APLICABLE, no 0.0: un cero afirmaría que no hay sesgo."""
    r = clasificar_sesgo_macro.invoke({"componentes": [
        {"contrato": "ES=F", "papel": "indice", "z": None, "signo": 1}]})
    assert r["sesgo_macro"] is None
    assert r["clasificacion"] == "NO_APLICABLE"


def test_el_sesgo_promedia_solo_sobre_lo_disponible():
    """
    Imputar un cero a la pata ausente convertiría una ausencia en una lectura
    neutra y arrastraría el promedio hacia el centro. Es la regla nº 1.
    """
    solo_indice = clasificar_sesgo_macro.invoke({"componentes": [
        {"contrato": "ES=F", "papel": "indice", "z": 1.5, "signo": 1},
        {"contrato": "CL=F", "papel": "sectorial", "z": None, "signo": 1}]})
    aislado = clasificar_sesgo_macro.invoke({"componentes": [
        {"contrato": "ES=F", "papel": "indice", "z": 1.5, "signo": 1}]})
    assert solo_indice["sesgo_macro"] == aislado["sesgo_macro"]
    assert solo_indice["n_disponibles"] == 1


# --------------------------------------------------------------------------- #
# 4. Monotonía del clasificador
# --------------------------------------------------------------------------- #
def test_la_clasificacion_de_sesgo_es_monotona():
    """
    La etiqueta solo puede mejorar si el sesgo sube. Misma propiedad que
    `test_la_etiqueta_es_monotona_en_la_puntuacion` fija para el momentum.
    """
    orden = ["VIENTO_EN_CONTRA_FUERTE", "VIENTO_EN_CONTRA", "NEUTRO",
             "VIENTO_A_FAVOR", "VIENTO_A_FAVOR_FUERTE"]
    previo = -1
    for i in range(-100, 101):
        actual = orden.index(_etiqueta_macro(i / 100.0))
        assert actual >= previo, f"la etiqueta empeoró al subir el sesgo en {i / 100.0}"
        previo = actual


def test_el_sesgo_es_monotono_en_el_zscore():
    """Más posicionamiento especulativo largo nunca puede dar menos sesgo."""
    previo = -2.0
    for z in [i / 10.0 for i in range(-40, 41)]:
        s = clasificar_sesgo_macro.invoke({"componentes": [
            {"contrato": "ES=F", "papel": "indice", "z": z, "signo": 1}]})["sesgo_macro"]
        assert s >= previo
        previo = s
