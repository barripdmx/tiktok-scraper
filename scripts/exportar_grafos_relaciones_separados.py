"""Genera GEXF independientes de seguidores y seguidos ya observados.

Una arista A → B significa que A sigue a B. La procedencia de la captura
determina en cuál de los dos archivos aparece; una relación confirmada por
ambas listas aparece en los dos.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import networkx as nx


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "blocus" / "datos" / "grafo_blocus_20261025"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def split_graphs(nodes: list[dict[str, str]], relations: list[dict[str, str]]) -> dict[str, nx.DiGraph]:
    by_id = {row["node_id"]: row for row in nodes}
    objectives = {row["node_id"] for row in nodes if row["objetivo"].strip()}
    result = {name: nx.DiGraph() for name in ("seguidores", "seguidos")}

    for relation in relations:
        captures = relation["capturas"].split("|")
        for name in result:
            selected = [capture for capture in captures if f":{name}:" in capture]
            if not selected:
                continue
            graph = result[name]
            source, target = relation["source"], relation["target"]
            for node_id in (source, target):
                if node_id not in by_id:
                    raise ValueError(f"Falta el nodo {node_id} de la relación")
                if node_id not in graph:
                    row = by_id[node_id]
                    attrs = {key: value for key, value in row.items() if key != "node_id"}
                    attrs["tipo"] = "cuenta"
                    attrs["label"] = f"@{row['username']}" if row["username"] else node_id
                    graph.add_node(node_id, **attrs)
            graph.add_edge(source, target, relation="follows", capturas="|".join(selected),
                           primera_observacion_utc=relation["primera_observacion_utc"],
                           ultima_observacion_utc=relation["ultima_observacion_utc"])

    for graph in result.values():
        for node_id in objectives - set(graph):
            row = by_id[node_id]
            attrs = {key: value for key, value in row.items() if key != "node_id"}
            attrs["tipo"] = "cuenta"
            attrs["label"] = f"@{row['username']}" if row["username"] else node_id
            graph.add_node(node_id, **attrs)
    return result


def main() -> None:
    nodes = read_csv(DEST / "cuentas.csv")
    relations = read_csv(DEST / "relaciones.csv")
    graphs = split_graphs(nodes, relations)
    summary = {}
    for name, graph in graphs.items():
        path = DEST / f"grafo_{name}.gexf"
        nx.write_gexf(graph, path)
        summary[name] = {"archivo": path.name, "cuentas": graph.number_of_nodes(),
                         "relaciones": graph.number_of_edges(),
                         "objetivos_incluidos": sum(bool(attrs["objetivo"])
                                                   for _, attrs in graph.nodes(data=True))}
    summary["nota"] = ("A → B significa que A sigue a B. Seguidores y seguidos se separan "
                       "por la lista en la que se observó la relación; las observadas en ambas "
                       "aparecen en los dos archivos. Cada archivo incluye los 54 objetivos, "
                       "incluso si no tienen aristas observadas en esa lista.")
    (DEST / "resumen_grafos_separados.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
