"""Publica las fechas contrastadas y actualiza tabla maestra y XLSX de Gemini."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.crear_tabla_fechas_usuarios import main as rebuild_users
from scripts.exportar_gemini_argon import main as rebuild_workbook


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "fechas_perfiles_ampliacion_20261027"
CACHE = OUT / "consultas_por_id.json"
CSV = OUT / "fechas_confirmadas_nuevas.csv"
FIELDS = ["user_id", "username_consultado", "username_devuelto", "fecha_creacion_perfil_utc",
          "campo_fuente", "url_perfil", "fecha_consulta_utc", "comentarios_observados", "objetivos_seguidos"]


def main():
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    confirmed = []
    for uid, row in raw.items():
        if row.get("status") != "available" or row.get("requested_user_id") != uid:
            continue
        confirmed.append({
            "user_id": uid, "username_consultado": row["requested_username"],
            "username_devuelto": row.get("returned_username", ""),
            "fecha_creacion_perfil_utc": row["fecha_creacion_perfil_utc"],
            "campo_fuente": row["source_field"], "url_perfil": row["source_url"],
            "fecha_consulta_utc": row["observed_at_utc"],
            "comentarios_observados": row["comentarios_observados"],
            "objetivos_seguidos": row["objetivos_seguidos"],
        })
    confirmed.sort(key=lambda r: (r["fecha_creacion_perfil_utc"], r["user_id"]))
    with CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(confirmed)
    print(f"Fechas nuevas confirmadas: {len(confirmed)}; CSV: {CSV}", flush=True)
    rebuild_users()
    rebuild_workbook()


if __name__ == "__main__":
    main()
