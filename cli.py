"""
Punto de entrada del análisis en vivo.

Antes recorría los tickers de forma independiente y volcaba una ficha por
valor. Ahora, además, carga UNA sola vez la referencia de mercado, construye la
cartera agregada con la matriz de correlaciones real y genera tres documentos:
el resumen ejecutivo, el informe completo y una ficha de detalle por compañía
con la traza de las herramientas que produjeron cada dictamen.

La diferencia importa: recomendar cuatro posiciones sin mirar cómo se
relacionan entre sí es recomendar concentración disfrazada de diversificación.
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# Codificación UTF-8 para la consola de Windows: los informes llevan acentos y
# emoji, y cp1252 los rompe.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from src.config import (
    CAPITAL_BASE, META_ARTEFACTO, META_HABILITADO, MEMORIA_DIR, OUTPUT_DIR,
    REFLEXION_HORIZONTE_SESIONES,
)
from src.data.fetcher import DataFetcher
from src.graph.workflow import (
    cargar_benchmark, cargar_contexto_macro, cargar_regimen, run_stock_analysis,
)
from src.memoria import MemoriaReflexion
from src.meta import ArtefactoAnacronico, ArtefactoIlegible, cargar_para
from src.portfolio import PortfolioConstructor
from src.utils.logging_agentes import configurar_logging, ruta_de_traza
from src.utils.report_generator import ReportGenerator

SIN_DATO = "n/d"
RUTA_MEMORIA = os.path.join(MEMORIA_DIR, "reflexion.jsonl")


def _resolver_produccion(benchmark_ticker: str = "SPY"):
    """
    Resolver de rentabilidad en exceso para la memoria de reflexión en vivo.

    Baja los cierres UNA vez por ticker y los reutiliza: la memoria pregunta por
    observación, y sin la caché una instalación con un año de historia abriría
    cientos de peticiones. Solo se descargan los tickers que tienen alguna
    observación vencida, porque `consolidar_hasta` resuelve de forma perezosa.

    La descarga la hace `obtener_cierres_historicos`, en `src/tools/extraccion.py`:
    ese módulo sigue siendo el único que sale a la red.
    """
    from src.tools.extraccion import obtener_cierres_historicos

    hoy = pd.Timestamp.today().normalize()
    desde = str((hoy - pd.Timedelta(days=1200)).date())
    hasta = str((hoy + pd.Timedelta(days=1)).date())
    cache: dict = {}

    def _serie(ticker: str):
        clave = ticker.upper()
        if clave not in cache:
            try:
                datos = obtener_cierres_historicos.invoke(
                    {"ticker": clave, "desde": desde, "hasta": hasta})
                cierres = datos.get("cierres") or {}
                serie = pd.Series(cierres, dtype=float)
                serie.index = pd.to_datetime(serie.index)
                cache[clave] = serie.sort_index()
            except Exception:
                cache[clave] = pd.Series(dtype=float)
        return cache[clave]

    def _cierre(serie: pd.Series, fecha: pd.Timestamp):
        if serie is None or serie.empty:
            return None
        previos = serie.loc[serie.index <= fecha]
        return float(previos.iloc[-1]) if len(previos) else None

    def _resolver(ticker: str, f0, f1):
        serie = _serie(ticker)
        p0, p1 = _cierre(serie, f0), _cierre(serie, f1)
        if not p0 or not p1:
            return None
        ret = p1 / p0 - 1.0
        bench = _serie(benchmark_ticker)
        b0, b1 = _cierre(bench, f0), _cierre(bench, f1)
        if b0 and b1:
            ret -= (b1 / b0 - 1.0)
        return ret

    return _resolver


def _tabla_ejecutiva(resultados):
    """Resumen ejecutivo en terminal: una línea por valor, la decisión primero."""
    if not resultados:
        return

    cab = (f"{'TICKER':<8}{'ESTILO':<22}{'CONV':>6}{'MOM':>7}"
           f"{'DICTAMEN':>16}{'PESO':>8}{'STOP':>10}{'OBJETIVO':>10}")
    print("\n" + "=" * len(cab))
    print(" RESUMEN EJECUTIVO")
    print("=" * len(cab))
    print(cab)
    print("-" * len(cab))

    for r in resultados:
        q = r.get("quality_report", {}) or {}
        t = r.get("technical_report", {}) or {}
        fd = r.get("final_decision", {}) or {}
        conv = (q.get("conviccion_fundamental") or {}).get("valor")
        mom = t.get("momentum_score")
        stop = fd.get("stop_loss_atr")
        objetivo = fd.get("take_profit_atr")
        print(
            f"{r.get('ticker', '?'):<8}"
            f"{(q.get('style_classification') or SIN_DATO)[:21]:<22}"
            f"{(f'{conv:.0f}' if conv is not None else SIN_DATO):>6}"
            f"{(f'{mom:+.0f}' if mom is not None else SIN_DATO):>7}"
            f"{fd.get('rating', SIN_DATO):>16}"
            f"{fd.get('peso_objetivo', 0.0):>7.2%} "
            f"{(f'${stop:.2f}' if stop else SIN_DATO):>10}"
            f"{(f'${objetivo:.2f}' if objetivo else SIN_DATO):>10}"
        )
    print("-" * len(cab))


def _mostrar_detalle(ticker: str) -> int:
    """Vuelca por pantalla la ficha pormenorizada de un valor ya analizado."""
    ruta = os.path.join(OUTPUT_DIR, "detalle", f"{ticker.upper()}.md")
    if not os.path.exists(ruta):
        print(f"\nNo hay ficha de {ticker.upper()} en {ruta}.")
        print("Analízalo primero:  python cli.py --tickers " + ticker.upper())
        return 1
    with open(ruta, encoding="utf-8") as f:
        print(f.read())
    return 0


def _investigar(ticker: str, pregunta: str) -> int:
    """
    Agente ReAct asesor, bajo demanda.

    Fuera de la ejecución diaria a propósito: encadena varias llamadas al
    proveedor y exige clave. Su respuesta no altera ningún rating, ningún peso
    ni ningún nivel de riesgo — ver `src/agents/investigador.py`.
    """
    from src.agents.investigador import LLMNoConfigurado
    from src.graph.investigacion import investigar

    print(f"\n[Investigador] {ticker.upper()}: {pregunta}\n")
    try:
        r = investigar(ticker, pregunta)
    except LLMNoConfigurado as e:
        print(f"  {e}")
        return 1

    print(f"  Herramientas consultadas: {', '.join(r['tools_invocadas']) or 'ninguna'}\n")
    print(r["respuesta"])
    print("\n  (Capa asesora: esta respuesta no modifica ningún dictamen del sistema.)\n")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Sistema Multi-Agente de Análisis Financiero de Selección de Élite")
    parser.add_argument("--tickers", "-t", type=str, default="NVDA,AAPL,MSFT,TSLA,INTC",
                        help="Lista de tickers separados por comas (ej. NVDA,AAPL,MSFT)")
    parser.add_argument("--benchmark", "-b", type=str, default="SPY",
                        help="Índice de referencia para el momentum relativo (por defecto SPY)")
    parser.add_argument("--capital", type=float, default=CAPITAL_BASE,
                        help="Capital de referencia para dimensionar la cartera")
    parser.add_argument("--sin-benchmark", action="store_true",
                        help="Omite la descarga del índice; el momentum se reporta en absoluto")
    parser.add_argument("--sin-macro", action="store_true",
                        help="Omite la descarga de futuros y COT; el sesgo macro se "
                             "declara no aplicable y no hay ajuste de precio de entrada")
    parser.add_argument("--sin-regimen", action="store_true",
                        help="omite la serie de volatilidad implícita: sin veto de "
                             "régimen ni puerta")
    parser.add_argument("--sin-cartera", action="store_true",
                        help="Omite la construcción de cartera y el cálculo de correlaciones")
    parser.add_argument("--con-reflexion", action="store_true",
                        help="Activa la memoria de reflexión en la DECISIÓN. Desactivada por "
                             "defecto: el contraste 2015-2025 la refutó (percentil frente a "
                             "selección aleatoria 7.4 -> 3.1). Sin la bandera, las señales se "
                             "siguen archivando pero ningún peso se recorta")
    parser.add_argument("--detalle", type=str, metavar="TICKER",
                        help="Vuelca por pantalla la ficha pormenorizada de un valor ya analizado")
    parser.add_argument("--investigar", type=str, nargs=2, metavar=("TICKER", "PREGUNTA"),
                        help="Agente ReAct asesor: responde una pregunta consultando las "
                             "herramientas reales. Requiere LLM configurado y no altera "
                             "ningún dictamen")
    parser.add_argument("--log", type=str, default="WARNING",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Detalle del log en CONSOLA. El fichero JSONL de "
                             "output/logs/ se escribe siempre completo")
    args = parser.parse_args()

    # Los dos modos de consulta no analizan nada: salen antes de tocar la red.
    if args.detalle:
        return _mostrar_detalle(args.detalle)
    if args.investigar:
        configurar_logging(args.log, args.investigar[0])
        return _investigar(args.investigar[0], args.investigar[1])

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    configurar_logging(args.log, ticker=tickers[0] if len(tickers) == 1 else None)

    print("\n=======================================================")
    print(" SISTEMA MULTI-AGENTE DE ANÁLISIS FINANCIERO (LangGraph)")
    print("=======================================================\n")
    print(f" Analizando {len(tickers)} empresa(s): {', '.join(tickers)}\n")

    # --- Referencia de mercado, una sola vez para todo el lote ------------
    benchmark = {}
    if not args.sin_benchmark:
        print(f"[0/{len(tickers)}] Cargando referencia de mercado ({args.benchmark})...")
        benchmark = cargar_benchmark(args.benchmark)
        if benchmark:
            r12 = benchmark.get("change_12m_pct")
            volatilidad = benchmark.get("volatilidad_anual")
            print(f"    -> {benchmark['ticker']}: 12m "
                  f"{f'{r12:+.1%}' if r12 is not None else 'n/d'}\n"
                f"volatilidad {f'{volatilidad:.1%}' if volatilidad is not None else 'n/d'} · "
                  )
        else:
            print("    -> No disponible. El momentum se calculará en términos absolutos.\n")

    # --- Posicionamiento en futuros, una sola vez para todo el lote -------
    # El COT no es un dato por ticker: el sesgo del futuro del petróleo es el
    # mismo para todas las energéticas del lote y se publica una vez por semana.
    # Descargarlo dentro del bucle sería pedir el mismo fichero de la CFTC una
    # vez por valor. Mismo patrón que el benchmark.
    macro = {}
    if not args.sin_macro:
        print("[0/{}] Cargando posicionamiento en futuros (COT de la CFTC)...".format(
            len(tickers)))
        macro = cargar_contexto_macro()
        if macro.get("contratos"):
            ok = ", ".join(macro.get("fuentes_ok", [])) or "ninguno"
            print(f"    -> {len(macro['contratos'])} contrato(s), con COT: {ok}\n")
        else:
            print("    -> No disponible. El sesgo macro se declarará no aplicable.\n")

    # --- Régimen de volatilidad, una sola vez para todo el lote -----------
    # Cuarto caso del mismo patrón, y el más literal de todos: el nivel del VIX
    # de una fecha es exactamente el mismo número para las cincuenta empresas
    # del lote. Descargarlo dentro del bucle sería pedir la misma serie de FRED
    # una vez por valor.
    regimen = {}
    if not args.sin_regimen:
        print("[0/{}] Cargando régimen de volatilidad (VIX vía ALFRED)...".format(
            len(tickers)))
        regimen = cargar_regimen()
        series = (regimen.get("series") or {})
        if regimen.get("disponible"):
            corto = series.get(regimen.get("serie_volatilidad"), {})
            obs = corto.get("observaciones") or []
            print(f"    -> {corto.get('serie')}: {len(obs)} observación(es), "
                  f"última {obs[-1]['fecha'] if obs else 'n/d'} "
                  f"= {obs[-1]['valor'] if obs else 'n/d'}\n")
        else:
            fallo = (regimen.get("fallos") or ["sin dosier"])[0]
            print(f"    -> No disponible ({fallo}). El régimen se declarará no "
                  f"aplicable y no se aplicará ningún veto.\n")

    # --- Memoria de reflexión, una sola vez para todo el lote -------------
    # Qué hizo el precio DESPUÉS de las señales que este sistema emitió en el
    # pasado. Mismo patrón que el benchmark y el COT: la tabla es común a todo
    # el lote y se consolida una vez. `consolidar_hasta(hoy)` solo incorpora
    # observaciones ya desenlazadas, así que una instalación reciente encuentra
    # la capa inactiva y lo declara en vez de inventarse una expectativa.
    # POR DEFECTO SE ARCHIVA PERO NO SE DECIDE. El contraste de 2015-2025 refutó
    # esta capa —percentil frente a selección aleatoria 7.4 → 3.1, expectativa
    # por operación +1.23% → +0.95%—, así que el dosier viaja vacío y ningún peso
    # se recorta. Seguir archivando cuesta un fichero de texto y es lo que
    # permitirá reevaluarla algún día con datos que no sean los mismos con los
    # que se refutó.
    memoria = MemoriaReflexion(resolver=_resolver_produccion(args.benchmark))
    leidas = memoria.cargar(RUTA_MEMORIA)
    dosier = {}
    if args.con_reflexion:
        print(f"[0/{len(tickers)}] Consolidando memoria de reflexión...")
        dosier = memoria.dosier(pd.Timestamp.today().normalize())
        if dosier.get("evaluable"):
            print(f"    -> {leidas} señal(es) archivada(s), "
                  f"{dosier['n_total']} ya desenlazada(s); "
                  f"exceso medio {dosier['media_global']:+.2%} "
                  f"a {dosier['horizonte_sesiones']} sesiones\n")
        else:
            print(f"    -> {dosier.get('motivo')}. La capa no ajustará ningún peso.\n")

    # --- Meta-modelo, una sola vez para todo el lote ----------------------
    # A diferencia del régimen o del COT, esto NO es un dosier compartido: cada
    # valor tiene su propia probabilidad. Lo que se resuelve una vez es la CARGA
    # del artefacto, que es cara y común.
    #
    # `cargar_para` levanta si el artefacto vio el futuro de hoy. En producción
    # eso no puede pasar —hoy es hoy— pero la comprobación se hace igual: es la
    # misma función que usa el backtest, y una segunda ruta de carga sin
    # verificación sería justo el agujero que ese control existe para tapar.
    meta_art = None
    if META_HABILITADO:
        print(f"[0/{len(tickers)}] Cargando meta-modelo...")
        try:
            meta_art = cargar_para(Path(META_ARTEFACTO),
                                   str(pd.Timestamp.today().date()))
            print(f"    -> entrenado con {meta_art.n_muestras} etiquetas hasta "
                  f"{meta_art.entrenado_hasta}, tasa base {meta_art.tasa_base:.1%}\n")
        except (ArtefactoIlegible, ArtefactoAnacronico) as exc:
            print(f"    -> No disponible ({exc}). El factor del meta-modelo será 1.0 "
                  f"y no se recortará ningún peso.\n")

    resultados = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Procesando {ticker}...")
        try:
            res = run_stock_analysis(ticker, benchmark_data=benchmark,
                                     macro_data=macro, reflexion_data=dosier,
                                     regimen_data=regimen, meta_artefacto=meta_art)
            resultados.append(res)

            fd = res.get("final_decision", {}) or {}
            q = res.get("quality_report", {}) or {}
            fr = res.get("fundamental_report", {}) or {}
            conviccion = (q.get("conviccion_fundamental") or {}).get("valor")
            n_tools = sum(len((r or {}).get("_traza", {}).get("tools", []))
                          for r in (q, fr, res.get("technical_report"),
                                    res.get("positioning_report"),
                                    res.get("news_report"), res.get("debate_report"), fd))

            print(f"    -> Filtro fundamental: {fr.get('status', 'N/A')}")
            print(f"    -> Estilo: {q.get('style_classification', 'n/d')} "
                  f"(convicción {conviccion if conviccion is not None else 'n/d'}/100)")
            print(f"    -> Dictamen: {fd.get('rating', 'N/A')} "
                  f"| peso {fd.get('peso_objetivo', 0.0):.2%}")
            pos = res.get("positioning_report") or {}
            if pos:
                aj = pos.get("ajuste_entrada_pct")
                print(f"    -> Entrada: {pos.get('entrada_clasificacion')} "
                      + ("(al precio de mercado)" if aj is None
                         else f"{aj:+.2%} -> ${pos.get('precio_entrada_objetivo')}"))
            print(f"    -> {n_tools} herramienta(s) invocada(s) · "
                  f"{len(res.get('messages', []))} mensaje(s) en la traza")
            if q.get("banderas_rojas"):
                print(f"    -> Banderas rojas: {len(q['banderas_rojas'])}")
            print()
        except Exception as e:
            print(f"    ERROR al analizar {ticker}: {type(e).__name__}: {e}\n")

    # --- Archivo de las señales de hoy ------------------------------------
    # Se anota DESPUÉS de decidir, nunca antes: meter la señal de hoy en el
    # dosier de hoy sería look-ahead, y del silencioso. Se archivan TODOS los
    # valores analizados, no solo las compras: la reflexión de bajo nivel vive
    # precisamente de que el sistema evalúa cincuenta valores y compra cinco.
    if resultados:
        hoy = pd.Timestamp.today().normalize()
        desenlace = hoy + pd.tseries.offsets.BDay(REFLEXION_HORIZONTE_SESIONES)
        for res in resultados:
            q = res.get("quality_report", {}) or {}
            t = res.get("technical_report", {}) or {}
            memoria.anotar(hoy, res.get("ticker", "?"),
                           q.get("style_classification"),
                           t.get("momentum_classification"), desenlace)
        try:
            memoria.guardar(RUTA_MEMORIA)
            print(f"Memoria de reflexión: {len(resultados)} señal(es) archivada(s) "
                  f"en {RUTA_MEMORIA}; se desenlazarán el {desenlace.date()}.\n")
        except Exception as e:
            print(f"    Advertencia: no se pudo guardar la memoria de reflexión ({e}).\n")

    # --- Cartera agregada -------------------------------------------------
    cartera = None
    if resultados and not args.sin_cartera:
        print("Construyendo cartera (correlaciones, límites sectoriales, presupuesto de riesgo)...")
        series = {}
        try:
            series = DataFetcher().fetch_series_precios([r.get("ticker") for r in resultados])
        except Exception as e:
            print(f"    Advertencia: no se pudieron descargar las series conjuntas ({e}). "
                  f"La cartera se construirá sin penalización por correlación.")
        cartera = PortfolioConstructor(capital=args.capital).construir(resultados, series)
        print(f"    -> {len(cartera.posiciones)} posición(es) · "
              f"exposición bruta {cartera.exposicion_bruta:.2%} · "
              f"liquidez {cartera.liquidez:.2%} · "
              f"riesgo agregado {cartera.riesgo_total:.2%}\n")

    reporter = ReportGenerator()
    ruta = reporter.generate_daily_selection(resultados, cartera=cartera, benchmark=benchmark)

    _tabla_ejecutiva(resultados)

    print(f"\n Resumen ejecutivo : {ruta}")
    print(f" Informe completo  : {os.path.join(OUTPUT_DIR, 'daily_selection.md')}")
    print(f" Detalle por valor : {os.path.join(OUTPUT_DIR, 'detalle')}"
          f"  (o `python cli.py --detalle {tickers[0]}`)")
    print(f" Traza estructurada: {ruta_de_traza(tickers[0] if len(tickers) == 1 else None)}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
