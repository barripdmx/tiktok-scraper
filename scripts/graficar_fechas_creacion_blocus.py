"""Fechas de creación de las cuentas Blocus analizadas, de sus seguidores/seguidos y de sus comentaristas.

Cada panel cuenta cuentas por mes de creación. Fecha confirmada: la que declara el perfil;
estimada: UID >> 32 (aproximación técnica, no prueba de creación).
"""

import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config.blocus import FALSOS_POSITIVOS, NOTA_FALSOS_POSITIVOS, destino, primera_publicacion_espana, rotular_ambito

ROOT = Path(__file__).resolve().parents[1]
USUARIOS = ROOT / "data/blocus/datos/usuarios_fecha_creacion/usuarios_por_fecha_creacion.csv"
OBJETIVOS = ROOT / "data/blocus/datos/grafo_blocus_20261025/cuentas.csv"
RELACIONES = ROOT / "data/blocus/datos/grafo_blocus_20261025/relaciones.csv"
COMENTARIOS = ROOT / "data/blocus/datos/comentarios_blocus_20261026/comentarios.csv"
SALIDA = ROOT / "data/blocus/datos/grafo_blocus_20261025/fechas_creacion_cuentas.png"
LOGO = ROOT / "assets/tiktok_logo.jpg"
MESES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    objetivos = {c["user_id"] for c in leer(OBJETIVOS) if c["objetivo"] and c["username"] not in FALSOS_POSITIVOS}
    usuarios = leer(USUARIOS)
    audiencia = set()  # seguidores y seguidos: el otro extremo de cada relación con una cuenta válida
    for r in leer(RELACIONES):
        o, d = r["source"].removeprefix("uid:"), r["target"].removeprefix("uid:")
        if o in objetivos or d in objetivos:
            audiencia.update((o, d))
    comentan = {r["autor_id"] for r in leer(COMENTARIOS) if r["cuenta_publicadora"] not in FALSOS_POSITIVOS}
    grupos = {
        "cuentas analizadas": [u for u in usuarios if u["user_id"] in objetivos],
        "seguidores y seguidos de esas cuentas": [u for u in usuarios if u["user_id"] in audiencia],
        "cuentas que comentan": [u for u in usuarios if u["user_id"] in comentan],
    }
    meses = [(a, m) for a in range(2018, 2027) for m in range(1, 13) if (a, m) <= (2026, 10)]
    fig, axes = plt.subplots(3, 1, figsize=(16, 9), dpi=100, facecolor="white", sharex=True)
    fig.subplots_adjust(left=0.06, right=0.97, top=0.84, bottom=0.12, hspace=0.5)
    for ax, (nombre, filas) in zip(axes, grupos.items()):
        conf, est = Counter(), Counter()
        sin = 0
        for u in filas:
            f = u["fecha_orden_utc"][:7]
            if not f:
                sin += 1
                continue
            clave = (int(f[:4]), int(f[5:7]))
            (conf if u["tipo_fecha"] == "Confirmada por perfil" else est)[clave] += 1
        x = range(len(meses))
        ax.bar(x, [est[m] for m in meses], color="#9DB7CF", label="fecha estimada (UID)", width=0.85)
        ax.bar(x, [conf[m] for m in meses], bottom=[est[m] for m in meses], color="#1F618D",
               label="confirmada por el perfil", width=0.85)
        ax.set_title(f"{nombre.lower()} ({len(filas):,}".replace(",", ".") + (f"; {sin} sin fecha)" if sin else ")"),
                     loc="left", fontsize=11, fontweight="bold", color="#222222")
        ax.grid(axis="y", color="#EBEBEB")
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        ax.tick_params(labelsize=8)
        pico = max(range(len(meses)), key=lambda i: conf[meses[i]] + est[meses[i]])
        total = conf[meses[pico]] + est[meses[pico]]
        ax.annotate(f"pico: {MESES_ES[meses[pico][1] - 1]} {meses[pico][0]} ({total:,})".replace(",", "."),
                    (pico, total), xytext=(0, 6), textcoords="offset points", ha="center", va="bottom", fontsize=8.5, color="#A93226",
                    bbox=dict(boxstyle="round,pad=0.3", fc="#F7F7F7", ec="#CCCCCC"))
        ax.set_ylim(top=ax.get_ylim()[1] * 1.15)
    primera, cuenta_primera = primera_publicacion_espana()
    i = meses.index((primera.year, primera.month))
    x_primera = i - 0.5 + (primera.day - 1 + primera.hour / 24) / 31  # posición dentro de la barra del mes
    for ax in axes:
        ax.axvline(x_primera, color="#C0392B", lw=0.8, zorder=4)
    axes[0].annotate(f"Primera publicación sobre España: {primera:%d/%m/%Y} (@{cuenta_primera})", (x_primera, 0.62), xycoords=("data", "axes fraction"),
                     xytext=(-14, 0), textcoords="offset points", ha="right", va="center", fontsize=8.5, color="#C0392B")
    axes[0].legend(loc="upper left", fontsize=8, frameon=False)
    marcas = [i for i, (a, m) in enumerate(meses) if m == 1]
    axes[-1].set_xticks(marcas)
    axes[-1].set_xticklabels([str(meses[i][0]) for i in marcas])
    fig.text(0.04, 0.95, "cuándo se crearon las cuentas blocus, sus seguidores y sus comentaristas",
             fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.915, "cuentas creadas por mes de creación (UTC); fecha del perfil cuando se ha consultado, "
             "estimada por UID en el resto", fontsize=10.5, color="#555555")
    fig.text(0.04, 0.03, "La fecha estimada UID >> 32 es una aproximación técnica y no prueba la creación de la cuenta. "
             "Las fechas confirmadas son una muestra sesgada: se priorizaron los últimos de cada lista.",
             fontsize=8.5, color="#555555")
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage
        fig.add_artist(AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.93),
                                      xycoords="figure fraction", frameon=False))
    fig.text(0.04, 0.005, NOTA_FALSOS_POSITIVOS, fontsize=8.5, color="#A93226")
    rotular_ambito(fig)
    fig.savefig(destino(SALIDA), facecolor="white")
    print(destino(SALIDA))


if __name__ == "__main__":
    main()
