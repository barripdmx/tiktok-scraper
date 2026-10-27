"""Regresión: TikTok puede señalar fin antes de entregar todas las respuestas."""

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/descargar_comentarios_http_blocus.py"
spec = importlib.util.spec_from_file_location("blocus_comments", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Response:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


class Client:
    def __init__(self):
        self.cursors = []

    def _get(self, path, params):
        self.cursors.append(params["cursor"])
        cursor = params["cursor"]
        return Response({"status_code": 0, "comments": [{"cid": str(cursor + 1)}],
                         "cursor": cursor + 1, "total": 2, "has_more": 0})


def test_reply_pagination_continues_after_early_has_more_zero():
    client = Client()
    rows, total, complete, pages = module.collect_pages(
        client, "/api/comment/list/reply/", {"item_id": "1", "comment_id": "2"}, replies=True)
    assert [row["cid"] for row in rows] == ["1", "2"]
    assert (total, complete, pages) == (2, True, 2)
    assert client.cursors == [0, 1]
