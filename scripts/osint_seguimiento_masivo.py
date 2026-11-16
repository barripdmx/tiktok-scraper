"""Seguimiento posterior a una cuenta Blocus: qué siguió cada seguidor después de seguirla.

Entrada: seguidores.csv de las cuentas españolas (lote del 25/10) y los seguidos.csv descargados de cada
seguidor (capturas/user_*/relaciones/*/seguidos.csv). TikTok devuelve las listas de la más reciente a la más
antigua (supuesto, igual que en seguidores): las cuentas ANTES de la Blocus en el fichero se siguieron DESPUÉS.
Salida en la carpeta del estudio: seguimiento_posterior.csv, coincidencias.csv, resumen.txt.
Uso: python -m scripts.osint_seguimiento_masivo
"""

import csv
import glob
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOTE = ROOT / "data/blocus/datos/lote_blocus_20261025T195208Z"
ESTUDIO = ROOT / "data/blocus/datos/osint_seguimiento_masivo_20261101"
CUENTAS = ("blocus.madrid blocusmanifestacionmdrz blocussalgeciras blocus148 blocusasturias manifestacion_barcelona "
           "blocus1barcelona blocus.barcelona blocusreus2 blocus.mallorca veyoubuy").split()
# Pista de nombre de usuario/apodo, no prueba de nada: revisar a mano.
CLAVES = re.compile(r"disturb|altercad|robo|ladron|saque|okupa|antifa|ultra|hooligan|riot|casse|emeute|"
                    r"vandal|tag[gs]?|crew|gang|pandilla|blocus|manif|huelga|bloque", re.I)


def leer(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    objetivo = defaultdict(list)  # seguidor -> [(cuenta Blocus, posición en su lista de seguidores)]
    for c in CUENTAS:
        for i, r in enumerate(leer(sorted(glob.glob(f"{LOTE}/user_{c}/relaciones/*/seguidores.csv"))[-1]), 1):
            objetivo[r["username"]].append((c, i))
    filas, despues = [], defaultdict(Counter)
    revisados = 0
    for ruta in glob.glob(f"{ESTUDIO}/capturas/user_*/relaciones/*/seguidos.csv"):
        seguidor = Path(ruta).parents[2].name[5:]
        lista = leer(ruta)
        if not lista:
            continue
        revisados += 1
        usuarios = [r["username"] for r in lista]
        for cuenta, pos_seguidor in objetivo.get(seguidor, []):
            if cuenta not in usuarios:  # la dejó de seguir o la lista está incompleta
                filas.append([seguidor, cuenta, pos_seguidor, len(usuarios), "", 0, ""])
                continue
            k = usuarios.index(cuenta)
            posteriores = usuarios[:k]
            for u in posteriores:
                despues[u][seguidor] += 1
            marcadas = [r["username"] for r in lista[:k] if CLAVES.search(r["username"] + " " + r["nickname"])]
            filas.append([seguidor, cuenta, pos_seguidor, len(usuarios), k + 1, len(posteriores), " ".join(marcadas)])
    with open(ESTUDIO / "seguimiento_posterior.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seguidor", "cuenta_blocus", "pos_en_seguidores_de_blocus", "total_seguidos_capturados",
                    "pos_de_blocus_en_sus_seguidos", "seguidas_despues", "posteriores_con_pista_en_nombre"])
        w.writerows(filas)
    comunes = [(u, len(s)) for u, s in despues.items() if len(s) >= 2]
    comunes.sort(key=lambda x: -x[1])
    with open(ESTUDIO / "coincidencias.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cuenta_seguida_despues", "seguidores_que_la_siguieron_despues", "pista_en_nombre"])
        w.writerows([u, n, "sí" if CLAVES.search(u) else ""] for u, n in comunes)
    con_pos = [x for x in filas if x[5] != 0 or x[4] != ""]
    resumen = (f"Seguidores con lista pública revisada: {revisados}\n"
               f"Pares seguidor-cuenta Blocus localizados: {len(con_pos)}\n"
               f"Cuentas seguidas después por 2 o más seguidores: {len(comunes)}\n")
    (ESTUDIO / "resumen.txt").write_text(resumen, encoding="utf-8")
    print(resumen)


if __name__ == "__main__":
    main()
