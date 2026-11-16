"""Estado de las 54 cuentas Blocus el 28/10/2026 frente a la captura (25-27/10): nombre, @ y desaparición.

11_estado_cuentas.png: las 54 cuentas, una fila cada una. 12_cuentas_desaparecidas.png: las 7 que ya no cargan y la
evidencia sobre la causa. Fuente de hoy: estado_actual_20261028.json (consulta del perfil público por cuenta).
"""

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

from config.blocus import FALSOS_POSITIVOS_BASE

ROOT = Path(__file__).resolve().parents[1]
GRAFO = ROOT / "data/blocus/datos/grafo_blocus_20261025"
HILO = ROOT / "data/blocus/graficas/Hilo_twitter_blocus_españa"
LOGO = ROOT / "assets/tiktok_logo.jpg"
FUENTES = ["DejaVu Sans", "Segoe UI Symbol", "Cambria Math", "Segoe UI Emoji"]  # apodos con letras matemáticas y emojis
GRIS, NARANJA, ROJO = "#555555", "#CA6F1E", "#C0392B"
# Evidencia por cuenta desaparecida (consulta del 28/10 a sus publicaciones capturadas; ver docs/BLOCUS_CAMBIOS_CUENTAS.md)
CAUSAS = {
    "blocusespanol": ("3 fotos visibles el 25/10", "las 3: 10204, author_status, status_audit_not_pass", "probable: moderación de TikTok"),
    "blocusmanifestacionmdrz": ("7 de 9 fotos ya caídas el 26/10", "10204, status_audit_not_pass (una, status_self_see)", "probable: moderación de TikTok"),
    "blocusasturias": ("5 de 5 fotos ya caídas el 26/10", "10204, content_classification, status_audit_not_pass", "probable: moderación de TikTok"),
    "manifestacion_barcelona": ("3 de 3 fotos ya caídas el 26/10", "10204, author_status, status_audit_not_pass", "probable: moderación de TikTok"),
    "blocus.madrid": ("sin publicaciones capturadas", "nada con qué contrastar", "no se puede saber"),
    "blocussalgeciras": ("perfil ya caído el 25/10", "sin publicaciones capturadas", "no se puede saber"),
    "blocus.mallorca": ("perfil ya caído el 26/10", "sin publicaciones capturadas", "no se puede saber"),
}


def estados():
    with (GRAFO / "cuentas.csv").open(encoding="utf-8-sig", newline="") as f:
        guardado = {r["username"]: r for r in csv.DictReader(f) if r["objetivo"]}
    hoy = json.loads((GRAFO / "estado_actual_20261028.json").read_text(encoding="utf-8"))
    filas = []
    for u in sorted(guardado):
        v = hoy[u]
        if v.get("st"):
            filas.append((u, "desaparecida", f"código {v['st']}", ROJO))
        elif u == "blocus.es_":
            filas.append((u, "sin comparar", "nombre guardado de relleno", GRIS))
        elif v["nick"] != guardado[u]["nickname"]:
            filas.append((u, "nombre cambiado", f"{guardado[u]['nickname']} → {v['nick']}", NARANJA))
        else:
            filas.append((u, "sin cambios", "", GRIS))
    return filas


def lienzo(titulo, subtitulo):
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor="white")
    fig.text(0.04, 0.94, titulo, fontsize=17, fontweight="bold", color="#222222")
    fig.text(0.04, 0.905, subtitulo, fontsize=10.5, color=GRIS)
    fig.text(0.985, 0.02, "@barripdmx", ha="right", fontsize=8, color="#999999")
    if LOGO.exists():
        fig.add_artist(AnnotationBbox(OffsetImage(plt.imread(LOGO), zoom=0.05, alpha=0.2), (0.945, 0.93),
                                      xycoords="figure fraction", frameon=False))
    return fig


def guardar(fig, nombre):
    HILO.mkdir(parents=True, exist_ok=True)
    fig.savefig(HILO / nombre, facecolor="white")
    plt.close(fig)
    print(HILO / nombre)


def grafica_11(filas):
    n = {k: sum(f[1] == k for f in filas) for k in ("desaparecida", "nombre cambiado", "sin cambios")}
    fig = lienzo(f"qué ha pasado con las {len(filas)} cuentas analizadas entre la captura y el 28/10/2026",
                 f"{n['sin cambios']} sin cambios · {n['nombre cambiado']} con el nombre público cambiado · "
                 f"{n['desaparecida']} desaparecidas · 0 con el @ cambiado")
    mitad = (len(filas) + 1) // 2
    for p, trozo in enumerate((filas[:mitad], filas[mitad:])):
        ax = fig.add_axes([0.04 + 0.49 * p, 0.12, 0.46, 0.7])
        ax.axis("off")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, mitad + 1)
        for x, t in ((0.0, "cuenta"), (0.4, "estado")):
            ax.text(x, mitad + 0.45, t, fontsize=10, fontweight="bold", color=GRIS)
        for i, (u, est, det, col) in enumerate(trozo):
            y = mitad - i - 0.3
            fp = u in FALSOS_POSITIVOS_BASE
            ax.text(0.0, y, "@" + u + (" (falso positivo)" if fp else ""), fontsize=8.5, va="center",
                    color="#999999" if fp else "#222222")
            ax.text(0.4, y, est, fontsize=8.5, va="center", color=col, fontweight="normal" if est == "sin cambios" else "bold")
            if det:
                ax.text(0.6, y, det, fontsize=8, va="center", color=col, fontfamily=FUENTES)
            ax.plot([0, 1], [y - 0.5] * 2, color="#F0F0F0", lw=0.6)
    fig.text(0.04, 0.06, "Se compara el identificador numérico de cada cuenta con su @ y su nombre público actuales: ningún @ cambió en las 47 cuentas que cargan. "
             "Las 7 desaparecidas se explican en la imagen siguiente.", fontsize=8.5, color=GRIS)
    fig.text(0.04, 0.035, "Nombre público = apodo editable. @blo.cus2026 e @intrvbll4057 llevan «Blocus» en letras matemáticas en negrita, igual que al capturarlas (sin cambio). "
             "Solo se detectan cambios entre la captura y el 28/10.", fontsize=8.5, color=GRIS)
    guardar(fig, "15_estado_cuentas.png")


def grafica_12():
    fig = lienzo("las 7 cuentas que han desaparecido: qué sabemos de la causa",
                 "cuentas cuyo perfil ya no carga el 28/10/2026 (10221: no existe ese @; 10202: sin significado documentado)")
    ax = fig.add_axes([0.04, 0.4, 0.92, 0.45])
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, len(CAUSAS) + 1)
    for x, t in ((0.0, "cuenta"), (0.2, "antes de desaparecer"), (0.42, "qué devuelven sus publicaciones hoy"), (0.82, "causa")):
        ax.text(x, len(CAUSAS) + 0.45, t, fontsize=10, fontweight="bold", color=GRIS)
    for i, (u, (antes, hoy, causa)) in enumerate(CAUSAS.items()):
        y = len(CAUSAS) - i - 0.3
        ax.text(0.0, y, "@" + u, fontsize=9.5, va="center", color="#222222")
        ax.text(0.2, y, antes, fontsize=8.5, va="center", color="#333333")
        ax.text(0.42, y, hoy, fontsize=8.5, va="center", color="#333333")
        ax.text(0.82, y, causa, fontsize=9.5, va="center", color=ROJO if causa.startswith("prob") else GRIS, fontweight="bold")
        ax.plot([0, 1], [y - 0.5] * 2, color="#F0F0F0", lw=0.6)
    nl = chr(10)
    fig.text(0.04, 0.33, "Cuatro cuentas: causa más probable, retirada por TikTok. Sus publicaciones devuelven estado de moderación (no pasó la revisión)" + nl
             + "y las de @blocusasturias y @manifestacion_barcelona ya estaban caídas el 26/10, antes que el perfil." + nl
             + "Si solo hubieran cambiado de @, esas publicaciones seguirían visibles con el @ nuevo (las de cuentas vivas sí cargan).",
             fontsize=9.5, color="#222222", va="top", linespacing=1.5)
    fig.text(0.04, 0.2, "Tres cuentas: no se puede saber, no hay publicaciones con las que contrastar." + nl
             + "¿Pueden haber cambiado de @? TikTok localiza una publicación por su ID aunque el @ de la dirección sea otro y devuelve el @ actual del autor (comprobado)." + nl
             + "En las 4 con publicaciones no apareció ningún @ nuevo: no parece un simple cambio de @. En las otras 3 no hay ID que consultar.",
             fontsize=9.5, color="#222222", va="top", linespacing=1.5)
    fig.text(0.04, 0.115, "Límites: el código 10221 también lo devuelve TikTok para un @ que nunca existió (comprobado con nombres inventados), así que por sí solo" + nl
             + "no distingue borrado, baneo o cambio de @. Los mensajes de estado (status_audit_not_pass, content_classification, author_status) son textos" + nl
             + "internos de TikTok sin documentación: su sentido es una interpretación por el nombre. TikTok no dice quién actuó ni por qué regla.",
             fontsize=8.5, color=GRIS, va="top", linespacing=1.5)
    guardar(fig, "16_cuentas_desaparecidas.png")


if __name__ == "__main__":
    grafica_11(estados())
    grafica_12()
