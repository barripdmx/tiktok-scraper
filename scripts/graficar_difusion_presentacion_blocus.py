"""Gráficas 8 y 10 de la presentación: grafo de difusión entre cuentas y matriz de hallazgos."""

import csv
import math
import statistics
from datetime import datetime
from collections import Counter, defaultdict
from itertools import combinations

import matplotlib.pyplot as plt
from matplotlib.patheffects import withStroke
import networkx as nx
from matplotlib.patches import Patch

from config.blocus import AMBITO, FALSOS_POSITIVOS
from scripts.analisis_emojis_blocus import cargar, resumen
from scripts.tema_cuentas_blocus import temas
from scripts.estilo_presentacion_blocus import AZUL, CLARO, GRIS, NARANJA, ROJO, ROOT, guardar, limpiar, nueva

GRAFO = ROOT / "data/blocus/datos/grafo_blocus_20261025"
COMENTARIOS = ROOT / "data/blocus/datos/comentarios_blocus_20261026/comentarios.csv"
USUARIOS = ROOT / "data/blocus/datos/usuarios_fecha_creacion/usuarios_por_fecha_creacion.csv"
COLOR_TEMA = {"francés": "#1F618D", "español": "#C0392B", "común": "#1E8449", "sin clasificar": "#7F8C8D"}
RECORRIDO = ("volem.graduacio", "blocuses", "manifestacion_barcelona")  # autor y las dos cuentas donde repite el texto


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def relaciones():
    cuentas = {c["user_id"]: c["username"] for c in leer(GRAFO / "cuentas.csv")
               if c["objetivo"] and c["username"] not in FALSOS_POSITIVOS}
    sigue, comenta = set(), set()
    for r in leer(GRAFO / "relaciones.csv"):
        o, d = r["source"].removeprefix("uid:"), r["target"].removeprefix("uid:")
        if o in cuentas and d in cuentas and o != d:
            sigue.add((cuentas[o], cuentas[d]))
    comentarios = [r for r in leer(COMENTARIOS) if r["cuenta_publicadora"] not in FALSOS_POSITIVOS]
    nombre = dict(cuentas)
    for r in comentarios:
        if r["autor_id"] in nombre and nombre[r["autor_id"]] != r["cuenta_publicadora"]:
            comenta.add((nombre[r["autor_id"]], r["cuenta_publicadora"]))
    cuentas_por_autor = defaultdict(set)
    for r in comentarios:
        cuentas_por_autor[r["autor_id"]].add(r["cuenta_publicadora"])
    compartidos = defaultdict(int)
    for cs in cuentas_por_autor.values():
        for a, b in combinations(sorted(cs), 2):
            compartidos[(a, b)] += 1
    multi = [cs for cs in cuentas_por_autor.values() if len(cs) >= 2]
    return sigue, comenta, compartidos, multi


def colocar_etiquetas(fig, ax, pos, tam, cuadro=None):
    """Pone «@cuenta» junto a cada nodo en la posición libre más cercana (sin pisar nodos, otras etiquetas ni el cuadro)."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    k = fig.dpi / 72
    nodos = {n: (ax.transData.transform(p), (tam[n] ** 0.5 / 2 + 2) * k) for n, p in pos.items()}
    ocupado = [cuadro.get_window_extent(rend)] if cuadro is not None else []
    cajas = {}
    candidatos = [(9, 5, "left", "bottom"), (9, -5, "left", "top"), (-9, 5, "right", "bottom"), (-9, -5, "right", "top"),
                  (0, 11, "center", "bottom"), (0, -11, "center", "top"), (16, 14, "left", "bottom"), (-16, 14, "right", "bottom"),
                  (16, -14, "left", "top"), (-16, -14, "right", "top"), (0, 22, "center", "bottom"), (0, -22, "center", "top")]
    area = ax.get_window_extent(rend)
    for n in sorted(pos, key=lambda x: -tam[x]):
        mejor = None
        for dx, dy, ha, va in candidatos:
            t = ax.annotate("@" + n, pos[n], xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, fontsize=8, zorder=7,
                            path_effects=[withStroke(linewidth=3, foreground="white")])
            b = t.get_window_extent(rend).expanded(1.04, 1.1)
            choques = sum(b.overlaps(o) for o in ocupado) + sum(b.overlaps(c) for c in cajas.values())
            for m, ((cx, cy), r) in nodos.items():
                if b.x0 - r < cx < b.x1 + r and b.y0 - r < cy < b.y1 + r:
                    choques += 1
            fuera = not (area.x0 <= b.x0 and b.x1 <= area.x1 and area.y0 <= b.y0 and b.y1 <= area.y1)
            puntos = choques + (3 if fuera else 0)
            if mejor is None or puntos < mejor[0]:
                if mejor is not None:
                    mejor[1].remove()
                mejor = (puntos, t, b)
            else:
                t.remove()
            if puntos == 0:
                break
        cajas[n] = mejor[2]


def grafica_8(por_tema=False, todas=False):
    """todas=True: mismo formato, pero con las relaciones de la gráfica 01 (incluye la audiencia compartida de seguidores y seguidos)."""
    sigue, comenta, compartidos, multi = relaciones()
    if todas:
        from scripts.graficar_cuentas_analizadas_blocus import construir
        nombres, _, comunes, _ = construir()
        compartidos = {(nombres[a], nombres[b]): n for (a, b), n in comunes.items()}
    tema = temas() if por_tema else {}
    c_sigue, c_recorrido = ("#222222", "#7D3C98") if por_tema else (AZUL, ROJO)
    g = nx.Graph()
    for a, b in list(sigue) + list(comenta) + list(compartidos):
        g.add_edge(a, b)
    pos = nx.spring_layout(g, seed=11, k=5.0 if todas else 2.4, iterations=400)
    fig, ax = nueva(("difusión entre cuentas de España" if AMBITO == "espana" else "difusión entre cuentas por tema: Francia y España") if por_tema else "difusión entre cuentas: " + ("todas las relaciones" if todas else "enlaces documentados"),
                    f"{g.number_of_nodes()} cuentas con " + ("alguna relación, incluida la audiencia compartida de seguidores y seguidos"
                    if todas else "al menos un enlace documentado (seguir, comentar o comentaristas comunes)") + "; cada línea indica qué relación representa",
                    f"{len(multi)} autores comentan en 2 o más cuentas ({sum(len(c) >= 3 for c in multi)} en 3 o más): una persona comentando "
                    "en varias cuentas no demuestra coordinación." + chr(10) + "Seguir y comentar es lo observado, no todo lo existente: de @teamblocus se capturaron 9.995 de 37.500 seguidores y varias listas de seguidos no estaban disponibles." + (" Tamaño del nodo: nº de cuentas con las que se relaciona." if todas else ""))
    ax.axis("off")
    for (a, b), n in compartidos.items():
        ax.plot(*zip(pos[a], pos[b]), color="#9AA5AE", lw=min(0.5 + (0.25 if todas else 1.4) * n, 8), alpha=0.35 if todas else 0.6, zorder=1)
    for a, b in sigue:
        ax.annotate("", xy=pos[b], xytext=pos[a], zorder=2, arrowprops=dict(arrowstyle="-|>", color=c_sigue, lw=2,
                    shrinkA=9, shrinkB=9, connectionstyle="arc3,rad=0.15"))
    for a, b in comenta:
        ax.annotate("", xy=pos[b], xytext=pos[a], zorder=2, arrowprops=dict(arrowstyle="-|>", color=NARANJA, lw=2, ls="--",
                    shrinkA=9, shrinkB=9, connectionstyle="arc3,rad=-0.15"))
    ax.set_position([0.03, 0.13, 0.74, 0.75])
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    ax.set_xlim(min(xs) - 0.25, max(xs) + 0.3)
    ax.set_ylim(min(ys) - 0.15, max(ys) + 0.35)
    autor, c1, c2 = RECORRIDO
    cuadro = None
    if c1 in pos and c2 in pos:
        ax.plot(*zip(pos[c1], pos[c2]), color=c_recorrido, lw=3.2, zorder=3)
        xm, ym = (pos[c1][0] + pos[c2][0]) / 2, (pos[c1][1] + pos[c2][1]) / 2
        cuadro = ax.annotate(f"@{autor} publica el mismo texto en ambas" + chr(10) + "(20/10: 14:47 y 17:05 UTC): pide compartir la cuenta",
                             (xm, ym), xytext=(0.62, 0.95), textcoords="axes fraction", ha="center", va="top", fontsize=8.5,
                             color=c_recorrido, arrowprops=dict(arrowstyle="-", color=c_recorrido, lw=0.8),
                             bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=c_recorrido), zorder=6)
    grado = dict(g.degree())
    tam = {n: (30 + 5 * grado[n]) if todas else 60 + 40 * grado[n] for n in g}
    ax.scatter([pos[n][0] for n in g], [pos[n][1] for n in g], s=[tam[n] for n in g],
               color=[COLOR_TEMA[tema.get(n, "sin clasificar")] if por_tema else GRIS for n in g], zorder=4)
    colocar_etiquetas(fig, ax, pos, tam, cuadro)
    aristas = [Patch(color=c_sigue, label="sigue a (flecha; observado)"), Patch(color=NARANJA, label="comenta en (flecha discontinua; observado)"),
               Patch(color="#9AA5AE", label="usuarios comunes (grosor = nº)" if todas else "autores comunes (grosor = nº de autores)"),
               Patch(color=c_recorrido, label="recorrido de un texto repetido")]
    if por_tema:
        n = Counter(tema.get(x, "sin clasificar") for x in g)
        nodos = [Patch(color=COLOR_TEMA[t], label=f"tema {t} ({n[t]})") for t in ("francés", "español", "común") if n[t]]
        fig.legend(handles=nodos, loc="upper left", bbox_to_anchor=(0.79, 0.78), frameon=False, fontsize=10, title="color del nodo",
                   alignment="left")
    fig.legend(handles=aristas, loc="upper left", bbox_to_anchor=(0.79, 0.52 if por_tema else 0.78), frameon=False, fontsize=9,
               title="líneas", alignment="left")
    guardar(fig, "08_red_todas_las_cuentas.png" if todas else "08_difusion_por_tema.png" if por_tema else "08_difusion_entre_cuentas.png")


def grafica_10():
    cuentas = [c for c in leer(GRAFO / "cuentas.csv") if c["objetivo"] and c["username"] not in FALSOS_POSITIVOS]
    fechas = {u["user_id"]: u for u in leer(USUARIOS)}
    nuevas = [c for c in cuentas if fechas[c["user_id"]]["fecha_orden_utc"][:7] >= "2026-09"]
    confirmadas = sum(fechas[c["user_id"]]["tipo_fecha"] == "Confirmada por perfil" for c in cuentas)
    _, _, _, multi = relaciones()
    t = sorted(datetime.fromisoformat(r["creado_utc"]) for r in resumen(cargar()[0])[0] if r["atipico"])
    huecos = [(b - a).total_seconds() for a, b in zip(t, t[1:])]
    mediana, rapidos = statistics.median(huecos) / 60, sum(h < 60 for h in huecos)
    columnas = ["caso", "concentración", "sincronía", "repetición", "contexto", "datos ausentes", "estado"]
    filas = [
        ("@teamblocus: emojis atípicos",
         "241 de 781 comentarios\n(18 de 9.653 en el resto)", f"No: intervalo mediano {mediana:.0f} min,\n{rapidos} pares a menos de 1 min",
         "Ningún texto se repite;\n466 emojis distintos", "Autoras creadas mar-sep 2026\n(fecha estimada por UID)",
         "Contenido del vídeo; si las\ncuentas siguen activas", "Observado\n(origen: hipótesis)"),
        ("Cuentas analizadas creadas\ndesde sept. 2026",
         f"{len(nuevas)} de {len(cuentas)} cuentas\n({100 * len(nuevas) / len(cuentas):.0f} %)", "Sí: creadas en los 2 meses\nanteriores a la captura",
         "—", "Convocatorias del 17, 24 y 31/10",
         f"{confirmadas} de {len(cuentas)} con fecha confirmada\nen el perfil; quién las creó", "Observado"),
        ("@volem.graduacio: mismo\ntexto en 2 cuentas",
         "2 comentarios idénticos\n(1 autor)", "2 h 18 min entre ambos\n(20/10)", "Texto idéntico en @blocuses\ny @manifestacion_barcelona",
         "Pide compartir la cuenta\ny llegar a institutos", "Si hay contacto con las cuentas;\nresto de su actividad", "Observado\n(coordinación: hipótesis)"),
        ("Picos del 17/10 en @blocussss_",
         "2 vídeos: 1.253 comentarios\ncapturados", "Sí: picos a las 6 h 49 min y 38 min\nde publicar (18 y 32 autores en 10 min)",
         "No: textos variados", "Vídeos de convocatoria del 17/10;\ncuentas de edades variadas", "Alcance real de los vídeos", "Observado\n(viral normal)"),
        (f"{len(multi)} autores en varias cuentas",
         "2 cuentas la mayoría;\n5 autores en 3", "Sin patrón claro", "Pocos casos repetidos", "Fechas de creación de\n2017 a 2026, sin agrupar",
         "Contenido y contexto de\ncada comentario", "Sin patrón"),
        ("País de creación declarado",
         "Francia 213, Bélgica 31,\nEspaña 12, sin dato 46", "—", "—", "Dato de TikTok; puede reflejar VPN",
         "Dónde está realmente\nquien publica", "No usar como origen"),
    ]
    colores = {"Observado": "#D5E8D4", "Sin patrón": "#EEEEEE", "No usar": "#F4CCCC"}
    fig, ax = nueva("qué está demostrado, qué es hipótesis y qué falta",
                    "casos revisados y el tipo de evidencia disponible; sin puntuación de «probabilidad de bots»",
                    "«Observado» describe un patrón en los datos; las explicaciones (automatización, coordinación) son hipótesis "
                    "hasta verificarlas fuera de este conjunto de datos.")
    ax.axis("off")
    tabla = ax.table(cellText=filas, colLabels=columnas, loc="center", cellLoc="left", colLoc="left",
                     colWidths=[0.17, 0.13, 0.17, 0.14, 0.14, 0.15, 0.10])
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(7.6)
    tabla.scale(1, 3.9)
    for (i, j), celda in tabla.get_celld().items():
        celda.set_edgecolor("#DDDDDD")
        if i == 0:
            celda.set_facecolor("#222222")
            celda.set_text_props(color="white", fontweight="bold")
        elif j == 0:
            celda.set_text_props(fontweight="bold")
        elif j == len(columnas) - 1:
            celda.set_facecolor(next((v for k, v in colores.items() if filas[i - 1][j].startswith(k)), "#FFF2CC"))
    guardar(fig, "10_matriz_hallazgos.png")


if __name__ == "__main__":
    grafica_8()
    grafica_8(por_tema=True)
    if not AMBITO:
        grafica_8(todas=True)
    if AMBITO != "espana":  # la matriz de hallazgos describe casos concretos del conjunto completo
        grafica_10()
