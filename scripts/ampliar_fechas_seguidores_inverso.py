"""Consulta fechas de perfiles priorizando el final de cada lista de seguidores.

El orden inverso de la respuesta web es una hipótesis de antigüedad, no una
fecha de seguimiento ni una cronología confirmada. Intercala los objetivos:
primero el último registro de cada lista, luego el penúltimo de cada una, etc.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.scrapers.tiktok_descargar_relaciones import FetchError, TikTokClient
from src.utils.tiktok_relaciones import atomic_json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "fechas_seguidores_orden_inverso_20261027"
CACHE = OUT / "consultas_por_id.json"
STATE = OUT / "estado.json"
QUEUE = OUT / "cola_prioridad.csv"
ORDER = ROOT / "outputs" / "grafo_blocus_20261025" / "orden_devuelto_seguidores.csv"
MASTER = ROOT / "outputs" / "01a173e7-58a9-7d53-a645-746d1a51b712" / "usuarios_por_fecha_creacion.csv"
PREVIOUS_CACHES = (
    ROOT / "outputs" / "primeros_50_blocus_20261026" / "fechas_consulta_por_id.json",
    ROOT / "outputs" / "fechas_perfiles_ampliacion_20261027" / "consultas_por_id.json",
)
QUEUE_FIELDS = ["prioridad", "user_id", "username", "objetivo", "puesto_desde_final_captura",
                "posicion_respuesta", "total_capturado_objetivo", "pagina", "evidencia"]


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        yield from csv.DictReader(stream)


def select_candidates(cache):
    confirmed = {r["user_id"] for r in csv_rows(MASTER) if r["fecha_creacion_perfil_utc"]}
    attempted = set(cache)
    for path in PREVIOUS_CACHES:
        if path.exists():
            attempted.update(json.loads(path.read_text(encoding="utf-8")))
    lists = defaultdict(list)
    for row in csv_rows(ORDER):
        lists[row["objetivo"]].append(row)
    ranked = []
    for target, rows in lists.items():
        ordered = sorted(rows, key=lambda r: int(r["posicion_respuesta"]), reverse=True)
        for distance, row in enumerate(ordered, 1):
            ranked.append((distance, target, row, len(ordered)))
    ranked.sort(key=lambda part: (part[0], part[1]))
    queue = []
    seen = set()
    for distance, target, row, total in ranked:
        uid = row["user_id"].strip()
        handle = row["username"].strip().lstrip("@")
        if not uid or not handle or uid in confirmed or uid in attempted or uid in seen:
            continue
        seen.add(uid)
        queue.append({
            "prioridad": len(queue) + 1, "user_id": uid, "username": handle,
            "objetivo": target, "puesto_desde_final_captura": distance,
            "posicion_respuesta": int(row["posicion_respuesta"]),
            "total_capturado_objetivo": total, "pagina": int(row["pagina"]),
            "evidencia": row["evidencia"],
        })
    return queue, len(lists)


def save(cache, target_successes, candidates_remaining, status, reason=""):
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(CACHE, cache)
    counts = Counter(row["status"] for row in cache.values())
    atomic_json(STATE, {
        "status": status, "updated_at_utc": utcnow(), "target_new_confirmed": target_successes,
        "attempted": len(cache), "new_confirmed": counts["available"],
        "candidate_pool_remaining": candidates_remaining,
        "results": dict(counts), "stop_reason": reason,
        "selection_rule": "ultimo registro de cada objetivo, penultimo, etc.; orden de llegada no confirmado",
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-successes", type=int, default=1000)
    parser.add_argument("--max-attempts", type=int, default=1600)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    if args.target_successes <= 0 or args.max_attempts <= 0:
        parser.error("Los límites deben ser positivos")
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    queue, objectives = select_candidates(cache)
    OUT.mkdir(parents=True, exist_ok=True)
    if not QUEUE.exists():
        with QUEUE.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=QUEUE_FIELDS)
            writer.writeheader()
            writer.writerows(queue)
    successes = sum(row.get("status") == "available" for row in cache.values())
    print(f"Objetivos con seguidores capturados: {objectives}; candidatos no consultados: {len(queue)}; "
          f"nuevas confirmadas: {successes}/{args.target_successes}; intentos previos: {len(cache)}", flush=True)
    if queue:
        print("Primeras prioridades:", [(r["objetivo"], r["puesto_desde_final_captura"], r["username"]) for r in queue[:8]], flush=True)
    if args.preview:
        return
    if successes >= args.target_successes:
        save(cache, args.target_successes, len(queue), "finished")
        return
    remaining_attempts = max(0, args.max_attempts - len(cache))
    if not remaining_attempts:
        save(cache, args.target_successes, len(queue), "attempt_limit")
        return
    save(cache, args.target_successes, len(queue), "running")
    client = TikTokClient(SimpleNamespace(sesion="anonima", cookies=None, cancel_file=None))
    consecutive_unavailable = 0
    try:
        for i, account in enumerate(queue[:remaining_attempts], 1):
            uid, handle = account["user_id"], account["username"]
            result = {
                "requested_user_id": uid, "requested_username": handle,
                "source_url": f"https://www.tiktok.com/@{handle}",
                "observed_at_utc": utcnow(), "status": "unavailable", "reason": "",
                "objetivo": account["objetivo"],
                "puesto_desde_final_captura": account["puesto_desde_final_captura"],
                "posicion_respuesta": account["posicion_respuesta"],
                "total_capturado_objetivo": account["total_capturado_objetivo"],
                "pagina": account["pagina"], "evidencia": account["evidencia"],
            }
            halt = False
            try:
                profile = client.profile(handle)
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
            if i % 10 == 0 or successes >= args.target_successes or stop_reason:
                status = "finished" if successes >= args.target_successes else "source_unavailable" if stop_reason else "running"
                save(cache, args.target_successes, len(queue) - i, status, stop_reason)
                print(f"Intentos {len(cache)}/{args.max_attempts}; nuevas confirmadas "
                      f"{successes}/{args.target_successes}; último: {result['status']} "
                      f"{result['reason']}", flush=True)
            if successes >= args.target_successes or stop_reason:
                return
        save(cache, args.target_successes, max(0, len(queue)-remaining_attempts),
             "attempt_limit" if len(cache) >= args.max_attempts else "candidate_pool_exhausted")
    except KeyboardInterrupt:
        save(cache, args.target_successes, len(queue), "interrupted")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    main()
