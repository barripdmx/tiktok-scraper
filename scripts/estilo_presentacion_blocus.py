"""Estilo común de las gráficas de la presentación Blocus (periodístico, 16:9, nota de falsos positivos)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

from config.blocus import NOTA_FALSOS_POSITIVOS

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "outputs/presentacion_blocus_20261028"
LOGO = ROOT / "assets/tiktok_logo.jpg"
AZUL, ROJO, NARANJA, GRIS, CLARO = "#1F618D", "#A93226", "#CA6F1E", "#4A4A4A", "#9DB7CF"


def nueva(titulo, subtitulo, nota, filas=1, columnas=1, **kw):
    """Figura 16:9 con título, subtítulo y pie. Devuelve (fig, ejes)."""
    fig, ejes = plt.subplots(filas, columnas, figsize=(16, 9), dpi=100, facecolor="white", **kw)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.8, bottom=0.14)
    fig.text(0.04, 0.94, titulo, fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.905, subtitulo, fontsize=10.5, color="#555555")
    fig.text(0.04, 0.035, nota, fontsize=8.5, color="#555555")
    fig.text(0.04, 0.008, NOTA_FALSOS_POSITIVOS, fontsize=8, color=ROJO)
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        fig.add_artist(AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.93),
                                      xycoords="figure fraction", frameon=False))
    return fig, ejes


def limpiar(ax, rejilla="y"):
    ax.grid(axis=rejilla, color="#EBEBEB")
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(labelsize=9)


def guardar(fig, nombre):
    DESTINO.mkdir(parents=True, exist_ok=True)
    ruta = DESTINO / nombre
    fig.savefig(ruta, facecolor="white")
    plt.close(fig)
    print(ruta)
    return ruta


def miles(n):
    return f"{n:,}".replace(",", ".")


def pct(x, dec=1):
    return f"{x:.{dec}f}".replace(".", ",") + " %"
