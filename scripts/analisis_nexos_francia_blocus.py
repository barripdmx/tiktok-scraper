"""Indicios de nexo entre las cuentas de tema español y la red francesa de Blocus (alimenta el informe OSINT).

Mide, solo con datos ya capturados: país declarado por TikTok en las publicaciones, idioma, hashtags comunes,
audiencia (seguidores) y comentaristas compartidos, y fechas de creación. Escribe nexos_francia.json junto al informe.
Un indicio no prueba coordinación ni origen: las cuentas pueden compartir un tema y una audiencia sin tener relación.
"""

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from config.blocus import FALSOS_POSITIVOS_BASE

ROOT = Path(__file__).resolve().parents[1]
DATOS = ROOT / "data/blocus/datos"
SALIDA = ROOT / "data/blocus/estudios/informe_osint_nexos_francia"
# Solo palabras que no existen en la otra lengua (le, la, les, que, sur, est… se comparten con el español y falsean el recuento)
FR = re.compile(r"\b(des|une|pour|dans|avec|nous|vous|pas|qui|c'est|ça|très|être|aussi|mais|merci|bonjour|j'ai|t'es|bloquons|grève|lycée|étudiants?)\b", re.I)
ES = re.compile(r"\b(los|las|una|para|con|nosotros|estamos|huelga|estudiantes|convocatoria|instituto|cuando|vamos|pero|también|muy|esto|está|gracias)\b", re.I)


def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    tema = {r["cuenta"]: r["tema"] for r in leer(DATOS / "grafo_blocus_20261025/tema_cuentas.csv") if r["cuenta"] not in FALSOS_POSITIVOS_BASE}
    es = {c for c, t in tema.items() if t == "español"}
    fr = {c for c, t in tema.items() if t == "francés"}
    pubs = [r for r in leer(DATOS / "comentarios_blocus_20261026/publicaciones.csv") if r["cuenta"] in tema]
    coms = [r for r in leer(DATOS / "comentarios_blocus_20261026/comentarios.csv") if r["cuenta_publicadora"] in tema]
    cuentas = {r["username"]: r for r in leer(DATOS / "grafo_blocus_20261025/cuentas.csv") if r["objetivo"]}
    out = {"cuentas": {"español": len(es), "francés": len(fr), "sin clasificar": len(tema) - len(es) - len(fr)}}

    por = lambda grupo: [p for p in pubs if p["cuenta"] in grupo]
    out["publicaciones"] = {"español": len(por(es)), "francés": len(por(fr))}
    out["pais_creacion"] = {n: Counter(p["meta_pais_creacion"] or "sin dato" for p in por(g)).most_common() for n, g in (("español", es), ("francés", fr))}
    out["idioma_texto"] = {n: Counter(p["meta_idioma_texto"] or "sin dato" for p in por(g)).most_common() for n, g in (("español", es), ("francés", fr))}

    etiquetas = lambda g: Counter(h.strip().lower() for p in por(g) for h in p["hashtags"].split("|") if h.strip())
    h_es, h_fr = etiquetas(es), etiquetas(fr)
    out["hashtags_comunes"] = sorted(((h, h_es[h], h_fr[h]) for h in set(h_es) & set(h_fr)), key=lambda x: -(x[1] + x[2]))[:15]

    # Francés en los textos de las publicaciones españolas (descripción y título)
    fr_en_es = [p["cuenta"] for p in por(es) if len(FR.findall(p["meta_descripcion"] + " " + p["meta_titulo_foto"])) > len(ES.findall(p["meta_descripcion"] + " " + p["meta_titulo_foto"]))]
    out["publicaciones_espanolas_con_texto_mas_frances_que_espanol"] = Counter(fr_en_es).most_common()

    # Comentarios: autores en cuentas españolas y francesas
    autores = defaultdict(set)
    for c in coms:
        autores[c["cuenta_publicadora"]].add(c["autor_id"])
    a_es = set().union(*(autores[c] for c in es)) if es else set()
    a_fr = set().union(*(autores[c] for c in fr)) if fr else set()
    out["comentaristas"] = {"en_cuentas_espanolas": len(a_es), "en_cuentas_francesas": len(a_fr), "en_ambos": len(a_es & a_fr)}
    out["comentarios_idioma"] = {n: {"mas_frances": sum(len(FR.findall(c["texto"])) > len(ES.findall(c["texto"])) for c in coms if c["cuenta_publicadora"] in g),
                                    "mas_espanol": sum(len(ES.findall(c["texto"])) > len(FR.findall(c["texto"])) for c in coms if c["cuenta_publicadora"] in g),
                                    "total": sum(1 for c in coms if c["cuenta_publicadora"] in g)} for n, g in (("español", es), ("francés", fr))}

    # Audiencia común (seguidores) entre pares de cuentas
    pares = leer(DATOS / "grafo_blocus_20261025/coincidencias_seguidores.csv")
    suma = Counter()
    for r in pares:
        a, b, n = r["a"], r["b"], int(r["shared"])
        if a in tema and b in tema:
            suma["español-español" if a in es and b in es else "francés-francés" if a in fr and b in fr else "español-francés" if {a, b} & es and {a, b} & fr else "otros"] += n
    out["audiencia_comun_seguidores"] = dict(suma)
    out["pares_espanol_frances_top"] = sorted(([r["a"], r["b"], int(r["shared"])] for r in pares if {r["a"], r["b"]} <= set(tema) and
                                                ((r["a"] in es and r["b"] in fr) or (r["b"] in es and r["a"] in fr))), key=lambda x: -x[2])[:10]

    # Fecha de creación de las cuentas (perfil) frente a su primera publicación
    fechas = {}
    for c in tema:
        f = cuentas.get(c, {}).get("fecha_creacion_perfil_utc") or cuentas.get(c, {}).get("fecha_uid_estimada_utc")
        if f:
            fechas[c] = f[:10]
    out["creacion_cuentas"] = {n: sorted((fechas[c], c) for c in g if c in fechas) for n, g in (("español", es), ("francés", fr))}
    primera = {}
    for p in pubs:
        t = datetime.fromtimestamp(int(p["id"]) >> 32, timezone.utc)
        if p["cuenta"] not in primera or t < primera[p["cuenta"]]:
            primera[p["cuenta"]] = t
    out["primera_publicacion"] = {n: sorted((primera[c].strftime("%Y-%m-%d %H:%M"), c) for c in g if c in primera) for n, g in (("español", es), ("francés", fr))}

    # Apodos con letras matemáticas y nombres que replican un patrón
    out["apodos_decorativos"] = [c for c in tema if any(0x1D400 <= ord(ch) <= 0x1D7FF for ch in cuentas.get(c, {}).get("nickname", ""))]
    out["texto_repetido_entre_cuentas"] = [(t, n) for t, n in Counter(p["meta_descripcion"].strip().lower() for p in pubs if len(p["meta_descripcion"]) > 30).most_common(8) if n > 1]
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "nexos_francia.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
