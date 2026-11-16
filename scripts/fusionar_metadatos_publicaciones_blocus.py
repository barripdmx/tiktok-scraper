"""Añade a publicaciones.csv de Blocus los metadatos de cada publicación.

Entrada: JSON con una lista de registros capturados desde la página pública de cada
publicación (campos abreviados, ver COLUMNAS) en --entrada (uno o varios archivos).
Salida: publicaciones.csv ampliado y metadatos_publicaciones.json (registros completos).
Las publicaciones que TikTok ya no sirve quedan con estado_metadatos «no_disponible:<código>».
"""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/blocus/datos/comentarios_blocus_20261026"
CSV_PATH = OUT / "publicaciones.csv"
JSON_PATH = OUT / "metadatos_publicaciones.json"

COLUMNAS = {
    "ct": "meta_creado_unix", "desc": "meta_descripcion", "ptitle": "meta_titulo_foto",
    "lang": "meta_idioma_texto", "titlang": "meta_idioma_titulo", "loc": "meta_pais_creacion",
    "aigct": "meta_aigc_label_type", "isaigc": "meta_is_aigc", "showaigc": "meta_mostrar_aviso_ia",
    "aigcd": "meta_aigc_descripcion", "cat": "meta_categoria", "ad": "meta_es_anuncio",
    "off": "meta_item_oficial", "orig": "meta_item_original", "priv": "meta_privado", "sec": "meta_secret",
    "ff": "meta_solo_amigos", "duet": "meta_duet", "stitch": "meta_stitch", "idx": "meta_indexable",
    "share": "meta_compartible", "cmts": "meta_estado_comentarios", "rev": "meta_en_revision",
    "proh": "meta_prohibido", "take": "meta_retirado", "sched": "meta_programado",
    "warn": "meta_aviso_json", "ctrl": "meta_item_control_json",
    "plays": "meta_reproducciones", "likes": "meta_me_gusta", "ncm": "meta_comentarios_api",
    "shares": "meta_compartidos", "saves": "meta_guardados", "reposts": "meta_reposts",
    "vid": "video_id_tiktok", "w": "video_ancho", "h": "video_alto", "dur": "video_duracion_s",
    "ratio": "video_ratio", "def": "video_definicion", "q": "video_calidad", "codec": "video_codec",
    "enc": "video_tipo_codificacion", "fmt": "video_formato", "vq": "video_vqscore",
    "size": "video_tamano_bytes", "br": "video_bitrate", "loud": "video_sonoridad", "peak": "video_pico_audio",
    "oaud": "video_audio_original", "subs": "video_subtitulos",
    "mid": "musica_id", "mt": "musica_titulo", "ma": "musica_autor", "mo": "musica_original",
    "md": "musica_duracion_s", "mc": "musica_copyright", "mcom": "musica_comercial",
    "aid": "autor_id", "au": "autor_usuario", "an": "autor_nombre",
    "aver": "autor_verificado", "apriv": "autor_privada", "acm": "autor_cfg_comentarios",
    "aduet": "autor_cfg_duet", "ast": "autor_cfg_stitch", "adl": "autor_cfg_descarga",
    "afol": "autor_seguidores", "afing": "autor_seguidos", "aheart": "autor_me_gusta",
    "avid": "autor_videos",
    "tags": "hashtags", "ments": "menciones", "nimg": "foto_n_imagenes", "iw": "foto_ancho", "ih": "foto_alto",
    "ib": "img_bytes", "ist": "img_http", "c2pa": "img_c2pa", "xmp": "img_xmp", "exift": "img_exif_tags",
    "gps": "img_gps", "fbmd": "img_fbmd", "dst": "img_digital_source_type", "agent": "img_c2pa_software_agent",
    "ctitle": "img_c2pa_titulo", "cgen": "img_c2pa_claim_generator", "signer": "img_c2pa_firma_tiktok",
    "xmptk": "img_xmp_toolkit", "extra": "meta_extra_json", "at": "meta_capturado_utc",
}
NUEVAS = ["estado_metadatos", "meta_creado_utc"] + [v for v in COLUMNAS.values() if v != "meta_creado_unix"]
NUEVAS.insert(2, "meta_creado_unix")


def cargar(entradas):
    registros = {}
    for ruta in entradas:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        for registro in datos:
            registros[str(registro["id"])] = registro
    return registros


def celda(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


def fila_meta(registro):
    if registro.get("err"):
        codigo = registro["err"].split(":")[1]
        return {"estado_metadatos": "no_disponible:" + codigo}
    fila = {"estado_metadatos": "ok" if registro.get("ct") != "0" else "ok_limitado"}
    for corto, largo in COLUMNAS.items():
        fila[largo] = celda(registro.get(corto))
    if registro.get("ct"):
        fila["meta_creado_utc"] = datetime.fromtimestamp(int(registro["ct"]), timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return fila


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", nargs="+", required=True)
    parser.add_argument("--csv", type=Path, default=CSV_PATH)
    parser.add_argument("--json", type=Path, default=JSON_PATH)
    args = parser.parse_args()

    registros = cargar(args.entrada)
    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        base = [c for c in lector.fieldnames if c not in NUEVAS]
        filas = list(lector)
    for fila in filas:
        registro = registros.get(fila["id"])
        for columna in NUEVAS:
            fila[columna] = ""
        fila["estado_metadatos"] = "pendiente"
        if registro:
            fila.update(fila_meta(registro))
    with args.csv.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=base + NUEVAS)
        escritor.writeheader()
        escritor.writerows(filas)
    temporal = args.json.with_suffix(".tmp")
    temporal.write_text(json.dumps([registros[k] for k in sorted(registros)], ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(args.json)
    estados = {}
    for fila in filas:
        estados[fila["estado_metadatos"]] = estados.get(fila["estado_metadatos"], 0) + 1
    print(json.dumps(estados, ensure_ascii=False))


if __name__ == "__main__":
    main()
