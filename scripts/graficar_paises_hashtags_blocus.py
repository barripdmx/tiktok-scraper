"""País de creación declarado por TikTok de las publicaciones Blocus y hashtags más usados."""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.blocus import FALSOS_POSITIVOS, NOTA_FALSOS_POSITIVOS

ROOT = Path(__file__).resolve().parents[1]
ENTRADA = ROOT / "outputs/comentarios_blocus_20261026/publicaciones.csv"
SALIDA = ROOT / "outputs/comentarios_blocus_20261026/paises_y_hashtags.png"
LOGO = ROOT / "assets/tiktok_logo.jpg"
PAISES = {"FR": "Francia", "ES": "España", "CL": "Chile", "BE": "Bélgica", "CA": "Canadá", "RO": "Rumanía",
          "IT": "Italia", "": "sin dato"}
COLORES = ["#1F618D", "#A93226", "#CA6F1E", "#1E8449", "#7D3C98", "#C8CED3"]
TOP_PAISES, TOP_CUENTAS, TOP_TAGS = 8, 4, 16


def main():
    with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
        filas = [fila for fila in csv.DictReader(f) if fila["cuenta"] not in FALSOS_POSITIVOS]
    n_pais = Counter(f["meta_pais_creacion"] for f in filas)
    paises = [p for p, _ in n_pais.most_common(TOP_PAISES)][::-1]
    cuentas = [c for c, _ in Counter(f["cuenta"] for f in filas).most_common(TOP_CUENTAS)]
    por_pais = defaultdict(Counter)
    for f in filas:
        c = f["cuenta"] if f["cuenta"] in cuentas else "otras cuentas"
        por_pais[f["meta_pais_creacion"]][c] += 1
    etiquetas = cuentas + ["otras cuentas"]
    tags = Counter(h.strip().lower() for f in filas for h in f["hashtags"].split("|") if h.strip())

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(16, 9), dpi=100, facecolor="white",
                                 gridspec_kw={"width_ratios": [1.15, 1]})
    fig.subplots_adjust(left=0.08, right=0.97, top=0.8, bottom=0.12, wspace=0.3)
    izq = [0] * len(paises)
    for cuenta, color in zip(etiquetas, COLORES):
        vals = [por_pais[p][cuenta] for p in paises]
        a1.barh([PAISES.get(p, p) for p in paises], vals, left=izq, color=color, height=0.7,
                label=f"@{cuenta}" if cuenta != "otras cuentas" else cuenta)
        izq = [a + b for a, b in zip(izq, vals)]
    for y, p in enumerate(paises):
        a1.text(izq[y] + 3, y, str(n_pais[p]), va="center", fontsize=9, color="#555555")
    a1.set_title("país de creación de la publicación", loc="left", fontsize=11, fontweight="bold")
    a1.legend(loc="lower right", fontsize=8.5, frameon=False)
    mas = tags.most_common(TOP_TAGS)[::-1]
    a2.barh([f"#{t}" for t, _ in mas], [n for _, n in mas], color="#1F618D", height=0.7)
    for y, (_, n) in enumerate(mas):
        a2.text(n + 2, y, str(n), va="center", fontsize=9, color="#555555")
    a2.set_title("hashtags más usados (publicaciones)", loc="left", fontsize=11, fontweight="bold")
    for ax in (a1, a2):
        ax.grid(axis="x", color="#EBEBEB")
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        ax.tick_params(labelsize=9)
    fig.text(0.04, 0.94, "desde dónde y con qué etiquetas publican las cuentas blocus",
             fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.905, f"{len(filas)} publicaciones; el país lo declara TikTok en los metadatos de cada publicación "
             "(ubicación de creación), no el perfil", fontsize=10.5, color="#555555")
    fig.text(0.04, 0.03, "El país de creación es un dato de TikTok y puede reflejar VPN o la ubicación de la cuenta; "
             "no prueba dónde está quien publica. Hashtags contados una vez por publicación.",
             fontsize=8.5, color="#555555")
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage
        fig.add_artist(AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.93),
                                      xycoords="figure fraction", frameon=False))
    fig.text(0.04, 0.005, NOTA_FALSOS_POSITIVOS, fontsize=8.5, color="#A93226")
    fig.savefig(SALIDA, facecolor="white")
    print(SALIDA)


if __name__ == "__main__":
    main()
