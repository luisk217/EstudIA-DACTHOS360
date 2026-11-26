"""Punto de entrada: ejecuta el pipeline y escribe las tablas y los JSON del frontend.

Uso:
    python -I run_pipeline.py [--datos RUTA] [--fecha-corte AAAA-MM-DD] [--estricto]
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline import config, exportacion, orquestador  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Lee argumentos, corre el pipeline y exporta."""
    ap = argparse.ArgumentParser(description="Pipeline DACTHO 360")
    ap.add_argument("--datos", type=Path, default=config.DIR_DATOS, help="Carpeta con las exportaciones crudas")
    ap.add_argument("--fecha-corte", type=date.fromisoformat, default=config.FECHA_CORTE_DEFECTO)
    ap.add_argument("--salida-web", type=Path, default=config.DIR_WEB)
    ap.add_argument("--salida-procesados", type=Path, default=config.DIR_PROCESADOS, help="Carpeta del modelo relacional en CSV")
    ap.add_argument("--estricto", action="store_true", help="Detiene la ejecución si el modelo tiene errores de integridad (los huérfanos de severidad aviso no la detienen)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config.Configuracion(dir_datos=args.datos, fecha_corte=args.fecha_corte, dir_web=args.salida_web, dir_procesados=args.salida_procesados)
    res = orquestador.ejecutar(cfg, estricto=args.estricto)
    exportacion.exportar_todo(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

