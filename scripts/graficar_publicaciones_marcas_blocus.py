"""Publicaciones Blocus por cuenta: tipo y marcas incrustadas en las fotos (Meta, etiqueta de IA)."""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.blocus import AMBITO, COLOR_TEMA, FALSOS_POSITIVOS, NOTA_FALSOS_POSITIVOS, destino, rotular_ambito, tema_de_cuentas

ROOT = Path(__file__).resolve().parents[1]
ENTRADA = ROOT / "data/blocus/datos/comentarios_blocus_20261026/publicaciones.csv"
SALIDA = ROOT / "data/blocus/datos/comentarios_blocus_20261026/publicaciones_marcas.png"
LOGO = ROOT / "assets/tiktok_logo.jpg"
CATEGORIAS = [  # (clave, texto de leyenda, color)
    ("video", "vídeo (no se descargó el archivo)", "#9DB7CF"),
    ("foto_limpia", "foto sin marcas", "#4A4A4A"),
    ("foto_meta", "foto con huella de Meta (FBMD)", "#CA6F1E"),
    ("foto_ia", "foto con etiqueta de IA incrustada (C2PA/EXIF de TikTok)", "#A93226"),
    ("no_disponible", "ya no disponible", "#DDDDDD"),
]


def a_int(valor):
    return int(valor) if valor.isdigit() else 0


def clasificar(fila):
    if fila["estado_metadatos"].startswith("no_disponible"):
        return "no_disponible"
    if fila["tipo"] == "video":
        return "video"
    if a_int(fila["foto_n_fbmd"]):
        return "foto_meta"
    if a_int(fila["foto_n_c2pa"]) or a_int(fila["foto_n_exif_sin_c2pa"]):
        return "foto_ia"
    return "foto_limpia"


def main():
    with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
        filas = [fila for fila in csv.DictReader(f) if fila["cuenta"] not in FALSOS_POSITIVOS]
    por_cuenta = defaultdict(Counter)
    for fila in filas:
        por_cuenta[fila["cuenta"]][clasificar(fila)] += 1
    total = Counter(c for cuenta in por_cuenta.values() for c in cuenta.elements())
    orden = sorted(por_cuenta, key=lambda c: sum(por_cuenta[c].values()))
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor="white")
    fig.subplots_adjust(left=0.14, right=0.97, top=0.82, bottom=0.12)
    izq = [0] * len(orden)
    for clave, texto, color in CATEGORIAS:
        vals = [por_cuenta[c][clave] for c in orden]
        ax.barh(orden, vals, left=izq, color=color, label=f"{texto} ({total[clave]})", height=0.75)
        izq = [a + b for a, b in zip(izq, vals)]
    for y, c in enumerate(orden):
        ax.text(izq[y] + 0.1, y, str(izq[y]), va="center", fontsize=8, color="#555555")
    if AMBITO == "espana":  # nombre de cada cuenta en el color de su tema
        tema = tema_de_cuentas()
        for lab in ax.get_yticklabels():
            lab.set_color(COLOR_TEMA[tema.get(lab.get_text(), "sin clasificar")])
    ax.grid(axis="x", color="#EBEBEB")
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.legend(loc="lower right", fontsize=9, frameon=False)
    fig.text(0.04, 0.94, f"publicaciones de las cuentas blocus: {len(filas)} en {len(por_cuenta)} cuentas",
             fontsize=17, fontweight="bold", color="#222222")
    fotos = total["foto_limpia"] + total["foto_meta"] + total["foto_ia"]
    fig.text(0.04, 0.905, f"de las {fotos} fotos disponibles, {total['foto_meta']} llevan la huella de Meta y "
             f"{total['foto_ia']} una etiqueta de IA; el resto no lleva marcas", fontsize=10.5, color="#555555")
    fig.text(0.04, 0.03, "Marcas leídas en todas las imágenes de cada álbum; una publicación cuenta si alguna imagen la lleva (huella FBMD, C2PA/EXIF de TikTok). "
             "FBMD indica que la imagen pasó por Meta; la etiqueta de IA la pone TikTok. Capturas del 26-27/10/2026.",
             fontsize=8.5, color="#555555")
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage
        fig.add_artist(AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.93),
                                      xycoords="figure fraction", frameon=False))
    fig.text(0.04, 0.005, NOTA_FALSOS_POSITIVOS, fontsize=8.5, color="#A93226")
    rotular_ambito(fig)
    fig.savefig(destino(SALIDA), facecolor="white")
    print(destino(SALIDA), dict(total))


if __name__ == "__main__":
    main()
