# -*- coding: utf-8 -*-
"""
tiktok_utils.py — Funciones compartidas entre los scrapers de TikTok.

Importar desde los scrapers:
    from tiktok_utils import (
        get_date_from_video_id, estimate_date_from_id_simple,
        is_likely_in_date_range, is_in_date_range,
        extract_video_id_from_url, extract_username_from_url,
        is_valid_video_url, parse_count,
        human_scroll, accept_cookies_banner, handle_verification,
        detect_end_of_results,
        load_cookies, save_cookies, ensure_context,
        collect_video_urls,
    )
"""

import os
import re
import glob
import json
import asyncio
import random
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# FECHA DESDE ID (Snowflake timestamp: id >> 32 = segundos Unix)
# ---------------------------------------------------------------------------

def get_date_from_video_id(video_id: str) -> datetime:
    """Extrae la fecha aproximada del ID del video (id >> 32 = timestamp Unix)."""
    try:
        vid = int(str(video_id).replace("'", "").strip())
        return datetime.fromtimestamp(vid >> 32)
    except Exception:
        return None


# Alias usado en 1_tiktok_scraper_user.py
get_date_from_id = get_date_from_video_id


def estimate_date_from_id_simple(video_id: str) -> datetime:
    """
    Estimación alternativa basada en el prefijo del ID (primeros 3 dígitos).
    Activo cuando el shift de 32 bits falla (IDs sin timestamp estándar).

    Rangos calibrados a 2026-05 (id >> 32 = unix timestamp):
        prefix >= 772 → 2027-01
        prefix >= 771 → 2026-12
        prefix >= 768 → 2026-09
        prefix >= 764 → 2026-06
        prefix >= 761 → 2026-03
        prefix >= 759 → 2026-01
        prefix >= 757 → 2025-12
        prefix >= 754 → 2025-09
        prefix >= 751 → 2025-06
        prefix >= 745 → 2025-01
        prefix >= 737 → 2024-06
        prefix >= 731 → 2024-01
        prefix >= 718 → 2023-01
        prefix >= 704 → 2022-01
        prefix >= 691 → 2021-01
        else          → 2020-01
    """
    try:
        vid = str(video_id).replace("'", "")
        prefix = int(vid[:3]) if len(vid) >= 3 else 0

        if prefix >= 772:
            return datetime(2027, 1, 1)
        elif prefix >= 771:
            return datetime(2026, 12, 1)
        elif prefix >= 768:
            return datetime(2026, 9, 1)
        elif prefix >= 764:
            return datetime(2026, 6, 1)
        elif prefix >= 761:
            return datetime(2026, 3, 1)
        elif prefix >= 759:
            return datetime(2026, 1, 1)
        elif prefix >= 757:
            return datetime(2025, 12, 1)
        elif prefix >= 754:
            return datetime(2025, 9, 1)
        elif prefix >= 751:
            return datetime(2025, 6, 1)
        elif prefix >= 745:
            return datetime(2025, 1, 1)
        elif prefix >= 737:
            return datetime(2024, 6, 1)
        elif prefix >= 731:
            return datetime(2024, 1, 1)
        elif prefix >= 718:
            return datetime(2023, 1, 1)
        elif prefix >= 704:
            return datetime(2022, 1, 1)
        elif prefix >= 691:
            return datetime(2021, 1, 1)
        else:
            return datetime(2020, 1, 1)
    except Exception:
        return None


def is_likely_in_date_range(
    video_id: str,
    start_dt: datetime,
    end_dt: datetime,
    margin_days: int = 2,
) -> bool:
    """Filtro previo con margen de error para no descartar videos en el límite."""
    if not start_dt and not end_dt:
        return True

    estimated = get_date_from_video_id(video_id) or estimate_date_from_id_simple(video_id)
    if not estimated:
        return True  # Si no se puede estimar, incluir por precaución

    margin = timedelta(days=margin_days)
    if start_dt and estimated.date() < (start_dt - margin).date():
        return False
    if end_dt and estimated.date() > (end_dt + margin).date():
        return False
    return True


def is_in_date_range(
    video_id: str,
    start_dt: datetime,
    end_dt: datetime,
) -> bool:
    """Filtro exacto sin margen (usado en el scraper de usuarios)."""
    if not start_dt and not end_dt:
        return True

    video_date = get_date_from_video_id(video_id)
    if not video_date:
        return True

    if start_dt and video_date.date() < start_dt.date():
        return False
    if end_dt and video_date.date() > end_dt.date():
        return False
    return True


# ---------------------------------------------------------------------------
# UTILIDADES DE URL
# ---------------------------------------------------------------------------

def normalize_tiktok_url(url: str) -> str:
    """
    Normaliza una URL de TikTok eliminando parámetros de tracking y fragmentos.
    No resuelve URLs cortas (vm.tiktok.com / vt.tiktok.com) — requeriría HTTP.
    """
    if not url:
        return ""
    # Eliminar query-string y fragmento
    url = url.split("?")[0].split("#")[0]
    # Asegurar protocolo
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("/"):
        url = "https://www.tiktok.com" + url
    return url


def extract_video_id_from_url(url: str) -> str:
    """Extrae el ID numérico de una URL de vídeo de TikTok.

    Soporta los formatos:
    - https://www.tiktok.com/@user/video/1234567890123456789
    - https://www.tiktok.com/@user/video/1234567890123456789?foo=bar
    - /t/XXXXXXXXXX/  (formato corto — no se puede resolver sin HTTP)
    """
    url = normalize_tiktok_url(url or "")
    m = re.search(r'/video/(\d+)', url)
    return m.group(1) if m else ""


def extract_username_from_url(url: str) -> str:
    url = normalize_tiktok_url(url or "")
    m = re.search(r'/@([^/]+)/video/', url)
    return m.group(1) if m else ""


def is_valid_video_url(url: str) -> bool:
    """Valida que la URL contenga un ID numérico de al menos 15 dígitos."""
    if not url or "/video/" not in (url or ""):
        return False
    try:
        video_id = normalize_tiktok_url(url).split("/video/")[-1].split("/")[0]
        return video_id.isdigit() and len(video_id) >= 15
    except Exception:
        return False


# ---------------------------------------------------------------------------
# MÉTRICAS
# ---------------------------------------------------------------------------

def parse_count(text: str) -> int:
    """Convierte '1.2M', '500K', '1.234' a entero. Usado en fallback HTML."""
    if not text:
        return 0
    text = text.strip().upper().replace(',', '.')
    try:
        if 'M' in text:
            return int(float(text.replace('M', '')) * 1_000_000)
        elif 'K' in text:
            return int(float(text.replace('K', '')) * 1_000)
        else:
            cleaned = re.sub(r'[^\d]', '', text)
            return int(cleaned) if cleaned else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# PLAYWRIGHT HELPERS (no dependen de config del scraper)
# ---------------------------------------------------------------------------

async def human_scroll(page) -> None:
    """Scroll humanizado alternando rueda, teclado y elemento para reducir detección."""
    technique = random.choice(["wheel", "wheel", "wheel", "keyboard", "element"])
    try:
        if technique == "wheel":
            await page.mouse.wheel(0, random.randint(400, 800))
        elif technique == "keyboard":
            key = random.choice(["PageDown", "PageDown", "End", "ArrowDown"])
            await page.keyboard.press(key)
            if key == "ArrowDown":
                for _ in range(random.randint(3, 8)):
                    await asyncio.sleep(0.1)
                    await page.keyboard.press("ArrowDown")
        elif technique == "element":
            videos = await page.query_selector_all('a[href*="/video/"]')
            if videos and len(videos) > 5:
                await videos[-1].scroll_into_view_if_needed()
    except Exception:
        try:
            await page.evaluate(f"window.scrollBy(0, {random.randint(400, 800)})")
        except Exception:
            pass


async def accept_cookies_banner(page):
    for sel in [
        'button:has-text("Aceptar todo")',
        'button:has-text("Accept all")',
        'button:has-text("I agree")',
    ]:
        try:
            b = await page.query_selector(sel)
            if b:
                await b.click()
                await asyncio.sleep(0.4)
                break
        except Exception:
            pass


async def handle_verification(page, max_wait: int = 90) -> bool:
    sels = [
        'div[id*="captcha"]',
        'div[class*="captcha"]',
        'div[class*="verify"]',
        'div[class*="secsdk"]',
    ]
    waited = 0
    while waited < max_wait:
        found = False
        for sel in sels:
            try:
                if await page.query_selector(sel):
                    found = True
                    break
            except Exception:
                pass
        if not found:
            return True
        await asyncio.sleep(1)
        waited += 1
    return False


async def detect_end_of_results(page) -> bool:
    selectors = [
        '[data-e2e="search-no-result"]',
        '[data-e2e="search-common-no-result"]',
        '[data-e2e="search-no-result-video"]',
    ]
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return True
        except Exception:
            pass
    try:
        el = await page.query_selector(
            "text=/no more results|no more videos|you\\'ve reached the end"
            "|no results|no videos|no se encontraron|sin resultados"
            "|fin de los resultados|no hay m[aá]s|has llegado al final/i"
        )
        if el and await el.is_visible():
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# GESTIÓN DE COOKIES Y CONTEXTO (parametrizados)
# ---------------------------------------------------------------------------

async def load_cookies(context, cookies_path: str) -> None:
    if os.path.exists(cookies_path):
        try:
            with open(cookies_path, "r", encoding="utf-8") as f:
                await context.add_cookies(json.load(f))
            print("🍪 Cookies cargadas")
        except Exception:
            pass


async def save_cookies(context, cookies_path: str) -> None:
    try:
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(await context.cookies(), f)
    except Exception:
        pass


def _release_profile_locks(profile_dir: str) -> None:
    """Elimina los archivos LOCK de instancia de Chrome que bloquean el arranque."""
    # Solo los dos LOCK críticos de instancia; los de leveldb son seguros
    critical = [
        os.path.join(profile_dir, "LOCK"),
        os.path.join(profile_dir, "Default", "LOCK"),
    ]
    for path in critical:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


async def ensure_context(
    pw,
    profile_dir: str,
    cookies_path: str,
    headless: bool = False,
    block_media: bool = True,
):
    """Lanza un contexto persistente de Chromium con cookies y configuración antibot."""
    _release_profile_locks(profile_dir)

    # Usamos channel="chrome" (Chrome del sistema) porque el perfil fue creado
    # con Google Chrome y el Chromium bundled de Playwright es mucho más antiguo.
    # Con headless=False, Chromium bundled crashea al abrir un perfil de Chrome 143+.
    launch_kwargs = dict(
        user_data_dir=profile_dir,
        headless=headless,
        channel="chrome",
        args=[
            '--disable-blink-features=AutomationControlled',
            '--window-size=1280,900',
        ],
        ignore_default_args=['--enable-automation'],
        viewport={'width': 1280, 'height': 900},
        user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/134.0.0.0 Safari/537.36'
        ),
    )

    try:
        context = await pw.chromium.launch_persistent_context(**launch_kwargs)
    except Exception:
        await asyncio.sleep(2)
        _release_profile_locks(profile_dir)
        context = await pw.chromium.launch_persistent_context(**launch_kwargs)

    if block_media:
        async def _route_handler(route):
            if route.request.resource_type in {"image", "media", "font"}:
                return await route.abort()
            return await route.continue_()
        await context.route("**/*", _route_handler)

    page = await context.new_page()
    await load_cookies(context, cookies_path)
    await page.goto("https://www.tiktok.com", timeout=60000)
    await accept_cookies_banner(page)
    await handle_verification(page, 30)
    await save_cookies(context, cookies_path)
    await page.close()
    return context


# ---------------------------------------------------------------------------
# RECOLECCIÓN DE URLs (parámetros configurables por scraper)
# ---------------------------------------------------------------------------

async def collect_video_urls(
    context,
    url: str,
    max_scroll: int = 0,
    scroll_pause: tuple = (1.2, 2.0),
    no_new_limit: int = 3,
    cookies_path: str = None,
) -> list:
    """
    Recorre una página de búsqueda o hashtag de TikTok recolectando URLs de vídeos.

    Args:
        max_scroll: Límite de scrolls (0 = sin límite).
        scroll_pause: (min, max) segundos entre scrolls.
        no_new_limit: Ciclos sin nuevas URLs antes de considerar fin del contenido.
    """
    page = await context.new_page()
    print(f"🌍 Abriendo {url}")
    await page.goto(url, timeout=60000)
    await accept_cookies_banner(page)
    await handle_verification(page, 30)

    if "/search" in url:
        try:
            tab = await page.query_selector('button[data-e2e="search-tab-video"]')
            if tab:
                await tab.click()
                await asyncio.sleep(2)
        except Exception:
            pass

    video_urls = set()
    prev_count, no_new = 0, 0
    _max = max_scroll if max_scroll and max_scroll > 0 else None
    i = 0

    while True:
        i += 1
        for sel in ['a[href*="/video/"]', 'div[data-e2e*="video"] a']:
            try:
                for a in await page.query_selector_all(sel):
                    href = await a.get_attribute("href")
                    if href and "/video/" in href:
                        if href.startswith("//"): href = f"https:{href}"
                        elif href.startswith("/"): href = f"https://www.tiktok.com{href}"
                        clean = href.split("?")[0]
                        if is_valid_video_url(clean):
                            video_urls.add(clean)
            except Exception:
                pass

        cur = len(video_urls)
        total_label = str(_max) if _max else "∞"
        print(f"Scroll {i}/{total_label} -> {cur} videos")

        if await detect_end_of_results(page):
            print("✅ Fin del contenido (aviso de TikTok)")
            break

        if cur == prev_count:
            no_new += 1
            if no_new >= no_new_limit and cur > 0:
                print("✅ Fin del contenido")
                break
        else:
            no_new = 0

        if _max and i >= _max:
            break

        await human_scroll(page)
        await asyncio.sleep(random.uniform(*scroll_pause))
        prev_count = cur

    if cookies_path:
        await save_cookies(context, cookies_path)
    await page.close()
    return list(video_urls)
