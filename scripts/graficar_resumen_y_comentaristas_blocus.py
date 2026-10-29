"""Resumen general de Blocus (todas las cuentas analizadas) y comentaristas más activos (según el ámbito activo)."""

import csv
import json
from collections import Counter
from datetime import datetime, timezone

from config.blocus import AMBITO, FALSOS_POSITIVOS, COLOR_TEMA, tema_de_cuentas
from scripts.estilo_presentacion_blocus import AZUL, GRIS, NARANJA, ROJO, ROOT, guardar, limpiar, miles, nueva

DATOS = ROOT / "data/blocus/datos"


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fecha_id(pid):
    return datetime.fromtimestamp(int(pid) >> 32, timezone.utc)


def resumen_conjunto():
    cuentas = [r["username"] for r in leer(DATOS / "grafo_blocus_20261025/cuentas.csv") if r["objetivo"] and r["username"] not in FALSOS_POSITIVOS]
    tema = tema_de_cuentas()
    pubs = [r for r in leer(DATOS / "comentarios_blocus_20261026/publicaciones.csv") if r["cuenta"] in cuentas]
    coms = [r for r in leer(DATOS / "comentarios_blocus_20261026/comentarios.csv") if r["cuenta_publicadora"] in cuentas]
    graf = json.loads((DATOS / "grafo_blocus_20261025/resumen.json").read_text(encoding="utf-8"))
    pais = Counter(p["meta_pais_creacion"] for p in pubs if p["meta_pais_creacion"])
    f = [fecha_id(p["id"]) for p in pubs]
    por_tema = {t: [c for c in cuentas if tema.get(c) == t] for t in ("francés", "español")}
    n_pub = {t: sum(p["cuenta"] in cs for p in pubs) for t, cs in por_tema.items()}
    n_com = {t: sum(c["cuenta_publicadora"] in cs for c in coms) for t, cs in por_tema.items()}

    fig, ax = nueva("Blocus en conjunto: las cuentas analizadas y lo que se ha capturado",
                    f"{len(cuentas)} cuentas con «blocus» en el nombre, capturadas el 25-27/10/2026; "
                    f"publicaciones del {min(f):%d/%m/%Y} al {max(f):%d/%m/%Y}",
                    "Los comentarios solo se capturaron hasta el 26/10. Las relaciones son seguidores y seguidos observados; "
                    "no todas las cuentas tenían la lista completa.")
    ax.axis("off")
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 3)
    fichas = [
        (miles(len(cuentas)), "cuentas analizadas"), (miles(len(pubs)), "publicaciones observadas"),
        (miles(len(coms)), "comentarios y respuestas"), (miles(len({c["autor_id"] for c in coms})), "comentaristas distintos"),
        (miles(graf["nodos"]), "cuentas en el grafo de relaciones"), (miles(graf["relaciones_dirigidas"]), "relaciones seguidor-seguido"),
        (f"{pais.most_common(1)[0][0]}  {100 * pais.most_common(1)[0][1] // sum(pais.values())} %", "país de creación más declarado"),
        (miles(len(por_tema["español"])), f"de tema español ({len(por_tema['francés'])} francés, {len(cuentas) - len(por_tema['español']) - len(por_tema['francés'])} sin tema)"),
    ]
    for i, (cifra, texto) in enumerate(fichas):
        x, y = i % 4, 2 - i // 4
        ax.add_patch(plt_rect(x + 0.05, y + 0.12, 0.9, 0.76))
        ax.text(x + 0.5, y + 0.56, cifra, ha="center", va="center", fontsize=26, fontweight="bold", color=AZUL)
        ax.text(x + 0.5, y + 0.27, texto, ha="center", va="center", fontsize=10.5, color=GRIS)
    # reparto por tema: franjas bajo las fichas
    ax2 = ax.figure.add_axes([0.07, 0.15, 0.9, 0.14])
    for fila, (etq, datos) in enumerate((("publicaciones", n_pub), ("comentarios", n_com))):
        total = sum(datos.values())
        izq = 0
        for t, v in datos.items():
            ax2.barh(fila, v / total, left=izq, color=COLOR_TEMA[t], height=0.6)
            etq_seg = f"{t} {miles(v)} ({100 * v / total:.0f} %)"
            if v / total < 0.12:  # segmento estrecho: la etiqueta va encima, en su color, alineada a la derecha
                ax2.text(izq + v / total, fila + 0.36, etq_seg, ha="right", va="bottom", fontsize=9, color=COLOR_TEMA[t], fontweight="bold")
            else:
                ax2.text(izq + v / total / 2, fila, etq_seg, ha="center", va="center", fontsize=9, color="white", fontweight="bold")
            izq += v / total
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["publicaciones", "comentarios"], fontsize=9)
    ax2.set_xlim(0, 1)
    ax2.axis("off") if False else ax2.set_xticks([])
    for lado in ("top", "right", "bottom", "left"):
        ax2.spines[lado].set_visible(False)
    ax2.set_title("Reparto por tema de la cuenta (español / francés)", loc="left", fontsize=10, fontweight="bold")
    guardar(fig, "00_resumen_conjunto.png")


def plt_rect(x, y, w, h):
    from matplotlib.patches import FancyBboxPatch
    return FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.04", fc="#F4F7FA", ec="#D5DEE6")


def comentaristas():
    tema = tema_de_cuentas()
    coms = [r for r in leer(DATOS / "comentarios_blocus_20261026/comentarios.csv") if r["cuenta_publicadora"] not in FALSOS_POSITIVOS]
    por_autor = Counter((c["autor_handle"] or c["autor_id"]) for c in coms)
    cuentas_por_autor = {}
    for c in coms:
        cuentas_por_autor.setdefault(c["autor_handle"] or c["autor_id"], set()).add(c["cuenta_publicadora"])
    top = por_autor.most_common(12)[::-1]
    propia = [a for a, _ in top if a in {c["cuenta_publicadora"] for c in coms}]
    fig, ax = nueva(f"Los {len(top)} comentaristas más activos de {miles(len(coms))} comentarios",
                    f"{miles(len(por_autor))} comentaristas distintos; {miles(sum(1 for a in por_autor if por_autor[a] > 1))} comentan más de una vez, "
                    f"{miles(sum(1 for a in cuentas_por_autor.values() if len(a) > 1))} lo hacen en más de una cuenta",
                    "Comentar mucho no implica coordinación: puede ser una conversación entre pocas personas. Se cuentan comentarios y respuestas."
                    + (f" @{propia[-1]} es una de las cuentas analizadas: son sus respuestas a quienes comentan." if propia else ""))
    ax.barh([f"@{a}" for a, _ in top], [n for _, n in top], color=AZUL if not AMBITO else COLOR_TEMA["español"], height=0.7)
    for y, (a, n) in enumerate(top):
        ax.text(n + max(v for _, v in top) * 0.012, y, f"{n}  ({len(cuentas_por_autor[a])} {'cuenta' if len(cuentas_por_autor[a]) == 1 else 'cuentas'})",
                va="center", fontsize=9, color="#333333")
    ax.set_xlim(0, max(v for _, v in top) * 1.18)
    limpiar(ax, "x")
    fig.subplots_adjust(left=0.18)
    guardar(fig, "07_comentaristas_mas_activos.png")


def nexos_francia():
    """Cuadro de indicios de nexo entre las cuentas de tema español y la red francesa, con el veredicto de cada uno."""
    d = json.loads((ROOT / "data/blocus/estudios/informe_osint_nexos_francia/nexos_francia.json").read_text(encoding="utf-8"))
    pais = {g: dict(v) for g, v in d["pais_creacion"].items()}
    ci, au = d["comentarios_idioma"], d["audiencia_comun_seguidores"]
    h = {x[0]: x for x in d["hashtags_comunes"]}
    com = d["comentaristas"]
    fil = [
        ("País de creación de las publicaciones", f"ES en {pais['español'].get('ES', 0)} de {d['publicaciones']['español']}; ninguna en FR",
         f"FR en {pais['francés'].get('FR', 0)} de {d['publicaciones']['francés']}", "sin nexo"),
        ("Idioma de los comentarios", f"{ci['español']['mas_espanol']} en español, {ci['español']['mas_frances']} en francés",
         f"{ci['francés']['mas_frances']:,} en francés, {ci['francés']['mas_espanol']} en español".replace(",", "."), "sin nexo"),
        ("Comentaristas en ambos grupos", f"{com['en_ambos']} de {com['en_cuentas_espanolas']} comentaristas de cuentas españolas", "", "sin nexo"),
        ("Audiencia común (seguidores compartidos)", f"español-español {au['español-español']}; español-francés {au['español-francés']}",
         f"francés-francés {au['francés-francés']:,}".replace(",", "."), "débil"),
        ("Hashtags comunes", f"#blocus ({h['blocus'][1]}), #manifestation ({h['manifestation'][1]}, en francés), #fyp ({h['fyp'][1]})",
         f"#blocus ({h['blocus'][2]}), #manifestation ({h['manifestation'][2]}), #fyp ({h['fyp'][2]})", "indicio de imitación"),
        ("Cronología", f"primera publicación: {dma(d['primera_publicacion']['español'][0][0])}", f"primera: {dma(d['primera_publicacion']['francés'][0][0])}; casi todas desde el 28/09", "compatible con difusión"),
        ("Cuentas latentes", "@blocusespanol (creada 16/11/2024) y @blocusmanifestacionmdrz (27/12/2024) sin publicaciones observadas hasta oct 2026", "", "a vigilar"),
    ]
    col = {"sin nexo": "#1E8449", "débil": "#CA6F1E", "indicio de imitación": "#CA6F1E", "compatible con difusión": "#CA6F1E", "a vigilar": "#A93226"}
    fig, ax = nueva("Nexos con Francia: qué indicios hay entre las cuentas de tema español y la red francesa",
                    f"{len(d['creacion_cuentas']['español'])} cuentas de tema español frente a {len(d['creacion_cuentas']['francés'])} de tema francés; cada fila compara una señal observable",
                    "Un indicio no prueba coordinación ni origen. Las publicaciones no disponibles (16 de 28 sin país) limitan la lectura; la audiencia compartida es una muestra.")
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, len(fil) + 1)
    for x, t in ((0.0, "señal"), (0.25, "cuentas de tema español"), (0.58, "cuentas de tema francés"), (0.84, "lectura")):
        ax.text(x, len(fil) + 0.4, t, fontsize=10, fontweight="bold", color=GRIS)
    for i, (n, a, b, v) in enumerate(fil):
        y = len(fil) - i - 0.4
        ax.text(0.0, y, n, fontsize=9.5, va="center", color="#222222", fontweight="bold")
        ax.text(0.25, y, textwrap_(a, 38), fontsize=8.5, va="center", color="#333333")
        ax.text(0.58, y, textwrap_(b, 30), fontsize=8.5, va="center", color="#333333")
        ax.text(0.84, y, v, fontsize=9.5, va="center", color=col[v], fontweight="bold")
        ax.plot([0, 1], [y - 0.5] * 2, color="#F0F0F0", lw=0.6)
    guardar(fig, "08_nexos_francia.png")


def dma(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def textwrap_(t, ancho):
    import textwrap
    return "\n".join(textwrap.wrap(t, ancho)) if t else "—"


if __name__ == "__main__":
    if not AMBITO:
        resumen_conjunto()
        nexos_francia()
    comentaristas()
