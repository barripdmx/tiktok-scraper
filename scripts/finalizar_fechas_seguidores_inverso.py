"""Publica la tanda priorizada de followers y actualiza la tabla y el XLSX."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.crear_tabla_fechas_usuarios import main as rebuild_users
from scripts.exportar_gemini_argon import main as rebuild_workbook


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "fechas_seguidores_orden_inverso_20261027"
CACHE = OUT / "consultas_por_id.json"
CSV = OUT / "fechas_confirmadas_orden_inverso.csv"
FIELDS = ["user_id", "username_consultado", "username_devuelto", "objetivo",
          "puesto_desde_final_captura", "posicion_respuesta", "total_capturado_objetivo",
          "pagina", "fecha_creacion_perfil_utc", "campo_fuente", "url_perfil",
          "fecha_consulta_utc", "evidencia", "nota_orden"]


def main():
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    rows = []
    for uid, item in cache.items():
        if item.get("status") != "available" or item.get("requested_user_id") != uid:
            continue
        rows.append({
            "user_id": uid, "username_consultado": item["requested_username"],
            "username_devuelto": item.get("returned_username", ""),
            "objetivo": item["objetivo"],
            "puesto_desde_final_captura": item["puesto_desde_final_captura"],
            "posicion_respuesta": item["posicion_respuesta"],
            "total_capturado_objetivo": item["total_capturado_objetivo"],
            "pagina": item["pagina"],
            "fecha_creacion_perfil_utc": item["fecha_creacion_perfil_utc"],
            "campo_fuente": item["source_field"],
            "url_perfil": item["source_url"],
            "fecha_consulta_utc": item["observed_at_utc"],
            "evidencia": item["evidencia"],
            "nota_orden": "Orden inverso de la respuesta web; antigüedad de seguimiento no confirmada",
        })
    rows.sort(key=lambda row: (row["puesto_desde_final_captura"], row["objetivo"], row["user_id"]))
    with CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Nuevas fechas confirmadas: {len(rows)}; CSV: {CSV}", flush=True)
    rebuild_users()
    rebuild_workbook()


if __name__ == "__main__":
    main()
