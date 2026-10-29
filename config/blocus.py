"""Cuentas del lote Blocus descartadas por falso positivo y ámbito de análisis de las gráficas.

Falsos positivos: entraron al lote solo porque su nombre contiene «blocus» (búsqueda de usuarios), pero su contenido
no tiene relación con las convocatorias: @blocus328 parece una comunidad haitiana (criollo haitiano,
publicaciones de oct 2025 a may 2026), @luccca93 publica memes de CapCut en un contexto catalán, @blocus75000
publica vídeos sin relación con el movimiento (fitness, baño, menciones a medios de EE. UU.) y la bio
de @blocus.es_ dice que usa el nombre «blocus» por marketing.
Las gráficas las excluyen y lo indican en una nota.

Ámbito: con la variable de entorno BLOCUS_AMBITO=espana las gráficas se limitan a las cuentas de tema español (rojo) y
común (verde), según data/blocus/datos/grafo_blocus_20261025/tema_cuentas.csv (scripts/tema_cuentas_blocus.py), y se guardan
en data/blocus/graficas/ambito_espana_20261028/.
"""

import csv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FALSOS_POSITIVOS_BASE = ("blocus328", "luccca93", "blocus75000", "blocus.es_")
# Sin contenido o sin datos para juzgarlas (perfiles sin vídeos, o no disponibles); se mantienen.
DUDOSAS = ("blocusscpmofrancia", "blocus91", "blocussgp", "blocus.cs", "blocusasturias", "manifestacion_barcelona")
AMBITO = os.environ.get("BLOCUS_AMBITO", "")
TEMA_CSV = ROOT / "data/blocus/datos/grafo_blocus_20261025/tema_cuentas.csv"
OBJETIVOS_CSV = ROOT / "data/blocus/datos/grafo_blocus_20261025/cuentas.csv"
COLOR_TEMA = {"francés": "#1F618D", "español": "#C0392B", "común": "#1E8449", "sin clasificar": "#7F8C8D"}


def _leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def tema_de_cuentas():
    """Diccionario cuenta -> tema (vacío si aún no se ha generado tema_cuentas.csv)."""
    return {r["cuenta"]: r["tema"] for r in _leer(TEMA_CSV)} if TEMA_CSV.exists() else {}


def _fuera_de_ambito():
    if AMBITO != "espana":
        return ()
    tema = tema_de_cuentas()
    todas = {r["username"] for r in _leer(OBJETIVOS_CSV) if r["objetivo"]} | set(tema)
    dentro = {c for c, t in tema.items() if t in ("español", "común")}
    return tuple(sorted(todas - dentro - set(FALSOS_POSITIVOS_BASE)))


FUERA_DE_AMBITO = _fuera_de_ambito()
# Lo que las gráficas excluyen de los datos (en el ámbito España, también todo lo que no es español ni común).
FALSOS_POSITIVOS = FALSOS_POSITIVOS_BASE + FUERA_DE_AMBITO
if AMBITO == "espana":
    _comunes = [c for c, t in tema_de_cuentas().items() if t == "común"]
    NOTA_FALSOS_POSITIVOS = ("Ámbito España: solo cuentas de tema español (rojo)"
                             + (f" y común (verde, {', '.join('@' + c for c in _comunes)})" if _comunes else "")
                             + f"; se excluyen {len(FUERA_DE_AMBITO)} cuentas de tema francés o sin clasificar (entre ellas @ftbl687, "
                             "cuyo contenido trata de Francia) y los falsos positivos "
                             + ", ".join("@" + c for c in FALSOS_POSITIVOS_BASE) + ".")
else:
    NOTA_FALSOS_POSITIVOS = ("Excluidas por falso positivo (solo comparten el nombre «blocus»): "
                             + ", ".join("@" + c for c in FALSOS_POSITIVOS_BASE) + ". Dudosas, se mantienen: "
                             + ", ".join("@" + c for c in DUDOSAS) + ".")


def primera_publicacion_espana():
    """(fecha UTC, cuenta) de la publicación más antigua de las cuentas de tema español; la fecha sale del ID (id >> 32)."""
    from datetime import datetime, timezone
    tema = tema_de_cuentas()
    pubs = [r for r in _leer(ROOT / "data/blocus/datos/comentarios_blocus_20261026/publicaciones.csv") if tema.get(r["cuenta"]) == "español"]
    primera = min(pubs, key=lambda r: int(r["id"]))
    return datetime.fromtimestamp(int(primera["id"]) >> 32, timezone.utc), primera["cuenta"]


def destino(ruta):
    """Ruta de salida: en el ámbito España, el mismo nombre de archivo dentro de data/blocus/graficas/ambito_espana_20261028/."""
    if AMBITO != "espana":
        return Path(ruta)
    carpeta = ROOT / "data/blocus/graficas/ambito_espana_20261028"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / Path(ruta).name


SUFIJO_TITULO = " · ámbito España" if AMBITO == "espana" else ""


def rotular_ambito(fig):
    """Añade el ámbito al título de la figura (el texto de tamaño 17)."""
    for t in fig.texts:
        if t.get_fontsize() == 17 and SUFIJO_TITULO not in t.get_text():
            t.set_text(t.get_text() + SUFIJO_TITULO)
