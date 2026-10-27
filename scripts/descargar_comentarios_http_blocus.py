"""Descarga reanudable de comentarios y respuestas de posts públicos Blocus.

Inventario: enlaces de vídeo y foto observados en el perfil de cada cuenta.
Red: reutiliza el cliente HTTP y la sesión principal del proyecto.
"""

import argparse
import csv
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/comentarios_blocus_20261026"
SOURCE = ROOT / "src/scrapers/tiktok_descargar_relaciones.py"
INPUT = OUT / "inventario_navegador.json"
POSTS = OUT / "por_publicacion"
FIELDS = ["cuenta_publicadora", "tipo_publicacion", "publication_id", "publication_url",
          "comment_id", "parent_comment_id", "is_reply", "autor_id", "autor_handle",
          "autor_nombre", "texto", "creado_utc", "likes", "replies_declaradas",
          "comentario_fijado", "imagenes"]


def module():
    spec = importlib.util.spec_from_file_location("_blocus_relaciones", SOURCE)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def inventory():
    entries = json.loads(INPUT.read_text(encoding="utf-8"))
    accounts = {}
    posts = []
    seen = set()
    for entry in entries:
        user = entry["user"]
        links = list(dict.fromkeys(entry.get("links") or []))
        accounts[user] = {"cuenta": user, "publicaciones_observadas": len(links),
                          "publicaciones_declaradas": entry.get("declared"),
                          "perfil_disponible": entry.get("declared") is not None,
                          "error_navegador": entry.get("error", ""),
                          "problema_navegador": entry.get("problem", False)}
        for url in links:
            match = re.fullmatch(r"https://www\.tiktok\.com/@([^/]+)/(video|photo)/(\d+)", url)
            if not match or match.group(1).lower() != user.lower():
                continue
            identifier = match.group(3)
            if identifier not in seen:
                posts.append({"cuenta": user, "tipo": match.group(2), "id": identifier, "url": url})
                seen.add(identifier)
    return accounts, posts


def fetch(client, path, params):
    response = client._get(path, params)
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError("Respuesta JSON inválida") from None
    if not isinstance(data, dict) or data.get("status_code") not in (0, "0"):
        raise RuntimeError(f"Error API: {data.get('status_code') if isinstance(data, dict) else 'formato'}")
    return data


def collect_pages(client, path, base_params, replies=False):
    cursor = 0
    seen_cursors = set()
    items = {}
    reported = None
    complete = False
    pages = 0
    while cursor not in seen_cursors:
        seen_cursors.add(cursor)
        data = fetch(client, path, {**base_params, "count": 50, "cursor": cursor})
        pages += 1
        batch = data.get("comments") or []
        for item in batch:
            identifier = str(item.get("cid") or item.get("id") or "")
            if identifier:
                items[identifier] = item
        if isinstance(data.get("total"), int):
            reported = data["total"]
        if not data.get("has_more"):
            if not (replies and reported is not None and len(items) < reported and batch):
                complete = not (replies and reported is not None and len(items) < reported)
                break
        next_cursor = data.get("cursor")
        if not isinstance(next_cursor, int) or next_cursor <= cursor or not batch:
            break
        if replies and reported is not None and next_cursor >= reported:
            complete = len(items) >= reported
            break
        cursor = next_cursor
    return list(items.values()), reported, complete, pages


def normalize(post, comment, parent=""):
    user = comment.get("user") or {}
    epoch = comment.get("create_time")
    try:
        date = datetime.fromtimestamp(int(epoch), timezone.utc).isoformat() if epoch else ""
    except (TypeError, ValueError, OverflowError):
        date = ""
    return {"cuenta_publicadora": post["cuenta"], "tipo_publicacion": post["tipo"],
            "publication_id": post["id"], "publication_url": post["url"],
            "comment_id": str(comment.get("cid") or comment.get("id") or ""),
            "parent_comment_id": parent, "is_reply": int(bool(parent)),
            "autor_id": str(user.get("uid") or user.get("id") or ""),
            "autor_handle": user.get("unique_id") or "",
            "autor_nombre": user.get("nickname") or "", "texto": comment.get("text") or "",
            "creado_utc": date, "likes": comment.get("digg_count") or 0,
            "replies_declaradas": comment.get("reply_comment_total") or 0,
            "comentario_fijado": comment.get("stick_position") or 0,
            "imagenes": len(comment.get("image_list") or [])}


def download_post(client, post):
    top, total, main_complete, main_pages = collect_pages(
        client, "/api/comment/list/", {"aid": 1988, "aweme_id": post["id"]})
    rows = {}
    replies_expected = 0
    replies_complete = True
    reply_pages = 0
    for item in top:
        row = normalize(post, item)
        rows[row["comment_id"]] = row
        inline = item.get("reply_comment") or []
        for reply in inline if isinstance(inline, list) else []:
            parsed = normalize(post, reply, row["comment_id"])
            rows[parsed["comment_id"]] = parsed
        expected = int(item.get("reply_comment_total") or 0)
        replies_expected += expected
        if expected:
            replies, _, complete, pages = collect_pages(
                client, "/api/comment/list/reply/",
                {"aid": 1988, "item_id": post["id"], "comment_id": row["comment_id"]}, replies=True)
            reply_pages += pages
            replies_complete &= complete
            for reply in replies:
                parsed = normalize(post, reply, row["comment_id"])
                rows[parsed["comment_id"]] = parsed
    captured_replies = sum(bool(row["is_reply"]) for row in rows.values())
    coverage_ok = ((total is None or len(rows) >= total)
                   and captured_replies >= replies_expected)
    data = {"post": post, "status": "completo" if main_complete and replies_complete and coverage_ok else "parcial",
            "collection_version": 2,
            "reportados_principales": total, "respuestas_declaradas": replies_expected,
            "paginas_principales": main_pages, "paginas_respuestas": reply_pages,
            "descargado_utc": datetime.now(timezone.utc).isoformat(), "comentarios": list(rows.values())}
    return data


def write_outputs(accounts, posts):
    summary = []
    csv_path = OUT / "comentarios.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for post in posts:
            path = POSTS / f"{post['id']}.json"
            if not path.exists():
                summary.append({**post, "estado": "pendiente", "capturados": 0})
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for row in data.get("comentarios", []):
                writer.writerow({key: row.get(key, "") for key in FIELDS})
            summary.append({**post, "estado": data.get("status"),
                            "capturados": len(data.get("comentarios", [])),
                            "reportados_principales": data.get("reportados_principales"),
                            "respuestas_declaradas": data.get("respuestas_declaradas"),
                            "error": data.get("error", "")})
    with (OUT / "estado_publicaciones.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["cuenta", "tipo", "id", "url", "estado", "capturados",
                                                "reportados_principales", "respuestas_declaradas", "error"])
        writer.writeheader()
        writer.writerows(summary)
    per_account = []
    for username, account in accounts.items():
        own = [row for row in summary if row["cuenta"] == username]
        per_account.append({**account,
                            "publicaciones_descargadas": sum(row["estado"] in ("completo", "parcial") for row in own),
                            "publicaciones_completas": sum(row["estado"] == "completo" for row in own),
                            "publicaciones_parciales": sum(row["estado"] == "parcial" for row in own),
                            "comentarios_capturados": sum(row["capturados"] for row in own)})
    with (OUT / "estado_cuentas.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        fields = ["cuenta", "perfil_disponible", "publicaciones_declaradas",
                  "publicaciones_observadas", "publicaciones_descargadas", "publicaciones_completas",
                  "publicaciones_parciales", "comentarios_capturados", "error_navegador",
                  "problema_navegador"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(per_account)
    atomic_json(OUT / "resumen.json", {"cuentas": list(accounts.values()), "publicaciones": len(posts),
                                      "publicaciones_completas": sum(x["estado"] == "completo" for x in summary),
                                      "publicaciones_parciales": sum(x["estado"] == "parcial" for x in summary),
                                      "publicaciones_pendientes": sum(x["estado"] == "pendiente" for x in summary),
                                      "comentarios_capturados": sum(x["capturados"] for x in summary)})


def audit_existing():
    for path in POSTS.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") != "completo":
            continue
        rows = data.get("comentarios") or []
        replies = sum(bool(row.get("is_reply")) for row in rows)
        if (len(rows) < (data.get("reportados_principales") or 0)
                or replies < (data.get("respuestas_declaradas") or 0)):
            data["status"] = "parcial"
            atomic_json(path, data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo-inventario", action="store_true")
    parser.add_argument("--max-publicaciones", type=int)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    POSTS.mkdir(exist_ok=True)
    audit_existing()
    accounts, posts = inventory()
    with (OUT / "publicaciones.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["cuenta", "tipo", "id", "url"])
        writer.writeheader()
        writer.writerows(posts)
    print(f"Inventario: {len(accounts)} cuentas, {len(posts)} publicaciones", flush=True)
    if args.solo_inventario:
        write_outputs(accounts, posts)
        return
    rel = module()
    client = rel.TikTokClient(argparse.Namespace(cookies=None, sesion="principal"))
    try:
        for i, post in enumerate(posts[:args.max_publicaciones] if args.max_publicaciones else posts, 1):
            path = POSTS / f"{post['id']}.json"
            if path.exists():
                prior = json.loads(path.read_text(encoding="utf-8"))
                if prior.get("status") == "completo" or (
                        prior.get("collection_version") == 2 and prior.get("status") == "parcial"):
                    continue
            try:
                data = download_post(client, post)
                atomic_json(path, data)
                print(f"[{i}/{len(posts)}] @{post['cuenta']} {post['id']}: {len(data['comentarios'])} comentarios, {data['status']}", flush=True)
            except rel.FetchError as exc:
                atomic_json(path, {"post": post, "status": "error", "error": str(exc), "comentarios": []})
                print(f"[{i}/{len(posts)}] {post['id']}: {exc}", flush=True)
                if exc.halt_batch:
                    break
            except Exception as exc:
                atomic_json(path, {"post": post, "status": "error", "error": str(exc), "comentarios": []})
                print(f"[{i}/{len(posts)}] {post['id']}: {exc}", flush=True)
            if i % 10 == 0:
                write_outputs(accounts, posts)
    finally:
        client.close()
        write_outputs(accounts, posts)


if __name__ == "__main__":
    main()
