"""Piloto de listas visibles de TikTok; captura trafico organico, sin repetir firmas."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from config.rutas import dataset_dir
from src.utils.tiktok_relaciones import (
    DIRECTIONS, ListPage, PayloadError, RelationStore, account_from_user,
    normalize_username, observation_time, parse_list, profile_from_hydration, utcnow,
)

SCENES = {"seguidores": "67", "seguidos": "21"}  # Observados en la web el 25/10/2026.
COUNT_SELECTORS = {"seguidores": "followers-count", "seguidos": "following-count"}
POPUP = '[data-e2e="follow-info-popup"]'
SCROLL_JS = """el => {
    const candidates = [el, ...el.querySelectorAll('*')].filter(n => {
        const style = getComputedStyle(n);
        return /(auto|scroll)/.test(style.overflowY) && n.scrollHeight > n.clientHeight + 4;
    });
    candidates.sort((a,b) => (b.scrollHeight-b.clientHeight)-(a.scrollHeight-a.clientHeight));
    if (!candidates.length) return false;
    const node = candidates[0], before = node.scrollTop;
    node.scrollTop += Math.max(400, node.clientHeight * .85);
    node.dispatchEvent(new Event('scroll', {bubbles:true}));
    return node.scrollTop !== before;
}"""
DOM_USERS_JS = """el => [...el.querySelectorAll('a[href]')].map(a => {
    if (!a.getClientRects().length || a.closest('[aria-hidden="true"]')) return null;
    const match = a.href.match(/^https:\\/\\/(?:www\\.)?tiktok\\.com\\/@([a-zA-Z0-9_.]+)\\/?$/);
    return match ? {username:match[1], display_name:(a.innerText||'').trim().split('\\n').find(t=>t.trim())||''} : null;
}).filter(Boolean)"""


def visible_count(text):
    text = (text or "").strip().replace("\u00a0", " ")
    if not re.fullmatch(r"\d+|\d{1,3}(?:[., ]\d{3})+", text):
        return None  # Un contador abreviado no es un total exacto.
    return int(re.sub(r"[., ]", "", text))


async def is_visible(locator):
    return bool(await locator.count()) and await locator.first.is_visible()


async def blocker(page, popup):
    for selector in ('[id*="captcha"]', '[class*="captcha"]', '[id*="verify-center"]'):
        if await is_visible(page.locator(selector)):
            return "verification_required"
    for selector in ('#loginModalContentContainer', '#login-modal-title', '[data-e2e="modal-login"]'):
        if await is_visible(page.locator(selector)):
            return "needs_login"
    text = (await popup.inner_text()).lower() if await is_visible(popup) else ""
    if any(s in text for s in ("following list is private", "following list is hidden",
                              "ha ocultado su lista", "lista de seguidos es privada",
                              "esta cuenta es privada", "this account is private")):
        return "private_or_hidden"
    return None


async def dismiss_cookie_notice(page):
    for text in ("Rechazar cookies opcionales", "Decline optional cookies", "Reject all"):
        button = page.get_by_role("button", name=text, exact=True)
        if await is_visible(button):
            with contextlib.suppress(Exception):
                await button.first.click(timeout=2000)
            return


async def read_profile(page, username):
    raw = await page.locator("#__UNIVERSAL_DATA_FOR_REHYDRATION__").text_content() if await page.locator("#__UNIVERSAL_DATA_FOR_REHYDRATION__").count() else None
    profile = profile_from_hydration(raw, username)
    if not profile:
        subtitle = page.locator('[data-e2e="user-subtitle"]')
        if not await is_visible(subtitle) or normalize_username(await subtitle.inner_text()) != username:
            raise ValueError("profile_unavailable")
        profile = {"username": username, "user_id": "", "nickname": "", "observed_at": utcnow()}
    for direction, key in (("seguidores", "followers"), ("seguidos", "following")):
        element = page.locator(f'[data-e2e="{COUNT_SELECTORS[direction]}"]')
        if await element.count():
            text = await element.first.inner_text()
            profile[key + "_display"] = text
            count = visible_count(text)
            if count is not None:
                profile[key] = count
    return profile


def relevant_request(url, direction, profile):
    parsed = urlsplit(url)
    if parsed.hostname != "www.tiktok.com" or parsed.path != "/api/user/list/":
        return False
    query = parse_qs(parsed.query)
    if query.get("scene") != [SCENES[direction]]:
        return False
    sid = profile.get("_sec_uid")
    uid = profile.get("user_id")
    # El sidebar tambien llama user/list: nunca mezclar la cuenta autenticada.
    return bool((sid and query.get("secUid") == [sid]) or
                (uid and (query.get("user_id") == [uid] or query.get("userId") == [uid])))


async def collect_direction(context, store, direction, options):
    page = await context.new_page()
    queue = asyncio.Queue()
    tasks = set()
    profile = {}
    accepting = False
    popup = page.locator(POPUP)
    api_error = None
    seen_cursors = set()
    store.state(direction, status="running", stop_reason=None, attempt_started_at=utcnow(),
                has_more=None, limit_reached=False)
    store.export()

    async def capture(response):
        if not accepting or not relevant_request(response.url, direction, profile):
            return
        if response.status == 429:
            await queue.put(("error", "rate_limited"))
            return
        if response.status != 200:
            await queue.put(("error", "http_error"))
            return
        try:
            payload = await asyncio.wait_for(response.json(), timeout=10)
        except Exception:
            await queue.put(("error", "api_empty_or_non_json_response"))
            return
        try:
            await queue.put(("page", parse_list(payload)))
        except PayloadError as exc:
            await queue.put(("error", str(exc)))

    def listener(response):
        if accepting and relevant_request(response.url, direction, profile):
            task = asyncio.create_task(capture(response))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    page.on("response", listener)
    reason, status = "unexpected_error", "error"
    started = asyncio.get_running_loop().time()
    try:
        await page.goto(f"https://www.tiktok.com/@{store.username}", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(3000)
        await dismiss_cookie_notice(page)
        profile = await read_profile(page, store.username)
        store.set_profile(profile)
        metric = "followers" if direction == "seguidores" else "following"
        store.state(direction, advertised_count=profile.get(metric), advertised_display=profile.get(metric + "_display"))
        print(f"{direction}: contador visible {profile.get(metric, 'no disponible')}", flush=True)
        accepting = True
        count_element = page.locator(f'[data-e2e="{COUNT_SELECTORS[direction]}"]')
        if not await is_visible(count_element):
            reason = "list_control_unavailable"
            status = "partial" if store.count(direction) else "unavailable"
            return
        await count_element.locator("..").click(timeout=5000)
        await page.wait_for_timeout(1500)
        idle = 0
        seen_dom = set()
        attempt_pages = 0
        deadline = started + options.max_segundos
        login_waited = False
        while asyncio.get_running_loop().time() < deadline:
            obstruction = await blocker(page, popup)
            if obstruction == "needs_login" and options.esperar_login and options.navegador == "visible" and not login_waited:
                print(f"Inicia sesion manualmente en el navegador; espera maxima {options.esperar_login}s.", flush=True)
                login_waited = True
                until = asyncio.get_running_loop().time() + options.esperar_login
                while obstruction == "needs_login" and asyncio.get_running_loop().time() < until:
                    await page.wait_for_timeout(1000)
                    obstruction = await blocker(page, popup)
                deadline = asyncio.get_running_loop().time() + options.max_segundos
                # Si el login recarga la pagina, el siguiente intento se reanuda
                # desde el comienzo con --reanudar y no pierde lo ya persistido.
            if obstruction:
                reason = obstruction
                status = "partial" if store.count(direction) else "unavailable"
                break
            before = store.count(direction)
            exhausted = False
            repeated = False
            while not queue.empty():
                kind, value = queue.get_nowait()
                if kind == "error":
                    api_error = value
                    continue
                attempt_pages += 1
                added = store.record_page(direction, value, max_accounts=options.max_cuentas)
                if value.cursor and value.cursor in seen_cursors and value.has_more is True and added == 0:
                    repeated = True
                if value.cursor:
                    seen_cursors.add(value.cursor)
                exhausted = value.has_more is False
                print(f"{direction}: pagina API, +{added}; total {store.count(direction)}", flush=True)
                store.export()
            if await is_visible(popup):
                candidates = await popup.evaluate(DOM_USERS_JS)
                users = []
                for item in candidates:
                    try:
                        user = account_from_user(item)
                    except ValueError:
                        continue
                    if user["username"] in seen_dom or user["username"] == store.username:
                        continue
                    seen_dom.add(user["username"])
                    users.append(user)
                if users:
                    store.record_page(direction, ListPage(users), source="dom", max_accounts=options.max_cuentas)
                    store.export()
            current = store.get(direction)
            total = store.count(direction)
            if current.get("limit_reached") or (options.max_cuentas and total >= options.max_cuentas and not exhausted):
                reason, status = "account_limit", "partial"
                break
            if exhausted:
                reason = "api_pagination_exhausted"
                status = "partial" if current.get("rejected_records") else "pagination_exhausted"
                break
            if repeated:
                reason, status = "repeated_cursor", "partial"
                break
            if attempt_pages >= options.max_paginas:
                reason, status = "page_limit", "partial"
                break
            if total == before and not tasks:
                idle += 1
            else:
                idle = 0
            if idle >= options.sin_avance:
                reason = api_error or ("ui_no_progress" if total else "list_not_loaded")
                status = "partial" if total else "unavailable"
                break
            if await is_visible(popup):
                await popup.evaluate(SCROLL_JS)
            await page.wait_for_timeout(1500)
        else:
            reason, status = "time_limit", "partial"
        # Contador al final de la captura: ayuda a interpretar cambios durante ella.
        element = page.locator(f'[data-e2e="{COUNT_SELECTORS[direction]}"]')
        if await element.count():
            store.state(direction, advertised_count_end=visible_count(await element.first.inner_text()))
    except asyncio.CancelledError:
        reason, status = "interrupted", "partial"
        raise
    except Exception as exc:
        reason = "navigation_error" if type(exc).__name__ in ("Error", "TimeoutError") else "profile_or_browser_error"
        status = "partial" if store.count(direction) else "error"
        print(f"{direction}: {reason} ({type(exc).__name__}).", flush=True)
    finally:
        accepting = False
        page.remove_listener("response", listener)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tuple(tasks), return_exceptions=True)
        store.state(direction, status=status, stop_reason=reason, finished_at=utcnow(),
                    last_api_error=api_error, total_observed=store.count(direction))
        store.export()
        with contextlib.suppress(Exception):
            await page.close()
        print(f"{direction}: {store.count(direction)} observados; {reason}.", flush=True)


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("Debe ser mayor que cero.")
    return number


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("Debe ser cero o positivo.")
    return number


def parser():
    p = argparse.ArgumentParser(description="Captura seguidores/seguidos visibles con cobertura explicita.")
    p.add_argument("--user", required=True, type=normalize_username)
    p.add_argument("--lista", choices=("ambas", *DIRECTIONS), default="ambas")
    p.add_argument("--max-cuentas", type=nonnegative, default=2000, help="Por lista; 0 sin limite de cuentas.")
    p.add_argument("--max-paginas", type=positive, default=100)
    p.add_argument("--max-segundos", type=positive, default=180, help="Tiempo maximo por lista.")
    p.add_argument("--sin-avance", type=positive, default=5)
    p.add_argument("--navegador", choices=("oculto", "visible"), default="oculto")
    p.add_argument("--esperar-login", type=nonnegative, default=0, help="Segundos para login manual; requiere navegador visible.")
    p.add_argument("--perfil", type=Path, default=ROOT / "drivers/tiktok_profile",
                   help="Perfil persistente existente. No se eliminan locks ni se copian perfiles.")
    p.add_argument("--cookies", type=Path, default=ROOT / "secrets/tiktok_cookies.json")
    p.add_argument("--importar-captura", type=Path,
                   help="JSON de listas visibles recogido en Chrome; exporta sin lanzar Playwright.")
    p.add_argument("--reanudar", type=Path, help="Carpeta de una ejecucion previa; recorre la UI desde el inicio y deduplica.")
    return p


def import_capture(options):
    """Importa observaciones DOM publicas y conserva su fecha, sin asumir exhaustividad."""
    try:
        capture = json.loads(options.importar_captura.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise ValueError("No se pudo leer el JSON de captura.") from None
    if not isinstance(capture, dict) or capture.get("method") != "chrome_visible_dom":
        raise ValueError("El archivo no es una captura chrome_visible_dom.")
    if normalize_username(capture.get("username")) != options.user:
        raise ValueError("La captura pertenece a otra cuenta.")
    raw_profile = capture.get("profile")
    if not isinstance(raw_profile, dict):
        raise ValueError("Falta el perfil de la captura.")
    profile = account_from_user(raw_profile)
    if profile["username"] != options.user:
        raise ValueError("El perfil pertenece a otra cuenta.")
    for field in ("followers", "following"):
        value = raw_profile.get(field)
        profile[field] = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
    lists = capture.get("lists")
    if not isinstance(lists, dict):
        raise ValueError("Faltan las listas de la captura.")
    started_at = observation_time(capture.get("started_at"))
    finished_at = observation_time(capture.get("finished_at"))
    profile["observed_at"] = finished_at
    directory = options.reanudar or options.importar_captura.resolve().parent
    store = RelationStore(directory, options.user, resume=bool(options.reanudar), method="chrome_visible_dom")
    try:
        store.set_profile(profile)
        if not options.reanudar:
            store.set_capture_window(started_at, finished_at)
        directions = DIRECTIONS if options.lista == "ambas" else (options.lista,)
        for direction in directions:
            entry = lists.get(direction)
            if not isinstance(entry, dict) or not isinstance(entry.get("pages"), list):
                store.state(direction, status="unavailable", stop_reason="missing_capture_list")
                continue
            metric = "followers" if direction == "seguidores" else "following"
            for raw_page in entry["pages"]:
                if not isinstance(raw_page, dict) or not isinstance(raw_page.get("users"), list):
                    raise ValueError("Pagina de captura no valida.")
                page = parse_list({"userList": raw_page["users"]})
                store.record_page(direction, page, source="chrome_dom",
                                  max_accounts=options.max_cuentas, observed_at=raw_page.get("observed_at"))
            count = store.count(direction)
            stop_reason = "account_limit" if store.get(direction, {}).get("limit_reached") else ("ui_no_progress" if count else "list_not_loaded")
            store.state(direction, status="partial" if count else "unavailable",
                        stop_reason=stop_reason,
                        advertised_count=entry.get("advertised_count_start", profile.get(metric)),
                        advertised_count_end=entry.get("advertised_count_end", profile.get(metric)),
                        finished_at=finished_at, snapshot_file=options.importar_captura.name)
            print(f"{direction}: {count} cuentas observadas en Chrome; cobertura parcial.", flush=True)
        store.export()
    finally:
        store.close()
    print(f"Resumen: {directory / 'ejecucion.json'}", flush=True)
    return 2  # El importador DOM conserva una muestra, no acredita la lista completa.


async def run(options):
    from playwright.async_api import async_playwright
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    directory = options.reanudar or Path(dataset_dir("user_" + options.user)) / "relaciones" / run_id
    store = RelationStore(directory, options.user, resume=bool(options.reanudar))
    if not store.get("profile"):
        store.set_profile({"username": options.user, "user_id": "", "nickname": "", "observed_at": utcnow()})
    directions = DIRECTIONS if options.lista == "ambas" else (options.lista,)
    print(f"Salida: {directory}", flush=True)
    try:
        async with async_playwright() as pw:
            context = None
            try:
                # El perfil lo gestiona Chrome. Si esta ocupado, se registra el
                # fallo; no se borran locks de un navegador que podria estar vivo.
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=str(options.perfil.resolve()), channel="chrome",
                    headless=options.navegador == "oculto", locale="es-ES",
                    viewport={"width":1280,"height":900},
                )
                if options.cookies.is_file():
                    try:
                        await context.add_cookies(json.loads(options.cookies.read_text(encoding="utf-8")))
                    except Exception:
                        print("No se pudieron cargar las cookies; se usa el estado del perfil.", flush=True)
                for direction in directions:
                    await collect_direction(context, store, direction, options)
            except asyncio.CancelledError:
                for direction in directions:
                    if store.get(direction, {}).get("status") == "running":
                        store.state(direction, status="partial", stop_reason="interrupted", finished_at=utcnow())
                raise
            except Exception as exc:
                print(f"No se pudo preparar el navegador ({type(exc).__name__}).", flush=True)
                for direction in directions:
                    if store.get(direction, {}).get("status") in ("not_requested", "running"):
                        store.state(direction, status="error", stop_reason="browser_unavailable", finished_at=utcnow())
            finally:
                if context:
                    with contextlib.suppress(Exception):
                        await context.close()
    finally:
        result = store.export()
        store.close()
    print(f"Resumen: {directory / 'ejecucion.json'}", flush=True)
    return 0 if all(result["lists"][d]["status"] == "pagination_exhausted" for d in directions) else 2


def main():
    options = parser().parse_args()
    try:
        return import_capture(options) if options.importar_captura else asyncio.run(run(options))
    except KeyboardInterrupt:
        print("Interrumpido; reanuda con --reanudar y la carpeta mostrada.", flush=True)
        return 130
    except ValueError as exc:
        print(str(exc), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
