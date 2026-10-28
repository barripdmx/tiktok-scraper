"""Gráficas 1 y 3 de la presentación: cronología de publicaciones y comentarios, y top 10 de cuentas."""

import csv
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

import matplotlib.dates as mdates

from config.blocus import AMBITO, COLOR_TEMA, FALSOS_POSITIVOS, tema_de_cuentas
from scripts.estilo_presentacion_blocus import AZUL, CLARO, GRIS, NARANJA, ROJO, ROOT, guardar, limpiar, miles, nueva

SALIDA = ROOT / "outputs/comentarios_blocus_20261026"
DESDE = date(2026, 9, 25)
OCTUBRE = date(2026, 10, 1)
CONVOCATORIAS = (17, 24, 31)  # días de octubre más citados como convocatoria en las descripciones
MENCION = re.compile(r"\b(\d{1,2})\s?(?:er)?\s?(?:de\s)?octobre\b|\b(\d{1,2})\s?(?:de\s)?octubre\b|\b(\d{1,2})/10\b", re.I)


def leer(nombre):
    with (SALIDA / nombre).open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("cuenta", r.get("cuenta_publicadora")) not in FALSOS_POSITIVOS]


def fecha_id(pid):
    return datetime.fromtimestamp(int(pid) >> 32, timezone.utc).date()


def menciones(textos):
    c = Counter()
    for t in textos:
        for m in MENCION.finditer(t):
            c[int(next(g for g in m.groups() if g))] += 1
    return c


def grafica_1(pubs, coms):
    p_dia = Counter(fecha_id(r["id"]) for r in pubs)
    c_dia = Counter(date.fromisoformat(r["creado_utc"][:10]) for r in coms)
    m_desc = menciones(r["meta_descripcion"] + " " + r["meta_titulo_foto"] for r in pubs)
    m_com = menciones(r["texto"] for r in coms)
    dias = [DESDE + timedelta(days=i) for i in range((date(2026, 10, 28) - DESDE).days + 1)]
    fig, (a1, a2) = nueva("cuándo crece la actividad: publicaciones y comentarios por día",
                          f"{miles(sum(p_dia[d] for d in dias))} publicaciones (fecha del ID) y "
                          f"{miles(sum(c_dia[d] for d in dias))} comentarios (fecha del comentario), UTC; "
                          "líneas discontinuas: fechas de convocatoria citadas en el corpus",
                          "Los comentarios solo se capturaron hasta el 26/10; las publicaciones ya no disponibles figuran por la fecha "
                          "de su ID. Citar una fecha no prueba que la convocatoria se celebrara.",
                          filas=2, sharex=True, gridspec_kw={"hspace": 0.12})
    a1.bar(dias, [p_dia[d] for d in dias], color=AZUL, width=0.85)
    a1.set_ylabel("publicaciones por día", fontsize=9)
    a2.bar(dias, [c_dia[d] for d in dias], color=NARANJA, width=0.85)
    a2.set_ylabel("comentarios por día", fontsize=9)
    for ax in (a1, a2):
        limpiar(ax)
        for dia in CONVOCATORIAS:
            ax.axvline(date(2026, 10, dia), color=ROJO, ls="--", lw=1.2)
    techo = max(p_dia[d] for d in dias) * 1.5
    a1.set_ylim(0, techo)
    for dia in CONVOCATORIAS:
        a1.text(date(2026, 10, dia) + timedelta(days=0.25), techo * 0.98,
                f"{dia}/10\ncitada en {m_desc[dia]} " + ("descripción" if m_desc[dia] == 1 else "descripciones")
                + f"\ny {m_com[dia]} " + ("comentario" if m_com[dia] == 1 else "comentarios"), fontsize=8.5, color=ROJO,
                va="top", ha="left")
    a2.set_xlim(DESDE - timedelta(days=1), date(2026, 11, 5))
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    a2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    guardar(fig, "01_cronologia_publicaciones_comentarios.png")


def grafica_3(pubs):
    por_cuenta = defaultdict(Counter)
    for r in pubs:
        por_cuenta[r["cuenta"]]["octubre" if fecha_id(r["id"]) >= OCTUBRE else "antes"] += 1
    top = sorted(por_cuenta, key=lambda c: -sum(por_cuenta[c].values()))[:10][::-1]
    fig, ax = nueva(f"las {len(top)} cuentas con más publicaciones, separadas por fecha",
                    f"publicaciones desde el 1 de octubre de 2026 frente a fechas anteriores (de {miles(len(pubs))} publicaciones)"
                    + (f"; ninguna de las {len(top)} publicó antes de octubre" if not any(por_cuenta[c]["antes"] for c in top) else ""),
                    "Fecha de cada publicación: ID >> 32. Una cuenta con mucho contenido anterior a octubre no lidera la "
                    "movilización actual.")
    ant = [por_cuenta[c]["antes"] for c in top]
    oct_ = [por_cuenta[c]["octubre"] for c in top]
    ax.barh(top, ant, color=CLARO, label="antes de octubre de 2026")
    ax.barh(top, oct_, left=ant, color=AZUL, label="octubre de 2026 en adelante")
    for y, (a, o) in enumerate(zip(ant, oct_)):
        ax.text(a + o + 0.4, y, f"{a + o}  ({o} en octubre)", va="center", fontsize=9, color="#333333")
    ax.legend(loc="lower right", frameon=False, fontsize=10)
    ax.set_xlim(0, max(a + o for a, o in zip(ant, oct_)) * 1.25)
    fig.subplots_adjust(left=0.15)
    limpiar(ax, "x")
    if AMBITO == "espana":  # nombre de cada cuenta en el color de su tema
        tema = tema_de_cuentas()
        for lab in ax.get_yticklabels():
            lab.set_color(COLOR_TEMA[tema.get(lab.get_text(), "sin clasificar")])
    guardar(fig, "03_top10_cuentas.png")


if __name__ == "__main__":
    pubs = [r for r in leer("publicaciones.csv")]
    coms = leer("comentarios.csv")
    grafica_1(pubs, coms)
    grafica_3(pubs)
