"""Mapa de calor de la audiencia compartida entre las cuentas Blocus con más usuarios vinculados.

Audiencia = usuarios que siguen a la cuenta, a los que sigue o que comentan en sus publicaciones.
Cada celda: usuarios comunes a dos cuentas, sin contar las propias cuentas analizadas.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from scripts.graficar_cuentas_analizadas_blocus import construir

ROOT = Path(__file__).resolve().parents[1]
SALIDA = ROOT / "outputs/grafo_blocus_20261025/audiencia_compartida.png"
LOGO = ROOT / "assets/tiktok_logo.jpg"
TOP = 22


def main():
    cuentas, _, comunes, audiencia = construir()
    ids = sorted(cuentas, key=lambda n: -len(audiencia[n]))[:TOP]
    m = np.zeros((TOP, TOP))
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i != j:
                m[i, j] = comunes.get((a, b)) or comunes.get((b, a)) or 0
    nombres = [f"@{cuentas[n]}  ({len(audiencia[n]):,})".replace(",", ".") for n in ids]
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor="white")
    fig.subplots_adjust(left=0.17, right=0.93, top=0.84, bottom=0.2)
    mostrar = np.ma.masked_where(np.eye(TOP, dtype=bool), m)
    im = ax.imshow(mostrar, cmap=LinearSegmentedColormap.from_list("t", ["#FFFFFF", "#25f4ee", "#1F618D", "#010101"]),
                   vmin=0, vmax=np.percentile(m[m > 0], 95), aspect="auto")
    ax.set_xticks(range(TOP), labels=[f"@{cuentas[n]}" for n in ids], rotation=60, ha="right", fontsize=8)
    ax.set_yticks(range(TOP), labels=nombres, fontsize=8)
    for i in range(TOP):
        for j in range(TOP):
            if i != j and m[i, j]:
                ax.text(j, i, int(m[i, j]), ha="center", va="center", fontsize=6.5,
                        color="white" if m[i, j] > im.norm.vmax * 0.5 else "#333333")
    for lado in ax.spines.values():
        lado.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="usuarios en común (escala cortada en el percentil 95)")
    fig.text(0.04, 0.93, "qué cuentas blocus comparten audiencia", fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.895, f"las {TOP} cuentas con más usuarios vinculados (entre paréntesis): seguidores, seguidos "
             "y comentaristas; celda = usuarios comunes a las dos cuentas", fontsize=10.5, color="#555555")
    top_par = max(comunes, key=comunes.get)
    fig.text(0.04, 0.05, f"El par con más audiencia común es @{cuentas[top_par[0]]} - @{cuentas[top_par[1]]} "
             f"({comunes[top_par]} usuarios). Compartir audiencia no demuestra coordinación: son comunidades "
             "que siguen temas parecidos. Capturas del 25-26/10/2026.", fontsize=8.5, color="#555555")
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage
        fig.add_artist(AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.93),
                                      xycoords="figure fraction", frameon=False))
    fig.savefig(SALIDA, facecolor="white")
    print(SALIDA)


if __name__ == "__main__":
    main()
