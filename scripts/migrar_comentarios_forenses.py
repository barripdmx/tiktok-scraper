# -*- coding: utf-8 -*-
"""Pasa los CSV de comentarios antiguos (12 columnas) a las 30 con los campos forenses.

Solo se calculan los 4 temporales (comment_timestamp_unix, comment_fecha_utc, comment_snowflake_utc,
comment_secuencia); el resto queda vacío hasta recapturar. Dry-run por defecto: `--aplicar` escribe.
"""
import argparse
import csv
import glob
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "src", "utils"))
from tiktok_utils import COLUMNAS_COMENTARIOS, migrar_csv_comentarios  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true", help="escribe los cambios (sin él solo informa)")
    ap.add_argument("csv", nargs="*", help="CSV concretos; por defecto data/**/*comentarios_api.csv")
    a = ap.parse_args()
    for ruta in a.csv or sorted(glob.glob(os.path.join(BASE, "data", "**", "*comentarios_api.csv"), recursive=True)):
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            cab = next(csv.reader(f), [])
        if cab == COLUMNAS_COMENTARIOS:
            print(f"= al día   {ruta}")
        elif not a.aplicar:
            print(f"· migraría {ruta} ({len(cab)} columnas → {len(COLUMNAS_COMENTARIOS)})")
        else:
            print(f"✔ {migrar_csv_comentarios(ruta):>8,} filas  {ruta}".replace(",", "."))


if __name__ == "__main__":
    main()
