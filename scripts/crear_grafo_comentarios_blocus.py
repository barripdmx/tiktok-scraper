"""Exporta para Gephi un grafo de cuentas e interacciones observadas.

Uso: python scripts/crear_grafo_comentarios_blocus.py
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "blocus" / "datos" / "comentarios_blocus_20261026"
DEST = ROOT / "data" / "blocus" / "datos" / "grafo_comentarios_blocus_20261026"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_account_ids(path: Path) -> dict[str, str]:
    """Relaciona las cuentas del lote con sus ID estables ya descargados."""
    ids: dict[str, str] = {}
    for row in read_csv(path):
        user_id = row["user_id"].strip()
        for value in (row["username"], row["objetivo"], *row["aliases"].split(", ")):
            name = value.strip().lower().lstrip("@")
            if name and user_id:
                if name in ids and ids[name] != user_id:
                    raise ValueError(f"Alias ambiguo en el grafo de relaciones: {name}")
                ids[name] = user_id
    return ids


def build_graph(
    accounts: list[dict[str, str]], comments: list[dict[str, str]], account_ids: dict[str, str]
) -> tuple[nx.DiGraph, dict]:
    graph = nx.DiGraph()
    author_accounts: dict[str, set[str]] = defaultdict(set)
    author_posts: dict[str, set[str]] = defaultdict(set)
    author_comments: Counter[str] = Counter()
    author_latest: dict[str, str] = {}
    author_handles: dict[str, str] = {}
    account_stats = {row["cuenta"].strip().lower().lstrip("@"): row for row in accounts}
    account_nodes: dict[str, str] = {}

    for row in accounts:
        account = row["cuenta"].strip().lower().lstrip("@")
        user_id = account_ids.get(account, "")
        if not user_id:
            raise ValueError(f"Sin ID estable para la cuenta analizada: {account}")
        node = f"uid:{user_id}"
        account_nodes[account] = node
        graph.add_node(
            node, tipo="cuenta", label=f"@{account}", user_id=user_id,
            handle=account, es_cuenta_analizada=True, cuenta=account,
            publicaciones_observadas=int(row["publicaciones_observadas"] or 0),
            publicaciones_parciales=int(row["publicaciones_parciales"] or 0),
            perfil_disponible=row["perfil_disponible"],
        )

    comments_by_id: dict[str, dict[str, str]] = {}
    for row in comments:
        comment_id = row["comment_id"].strip()
        if not comment_id or comment_id in comments_by_id:
            raise ValueError(f"ID de comentario vacío o duplicado: {comment_id!r}")
        comments_by_id[comment_id] = row
        account = row["cuenta_publicadora"].strip().lower().lstrip("@")
        if account not in account_stats:
            raise ValueError(f"Cuenta ajena al lote: {account}")
        author_id = row["autor_id"].strip()
        if not author_id:
            raise ValueError(f"Sin ID estable de autor: comentario {comment_id}")
        author = f"uid:{author_id}"
        handle = row["autor_handle"].strip().lstrip("@")
        created = row["creado_utc"].strip()
        if created >= author_latest.get(author, ""):
            author_latest[author] = created
            author_handles[author] = handle
        author_accounts[author].add(account)
        author_posts[author].add(row["publication_id"])
        author_comments[author] += 1
        if author not in graph:
            graph.add_node(author, tipo="cuenta", label=f"@{handle}" if handle else author_id,
                           user_id=author_id, handle=handle, es_cuenta_analizada=False)

    for author in author_accounts:
        graph.nodes[author].update(
            label=(graph.nodes[author]["label"] if graph.nodes[author]["es_cuenta_analizada"]
                   else f"@{author_handles[author]}" if author_handles[author]
                   else author.removeprefix("uid:")),
            handle=(graph.nodes[author]["handle"] if graph.nodes[author]["es_cuenta_analizada"]
                    else author_handles[author]),
            cuentas_distintas=len(author_accounts[author]),
            publicaciones_distintas=len(author_posts[author]),
            comentarios=author_comments[author],
            cuentas_comentadas=", ".join(sorted(author_accounts[author])),
        )

    replies = 0
    for row in comments:
        source = f"uid:{row['autor_id'].strip()}"
        parent = row["parent_comment_id"].strip()
        if parent:
            if parent not in comments_by_id:
                raise ValueError(f"Respuesta con padre no capturado: {row['comment_id']} → {parent}")
            parent_row = comments_by_id[parent]
            if parent_row["publication_id"] != row["publication_id"]:
                raise ValueError(f"Respuesta de otra publicación: {row['comment_id']} → {parent}")
            target = f"uid:{parent_row['autor_id'].strip()}"
            field = "respuestas"
            replies += 1
        else:
            account = row["cuenta_publicadora"].strip().lower().lstrip("@")
            target = account_nodes[account]
            field = "comentarios_principales"
        if not graph.has_edge(source, target):
            graph.add_edge(source, target, comentarios_principales=0, respuestas=0,
                           interacciones=0, weight=0)
        graph[source][target][field] += 1
        graph[source][target]["interacciones"] += 1
        graph[source][target]["weight"] += 1

    for _, _, attrs in graph.edges(data=True):
        attrs["tipo"] = ("mixta" if attrs["comentarios_principales"] and attrs["respuestas"]
                         else "comentario_principal" if attrs["comentarios_principales"]
                         else "respuesta")

    summary = {
        "cuentas_lote": len(accounts),
        "cuentas_con_comentarios": len({r["cuenta_publicadora"] for r in comments}),
        "comentarios": len(comments),
        "comentarios_principales": len(comments) - replies,
        "respuestas": replies,
        "autores_distintos": len(author_accounts),
        "autores_en_varias_cuentas": sum(len(v) > 1 for v in author_accounts.values()),
        "autores_en_varias_publicaciones": sum(len(v) > 1 for v in author_posts.values()),
        "nodos": graph.number_of_nodes(),
        "aristas": graph.number_of_edges(),
        "bucles_misma_cuenta": nx.number_of_selfloops(graph),
        "publicaciones_parciales": sum(int(r["publicaciones_parciales"] or 0) for r in accounts),
        "nota_cobertura": "Solo comentarios públicos capturados; "
                         f"{sum(int(r['publicaciones_parciales'] or 0) for r in accounts)} "
                         "publicaciones tienen cobertura parcial.",
    }
    return graph, summary


def export_graph(graph: nx.DiGraph, summary: dict) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    nx.write_gexf(graph, DEST / "grafo_comentarios_completo.gexf")
    node_fields = ["id", "tipo", "label", "user_id", "handle", "es_cuenta_analizada",
                   "cuenta", "cuentas_distintas", "publicaciones_distintas",
                   "comentarios", "cuentas_comentadas", "publicaciones_observadas",
                   "publicaciones_parciales", "perfil_disponible"]
    edge_fields = ["origen", "destino", "tipo", "comentarios_principales",
                   "respuestas", "interacciones", "weight"]
    write_csv(DEST / "nodos.csv", [{"id": node, **attrs} for node, attrs in graph.nodes(data=True)], node_fields)
    write_csv(DEST / "aristas.csv", [dict(origen=a, destino=b, **attrs) for a, b, attrs in graph.edges(data=True)], edge_fields)
    shared = []
    for node, attrs in graph.nodes(data=True):
        if attrs.get("cuentas_distintas", 0) > 1:
            shared.append({"autor_id": attrs["user_id"], "autor_handle": attrs["handle"],
                           "cuentas_distintas": attrs["cuentas_distintas"],
                           "comentarios": attrs["comentarios"],
                           "cuentas": attrs["cuentas_comentadas"]})
    shared.sort(key=lambda r: (-r["cuentas_distintas"], -r["comentarios"], r["autor_handle"]))
    write_csv(DEST / "autores_en_varias_cuentas.csv", shared,
              ["autor_id", "autor_handle", "cuentas_distintas", "comentarios", "cuentas"])
    (DEST / "resumen.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def export_viewer(accounts: list[dict[str, str]], comments: list[dict[str, str]], summary: dict) -> None:
    payload = {
        "accounts": [r["cuenta"] for r in accounts],
        "comments": [{"id": r["comment_id"], "parent": r["parent_comment_id"],
                      "account": r["cuenta_publicadora"], "post": r["publication_id"],
                      "url": r["publication_url"], "author": r["autor_id"],
                      "handle": r["autor_handle"], "text": r["texto"],
                      "date": r["creado_utc"], "likes": r["likes"]} for r in comments],
        "summary": summary,
    }
    template = (Path(__file__).with_name("plantilla_grafo_comentarios.html")).read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    (DEST / "grafo_interactivo.html").write_text(template.replace("/*__DATA__*/", data), encoding="utf-8")


def main() -> None:
    accounts = read_csv(SOURCE / "estado_cuentas.csv")
    comments = read_csv(SOURCE / "comentarios.csv")
    account_ids = read_account_ids(ROOT / "data" / "blocus" / "datos" / "grafo_blocus_20261025" / "cuentas.csv")
    graph, summary = build_graph(accounts, comments, account_ids)
    export_graph(graph, summary)
    export_viewer(accounts, comments, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(DEST)


if __name__ == "__main__":
    main()
