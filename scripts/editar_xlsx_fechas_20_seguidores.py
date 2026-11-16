"""Sustituye los @followers del XLSX por sus fechas de creación disponibles."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "blocus" / "datos" / "lote_blocus_20261025T195208Z" / "cuentas_analizadas_20_seguidores_mas_antiguos_observados.xlsx"
FOLDER = ROOT / "data" / "blocus" / "datos" / "edicion_fechas_20_20261027"
DEST = FOLDER / "fechas_20_actualizado.xlsx"
MAP = FOLDER / "fechas_20.json"


def main() -> None:
    original_sha256 = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    mapping = json.loads(MAP.read_text(encoding="utf-8"))
    workbook = load_workbook(SOURCE)
    if len(workbook.worksheets) != 1:
        raise ValueError("Se esperaba una sola hoja")
    sheet = workbook.active
    if (sheet.max_row, sheet.max_column, sheet["A1"].value) != (55, 21, "cuenta_analizada"):
        raise ValueError("La matriz ya no coincide con las 54 cuentas y 20 seguidores")
    counts = {"confirmadas": 0, "estimadas": 0, "sin_fecha": 0, "vacias": 0}
    for rank in range(1, 21):
        sheet.cell(1, rank + 1).value = f"creacion_{rank:02d}_utc"
    for row_number in range(2, 56):
        account = sheet.cell(row_number, 1).value
        selected = mapping.get(account, [])
        for rank in range(1, 21):
            cell = sheet.cell(row_number, rank + 1)
            member = selected[rank - 1] if rank <= len(selected) else None
            if member is None:
                if cell.value not in (None, ""):
                    raise ValueError(f"@{account}: seguidor inesperado en puesto {rank}")
                counts["vacias"] += 1
                continue
            if cell.value != member["esperado"]:
                raise ValueError(f"@{account}: identidad distinta en puesto {rank}: {cell.value}")
            if member["fecha_perfil"]:
                moment = datetime.fromisoformat(member["fecha_perfil"].replace("Z", "+00:00"))
                cell.value = moment.astimezone(timezone.utc).replace(tzinfo=None)
                cell.number_format = "yyyy-mm-dd hh:mm"
                counts["confirmadas"] += 1
            elif member["fecha_uid_estimada"]:
                cell.value = "≈" + member["fecha_uid_estimada"][:16].replace("T", " ")
                counts["estimadas"] += 1
            else:
                cell.value = "sin fecha"
                counts["sin_fecha"] += 1
    if counts != {"confirmadas": 717, "estimadas": 199, "sin_fecha": 1, "vacias": 163}:
        raise ValueError(f"Recuento inesperado: {counts}")
    workbook.save(DEST)
    print(json.dumps({"destino_temporal": str(DEST), "origen_sha256": original_sha256,
                      **counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
