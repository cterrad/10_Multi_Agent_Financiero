"""
Recarga en frío de las series de FRED/ALFRED. Reejecutable sin riesgo.

    <python> -m src.data.fred.backfill --desde 2013 --hasta 2026

QUÉ HACE Y QUÉ NO
-----------------
Descarga, año a año y por serie, la **primera publicación** de cada observación
(`output_type=4`) y la persiste en `data/cache/fred/{SERIE}_{AÑO}.json`. A partir
de ahí `--offline` reproduce el estudio sin red.

Es seguro reejecutarlo:

  · un año ya cacheado y CERRADO no se vuelve a pedir;
  · un año cacheado cuyo contenido coincide no se reescribe;
  · un año cacheado cuyo contenido **difiere** levanta `VintageDivergente` y
    **no** se sobrescribe. Que el proveedor reescriba historia ya consumida es
    un evento que registrar e investigar, no algo que absorber en silencio: es
    justo la propiedad que hace que un estudio del año pasado siga siendo
    reproducible hoy.

Cada escritura deja una línea en el manifiesto append-only con la serie, el año,
el recuento de filas y una suma de verificación del contenido. Sin marca de
reloj de pared: dos ejecuciones `--offline` tienen que poder compararse byte a
byte.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import List

from src.data.fred import series_requeridas
from src.data.fred.cache import VintageDivergente, anio_esta_cerrado, leer_serie
from src.data.fred.serie import FredNoConfigurado, _descargar_anio
from src.data.fred import cache as fred_cache


def recargar(desde: int, hasta: int, series: List[str],
             forzar_ano_corriente: bool = True) -> int:
    """Devuelve 0 si todo fue bien, 1 si alguna serie o año falló."""
    fallos = 0
    for serie in series:
        print(f"\n=== {serie} ===")
        for anio in range(desde, hasta + 1):
            cacheado = leer_serie(serie, anio)
            cerrado = anio_esta_cerrado(anio)
            if cacheado is not None and cerrado:
                print(f"  {anio}  {len(cacheado):4d} filas  (caché, año cerrado)")
                continue
            if cacheado is not None and not forzar_ano_corriente:
                print(f"  {anio}  {len(cacheado):4d} filas  (caché)")
                continue

            try:
                filas, motivo = _descargar_anio(serie, anio)
            except FredNoConfigurado as exc:
                print(f"  ✗ {exc}")
                return 1
            if motivo:
                # «La serie no existe en ALFRED» NO es un fallo de red: es el
                # límite del ARCHIVO, que puede empezar más tarde que la propia
                # serie. `VXVCLS` es el caso: sus observaciones llegan a 2007
                # pero su histórico de vintages solo a 2014. Se declara como
                # frontera de cobertura y no se reintenta, porque no hay nada
                # que reintentar.
                if "does not exist in ALFRED" in motivo:
                    print(f"  {anio}  — sin archivo en ALFRED (frontera de "
                          f"cobertura, no un fallo)")
                    continue
                print(f"  {anio}  ✗ {motivo}")
                fallos += 1
                continue
            if not filas:
                print(f"  {anio}     0 filas  (sin observaciones publicadas)")
                continue
            try:
                info = fred_cache.escribir_serie(serie, anio, filas)
            except VintageDivergente as exc:
                print(f"  {anio}  ✗ VINTAGE DIVERGENTE — no se sobrescribe.\n     {exc}")
                fallos += 1
                continue
            estado = "escrito" if info["escrito"] else "sin cambios"
            print(f"  {anio}  {len(filas):4d} filas  huella {info['huella']}  ({estado})")
    return 1 if fallos else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--desde", type=int, default=2013,
                   help="primer año de observación (por defecto 2013: da un año "
                        "de margen para la ventana del z-score de 2014 en adelante)")
    p.add_argument("--hasta", type=int, default=date.today().year)
    p.add_argument("--series", type=str, default="",
                   help="lista separada por comas; por defecto las del dosier")
    args = p.parse_args(argv)

    series = ([s.strip().upper() for s in args.series.split(",") if s.strip()]
              or series_requeridas())
    print(f"Recarga de FRED/ALFRED: {', '.join(series)} · {args.desde}-{args.hasta}")
    return recargar(args.desde, args.hasta, series)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
