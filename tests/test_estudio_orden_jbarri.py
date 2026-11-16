import json
import zipfile

from scripts.estudio_orden_jbarri_analizar import compare, read_export
from scripts.estudio_orden_jbarri_capturar import capture_list
from src.scrapers.tiktok_descargar_relaciones import FetchError
from src.utils.tiktok_relaciones import ListPage


def test_exportacion_json_zip_y_inversiones(tmp_path):
    archive = tmp_path / "exportacion.zip"
    data = {
        "Profile And Settings": {
            "Follower": {"FansList": [
                {"Date": "2026-10-01 10:00:00 UTC", "Username": "a"},
                {"Date": "2026-10-03 10:00:00 UTC", "Username": "b"},
                {"Date": "2026-10-02 10:00:00 UTC", "Username": "c"},
                {"Date": "2026-09-01 10:00:00 UTC", "Username": "solo_export"},
            ]},
            "Following": {"Following": [
                {"Date": "2025-01-01T00:00:00Z", "Username": "d"}
            ]},
            "Profile Information": {"Email": "no-debe-salir@example.com"},
        }
    }
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("user_data_tiktok.json", json.dumps(data))
    dated, metadata = read_export(archive)
    assert dated["seguidores"]["a"] == "2026-10-01T10:00:00+00:00"
    assert dated["seguidos"]["d"] == "2025-01-01T00:00:00+00:00"
    assert "no-debe-salir" not in json.dumps(metadata)
    web = [{"posicion_respuesta": str(i), "username": name, "pagina": "1",
            "posicion_en_pagina": str(i), "user_id": str(i), "cursor_enviado": "0",
            "minCursor": "1", "maxCursor": "", "observed_at": "2026-10-26T12:00:00Z",
            "evidencia": "pagina_0001.json"} for i, name in enumerate(("a", "b", "c", "sin_cruce"), 1)]
    table, summary = compare(web, dated["seguidores"], "seguidores")
    assert len(table) == 5
    assert summary["coincidencias_con_fecha"] == 3
    assert summary["solo_exportacion"] == 1
    assert summary["pares_fechas_distintas"] == 3
    assert summary["inversiones"] == 2
    assert table[-2]["estado_cruce"] == "sin_cruce_exportacion"
    assert table[-1]["estado_cruce"] == "solo_exportacion"
    assert table[-1]["username_web"] == ""
    assert table[-1]["username_exportacion"] == "solo_export"


def test_captura_reanuda_desde_ultimo_cursor(tmp_path):
    folder = tmp_path / "seguidores"

    class FirstClient:
        def __init__(self):
            self.calls = []

        def user_list(self, sec_uid, direction, cursor):
            self.calls.append(cursor)
            if cursor == "0":
                return ListPage([{"user_id": "1", "username": "a"}], True), {
                    "minCursor": 100, "hasMore": True, "total": 2}
            raise FetchError("api_error")

    first = FirstClient()
    partial = capture_list(first, {"_sec_uid": "x", "followers": 2}, "seguidores", folder)
    assert partial["status"] == "partial"
    assert first.calls == ["0", "100"]

    class NextClient:
        def __init__(self):
            self.calls = []

        def user_list(self, sec_uid, direction, cursor):
            self.calls.append(cursor)
            return ListPage([{"user_id": "2", "username": "b"}], False), {
                "minCursor": 90, "hasMore": False, "total": 2}

    second = NextClient()
    done = capture_list(second, {"_sec_uid": "x", "followers": 2}, "seguidores", folder, resume=True)
    assert second.calls == ["100"]
    assert done["status"] == "pagination_exhausted"
    assert done["rows"] == 2
    assert done["pages"] == 2
