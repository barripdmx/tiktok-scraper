"""Comentarios de «combinación atípica de emojis» en los comentarios capturados de Blocus.

Definición (reproducible): comentario formado solo por 2 a 4 emojis Unicode, todos distintos entre sí,
ninguno de los 15 emojis más frecuentes en los comentarios de las demás cuentas. Se descartan los
modificadores de tono de piel y los códigos de pegatinas de TikTok («[Réconfortant]»).
Se excluyen las cuentas falso positivo (config/blocus.py).
"""

import csv
import re
from collections import Counter
from pathlib import Path

from config.blocus import FALSOS_POSITIVOS

ROOT = Path(__file__).resolve().parents[1]
COMENTARIOS = ROOT / "outputs/comentarios_blocus_20261026/comentarios.csv"
CUENTA_FOCO = "teamblocus"
TOP_COMUNES = 15
EMOJI = re.compile("[\U0001F1E6-\U0001F1FF]{2}|[\U0001F000-\U0001F1E5\U0001F200-\U0001FAFF☀-➿⬀-⯿"
                   "←-⇿⌀-⏿■-◿‼⁉™ℹ〰〽㊗㊙]")
TONO_PIEL = re.compile("[🏻-🏿]")
RUIDO = re.compile(r"[\s️‍]")


def emojis(texto):
    """Devuelve (lista de emojis, ¿el comentario es solo emojis?)."""
    texto = TONO_PIEL.sub("", texto)
    return EMOJI.findall(texto), not RUIDO.sub("", EMOJI.sub("", texto))


def cargar():
    with COMENTARIOS.open(encoding="utf-8-sig", newline="") as f:
        filas = [r for r in csv.DictReader(f) if r["cuenta_publicadora"] not in FALSOS_POSITIVOS]
    for r in filas:
        r["emojis"], r["solo_emojis"] = emojis(r["texto"])
        r["n_emojis"] = len(r["emojis"])
        r["solo_2a4"] = r["solo_emojis"] and 2 <= r["n_emojis"] <= 4
    comunes = {e for e, _ in Counter(e for r in filas if r["cuenta_publicadora"] != CUENTA_FOCO
                                     for e in r["emojis"]).most_common(TOP_COMUNES)}
    for r in filas:
        r["atipico"] = r["solo_2a4"] and len(set(r["emojis"])) == r["n_emojis"] and not set(r["emojis"]) & comunes
    return filas, comunes


def resumen(filas):
    foco = [r for r in filas if r["cuenta_publicadora"] == CUENTA_FOCO]
    resto = [r for r in filas if r["cuenta_publicadora"] != CUENTA_FOCO]
    return foco, resto


if __name__ == "__main__":
    filas, comunes = cargar()
    foco, resto = resumen(filas)
    at = [r for r in foco if r["atipico"]]
    print("comunes:", "".join(sorted(comunes)))
    print(f"atípicos foco {len(at)}/{len(foco)}  resto {sum(r['atipico'] for r in resto)}/{len(resto)}")
    print(f"solo 2-4 emojis foco {sum(r['solo_2a4'] for r in foco)}  resto {sum(r['solo_2a4'] for r in resto)}")
    apar = [e for r in at for e in r["emojis"]]
    print("apariciones", len(apar), "distintos", len(set(apar)), "autores", len({r["autor_id"] for r in at}))
    print("por n:", Counter(r["n_emojis"] for r in at), "por día:", Counter(r["creado_utc"][:10] for r in at).most_common(6))
