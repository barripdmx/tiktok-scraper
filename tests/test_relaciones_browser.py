"""Integracion con Chrome y web simulada; todas las peticiones se interceptan."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.scrapers.tiktok_scraper_relaciones import collect_direction
from src.utils.tiktok_relaciones import RelationStore

HTML = """<!doctype html><meta charset="utf-8">
<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">HYDRATION</script>
<h2 data-e2e="user-subtitle">blocusespanol</h2>
<div onclick="start(67)"><strong data-e2e="followers-count">2</strong>Seguidores</div>
<div onclick="start(21)"><strong data-e2e="following-count">2</strong>Siguiendo</div>
<div data-e2e="follow-info-popup" id="popup" style="display:none;overflow-y:auto;height:120px">
<div style="height:1600px" id="content"></div></div>
<script>
let activeScene, requested=false;
async function requestPage(n) {
  try { await (await fetch('/api/user/list/?scene='+activeScene+'&secUid=target&p='+n)).json(); } catch(e) {}
}
function start(scene) {
  activeScene=scene;
  const popup=document.getElementById('popup');
  popup.style.display='block';
  if (MODE==='private') {
    document.getElementById('content').innerText='This account is private';
    return;
  }
  requestPage(0);
  popup.addEventListener('scroll',()=>{if(!requested){requested=true;requestPage(1);}});
}
</script>"""


@pytest.mark.parametrize(("mode", "expected_count", "expected_reason"), [
    ("pages", 2, "api_pagination_exhausted"),
    ("empty_response", 0, "api_empty_or_non_json_response"),
    ("private", 0, "private_or_hidden"),
    ("repeat", 1, "repeated_cursor"),
])
def test_real_browser_capture_and_stop_reasons(tmp_path, mode, expected_count, expected_reason):
    pytest.importorskip("playwright.async_api")
    from playwright.async_api import async_playwright, Error

    async def scenario():
        store = RelationStore(tmp_path / "run", "blocusespanol")
        store.set_profile({"username": "blocusespanol", "user_id": "", "nickname": ""})
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.launch(channel="chrome", headless=True)
            except Error as exc:
                if "executable" in str(exc).lower() and "exist" in str(exc).lower():
                    store.close()
                    pytest.skip("Chrome no instalado")
                raise
            context = await browser.new_context()
            calls = []
            js_errors = []
            context.on("page", lambda page: page.on("pageerror", lambda error: js_errors.append(str(error))))
            hydration = {"__DEFAULT_SCOPE__": {"webapp.user-detail": {"userInfo": {
                "user": {"id": "7437948011063854112", "uniqueId": "blocusespanol", "secUid": "target"},
                "stats": {"followerCount": 2, "followingCount": 2}}}}}
            html = HTML.replace(">HYDRATION</script>", ">" + json.dumps(hydration) + "</script>").replace("MODE", json.dumps(mode))

            async def route_request(route):
                url = urlsplit(route.request.url)
                calls.append(url.path + ("?" + url.query if url.query else ""))
                if url.path == "/@blocusespanol":
                    await route.fulfill(status=200, content_type="text/html", body=html)
                elif url.path == "/api/user/list/":
                    if mode == "empty_response":
                        await route.fulfill(status=200, content_type="application/json", body="")
                    else:
                        index = int(parse_qs(url.query).get("p", ["0"])[0])
                        name = "cuenta_uno" if index == 0 or mode == "repeat" else "cuenta_dos"
                        uid = "7437948011063854113" if name == "cuenta_uno" else "7437948011063854114"
                        payload = {"statusCode": 0, "userList": [{"user": {"id": uid, "uniqueId": name}}],
                                   "hasMore": bool(index == 0 or mode == "repeat"),
                                   "minCursor": 0, "maxCursor": 123 if index == 0 or mode == "repeat" else 122}
                        await route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
                else:
                    await route.abort()

            await context.route("**/*", route_request)
            options = SimpleNamespace(max_segundos=35, max_cuentas=100, max_paginas=10,
                                      sin_avance=2, esperar_login=0, navegador="oculto")
            try:
                await collect_direction(context, store, "seguidores", options)
                result = store.export()
                state = result["lists"]["seguidores"]
                assert state["total_observed"] == expected_count, {"calls": calls, "js_errors": js_errors, "state": state}
                assert state["stop_reason"] == expected_reason, {"calls": calls, "js_errors": js_errors, "state": state}
                assert state["coverage_validated"] is False
                assert state["advertised_count"] == 2
                if mode == "pages":
                    assert state["status"] == "pagination_exhausted"
                    assert state["api_pages"] == 2
                    assert state["matches_displayed_count"] is True
                elif mode in ("empty_response", "private"):
                    assert state["status"] == "unavailable"
                assert {c.split("?")[0] for c in calls} <= {"/@blocusespanol", "/api/user/list/", "/favicon.ico"}
                assert not js_errors, js_errors
            finally:
                store.close()
                await browser.close()
    asyncio.run(scenario())
