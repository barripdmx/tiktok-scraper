"""Fecha de creación frente a seguidores de las cuentas Blocus publicadoras (me gusta = tamaño)."""

import csv
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from config.blocus import AMBITO, COLOR_TEMA, FALSOS_POSITIVOS, NOTA_FALSOS_POSITIVOS, destino, rotular_ambito, tema_de_cuentas

ROOT = Path(__file__).resolve().parents[1]
PUBLICACIONES = ROOT / "data/blocus/datos/comentarios_blocus_20261026/publicaciones.csv"
USUARIOS = ROOT / "data/blocus/datos/usuarios_fecha_creacion/usuarios_por_fecha_creacion.csv"
SALIDA = ROOT / "data/blocus/datos/comentarios_blocus_20261026/cuentas_creacion_seguidores.png"
LOGO = ROOT / "assets/tiktok_logo.jpg"


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def numero(valor):
    return int(valor) if valor.isdigit() else None


def main():
    fechas = {u["user_id"]: (u["fecha_orden_utc"], u["tipo_fecha"]) for u in leer(USUARIOS)}
    cuentas = {}
    for fila in leer(PUBLICACIONES):
        if fila["cuenta"] in FALSOS_POSITIVOS:
            continue
        if fila["autor_id"] and fila["cuenta"] not in cuentas and numero(fila["autor_seguidores"]) is not None:
            fecha, tipo = fechas.get(fila["autor_id"], ("", ""))
            if fecha:
                cuentas[fila["cuenta"]] = (datetime.fromisoformat(fecha), numero(fila["autor_seguidores"]),
                                           numero(fila["autor_me_gusta"]) or 0, tipo)
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100, facecolor="white")
    fig.subplots_adjust(left=0.07, right=0.97, top=0.82, bottom=0.12)
    tema = tema_de_cuentas()
    for nombre, (f, seg, meg, tipo) in cuentas.items():
        conf = tipo == "Confirmada por perfil"
        ax.scatter(f, max(seg, 1), s=25 + 2.2 * meg ** 0.5, color=(COLOR_TEMA[tema.get(nombre, "sin clasificar")] if AMBITO == "espana" else "#1F618D") if conf else "#9DB7CF", alpha=0.8,
                   edgecolor="white", zorder=3)
        if seg >= 700 or meg >= 20000:
            ax.annotate(f"@{nombre}", (f, max(seg, 1)), xytext=(6, 4), textcoords="offset points", fontsize=8)
    ax.set_yscale("log")
    ax.set_ylabel("seguidores declarados (escala logarítmica)", fontsize=9)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(color="#EBEBEB")
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    recientes = sum(1 for v in cuentas.values() if v[0] >= datetime(2026, 9, 1, tzinfo=v[0].tzinfo))
    fig.text(0.04, 0.94, f"cuentas blocus publicadoras: creación y tamaño ({len(cuentas)} cuentas)",
             fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.905, f"{recientes} se crearon desde septiembre de 2026; tamaño del punto = me gusta totales "
             "de la cuenta; " + ("rojo = tema español, verde = común; tono claro = fecha estimada" if AMBITO == "espana" else "azul oscuro = fecha confirmada por el perfil, claro = estimada"), fontsize=10.5, color="#555555")
    fig.text(0.04, 0.03, "Seguidores y me gusta declarados por TikTok en los metadatos de la publicación (26-27/10/2026). "
             "Fecha de creación: perfil cuando se consultó; si no, UID >> 32 (aproximación).",
             fontsize=8.5, color="#555555")
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        from matplotlib.offsetbox import AnnotationBbox, OffsetImage
        fig.add_artist(AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.93),
                                      xycoords="figure fraction", frameon=False))
    fig.text(0.04, 0.005, NOTA_FALSOS_POSITIVOS, fontsize=8.5, color="#A93226")
    rotular_ambito(fig)
    fig.savefig(destino(SALIDA), facecolor="white")
    print(destino(SALIDA), len(cuentas), recientes)


if __name__ == "__main__":
    main()
