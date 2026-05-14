# -*- coding: utf-8 -*-
"""
TikTok Scraper v4 - PERFIL DE USUARIO
=====================================
Extrae todos los videos de un usuario/cuenta específica.
Incluye filtro previo por fecha usando el ID del video.
"""

import os
import re
import csv
import json
import asyncio
import random
import logging
from datetime import datetime
from playwright.async_api import async_playwright

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils')))

from tiktok_utils import (
    get_date_from_id, get_date_from_video_id,
    is_in_date_range, is_likely_in_date_range,
    extract_video_id_from_url, is_valid_video_url, parse_count,
    human_scroll, accept_cookies_banner, handle_verification,
    load_cookies, save_cookies, ensure_context as _ensure_context_base,
)

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', '.env')
    load_dotenv(env_path)
except:
    pass

# ------------------- CONFIG -------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

COOKIES_PATH = os.path.join(DATA_DIR, "tiktok_cookies.json")
PROFILE_DIR = os.path.join(BASE_DIR, "drivers", "tiktok_profile")

HEADLESS = False
BLOCK_MEDIA = True
MAX_SCROLL = 50  # Más scrolls para perfiles con muchos videos
SCROLL_PAUSE = (1.2, 2.0)
NO_NEW_LIMIT = 5  # Más intentos antes de parar

# ------------------- LOGGING -------------------
_LOG_PATH = os.path.join(DATA_DIR, "scraper_user.log")
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


# ------------------- RECOLECCIÓN DE VIDEOS DEL USUARIO -------------------
async def collect_user_videos(context, username: str, max_scroll: int = MAX_SCROLL):
    """
    Recolecta todas las URLs de videos de un perfil de usuario.
    """
    def _parse_unix_dt(raw_ts):
        try:
            if raw_ts in (None, "", 0, "0"):
                return None
            return datetime.fromtimestamp(int(raw_ts))
        except Exception:
            return None

    def _fallback_dt_from_user_id(user_id):
        try:
            uid = int(str(user_id).strip())
            ts = uid >> 32
            if ts <= 0:
                return None
            dt = datetime.fromtimestamp(ts)
            # Los IDs "cortos" legacy no sirven para inferir fecha.
            if dt.year < 2015 or dt > datetime.now():
                return None
            return dt
        except Exception:
            return None

    page = await context.new_page()
    
    # Limpiar username
    username = username.strip().lstrip("@")
    profile_url = f"https://www.tiktok.com/@{username}"
    
    print(f"🌍 Abriendo perfil: {profile_url}")
    
    try:
        await page.goto(profile_url, timeout=60000)
    except Exception as e:
        print(f"❌ Error al cargar perfil: {e}")
        await page.close()
        return [], {}
    
    await accept_cookies_banner(page)
    await handle_verification(page, 30)
    
    # Verificar si el perfil existe
    await asyncio.sleep(2)
    
    # Intentar obtener info del usuario
    user_info = {}
    try:
        raw = await page.evaluate("""() => {
            const el = document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__');
            return el ? el.textContent : null;
        }""")
        
        if raw:
            data = json.loads(raw)
            scope = data.get("__DEFAULT_SCOPE__", {})
            user_detail = scope.get("webapp.user-detail", {})
            user_data = user_detail.get("userInfo", {}).get("user", {})
            stats_data = user_detail.get("userInfo", {}).get("stats", {})
            user_id = str(user_data.get("id", "") or "")
            account_create_dt = _parse_unix_dt(user_data.get("createTime"))
            account_create_source = "createTime" if account_create_dt else ""

            if not account_create_dt and user_id:
                account_create_dt = _fallback_dt_from_user_id(user_id)
                if account_create_dt:
                    account_create_source = "id>>32"
            
            user_info = {
                "username": user_data.get("uniqueId", username),
                "user_id": user_id,
                "sec_uid": user_data.get("secUid", ""),
                "nickname": user_data.get("nickname", ""),
                "verified": user_data.get("verified", False),
                "followers": stats_data.get("followerCount", 0),
                "following": stats_data.get("followingCount", 0),
                "likes": stats_data.get("heart", 0),
                "video_count": stats_data.get("videoCount", 0),
                "bio": user_data.get("signature", ""),
                "account_created_at": (
                    account_create_dt.strftime("%d-%m-%Y %H:%M:%S")
                    if account_create_dt else ""
                ),
                "account_created_source": account_create_source,
            }
            
            print(f"\n👤 Usuario: @{user_info['username']}")
            print(f"   📛 Nombre: {user_info['nickname']}")
            print(f"   ✅ Verificado: {'Sí' if user_info['verified'] else 'No'}")
            if user_info["account_created_at"]:
                print(f"   🗓️ Creación cuenta: {user_info['account_created_at']}")
            print(f"   👥 Seguidores: {user_info['followers']:,}")
            print(f"   🎬 Videos: {user_info['video_count']}")
            print(f"   ❤️ Likes totales: {user_info['likes']:,}")
    except Exception as e:
        print(f"⚠️ No se pudo obtener info del usuario: {e}")
    
    # Asegurar que estamos en la pestaña de videos
    try:
        # Buscar y clickear la pestaña de videos si existe
        video_tab = await page.query_selector('[data-e2e="videos-tab"]')
        if video_tab:
            await video_tab.click()
            await asyncio.sleep(1)
    except:
        pass
    
    # Recolectar URLs de videos
    video_urls = set()
    prev_count, no_new = 0, 0
    
    print(f"\n📜 Haciendo scroll para recolectar videos...")
    
    for i in range(max_scroll):
        # Buscar enlaces a videos
        selectors = [
            f'a[href*="/@{username}/video/"]',
            'div[data-e2e="user-post-item"] a',
            'div[class*="DivItemContainer"] a[href*="/video/"]',
            'a[href*="/video/"]',
        ]
        
        for sel in selectors:
            try:
                anchors = await page.query_selector_all(sel)
                for a in anchors:
                    href = await a.get_attribute("href")
                    if href and "/video/" in href:
                        # Asegurar que es del usuario correcto
                        if f"/@{username}/" in href.lower() or f"/@{username.lower()}/" in href.lower():
                            if href.startswith("/"):
                                href = f"https://www.tiktok.com{href}"
                            clean = href.split("?")[0]
                            if is_valid_video_url(clean):
                                video_urls.add(clean)
            except:
                pass
        
        cur = len(video_urls)
        print(f"   Scroll {i+1}/{max_scroll} -> {cur} videos")
        
        if cur == prev_count:
            no_new += 1
            if no_new >= NO_NEW_LIMIT:
                print("   ✅ No hay más videos")
                break
        else:
            no_new = 0
        
        # Scroll
        await human_scroll(page)
        await asyncio.sleep(random.uniform(*SCROLL_PAUSE))
        prev_count = cur
    
    await save_cookies(context)
    await page.close()
    
    return list(video_urls), user_info


# ------------------- EXTRACCIÓN DE METADATOS -------------------
async def extract_metadata(context, url, username):
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

        # Menciones
        mentions = []
        for te in item.get("textExtra", []) or []:
            if te.get("userUniqueId"):
                mentions.append(te["userUniqueId"])
        mentions.extend(re.findall(r"@([A-Za-z0-9\._]+)", video_desc))
        mentions = list(dict.fromkeys(mentions))

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
            "video_ratio": video_obj.get("ratio", ""),
            "video_likes": int(stats.get("diggCount", 0) or 0),
            "video_vistas": int(stats.get("playCount", 0) or 0),
            "video_compartidos": int(stats.get("shareCount", 0) or 0),
            "video_comentarios": int(stats.get("commentCount", 0) or 0),
            "video_guardados": int(stats.get("collectCount", 0) or 0),
            "username": author_obj.get("uniqueId", username),
            "author_nickname": author_obj.get("nickname", ""),
            "author_verified": "Sí" if author_obj.get("verified") else "No",
            "music_id": str(music.get("id", "")),
            "music_title": music.get("title", ""),
            "music_author": music.get("authorName", ""),
            "cover_url": video_obj.get("cover", ""),
            "hashtags": "|".join(hashtags),
            "mentions": "|".join(mentions),
            "_create_dt": create_time,
        }
    finally:
        await page.close()


# ------------------- GUARDAR -------------------
def save_results(username, rows, user_info):
    json_path = os.path.join(DATA_DIR, f"user_{username}_videos.json")
    csv_path = os.path.join(DATA_DIR, f"user_{username}_videos.csv")
    
    output = {
        "user_info": user_info,
        "videos_count": len(rows),
        "scraped_at": datetime.now().isoformat(),
        "videos": rows
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    
    fields = ["video_id", "video_url", "video_desc", "video_fecha", "video_duracion_seg",
              "video_width", "video_height", "video_ratio", "video_likes", "video_vistas",
              "video_compartidos", "video_comentarios", "video_guardados", "username",
              "author_nickname", "author_verified", "music_id", "music_title", "music_author",
              "cover_url", "hashtags", "mentions"]
    
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore', quoting=csv.QUOTE_NONNUMERIC)
        w.writeheader()
        w.writerows(rows)
    
    print(f"\n📁 JSON: {json_path}")
    print(f"📄 CSV:  {csv_path}")


# ------------------- MAIN -------------------
async def main():
    print("=" * 60)
    print("TikTok Scraper v4 - PERFIL DE USUARIO")
    print("Extrae todos los videos de una cuenta")
    print("=" * 60)
    
    username = input("\n👤 Usuario (sin @): ").strip().lstrip("@")
    if not username:
        print("❌ Debes introducir un usuario")
        return
    
    start_str = input("📅 Fecha inicio (dd-mm-aaaa) o Enter para todas: ").strip()
    end_str = input("📅 Fecha fin (dd-mm-aaaa) o Enter para todas: ").strip()
    
    def parse_date(s):
        try:
            return datetime.strptime(s.strip(), "%d-%m-%Y") if s.strip() else None
        except:
            return None
    
    start_dt = parse_date(start_str)
    end_dt = parse_date(end_str)
    
    if start_dt or end_dt:
        rango = f"{start_dt.strftime('%d-%m-%Y') if start_dt else 'inicio'} → {end_dt.strftime('%d-%m-%Y') if end_dt else 'fin'}"
        print(f"\n⏱️ Filtro de fechas: {rango}")

    log.info("Inicio scraping user | username=@%s start=%s end=%s", username,
             start_dt.date() if start_dt else None, end_dt.date() if end_dt else None)

    async with async_playwright() as pw:
        context = await ensure_context(pw)
        try:

            # Recolectar videos del usuario
            video_urls, user_info = await collect_user_videos(context, username)

            if not video_urls:
                print(f"\n❌ No se encontraron videos para @{username}")
                print("   Verifica que el usuario existe y tiene videos públicos")
                return

            print(f"\n📊 Videos encontrados: {len(video_urls)}")

            # Pre-filtrar por fecha (EXACTO - calculado desde el ID)
            if start_dt or end_dt:
                filtered = []
                skipped = 0

                for url in video_urls:
                    vid = extract_video_id_from_url(url)
                    if is_in_date_range(vid, start_dt, end_dt):
                        filtered.append(url)
                    else:
                        skipped += 1

                print(f"🗓️ Filtrado por fecha (exacto desde ID): {len(filtered)} en rango, {skipped} descartados")
                video_urls = filtered

            if not video_urls:
                print("❌ No hay videos en el rango de fechas especificado")
                return

            # Extraer metadatos
            print(f"\n🔬 Extrayendo metadatos de {len(video_urls)} videos...")
            rows = []

            for i, url in enumerate(video_urls, 1):
                try:
                    meta = await extract_metadata(context, url, username)
                    create_dt = meta.pop("_create_dt", None)

                    # Verificar fecha exacta
                    in_range = True
                    if create_dt:
                        if start_dt and create_dt.date() < start_dt.date():
                            in_range = False
                        if end_dt and create_dt.date() > end_dt.date():
                            in_range = False

                    if in_range:
                        rows.append(meta)
                        likes = meta["video_likes"]
                        views = meta["video_vistas"]
                        fecha = meta["video_fecha"][:10] if meta["video_fecha"] else "?"
                        print(f"   ✅ {i}/{len(video_urls)} | {fecha} | {likes:,}👍 {views:,}👁")
                    else:
                        fecha_str = create_dt.strftime('%d-%m-%Y') if create_dt else '?'
                        print(f"   ⏭️ {i}/{len(video_urls)} | {fecha_str} (fuera de rango)")

                except Exception as e:
                    log.warning("metadata_error url=%s err=%s", url, str(e)[:120])
                    print(f"   ⚠️ {i}/{len(video_urls)} error: {str(e)[:40]}")

                await asyncio.sleep(random.uniform(0.5, 1.0))

        finally:
            await context.close()

    log.info("Fin scraping user | username=@%s saved=%d", username, len(rows))
    if rows:
        save_results(username, rows, user_info)
        
        total_likes = sum(r["video_likes"] for r in rows)
        total_views = sum(r["video_vistas"] for r in rows)
        total_comments = sum(r["video_comentarios"] for r in rows)
        total_shares = sum(r["video_compartidos"] for r in rows)
        
        print(f"\n📈 RESUMEN @{username}:")
        print(f"   Videos: {len(rows)}")
        print(f"   Total Likes: {total_likes:,}")
        print(f"   Total Views: {total_views:,}")
        print(f"   Total Comments: {total_comments:,}")
        print(f"   Total Shares: {total_shares:,}")
        if total_views > 0:
            engagement = (total_likes + total_comments + total_shares) / total_views * 100
            print(f"   Engagement Rate: {engagement:.2f}%")
    else:
        print(f"\n⚠️ No se encontraron videos de @{username} en el rango especificado")


if __name__ == "__main__":
    asyncio.run(main())
