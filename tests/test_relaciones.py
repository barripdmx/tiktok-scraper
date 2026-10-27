"""Pruebas de identidad, paginacion y recuperacion de relaciones (sin red)."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.utils.tiktok_relaciones import (
    ListPage, PayloadError, RelationStore, account_from_user, exact_id,
    normalize_username, parse_list, profile_from_hydration,
)
from src.scrapers.tiktok_scraper_relaciones import relevant_request, visible_count


def user(name="cuenta", uid="7437948011063854113"):
    return {"username": name, "user_id": uid, "nickname": "Nombre", "verified": False}


@pytest.fixture
def store(tmp_path):
    result = RelationStore(tmp_path / "run", "blocusespanol")
    result.set_profile(user("blocusespanol", "7437948011063854112"))
    yield result
    result.close()


@pytest.mark.parametrize("value", [7437948011063854113.0, "7437948011063854113.0", "7.437948011063854e18", True, "-1"])
def test_refuses_imprecise_or_invalid_uid(value):
    with pytest.raises(ValueError):
        exact_id(value)


def test_large_ids_stay_exact_text(store):
    value = 7437948011063854113
    assert exact_id(value) == "7437948011063854113"
    store.record_page("seguidores", ListPage([user(uid=exact_id(value))], False))
    row = store.db.execute("SELECT user_id,typeof(user_id) AS kind FROM accounts WHERE username='cuenta'").fetchone()
    assert row["user_id"] == str(value) and row["kind"] == "text"
    store.export()
    with (store.directory / "seguidores.csv").open(encoding="utf-8-sig", newline="") as f:
        assert next(csv.DictReader(f))["user_id"] == str(value)


@pytest.mark.parametrize("value", ["../escape", "https://www.tiktok.com/@x", "dos cuentas", "x/" ])
def test_rejects_paths_and_urls(value):
    with pytest.raises(ValueError):
        normalize_username(value)


def test_profile_hydration_preserves_missing_counts_and_identity():
    raw = json.dumps({"__DEFAULT_SCOPE__": {"webapp.user-detail": {"userInfo": {
        "user": {"id": 7437948011063854112, "uniqueId": "blocusespanol", "secUid": "internal"},
        "stats": {"followerCount": 0}}}}})
    profile = profile_from_hydration(raw, "blocusespanol")
    assert profile["user_id"] == "7437948011063854112"
    assert profile["followers"] == 0
    assert profile["following"] is None
    assert profile_from_hydration(raw, "otra") == {}


def test_web_and_research_list_contracts():
    web = parse_list({"statusCode": 0, "userList": [{"user": {"id": "7437948011063854113", "uniqueId": "cuenta"}}],
                      "hasMore": 1, "minCursor": 123, "maxCursor": 456})
    assert web.users[0]["user_id"] == "7437948011063854113"
    assert web.has_more is True and "maxCursor" in web.cursor
    research = parse_list({"error": {"code": "ok"}, "data": {"user_followers": [
        {"username": "cuenta", "display_name": "Nombre"}], "has_more": False, "cursor": 123}})
    assert research.users[0]["user_id"] == "" and research.has_more is False


@pytest.mark.parametrize("payload", [{}, {"statusCode": 10221}, {"userList": None}, {"data": {"count": 0}},
                                    {"userList": [], "hasMore": "false"}, {"error": {"code": "scope_not_authorized"}}])
def test_failure_is_not_an_empty_list(payload):
    with pytest.raises(PayloadError):
        parse_list(payload)


def test_invalid_users_are_counted_as_rejected():
    page = parse_list({"userList": [{"user": {"id": 7437948011063854113.0, "uniqueId": "bad"}}, {}],
                       "hasMore": False})
    assert page.users == [] and page.rejected == 2


def test_deduplicates_pages_and_resume_without_losing_checkpoint(tmp_path):
    folder = tmp_path / "run"
    s = RelationStore(folder, "blocusespanol")
    s.set_profile(user("blocusespanol", "7437948011063854112"))
    s.record_page("seguidores", ListPage([user()], True, "page1"))
    s.close()  # Simula terminar antes de regenerar las exportaciones.
    resumed = RelationStore(folder, "blocusespanol", resume=True)
    assert resumed.get("seguidores")["cursor"] == "page1"
    assert resumed.record_page("seguidores", ListPage([user(), user("segunda", "7437948011063854114")], False, "page2")) == 1
    assert resumed.count("seguidores") == 2
    assert resumed.export()["lists"]["seguidores"]["total_observed"] == 2
    resumed.close()


def test_dom_enrichment_and_api_duplicates_do_not_create_accounts(store):
    store.record_page("seguidores", ListPage([user(uid="")]), source="dom")
    store.record_page("seguidores", ListPage([user()], True, "next"), source="api")
    store.record_page("seguidores", ListPage([user(uid="")]), source="dom")
    assert store.count("seguidores") == 1
    assert store.get("seguidores")["cursor"] == "next"
    assert store.get("seguidores")["has_more"] is True
    assert store.db.execute("SELECT user_id FROM accounts WHERE username='cuenta'").fetchone()[0] == "7437948011063854113"


def test_conflicting_known_ids_are_not_merged_by_handle(store):
    store.record_page("seguidores", ListPage([user(), user(uid="7437948011063854114")]))
    assert store.count("seguidores") == 2


def test_directions_and_reciprocal_edges_are_preserved(store):
    store.record_page("seguidores", ListPage([user()], False))
    store.record_page("seguidos", ListPage([user()], False))
    store.export()
    with (store.directory / "relaciones.csv").open(encoding="utf-8-sig", newline="") as f:
        edges = list(csv.DictReader(f))
    assert {(x["source_username"], x["target_username"]) for x in edges} == {
        ("cuenta", "blocusespanol"), ("blocusespanol", "cuenta")}
    import networkx as nx
    graph = nx.read_gexf(store.directory / "relaciones.gexf")
    assert graph.number_of_edges() == 2


def test_unavailable_lists_have_unknown_coverage_and_no_claim_of_zero_population(store):
    store.state("seguidores", advertised_count=628, status="unavailable", stop_reason="api_empty_or_non_json_response")
    manifest = store.export()
    state = manifest["lists"]["seguidores"]
    assert state["total_observed"] == 0
    assert state["advertised_count"] == 628
    assert state["matches_displayed_count"] is False
    assert manifest["coverage_validated"] is False


def test_strict_account_limit_counts_new_members_only(store):
    store.record_page("seguidores", ListPage([user()]), max_accounts=2)
    store.record_page("seguidores", ListPage([user(), user("dos", "7437948011063854114"), user("tres", "7437948011063854115")]), max_accounts=2)
    assert store.count("seguidores") == 2
    assert store.get("seguidores")["limit_reached"] is True


def test_export_never_contains_internal_identifier_or_session_fields(store):
    store.set_profile({**user("blocusespanol", "7437948011063854112"), "_sec_uid": "internal-secret"})
    store.export()
    text = "\n".join(p.read_text(encoding="utf-8-sig") for p in store.directory.iterdir() if p.suffix in (".json", ".csv"))
    assert "internal-secret" not in text and "sec_uid" not in text
    assert "msToken" not in text


def test_resume_rejects_other_target(tmp_path):
    folder = tmp_path / "run"
    RelationStore(folder, "blocusespanol").close()
    with pytest.raises(ValueError, match="coincide"):
        RelationStore(folder, "otra", resume=True)


def test_request_matching_excludes_sidebar_and_other_direction():
    profile = {"_sec_uid": "target", "user_id": "7437948011063854112"}
    url = "https://www.tiktok.com/api/user/list/?scene=67&secUid=target&msToken=secret"
    assert relevant_request(url, "seguidores", profile)
    assert not relevant_request(url.replace("target", "sidebar"), "seguidores", profile)
    assert not relevant_request(url, "seguidos", profile)
    assert not relevant_request(url, "seguidores", {})


@pytest.mark.parametrize(("text", "expected"), [("628", 628), ("1.234", 1234), ("1,234", 1234), ("1.2K", None), ("", None)])
def test_only_exact_display_counts_are_used_for_coverage(text, expected):
    assert visible_count(text) == expected


def test_chrome_import_preserves_observation_dates_and_partial_coverage(tmp_path):
    from src.scrapers.tiktok_scraper_relaciones import import_capture, parser
    snapshot = tmp_path / "captura_chrome.json"
    capture = {
        "method": "chrome_visible_dom", "username": "blocusespanol",
        "started_at": "2026-10-25T17:00:00.000Z", "finished_at": "2026-10-25T17:02:00.000Z",
        "profile": {"username": "blocusespanol", "nickname": "BlocusMadrid", "followers": 632, "following": 212},
        "lists": {
            "seguidores": {"pages": [{"observed_at": "2026-10-25T17:00:01.000Z", "users": [
                {"username": "cuenta", "display_name": "Nombre"},
                {"username": "segunda", "display_name": "Segunda"}]}]},
            "seguidos": {"pages": [{"observed_at": "2026-10-25T17:01:00.000Z", "users": [
                {"username": "cuenta", "display_name": "Nombre"}]}]},
        },
    }
    snapshot.write_text(json.dumps(capture), encoding="utf-8")
    options = parser().parse_args(["--user", "blocusespanol", "--importar-captura", str(snapshot)])
    assert import_capture(options) == 2
    result = json.loads((tmp_path / "ejecucion.json").read_text(encoding="utf-8"))
    assert result["method"] == "chrome_visible_dom"
    assert result["started_at"] == "2026-10-25T17:00:00+00:00"
    assert result["lists"]["seguidores"]["total_observed"] == 2
    assert result["lists"]["seguidos"]["total_observed"] == 1
    assert result["lists"]["seguidores"]["status"] == "partial"
    with (tmp_path / "seguidores.csv").open(encoding="utf-8-sig", newline="") as f:
        records = list(csv.DictReader(f))
    assert records[0]["user_id"] == ""
    assert records[0]["observed_at"] == "2026-10-25T17:00:01+00:00"
    assert records[0]["source"] == "chrome_dom"
    options.reanudar = tmp_path
    assert import_capture(options) == 2
    result = json.loads((tmp_path / "ejecucion.json").read_text(encoding="utf-8"))
    assert result["lists"]["seguidores"]["total_observed"] == 2


def test_import_refuses_another_target_before_creating_database(tmp_path):
    from src.scrapers.tiktok_scraper_relaciones import import_capture, parser
    snapshot = tmp_path / "captura.json"
    snapshot.write_text(json.dumps({"method": "chrome_visible_dom", "username": "otra"}), encoding="utf-8")
    options = parser().parse_args(["--user", "blocusespanol", "--importar-captura", str(snapshot)])
    with pytest.raises(ValueError, match="otra cuenta"):
        import_capture(options)
    assert not (tmp_path / "relaciones.sqlite3").exists()


def test_resume_keeps_capture_methods_separate(tmp_path):
    folder = tmp_path / "run"
    RelationStore(folder, "blocusespanol", method="chrome_visible_dom").close()
    with pytest.raises(ValueError, match="metodo"):
        RelationStore(folder, "blocusespanol", resume=True)
