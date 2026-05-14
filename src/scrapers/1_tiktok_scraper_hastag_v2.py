# -*- coding: utf-8 -*-
"""
TikTok Scraper v2 - BÚSQUEDA ESTRICTA LITERAL
=============================================
Recolecta videos desde búsqueda y página de hashtag, pero SOLO guarda
los que contienen la consulta de forma literal exacta en texto o hashtags.

No acepta parecidos ni variantes:
- 'hidrosismo' NO coincide con 'hidrosismos'
- 'hidrosismo' NO coincide con 'hydroseismic'

NOTA: La fecha extraída del ID es aproximada (±1 día) pero suficiente
para filtrar la mayoría de videos antiguos sin visitarlos.
"""

import os
import re
import csv
import json
import asyncio
import random
import logging
from datetime import datetime
from urllib.parse import quote
from playwright.async_api import async_playwright

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils')))

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
    load_dotenv(env_path)
except:
    pass

from tiktok_utils import (
    get_date_from_video_id, estimate_date_from_id_simple, is_likely_in_date_range,
    extract_video_id_from_url, extract_username_from_url, is_valid_video_url, parse_count,
    human_scroll, accept_cookies_banner, handle_verification, detect_end_of_results,
    load_cookies, save_cookies, ensure_context as _ensure_context_base, collect_video_urls as _collect_video_urls_base,
)

# ------------------- CONFIG -------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

COOKIES_PATH = os.path.join(DATA_DIR, "tiktok_cookies.json")
PROFILE_DIR = os.path.join(BASE_DIR, "drivers", "tiktok_profile")

HEADLESS = False
BLOCK_MEDIA = True
MAX_SCROLL_SEARCH = 0  # 0 = sin límite (scroll hasta fin)
SCROLL_PAUSE = (1.2, 2.0)
NO_NEW_LIMIT = 6
STRICT_LITERAL = True

# ------------------- LOGGING -------------------
_LOG_PATH = os.path.join(DATA_DIR, "scraper_hastag_v2.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(_LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ------------------- WRAPPERS DE CONFIG -------------------
async def ensure_context(pw):
    """Wrapper que inyecta la configuración del scraper en ensure_context de tiktok_utils."""
    return await _ensure_context_base(pw, PROFILE_DIR, COOKIES_PATH, HEADLESS, BLOCK_MEDIA)

async def collect_video_urls(context, url, max_scroll=MAX_SCROLL_SEARCH):
    """Wrapper que inyecta scroll_pause y no_new_limit del scraper."""
    return await _collect_video_urls_base(
        context, url, max_scroll, SCROLL_PAUSE, NO_NEW_LIMIT, COOKIES_PATH
    )


# ------------------- EXTRACCIÓN DE METADATOS -------------------
async def extract_metadata(context, url):
    page = await context.new_page()
    try:
        await page.goto(url, timeout=60000)
        await accept_cookies_banner(page)
        await asyncio.sleep(1)

        video_id = extract_video_id_from_url(url)

        raw = await page.evaluate("""() => {
            const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
            return el ? el.textContent : null;
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
                scope = data.get("__DEFAULT_SCOPE__", {})
                detail = scope.get("webapp.video-detail", {})
                item = detail.get("itemInfo", {}).get("itemStruct", {})
                
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
                        except:
                            pass
            except:
                pass

        # Hashtags
        hashtags = []
        for te in item.get("textExtra", []) or []:
            if te.get("hashtagName"):
                hashtags.append(te["hashtagName"])
        hashtags.extend(re.findall(r"#(\w+)", video_desc))
        hashtags = list(dict.fromkeys(hashtags))

        # ---- PIEZA 1: Fallback HTML cuando el JSON no devuelve métricas ----
        if not stats.get("diggCount") and not stats.get("playCount"):
            async def _html_count(selectors):
                for sel in selectors:
                    try:
                        el = await page.query_selector(sel)
                        if el:
                            val = parse_count(await el.text_content())
                            if val > 0:
                                return val
                    except:
                        pass
                return 0
            html_likes    = await _html_count(['[data-e2e="like-count"]', 'strong[data-e2e="like-count"]', '[data-e2e="browse-like-count"]'])
            html_views    = await _html_count(['strong[data-e2e="video-views"]', '[data-e2e="video-views"]', '[class*="playCount"]'])
            html_comments = await _html_count(['[data-e2e="comment-count"]', '[data-e2e="browse-comment-count"]'])
            html_shares   = await _html_count(['[data-e2e="share-count"]', '[data-e2e="browse-share-count"]'])
            html_saves    = await _html_count(['[data-e2e="collect-count"]', '[data-e2e="favorite-count"]'])
            if html_likes or html_views:
                print(f"   ↩ Fallback HTML: {html_likes}👍 {html_views}👁")
                stats = {"diggCount": html_likes, "playCount": html_views,
                         "commentCount": html_comments, "shareCount": html_shares,
                         "collectCount": html_saves}

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

# ------------------- GUARDAR -------------------
def _write_json_csv(json_path, csv_path, rows):
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2, default=str)

    fields = ["video_id","video_url","video_desc","video_fecha","video_duracion_seg",
              "video_width","video_height","video_likes","video_vistas","video_compartidos",
              "video_comentarios","video_guardados","username","author_nickname",
              "author_verified","music_title","music_author","hashtags"]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore', quoting=csv.QUOTE_NONNUMERIC)
        w.writeheader()
        w.writerows(rows)


def save_results(query, rows):
    # Salida v2 estricta (nueva)
    strict_json = os.path.join(DATA_DIR, f"{query}_videos_v2_estricto.json")
    strict_csv = os.path.join(DATA_DIR, f"{query}_videos_v2_estricto.csv")
    _write_json_csv(strict_json, strict_csv, rows)

    # Salida clásica (compatibilidad con tu flujo anterior)
    legacy_json = os.path.join(DATA_DIR, f"{query}_videos.json")
    legacy_csv = os.path.join(DATA_DIR, f"{query}_videos.csv")
    _write_json_csv(legacy_json, legacy_csv, rows)

    print(f"\n📁 JSON v2:     {strict_json}")
    print(f"📄 CSV v2:      {strict_csv}")
    print(f"📁 JSON clásico:{legacy_json}")
    print(f"📄 CSV clásico: {legacy_csv}")

    return {
        "strict_json": strict_json,
        "strict_csv": strict_csv,
        "legacy_json": legacy_json,
        "legacy_csv": legacy_csv,
    }



# ------------------- MAIN -------------------
async def main():
    print("=" * 60)
    print("TikTok Scraper v2 - BÚSQUEDA ESTRICTA LITERAL")
    print("Solo guarda videos con coincidencia EXACTA de la consulta")
    print("Puedes usar varios términos separados por coma: hola,adios")
    print("=" * 60)
    
    query_raw = input("\n🔍 Palabra(s) o hashtag(s) EXACTAS (sin #, separadas por coma): ").strip()
    query_terms = parse_query_terms(query_raw)
    if not query_terms:
        return
    query_label = build_query_label(query_terms)
    report_title = ", ".join(query_terms)
    
    start_str = input("📅 Fecha inicio (dd-mm-aaaa) o Enter para omitir: ").strip()
    end_str = input("📅 Fecha fin (dd-mm-aaaa) o Enter para omitir: ").strip()
    
    def parse_date(s):
        try:
            return datetime.strptime(s.strip(), "%d-%m-%Y") if s.strip() else None
        except:
            return None
    
    start_dt = parse_date(start_str)
    end_dt = parse_date(end_str)
    
    if start_dt or end_dt:
        print(f"\n⏱️ Filtro de fechas: {start_dt.strftime('%d-%m-%Y') if start_dt else 'inicio'} → {end_dt.strftime('%d-%m-%Y') if end_dt else 'fin'}")
        print("   (Se filtrarán videos ANTES de visitarlos basándose en el ID)")
    if STRICT_LITERAL:
        print(f"🎯 Modo estricto OR para términos: {', '.join(query_terms)}")

    log.info("Inicio scraping v2 | terms=%s start=%s end=%s strict=%s",
             query_terms, start_dt.date() if start_dt else None,
             end_dt.date() if end_dt else None, STRICT_LITERAL)

    async with async_playwright() as pw:
        context = await ensure_context(pw)
        try:

            # Recolectar URLs para cada término y combinar sin duplicados
            all_urls_set = set()
            for term in query_terms:
                print(f"\n🔎 Término: {term}")
                search_url = f"https://www.tiktok.com/search/video?q={quote(term)}"
                urls1 = await collect_video_urls(context, search_url)
                print(f"   Búsqueda: {len(urls1)} videos")
                log.info("term=%s search=%d", term, len(urls1))

                tag_url = f"https://www.tiktok.com/tag/{quote(term)}"
                urls2 = await collect_video_urls(context, tag_url)
                print(f"   Hashtag: {len(urls2)} videos")
                log.info("term=%s tag=%d", term, len(urls2))

                before = len(all_urls_set)
                all_urls_set.update(urls1)
                all_urls_set.update(urls2)
                added = len(all_urls_set) - before
                print(f"   +{added} URLs nuevas (acumulado {len(all_urls_set)})")

            all_urls = list(all_urls_set)
            print(f"\n📊 Total único: {len(all_urls)} videos")

            # ========== FILTRO PREVIO POR FECHA ==========
            if start_dt or end_dt:
                filtered_urls = []
                skipped = 0

                for url in all_urls:
                    vid = extract_video_id_from_url(url)
                    if is_likely_in_date_range(vid, start_dt, end_dt, margin_days=3):
                        filtered_urls.append(url)
                    else:
                        skipped += 1

                print(f"🗓️ Pre-filtrado: {len(filtered_urls)} posibles en rango, {skipped} descartados")
                all_urls = filtered_urls

            if not all_urls:
                print("❌ No hay videos para procesar")
                return

            # Extraer metadatos solo de los filtrados
            print(f"\n🔬 Extrayendo metadatos de {len(all_urls)} videos...")
            rows = []
            strict_skipped = 0

            for i, url in enumerate(all_urls, 1):
                try:
                    meta = await extract_metadata(context, url)
                    create_dt = meta.pop("_create_dt", None)

                    # Verificar fecha exacta (la del JSON es precisa)
                    in_range = True
                    if create_dt:
                        if start_dt and create_dt.date() < start_dt.date():
                            in_range = False
                        if end_dt and create_dt.date() > end_dt.date():
                            in_range = False

                    if in_range:
                        strict_ok = True
                        if STRICT_LITERAL:
                            if not meta.get("video_desc") and not meta.get("hashtags"):
                                strict_ok = True   # metadatos vacíos (bot detection), incluir con aviso
                                print(f"   ⚠️  {i}/{len(all_urls)} | metadatos vacíos, incluido igualmente")
                            else:
                                strict_ok = matches_any_query_strict_literal(
                                    query_terms,
                                    meta.get("video_desc", ""),
                                    meta.get("hashtags", ""),
                                )

                        if strict_ok:
                            rows.append(meta)
                            likes = meta["video_likes"]
                            views = meta["video_vistas"]
                            fecha = meta["video_fecha"][:10] if meta["video_fecha"] else "?"
                            print(f"   ✅ {i}/{len(all_urls)} | {fecha} | {likes:,}👍 {views:,}👁")
                        else:
                            strict_skipped += 1
                            desc_preview = (meta.get("video_desc") or "")[:60].replace("\n", " ")
                            tags_preview = (meta.get("hashtags") or "")[:60]
                            print(f"   ⛔ {i}/{len(all_urls)} | filtro estricto | desc: {desc_preview!r} | tags: {tags_preview!r}")
                    else:
                        print(f"   ⏭️ {i}/{len(all_urls)} | {create_dt.strftime('%d-%m-%Y') if create_dt else '?'} (fuera de rango exacto)")

                except Exception as e:
                    log.warning("metadata_error url=%s err=%s", url, str(e)[:120])
                    print(f"   ⚠️ {i}/{len(all_urls)} error: {str(e)[:40]}")

                await asyncio.sleep(random.uniform(0.5, 1.0))

        finally:
            await context.close()

    log.info("Fin scraping v2 | saved=%d strict_skipped=%d", len(rows), strict_skipped if STRICT_LITERAL else 0)
    if rows:
        paths = save_results(query_label, rows)
        
        total_likes = sum(r["video_likes"] for r in rows)
        total_views = sum(r["video_vistas"] for r in rows)
        
        print(f"\n📈 RESUMEN:")
        print(f"   Videos: {len(rows)}")
        print(f"   Likes: {total_likes:,}")
        print(f"   Views: {total_views:,}")
        if STRICT_LITERAL:
            print(f"   Descartados por estricto: {strict_skipped}")

    else:
        print("\n⚠️ No se encontraron videos válidos con filtro estricto")

if __name__ == "__main__":
    asyncio.run(main())
