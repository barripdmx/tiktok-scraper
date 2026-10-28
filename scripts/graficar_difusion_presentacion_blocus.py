"""Gráficas 8 y 10 de la presentación: grafo de difusión entre cuentas y matriz de hallazgos."""

import csv
import math
import statistics
from datetime import datetime
from collections import Counter, defaultdict
from itertools import combinations

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.patches import Patch

from config.blocus import FALSOS_POSITIVOS
from scripts.analisis_emojis_blocus import cargar, resumen
from scripts.tema_cuentas_blocus import temas
from scripts.estilo_presentacion_blocus import AZUL, CLARO, GRIS, NARANJA, ROJO, ROOT, guardar, limpiar, nueva

GRAFO = ROOT / "outputs/grafo_blocus_20261025"
COMENTARIOS = ROOT / "outputs/comentarios_blocus_20261026/comentarios.csv"
USUARIOS = ROOT / "outputs/01a173e7-58a9-7d53-a645-746d1a51b712/usuarios_por_fecha_creacion.csv"
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


def grafica_8(por_tema=False):
    sigue, comenta, compartidos, multi = relaciones()
    tema = temas() if por_tema else {}
    c_sigue, c_recorrido = ("#222222", "#7D3C98") if por_tema else (AZUL, ROJO)
    g = nx.Graph()
    for a, b in list(sigue) + list(comenta) + list(compartidos):
        g.add_edge(a, b)
    pos = nx.spring_layout(g, seed=11, k=1.1, iterations=300)
    fig, ax = nueva("difusión entre cuentas por tema: Francia, España y cuentas comunes" if por_tema else "difusión entre cuentas: enlaces documentados",
                    f"{g.number_of_nodes()} cuentas con al menos un enlace observado; cada línea indica qué relación representa",
                    f"{len(multi)} autores comentan en 2 o más cuentas ({sum(len(c) >= 3 for c in multi)} en 3 o más): una persona comentando "
                    "en varias cuentas no demuestra coordinación. Los enlaces entre cuentas son pocos.")
    ax.axis("off")
    for (a, b), n in compartidos.items():
        ax.plot(*zip(pos[a], pos[b]), color="#9AA5AE", lw=min(0.8 + 1.4 * n, 8), alpha=0.6, zorder=1)
    for a, b in sigue:
        ax.annotate("", xy=pos[b], xytext=pos[a], zorder=2, arrowprops=dict(arrowstyle="-|>", color=c_sigue, lw=2,
                    shrinkA=9, shrinkB=9, connectionstyle="arc3,rad=0.15"))
    for a, b in comenta:
        ax.annotate("", xy=pos[b], xytext=pos[a], zorder=2, arrowprops=dict(arrowstyle="-|>", color=NARANJA, lw=2, ls="--",
                    shrinkA=9, shrinkB=9, connectionstyle="arc3,rad=-0.15"))
    autor, c1, c2 = RECORRIDO
    if c1 in pos and c2 in pos:
        ax.plot(*zip(pos[c1], pos[c2]), color=c_recorrido, lw=3.2, zorder=3)
        xm, ym = (pos[c1][0] + pos[c2][0]) / 2, (pos[c1][1] + pos[c2][1]) / 2
        ax.annotate(f"@{autor} publica el mismo texto en ambas\n(20/10: 14:47 y 17:05 UTC): pide compartir la cuenta",
                    (xm, ym), xytext=(-250, 45), textcoords="offset points", fontsize=8.5, color=c_recorrido,
                    arrowprops=dict(arrowstyle="-", color=c_recorrido, lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=c_recorrido))
    grado = dict(g.degree())
    ax.scatter([pos[n][0] for n in g], [pos[n][1] for n in g], s=[60 + 40 * grado[n] for n in g],
               color=[COLOR_TEMA[tema.get(n, "sin clasificar")] if por_tema else GRIS for n in g], zorder=4)
    for n in g:
        ax.annotate("@" + n, pos[n], xytext=(7, 7), textcoords="offset points", fontsize=8, zorder=5)
    aristas = [Patch(color=c_sigue, label="sigue a (flecha)"), Patch(color=NARANJA, label="comenta en (flecha discontinua)"),
               Patch(color="#9AA5AE", label="autores comunes (grosor = nº de autores)"),
               Patch(color=c_recorrido, label="recorrido de un texto repetido")]
    if por_tema:
        n = Counter(tema.get(x, "sin clasificar") for x in g)
        nodos = [Patch(color=COLOR_TEMA[t], label=f"tema {t} ({n[t]})") for t in ("francés", "español", "común") if n[t]]
        ax.add_artist(ax.legend(handles=nodos, loc="lower left", frameon=False, fontsize=10, title="color del nodo"))
    ax.legend(handles=aristas, loc="lower right", frameon=False, fontsize=9)
    guardar(fig, "08_difusion_por_tema.png" if por_tema else "08_difusion_entre_cuentas.png")


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
    grafica_10()
