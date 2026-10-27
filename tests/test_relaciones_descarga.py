"""Contratos del descargador: entrada, páginas, fallos, lotes y exportaciones."""
import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.scrapers import tiktok_descargar_relaciones as download
from src.utils.tiktok_relaciones import parse_list
from src.utils.tiktok_relaciones_entrada import account_name, read_accounts


def profile(name):
    return {"username": name, "user_id": "7437948011063854112", "nickname": name,
            "followers": 2, "following": 2, "_sec_uid": "not_exported", "private_account": False,
            "following_visibility": 1}


def payload(n, more=False, cursor=123, rejected=False):
    rows = [{"user": {"id": str(7437948011063854200 + n), "uniqueId": f"cuenta{n}"}}]
    if rejected:
        rows.append({"user": {"id": "0", "uniqueId": "", "nickname": ""}})
    return {"statusCode": 0, "userList": rows, "hasMore": more, "minCursor": cursor, "total": 2}


class Client:
    def __init__(self, options):
        self.calls, self.closed = [], False

    def profile(self, name):
        self.calls.append(("profile", name))
        return profile(name)

    def user_list(self, uid, direction, cursor):
        self.calls.append((direction, cursor))
        data = payload(1, True) if cursor == "0" else payload(2, False, 12)
        return parse_list(data), data

    def close(self):
        self.closed = True


def options(tmp_path, *extra):
    return download.parser().parse_args(["--user", "blocusespanol", "--salida", str(tmp_path), *extra])


def manifest(tmp_path, name="blocusespanol"):
    paths = list((tmp_path / ("user_" + name)).rglob("ejecucion.json"))
    assert len(paths) == 1
    return json.loads(paths[0].read_text(encoding="utf-8")), paths[0].parent


@pytest.mark.parametrize("value", ["@BlocusEspanol", "blocusespanol", "https://www.tiktok.com/@blocusespanol/?lang=es", "tiktok.com/@blocusespanol"])
def test_account_forms(value):
    assert account_name(value) == "blocusespanol"


@pytest.mark.parametrize("value", ["../escape", "https://evil.example/@x", "https://www.tiktok.com@evil.example/@x",
                                  "https://www.tiktok.com/@x/video/12", "https://www.tiktok.com:444/@x", "dos cuentas"])
def test_rejects_invalid_targets(value):
    with pytest.raises(ValueError):
        account_name(value)


@pytest.mark.parametrize("suffix,content", [
    (".txt", "# ejemplo\n@UNO\nhttps://www.tiktok.com/@dos\nuno\n"),
    (".csv", "username,nota\n@UNO,a\ndos,b\nuno,c\n"),
    (".csv", "cuenta;nota\n@UNO;España\ndos;otra\nuno;repetida\n"),
    (".csv", "@UNO\ndos\nuno\n"),
    (".csv", "URL\nhttps://www.tiktok.com/@UNO\n@dos\nuno\n"),
])
def test_files_normalize_and_deduplicate(tmp_path, suffix, content):
    path = tmp_path / ("entrada" + suffix)
    path.write_text(content, encoding="utf-8-sig")
    result = read_accounts(path)
    assert result.usernames == ("uno", "dos")
    assert result.duplicates == 1


@pytest.mark.parametrize("content", ["", "username,nota\n,otra\n", "nombre,nota\nx,y\n",
                                     "username,url\nx,https://www.tiktok.com/@x\n", "username\n../escape\n"])
def test_bad_file_fails_before_network_or_output(tmp_path, content):
    path = tmp_path / "mal.csv"
    path.write_text(content, encoding="utf-8")
    opts = download.parser().parse_args(["--archivo", str(path), "--salida", str(tmp_path / "out")])
    def forbidden(_):
        pytest.fail("No debe preparar la red para un archivo inválido")
    with pytest.raises(ValueError):
        download.run_job(opts, forbidden)
    assert not (tmp_path / "out").exists()


def test_two_pages_both_lists_exact_ids_and_exports(tmp_path):
    client = Client(None)
    assert download.run_job(options(tmp_path, "--no-prompt"), lambda _: client) == 0
    result, folder = manifest(tmp_path)
    assert client.closed
    assert [(d, c) for d, c in client.calls if d == "seguidores"] == [("seguidores", "0"), ("seguidores", "123")]
    for direction in ("seguidores", "seguidos"):
        state = result["lists"][direction]
        assert state["total_observed"] == 2 and state["status"] == "pagination_exhausted"
        assert state["matches_displayed_count_end"] is True
        assert state["coverage_validated"] is False
    with (folder / "seguidores.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.DictReader(stream))["user_id"] == "7437948011063854201"
    import networkx as nx
    graph = nx.read_gexf(folder / "relaciones.gexf")
    assert len(graph) == 3 and graph.number_of_edges() == 4
    assert "not_exported" not in (folder / "ejecucion.json").read_text()


def test_limit_preserves_partial_state_and_selected_direction(tmp_path):
    assert download.run_job(options(tmp_path, "--lista", "seguidos", "--max-cuentas", "1"), Client) == 2
    result, _ = manifest(tmp_path)
    assert result["lists"]["seguidos"]["total_observed"] == 1
    assert result["lists"]["seguidos"]["stop_reason"] == "account_limit"
    assert result["lists"]["seguidores"]["status"] == "not_requested"


def test_empty_json_is_unavailable_not_zero_complete(tmp_path):
    class Empty(Client):
        def user_list(self, *args):
            raise download.FetchError("empty_response", halt_batch=True)
    assert download.run_job(options(tmp_path), Empty) == 2
    result, _ = manifest(tmp_path)
    assert result["lists"]["seguidores"]["status"] == "unavailable"
    assert result["lists"]["seguidos"]["status"] == "not_run"


@pytest.mark.parametrize("changes,valid", [({}, True), ({"total": 1}, False),
    ({"total": False}, False), ({"hasMore": True}, False),
    ({"isTruncated": True}, False), ({"userList": None}, False)])
def test_missing_list_only_normalized_for_explicit_zero(changes, valid):
    data = {"statusCode": 0, "status_code": 0, "total": 0, "hasMore": False,
            "isTruncated": False, "minCursor": -1, **changes}
    client = object.__new__(download.TikTokClient)
    client._get = lambda *args: SimpleNamespace(json=lambda: data)
    if valid:
        page, payload_data = client.user_list("uid", "seguidos", "0")
        assert page.users == [] and page.has_more is False and payload_data["total"] == 0
    else:
        with pytest.raises(download.FetchError):
            client.user_list("uid", "seguidos", "0")


@pytest.mark.parametrize("cursor,changes,valid", [
    ("123", {}, True), ("0", {}, False), ("123", {"hasMore": True}, False),
    ("123", {"minCursor": 124}, False), ("123", {"isTruncated": True}, False),
    ("123", {"statusCode": 10101}, False), ("123", {"userList": None}, False),
])
def test_terminal_page_without_list_requires_explicit_end(cursor, changes, valid):
    data = {"statusCode": 0, "total": 210, "hasMore": False,
            "isTruncated": False, "minCursor": 100, **changes}
    client = object.__new__(download.TikTokClient)
    client._get = lambda *args: SimpleNamespace(json=lambda: data)
    if valid:
        page, raw = client.user_list("uid", "seguidos", cursor)
        assert page.users == [] and page.has_more is False and raw["total"] == 210
    else:
        with pytest.raises(download.FetchError):
            client.user_list("uid", "seguidos", cursor)


@pytest.mark.parametrize("case,reason", [("repeat", "no_progress_or_repeated_cursor"), ("missing", "missing_pagination"), ("truncated", "upstream_truncated")])
def test_bad_pagination_stops_and_keeps_pages(tmp_path, case, reason):
    class Bad(Client):
        def user_list(self, uid, direction, cursor):
            data = payload(1, True, 0)
            if case == "missing":
                data.pop("minCursor")
            if case == "truncated":
                data["isTruncated"] = True
            return parse_list(data), data
    assert download.run_job(options(tmp_path, "--lista", "seguidores"), Bad) == 2
    result, _ = manifest(tmp_path)
    assert result["lists"]["seguidores"]["stop_reason"] == reason
    assert result["lists"]["seguidores"]["total_observed"] == 1


def test_unidentifiable_record_and_count_gap_are_observations(tmp_path):
    class Dummy(Client):
        def user_list(self, *args):
            data = payload(1, rejected=True)
            return parse_list(data), data
    assert download.run_job(options(tmp_path), Dummy) == 2
    result, _ = manifest(tmp_path)
    assert result["lists"]["seguidores"]["rejected_records"] == 1
    assert result["lists"]["seguidores"]["matches_displayed_count"] is False


def test_batch_continues_missing_account_and_deduplicates(tmp_path):
    path = tmp_path / "cuentas.txt"
    path.write_text("missing\n@valid\nVALID\n", encoding="utf-8")
    class Mixed(Client):
        def profile(self, name):
            if name == "missing":
                raise download.FetchError("profile_status_10221")
            return super().profile(name)
    opts = download.parser().parse_args(["--archivo", str(path), "--salida", str(tmp_path / "out")])
    assert download.run_job(opts, Mixed) == 2
    summary = json.loads(next((tmp_path / "out/lotes_relaciones").rglob("resumen.json")).read_text())
    assert summary["input_accounts"] == 2 and summary["duplicates_ignored"] == 1
    assert summary["accounts"][0]["lists"]["seguidores"]["status"] == "unavailable"
    assert summary["accounts"][1]["lists"]["seguidores"]["total_observed"] == 2


def test_batch_halts_on_rate_limit_without_requesting_next_account(tmp_path):
    path = tmp_path / "cuentas.txt"
    path.write_text("uno\ndos\n", encoding="utf-8")
    class Limited(Client):
        def profile(self, name):
            assert name == "uno"
            raise download.FetchError("http_429", halt_batch=True)
    opts = download.parser().parse_args(["--archivo", str(path), "--salida", str(tmp_path / "out")])
    assert download.run_job(opts, Limited) == 2
    summary = json.loads(next((tmp_path / "out/lotes_relaciones").rglob("resumen.json")).read_text())
    assert summary["accounts"][1]["lists"]["seguidores"]["status"] == "not_run"
    assert not (tmp_path / "out/user_dos").exists()


def test_private_list_does_not_trigger_requests(tmp_path):
    class Private(Client):
        def profile(self, name):
            return {**profile(name), "private_account": True}
        def user_list(self, *args):
            pytest.fail("No se debe solicitar una lista privada")
    assert download.run_job(options(tmp_path), Private) == 2


def test_interruption_keeps_prior_page_and_updates_manifest(tmp_path):
    class Interrupted(Client):
        def user_list(self, uid, direction, cursor):
            if cursor != "0":
                raise KeyboardInterrupt
            return super().user_list(uid, direction, cursor)
    with pytest.raises(KeyboardInterrupt):
        download.run_job(options(tmp_path), Interrupted)
    result, folder = manifest(tmp_path)
    assert result["lists"]["seguidores"]["total_observed"] == 1
    assert result["lists"]["seguidores"]["stop_reason"] == "interrupted"
    assert json.loads((folder / "resumen.json").read_text())["status"] == "interrupted"


def test_menu_cancel_keeps_page_and_does_not_start_next_account(tmp_path):
    path = tmp_path / "cuentas.txt"
    path.write_text("uno\ndos\n", encoding="utf-8")
    cancel = tmp_path / "detener"
    class Cancelled(Client):
        def user_list(self, *args):
            page = super().user_list(*args)
            cancel.write_text("stop", encoding="utf-8")
            return page
    opts = download.parser().parse_args(["--archivo", str(path), "--salida", str(tmp_path / "out"),
                                        "--cancel-file", str(cancel)])
    with pytest.raises(KeyboardInterrupt):
        download.run_job(opts, Cancelled)
    result, _ = manifest(tmp_path / "out", "uno")
    assert result["lists"]["seguidores"]["total_observed"] == 1
    assert result["lists"]["seguidores"]["stop_reason"] == "interrupted"
    summary = json.loads(next((tmp_path / "out/lotes_relaciones").rglob("resumen.json")).read_text())
    assert summary["accounts"][1]["lists"]["seguidores"]["status"] == "not_run"


def test_default_has_no_artificial_capture_limit(tmp_path):
    opts = options(tmp_path)
    assert (opts.max_cuentas, opts.max_paginas, opts.max_segundos) == (0, 0, 0)


def test_session_file_selection_keeps_existing_alias_and_explicit_override(tmp_path):
    principal = download.ROOT / "secrets/tiktok_cookies.json"
    secundaria = download.ROOT / "secrets/tiktok_cookies_secundaria.json"
    assert download.session_cookie_path(options(tmp_path, "--sesion", "principal")) == principal
    assert download.session_cookie_path(options(tmp_path, "--sesion", "guardada")) == principal
    assert download.session_cookie_path(options(tmp_path, "--sesion", "secundaria")) == secundaria
    other = tmp_path / "other.json"
    assert download.session_cookie_path(options(tmp_path, "--sesion", "secundaria", "--cookies", str(other))) == other


def test_optional_page_limit(tmp_path):
    assert download.run_job(options(tmp_path, "--max-paginas", "1"), Client) == 2
    result, _ = manifest(tmp_path)
    assert result["lists"]["seguidores"]["stop_reason"] == "page_limit"
    assert result["lists"]["seguidores"]["total_observed"] == 1


@pytest.mark.parametrize("creation,expected", [(1731782585, "2024-11-16T18:43:05+00:00"),
    (0, None), (True, None), ("1731782585", None), (9999999999999, None)])
def test_transport_parses_real_contract_without_exporting_tokens(monkeypatch, creation, expected):
    import curl_cffi.requests
    class Session:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is False
        def get(self, url, **kwargs):
            assert kwargs["allow_redirects"] is False
            raw = json.dumps({"__DEFAULT_SCOPE__": {"webapp.user-detail": {"statusCode": 0, "userInfo": {
                "user": {"id": "7437948011063854112", "uniqueId": "blocusespanol", "secUid": "private_token", "followingVisibility": 1, "createTime": creation},
                "stats": {"followerCount": 2, "followingCount": 3}}}}})
            return SimpleNamespace(status_code=200, content=b"data", text=f'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">{raw}</script>')
        def close(self):
            pass
    monkeypatch.setattr(curl_cffi.requests, "Session", Session)
    client = download.TikTokClient(SimpleNamespace(sesion="anonima"))
    result = client.profile("blocusespanol")
    assert result["followers"] == 2 and result["following"] == 3
    assert result["_sec_uid"] == "private_token"
    assert result.get("created_at") == expected
    assert (result.get("creation_source") == "public_profile_createTime") is bool(expected)
    client.close()
