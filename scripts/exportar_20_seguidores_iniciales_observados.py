"""Exporta una matriz cuenta × veinte seguidores antiguos observados.

La prueba con @jbarri respalda que la respuesta web va de reciente a antiguo,
pero estos registros no certifican los primeros seguidores históricos.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "blocus" / "datos" / "grafo_blocus_20261025"
DEST = ROOT / "data" / "blocus" / "datos" / "lote_blocus_20261025T195208Z" / "cuentas_analizadas_20_seguidores_mas_antiguos_observados.csv"
FIELDS = ["cuenta_analizada", *(f"seguidor_{rank:02d}" for rank in range(1, 21))]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_rows(coverage: list[dict[str, str]], followers: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in followers:
        grouped[row["objetivo"]].append(row)
    result = []
    for state in coverage:
        if state["lista"] != "seguidores":
            continue
        account = state["username"]
        observed = sorted(grouped.get(account, []), key=lambda row: int(row["posicion_respuesta"]), reverse=True)
        if len(observed) != int(state["cuentas"] or 0):
            raise ValueError(f"Filas de seguidores incoherentes para @{account}")
        row = {"cuenta_analizada": account}
        for rank, follower in enumerate(observed[:20], 1):
            row[f"seguidor_{rank:02d}"] = ("@" + follower["username"] if follower["username"]
                                           else "uid:" + follower["user_id"])
        result.append(row)
    return result


def main() -> None:
    coverage = read_csv(SOURCE / "cobertura.csv")
    followers = read_csv(SOURCE / "orden_devuelto_seguidores.csv")
    result = build_rows(coverage, followers)
    with DEST.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(result)
    print(f"{DEST}\ncuentas={len(result)}; "
          f"seguidores={sum(bool(row.get(field)) for row in result for field in FIELDS[1:])}")


if __name__ == "__main__":
    main()
