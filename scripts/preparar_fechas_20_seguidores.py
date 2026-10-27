"""Prepara por ID exacto las fechas del XLSX de veinte seguidores observados."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs" / "grafo_blocus_20261025" / "orden_devuelto_seguidores.csv"
DEST = ROOT / "outputs" / "edicion_fechas_20_20261027" / "fechas_20.json"


def main() -> None:
    grouped = defaultdict(list)
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            grouped[row["objetivo"]].append(row)
    result = {}
    for account, rows in grouped.items():
        selected = sorted(rows, key=lambda row: int(row["posicion_respuesta"]), reverse=True)[:20]
        result[account] = [{"esperado": "@" + row["username"] if row["username"]
                            else "uid:" + row["user_id"],
                            "user_id": row["user_id"],
                            "fecha_perfil": row["fecha_creacion_perfil_utc"],
                            "fecha_uid_estimada": row["fecha_uid_estimada_utc"]}
                           for row in selected]
    DEST.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(f"cuentas_con_filas={len(result)}; seguidores={sum(map(len, result.values()))}")


if __name__ == "__main__":
    main()
