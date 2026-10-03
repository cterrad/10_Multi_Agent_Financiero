# Catálogo de fuentes de datos — coste cero e historia reconstruible

> Fase 1 (Loop S) del encargo `prompts/entry_precision_agents_prompt.md`.
> Se detuvo en la **iteración 18 de 25** por la regla de parada temprana: tres
> iteraciones consecutivas (16, 17, 18) no cualificaron ninguna fuente nueva.
>
> **Cada iteración lleva una recuperación real.** La documentación de un
> proveedor es una afirmación; un cuerpo de respuesta es evidencia. Las
> iteraciones sin PROOF no se han contado.

## La puerta, y por qué no se negocia

| Clase | ¿Puede alimentar la decisión? |
|---|---|
| **PIT-NATIVE** | Sí, desde el primer día. |
| **PIT-ARCHIVABLE** | **No**, hasta que el archivo local cubra la ventana del estudio. |
| **NO-HISTORY** | **Nunca.** Solo capa asesora, excluida del replay y declarada ausente. |

**Ningún número que llegue a una decisión puede venir de una fuente que no se
pueda reproducir.** Si eso deja a un agente sin insumos, el agente no se entrega
y se reporta como resultado negativo.

---

## Resultado en una tabla

| # | Fuente | Clase | Uso | Qué cierra |
|---|---|---|---|---|
| **S4** | **Histórico OHLCV del propio anfitrión (`PriceStore`)** | **PIT-NATIVE** | **Ruta de decisión** | **El monopolio de la cadena de opciones sobre el NIVEL de entrada.** Ver §«El hallazgo». |
| S1 | FRED/ALFRED `VIXCLS` | PIT-NATIVE | Ruta de decisión | D1 — puerta de régimen macro |
| S2 | FRED/ALFRED `VXVCLS` (VIX 3M) | PIT-NATIVE | Ruta de decisión | D1 — estructura temporal de la volatilidad |
| S3 | FRED/ALFRED `WALCL`, `WRESBAL`, `RRPONTSYD`, `DGS10`, `DGS2`, `T10Y2Y` | PIT-NATIVE | Ruta de decisión | D2 — liquidez y tipos |
| S5 | CFTC COT | PIT-NATIVE | Ruta de decisión | Ya integrada (precedente del sistema) |
| S6 | SEC EDGAR `companyfacts` | PIT-NATIVE | Ruta de decisión | Ya integrada |
| S7 | Factores diarios Fama-French | PIT-ARCHIVABLE | **Solo estudio** | D6 — alfa ajustada por factores |
| S8 | Curva diaria del Tesoro de EEUU | PIT-NATIVE | Redundante con S3 | — |
| S9 | Índice diario de EDGAR (`daily-index`) | PIT-NATIVE | Solo estudio (frontera) | D9 — la única vía gratuita a un `NewsStore` |
| S10 | SEC Financial Statement Data Sets | PIT-NATIVE | Descartada por coste de recarga | Redundante con S6 |
| S11 | Volumen de venta en corto de FINRA | PIT-ARCHIVABLE | **Solo estudio** (2018-10→) | D4 **parcialmente** — no cubre 2015-2018 |
| S12 | Cadena de opciones por ticker (yfinance) | PIT-ARCHIVABLE | Producción sí, backtest no | Sin cambios |
| S13 | Ratio put/call de CBOE | **DESCONTINUADA** | **DISCARD** | Nada. Ver §S13. |
| S14 | Interés corto consolidado de FINRA | No cualificada | DISCARD | — |
| S15 | EOD independiente (Stooq) | No cualificada | DISCARD | — |
| S16 | Composición histórica del índice (Wikipedia) | NO-HISTORY | DISCARD | **No cierra D7.** |
| S17 | Diferencial *high yield* ICE BofA | Cobertura insuficiente | DISCARD | — |
| S18 | Cadenas de opciones históricas por ticker | De pago | DISCARD | — |

---

## EL HALLAZGO — la fuente cualificada que ya estaba dentro del repositorio

El encargo pide *«una sustitución PIT-native y gratuita de algo que el sistema
obtiene hoy de una fuente sin historia»*. La respuesta no es una API externa.

**El `nivel_referencia` del ajuste de entrada sale HOY, en exclusiva, de la
cadena de opciones** ([decision.py:575-582](src/tools/decision.py#L575-L582)):
`SOPORTE_OI`, `GAMMA_FLIP` y `MAX_PAIN`, los tres. Sin cadena no hay candidatos,
el ajuste es `None` y la entrada es el precio de mercado. En el backtest la
cadena está siempre ausente, así que **el ajuste de entrada es siempre nulo** y
la limitación nº 5 del informe dice, con razón, que el estudio mide un sistema
distinto del que decide en vivo.

Pero *«nivel de precio al que probablemente vuelva el valor»* **no es una
pregunta que solo sepa responder una cadena de opciones.** Es la pregunta que el
repo 07 responde con OHLCV puro:

- `add_liquidity` → mínimo de la sesión anterior, mínimo de la semana anterior,
  número redondo más cercano. Todo con `shift(1)`, causal por construcción.
- `_donchian_frame` (repo 06) → canal alto/bajo de N sesiones.

Y el anfitrión **ya tiene ese dato, point-in-time, cacheado y protegido por un
test**:

| Propiedad | Evidencia |
|---|---|
| Cobertura | `data/cache/prices/`: 51 valores, `AAPL` de 2013-11-27 a 2025-12-30, 3 040 sesiones. |
| Columnas | `Open, High, Low, Close, Volume` — el OHLC completo que los niveles necesitan. |
| Corte point-in-time | `PriceStore.window(ticker, as_of, lookback_days)` corta en `as_of` **inclusive** ([data.py:230](src/backtest/data.py#L230)). |
| Protección | `test_no_lookahead_future_prices_do_not_change_past_signal` ya fija exactamente esta propiedad. |
| Coste | Cero. Ya descargado. `--offline` lo reproduce. |

**El monopolio de la cadena sobre el nivel no es una limitación de datos: es una
decisión de diseño.** Y es la decisión que hace que el ajuste de entrada sea
inmedible. Sustituirla —o mejor, complementarla— convierte un
`UNMEASURABLE-WITH-CURRENT-DATA` en algo que el backtest puede medir sobre las
132 fechas de rebalanceo del estudio completo, sin comprar nada y sin esperar a
que un archivo madure.

Esa es la fuente más valiosa de esta fase, y estaba dentro del repositorio.

---

# LEDGER DEL LOOP S

## ITER 1/25 — FRED/ALFRED, interfaz de archivo

```
SOURCE      Federal Reserve Economic Data (St. Louis Fed) — api.stlouisfed.org.
            Interfaz ALFRED via los parametros realtime_start / realtime_end.
COST        Gratuita. Clave requerida (registro instantaneo). Presente en .env,
            32 caracteres, verificada contra la API.
VINTAGE     realtime_start=realtime_end=T devuelve la serie TAL Y COMO SE CONOCIA
            en T. Mecanismo nombrado y verificado, no inferido de la doc.
COVERAGE    Depende de la serie. Ver iteraciones 2-5.
REVISIONS   Depende de la serie. Ver ITER 5.
LAG         IMPUESTO POR LA API. Ver ITER 4 — es la prueba clave de esta fase.
BACKFILL    1 peticion por serie y por fecha de corte, o 1 peticion por serie con
            realtime_start=1776-07-04 para traer TODOS los vintages de golpe.
CLASS       PIT-NATIVE
USE         Ruta de decision
CLOSES      D1, D2. Es el mecanismo, no la serie.
PROOF       DGS10, vintage 2016-06-01, observaciones 2016-05-20..31:
            {"realtime_start":"2016-06-01","realtime_end":"2016-06-01",...,
             "observations":[{"date":"2016-05-20","value":"1.85"}, ...]}  count=8
LEDGER      [S-mecanismo: ALFRED]
```

## ITER 2/25 — `VIXCLS` (índice de volatilidad CBOE)

```
SOURCE      FRED VIXCLS — cierre diario del VIX.
COST        Gratuita (misma clave).
VINTAGE     Verificado con realtime_start=realtime_end=2018-03-01.
COVERAGE    1990-01-02 -> 2026-09-03. Diaria. Cubre la ventana entera con
            un ano largo de margen para la ventana z de 60 sesiones.
REVISIONS   NO SE REVISA. Ver ITER 5.
LAG         Cero: el cierre del dia es visible ese mismo dia. Ver ITER 4.
BACKFILL    1 peticion. ~9 000 observaciones.
CLASS       PIT-NATIVE
USE         Ruta de decision
CLOSES      D1 — es el insumo de la puerta de regimen macro del repo 07.
PROOF       Vintage 2018-03-01, ventana 2018-02-01..09 (el episodio "Volmageddon"):
              2018-02-01 13.47 | 2018-02-02 17.31 | 2018-02-05 37.32
              2018-02-06 29.98 | 2018-02-07 27.73 | 2018-02-08 33.46
              2018-02-09 29.06   -- 7 observaciones, todas con realtime 2018-03-01
LEDGER      [ALFRED, S1:VIXCLS]
```

## ITER 3/25 — `VXVCLS` (VIX a 3 meses) — estructura temporal

```
SOURCE      FRED VXVCLS — indice de volatilidad del S&P 500 a 3 meses.
COST        Gratuita.
VINTAGE     Mismo mecanismo.
COVERAGE    2007-12-04 -> 2026-09-03, diaria. Cubre la ventana entera.
            VIX9DCLS: NO EXISTE en FRED (comprobado, no asumido).
REVISIONS   No revisada (misma familia que VIXCLS).
LAG         Cero.
BACKFILL    1 peticion.
CLASS       PIT-NATIVE
USE         Ruta de decision
CLOSES      D1 ampliado: el cociente VIX/VIX3M mide si la curva de volatilidad
            esta invertida — el estres es INMEDIATO, no de fondo. Discrimina
            mejor que el nivel a secas, que es el unico input de la puerta de 07.
PROOF       {"id":"VXVCLS","frequency_short":"D","observation_start":"2007-12-04",
             "observation_end":"2026-09-03"}
LEDGER      [ALFRED, S1:VIXCLS, S2:VXVCLS]
```

## ITER 4/25 — Retardo de publicación: `WALCL`, `WRESBAL`, `RRPONTSYD`

```
SOURCE      FRED WALCL (activos totales de la Fed, semanal, referida al miercoles),
            WRESBAL (reservas, semanal), RRPONTSYD (repo inverso, diaria).
            Son las series que el repo 02 consume — sin vintage y con relleno
            inventado cuando falta la clave.
COST        Gratuita.
VINTAGE     realtime_start/realtime_end.
COVERAGE    WALCL 2002-12-18 ->; WRESBAL 2002-12-18 ->; RRPONTSYD 2003-02-07 ->.
            Todas cubren la ventana.
REVISIONS   El VALOR no se revisa (ITER 5). Lo que cambia es su VISIBILIDAD.
LAG         *** LA PRUEBA CLAVE DE ESTA FASE ***
            ALFRED impone el retardo por si solo. No hay que modelarlo: hay que
            no estorbarlo.
BACKFILL    1 peticion por serie y fecha de corte, memoizable.
CLASS       PIT-NATIVE
USE         Ruta de decision
CLOSES      D2. Y resuelve el problema point-in-time que el encargo señala como
            "la parte dificil" del repo 02: no hay parte dificil si se usa ALFRED.
PROOF       WALCL, observacion del miercoles 2020-03-25:
              consultado el 2020-03-25 -> 0 observaciones visibles
              consultado el 2020-03-26 -> 1 observacion visible
              consultado el 2020-03-27 -> 1 observacion visible
            VIXCLS, misma observacion 2020-03-25:
              consultado el 2020-03-25 -> 1 -> 63.95   (mismo dia, sin retardo)
            Es el par filed/end del XBRL y el fecha_informe/fecha_publicacion del
            COT, aplicado por el proveedor.
LEDGER      [ALFRED, S1, S2, S3:{WALCL,WRESBAL,RRPONTSYD,DGS10,DGS2,T10Y2Y}]
```

## ITER 5/25 — Comportamiento ante revisiones

```
SOURCE      Las tres series anteriores, misma observacion, tres vintages.
COST        —
VINTAGE     —
COVERAGE    —
REVISIONS   *** NINGUNA DE LAS TRES SE REVISA ***
            Es un resultado importante y ligeramente incomodo: significa que para
            ESTAS series el mecanismo de vintage CONFIRMA en vez de corregir. Su
            valor entero esta en el retardo de publicacion (ITER 4), no en la
            revision. Series que SI se revisan (PIB, empleo, produccion
            industrial) quedan fuera del alcance de este encargo.
LAG         —
BACKFILL    —
CLASS       —
USE         Justifica consumir SIEMPRE el vintage de T, aunque para estas series
            el valor coincida: la regla no puede depender de que una serie
            concreta resulte no revisarse.
CLOSES      Nada nuevo. Es una verificacion.
PROOF       Observacion 2020-03-25 pedida con tres realtime distintos:
              WALCL  : 2020-04-01 -> 5254278.0 | 2021-01-01 -> 5254278.0 | 2026-09-05 -> 5254278.0
              VIXCLS : 2020-04-01 -> 63.95     | 2021-01-01 -> 63.95     | 2026-09-05 -> 63.95
              DGS10  : 2020-04-01 -> 0.88      | 2021-01-01 -> 0.88      | 2026-09-05 -> 0.88
LEDGER      sin altas
```

## ITER 6/25 — CBOE `VIX_History.csv` (vía directa, sin clave)

```
SOURCE      cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
COST        Gratuita, sin autenticacion.
VINTAGE     NO HAY. Es un fichero unico que se sobrescribe. El pasado que sirve
            es el pasado tal y como se ve HOY.
COVERAGE    1990-01-02 -> 2026-09-04. OHLC del VIX, no solo el cierre.
REVISIONS   Desconocido — sin vintage no se puede saber.
LAG         Diario.
BACKFILL    1 peticion.
CLASS       PIT-ARCHIVABLE (por la ausencia de vintage; el dato en si es inmutable
            en la practica, pero eso es una creencia, no una verificacion).
USE         RESPALDO de S1, no sustituto. Aporta el OHLC del VIX, que FRED no da.
CLOSES      Nada que S1 no cierre mejor. Se prefiere ALFRED precisamente porque
            tiene vintage verificable.
PROOF       DATE,OPEN,HIGH,LOW,CLOSE
            01/02/1990,17.24,17.24,17.24,17.24
            ...
            09/04/2026,14.15,14.58,13.80,14.53
LEDGER      [ALFRED, S1, S2, S3]  (S6-CBOE anotada como respaldo)
```

## ITER 7/25 — Ratio put/call de CBOE ⚠ **DESCONTINUADA**

```
SOURCE      cdn.cboe.com/resources/options/volume_and_call_put_ratios/
            {totalpc, equitypc, indexpc}.csv
COST        Gratuita, sin autenticacion. HTTP 200 en las tres.
VINTAGE     No hay, pero cada fila lleva su fecha y es inmutable.
COVERAGE    *** 2006-11-01 -> 2019-10-04. LA SERIE ESTA MUERTA. ***
            139 830 bytes en totalpc.csv, 135 696 en equitypc.csv. La ultima fila
            de ambos es del 4 de octubre de 2019.
REVISIONS   Irrelevante: no hay observaciones nuevas.
LAG         Era diario.
BACKFILL    1 peticion.
CLASS       DESCONTINUADA
USE         *** DISCARD ***
CLOSES      NADA. Y esta es la iteracion mas instructiva del loop.
            Era el candidato con mas valor aparente: un put/call de INDICE con
            historia real, que habria dado al bloque de opciones un componente
            medible en el backtest y habria cerrado parte de la limitacion nº 5.
            Cubre 2015-01 a 2019-10 — casi cinco anos de la ventana del estudio.
            Y por eso mismo hay que descartarla: una serie que MUERE A MITAD DEL
            ESTUDIO es peor que ninguna. El agente se comportaria de una forma
            hasta octubre de 2019 y de otra despues, por un motivo que no tiene
            nada que ver con el mercado, y el backtest atribuiria esa
            discontinuidad a la senal.
            Ajustar el sistema sobre el tramo en que la serie existe y despues
            operar sin ella es exactamente el defecto metodologico que este
            proyecto ya documento dos veces.
PROOF       tail -3 totalpc.csv:
              10/02/2019, 2830814, 3591241, 6422055, 1.27
              10/03/2019, 2097645, 2882751, 4980396, 1.37
              10/04/2019, 2175006, 2289715, 4464721, 1.05
LEDGER      sin altas (descarte razonado)
```

## ITER 8/25 — Volumen de venta en corto de FINRA

```
SOURCE      cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt
            Volumen corto diario POR TICKER en el mercado consolidado.
COST        Gratuita, sin autenticacion.
VINTAGE     Un fichero por dia de negociacion, con la fecha en el nombre. Es la
            forma de clave por vintage en su version mas literal.
COVERAGE    *** El archivo empieza entre 2018-09-03 y 2018-10-01. ***
            Acotado por bisección: 20180302 403 · 20180601 403 · 20180903 403 ·
            20181001 200 · 20181101 200 · 20181203 200 · 20190102 200 ·
            20200102 200 · 20250102 200 · 20260901 200.
            La ventana del estudio empieza en 2015-01: FALTAN CASI CUATRO ANOS.
REVISIONS   Ninguna: fichero cerrado por dia.
LAG         Publicado el mismo dia tras el cierre.
BACKFILL    ~1 800 peticiones para 2018-10 -> hoy, ~350 KB cada una: ~600 MB.
CLASS       PIT-ARCHIVABLE con COBERTURA PARCIAL
USE         *** SOLO ESTUDIO ***, y solo sobre 2019-2025.
CLOSES      D4 A MEDIAS, que en este proyecto significa que no lo cierra. Un
            componente de decision que no existe en el primer tercio del estudio
            reproduce exactamente el defecto documentado del bloque de opciones:
            "un bloque cuyos componentes principales tardan tres meses en
            activarse es un bloque que no funciona cuando se estrena". Aqui son
            cuatro anos.
PROOF       head -3 de CNMSshvol20250102.txt:
              Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
              20250102|A|102002|124|308407|B,Q,N
              20250102|AA|464410|100|977185|B,Q,N
LEDGER      [.., S11:FINRA-shortvol (solo estudio, 2018-10->)]
```

## ITER 9/25 — Interés corto consolidado de FINRA

```
SOURCE      cdn.finra.org/equity/otcmarket/biweekly/shrt{YYYYMMDD}.txt
COST        Gratuita en teoria.
VINTAGE     Llevaria fecha de liquidacion y de publicacion — el par correcto.
COVERAGE    NO VERIFICABLE: HTTP 403 en la ruta probada.
REVISIONS   —
LAG         —
BACKFILL    —
CLASS       NO CUALIFICADA
USE         DISCARD
CLOSES      Nada. D5 queda abierta.
PROOF       HTTP 403 sobre shrt20240115.txt. Sin cuerpo de respuesta utilizable,
            la iteracion no cualifica: la ruta correcta existira, pero este loop
            no acredita fuentes por conjetura.
LEDGER      sin altas
```

## ITER 10/25 — Factores diarios Fama-French

```
SOURCE      mba.tuck.dartmouth.edu/.../F-F_Research_Data_5_Factors_2x3_daily_CSV.zip
            y F-F_Momentum_Factor_daily_CSV.zip
COST        Gratuita, sin autenticacion.
VINTAGE     NO HAY. Un unico fichero que se republica al recalcularse.
COVERAGE    1963 -> presente, diaria. 150 090 y 85 202 bytes.
REVISIONS   *** SI, y es el motivo del descarte para la decision. *** Los
            factores se reconstruyen sobre CRSP y una revision de CRSP cambia
            valores pasados. Sin vintage no se puede saber cual se consumio.
LAG         Mensual, aproximadamente.
BACKFILL    2 peticiones.
CLASS       PIT-ARCHIVABLE (archivo por vintage desde hoy; el pasado, no)
USE         *** SOLO ESTUDIO ***
CLOSES      D6. Permite publicar una ALFA AJUSTADA POR FACTORES en vez de una
            alfa contra un unico indice — que es una mejora directa de como el
            sistema se juzga a si mismo, sin tocar ninguna decision. Que sea
            "solo estudio" no la degrada: el estudio es precisamente su sitio.
PROOF       HTTP 200, 150 090 b (FF5 diario) y 85 202 b (momentum diario).
LEDGER      [.., S7:FamaFrench (solo estudio)]
```

## ITER 11/25 — SEC Financial Statement Data Sets

```
SOURCE      sec.gov/files/dera/data/financial-statement-data-sets/{YYYY}q{N}.zip
COST        Gratuita. Exige User-Agent identificativo.
VINTAGE     PIT POR CONSTRUCCION: cada fichero es el volcado de un trimestre y
            cada fila lleva numero de registro (accession) y fecha de presentacion.
COVERAGE    2009q2 -> presente. Cubre la ventana entera.
REVISIONS   Ninguna: un trimestre publicado es inmutable.
LAG         Trimestral.
BACKFILL    44 trimestres x ~110 MB = ~4,8 GB. 2015q1 pesa 98 944 359 b y
            2024q4 122 932 548 b, medidos.
CLASS       PIT-NATIVE
USE         DESCARTADA POR REDUNDANCIA, no por calidad.
CLOSES      Nada que S6 no cierre ya. `FundamentalStore` filtra companyfacts por
            filed <= t y su cache pesa una fraccion de esos 4,8 GB. Cambiar de
            fuente seria una segunda implementacion de la seleccion point-in-time
            de los fundamentales — el bug de clase que este proyecto prohibe.
PROOF       2015q1.zip -> HTTP 200, 98 944 359 bytes
            2024q4.zip -> HTTP 200, 122 932 548 bytes
LEDGER      sin altas
```

## ITER 12/25 — Curva diaria del Tesoro de EEUU

```
SOURCE      home.treasury.gov/.../daily-treasury-rates.csv/{YYYY}/all?...&_format=csv
COST        Gratuita, sin autenticacion.
VINTAGE     Un CSV por ano; cada fila lleva su fecha. No se revisa.
COVERAGE    1990 -> presente, doce vencimientos de 1 mes a 30 anos.
REVISIONS   Ninguna conocida.
LAG         Publicada el mismo dia tras el cierre.
BACKFILL    11 peticiones (una por ano).
CLASS       PIT-NATIVE
USE         Redundante con S3 (DGS10, DGS2, T10Y2Y via ALFRED).
CLOSES      D2, pero S3 ya lo cierra con vintage verificable y una sola fuente.
            El encargo pide preferir una fuente que sirva a varios agentes antes
            que varias estrechas: ALFRED sirve a los dos bloques macro.
PROOF       Date,"1 Mo","2 Mo",...,"10 Yr","20 Yr","30 Yr"
            12/31/2018,2.44,2.45,2.45,2.56,2.63,2.48,2.46,2.51,2.59,2.69,2.87,3.02
LEDGER      [.., S8:Treasury (redundante)]
```

## ITER 13/25 — EOD independiente (Stooq)

```
SOURCE      stooq.com/q/d/l/?s=aapl.us&d1=...&d2=...&i=d
COST        Gratuita en teoria.
VINTAGE     —
COVERAGE    NO VERIFICABLE.
REVISIONS   —
LAG         —
BACKFILL    —
CLASS       NO CUALIFICADA
USE         DISCARD
CLOSES      Nada. D10 queda abierta: NO SE PUEDE CUANTIFICAR cuanto distorsiona
            el reajuste retroactivo de yfinance a los indicadores tecnicos. Es
            una limitacion nueva y hay que declararla.
PROOF       Devuelve un desafio anti-bot de JavaScript (proof-of-work SHA-256),
            no datos. Cuerpo capturado, sin cifras dentro.
LEDGER      sin altas
```

## ITER 14/25 — Índice diario de EDGAR

```
SOURCE      sec.gov/Archives/edgar/daily-index/{YYYY}/QTR{N}/form.{YYYYMMDD}.idx
            TODO lo presentado ante la SEC ese dia, con tipo de formulario, CIK y
            FECHA DE PRESENTACION exacta.
COST        Gratuita. User-Agent identificativo.
VINTAGE     PIT POR CONSTRUCCION: un fichero por dia, inmutable.
COVERAGE    1994 -> presente.
REVISIONS   Ninguna.
LAG         Mismo dia.
BACKFILL    ~2 770 peticiones para la ventana del estudio.
CLASS       PIT-NATIVE
USE         SOLO ESTUDIO por ahora — y es la FRONTERA declarada.
CLOSES      D9 PARCIALMENTE, y es la unica via gratuita que lo hace. Un
            `NewsStore` point-in-time construido sobre este indice mas los 8-K
            seria reconstruible de verdad, con la misma disciplina que
            `FundamentalStore`. Cubre resultados y hechos relevantes; NO cubre
            prensa general, que sigue sin via gratuita.
            *** Construirlo NO autoriza por si solo a conectar las noticias a la
            decision.*** El prompt es explicito y `CLAUDE.md` tambien: las
            noticias siguen siendo asesoras hasta que el almacen cubra la ventana
            y `test_news_report_does_not_alter_decision` se retire
            deliberadamente, con evidencia. Queda fuera del alcance de este
            encargo y se anota en NEXT_STEPS.
PROOF       form.20150105.idx:
              Form Type   Company Name                       CIK    Date Filed  File Name
              1-A/A       RX HEALTHCARE SYSTEMS LTD          1389049  20141222  edgar/data/...
            Notese: presentado el 2014-12-22, diseminado el 2015-01-05. El par
            esta en el propio fichero.
LEDGER      [.., S9:EDGAR-daily-index (frontera declarada)]
```

## ITER 15/25 — El histórico OHLCV del anfitrión ★

```
SOURCE      data/cache/prices/{TICKER}.csv, servido por PriceStore.window().
            No es una fuente externa: es la que el sistema YA tiene.
COST        Cero. Ya descargada, 254 MB de cache, `--offline` la reproduce.
VINTAGE     El corte lo aplica PriceStore.window(ticker, as_of, lookback_days),
            que corta en as_of INCLUSIVE (data.py:230). La cache lleva metadatos
            de cobertura (`.meta.json`) y `_covers()` compara contra el rango
            SOLICITADO, no contra las filas del CSV.
COVERAGE    51 valores. AAPL: 2013-11-27 -> 2025-12-30, 3 040 sesiones.
            Columnas Open, High, Low, Close, Volume — el OHLC COMPLETO.
REVISIONS   Si: yfinance sirve precios REAJUSTADOS retroactivamente. Es la
            limitacion D10, que ITER 13 no ha podido cuantificar. Afecta por
            igual a los indicadores que el sistema ya usa, asi que no introduce
            un sesgo NUEVO — pero hay que declararlo.
LAG         Ninguno para el backtest.
BACKFILL    Ninguna. Ya esta.
CLASS       PIT-NATIVE (y ya protegida por
            test_no_lookahead_future_prices_do_not_change_past_signal)
USE         *** RUTA DE DECISION ***
CLOSES      *** LA LIMITACION Nº 5, que es la mas importante del informe. ***
            Con `add_liquidity` (repo 07) y el canal de Donchian (repo 06), este
            dato produce NIVELES DE PRECIO concretos —minimo de N sesiones,
            minimo del mes anterior, suelo del canal, numero redondo— sin cadena
            de opciones. El backtest puede por fin medir un ajuste de entrada
            sobre las 132 fechas del estudio completo.
            Es la sustitucion PIT-native que el encargo pide, y no habia que
            salir del repositorio a buscarla.
PROOF       AAPL: 2013-11-27 -> 2025-12-30 | 3040 sesiones
                  cols ['Open','High','Low','Close','Volume'] | OHLC completo: True
            102 ficheros en data/cache/prices/ (51 csv + 51 meta).
LEDGER      [.., ★ S4:PriceStore-OHLCV (RUTA DE DECISION)]
```

## ITER 16/25 — Composición histórica del índice (Wikipedia)

```
SOURCE      Tabla de altas y bajas del S&P 500 en Wikipedia (API MediaWiki).
COST        Gratuita. HTTP 200.
VINTAGE     *** NO HAY, Y NO ES UN DETALLE. *** Se puede pedir una REVISION
            antigua de la pagina, pero eso devuelve lo que la pagina decia
            entonces, no lo que el indice era entonces. La tabla de "cambios" es
            un artefacto redactado HOY sobre el pasado, editable por cualquiera.
COVERAGE    Aparente: decadas. Real: sin garantia de completitud ni de exactitud.
REVISIONS   Continuas y no rastreables como vintage del DATO.
LAG         —
BACKFILL    1 peticion.
CLASS       NO-HISTORY (en el sentido que importa aqui)
USE         DISCARD
CLOSES      *** NO CIERRA D7. *** El sesgo de supervivencia sigue en pie y sigue
            siendo el sesgo residual dominante: contamina TODAS las cifras del
            informe, no las de un agente. Cerrarlo de verdad exige composiciones
            historicas fechadas y auditadas (CRSP, Norgate, Sharadar), que son de
            pago. Se mantiene en NEXT_STEPS #8 y en las limitaciones.
PROOF       API MediaWiki HTTP 200 sobre List_of_S&P_500_companies. Se descarta
            por la naturaleza de la fuente, no por su disponibilidad.
LEDGER      sin altas
```

## ITER 17/25 — Diferencial *high yield* (ICE BofA)

```
SOURCE      FRED BAMLH0A0HYM2 — ICE BofA US High Yield Option-Adjusted Spread.
COST        Gratuita.
VINTAGE     Mecanismo ALFRED disponible.
COVERAGE    *** 2023-09-05 -> 2026-09-03. TRES ANOS. ***
            El diferencial HY es historicamente una de las mejores medidas de
            estres crediticio y la serie llegaba a 1996; el acceso historico
            gratuito esta hoy restringido.
REVISIONS   —
LAG         Diario.
BACKFILL    1 peticion.
CLASS       COBERTURA INSUFICIENTE
USE         DISCARD
CLOSES      Nada. Habria sido el mejor complemento del VIX para el bloque de
            estres —el VIX mide miedo en renta variable, el HY mide tension de
            credito— pero tres de once anos no permiten ni entrenar ni validar.
PROOF       {"id":"BAMLH0A0HYM2","frequency_short":"D",
             "observation_start":"2023-09-05","observation_end":"2026-09-03"}
LEDGER      sin altas
```

## ITER 18/25 — Cadenas de opciones históricas por ticker — **PARADA**

```
SOURCE      OptionMetrics/IvyDB, CBOE DataShop, ORATS.
COST        *** DE PAGO. DISCARD INMEDIATO por la regla de coste. ***
CLASS       —
USE         DISCARD
CLOSES      Nada. La limitacion nº 5 NO se cierra por esta via, y no se cerrara.
            El sustituto medible es S4 (ITER 15), que no reproduce el bloque de
            opciones sino que le da una ALTERNATIVA de nivel construida con datos
            que si son reconstruibles. La diferencia hay que nombrarla y no
            promediarla: el backtest medira el ajuste de entrada CON NIVELES DE
            PRECIO, no con niveles de open interest.
PROOF       No procede: el coste se verifica en el catalogo del proveedor y la
            regla del encargo es terminante.
LEDGER      sin altas

>>> PARADA TEMPRANA. Iteraciones 16, 17 y 18 sin altas consecutivas.
>>> Loop S detenido en 18/25 conforme a la regla del encargo.
```

---

## Demandas de datos que NINGUNA fuente gratuita cualificada puede cubrir

Esta lista no es un fracaso: **es la frontera honesta de lo que este sistema
podrá validar jamás sin pagar**, y va a `build_limitations()`.

| # | Demanda | Por qué no se puede cubrir | Consecuencia declarada |
|---|---|---|---|
| **D8** | Cadenas de opciones históricas por ticker | De pago, sin excepción (ITER 18) | El bloque de opciones del Analista de Posicionamiento **nunca** se medirá tal cual es. El backtest medirá una alternativa de nivel construida sobre precio (S4), y eso hay que decirlo en vez de promediarlo. |
| **D7** | Composición histórica del índice con fechas | Wikipedia no es una fuente con vintage (ITER 16); lo auditado es de pago | El **sesgo de supervivencia sigue siendo el sesgo residual dominante** y contamina todas las cifras del informe. |
| **D9** | Prensa general con marca temporal real | Solo los archivos de la SEC son fechados y gratuitos (ITER 14); la prensa exige un proveedor de archivo de pago | Las noticias **siguen siendo capa asesora**. `test_news_report_does_not_alter_decision` se conserva. |
| **D10** | Precios EOD sin reajuste retroactivo | La alternativa gratuita probada está tras un desafío anti-bot (ITER 13) | **No se puede cuantificar** cuánto distorsiona el reajuste de yfinance a los indicadores. Limitación nueva. |
| **D5** | Interés corto consolidado | Ruta probada devuelve 403 (ITER 9) | El modelo de nivel no dispondrá de esta variable. |
| D4 (parcial) | Volumen corto diario **antes de 2018-10** | El archivo de FINRA no llega (ITER 8) | Cualquier componente basado en él sería inerte en el primer tercio del estudio. Por eso queda en «solo estudio». |
| — | Diferencial de crédito HY con historia | Acceso gratuito restringido a 2023→ (ITER 17) | El bloque de estrés se apoya solo en volatilidad implícita, no en crédito. |

## Ingeniería de reproducibilidad — cómo se consume lo cualificado

1. **Manifiesto append-only.** Cada recuperación anota fuente, endpoint, vintage
   o `as_of`, recuento de filas y suma de verificación del contenido. **Sin
   marca de reloj de pared en la salida persistida**: el propio proyecto ya tuvo
   ese defecto y lo corrigió haciendo secuenciales los identificadores de traza.
2. **Caché inmutable con clave por vintage.** El patrón de `data/cache/cot/` y
   nunca el de `data/cache/news/`. Una redescarga que devuelva bytes distintos
   para el mismo vintage **levanta excepción**: es un evento que registrar, no
   algo que sobrescribir en silencio.
3. **`--offline` debe reproducir el estudio bit a bit.** Ya es una propiedad
   documentada del repositorio. Si una fuente nueva la rompe, la fuente está
   mal, no la propiedad.
4. **Un solo filtro point-in-time por serie, en código de producción.** Cada
   almacén nuevo reutiliza la función de selección de producción con un
   parámetro `as_of` — el patrón `COTStore` → `serie_semanal`. Una segunda
   implementación dentro de `src/backtest/` es un bug de la misma clase que una
   regla de decisión duplicada.
5. **El vintage se declara en el informe.** Cada ejecución dice qué vintage de
   cada serie usó, para que dos ejecuciones que discrepen se puedan diagnosticar
   en vez de discutir.
