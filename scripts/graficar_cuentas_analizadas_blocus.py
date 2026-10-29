"""Gráfica de las cuentas Blocus analizadas: en rojo las que no tienen relación con las demás.

Relación entre dos cuentas analizadas: una sigue a la otra o comenta en sus publicaciones, o
comparten audiencia (usuarios que siguen/son seguidos por ambas o comentan en ambas).
Rojo: ninguna de las dos cosas con ninguna otra cuenta analizada.
"""

import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from config.blocus import AMBITO, COLOR_TEMA, FALSOS_POSITIVOS, FALSOS_POSITIVOS_BASE, NOTA_FALSOS_POSITIVOS, destino, tema_de_cuentas

ROOT = Path(__file__).resolve().parents[1]
GRAFO = ROOT / "data/blocus/datos/grafo_blocus_20261025"
COMENT = ROOT / "data/blocus/datos/comentarios_blocus_20261026/comentarios.csv"
SALIDA = GRAFO / "cuentas_analizadas_relaciones.png"
HILO = ROOT / "data/blocus/graficas/Hilo_twitter_blocus_españa"
LOGO = ROOT / "assets/tiktok_logo.jpg"
FONDO_CAJA = dict(boxstyle="round,pad=0.5", fc="#F7F7F7", ec="#CCCCCC")


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def construir():
    cuentas = {c["user_id"]: c["username"] for c in leer(GRAFO / "cuentas.csv") if c["objetivo"] and c["username"] not in FALSOS_POSITIVOS}
    por_nombre = {n: i for i, n in cuentas.items()}
    directas = {}  # (origen, destino) -> {"sigue": bool, "comenta": n}
    audiencia = defaultdict(set)  # cuenta -> usuarios que la siguen, que ella sigue o que la comentan
    for r in leer(GRAFO / "relaciones.csv"):
        o, d = r["source"].removeprefix("uid:"), r["target"].removeprefix("uid:")
        if d in cuentas:
            audiencia[d].add(o)
        if o in cuentas:
            audiencia[o].add(d)
        if o in cuentas and d in cuentas and o != d:
            directas.setdefault((o, d), {"sigue": False, "comenta": 0})["sigue"] = True
    for r in leer(COMENT):
        o, d = r["autor_id"], por_nombre.get(r["cuenta_publicadora"])
        if d:
            audiencia[d].add(o)
        if o in cuentas and d and o != d:
            directas.setdefault((o, d), {"sigue": False, "comenta": 0})["comenta"] += 1
    comunes = {}
    ids = list(cuentas)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            n = len((audiencia[a] & audiencia[b]) - set(ids))
            if n:
                comunes[(a, b)] = n
    return cuentas, directas, comunes, audiencia


def main():
    cuentas, directas, comunes, audiencia = construir()
    g = nx.Graph()
    g.add_nodes_from(cuentas)
    g.add_edges_from(directas)
    g.add_weighted_edges_from((a, b, n) for (a, b), n in comunes.items())
    aislados = sorted((n for n in g if g.degree(n) == 0), key=lambda n: cuentas[n])
    conectados = [n for n in g if g.degree(n) > 0]
    print(f"{len(cuentas)} cuentas, {len(directas)} directas, {len(comunes)} pares con audiencia común, "
          f"{len(aislados)} sin relación")

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor="white")
    ax = fig.add_axes([0.0, 0.1, 0.8, 0.68])
    ax.axis("off")
    sub = g.subgraph(conectados)
    orden = sorted(sub, key=lambda n: -sub.degree(n, weight="weight"))
    orden = orden[0::2] + orden[1::2][::-1]  # las más conectadas a ambos lados, pegadas
    ang = {n: 2 * math.pi * i / len(orden) for i, n in enumerate(orden)}
    pos = {n: (0.85 * math.cos(a), 0.85 * math.sin(a)) for n, a in ang.items()}
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.3, 1.3)
    ax.set_aspect('equal')
    maximo = max(comunes.values())
    for (a, b), n in comunes.items():
        ax.plot(*zip(pos[a], pos[b]), color="#6C7A89", alpha=min(0.7, 0.18 + 1.5 * n / maximo), zorder=1,
                lw=0.5 + 3.6 * n / maximo)
    estilo = {"sigue": "#1F618D", "comenta": "#CA6F1E"}
    for (o, d), t in directas.items():
        for tipo in ("sigue", "comenta"):
            if t[tipo]:
                ax.annotate("", xy=pos[d], xytext=pos[o], zorder=2, arrowprops=dict(
                    arrowstyle="-|>", color=estilo[tipo], ls="-" if tipo == "sigue" else "--", lw=1.8,
                    shrinkA=6, shrinkB=6, connectionstyle="arc3,rad=0.2" if tipo == "sigue" else "arc3,rad=-0.2"))
    tam = {n: 25 + 6 * len(audiencia[n]) ** 0.5 for n in sub}
    tema = tema_de_cuentas()
    por_tema = AMBITO == "espana"
    nx.draw_networkx_nodes(sub, pos, ax=ax, node_size=[tam[n] for n in sub], node_color=[
        COLOR_TEMA[tema.get(cuentas[n], "sin clasificar")] if por_tema else "#4A4A4A" for n in sub])
    for n in sub:
        a = ang[n]
        izq = math.cos(a) < 0
        rho = 0.9 + 0.0045 * tam[n] ** 0.5
        ax.text(rho * math.cos(a), rho * math.sin(a), "@" + cuentas[n], fontsize=7, va="center",
                ha="right" if izq else "left", rotation=math.degrees(a) + (180 if izq else 0),
                rotation_mode="anchor")

    ax2 = fig.add_axes([0.8, 0.1, 0.19, 0.78])
    ax2.axis("off")
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    color_aislado = "#555555" if por_tema else "#C0392B"
    ax2.text(0, 0.98, f"cuentas analizadas ({len(cuentas)})", fontsize=12, fontweight="bold", color="#222222")
    ax2.text(0, 0.94, f"en rojo, sin ninguna relación ({len(aislados)})" if not por_tema else
             f"en negrita, sin ninguna relación ({len(aislados)})", fontsize=8.5, color=color_aislado)
    todas = sorted(cuentas, key=lambda n: cuentas[n].lower())
    filas = (len(todas) + 1) // 2
    for i, n in enumerate(todas):
        x, y = 0.04 + 0.5 * (i // filas), 0.89 - 0.030 * (i % filas)
        aislada = n in aislados
        col = color_aislado if aislada else (COLOR_TEMA[tema.get(cuentas[n], "sin clasificar")] if por_tema else "#4A4A4A")
        ax2.scatter(x, y, s=14, color=col, zorder=3)
        ax2.text(x + 0.03, y, "@" + cuentas[n], va="center", fontsize=7, color=col, fontweight="bold" if aislada else "normal")
    etiqueta = "de España" if por_tema else "analizadas"
    fig.text(0.04, 0.94, f"cuentas blocus {etiqueta}: {len(cuentas)}, de las que {len(aislados)} no guardan "
             "ninguna relación con las demás", fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.905, "con relación = se siguen o se comentan entre sí, o comparten usuarios (seguidores, seguidos o comentaristas) · "
             "tamaño del nodo: usuarios vinculados" + chr(10) + "sin relación = ninguna otra cuenta analizada la sigue ni la comenta, y sus "
             "usuarios no coinciden con los de ninguna otra", fontsize=10.5, color="#555555", va="top")
    n_sig = sum(t["sigue"] for t in directas.values())
    n_com = sum(bool(t["comenta"]) for t in directas.values())
    fig.text(0.04, 0.05, f"flechas azules: sigue a ({n_sig}) · naranjas: comenta en ({n_com}) · líneas grises: "
             f"audiencia compartida ({len(comunes)} pares, grosor = nº de usuarios comunes, hasta {maximo}). "
             "Capturas del 25-26/10/2026.\n"
             "Que no haya relación observada no demuestra que no exista; "
             "tampoco su presencia demuestra coordinación.", fontsize=8.5, color="#555555")
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage
        marca = AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.12),
                               xycoords="figure fraction", frameon=False)
        fig.add_artist(marca)
    fig.text(0.04, 0.005, NOTA_FALSOS_POSITIVOS, fontsize=8.5, color="#A93226")
    ax2.text(0, 0.1, "falso positivo, excluidas:" + chr(10) + chr(10).join("@" + c for c in FALSOS_POSITIVOS_BASE),
             fontsize=8, color="#7F8C8D", va="top")
    fig.savefig(destino(SALIDA), facecolor="white")
    print(destino(SALIDA))
    if not AMBITO:  # la imagen 01 del hilo es la de las 50 cuentas, no la del ámbito España
        HILO.mkdir(parents=True, exist_ok=True)
        fig.savefig(HILO / "01_cuentas_analizadas_relaciones.png", facecolor="white")


if __name__ == "__main__":
    main()
