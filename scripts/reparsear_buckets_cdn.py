"""Re-parsea los buckets de origen del CDN de TikTok desde los JSON crudos de Blocus (solo lectura).

Genera un CSV NUEVO con el bucket completo y el sufijo del avatar del autor y del vídeo, y una tabla cruzada
avatar vs. vídeo. No modifica ningún archivo existente ni lleva el host por fila (solo imprime los hosts únicos).

    python -m scripts.reparsear_buckets_cdn [carpeta_metadatos_crudos] [-o salida.csv]
"""
import os
import re
import sys
import csv
import glob
import json
import argparse
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "utils"))
from tiktok_utils import bucket_cdn, cluster_cdn, _snowflake_ts  # noqa: E402

CARPETA = os.path.join("data", "blocus", "datos", "comentarios_blocus_20261026", "metadatos_crudos")
COLUMNAS = ["video_id", "autor_uid", "autor_cohorte_anio", "avatar_origin_bucket", "avatar_bucket_suffix",
            "avatar_legacy_musically", "video_origin_bucket", "video_bucket_suffix"]


def _urls_avatar(autor: dict) -> list:
    return [autor.get(k) for k in ("avatarThumb", "avatarMedium", "avatarLarger")]


def _urls_video(video: dict) -> list:
    play = video.get("playAddr")
    if isinstance(play, dict):
        play = (play.get("UrlList") or [""])[0]
    return [(video.get("PlayAddrStruct") or {}).get("UrlList", [""])[0], play, video.get("downloadAddr")]


def _primero(urls) -> tuple:
    """Bucket de la primera URL que lo tenga: (bucket, sufijo, legacy, url)."""
    for u in urls:
        b = bucket_cdn(u)
        if b[0]:
            return (*b, u)
    return "", "", False, ""


def _host(url) -> str:
    m = re.match(r"https?://([^/]+)/", url) if isinstance(url, str) else None
    return m.group(1) if m else ""


def _cluster(bucket: str) -> str:
    return cluster_cdn("/" + bucket + "/") if bucket else ""


def leer(carpeta: str):
    filas, hosts = [], {"avatar": Counter(), "video": Counter()}
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        try:
            with open(ruta, encoding="utf-8") as f:
                item = (json.load(f) or {}).get("item") or {}
        except (OSError, ValueError):
            continue
        if not item.get("id"):
            continue
        autor, video = item.get("author") or {}, item.get("video") or {}
        ab, asf, aleg, au = _primero(_urls_avatar(autor))
        vb, vsf, _, vu = _primero(_urls_video(video))
        hosts["avatar"][_host(au)] += 1
        hosts["video"][_host(vu)] += 1
        ts = _snowflake_ts(autor.get("id"))
        filas.append({"video_id": str(item["id"]), "autor_uid": str(autor.get("id") or ""),
                      "autor_cohorte_anio": datetime.fromtimestamp(ts, tz=timezone.utc).year if ts else "",
                      "avatar_origin_bucket": ab, "avatar_bucket_suffix": asf,
                      "avatar_legacy_musically": str(aleg) if ab else "",
                      "video_origin_bucket": vb, "video_bucket_suffix": vsf})
    return filas, hosts


def _tabla(titulo: str, pares: Counter, filas_k, cols_k) -> None:
    print(f"\n{titulo}  (filas = avatar, columnas = vídeo)")
    ancho = max(len(str(c)) for c in cols_k + ["avatar \\ vídeo"]) + 2
    print("avatar \\ vídeo".ljust(16) + "".join(str(c).rjust(ancho) for c in cols_k) + "total".rjust(ancho))
    for a in filas_k:
        tot = sum(pares[(a, v)] for v in cols_k)
        print(str(a).ljust(16) + "".join(str(pares[(a, v)]).rjust(ancho) for v in cols_k) + str(tot).rjust(ancho))


def resumen(filas: list, hosts: dict) -> None:
    con_ambos = [r for r in filas if r["avatar_origin_bucket"] and r["video_origin_bucket"]]
    print(f"Vídeos leídos: {len(filas)} | con bucket de avatar: {sum(bool(r['avatar_origin_bucket']) for r in filas)}"
          f" | con bucket de vídeo: {sum(bool(r['video_origin_bucket']) for r in filas)} | con ambos: {len(con_ambos)}")
    for k, c in hosts.items():
        print(f"Hosts únicos de {k}: {dict(c)}")
    if not con_ambos:
        return
    for r in con_ambos:
        r["_ac"], r["_vc"] = _cluster(r["avatar_origin_bucket"]), _cluster(r["video_origin_bucket"])
        r["_as"], r["_vs"] = r["avatar_bucket_suffix"] or "(vacío)", r["video_bucket_suffix"] or "(vacío)"
    cl = sorted({r["_ac"] for r in con_ambos} | {r["_vc"] for r in con_ambos})
    _tabla("Clúster", Counter((r["_ac"], r["_vc"]) for r in con_ambos), cl, cl)
    su = sorted({r["_as"] for r in con_ambos} | {r["_vs"] for r in con_ambos})
    _tabla("Sufijo", Counter((r["_as"], r["_vs"]) for r in con_ambos), su, su)
    dis = [r for r in con_ambos if r["_ac"] != r["_vc"]]
    print(f"\nAvatar y vídeo en distinto clúster: {len(dis)} de {len(con_ambos)} ({len(dis) / len(con_ambos):.1%})")
    llamativos = [r for r in dis if r["_ac"] == "alisg" or r["avatar_legacy_musically"] == "True"
                  or (r["_vc"] == "no1a" and r["_ac"] != "no1a")]
    print(f"Discordancias llamativas (avatar alisg o legacy, o vídeo no1a con avatar de otro clúster): {len(llamativos)}")
    for r in llamativos[:15]:
        print(f"  {r['video_id']}  avatar={r['avatar_origin_bucket']}  vídeo={r['video_origin_bucket']}")
    print("\nCohorte (año de creación de la cuenta del autor) vs. clúster del avatar")
    por = {}
    for r in filas:
        if r["autor_cohorte_anio"] != "" and r["avatar_origin_bucket"]:
            por.setdefault(r["autor_cohorte_anio"], Counter())[_cluster(r["avatar_origin_bucket"])] += 1
    for anio in sorted(por):
        print(f"  {anio}: {dict(por[anio])}")
    out = [r for r in filas if r["autor_cohorte_anio"] == 2026 and r["avatar_origin_bucket"] and _cluster(r["avatar_origin_bucket"]) != "no1a"]
    print(f"Outliers intra-cohorte: cuentas de 2026 con avatar fuera de no1a: {len(out)}; "
          f"avatares legacy musically: {sum(r['avatar_legacy_musically'] == 'True' for r in filas)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("carpeta", nargs="?", default=CARPETA)
    ap.add_argument("-o", "--salida", default=os.path.join(os.path.dirname(CARPETA), "buckets_cdn_reparseo.csv"))
    a = ap.parse_args()
    filas, hosts = leer(a.carpeta)
    with open(a.salida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
        w.writeheader()
        w.writerows(filas)
    print(f"CSV nuevo: {a.salida}")
    resumen(filas, hosts)


if __name__ == "__main__":
    main()
