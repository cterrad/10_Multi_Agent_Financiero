"""
Informes Commitments of Traders de la CFTC.

Que se descarga y por que
-------------------------
La CFTC publica cada viernes a las 15:30 ET el posicionamiento agregado por
categoria de operador, referido al MARTES anterior. El archivo historico son
ficheros anuales comprimidos (`deacot{ANIO}.zip`), publicos y gratuitos.

Se usa la categoria NO COMERCIAL (especuladores). Los comerciales cubren
produccion o inventario, asi que su posicion la dicta el negocio y no una
opinion; los no comerciales son el flujo direccional marginal y su
posicionamiento revierte a la media. La posicion comercial se conserva en cada
fila para el informe, pero no entra en ningun calculo.

La distincion que hace valido el backtest
-----------------------------------------
Cada fila lleva DOS fechas:

    fecha_informe      el martes al que se refieren los datos
    fecha_publicacion  el viernes en que se hicieron publicos

Es exactamente el par `end` / `filed` de los hechos XBRL
(`src/backtest/data.py`). Filtrar por `fecha_informe` en un estudio historico
permite operar el miercoles con datos que nadie tenia, que es la misma fuga que
el proyecto ya corrigio para los fundamentales. Todo filtro point-in-time de
este modulo usa `fecha_publicacion`.

Robustez frente al formato
--------------------------
Los nombres de columna de la CFTC han cambiado entre formatos historicos
(Legacy / Disaggregated / TFF), asi que las columnas se resuelven por
coincidencia de subcadena normalizada y no por posicion ni por nombre exacto.
Si falta una columna obligatoria, el ano se declara no disponible con su motivo
en vez de devolver ceros: una serie de posicionamiento a cero no es "sin
posicionamiento", es un fichero que no se supo leer.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    COT_HTTP_TIMEOUT,
    COT_RETARDO_PUBLICACION_DIAS,
    COT_URL_ANUAL,
    SEC_EDGAR_USER_AGENT,
)
from src.data.futuros import cache as macro_cache

NOMBRE = "cot_cftc"

# Columnas obligatorias. Sin cualquiera de ellas el ano no es utilizable.
_OBLIGATORIAS = ("mercado", "fecha_informe", "no_comercial_largos",
                 "no_comercial_cortos", "interes_abierto")


def _norm(texto: str) -> str:
    """Cabecera a forma comparable: minusculas, solo alfanumerico."""
    return re.sub(r"[^a-z0-9]+", "", (texto or "").lower())


def _resolver_columnas(cabecera: List[str]) -> Dict[str, int]:
    """
    Indice de cada columna logica en la cabecera real.

    El orden de resolucion importa: "commercialpositionslong" es subcadena de
    "noncommercialpositionslong", asi que las no comerciales se resuelven
    primero y las comerciales excluyen explicitamente las ya asignadas. Sin esa
    precaucion, la posicion especulativa y la de cobertura se intercambian en
    silencio y el sesgo sale con el signo invertido.
    """
    norms = [_norm(c) for c in cabecera]
    cols: Dict[str, int] = {}

    def buscar(*fragmentos: str, excluir: Tuple[str, ...] = ()) -> Optional[int]:
        for i, n in enumerate(norms):
            if i in cols.values():
                continue
            if all(f in n for f in fragmentos) and not any(e in n for e in excluir):
                return i
        return None

    for clave, args, kwargs in (
        ("mercado", ("marketandexchangenames",), {}),
        # La fecha con ano de cuatro digitos, no la de seis. "yyyy" solo aparece
        # en la primera; la de seis digitos normaliza a "...yymmdd".
        ("fecha_informe", ("date", "yyyy"), {}),
        ("no_comercial_largos", ("noncommercial", "long", "all"), {}),
        ("no_comercial_cortos", ("noncommercial", "short", "all"), {}),
        ("comercial_largos", ("commercial", "long", "all"), {"excluir": ("noncommercial",)}),
        ("comercial_cortos", ("commercial", "short", "all"), {"excluir": ("noncommercial",)}),
        ("interes_abierto", ("openinterest", "all"), {}),
    ):
        idx = buscar(*args, **kwargs)
        if idx is not None:
            cols[clave] = idx

    if "mercado" not in cols and norms:
        # Algunos volcados no rotulan la primera columna. Es siempre el mercado.
        cols["mercado"] = 0
    return cols


def _fecha(valor: str) -> Optional[date]:
    v = (valor or "").strip().split(" ")[0]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _entero(valor: str) -> Optional[int]:
    v = (valor or "").strip().replace(",", "").replace('"', "")
    if not v or v in (".", "-"):
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def fecha_de_publicacion(fecha_informe: date) -> date:
    """
    Martes del informe -> viernes de su publicacion.

    Es el equivalente de `MIN_REPORTING_LAG_DAYS` para el COT, y por el mismo
    motivo: sin este desplazamiento, un backtest lee el lunes cifras que se
    hicieron publicas el viernes siguiente.
    """
    return fecha_informe + timedelta(days=COT_RETARDO_PUBLICACION_DIAS)


# --------------------------------------------------------------------------- #
# Descarga y parseo
# --------------------------------------------------------------------------- #
def _descargar_anio(anio: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Devuelve `(filas, motivo_de_fallo)`. Nunca lanza."""
    try:
        import requests
    except ImportError:  # pragma: no cover
        return [], "el paquete `requests` no esta disponible"

    url = COT_URL_ANUAL.format(anio=anio)
    try:
        r = requests.get(url, headers={"User-Agent": SEC_EDGAR_USER_AGENT},
                         timeout=COT_HTTP_TIMEOUT)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code} en {url}"
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nombres = [n for n in z.namelist() if not n.endswith("/")]
            if not nombres:
                return [], f"el zip de {anio} viene vacio"
            crudo = z.read(nombres[0]).decode("latin-1", errors="replace")
    except Exception as exc:  # pragma: no cover - depende de la red
        return [], f"{type(exc).__name__}: {exc}"

    return _parsear(crudo, anio)


def _parsear(crudo: str, anio: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Texto CSV de la CFTC a filas normalizadas. Expuesto para los tests."""
    lector = csv.reader(io.StringIO(crudo))
    try:
        cabecera = next(lector)
    except StopIteration:
        return [], f"el fichero de {anio} no tiene cabecera"

    cols = _resolver_columnas(cabecera)
    faltan = [c for c in _OBLIGATORIAS if c not in cols]
    if faltan:
        return [], (f"el formato de {anio} no trae las columnas {faltan}; "
                    f"cabecera leida: {cabecera[:8]}")

    filas: List[Dict[str, Any]] = []
    for campos in lector:
        if len(campos) <= max(cols.values()):
            continue
        fecha = _fecha(campos[cols["fecha_informe"]])
        largos = _entero(campos[cols["no_comercial_largos"]])
        cortos = _entero(campos[cols["no_comercial_cortos"]])
        oi = _entero(campos[cols["interes_abierto"]])
        if fecha is None or largos is None or cortos is None or not oi:
            # Ausencia declarada por omision de la fila: una fila con
            # posicionamiento desconocido no puede entrar como cero en una
            # serie sobre la que despues se calcula una desviacion tipica.
            continue
        filas.append({
            "mercado": (campos[cols["mercado"]] or "").strip(),
            "fecha_informe": fecha.isoformat(),
            "fecha_publicacion": fecha_de_publicacion(fecha).isoformat(),
            "no_comercial_largos": largos,
            "no_comercial_cortos": cortos,
            "comercial_largos": _entero(campos[cols["comercial_largos"]]) if "comercial_largos" in cols else None,
            "comercial_cortos": _entero(campos[cols["comercial_cortos"]]) if "comercial_cortos" in cols else None,
            "interes_abierto": oi,
        })
    if not filas:
        return [], f"el fichero de {anio} no dejo ninguna fila utilizable"
    return filas, None


def _filas_del_anio(anio: int, offline: bool = False,
                    directorio: Optional[Any] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Filas del ano, de cache si existe. Un ano cerrado no se vuelve a descargar.

    La cache se guarda POR MERCADO (`escribir_cot`) y no por ano completo, para
    que un fichero pese kilobytes y no decenas de megas. Esta funcion solo se
    llama cuando falta el mercado pedido.
    """
    filas, motivo = ([], None) if offline else _descargar_anio(anio)
    if offline and not filas:
        motivo = f"modo offline y sin cache para {anio}"
    return filas, motivo


def serie_semanal(patron_mercado: str, as_of: Optional[str] = None,
                  semanas: int = 156, offline: bool = False,
                  directorio: Optional[Any] = None) -> Dict[str, Any]:
    """
    Serie semanal de posicionamiento del mercado que case con `patron_mercado`.

    `as_of` (YYYY-MM-DD) filtra por FECHA DE PUBLICACION, nunca por la del
    informe. En produccion se omite —la pregunta es que se sabe hoy— y existe
    para que el backtest no reintroduzca la fuga por descuido.

    Cuando varios mercados casan con el patron (el crudo cotiza en varias
    bolsas), se elige el de mayor interes abierto acumulado, con desempate
    alfabetico. Es una regla fija y declarada: sin ella, la eleccion dependeria
    del orden de las filas del fichero.
    """
    tope = date.fromisoformat(as_of) if as_of else date.today()
    anio_final = tope.year
    # `semanas` de historia mas el ano en curso, redondeado al alza.
    anio_inicial = anio_final - max(1, (semanas // 52) + 1)

    filas: List[Dict[str, Any]] = []
    fallos: List[str] = []
    for anio in range(anio_inicial, anio_final + 1):
        cacheado = macro_cache.leer_cot(patron_mercado, anio, directorio)
        if cacheado is not None and (macro_cache.anio_esta_cerrado(anio, tope) or offline):
            filas.extend(cacheado)
            continue
        del_anio, motivo = _filas_del_anio(anio, offline=offline, directorio=directorio)
        if motivo:
            if cacheado is not None:
                filas.extend(cacheado)
            else:
                fallos.append(f"{anio}: {motivo}")
            continue
        del_mercado = _elegir_mercado(del_anio, patron_mercado)
        macro_cache.escribir_cot(patron_mercado, anio, del_mercado, directorio)
        filas.extend(del_mercado)

    visibles = [f for f in filas if f["fecha_publicacion"] <= tope.isoformat()]
    visibles.sort(key=lambda f: f["fecha_informe"])
    # Deduplica por fecha de informe conservando la ultima aparicion, por si un
    # ano se solapa entre la cache y una descarga nueva.
    unicas: Dict[str, Dict[str, Any]] = {f["fecha_informe"]: f for f in visibles}
    serie = sorted(unicas.values(), key=lambda f: f["fecha_informe"])[-semanas:]

    return {
        "mercado": serie[-1]["mercado"] if serie else patron_mercado,
        "patron": patron_mercado,
        "as_of": tope.isoformat(),
        "n_semanas": len(serie),
        "serie": serie,
        "fallos": fallos,
    }


def _elegir_mercado(filas: List[Dict[str, Any]], patron: str) -> List[Dict[str, Any]]:
    """Filas del mercado que mejor case con el patron. Ver `serie_semanal`."""
    patron = (patron or "").upper()
    candidatas = [f for f in filas if patron in f["mercado"].upper()]
    if not candidatas:
        return []
    por_mercado: Dict[str, int] = {}
    for f in candidatas:
        por_mercado[f["mercado"]] = por_mercado.get(f["mercado"], 0) + f["interes_abierto"]
    elegido = sorted(por_mercado.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return [f for f in candidatas if f["mercado"] == elegido]
