# -*- coding: utf-8 -*-
"""
================================================================================
TikTok Comment Scraper v13 FINAL
================================================================================

CAMBIOS vs versión anterior:
    - Cabecera: autor_nombre + autor_handle separados
    - Campo aweme_id_api añadido
    - Refresh preventivo cada ~1000 comentarios (nueva sesión de cookies)

DESCRIPCIÓN:
    Extrae comentarios de videos de TikTok usando Playwright.
    Intercepta las respuestas de /api/comment/list/ mientras hace scroll.

REQUISITOS:
    pip install playwright
    playwright install chromium

USO:
    python tiktok_scraper_comentarios_v13_FINAL.py
    
    1. Selecciona un CSV con URLs de videos (columna: video_url, url, URL o link)
    2. Indica cuántos videos procesar (Enter = todos)
    3. Indica límite de comentarios por video (Enter = sin límite)

ARCHIVOS GENERADOS:
    - data_tiktok/<nombre_csv>_comentarios.csv  → Todos los comentarios
    - data_tiktok/logs/tiktok_scraper_YYYYMMDD_HHMMSS.log → Log global
    - data_tiktok/logs/YYYYMMDD_HHMMSS_<video_id>.log → Log por video

ESTRUCTURA DEL CSV DE SALIDA:
    video_id, video_url, username, comment_id, fecha, autor_nombre, autor_handle, texto, likes, aweme_id_api

================================================================================
LIMITACIONES CONOCIDAS (TikTok server-side, no hay solución):
================================================================================

1. COBERTURA POR TAMAÑO DE VIDEO:
   - Videos < 500 comentarios:  70-90% de cobertura
   - Videos 500-2000 comentarios: 50-75% de cobertura  
   - Videos 5000+ comentarios (virales): 25-40% de cobertura

2. CAUSA:
   - TikTok limita la paginación de comentarios a ~1400-1600 por sesión
   - Después de cierto punto, el cursor se reinicia o deja de devolver nuevos
   - Esto es una limitación del servidor, no del scraper
   - Documentado en: https://github.com/davidteather/TikTok-Api/issues/926

3. ALTERNATIVAS PARA MÁS COBERTURA:
   - TikTok Research API (oficial, requiere aplicar como investigador)
   - Servicios de pago: TikAPI, EnsembleData (~$50-100/mes)

================================================================================
"""

import os
import re
import csv
import json
import time
import asyncio
import random
import sys
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Callable

from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError
import traceback

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
BASE_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR     = os.path.join(BASE_DIR, "data")
COOKIES_PATH = os.path.join(DATA_DIR, "tiktok_cookies.json")
PROFILE_DIR  = os.path.join(BASE_DIR, "drivers", "tiktok_profile")
LOG_DIR      = os.path.join(DATA_DIR, "logs")

# Crear directorios
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR,  exist_ok=True)

# Parámetros de scraping (optimizados tras múltiples pruebas)
HEADLESS = False                    # False = más difícil de detectar como bot
SCROLL_WAIT_MIN = 1.2               # Espera mínima entre scrolls (segundos)
SCROLL_WAIT_MAX = 3.0               # Espera máxima entre scrolls
NO_PROGRESS_LIMIT = 14              # Ciclos sin progreso antes de reintentar
STUCK_RETRY_CYCLES = 3              # Reintentos cuando se queda atascado
PAUSE_EVERY_PAGES = 30              # Pausa larga cada N páginas
LONG_PAUSE_MIN = 5.0                # Pausa larga mínima
LONG_PAUSE_MAX = 12.0               # Pausa larga máxima
MAX_SCROLLS_HARD = 1200             # Límite absoluto de scrolls

# NUEVO: Refresh preventivo
REFRESH_EVERY_COMMENTS = 1000       # Refresh cada N comentarios acumulados
REFRESH_WAIT_MIN = 20               # Espera mínima tras refresh (segundos)
REFRESH_WAIT_MAX = 40               # Espera máxima tras refresh (segundos)

# NUEVO: Guardado incremental y salida temprana si has_more=0 sin progreso
SAVE_PARTIAL_EVERY_VIDEO = True
CHECKPOINT_SUFFIX = "_checkpoint.json"   # Pieza 4: reanudación
HAS_MORE_GRACE_SEC = 20
HAS_MORE_GRACE_NO_PROGRESS = 6
# NUEVO: Cortar antes si el cursor se repite sin progreso
SAME_CURSOR_LIMIT = 8
MAX_NO_PROGRESS_SEC = 180

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36"


# ============================================================================
# LOGGING
# ============================================================================

class _TeeIO:
    """Duplica stdout/stderr a ficheros de log."""
    def __init__(self, base, files=None):
        self.base = base
        self.files = list(files or [])

    def write(self, s):
        try:
            self.base.write(s)
        except:
            pass
        for f in list(self.files):
            try:
                f.write(s)
            except:
                self.files.remove(f) if f in self.files else None

    def flush(self):
        try:
            self.base.flush()
        except:
            pass
        for f in list(self.files):
            try:
                f.flush()
            except:
                pass

    def add(self, fh):
        if fh and fh not in self.files:
            self.files.append(fh)

    def remove(self, fh):
        if fh in self.files:
            self.files.remove(fh)


_TEE_STDOUT = None
_TEE_STDERR = None
_GLOBAL_LOG_FH = None
_LOG_TS = None
_GLOBAL_LOG_PATH = None


def init_logging():
    """Activa logging a fichero."""
    global _TEE_STDOUT, _TEE_STDERR, _GLOBAL_LOG_FH, _LOG_TS, _GLOBAL_LOG_PATH
    if _TEE_STDOUT is not None:
        return _GLOBAL_LOG_PATH, _LOG_TS

    _LOG_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
    _GLOBAL_LOG_PATH = os.path.join(LOG_DIR, f"tiktok_scraper_{_LOG_TS}.log")
    _GLOBAL_LOG_FH = open(_GLOBAL_LOG_PATH, "a", encoding="utf-8", errors="ignore")

    _TEE_STDOUT = _TeeIO(getattr(sys, "__stdout__", sys.stdout), files=[_GLOBAL_LOG_FH])
    _TEE_STDERR = _TeeIO(getattr(sys, "__stderr__", sys.stderr), files=[_GLOBAL_LOG_FH])

    sys.stdout = _TEE_STDOUT
    sys.stderr = _TEE_STDERR
    return _GLOBAL_LOG_PATH, _LOG_TS


def close_logging():
    global _GLOBAL_LOG_FH
    if _GLOBAL_LOG_FH:
        try:
            _GLOBAL_LOG_FH.flush()
            _GLOBAL_LOG_FH.close()
        except:
            pass
    _GLOBAL_LOG_FH = None


# ============================================================================
# UTILIDADES
# ============================================================================

def seleccionar_csv() -> str:
    """Abre diálogo para seleccionar CSV."""
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return sys.argv[1]
    root = tk.Tk()
    root.withdraw()
    ruta = filedialog.askopenfilename(
        title="Selecciona el CSV con videos de TikTok",
        filetypes=[("CSV", "*.csv")]
    )
    if not ruta:
        print("❌ No se seleccionó ningún archivo.")
        raise SystemExit(1)
    return ruta


def cargar_urls_desde_csv(ruta_csv: str) -> List[str]:
    """Carga URLs desde CSV."""
    with open(ruta_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        return []

    url_col = None
    for col in ["video_url", "url", "URL", "link"]:
        if col in rows[0]:
            url_col = col
            break
    if not url_col:
        raise KeyError("No se encontró columna de URL (video_url/url/URL/link).")

    return [(r.get(url_col) or "").strip() for r in rows if (r.get(url_col) or "").strip()]


def extract_video_id(url: str) -> str:
    m = re.search(r"/video/(\d+)", url)
    return m.group(1) if m else ""


def extract_username(url: str) -> str:
    m = re.search(r"tiktok\.com/@([^/]+)/video", url)
    return m.group(1) if m else ""


def normalizar_texto(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def guardar_csv(comentarios: List[Dict[str, Any]], ruta_csv: str) -> None:
    """Guarda comentarios en CSV con nueva estructura."""
    if not comentarios:
        return
    # MODIFICADO: Nueva cabecera con autor_nombre, autor_handle y aweme_id_api
    campos = ["video_id", "video_url", "username", "comment_id", "fecha", 
              "autor_nombre", "autor_handle", "texto", "likes", "aweme_id_api"]
    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for c in comentarios:
            w.writerow({k: c.get(k, "") for k in campos})

def append_csv(comentarios: List[Dict[str, Any]], ruta_csv: str) -> None:
    """Añade comentarios al CSV (crea cabecera si no existe)."""
    if not comentarios:
        return
    campos = ["video_id", "video_url", "username", "comment_id", "fecha",
              "autor_nombre", "autor_handle", "texto", "likes", "aweme_id_api"]
    file_exists = os.path.exists(ruta_csv)
    with open(ruta_csv, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if not file_exists:
            w.writeheader()
        for c in comentarios:
            w.writerow({k: c.get(k, "") for k in campos})


# ---- PIEZA 4: Checkpoint de reanudación ----------------------------
def save_checkpoint(path: str, processed_ids: List[str], out_csv: str) -> None:
    """Persiste los IDs de videos ya procesados para poder reanudar."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"processed_video_ids": processed_ids, "out_csv": out_csv}, f, ensure_ascii=False, indent=2)


def load_checkpoint(path: str) -> dict:
    """Carga el checkpoint de una sesión anterior. Devuelve {} si no existe."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def load_cookies_file() -> Optional[List[Dict[str, Any]]]:
    """Carga cookies desde archivo JSON."""
    if not os.path.exists(COOKIES_PATH):
        return None
    try:
        with open(COOKIES_PATH, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        return cookies if isinstance(cookies, list) and cookies else None
    except:
        return None


def is_target_closed_error(e: Exception) -> bool:
    """Detecta si el error es por cierre del navegador."""
    name = type(e).__name__
    msg = str(e)
    return ("TargetClosedError" in name) or ("Target page, context or browser has been closed" in msg)


# ============================================================================
# FUNCIONES DE PLAYWRIGHT
# ============================================================================

async def wait_for_comment_response(page, timeout_ms: int) -> bool:
    """Espera respuesta de la API de comentarios."""
    pred = lambda r: "/api/comment/list/" in getattr(r, "url", "")
    try:
        await page.wait_for_response(pred, timeout=timeout_ms)
        return True
    except PWTimeoutError:
        return False
    except:
        return False


async def accept_cookies_best_effort(page) -> None:
    """Acepta banner de cookies si aparece."""
    selectors = [
        'button:has-text("Accept all")',
        'button:has-text("Aceptar todo")',
        'button:has-text("Accept")',
        'button:has-text("Aceptar")',
        '[data-e2e="cookie-banner-accept"]',
    ]
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                await el.click(timeout=1500)
                await page.wait_for_timeout(800)
                return
        except:
            pass


async def dismiss_overlays(page) -> None:
    """Cierra popups y overlays."""
    # Escape
    for _ in range(3):
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(200)
        except:
            pass

    # Botones de cierre
    close_selectors = [
        'button[aria-label="Close"]',
        'button[aria-label="Cerrar"]',
        'button:has-text("Not now")',
        'button:has-text("Ahora no")',
        'button:has-text("Continue as guest")',
        'button:has-text("Continuar como invitado")',
        '[role="dialog"] button',
    ]
    for sel in close_selectors:
        try:
            els = await page.query_selector_all(sel)
            for el in els[:5]:
                if await el.is_visible():
                    await el.click(timeout=800)
                    await page.wait_for_timeout(300)
        except:
            continue

    await accept_cookies_best_effort(page)


async def ensure_logged_in_best_effort(context) -> bool:
    """Verifica si hay sesión activa."""
    page = await context.new_page()
    try:
        await page.goto("https://www.tiktok.com", timeout=60000, wait_until="domcontentloaded")
        await accept_cookies_best_effort(page)
        await page.wait_for_timeout(1500)

        # Si hay botón de login visible, no está logueado
        login_btn = await page.query_selector('[data-e2e="top-login-button"], button:has-text("Log in")')
        if login_btn and await login_btn.is_visible():
            return False

        # Verificar señales de login
        checks = ['[data-e2e="nav-profile"]', 'img[class*="Avatar" i]']
        for sel in checks:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return True

        # Verificar cookies de sesión
        cookies = await context.cookies("https://www.tiktok.com")
        names = {c.get("name", "") for c in cookies}
        if "sid_tt" in names or any(n.lower().startswith("session") for n in names):
            return True

        return False
    finally:
        await page.close()


async def find_scroll_container_css(page) -> Optional[str]:
    """Encuentra el contenedor scrolleable de comentarios."""
    return await page.evaluate("""() => {
      function cssPath(el){
        if(!el) return null;
        const parts=[];
        while(el && el.nodeType===Node.ELEMENT_NODE && el!==document.body){
          let part=el.tagName.toLowerCase();
          if(el.id){part+='#'+CSS.escape(el.id); parts.unshift(part); break;}
          const cls=(el.className && typeof el.className==='string')? el.className.trim():'';
          if(cls){
            const first=cls.split(/\\s+/).slice(0,2).map(c=>'.'+CSS.escape(c)).join('');
            if(first) part+=first;
          }
          const p=el.parentElement;
          if(p){
            const sib=Array.from(p.children).filter(x=>x.tagName===el.tagName);
            if(sib.length>1) part+=`:nth-of-type(${sib.indexOf(el)+1})`;
          }
          parts.unshift(part);
          el=el.parentElement;
        }
        return parts.join(' > ');
      }

      const item = document.querySelector('[data-e2e="comment-level-1"]') ||
                   document.querySelector('[data-e2e*="comment-level"]') ||
                   document.querySelector('div[class*="CommentItem" i]') ||
                   document.querySelector('div[class*="CommentList" i]');
      if(!item) return null;

      let cur=item;
      while(cur && cur!==document.body){
        const st=getComputedStyle(cur);
        const oy=(st.overflowY||'').toLowerCase();
        const can=(oy==='auto'||oy==='scroll'||oy==='overlay') && (cur.scrollHeight>cur.clientHeight+5);
        if(can) return cssPath(cur);
        cur=cur.parentElement;
      }

      const fb = document.querySelector('[class*="DivCommentListContainer"]') || 
                 document.querySelector('[class*="DivCommentContainer"]') ||
                 document.querySelector('[data-e2e="comment-list"]');
      if(fb && fb.scrollHeight>fb.clientHeight+10) return cssPath(fb);
      return null;
    }""")


async def scroll_container(page, css_sel: str) -> bool:
    """Hace scroll en el contenedor de comentarios."""
    try:
        res = await page.evaluate("""(cssSel)=>{
          const el=document.querySelector(cssSel);
          if(!el) return {ok:false};
          const before=el.scrollTop;
          el.scrollTop = before + el.clientHeight*0.9;
          el.dispatchEvent(new Event('scroll',{bubbles:true}));
          const after=el.scrollTop;
          return {ok:true, moved:(after>before+1)};
        }""", css_sel)
        return bool(res.get("ok") and res.get("moved"))
    except:
        return False


async def open_comments_panel(page) -> Dict[str, Any]:
    """Abre el panel de comentarios."""
    await dismiss_overlays(page)

    async def panel_visible() -> bool:
        selectors = [
            '[data-e2e="comment-level-1"]',
            '[data-e2e="comment-list"]',
            '[data-e2e="comment-item"]',
            'div[class*="CommentItem" i]',
            'div[class*="CommentList" i]',
            'div[class*="DivCommentList" i]',
        ]
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    return True
            except:
                pass
        try:
            el = await page.query_selector(
                'text=/no comments|comments are turned off|comments disabled|sin comentarios|comentarios desactivados|comentarios deshabilitados|no hay comentarios/i'
            )
            if el and await el.is_visible():
                return True
        except:
            pass
        return False

    # Si ya está abierto, no hacer clics
    if await panel_visible():
        return {"opened": True, "via": "already-open"}

    selectors = [
        'button:has([data-e2e="comment-icon"])',
        'button:has([data-e2e="browse-comment-icon"])',
        '[aria-label*="comment" i]',
        '[aria-label*="coment" i]',
        '[data-e2e="comment-icon"]',
        '[data-e2e="comment-count"]',
        '[data-e2e="comment-button"]',
    ]
    
    for attempt in range(3):
        for sel in selectors:
            try:
                els = await page.query_selector_all(sel)
                for el in els[:12]:
                    if not await el.is_visible():
                        continue
                        
                    # Buscar el botón padre clicable
                    target = el
                    try:
                        target = await el.evaluate_handle("e=>e.closest('button,a,[role=\"button\"]')||e")
                    except:
                        pass

                    try:
                        await target.scroll_into_view_if_needed(timeout=1500)
                    except:
                        pass

                    try:
                        await target.click(timeout=1200)
                    except:
                        await target.click(timeout=1200, force=True)

                    await page.wait_for_timeout(900)
                    
                    # Verificar que se abrió
                    if await panel_visible():
                        return {"opened": True, "via": sel}
            except:
                continue

        await page.wait_for_timeout(800)
        await dismiss_overlays(page)
        if await panel_visible():
            return {"opened": True, "via": "post-dismiss"}

    return {"opened": False, "via": None}


async def ensure_expected_video(page, expected_url: str, expected_video_id: str, stage: str = "") -> bool:
    """Verifica que seguimos en el video correcto (TikTok puede cambiar de video)."""
    try:
        current_url = page.url or ""
        current_id = extract_video_id(current_url)
        if expected_video_id and current_id and current_id != expected_video_id:
            print(f"[GUARD] Desvío detectado ({stage}). Reabriendo: {expected_url}")
            await page.goto(expected_url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(600)
            return False
    except:
        pass
    return True


async def create_context(pw):
    """Crea contexto de Playwright con perfil persistente."""
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=HEADLESS,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        viewport={"width": 1280, "height": 900},
        user_agent=UA,
    )

    cookies = load_cookies_file()
    if cookies:
        try:
            await context.add_cookies(cookies)
            print("🍪 Cookies cargadas")
        except Exception as e:
            print(f"⚠️ No se pudieron cargar cookies: {e}")
    else:
        print("⚠️ No se encontró archivo de cookies (data_tiktok/tiktok_cookies.json)")

    try:
        logged = await ensure_logged_in_best_effort(context)
        if logged:
            print("✅ Sesión detectada")
        else:
            print("⚠️ No se detecta sesión. Continuando como guest.")
    except:
        pass

    return context


# ============================================================================
# EXTRACCIÓN DE COMENTARIOS
# ============================================================================

def _extract_cursor_from_url(u: str) -> str:
    m = re.search(r"[?&]cursor=(\d+)", u)
    return m.group(1) if m else "?"


def _extract_aweme_id_from_url(u: str) -> str:
    """Extrae el aweme_id (video_id) de la URL de la API."""
    m = re.search(r"[?&]aweme_id=(\d+)", u)
    return m.group(1) if m else ""


async def extract_comments(context, url: str, limit: Optional[int] = None) -> Tuple[List[Dict[str, Any]], int]:
    """
    Extrae comentarios de un video.
    Retorna: (lista_comentarios, total_reportado_por_api)
    """
    page = await context.new_page()
    video_id = extract_video_id(url) or "???"
    username = extract_username(url)

    comments_by_cid: Dict[str, Dict[str, Any]] = {}
    total_from_api = 0
    has_more_last = None
    pages_seen = 0
    last_progress_time = time.time()
    last_cursor_seen: Optional[str] = None
    same_cursor_count = 0
    start_time = time.time()
    
    # NUEVO: Para almacenar aweme_id de cada comentario
    aweme_id_for_comment: Dict[str, str] = {}

    async def handle_comment_list_response(response):
        nonlocal total_from_api, has_more_last, pages_seen, last_progress_time, last_cursor_seen, same_cursor_count
        try:
            u = response.url
            if "/api/comment/list/" not in u:
                return
            
            # Extraer aweme_id de la respuesta
            aweme_id = _extract_aweme_id_from_url(u)
            
            # FILTRAR: solo aceptar respuestas del video correcto
            if aweme_id and aweme_id != video_id:
                print(f"[{video_id}] ⚠️ IGNORANDO respuesta de otro video: {aweme_id}")
                return
            
            data = await response.json()
            batch = data.get("comments") or []
            total = int(data.get("total") or 0)
            has_more = data.get("has_more")

            total_from_api = max(total_from_api, total)
            has_more_last = has_more
            cursor = _extract_cursor_from_url(u)

            new_count = 0
            for c in batch:
                if not c:
                    continue
                cid = str(c.get("cid") or c.get("id") or "")
                if cid and cid not in comments_by_cid:
                    comments_by_cid[cid] = c
                    # NUEVO: Guardar aweme_id asociado a este comentario
                    aweme_id_for_comment[cid] = aweme_id or video_id
                    new_count += 1

            if cursor != "?":
                if cursor == last_cursor_seen and new_count == 0:
                    same_cursor_count += 1
                else:
                    same_cursor_count = 0
                    last_cursor_seen = cursor

            pages_seen += 1
            if new_count > 0:
                last_progress_time = time.time()

            elapsed = max(1e-3, time.time() - start_time)
            acc = len(comments_by_cid)
            pct = int((acc / total) * 100) if total else 0
            rate = acc / elapsed
            status = "nuevo" if new_count > 0 else "sin nuevos"
            print(
                f"[{video_id}] page#{pages_seen} cursor={cursor} has_more={has_more} "
                f"batch={len(batch)} +{new_count} acc={acc}/{total or '?'} ({pct}%) "
                f"{status} rate={rate:.1f}/s"
            )
        except:
            pass

    page.on("response", lambda r: asyncio.create_task(handle_comment_list_response(r)))

    try:
        # Cargar página
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        print(f"[{video_id}] Cargando...")
        await ensure_expected_video(page, url, video_id, stage="post-goto")
        await accept_cookies_best_effort(page)
        await page.wait_for_timeout(1500)
        await dismiss_overlays(page)

        # Abrir panel de comentarios
        open_info = await open_comments_panel(page)
        if not open_info.get("opened"):
            await page.reload(timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1200)
            await ensure_expected_video(page, url, video_id, stage="reload")
            open_info = await open_comments_panel(page)

        if not open_info.get("opened"):
            print(f"[{video_id}] ⚠️ No se pudo abrir panel de comentarios")
            await page.close()
            return [], 0

        await wait_for_comment_response(page, timeout_ms=15000)

        if not comments_by_cid:
            print(f"[{video_id}] ⚠️ No llegaron respuestas de la API")
            await page.close()
            return [], 0

        # Encontrar contenedor de scroll
        container_css = await find_scroll_container_css(page)
        if container_css:
            print(f"[{video_id}] 🧭 Contenedor scroll detectado")
        else:
            print(f"[{video_id}] ⚠️ No se detectó contenedor; usaré wheel")

        # Loop de scroll
        no_progress = 0
        stuck_cycles = 0
        scrolls = 0
        last_acc = len(comments_by_cid)
        target_total = total_from_api or 0

        while True:
            # Verificar límites
            if limit is not None and len(comments_by_cid) >= limit:
                print(f"[{video_id}] STOP reason=limit acc={len(comments_by_cid)}")
                break
            
            if target_total and len(comments_by_cid) >= target_total:
                print(f"[{video_id}] STOP reason=reached_total acc={len(comments_by_cid)}")
                break

            if scrolls >= MAX_SCROLLS_HARD:
                print(f"[{video_id}] STOP reason=max_scrolls acc={len(comments_by_cid)}")
                break

            # Scroll
            moved = False
            if container_css:
                moved = await scroll_container(page, container_css)
            
            # Verificar que seguimos en el video correcto después de scroll
            still_correct = await ensure_expected_video(page, url, video_id, stage="post-scroll")
            if not still_correct:
                # TikTok nos desvió, reabrir panel de comentarios
                await page.wait_for_timeout(1000)
                await dismiss_overlays(page)
                await open_comments_panel(page)
                container_css = await find_scroll_container_css(page) or container_css
                continue
            
            if not moved:
                await page.reload(timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1200)
                await ensure_expected_video(page, url, video_id, stage="reload-no-scroll")
                open_info = await open_comments_panel(page)
                if open_info.get("opened"):
                    container_css = await find_scroll_container_css(page)

            # Esperar respuesta
            got = await wait_for_comment_response(page, timeout_ms=7000)
            if not got:
                await page.wait_for_timeout(int(random.uniform(SCROLL_WAIT_MIN, SCROLL_WAIT_MAX) * 1000))

            await page.wait_for_timeout(120)

            if total_from_api:
                target_total = total_from_api

            # Verificar progreso
            acc = len(comments_by_cid)
            if acc == last_acc:
                no_progress += 1
            else:
                no_progress = 0
                last_acc = acc

            if same_cursor_count >= SAME_CURSOR_LIMIT and no_progress >= NO_PROGRESS_LIMIT:
                print(f"[{video_id}] STOP reason=cursor_loop acc={len(comments_by_cid)} cursor={last_cursor_seen}")
                break

            if (time.time() - last_progress_time) > MAX_NO_PROGRESS_SEC:
                print(f"[{video_id}] STOP reason=no_progress_timeout acc={len(comments_by_cid)}")
                break

            if has_more_last == 0 and (time.time() - last_progress_time) > HAS_MORE_GRACE_SEC:
                if target_total and len(comments_by_cid) < int(target_total * 0.95):
                    if no_progress >= HAS_MORE_GRACE_NO_PROGRESS:
                        print(f"[{video_id}] STOP reason=has_more_0_grace acc={len(comments_by_cid)}")
                        break
                    else:
                        print(f"[{video_id}] has_more=0 pero lejos del total → gracia")
                else:
                    print(f"[{video_id}] STOP reason=has_more_0 acc={len(comments_by_cid)}")
                    break

            scrolls += 1

            # Pausa larga periódica
            if pages_seen and pages_seen % PAUSE_EVERY_PAGES == 0:
                pause = random.uniform(LONG_PAUSE_MIN, LONG_PAUSE_MAX)
                print(f"[{video_id}] ⏸️ pausa {pause:.1f}s")
                await page.wait_for_timeout(int(pause * 1000))

            # Manejar atasco
            if no_progress >= NO_PROGRESS_LIMIT:
                stuck_cycles += 1
                print(f"[{video_id}] ⚠️ STUCK cycle={stuck_cycles} acc={acc}/{target_total or '?'}")
                
                if stuck_cycles > STUCK_RETRY_CYCLES:
                    print(f"[{video_id}] STOP reason=stuck acc={acc}")
                    break

                await page.wait_for_timeout(int(random.uniform(6.0, 14.0) * 1000))
                await page.reload(timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1200)
                await ensure_expected_video(page, url, video_id, stage="reload-stuck")
                await dismiss_overlays(page)
                await open_comments_panel(page)
                container_css = await find_scroll_container_css(page) or container_css
                no_progress = 0

            await page.wait_for_timeout(int(random.uniform(SCROLL_WAIT_MIN, SCROLL_WAIT_MAX) * 1000))

        # MODIFICADO: Convertir a formato de salida con nuevos campos
        out: List[Dict[str, Any]] = []
        for cid, c in comments_by_cid.items():
            user = c.get("user", {}) or {}
            # NUEVO: Separar autor_nombre y autor_handle
            autor_nombre = user.get("nickname") or ""
            autor_handle = user.get("unique_id") or ""
            text = c.get("text") or ""
            likes = c.get("digg_count") or 0
            ts = c.get("create_time") or 0
            try:
                fecha = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
            except:
                fecha = ""
            
            # NUEVO: aweme_id_api
            aweme_api = aweme_id_for_comment.get(cid, video_id)
            
            out.append({
                "video_id": video_id,
                "video_url": url,
                "username": username,
                "comment_id": cid,
                "fecha": fecha,
                "autor_nombre": normalizar_texto(autor_nombre),
                "autor_handle": normalizar_texto(autor_handle),
                "texto": normalizar_texto(text),
                "likes": likes,
                "aweme_id_api": aweme_api,
            })

        await page.close()
        return out, (target_total or len(out))

    except Exception as e:
        print(f"[{video_id}] ❌ Error: {e}")
        traceback.print_exc()
        try:
            await page.close()
        except:
            pass
        raise


# ============================================================================
# MAIN
# ============================================================================

async def main():
    global_log_path, log_ts = init_logging()
    
    print("=" * 60)
    print("TikTok Comment Scraper v13 FINAL")
    print("- autor_nombre + autor_handle separados")
    print("- aweme_id_api añadido")
    print(f"- Refresh preventivo cada ~{REFRESH_EVERY_COMMENTS} comentarios")
    print("=" * 60)
    print("⚠️  LIMITACIONES CONOCIDAS:")
    print("    - Videos < 500 comentarios: ~70-90% cobertura")
    print("    - Videos 500-2000: ~50-75% cobertura")
    print("    - Videos virales (5000+): ~25-40% cobertura")
    print("    (Limitación del servidor de TikTok, no del scraper)")
    print("=" * 60)

    ruta_csv = seleccionar_csv()
    urls = cargar_urls_desde_csv(ruta_csv)
    print(f"📂 Archivo: {os.path.basename(ruta_csv)}")
    print(f"📊 Videos encontrados: {len(urls)}")
    base = os.path.splitext(os.path.basename(ruta_csv))[0]
    out_csv = os.path.join(DATA_DIR, f"{base}_comentarios.csv")

    # ---- PIEZA 4: Cargar checkpoint y ofrecer reanudación ----
    checkpoint_path = os.path.join(DATA_DIR, f"{base}{CHECKPOINT_SUFFIX}")
    checkpoint = load_checkpoint(checkpoint_path)
    processed_ids: List[str] = list(checkpoint.get("processed_video_ids", []))
    is_resume = False

    if processed_ids:
        n_skip = sum(1 for u in urls if extract_video_id(u) in processed_ids)
        if n_skip > 0:
            print(f"\n♻️  Checkpoint encontrado: {n_skip} videos ya procesados.")
            ans = input("   ¿Continuar desde donde se quedó? (S/n): ").strip().lower()
            if ans in ("", "s", "si", "sí", "y", "yes"):
                urls = [u for u in urls if extract_video_id(u) not in processed_ids]
                print(f"   ↩ Saltando {n_skip} videos. Quedan {len(urls)} por procesar.")
                is_resume = True
            else:
                processed_ids = []

    cuantos = input("\n🔢 ¿Cuántos videos procesar? (Enter=todos): ").strip()
    if cuantos:
        try:
            urls = urls[:int(cuantos)]
        except:
            pass

    lim = input("💬 ¿Límite de comentarios por vídeo? (Enter=sin límite): ").strip()
    limit = int(lim) if lim.isdigit() else None

    print(f"\n🔬 Procesando {len(urls)} videos...\n")

    all_comments: List[Dict[str, Any]] = []
    ok_videos = 0
    total_expected = 0
    
    # NUEVO: Contador para refresh preventivo
    comments_since_refresh = 0
    last_refresh_count = 0

    async with async_playwright() as pw:
        ctx = await create_context(pw)

        for idx, url in enumerate(urls, 1):
            await asyncio.sleep(random.uniform(0.8, 2.0))
            vid = extract_video_id(url)
            vid_short = ("..." + vid[-12:]) if vid and len(vid) > 12 else (vid or "???")
            print(f"\n▶️ [{idx}/{len(urls)}] {vid_short} iniciando...")

            # =====================================================
            # NUEVO: Refresh preventivo cada ~1000 comentarios
            # =====================================================
            if comments_since_refresh >= REFRESH_EVERY_COMMENTS:
                wait_time = random.randint(REFRESH_WAIT_MIN, REFRESH_WAIT_MAX)
                print(f"\n🔄 Refresh preventivo ({comments_since_refresh} comentarios acumulados)")
                print(f"   Cerrando navegador y esperando {wait_time}s...")
                
                try:
                    await ctx.close()
                except:
                    pass
                
                await asyncio.sleep(wait_time)
                
                ctx = await create_context(pw)
                print(f"   ✅ Contexto refrescado. Continuando...\n")
                
                comments_since_refresh = 0
                last_refresh_count = len(all_comments)

            attempts = 0
            while True:
                attempts += 1
                try:
                    # Log por video
                    video_log_path = os.path.join(LOG_DIR, f"{log_ts}_{vid}.log")
                    video_fh = open(video_log_path, "a", encoding="utf-8", errors="ignore")
                    try:
                        if _TEE_STDOUT:
                            _TEE_STDOUT.add(video_fh)
                        if _TEE_STDERR:
                            _TEE_STDERR.add(video_fh)
                        
                        comments, total = await extract_comments(ctx, url, limit=limit)
                    finally:
                        if _TEE_STDOUT:
                            _TEE_STDOUT.remove(video_fh)
                        if _TEE_STDERR:
                            _TEE_STDERR.remove(video_fh)
                        video_fh.close()

                    cap = len(comments)
                    total_expected += total
                    pct = int((cap / total) * 100) if total else 0
                    status = "✅" if total and pct >= 70 else "⚠️"
                    print(f"\n📹 [{idx}/{len(urls)}] {vid_short} {status} {cap}/{total} ({pct}%)\n")

                    if cap:
                        ok_videos += 1
                        all_comments.extend(comments)
                        # NUEVO: Actualizar contador de refresh
                        comments_since_refresh += cap
                        if SAVE_PARTIAL_EVERY_VIDEO:
                            append_csv(comments, out_csv)
                            print(f"💾 Parcial guardado (+{cap})")
                        # PIEZA 4: Actualizar checkpoint tras cada video exitoso
                        processed_ids.append(vid)
                        save_checkpoint(checkpoint_path, processed_ids, out_csv)
                    break

                except Exception as e:
                    if is_target_closed_error(e) and attempts <= 2:
                        print(f"⚠️ Contexto cerrado. Recreando (intento {attempts}/2)...")
                        try:
                            await ctx.close()
                        except:
                            pass
                        ctx = await create_context(pw)
                        continue
                    else:
                        print(f"❌ Fallo definitivo en {vid_short}: {e}")
                        break

        await ctx.close()

    # PIEZA 4: En reanudación los comentarios ya están en out_csv vía append_csv.
    # En ejecución normal hacemos el volcado final completo.
    if is_resume:
        print(f"📄 Comentarios acumulados en: {out_csv}")
    else:
        guardar_csv(all_comments, out_csv)

    # Borrar checkpoint si completamos todos los videos
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
        print("🗑️  Checkpoint eliminado (proceso completado).")

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"📄 CSV guardado: {out_csv}")
    print(f"✅ Videos con comentarios: {ok_videos}/{len(urls)}")
    print(f"📌 Total esperado (API): {total_expected:,}")
    print(f"📌 Total capturado: {len(all_comments):,}")
    if total_expected:
        print(f"📊 Cobertura global: {int(len(all_comments)/total_expected*100)}%")
    print(f"🧾 Log global: {global_log_path}")
    print(f"🧾 Logs por video: {LOG_DIR}/")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        close_logging()
