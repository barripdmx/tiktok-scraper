"""Amplía fechas declaradas por perfiles de usuarios del conjunto Blocus.

Consulta perfiles públicos a ritmo del cliente existente, valida el UID y guarda
progreso incremental. No convierte las fechas derivadas del UID en confirmadas.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.scrapers.tiktok_descargar_relaciones import FetchError, TikTokClient
from src.utils.tiktok_relaciones import atomic_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "blocus" / "datos" / "fechas_perfiles_ampliacion_20261027"
CACHE = OUT / "consultas_por_id.json"
STATE = OUT / "estado.json"
USERS = ROOT / "data" / "blocus" / "datos" / "usuarios_fecha_creacion" / "usuarios_por_fecha_creacion.csv"
GRAPH = ROOT / "data" / "blocus" / "datos" / "grafo_blocus_20261025" / "cuentas.csv"
OLD_CACHE = ROOT / "data" / "blocus" / "datos" / "primeros_50_blocus_20261026" / "fechas_consulta_por_id.json"
PERMANENT_REASONS = {
    "profile_status_10222", "profile_status_10221", "profile_status_10202",
    "profile_status_10223", "uid_mismatch", "createTime_missing_or_invalid",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def select_candidates(cache: dict) -> list[dict]:
    old = json.loads(OLD_CACHE.read_text(encoding="utf-8")) if OLD_CACHE.exists() else {}
    degrees = {r["user_id"]: int(r["seguidos_observados_grafo"] or 0) for r in read_csv(GRAPH)}
    selected = []
    for row in read_csv(USERS):
        uid, username = row["user_id"].strip(), row["usuario"].strip().lstrip("@")
        if row["fecha_creacion_perfil_utc"] or not uid or not username or uid in cache:
            continue
        if old.get(uid, {}).get("reason") in PERMANENT_REASONS:
            continue
        selected.append({
            "user_id": uid, "username": username,
            "comentarios": int(row["comentarios_observados"] or 0),
            "objetivos_seguidos": degrees.get(uid, 0),
            "en_grafo_relaciones": row["en_grafo_relaciones"],
        })
    return sorted(selected, key=lambda x: (-x["comentarios"], -x["objetivos_seguidos"], x["user_id"]))


def save(cache: dict, target_successes: int, candidates_remaining: int, status: str, reason=""):
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(CACHE, cache)
    counts = Counter(v["status"] for v in cache.values())
    atomic_json(STATE, {
        "status": status, "updated_at_utc": utcnow(), "target_new_confirmed": target_successes,
        "attempted": len(cache), "new_confirmed": counts["available"],
        "candidate_pool_remaining": candidates_remaining, "results": dict(counts),
        "stop_reason": reason,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-successes", type=int, default=1000)
    parser.add_argument("--max-attempts", type=int, default=1600)
    args = parser.parse_args()
    if args.target_successes <= 0 or args.max_attempts <= 0:
        parser.error("Los límites deben ser positivos")
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    candidates = select_candidates(cache)
    successes = sum(row.get("status") == "available" for row in cache.values())
    print(f"Confirmadas nuevas: {successes}/{args.target_successes}; "
          f"candidatas pendientes: {len(candidates)}; intentos previos: {len(cache)}", flush=True)
    if successes >= args.target_successes:
        save(cache, args.target_successes, len(candidates), "finished")
        return
    remaining_attempts = max(0, args.max_attempts - len(cache))
    if remaining_attempts == 0:
        save(cache, args.target_successes, len(candidates), "attempt_limit")
        return
    save(cache, args.target_successes, len(candidates), "running")
    client = TikTokClient(SimpleNamespace(sesion="anonima", cookies=None, cancel_file=None))
    consecutive_unavailable = 0
    try:
        for i, account in enumerate(candidates[:remaining_attempts], 1):
            uid, username = account["user_id"], account["username"]
            result = {
                "requested_user_id": uid, "requested_username": username,
                "source_url": f"https://www.tiktok.com/@{username}",
                "observed_at_utc": utcnow(), "status": "unavailable", "reason": "",
                "comentarios_observados": account["comentarios"],
                "objetivos_seguidos": account["objetivos_seguidos"],
            }
            halt = False
            try:
                profile = client.profile(username)
                if str(profile["user_id"]) != uid:
                    result["reason"] = "uid_mismatch"
                elif not profile.get("created_at"):
                    result["reason"] = "createTime_missing_or_invalid"
                else:
                    result.update({
                        "status": "available", "returned_username": profile["username"],
                        "fecha_creacion_perfil_utc": profile["created_at"],
                        "createTime": profile["creation_time"],
                        "source_field": "webapp.user-detail.userInfo.user.createTime",
                    })
                    successes += 1
            except FetchError as exc:
                result["reason"] = exc.reason
                halt = exc.halt_batch
            cache[uid] = result
            if result["status"] == "unavailable" and result["reason"] in ("profile_status_209002", "profile_not_available"):
                consecutive_unavailable += 1
            else:
                consecutive_unavailable = 0
            stop_reason = result["reason"] if halt else ""
            if consecutive_unavailable >= 15:
                stop_reason = "15_consecutive_profile_unavailable"
            if i % 10 == 0 or successes >= args.target_successes or halt or stop_reason:
                status = "finished" if successes >= args.target_successes else "source_unavailable" if stop_reason else "running"
                save(cache, args.target_successes, len(candidates) - i, status, stop_reason)
                print(f"Intentos {len(cache)}/{args.max_attempts}; nuevas confirmadas "
                      f"{successes}/{args.target_successes}; último: {result['status']} "
                      f"{result['reason']}", flush=True)
            if successes >= args.target_successes or halt or stop_reason:
                return
        save(cache, args.target_successes, max(0, len(candidates)-remaining_attempts),
             "attempt_limit" if len(cache) >= args.max_attempts else "candidate_pool_exhausted")
    except KeyboardInterrupt:
        save(cache, args.target_successes, len(candidates), "interrupted")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    main()
