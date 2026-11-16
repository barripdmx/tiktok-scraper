"""Comentarios de las publicaciones Blocus por día y cuenta publicadora."""

import csv
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from config.blocus import AMBITO, COLOR_TEMA, FALSOS_POSITIVOS, NOTA_FALSOS_POSITIVOS, destino, rotular_ambito, tema_de_cuentas

ROOT = Path(__file__).resolve().parents[1]
ENTRADA = ROOT / "data/blocus/datos/comentarios_blocus_20261026/comentarios.csv"
SALIDA = ROOT / "data/blocus/datos/comentarios_blocus_20261026/comentarios_por_dia.png"
LOGO = ROOT / "assets/tiktok_logo.jpg"
COLORES = ["#1F618D", "#A93226", "#CA6F1E", "#1E8449", "#7D3C98", "#4A4A4A", "#C8CED3"]
DESDE = date(2026, 9, 25)  # antes de esta fecha hay solo unos pocos comentarios sueltos
TOP = 6


def main():
    por_dia = defaultdict(Counter)
    totales = Counter()
    for fila in csv.DictReader(ENTRADA.open(encoding="utf-8-sig", newline="")):
        if fila["cuenta_publicadora"] in FALSOS_POSITIVOS:
            continue
        dia = date.fromisoformat(fila["creado_utc"][:10])
        por_dia[dia][fila["cuenta_publicadora"]] += 1
        totales[fila["cuenta_publicadora"]] += 1
    principales = [c for c, _ in totales.most_common(TOP)]
    antes = sum(sum(c.values()) for d, c in por_dia.items() if d < DESDE)
    d0, d1 = (min(por_dia) if AMBITO == "espana" else DESDE), max(por_dia)
    dias = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
    series = {c: [por_dia[d][c] for d in dias] for c in principales}
    series["otras cuentas"] = [sum(v for k, v in por_dia[d].items() if k not in principales) for d in dias]
    colores = COLORES
    if AMBITO == "espana":  # solo dos series: cuentas de tema español (rojo) y cuentas comunes (verde)
        tema = tema_de_cuentas()
        comunes = [c for c in totales if tema.get(c) == "común"]
        series = {f"cuentas de tema español ({sum(v for c, v in totales.items() if c not in comunes):,})".replace(",", "."):
                  [sum(v for k, v in por_dia[d].items() if k not in comunes) for d in dias]}
        for c in comunes:
            series[f"@{c} (común, {totales[c]:,})".replace(",", ".")] = [por_dia[d][c] for d in dias]
        colores = [COLOR_TEMA["español"], COLOR_TEMA["común"]]
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor="white")
    fig.subplots_adjust(left=0.06, right=0.97, top=0.82, bottom=0.12)
    base = [0] * len(dias)
    for (c, vals), color in zip(series.items(), colores):
        ax.bar(dias, vals, bottom=base, color=color, width=0.85,
               label=(f"@{c} ({totales[c]:,})".replace(",", ".") if c in totales else c))
        base = [a + b for a, b in zip(base, vals)]
    ax.grid(axis="y", color="#EBEBEB")
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.tick_params(labelsize=8)
    ax.set_ylabel("comentarios por día", fontsize=9)
    suma = [sum(v[i] for v in series.values()) for i in range(len(dias))]
    pico = max(range(len(dias)), key=suma.__getitem__)
    ax.annotate(f"pico: {dias[pico]:%d/%m/%Y} ({suma[pico]:,})".replace(",", "."), (dias[pico], suma[pico]),
                xytext=(0, 6), textcoords="offset points", ha="center", va="bottom", fontsize=9, color="#A93226",
                bbox=dict(boxstyle="round,pad=0.3", fc="#F7F7F7", ec="#CCCCCC"))
    ax.set_ylim(top=ax.get_ylim()[1] * 1.12)  # hueco para el rótulo del pico sobre la barra
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    n = sum(totales.values())
    fig.text(0.04, 0.94, f"cuándo se escribieron los {n:,} comentarios capturados".replace(",", "."),
             fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.905, f"comentarios y respuestas por día (UTC), "
             f"del {d0:%d/%m/%Y} al {d1:%d/%m/%Y}" + ("; cuentas de tema español (28 publicaciones)" if AMBITO == "espana" else f"; las {TOP} cuentas con más comentarios por separado"),
             fontsize=10.5, color="#555555")
    fig.text(0.04, 0.03, (f"Se omiten {antes} comentarios anteriores al {DESDE:%d/%m/%Y}. " if antes else "") + f"Solo comentarios capturados el 26/10/2026; las publicaciones con comentarios parciales "
             "subrepresentan su actividad. Un pico indica una publicación muy comentada, no coordinación.",
             fontsize=8.5, color="#555555")
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage
        fig.add_artist(AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.93),
                                      xycoords="figure fraction", frameon=False))
    fig.text(0.04, 0.005, NOTA_FALSOS_POSITIVOS, fontsize=8.5, color="#A93226")
    rotular_ambito(fig)
    fig.savefig(destino(SALIDA), facecolor="white")
    if AMBITO == "espana":
        hilo = ROOT / "data/blocus/graficas/Hilo_twitter_blocus_españa"
        hilo.mkdir(parents=True, exist_ok=True)
        fig.savefig(hilo / "03_comentarios_por_dia.png", facecolor="white")
    print(destino(SALIDA), d0, d1, dias[pico], suma[pico])


if __name__ == "__main__":
    main()
