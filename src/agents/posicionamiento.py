"""
Agente Analista de Posicionamiento y Precio de Entrada.

QUE RESUELVE
------------
El sistema decidia QUE comprar y CUANTO, pero nunca A QUE PRECIO: el Fund
Manager tomaba el ultimo cierre y median desde ahi el stop, el objetivo y el
tamano. Un stop medido desde un precio que no se ha pagado describe una
operacion que nadie hizo.

Este agente cruza tres senales y de ahi sale un precio de entrada objetivo:

  1. SESGO MACRO      posicionamiento de especuladores en futuros (COT de la
                      CFTC), por contrato de indice y por contrato sectorial.
                      Da DIRECCION.
  2. SESGO DE OPCIONES put/call ratio y skew en percentil historico, mas la
                      posicion frente al punto de inflexion de la gamma. Da
                      DIRECCION y, sobre todo, da NIVEL: los strikes de mayor
                      open interest, el max pain y el gamma flip son precios
                      concretos.
  3. MOMENTUM         `momentum_score` del Analista Tecnico. Da la senal propia
                      del valor.

Si las tres confirman y nada esta sobreextendido, se entra a mercado. Si
divergen, se exige un retroceso hasta el nivel de referencia.

POR QUE VA DESPUES DEL ANALISTA TECNICO Y NO EN PARALELO
--------------------------------------------------------
Porque consume lo que el tecnico escribe: `momentum_score` es la tercera pata de
la confluencia, `sobreextendido` es lo que prohibe perseguir el precio, y `atr`
es lo que acota el ajuste. Es una dependencia de datos real, del mismo tipo que
obliga a ordenar —y no paralelizar— los pasos dentro de `quality.py`.
Paralelizarlo no romperia el grafo: produciria un dictamen distinto, uno sin
comparacion de tres vias.

Ademas seria paralelismo sin ganancia: este agente no toca la red. La
recoleccion la hacen `obtener_contexto_macro` y `obtener_cadena_opciones`, que
pertenecen a la ingesta. Es el mismo argumento por el que `quality_analysis` va
secuencial antes del fan-out.

EL ORDEN DE LAS LLAMADAS NO ES INTERCAMBIABLE
---------------------------------------------
El sesgo macro necesita el contrato sectorial resuelto; el sesgo de opciones
necesita los percentiles y el punto de inflexion ya calculados; y el ajuste de
entrada necesita los dos sesgos Y el nivel. Reordenar no produce un error:
produce otro precio de entrada.

CAPA DE DECISION
----------------
`precio_entrada_objetivo` alimenta `calcular_niveles_riesgo` en el Fund Manager,
y por esa via el stop, el objetivo, el ratio riesgo/recompensa y el tamano de la
posicion. NO es capa asesora, a diferencia del Analista de Noticias.

EL NIVEL YA NO TIENE UN SOLO PROVEEDOR
---------------------------------------
Hasta la incorporacion del Analista de Estructura, los tres candidatos de nivel
salian los tres de la cadena de opciones, asi que su ausencia no degradaba el
bloque: lo ANULABA. Y como el historico de cadenas por ticker es de pago, en el
backtest la cadena esta siempre ausente y el ajuste era siempre `None`: el
estudio media un sistema sin ajuste de entrada mientras produccion si lo
aplicaba.

`soporte_estructural` es el cuarto candidato y el unico derivado del OHLCV, que
el sistema si tiene point-in-time. Con el, el estudio puede MEDIR el ajuste de
entrada sobre las 132 fechas de rebalanceo.

Lo que sigue sin medirse es el bloque de OPCIONES tal cual es: el nivel que el
backtest evalua sale de soportes de precio, NO de open interest ni de max pain.
La diferencia se nombra en `build_limitations()` en vez de promediarse.

INVARIANTE
----------
Ninguna de las cifras anteriores depende del LLM. El modelo solo puede
sobrescribir `summary`, y siempre despues de que todo este calculado. Se
verifica en `assert_llm_is_decision_neutral()`.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import AgenteBase, Traza
from src.config import (
    FUTURO_INDICE,
    SECTOR_DESCONOCIDO,
    get_llm,  # noqa: F401  - resuelto por modulo; ver AgenteBase._obtener_llm
    texto_de_respuesta_llm,  # noqa: F401
)
from src.prompts import SYSTEM_POSICIONAMIENTO, prompt_posicionamiento
from src.state import FinancialAnalysisState

NO_APLICABLE = "NO_APLICABLE"


class PositioningAnalystAgent(AgenteBase):
    """
    Precio de entrada objetivo a partir del posicionamiento en derivados.

    Capa de DECISION: su salida alimenta los niveles de riesgo y el tamano.
    """

    nombre = "posicionamiento"
    rol = "Analista de Posicionamiento y Entrada"
    system_prompt = SYSTEM_POSICIONAMIENTO

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        sector = state.get("sector") or SECTOR_DESCONOCIDO
        tech = state.get("technical_report", {}) or {}
        raw_tech = state.get("yfinance_data", {}).get("technical", {}) or {}
        futures = state.get("futures_data", {}) or {}
        opciones = state.get("options_data", {}) or {}
        estructura = state.get("estructura_report", {}) or {}
        regimen = state.get("regimen_report", {}) or {}

        precio = tech.get("close") or raw_tech.get("close") or 0.0
        atr = tech.get("atr") or raw_tech.get("atr") or 0.0
        momentum_score = tech.get("momentum_score")
        sobreextendido = bool(tech.get("sobreextendido"))

        macro = self._bloque_macro(sector, futures, traza)
        opc = self._bloque_opciones(precio, opciones, traza)

        # Comprar en el techo del canal de open interest es comprar contra la
        # oferta pendiente. Cuenta como sobreextension —misma familia que el RSI
        # extremo— y por tanto prohibe perseguir el precio. Es el caso que el
        # 2026-08-30 dejo a AAPL entrando a mercado en el percentil 98 de su
        # canal.
        sobreextendido = sobreextendido or opc["en_techo_del_canal"]

        # Dos banderas mas de la MISMA FAMILIA: ninguna cambia el signo de la
        # tesis, todas prohiben perseguir el precio. Se unen por `or` porque
        # cualquiera de ellas basta para cerrar la puerta, y ninguna puede
        # abrirla — que es lo que las hace monotonas por construccion, igual que
        # los vetos de `aplicar_vetos`.
        #
        #   · `soporte_lejano`: el valor cotiza sin referencia estructural debajo.
        #   · `puerta_regimen` cerrada: el mercado esta en tension o en panico, y
        #     comprar a mercado ahi es el "cuchillo cayendo" del repositorio 07.
        sobreextendido = (sobreextendido
                          or bool(estructura.get("soporte_lejano"))
                          or not regimen.get("puerta_regimen", True))

        entrada = self.usar_tool("ajustar_precio_entrada", {
            "precio": precio,
            "atr": atr,
            "sesgo_macro": macro["sesgo_macro"],
            "sesgo_opciones": opc["sesgo_opciones"],
            "momentum_score": momentum_score,
            "soporte_oi": opc["soporte_oi"],
            "max_pain": opc["max_pain"],
            "gamma_flip": opc["gamma_flip"],
            "max_pain_operable": opc["max_pain_operable"],
            "regimen_gamma": opc["regimen_gamma"],
            "sobreextendido": sobreextendido,
            # Cuarto candidato de nivel, y el UNICO que no depende de la cadena
            # de opciones. Sin el, en el backtest no habia ningun candidato y el
            # ajuste era None en el 100% de las senales.
            "soporte_estructural": estructura.get("soporte"),
        }, traza)

        estado = self._estado(macro, opc, estructura.get("soporte"))
        signals = self._signals(macro, opc, entrada)
        if estructura.get("soporte") is not None:
            signals.insert(-1, (
                f"Soporte estructural {estructura.get('soporte_origen')} en "
                f"{estructura['soporte']}"
                + (f" ({estructura['distancia_atr']:.2f} ATR por debajo)"
                   if estructura.get("distancia_atr") is not None else "")))
        if not regimen.get("puerta_regimen", True):
            signals.insert(-1, (
                f"Puerta de regimen CERRADA ({regimen.get('regimen_clasificacion')}): "
                f"prohibe perseguir el precio"))
        summary = self._resumen(ticker, precio, macro, opc, entrada)

        return {
            "status": estado,
            "sector": sector,
            "precio_mercado": round(precio, 2) if precio else None,
            # --- Bloque macro (DECISION via el veto de aplicar_vetos) ------
            "sesgo_macro": macro["sesgo_macro"],
            "sesgo_macro_clasificacion": macro["clasificacion"],
            "cot": macro["detalle"],
            "contrato_sectorial": macro["contrato_sectorial"],
            "posicionamiento_extremo": macro["extremo"],
            # --- Bloque de opciones (DECISION via el nivel de entrada) -----
            "sesgo_opciones": opc["sesgo_opciones"],
            "sesgo_opciones_clasificacion": opc["clasificacion"],
            "opciones": opc["detalle"],
            "soporte_oi": opc["soporte_oi"],
            "resistencia_oi": opc["resistencia_oi"],
            "max_pain": opc["max_pain"],
            "gamma_flip": opc["gamma_flip"],
            "gex_total": opc["gex_total"],
            "regimen_gamma": opc["regimen_gamma"],
            "posicion_en_canal": opc["posicion_en_canal"],
            "en_techo_del_canal": opc["en_techo_del_canal"],
            # --- Bloque de estructura de precio (DECISION via el nivel) -----
            # Cuarto candidato de nivel y el unico reconstruible point-in-time.
            "soporte_estructural": estructura.get("soporte"),
            "soporte_estructural_origen": estructura.get("soporte_origen"),
            "soporte_lejano": bool(estructura.get("soporte_lejano")),
            # --- Bloque de regimen (DECISION via la puerta y el veto) -------
            "regimen_clasificacion": regimen.get("regimen_clasificacion"),
            "puerta_regimen": bool(regimen.get("puerta_regimen", True)),
            # --- Combinacion ------------------------------------------------
            "entrada_clasificacion": entrada["entrada_clasificacion"],
            "confluencia": entrada["confluencia"],
            "sesgo_medio": entrada.get("sesgo_medio"),
            "componentes": entrada["componentes"],
            "componentes_disponibles": entrada["componentes_disponibles"],
            "nivel_referencia": entrada["nivel_referencia"],
            "nivel_origen": entrada["nivel_origen"],
            "ajuste_entrada_pct": entrada["ajuste_entrada_pct"],
            "precio_entrada_objetivo": entrada["precio_entrada_objetivo"],
            "motivo_entrada": entrada.get("motivo"),
            "detalle_entrada": entrada,
            "signals": signals,
            "resumen_determinista": summary,
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    def _bloque_macro(self, sector: str, futures: Dict[str, Any],
                      traza: Traza) -> Dict[str, Any]:
        """
        Sesgo macro: pata de indice (siempre) mas pata sectorial (si existe).

        El sector que no figura en `SECTOR_A_FUTURO` no recibe pata sectorial y
        se evalua solo con el indice. No se le asigna un proxy: forzar un
        contrato para un sector sin relacion clara produce un numero donde no
        hay senal.
        """
        contrato = self.usar_tool("resolver_contrato_sectorial", {"sector": sector}, traza)
        contratos = (futures or {}).get("contratos", {}) or {}

        patas: List[Dict[str, Any]] = [
            {"codigo": FUTURO_INDICE["contrato"], "papel": "indice",
             "signo": FUTURO_INDICE["signo"]},
        ]
        if contrato.get("es_aplicable"):
            patas.append({"codigo": contrato["contrato"], "papel": "sectorial",
                          "signo": contrato["signo"]})

        componentes: List[Dict[str, Any]] = []
        detalle: List[Dict[str, Any]] = []
        for pata in patas:
            datos = contratos.get(pata["codigo"], {}) or {}
            serie = (datos.get("cot", {}) or {}).get("serie", []) or []
            z = self.usar_tool("calcular_zscore_cot", {"serie": serie}, traza)
            componentes.append({"contrato": pata["codigo"], "papel": pata["papel"],
                                "z": z.get("z"), "signo": pata["signo"],
                                "extremo": z.get("extremo", False),
                                "motivo": z.get("motivo")})
            detalle.append({
                "contrato": pata["codigo"], "papel": pata["papel"],
                "mercado": (datos.get("cot", {}) or {}).get("mercado"),
                "signo": pata["signo"],
                "ultima_fecha_informe": (serie[-1]["fecha_informe"] if serie else None),
                "ultima_fecha_publicacion": (serie[-1]["fecha_publicacion"] if serie else None),
                "precio_continuo": (datos.get("precio", {}) or {}).get("close"),
                **{k: z.get(k) for k in ("z", "n_semanas", "posicion_neta", "media",
                                         "desviacion_tipica", "extremo", "motivo")},
            })

        clasificado = self.usar_tool("clasificar_sesgo_macro",
                                     {"componentes": componentes}, traza)
        return {
            "sesgo_macro": clasificado["sesgo_macro"],
            "clasificacion": clasificado["clasificacion"],
            "extremo": clasificado["extremo"],
            "detalle": detalle,
            "contrato_sectorial": (contrato.get("contrato")
                                   if contrato.get("es_aplicable") else None),
            "motivo_sector": contrato.get("motivo"),
        }

    # ------------------------------------------------------------------ #
    def _bloque_opciones(self, precio: float, opciones: Dict[str, Any],
                         traza: Traza) -> Dict[str, Any]:
        """
        Sesgo y niveles de la cadena.

        Sin cadena utilizable todo el bloque es NO_APLICABLE y los niveles son
        `None`. No hay valor por defecto: un cero se leeria como "sin sesgo de
        posicionamiento", que es una afirmacion sobre una cadena que aqui no
        existe.
        """
        vacio = {
            "sesgo_opciones": None, "clasificacion": NO_APLICABLE,
            "soporte_oi": None, "resistencia_oi": None, "max_pain": None,
            "max_pain_operable": False, "gamma_flip": None, "gex_total": None,
            "posicion_en_canal": None, "en_techo_del_canal": False,
            "regimen_gamma": NO_APLICABLE,
            "detalle": {"disponible": False,
                        "motivo": (opciones or {}).get("motivo",
                                                       "sin cadena de opciones en el estado")},
        }
        if not opciones or not opciones.get("disponible") or not precio:
            return vacio

        contratos = opciones.get("contratos", []) or []
        agregados = opciones.get("agregados", {}) or {}
        historico = opciones.get("historico", []) or []

        # El precio de referencia es el cierre del Analista Tecnico, no el
        # `spot` que guardo la cadena: una cadena servida de cache puede traer
        # el precio de una descarga anterior del mismo dia.
        pcr = self.usar_tool("calcular_put_call_ratio",
                             {"agregados": agregados, "historico": historico}, traza)
        niveles = self.usar_tool("identificar_niveles_oi",
                                 {"contratos": contratos, "spot": precio}, traza)
        maxpain = self.usar_tool("calcular_max_pain", {"contratos": contratos}, traza)
        gex = self.usar_tool("calcular_gamma_exposure",
                             {"contratos": contratos, "spot": precio}, traza)
        flip = self.usar_tool("localizar_gamma_flip",
                              {"contratos": contratos, "spot": precio}, traza)
        skew = self.usar_tool("calcular_skew",
                              {"agregados": agregados, "historico": historico}, traza)
        sesgo = self.usar_tool("clasificar_sesgo_opciones", {
            "posicion_en_canal": niveles.get("posicion_en_canal"),
            "skew_normalizado": skew.get("skew_normalizado"),
            "percentil_pcr": pcr.get("percentil_pcr"),
            "percentil_skew": skew.get("percentil_skew"),
            "gamma_flip": flip.get("gamma_flip"),
            "spot": precio}, traza)

        return {
            "sesgo_opciones": sesgo["sesgo_opciones"],
            "clasificacion": sesgo["clasificacion"],
            "soporte_oi": niveles.get("soporte_oi"),
            "resistencia_oi": niveles.get("resistencia_oi"),
            "max_pain": maxpain.get("max_pain"),
            "max_pain_operable": bool(maxpain.get("es_operable")),
            "posicion_en_canal": niveles.get("posicion_en_canal"),
            "en_techo_del_canal": bool(niveles.get("en_techo_del_canal")),
            "gamma_flip": flip.get("gamma_flip"),
            "gex_total": gex.get("gex_total"),
            "regimen_gamma": gex.get("regimen", NO_APLICABLE),
            "detalle": {
                "disponible": True,
                "oi_total": opciones.get("oi_total"),
                "n_dias_historico": opciones.get("n_dias_historico", 0),
                "minimo_dias_historico": opciones.get("minimo_dias_historico"),
                "desde_cache": opciones.get("desde_cache", False),
                "put_call": pcr,
                "niveles_oi": niveles,
                "max_pain": maxpain,
                "gamma": gex,
                "gamma_flip": flip,
                "skew": skew,
                "sesgo": sesgo,
            },
        }

    # ------------------------------------------------------------------ #
    @staticmethod
    def _estado(macro: Dict[str, Any], opc: Dict[str, Any],
                soporte_estructural: Optional[float] = None) -> str:
        """
        Tres estados segun cuantos bloques hayan podido evaluarse.

        El soporte estructural cuenta como fuente de NIVEL, igual que el soporte
        de open interest: sin cadena pero con estructura el bloque sigue
        produciendo un precio de entrada, y por eso el estado ya no es
        DATOS_INSUFICIENTES en el backtest.
        """
        hay_macro = macro["sesgo_macro"] is not None
        hay_nivel = (opc["sesgo_opciones"] is not None
                     or opc["soporte_oi"] is not None
                     or soporte_estructural is not None)
        if hay_macro and hay_nivel:
            return "SUCCESS"
        if hay_macro or hay_nivel:
            return "DEGRADADO"
        return "DATOS_INSUFICIENTES"

    @staticmethod
    def _signals(macro: Dict[str, Any], opc: Dict[str, Any],
                 entrada: Dict[str, Any]) -> List[str]:
        senales: List[str] = []
        for pata in macro["detalle"]:
            if pata.get("z") is not None:
                senales.append(
                    f"COT {pata['contrato']} ({pata['papel']}): z={pata['z']:+.2f} sobre "
                    f"{pata['n_semanas']} semanas, informe del {pata['ultima_fecha_informe']} "
                    f"publicado el {pata['ultima_fecha_publicacion']}"
                    + (" — posicionamiento EXTREMO" if pata.get("extremo") else ""))
            else:
                senales.append(f"COT {pata['contrato']} ({pata['papel']}): no evaluable "
                               f"({pata.get('motivo')})")
        if opc["detalle"].get("disponible"):
            d = opc["detalle"]
            senales.append(
                f"Put/call por open interest {d['put_call'].get('pcr_oi')} "
                f"(percentil {d['put_call'].get('percentil_pcr')}, "
                f"{d['put_call'].get('status')})")
            senales.append(
                f"Niveles de la cadena: soporte {opc['soporte_oi']}, "
                f"resistencia {opc['resistencia_oi']}, max pain {opc['max_pain']} "
                f"({'operable' if opc['max_pain_operable'] else 'lejos del vencimiento'}), "
                f"gamma flip {opc['gamma_flip']}")
            senales.append(f"Regimen de gamma: {opc['regimen_gamma']} "
                           f"(exposicion {opc['gex_total']})")
            if opc["posicion_en_canal"] is not None:
                senales.append(
                    f"Posicion en el canal de open interest: "
                    f"{opc['posicion_en_canal']:.0%} "
                    + ("(TECHO: se compraria contra la oferta pendiente)"
                       if opc["en_techo_del_canal"] else "(hay recorrido al alza)"))
        else:
            senales.append(f"Cadena de opciones no utilizable: "
                           f"{opc['detalle'].get('motivo')}")
        senales.append(
            f"Confluencia {entrada.get('confluencia')} sobre "
            f"{len(entrada.get('componentes_disponibles', []))} componente(s) "
            f"-> {entrada['entrada_clasificacion']}")
        return senales

    @staticmethod
    def _resumen(ticker: str, precio: float, macro: Dict[str, Any],
                 opc: Dict[str, Any], entrada: Dict[str, Any]) -> str:
        if entrada["ajuste_entrada_pct"] is None:
            return (
                f"Posicionamiento de {ticker}: sesgo macro {macro['clasificacion']}"
                + (f" ({macro['sesgo_macro']:+.2f})" if macro["sesgo_macro"] is not None else "")
                + f" y cadena de opciones {opc['clasificacion']}. "
                f"No se emite ajuste de entrada: {entrada.get('motivo')}. "
                f"La entrada se toma al precio de mercado "
                f"({f'${precio:.2f}' if precio else 'no disponible'}).")

        ajuste = entrada["ajuste_entrada_pct"]
        return (
            f"Posicionamiento de {ticker}: sesgo macro {macro['clasificacion']}"
            + (f" ({macro['sesgo_macro']:+.2f})" if macro["sesgo_macro"] is not None else "")
            + f", cadena de opciones {opc['clasificacion']}"
            + (f" ({opc['sesgo_opciones']:+.2f})" if opc["sesgo_opciones"] is not None else "")
            + f" y regimen de gamma {opc['regimen_gamma']}. "
            f"Confluencia {entrada['confluencia']:.0%} -> {entrada['entrada_clasificacion']}: "
            + (f"entrada a mercado en ${precio:.2f}." if ajuste == 0.0 else
               f"entrada objetivo ${entrada['precio_entrada_objetivo']:.2f} "
               f"({ajuste:+.2%} sobre los ${precio:.2f} de mercado), apoyada en "
               f"{entrada['nivel_origen']} en {entrada['nivel_referencia']}."))

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        return prompt_posicionamiento(state.get("ticker", "UNKNOWN"), informe)

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        ajuste = informe.get("ajuste_entrada_pct")
        return (f"entrada {informe.get('entrada_clasificacion')} · "
                f"ajuste {'n/d' if ajuste is None else f'{ajuste:+.2%}'} · "
                f"macro {informe.get('sesgo_macro_clasificacion')} · "
                f"opciones {informe.get('sesgo_opciones_clasificacion')}")
