"""Contratos esenciales del grafo de comentarios."""

from scripts.crear_grafo_comentarios_blocus import build_graph


def test_respuestas_y_autor_compartido_entre_cuentas():
    accounts = [
        {"cuenta": name, "publicaciones_observadas": "1", "publicaciones_parciales": "0",
         "perfil_disponible": "True"}
        for name in ("cuenta_a", "cuenta_b", "sin_comentarios")
    ]

    def comment(comment_id, account, author, parent=""):
        return {
            "comment_id": comment_id, "cuenta_publicadora": account,
            "autor_id": author, "autor_handle": author,
            "texto": "Texto de prueba", "creado_utc": "2026-10-26T10:00:00Z",
            "publication_id": "post_" + account,
            "publication_url": "https://www.tiktok.com/@" + account + "/video/123",
            "parent_comment_id": parent, "is_reply": "1" if parent else "0", "likes": "0",
        }

    comments = [
        comment("c1", "cuenta_a", "101"),
        comment("c2", "cuenta_a", "202", "c1"),
        comment("c3", "cuenta_b", "101"),
    ]
    graph, summary = build_graph(accounts, comments,
                                 {"cuenta_a": "101", "cuenta_b": "102", "sin_comentarios": "103"})

    assert set(graph) == {"uid:101", "uid:102", "uid:103", "uid:202"}
    assert graph["uid:101"]["uid:101"]["comentarios_principales"] == 1
    assert graph["uid:202"]["uid:101"]["respuestas"] == 1
    assert graph["uid:101"]["uid:102"]["comentarios_principales"] == 1
    assert graph.nodes["uid:101"]["cuentas_distintas"] == 2
    assert "uid:103" in graph
    assert all(attrs["tipo"] == "cuenta" and "texto" not in attrs
               for _, attrs in graph.nodes(data=True))
    assert all("texto" not in attrs for _, _, attrs in graph.edges(data=True))
    assert summary["respuestas"] == 1
    assert summary["autores_en_varias_cuentas"] == 1
