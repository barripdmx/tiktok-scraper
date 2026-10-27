"""Gráfica de las cuentas Blocus analizadas: en rojo las que no tienen relación con las demás.

Relación entre cuentas analizadas: una sigue a otra (relaciones.csv) o una comenta/responde
en las publicaciones de otra (comentarios.csv). No incluye audiencias compartidas.
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
GRAFO = ROOT / "outputs/grafo_blocus_20261025"
COMENT = ROOT / "outputs/comentarios_blocus_20261026/comentarios.csv"
SALIDA = GRAFO / "cuentas_analizadas_relaciones.png"
LOGO = ROOT / "assets/tiktok_logo.jpg"
FONDO_CAJA = dict(boxstyle="round,pad=0.5", fc="#F7F7F7", ec="#CCCCCC")


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def construir():
    cuentas = {c["user_id"]: c["username"] for c in leer(GRAFO / "cuentas.csv") if c["objetivo"]}
    por_nombre = {n: i for i, n in cuentas.items()}
    aristas = {}  # (origen, destino) -> {"sigue": bool, "comenta": n}
    for r in leer(GRAFO / "relaciones.csv"):
        o, d = r["source"].removeprefix("uid:"), r["target"].removeprefix("uid:")
        if o in cuentas and d in cuentas and o != d:
            aristas.setdefault((o, d), {"sigue": False, "comenta": 0})["sigue"] = True
    for r in leer(COMENT):
        o, d = r["autor_id"], por_nombre.get(r["cuenta_publicadora"])
        if o in cuentas and d and o != d:
            aristas.setdefault((o, d), {"sigue": False, "comenta": 0})["comenta"] += 1
    return cuentas, aristas


def main():
    cuentas, aristas = construir()
    g = nx.Graph()
    g.add_nodes_from(cuentas)
    g.add_edges_from(aristas)
    aislados = sorted((n for n in g if g.degree(n) == 0), key=lambda n: cuentas[n])
    conectados = [n for n in g if g.degree(n) > 0]
    print(f"{len(cuentas)} cuentas, {len(aristas)} relaciones, {len(aislados)} sin relación")

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor="white")
    ax = fig.add_axes([0.02, 0.1, 0.62, 0.78])
    ax.axis("off")
    ax.set_xlim(-0.35, 1.25)
    sub = g.subgraph(conectados)
    pos = nx.rescale_layout_dict(nx.spring_layout(sub, seed=7, k=1.2), scale=1)
    pos = {n: ((x + 1) / 2, y) for n, (x, y) in pos.items()}
    estilo = {"sigue": ("#1F618D", "-"), "comenta": ("#CA6F1E", "--")}
    for (o, d), t in aristas.items():
        for tipo in ("sigue", "comenta"):
            if t[tipo]:
                color, ls = estilo[tipo]
                ax.annotate("", xy=pos[d], xytext=pos[o], arrowprops=dict(
                    arrowstyle="-|>", color=color, ls=ls, lw=1.6, shrinkA=9, shrinkB=9,
                    connectionstyle="arc3,rad=0.12" if tipo == "sigue" else "arc3,rad=-0.12"))
    nx.draw_networkx_nodes(sub, pos, ax=ax, node_color="#4A4A4A", node_size=260)
    nx.draw_networkx_labels(sub, pos, {n: "@" + cuentas[n] for n in sub}, ax=ax,
                            font_size=8, verticalalignment="bottom", clip_on=False)

    ax2 = fig.add_axes([0.66, 0.1, 0.32, 0.78])
    ax2.axis("off")
    ax2.set_xlim(0, 2)
    filas = -(-len(aislados) // 2)
    ax2.set_ylim(-filas - 0.5, 1.2)
    ax2.text(0, 0.9, f"sin ninguna relación ({len(aislados)})", color="#A93226", fontsize=12, fontweight="bold")
    for i, n in enumerate(aislados):
        x, y = (i // filas) * 1.0, -(i % filas) - 0.2
        ax2.scatter(x + 0.05, y, s=70, color="#C0392B", zorder=3)
        ax2.text(x + 0.12, y, "@" + cuentas[n], va="center", fontsize=8, color="#C0392B")

    fig.text(0.04, 0.94, f"cuentas blocus analizadas: {len(cuentas)}, de las que {len(aislados)} no guardan "
             "relación con las demás", fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.905, "relación = una cuenta sigue a otra, o comenta/responde en sus publicaciones "
             "(solo entre cuentas analizadas)", fontsize=10.5, color="#555555")
    n_sig = sum(t["sigue"] for t in aristas.values())
    n_com = sum(bool(t["comenta"]) for t in aristas.values())
    fig.text(0.04, 0.07, f"azul continua: sigue a ({n_sig}) · naranja discontinua: comenta en ({n_com}). "
             "Capturas del 25-26/10/2026. Que no haya relación observada no demuestra que no exista; "
             "tampoco su presencia demuestra coordinación.", fontsize=8.5, color="#555555", wrap=True)
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage
        marca = AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.12),
                               xycoords="figure fraction", frameon=False)
        fig.add_artist(marca)
    fig.savefig(SALIDA, facecolor="white")
    print(SALIDA)


if __name__ == "__main__":
    main()
