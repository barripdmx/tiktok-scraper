"""Gráficas 5, 6 y 7 de la presentación: combinaciones atípicas de emojis en los comentarios de @teamblocus."""

import csv
from collections import Counter
from datetime import datetime
from random import Random

import matplotlib.dates as mdates

from scripts.analisis_emojis_blocus import CUENTA_FOCO, TOP_COMUNES, cargar, resumen
from scripts.estilo_presentacion_blocus import AZUL, CLARO, GRIS, NARANJA, ROJO, ROOT, guardar, limpiar, miles, nueva, pct

USUARIOS = ROOT / "data/blocus/datos/usuarios_fecha_creacion/usuarios_por_fecha_creacion.csv"
DEFINICION = (f"Definición: comentario formado solo por 2 a 4 emojis distintos, ninguno entre los {TOP_COMUNES} más "
              "frecuentes de las demás cuentas (sin texto, sin pegatinas «[…]»).")


def datos():
    filas, _ = cargar()
    foco, resto = resumen(filas)
    atipicos = sorted((r for r in foco if r["atipico"]), key=lambda r: r["creado_utc"])
    return filas, foco, resto, atipicos


def grafica_5(foco, resto, atipicos):
    a_f, a_r = len(atipicos), sum(r["atipico"] for r in resto)
    s_f, s_r = sum(r["solo_2a4"] for r in foco), sum(r["solo_2a4"] for r in resto)
    fig, ax = nueva(f"la anomalía de los emojis: {pct(100 * a_f / len(foco))} de los comentarios de @{CUENTA_FOCO}",
                    "comentarios que son solo una combinación atípica de 2 a 4 emojis, por cuenta publicadora",
                    DEFINICION + f" Una sola publicación concentra los {len(foco)} comentarios de @{CUENTA_FOCO}.")
    grupos = [("combinación atípica de emojis", a_f, a_r), ("solo 2-4 emojis, cualquiera", s_f, s_r)]
    ancho = 0.36
    for i, (nombre, f, r) in enumerate(grupos):
        for j, (num, den, color, etiqueta) in enumerate(
                [(f, len(foco), ROJO, f"@{CUENTA_FOCO}"), (r, len(resto), CLARO, "resto de cuentas")]):
            x = i + (j - 0.5) * (ancho + 0.04)
            ax.bar(x, 100 * num / den, ancho, color=color, label=etiqueta if i == 0 else None)
            ax.text(x, 100 * num / den + 0.8, f"{pct(100 * num / den, 2)}\n{miles(num)} / {miles(den)}", ha="center",
                    fontsize=10, fontweight="bold" if j == 0 else None, color="#222222")
    ax.set_xticks(range(len(grupos)), [g[0] for g in grupos], fontsize=11)
    ax.set_ylabel("% de los comentarios capturados", fontsize=9)
    ax.set_ylim(0, 48)
    ax.legend(loc="upper right", frameon=False, fontsize=10)
    ax.text(0.5, 43, "Los comentarios solo de emojis son habituales en todas las cuentas;\n"
            "lo atípico es la combinación de emojis poco usados.", ha="center", fontsize=9.5, color=GRIS)
    limpiar(ax)
    guardar(fig, "05_anomalia_emojis.png")


def grafica_6(atipicos):
    por_n = {2: ROJO, 3: NARANJA, 4: AZUL}
    t = [datetime.fromisoformat(r["creado_utc"]) for r in atipicos]
    rng = Random(4)
    fig, (a1, a2) = nueva("cronología de los comentarios con combinaciones atípicas de emojis",
                          f"{len(atipicos)} comentarios en @{CUENTA_FOCO}, del {t[0]:%d/%m} al {t[-1]:%d/%m/%Y} (UTC); "
                          "color según el número de emojis", DEFINICION, filas=2, sharex=True,
                          gridspec_kw={"height_ratios": [1, 2], "hspace": 0.12})
    dias = Counter(x.date() for x in t)
    a1.bar(list(dias), list(dias.values()), color=ROJO, width=0.8)
    a1.set_ylabel("por día", fontsize=9)
    for n, color in por_n.items():
        xs = [x for x, r in zip(t, atipicos) if r["n_emojis"] == n]
        a2.scatter(xs, [n + rng.uniform(-0.28, 0.28) for _ in xs], s=22, color=color, alpha=0.8, label=f"{n} emojis")
    a2.set_yticks([2, 3, 4], ["2 emojis", "3 emojis", "4 emojis"])
    a2.set_ylim(1.4, 4.6)
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    a2.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    limpiar(a1)
    limpiar(a2, "both")
    huecos = sorted(b - a for a, b in zip(t, t[1:]))
    a2.text(0.01, 0.03, f"intervalo mediano entre comentarios: {huecos[len(huecos) // 2].total_seconds() / 60:.0f} min · "
            f"{sum(h.total_seconds() < 60 for h in huecos)} pares a menos de 1 min · "
            "sin respuestas, sin fijados, 3 con algún «me gusta»", transform=a2.transAxes, fontsize=9, color=GRIS)
    guardar(fig, "06_cronologia_emojis.png")


def grafica_7(foco, resto, atipicos):
    apar = Counter(e for r in atipicos for e in r["emojis"])
    veces = Counter(min(v, 5) for v in apar.values())
    usuarios = {u["user_id"]: u for u in csv.DictReader(USUARIOS.open(encoding="utf-8-sig"))}

    def meses(filas):
        c = Counter(usuarios[r["autor_id"]]["fecha_orden_utc"][:7] for r in filas
                    if r["autor_id"] in usuarios and usuarios[r["autor_id"]]["fecha_orden_utc"])
        return c, sum(c.values())

    fig, (a1, a2) = nueva("diversidad de los emojis y antigüedad de quienes los escriben",
                          f"{miles(len(apar))} emojis distintos en {miles(sum(apar.values()))} apariciones; "
                          "fecha de creación estimada de las cuentas autoras",
                          DEFINICION + " Fecha de creación: UID >> 32, aproximación técnica, no prueba de creación.",
                          columnas=2, gridspec_kw={"wspace": 0.25})
    xs = [1, 2, 3, 4, 5]
    a1.bar(xs, [veces[x] for x in xs], color=ROJO)
    for x in xs:
        a1.text(x, veces[x] + 6, str(veces[x]), ha="center", fontsize=10)
    a1.set_xticks(xs, ["1 vez", "2 veces", "3 veces", "4 veces", "5 o más"])
    a1.set_title("cuántos emojis distintos aparecen 1, 2, 3… veces", loc="left", fontsize=11, fontweight="bold")
    a1.set_ylabel("emojis distintos", fontsize=9)
    limpiar(a1)
    a1.text(0.97, 0.9, "una búsqueda de textos duplicados\nno detectaría este patrón:\nningún comentario se repite",
            transform=a1.transAxes, ha="right", fontsize=9.5, color=GRIS)
    grupos = [("autoras de los comentarios atípicos", atipicos, ROJO),
              (f"otros comentaristas de @{CUENTA_FOCO}", [r for r in foco if not r["atipico"]], NARANJA),
              ("comentaristas de las demás cuentas", resto, CLARO)]
    claves = [f"2026-{m:02d}" for m in range(1, 11)]
    for i, (nombre, filas, color) in enumerate(grupos):
        c, n = meses(filas)
        a2.bar([k + (i - 1) * 0.28 for k in range(len(claves))], [100 * c[k] / n for k in claves], 0.27, color=color,
               label=f"{nombre} (n = {miles(n)})")
    a2.set_xticks(range(len(claves)), [m[5:] + "/26" for m in claves], fontsize=8)
    a2.set_title("mes de creación estimado de la cuenta (el resto, antes de 2026)", loc="left", fontsize=11, fontweight="bold")
    a2.set_ylabel("% de cada grupo", fontsize=9)
    a2.legend(frameon=False, fontsize=8.5, loc="upper left")
    limpiar(a2)
    guardar(fig, "07_diversidad_y_antiguedad.png")


if __name__ == "__main__":
    _, foco, resto, atipicos = datos()
    grafica_5(foco, resto, atipicos)
    grafica_6(atipicos)
    grafica_7(foco, resto, atipicos)
