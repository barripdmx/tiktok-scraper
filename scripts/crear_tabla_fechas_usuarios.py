"""Unifica usuarios observados y ordena las fechas verificadas/estimadas.

La fecha declarada por el perfil prevalece. Para el resto, UID >> 32 es una
estimación técnica, nunca una fecha de creación verificada.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "blocus" / "datos" / "usuarios_fecha_creacion"
PROFILE_CACHES = (
    ROOT / "data" / "blocus" / "datos" / "fechas_perfiles_ampliacion_20261027" / "consultas_por_id.json",
    ROOT / "data" / "blocus" / "datos" / "fechas_seguidores_orden_inverso_20261027" / "consultas_por_id.json",
)
FIELDS = ["fecha_orden_utc", "tipo_fecha", "usuario", "user_id",
          "fecha_creacion_perfil_utc", "fecha_uid_estimada_utc",
          "en_grafo_relaciones", "en_grafo_comentarios", "comentarios_observados",
          "fuente_fecha_perfil"]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def estimate(uid: str) -> str:
    try:
        value = datetime.fromtimestamp(int(uid) >> 32, timezone.utc)
        if datetime(2014, 1, 1, tzinfo=timezone.utc) <= value <= datetime.now(timezone.utc):
            return value.isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    return ""


def build(accounts: list[dict[str, str]], comments: list[dict[str, str]]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for row in accounts:
        uid = row["user_id"].strip()
        if not uid or uid in by_id:
            raise ValueError(f"ID ausente o duplicado en cuentas: {uid!r}")
        by_id[uid] = {
            "usuario": row["username"].strip().lstrip("@"), "user_id": uid,
            "fecha_creacion_perfil_utc": row["fecha_creacion_perfil_utc"].strip(),
            "fecha_uid_estimada_utc": row["fecha_uid_estimada_utc"].strip(),
            "en_grafo_relaciones": "Sí", "en_grafo_comentarios": "No",
            "comentarios_observados": 0,
            "fuente_fecha_perfil": row["fuente_fecha_perfil"].strip(),
        }
    latest_handle: dict[str, tuple[str, str]] = {}
    counts: Counter[str] = Counter()
    for row in comments:
        uid = row["autor_id"].strip()
        if not uid:
            continue
        counts[uid] += 1
        created = row["creado_utc"].strip()
        if created >= latest_handle.get(uid, ("", ""))[0]:
            latest_handle[uid] = (created, row["autor_handle"].strip().lstrip("@"))
    for uid, count in counts.items():
        if uid not in by_id:
            by_id[uid] = {
                "usuario": latest_handle[uid][1], "user_id": uid,
                "fecha_creacion_perfil_utc": "",
                "fecha_uid_estimada_utc": estimate(uid),
                "en_grafo_relaciones": "No", "en_grafo_comentarios": "Sí",
                "comentarios_observados": count, "fuente_fecha_perfil": "",
            }
        else:
            by_id[uid]["en_grafo_comentarios"] = "Sí"
            by_id[uid]["comentarios_observados"] = count
            if not by_id[uid]["usuario"]:
                by_id[uid]["usuario"] = latest_handle[uid][1]
    for row in by_id.values():
        verified = row["fecha_creacion_perfil_utc"]
        estimated = row["fecha_uid_estimada_utc"]
        row["fecha_orden_utc"] = verified or estimated
        row["tipo_fecha"] = "Confirmada por perfil" if verified else "Estimada por UID" if estimated else "Sin fecha"
    return sorted(by_id.values(), key=lambda row: (
        not bool(row["fecha_orden_utc"]), row["fecha_orden_utc"], row["user_id"]))


def apply_new_profile_dates(table: list[dict]) -> int:
    """Añade fechas contrastadas por UID sin modificar las capturas originales."""
    by_id = {row["user_id"]: row for row in table}
    added = 0
    for path in PROFILE_CACHES:
        if not path.exists():
            continue
        cache = json.loads(path.read_text(encoding="utf-8"))
        for uid, evidence in cache.items():
            if evidence.get("status") != "available" or uid not in by_id:
                continue
            if evidence.get("requested_user_id") != uid or not evidence.get("fecha_creacion_perfil_utc"):
                continue
            row = by_id[uid]
            if not row["fecha_creacion_perfil_utc"]:
                added += 1
            row["fecha_creacion_perfil_utc"] = evidence["fecha_creacion_perfil_utc"]
            row["fuente_fecha_perfil"] = evidence["source_url"] + " · user.createTime"
            row["fecha_orden_utc"] = evidence["fecha_creacion_perfil_utc"]
            row["tipo_fecha"] = "Confirmada por perfil"
    table.sort(key=lambda row: (not bool(row["fecha_orden_utc"]), row["fecha_orden_utc"], row["user_id"]))
    return added


def main() -> None:
    accounts = rows(ROOT / "data" / "blocus" / "datos" / "grafo_blocus_20261025" / "cuentas.csv")
    comments = rows(ROOT / "data" / "blocus" / "datos" / "comentarios_blocus_20261026" / "comentarios.csv")
    table = build(accounts, comments)
    added = apply_new_profile_dates(table)
    DEST.mkdir(parents=True, exist_ok=True)
    with (DEST / "usuarios_por_fecha_creacion.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(table)
    summary = {"usuarios": len(table), "nuevas_confirmadas_por_perfil": added,
               "tipos_fecha": dict(Counter(row["tipo_fecha"] for row in table)),
               "en_ambos_grafos": sum(row["en_grafo_relaciones"] == "Sí" and
                                      row["en_grafo_comentarios"] == "Sí" for row in table),
               "orden": "Fecha de creación confirmada o estimada, UTC, de antigua a reciente; sin fecha al final",
               "nota": "Las fechas UID >> 32 son estimaciones técnicas y no prueban la creación de la cuenta."}
    (DEST / "resumen_fechas_usuarios.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
