"""Añade a publicaciones.csv de Blocus la revisión de todas las imágenes de cada álbum.

Entrada (--entrada): TSV sin cabecera con una fila por publicación de fotos:
id, imágenes revisadas, con FBMD, con C2PA, con XMP, con EXIF sin C2PA,
con ICC de Google («n:versión»), JPEG progresivos, ambos servidores idénticos (1/0),
SHA-256 (12 hex) de cada imagen separados por «|».
Las imágenes se leyeron completas, segmento a segmento, desde los dos servidores del CDN.
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "outputs/comentarios_blocus_20261026/publicaciones.csv"

CAMPOS = ["foto_n_revisadas", "foto_n_fbmd", "foto_n_c2pa", "foto_n_xmp", "foto_n_exif_sin_c2pa",
          "foto_icc_google", "foto_n_jpeg_progresivo", "foto_servidores_identicos", "foto_sha256_12"]
NUEVAS = CAMPOS + ["foto_duplicada_en"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", type=Path, required=True)
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    args = parser.parse_args()

    revision = {}
    for linea in args.entrada.read_text(encoding="utf-8").splitlines():
        valores = linea.split("\t")
        assert len(valores) == len(CAMPOS) + 1, linea
        revision[valores[0]] = dict(zip(CAMPOS, valores[1:]))
    por_hash = defaultdict(set)
    for pid, fila in revision.items():
        for sha in fila["foto_sha256_12"].split("|"):
            por_hash[sha].add(pid)

    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        base = [c for c in lector.fieldnames if c not in NUEVAS]
        filas = list(lector)
    for fila in filas:
        datos = revision.get(fila["id"], {})
        for columna in NUEVAS:
            fila[columna] = datos.get(columna, "")
        if datos:
            otras = set().union(*(por_hash[s] for s in datos["foto_sha256_12"].split("|"))) - {fila["id"]}
            fila["foto_duplicada_en"] = "|".join(sorted(otras))
    with args.csv.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=base + NUEVAS)
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"{sum(1 for f in filas if f['foto_n_revisadas'])} publicaciones con revisión de fotos")


if __name__ == "__main__":
    main()
