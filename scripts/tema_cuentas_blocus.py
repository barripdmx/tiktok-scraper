"""Clasifica las cuentas Blocus por tema: francés, español o común (hablan de los dos).

Evidencia por cuenta, en este orden:
1. Idioma de lo que publica (descripciones, hashtags) y de los comentarios de sus publicaciones, contando palabras
   distintivas del francés y del español (listas FR/ES de abajo).
2. Si casi no hay texto (menos de 3 palabras distintivas): país de creación declarado por TikTok; en las cuentas sin
   publicaciones, el grupo «referencia_espana» de las candidatas.
Reglas: español/francés si ese idioma supera el 60 % de las palabras distintivas; común si cada idioma tiene al menos
20 palabras y el 8 % del total. Es una clasificación heurística: la columna «confianza» indica cuánta evidencia hay.
Escribe data/blocus/datos/grafo_blocus_20261025/tema_cuentas.csv.
"""

import csv
import json
import re
from collections import Counter

from config.blocus import FALSOS_POSITIVOS
from scripts.estilo_presentacion_blocus import ROOT

SALIDA = ROOT / "data/blocus/datos/grafo_blocus_20261025/tema_cuentas.csv"
PUBLICACIONES = ROOT / "data/blocus/datos/comentarios_blocus_20261026/publicaciones.csv"
COMENTARIOS = ROOT / "data/blocus/datos/comentarios_blocus_20261026/comentarios.csv"
CANDIDATAS = ROOT / "data/blocus/datos/cuentas_blocus_20261025/candidatas_ampliadas.json"
PAISES_FR = {"FR", "BE", "CA", "RO", "NL", "IT"}  # cuentas con texto francés fuera de Francia
FR = set("les des est pas vous nous c'est cest qui avec mais sont ça très faut jamais merci mdr lycée lycee macron aujourd'hui "
         "demain faire être je suis du aux ont comme cette ces mon ma mes notre votre dans pour".split())
ES = set("los las del para por con una es vamos españa espana huelga manifestación manifestacion gobierno pero como más esto "
         "todos todas nuestro vuestro hoy mañana semana institutos porfavor gracias estudiantes instituto murcia catalunya".split())
PALABRA = re.compile(r"[a-zà-ÿñ']+")


# Revisión manual: el recuento de palabras la dejaba como «común», pero sus 22 publicaciones tratan de Francia
# (#french, #manifest) y sus comentarios, en inglés, portugués y ruso, hablan de Francia, Macron y París; ninguno de España.
REVISADAS = {"ftbl687": "revisión manual: contenido sobre Francia, sin publicaciones sobre España"}


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def hits(texto):
    palabras = PALABRA.findall(texto.lower())
    return sum(p in FR for p in palabras), sum(p in ES for p in palabras)


def clasificar():
    pubs, coms = leer(PUBLICACIONES), leer(COMENTARIOS)
    ref_es = {c["username"] for c in json.loads(CANDIDATAS.read_text(encoding="utf-8"))["accounts"]
              if c.get("group") == "referencia_espana"}
    cuentas = ({r["cuenta"] for r in pubs} | {r["cuenta_publicadora"] for r in coms} | ref_es) - set(FALSOS_POSITIVOS)
    filas = []
    for cuenta in sorted(cuentas):
        propio = " ".join(r["meta_descripcion"] + " " + r["hashtags"].replace("|", " ") + " " + r["meta_titulo_foto"]
                          for r in pubs if r["cuenta"] == cuenta)
        ajeno = " ".join(r["texto"] for r in coms if r["cuenta_publicadora"] == cuenta)
        (f1, e1), (f2, e2) = hits(propio), hits(ajeno)
        f, e = f1 + f2, e1 + e2
        paises = Counter(r["meta_pais_creacion"] for r in pubs if r["cuenta"] == cuenta and r["meta_pais_creacion"])
        pais = paises.most_common(1)[0][0] if paises else ""
        total = f + e
        if total >= 3:
            if min(f, e) >= 20 and min(f, e) / total >= 0.08:
                tema, motivo = "común", "ambos idiomas con peso"
            else:
                tema = "español" if e / total > 0.6 else "francés" if f / total > 0.6 else "sin clasificar"
                motivo = "idioma del texto"
            confianza = "alta" if total >= 20 else "baja"
        elif cuenta in ref_es:
            tema, motivo, confianza = "español", "grupo referencia_espana (sin texto)", "baja"
        elif pais == "ES":
            tema, motivo, confianza = "español", "país de creación ES (sin texto)", "baja"
        elif pais in PAISES_FR:
            tema, motivo, confianza = "francés", f"país de creación {pais} (sin texto)", "baja"
        else:
            tema, motivo, confianza = "sin clasificar", "sin evidencia", "—"
        if cuenta in REVISADAS:
            tema, motivo, confianza = "francés", REVISADAS[cuenta], "alta"
        filas.append({"cuenta": cuenta, "tema": tema, "confianza": confianza, "palabras_fr": f, "palabras_es": e,
                      "pais_creacion": pais, "motivo": motivo})
    return filas


def temas():
    """Diccionario cuenta -> tema."""
    return {f["cuenta"]: f["tema"] for f in clasificar()}


if __name__ == "__main__":
    filas = clasificar()
    with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    print(SALIDA, dict(Counter(f["tema"] for f in filas)))
    for f in filas:
        if f["tema"] != "francés" or f["confianza"] == "baja":
            print(f"{f['cuenta']:26s}{f['tema']:15s}{f['confianza']:6s}fr={f['palabras_fr']:5d} es={f['palabras_es']:4d} {f['motivo']}")
