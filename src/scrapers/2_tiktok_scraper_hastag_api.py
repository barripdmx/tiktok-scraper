# -*- coding: utf-8 -*-
"""
2_tiktok_scraper_hastag_api.py — Scraper híbrido via API interna
================================================================
Estrategia basada en API: en lugar de hacer scroll del DOM,
pagina directamente contra la API interna de TikTok usando page.evaluate(fetch()).

Cómo funciona:
  1. Playwright carga la página UNA VEZ para establecer la sesión.
  2. Las siguientes llamadas usan fetch() desde el contexto del navegador:
     TikTok's JS hooks añaden X-Bogus, msToken y _signature automáticamente.
  3. La API devuelve metadatos completos → NO es necesario visitar cada video.

Ventajas vs 1_tiktok_scraper_hastag.py (DOM scroll):
  • Sin latencia de renderizado por scroll (100 vídeos ~7s vs ~9min)
  • Metadatos completos en la misma llamada API
  • Cobertura más profunda: paginación por cursor directa

Limitaciones:
  • Requiere sesión activa (ejecutar 1-guardar_sesion.py antes)
  • Si TikTok endurece X-Bogus server-side puede requerir re-firma (ver Opción 3)
"""

import os
import re
import csv
import json
import asyncio
import random
import logging
import unicodedata
from datetime import datetime
from urllib.parse import quote, urlencode

from playwright.async_api import async_playwright

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils')))

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
    load_dotenv(env_path)
except Exception:
    pass

from tiktok_utils import (
    is_likely_in_date_range,
    extract_video_id_from_url,
    extract_username_from_url,
    parse_count,
    accept_cookies_banner,
    handle_verification,
    ensure_context as _ensure_context_base,
    collect_video_urls as _collect_video_urls_base,
    save_cookies,
)

# ------------------- CONFIG -------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

COOKIES_PATH = os.path.join(DATA_DIR, "tiktok_cookies.json")
PROFILE_DIR = os.path.join(BASE_DIR, "drivers", "tiktok_profile")

HEADLESS = False
BLOCK_MEDIA = True
PAGE_SIZE = 30      # items por request API (máx ~50 para challenge, ~20 para search)
STRICT_MODE = os.getenv("TIKTOK_STRICT_MODE", "contains").strip().lower() or "contains"
MAX_SCROLL_TAG_FALLBACK = 0
SCROLL_PAUSE = (1.2, 2.0)
NO_NEW_LIMIT = 6

# ------------------- LOGGING -------------------
_LOG_PATH = os.path.join(DATA_DIR, "scraper_hastag_api.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ------------------- CONTEXT WRAPPER -------------------

async def ensure_context(pw):
    return await _ensure_context_base(pw, PROFILE_DIR, COOKIES_PATH, HEADLESS, BLOCK_MEDIA)


async def collect_video_urls(context, url, max_scroll=MAX_SCROLL_TAG_FALLBACK):
    return await _collect_video_urls_base(
        context, url, max_scroll, SCROLL_PAUSE, NO_NEW_LIMIT, COOKIES_PATH
    )


# ------------------- IN-BROWSER FETCH -------------------

async def api_fetch(page, url: str) -> dict:
    """
    Ejecuta fetch(url) DENTRO del contexto del navegador.
    TikTok's JS interceptors añaden X-Bogus, _signature y msToken automáticamente.
    Devuelve el JSON o un dict con '_error' si falla.
    """
    result = await page.evaluate(
        """async (url) => {
            try {
                const r = await fetch(url, {credentials: 'include'});
                if (!r.ok) return {_error: r.status, _url: url};
                const ct = r.headers.get('content-type') || '';
                if (!ct.includes('json')) return {_error: 'not-json', _url: url};
                return await r.json();
            } catch(e) {
                return {_error: String(e), _url: url};
            }
        }""",
        url,
    )
    return result or {}


# ------------------- CHALLENGE ID -------------------

async def get_challenge_id(page, tag: str) -> str:
    """
    Navega a /tag/{tag} y extrae el challengeID del JSON embebido.
    Devuelve string vacío si no se encuentra.
    """
    tag_url = f"https://www.tiktok.com/tag/{quote(tag)}"
    await page.goto(tag_url, timeout=60000, wait_until="domcontentloaded")
    await accept_cookies_banner(page)
    await asyncio.sleep(2)

    challenge_id = await page.evaluate("""() => {
        const pickDigits = (value) => {
            if (value == null) return '';
            const s = String(value);
            return /^\\d{6,}$/.test(s) ? s : '';
        };

        const visit = (node, depth = 0) => {
            if (!node || depth > 6) return '';
            if (Array.isArray(node)) {
                for (const item of node) {
                    const found = visit(item, depth + 1);
                    if (found) return found;
                }
                return '';
            }
            if (typeof node !== 'object') return '';

            for (const [key, value] of Object.entries(node)) {
                const lowerKey = String(key).toLowerCase();
                if (lowerKey === 'challengeid' || lowerKey === 'challenge_id' || lowerKey === 'cid') {
                    const direct = pickDigits(value);
                    if (direct) return direct;
                }
                if (lowerKey === 'challenge' && value && typeof value === 'object') {
                    const nested = pickDigits(value.id || value.challengeId || value.challenge_id);
                    if (nested) return nested;
                }
                if (value && typeof value === 'object') {
                    const found = visit(value, depth + 1);
                    if (found) return found;
                }
            }
            return '';
        };

        const tryJsonText = (text) => {
            if (!text) return '';
            try {
                return visit(JSON.parse(text));
            } catch (e) {
                return '';
            }
        };

        const candidates = [
            document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent || '',
            document.getElementById('__NEXT_DATA__')?.textContent || '',
            document.getElementById('SIGI_STATE')?.textContent || '',
            window.__UNIVERSAL_DATA_FOR_REHYDRATION__ ? JSON.stringify(window.__UNIVERSAL_DATA_FOR_REHYDRATION__) : '',
            window.__NEXT_DATA__ ? JSON.stringify(window.__NEXT_DATA__) : '',
            window.SIGI_STATE ? JSON.stringify(window.SIGI_STATE) : '',
        ];

        for (const text of candidates) {
            const found = tryJsonText(text);
            if (found) return found;
        }

        const html = document.documentElement?.outerHTML || '';
        const regexes = [
            /"challengeID":"?(\\d{6,})"?/i,
            /"challengeId":"?(\\d{6,})"?/i,
            /"cid":"?(\\d{6,})"?/i,
            /challengeID=?(\\d{6,})/i,
        ];
        for (const rx of regexes) {
            const match = html.match(rx);
            if (match) return match[1];
        }

        return '';
    }""")
    return str(challenge_id or "").strip()


# ------------------- PAGINATE CHALLENGE (HASHTAG) -------------------

async def collect_from_challenge(page, challenge_id: str, tag: str, max_videos: int = 0) -> list:
    """
    Pagina /api/challenge/item_list/ y devuelve lista de item dicts con metadatos completos.
    """
    base_params = {
        "aid": "1988",
        "app_language": "es",
        "app_name": "tiktok_web",
        "challengeID": challenge_id,
        "count": PAGE_SIZE,
        "device_platform": "web_pc",
        "from_page": "hashtag",
        "region": "ES",
    }

    items = {}
    cursor = 0
    page_num = 0
    consecutive_empty = 0

    while True:
        page_num += 1
        params = {**base_params, "cursor": cursor}
        url = f"https://www.tiktok.com/api/challenge/item_list/?{urlencode(params)}"

        data = await api_fetch(page, url)

        if "_error" in data:
            log.warning("challenge_api_error tag=%s page=%d err=%s", tag, page_num, data.get("_error"))
            break

        batch = data.get("itemList") or []
        has_more = bool(data.get("hasMore"))
        next_cursor = data.get("cursor", cursor + len(batch))

        new_count = 0
        for item in batch:
            vid = item.get("id", "")
            if vid and vid not in items:
                items[vid] = item
                new_count += 1

        log.info("challenge tag=%s page=%d cursor=%d +%d acc=%d has_more=%s",
                 tag, page_num, cursor, new_count, len(items), has_more)
        print(f"      página {page_num:3d} | cursor={cursor:6d} | +{new_count:3d} | acumulado={len(items)}")

        if new_count == 0:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                print(f"      ✅ 3 páginas sin nuevos, fin")
                break
        else:
            consecutive_empty = 0

        if not has_more or not batch:
            break
        if max_videos and len(items) >= max_videos:
            break

        cursor = next_cursor
        await asyncio.sleep(random.uniform(0.3, 0.8))

    return list(items.values())


# ------------------- PAGINATE SEARCH -------------------

async def collect_from_search(page, keyword: str, max_videos: int = 0) -> list:
    """
    Navega a la página de búsqueda y pagina /api/search/general/full/.
    Devuelve lista de item dicts.
    """
    search_url = f"https://www.tiktok.com/search/video?q={quote(keyword)}"
    await page.goto(search_url, timeout=60000, wait_until="domcontentloaded")
    await accept_cookies_banner(page)
    await asyncio.sleep(2)

    base_params = {
        "aid": "1988",
        "app_language": "es",
        "app_name": "tiktok_web",
        "device_platform": "web_pc",
        "keyword": keyword,
        "count": 20,
        "region": "ES",
        "search_source": "switch_tab",
        "type": "1",
    }

    items = {}
    offset = 0
    page_num = 0
    consecutive_empty = 0
    last_offset = -1

    while True:
        page_num += 1
        params = {**base_params, "offset": offset}
        url = f"https://www.tiktok.com/api/search/general/full/?{urlencode(params)}"

        data = await api_fetch(page, url)

        if "_error" in data:
            log.warning("search_api_error kw=%s page=%d err=%s", keyword, page_num, data.get("_error"))
            break

        batch_raw = data.get("data") or []
        has_more = bool(data.get("has_more"))
        next_offset = data.get("cursor", offset + len(batch_raw))

        new_count = 0
        for entry in batch_raw:
            # type=1 son vídeos; ignorar perfiles, hashtags, etc.
            if entry.get("type") != 1:
                continue
            item = entry.get("item", {})
            vid = item.get("id", "")
            if vid and vid not in items:
                items[vid] = item
                new_count += 1

        log.info("search kw=%s page=%d offset=%d +%d acc=%d has_more=%s",
                 keyword, page_num, offset, new_count, len(items), has_more)
        print(f"      página {page_num:3d} | offset={offset:6d} | +{new_count:3d} | acumulado={len(items)}")

        if new_count == 0:
            consecutive_empty += 1
            if consecutive_empty >= 3:
                print(f"      ✅ 3 páginas sin nuevos, fin")
                break
        else:
            consecutive_empty = 0

        count_requested = int(base_params["count"])
        offset_advanced = isinstance(next_offset, int) and next_offset > offset
        looks_truncated = len(batch_raw) >= count_requested and offset_advanced

        if not batch_raw:
            break
        if max_videos and len(items) >= max_videos:
            break
        if not offset_advanced or next_offset == last_offset:
            break
        if not has_more and not looks_truncated:
            break

        last_offset = offset
        offset = next_offset
        await asyncio.sleep(random.uniform(0.3, 0.8))

    return list(items.values())


# ------------------- ITEM → ROW -------------------

def item_to_row(item: dict, video_url: str) -> dict:
    """Convierte un item de la API al formato CSV estándar del proyecto."""
    stats = item.get("stats", {})
    video_obj = item.get("video", {})
    author_obj = item.get("author", {})
    music = item.get("music", {})
    video_desc = item.get("desc", "")

    create_time = None
    ct = item.get("createTime")
    if ct:
        try:
            create_time = datetime.fromtimestamp(int(ct))
        except Exception:
            pass

    hashtags = []
    for te in item.get("textExtra", []) or []:
        if te.get("hashtagName"):
            hashtags.append(te["hashtagName"])
    hashtags.extend(re.findall(r"#(\w+)", video_desc))
    hashtags = list(dict.fromkeys(hashtags))

    return {
        "video_id": str(item.get("id", "")),
        "video_url": video_url,
        "video_desc": video_desc[:500],
        "video_fecha": create_time.strftime("%d-%m-%Y %H:%M:%S") if create_time else "",
        "video_duracion_seg": int(video_obj.get("duration", 0) or 0),
        "video_width": int(video_obj.get("width", 0) or 0),
        "video_height": int(video_obj.get("height", 0) or 0),
        "video_likes": int(stats.get("diggCount", 0) or 0),
        "video_vistas": int(stats.get("playCount", 0) or 0),
        "video_compartidos": int(stats.get("shareCount", 0) or 0),
        "video_comentarios": int(stats.get("commentCount", 0) or 0),
        "video_guardados": int(stats.get("collectCount", 0) or 0),
        "username": author_obj.get("uniqueId", ""),
        "author_nickname": author_obj.get("nickname", ""),
        "author_verified": "Sí" if author_obj.get("verified") else "No",
        "music_title": music.get("title", ""),
        "music_author": music.get("authorName", ""),
        "hashtags": "|".join(hashtags),
        "_create_dt": create_time,
    }


async def extract_metadata(context, url: str) -> dict:
    """
    Fallback DOM: visita el vídeo y extrae metadatos desde el JSON embebido.
    """
    page = await context.new_page()
    try:
        await page.goto(url, timeout=60000)
        await accept_cookies_banner(page)
        await asyncio.sleep(1)

        video_id = extract_video_id_from_url(url)
        raw = await page.evaluate("""() => {
            const ids = ['__UNIVERSAL_DATA_FOR_REHYDRATION__', 'SIGI_STATE', '__NEXT_DATA__'];
            for (const id of ids) {
                const el = document.getElementById(id);
                if (el && el.textContent) return el.textContent;
            }
            return null;
        }""")

        item = {}
        stats = {}
        video_obj = {}
        author_obj = {}
        music = {}
        video_desc = ""
        create_time = None

        if raw:
            try:
                data = json.loads(raw)
                scope = data.get("__DEFAULT_SCOPE__", {}) if isinstance(data, dict) else {}
                detail = scope.get("webapp.video-detail", {}) if isinstance(scope, dict) else {}
                item = detail.get("itemInfo", {}).get("itemStruct", {}) if isinstance(detail, dict) else {}

                if item:
                    stats = item.get("stats", {})
                    video_obj = item.get("video", {})
                    author_obj = item.get("author", {})
                    music = item.get("music", {})
                    video_desc = item.get("desc", "")
                    ct = item.get("createTime")
                    if ct:
                        try:
                            create_time = datetime.fromtimestamp(int(ct))
                        except Exception:
                            pass
            except Exception:
                pass

        hashtags = []
        for te in item.get("textExtra", []) or []:
            if te.get("hashtagName"):
                hashtags.append(te["hashtagName"])
        hashtags.extend(re.findall(r"#(\w+)", video_desc))
        hashtags = list(dict.fromkeys(hashtags))

        if not stats.get("diggCount") and not stats.get("playCount"):
            async def _html_count(selectors):
                for sel in selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            val = parse_count(await el.text_content())
                            if val > 0:
                                return val
                    except Exception:
                        pass
                return 0

            html_likes = await _html_count(['[data-e2e="like-count"]', 'strong[data-e2e="like-count"]', '[data-e2e="browse-like-count"]'])
            html_views = await _html_count(['strong[data-e2e="video-views"]', '[data-e2e="video-views"]', '[class*="playCount"]'])
            html_comments = await _html_count(['[data-e2e="comment-count"]', '[data-e2e="browse-comment-count"]'])
            html_shares = await _html_count(['[data-e2e="share-count"]', '[data-e2e="browse-share-count"]'])
            html_saves = await _html_count(['[data-e2e="collect-count"]', '[data-e2e="favorite-count"]'])
            if html_likes or html_views:
                stats = {
                    "diggCount": html_likes,
                    "playCount": html_views,
                    "commentCount": html_comments,
                    "shareCount": html_shares,
                    "collectCount": html_saves,
                }

        return {
            "video_id": str(video_id),
            "video_url": url,
            "video_desc": video_desc[:500],
            "video_fecha": create_time.strftime("%d-%m-%Y %H:%M:%S") if create_time else "",
            "video_duracion_seg": int(video_obj.get("duration", 0) or 0),
            "video_width": int(video_obj.get("width", 0) or 0),
            "video_height": int(video_obj.get("height", 0) or 0),
            "video_likes": int(stats.get("diggCount", 0) or 0),
            "video_vistas": int(stats.get("playCount", 0) or 0),
            "video_compartidos": int(stats.get("shareCount", 0) or 0),
            "video_comentarios": int(stats.get("commentCount", 0) or 0),
            "video_guardados": int(stats.get("collectCount", 0) or 0),
            "username": author_obj.get("uniqueId", "") or extract_username_from_url(url),
            "author_nickname": author_obj.get("nickname", ""),
            "author_verified": "Sí" if author_obj.get("verified") else "No",
            "music_title": music.get("title", ""),
            "music_author": music.get("authorName", ""),
            "hashtags": "|".join(hashtags),
            "_create_dt": create_time,
        }
    finally:
        await page.close()


# ------------------- FILTRO ESTRICTO LITERAL -------------------

def normalize_match_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower()


def matches_query(query_terms: list, desc: str, hashtags_str: str, mode: str = "contains") -> bool:
    """
    Evalua coincidencia entre la consulta y el contenido del video.

    Modos:
      - exact: palabra completa
      - contains: subcadena normalizada
      - off: siempre True
    """
    mode = (mode or "contains").lower()
    if mode == "off":
        return True

    combined = normalize_match_text(desc + " " + hashtags_str)
    for term in query_terms:
        normalized_term = normalize_match_text(term).strip().lstrip("#")
        if not normalized_term:
            continue
        if mode == "contains":
            if normalized_term in combined:
                return True
            continue

        pattern = r"(?<!\w)" + re.escape(normalized_term) + r"(?!\w)"
        if re.search(pattern, combined):
            return True
    return False


# ------------------- GUARDAR -------------------

def save_results(label: str, rows: list) -> dict:
    fields = [
        "video_id", "video_url", "video_desc", "video_fecha", "video_duracion_seg",
        "video_width", "video_height", "video_likes", "video_vistas", "video_compartidos",
        "video_comentarios", "video_guardados", "username", "author_nickname",
        "author_verified", "music_title", "music_author", "hashtags",
    ]

    json_path = os.path.join(DATA_DIR, f"{label}_videos_api.json")
    csv_path  = os.path.join(DATA_DIR, f"{label}_videos_api.csv")

    # JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)

    # CSV
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore",
                           quoting=csv.QUOTE_NONNUMERIC)
        w.writeheader()
        w.writerows(rows)

    print(f"\n📁 JSON: {json_path}")
    print(f"📄 CSV:  {csv_path}")
    return {"json": json_path, "csv": csv_path}


# ------------------- MAIN -------------------

async def main():
    print("=" * 60)
    print("TikTok Scraper API Híbrido — Opción 2")
    print("Pagina la API directamente (sin scroll DOM)")
    print("=" * 60)

    query_raw = input("\n🔍 Término(s) exactos (sin #, separados por coma): ").strip()
    try:
        terms = next(csv.reader([query_raw], skipinitialspace=True))
        terms = [t.strip() for t in terms if t and t.strip()]
    except Exception:
        terms = [t.strip() for t in query_raw.split(",") if t.strip()]
    if not terms:
        return

    start_str = input("📅 Fecha inicio (dd-mm-aaaa) o Enter: ").strip()
    end_str   = input("📅 Fecha fin (dd-mm-aaaa) o Enter: ").strip()

    def parse_date(s):
        try:
            return datetime.strptime(s.strip(), "%d-%m-%Y") if s.strip() else None
        except Exception:
            return None

    start_dt = parse_date(start_str)
    end_dt   = parse_date(end_str)
    label    = "_".join(t.replace(" ", "_") for t in terms[:3])

    if start_dt or end_dt:
        print(f"\n⏱️ Fechas: {start_dt.strftime('%d-%m-%Y') if start_dt else '∞'} → "
              f"{end_dt.strftime('%d-%m-%Y') if end_dt else '∞'}")
    if STRICT_MODE != "off":
        print(f"🎯 Filtro activo ({STRICT_MODE}) para: {', '.join(terms)}")

    log.info("Inicio API scraper | terms=%s start=%s end=%s", terms,
             start_dt.date() if start_dt else None, end_dt.date() if end_dt else None)

    all_items = {}  # video_id → item dict (API)
    dom_rows = {}   # video_id → row dict (fallback DOM)

    async with async_playwright() as pw:
        context = await ensure_context(pw)
        # Una sola página para todo — sin cargar N páginas individuales
        page = await context.new_page()
        try:
            for term in terms:
                print(f"\n{'─'*50}")
                print(f"🔎 Término: {term}")

                # Búsqueda
                print("  [búsqueda]")
                before = len(all_items)
                search_items = await collect_from_search(page, term)
                for it in search_items:
                    vid = it.get("id", "")
                    if vid and vid not in all_items:
                        all_items[vid] = it
                print(f"  → búsqueda: {len(search_items)} | +{len(all_items)-before} nuevos")

                # Hashtag
                print("  [hashtag]")
                before2 = len(all_items)
                challenge_id = await get_challenge_id(page, term)
                if challenge_id:
                    tag_items = await collect_from_challenge(page, challenge_id, term)
                    for it in tag_items:
                        vid = it.get("id", "")
                        if vid and vid not in all_items:
                            all_items[vid] = it
                    print(f"  → hashtag: {len(tag_items)} | +{len(all_items)-before2} nuevos")
                else:
                    print(f"  ⚠️ challengeID no encontrado para #{term}")
                    print("  ↩ fallback DOM en /tag/... para recuperar más vídeos")
                    tag_url = f"https://www.tiktok.com/tag/{quote(term)}"
                    try:
                        dom_urls = await collect_video_urls(context, tag_url)
                    except Exception as e:
                        dom_urls = []
                        log.warning("tag_dom_fallback_error term=%s err=%s", term, str(e)[:160])

                    new_dom = 0
                    print(f"  → fallback DOM URLs: {len(dom_urls)}")
                    for idx, url in enumerate(dom_urls, 1):
                        vid = extract_video_id_from_url(url)
                        if not vid or vid in all_items or vid in dom_rows:
                            continue
                        try:
                            row = await extract_metadata(context, url)
                        except Exception as e:
                            log.warning("tag_dom_metadata_error term=%s url=%s err=%s", term, url, str(e)[:160])
                            continue

                        row_vid = row.get("video_id", "")
                        if row_vid:
                            dom_rows[row_vid] = row
                            new_dom += 1
                        if idx % 10 == 0:
                            print(f"      fallback DOM procesados: {idx}/{len(dom_urls)} | +{new_dom} metadatos")
                        await asyncio.sleep(random.uniform(0.3, 0.8))

                    print(f"  → hashtag DOM: {len(dom_urls)} URLs | +{new_dom} metadatos nuevos")

        finally:
            await page.close()
            await save_cookies(context, COOKIES_PATH)
            await context.close()

    print(f"\n📊 Total único de la API: {len(all_items)} vídeos")
    if dom_rows:
        print(f"📊 Total extra por DOM:    {len(dom_rows)} vídeos")

    # ---- Post-procesado: filtros de fecha y estricto ----
    rows = []
    skipped_date = 0
    skipped_strict = 0
    skipped_id = 0

    for vid, item in all_items.items():
        author = item.get("author", {}).get("uniqueId", "")
        if not author or not vid:
            skipped_id += 1
            continue
        video_url = f"https://www.tiktok.com/@{author}/video/{vid}"

        row = item_to_row(item, video_url)
        create_dt = row.pop("_create_dt", None)

        # Filtro fecha exacto (los datos de la API son precisos)
        if create_dt:
            if start_dt and create_dt.date() < start_dt.date():
                skipped_date += 1
                continue
            if end_dt and create_dt.date() > end_dt.date():
                skipped_date += 1
                continue

        # Filtro de coincidencia
        if STRICT_MODE != "off":
            desc = row.get("video_desc", "")
            tags = row.get("hashtags", "")
            if desc or tags:
                if not matches_query(terms, desc, tags, STRICT_MODE):
                    skipped_strict += 1
                    continue

        rows.append(row)

    for vid, row in dom_rows.items():
        if any(r.get("video_id") == vid for r in rows):
            continue

        create_dt = row.pop("_create_dt", None)

        if create_dt:
            if start_dt and create_dt.date() < start_dt.date():
                skipped_date += 1
                continue
            if end_dt and create_dt.date() > end_dt.date():
                skipped_date += 1
                continue

        if STRICT_MODE != "off":
            desc = row.get("video_desc", "")
            tags = row.get("hashtags", "")
            if desc or tags:
                if not matches_query(terms, desc, tags, STRICT_MODE):
                    skipped_strict += 1
                    continue

        rows.append(row)

    print(f"   Sin author/id:            {skipped_id}")
    print(f"   Descartados por fecha:    {skipped_date}")
    print(f"   Descartados por estricto: {skipped_strict}")
    print(f"   ✅ Vídeos válidos:        {len(rows)}")

    if rows:
        save_results(label, rows)
        total_likes = sum(r["video_likes"] for r in rows)
        total_views = sum(r["video_vistas"] for r in rows)
        print(f"\n📈 RESUMEN:")
        print(f"   Vídeos: {len(rows)}")
        print(f"   Likes:  {total_likes:,}")
        print(f"   Views:  {total_views:,}")
        log.info("Fin | saved=%d skipped_date=%d skipped_strict=%d", len(rows), skipped_date, skipped_strict)
    else:
        print("\n⚠️ No se encontraron vídeos válidos")


if __name__ == "__main__":
    asyncio.run(main())
