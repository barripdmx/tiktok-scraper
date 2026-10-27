"""Captura orden y cursores de las listas públicas de @jbarri.

Guarda solo datos públicos de lista; nunca almacena cookies ni firmas.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.scrapers.tiktok_descargar_relaciones import FetchError, TikTokClient


DEFAULT_PARENT = ROOT / "outputs" / "estudio_orden_jbarri_20261026"
FIELDS = (
    "lista", "posicion_respuesta", "pagina", "posicion_en_pagina", "user_id", "username",
    "cursor_enviado", "minCursor", "maxCursor", "observed_at", "evidencia",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def capture_list(client, profile: dict, direction: str, folder: Path, resume: bool = False) -> dict:
    if resume:
        with (folder.parent / f"{direction}.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        evidence_files = sorted(folder.glob("pagina_*.json"))
        if not evidence_files:
            raise ValueError(f"No hay páginas para reanudar {direction}.")
        old_pages = [json.loads(p.read_text(encoding="utf-8")) for p in evidence_files]
        cursor = str(old_pages[-1]["minCursor"])
        if not cursor.isdigit() or old_pages[-1]["hasMore"] is not True:
            raise ValueError(f"La última página de {direction} no permite reanudación.")
        seen = {"0", *(str(p["minCursor"]) for p in old_pages)}
        first_page = len(evidence_files) + 1
    else:
        folder.mkdir(parents=True, exist_ok=False)
        rows = []
        cursor = "0"
        seen = {cursor}
        first_page = 1
    status = "partial"
    reason = "unknown"
    advertised = profile.get("followers" if direction == "seguidores" else "following")
    try:
        for page_number in range(first_page, 1001):
            page, payload = client.user_list(profile["_sec_uid"], direction, cursor)
            observed = utcnow()
            evidence_path = folder / f"pagina_{page_number:04d}.json"
            evidence = {
                "username": "jbarri", "direction": direction, "page": page_number,
                "observed_at": observed, "cursor_sent": cursor,
                "minCursor": payload.get("minCursor"), "maxCursor": payload.get("maxCursor"),
                "hasMore": page.has_more, "isTruncated": payload.get("isTruncated"),
                "total": payload.get("total"), "rejected": page.rejected,
                "rows": [
                    {"position_in_page": i, "user_id": u["user_id"], "username": u["username"]}
                    for i, u in enumerate(page.users, 1)
                ],
            }
            evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
            for user in evidence["rows"]:
                rows.append({
                    "lista": direction, "posicion_respuesta": len(rows) + 1,
                    "pagina": page_number, "posicion_en_pagina": user["position_in_page"],
                    "user_id": user["user_id"], "username": user["username"],
                    "cursor_enviado": cursor, "minCursor": payload.get("minCursor"),
                    "maxCursor": payload.get("maxCursor"), "observed_at": observed,
                    "evidencia": str(evidence_path.resolve()),
                })
            print(f"@jbarri · {direction}: página {page_number}; {len(rows)} filas", flush=True)
            if payload.get("isTruncated"):
                reason = "upstream_truncated"
                break
            if page.has_more is False:
                status, reason = "pagination_exhausted", "has_more_false"
                break
            next_cursor = payload.get("minCursor")
            if page.has_more is not True or isinstance(next_cursor, bool) or not isinstance(next_cursor, int):
                reason = "missing_cursor"
                break
            if str(next_cursor) in seen or not page.users:
                reason = "repeated_cursor_or_empty_page"
                break
            cursor = str(next_cursor)
            seen.add(cursor)
        else:
            reason = "page_limit"
    except FetchError as exc:
        status = "partial" if rows else "unavailable"
        reason = exc.reason
    with (folder.parent / f"{direction}.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "status": status, "reason": reason, "rows": len(rows), "pages": len(list(folder.glob("pagina_*.json"))),
        "advertised_count_start": advertised, "duplicates": len(rows) - len({r["user_id"] for r in rows}),
        "finished_at": utcnow(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", type=Path, default=None)
    parser.add_argument("--reanudar", type=Path, help="Carpeta captura_web_* incompleta.")
    args = parser.parse_args()
    parent = args.salida or DEFAULT_PARENT
    parent.mkdir(parents=True, exist_ok=True)
    run = args.reanudar or parent / ("captura_web_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    if args.reanudar:
        previous = json.loads((run / "resumen.json").read_text(encoding="utf-8"))
        if previous.get("target") != "jbarri":
            raise ValueError("La captura no pertenece a @jbarri.")
    else:
        run.mkdir(exist_ok=False)
        previous = None
    client = TikTokClient(SimpleNamespace(sesion="anonima", cookies=None, cancel_file=None))
    result = previous or {"target": "jbarri", "started_at": utcnow(), "lists": {}}
    try:
        profile = client.profile("jbarri")
        if previous and profile.get("user_id") != previous.get("profile", {}).get("user_id"):
            raise ValueError("El ID de @jbarri cambió; no se mezclan capturas.")
        result["profile"] = {k: profile.get(k) for k in
                             ("username", "user_id", "followers", "following", "private_account", "following_visibility")}
        for direction in ("seguidores", "seguidos"):
            if previous and previous.get("lists", {}).get(direction, {}).get("status") == "pagination_exhausted":
                continue
            if direction == "seguidos" and profile.get("following_visibility") not in (None, 1, "1"):
                result["lists"][direction] = {"status": "unavailable", "reason": "private_list"}
                continue
            result["lists"][direction] = capture_list(client, profile, direction, run / direction,
                                                       resume=bool(previous))
        try:
            end = client.profile("jbarri")
            for direction, count_key in (("seguidores", "followers"), ("seguidos", "following")):
                result["lists"][direction]["advertised_count_end"] = end.get(count_key)
        except FetchError as exc:
            result["profile_end_error"] = exc.reason
    finally:
        client.close()
        result["finished_at"] = utcnow()
        (run / "resumen.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(run.resolve())
    return 0 if all(v.get("status") == "pagination_exhausted" for v in result["lists"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
