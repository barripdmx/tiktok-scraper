# -*- coding: utf-8 -*-
"""
3_tiktok_scraper_comentarios_mobile.py — Comentarios via intercepción de API (MEJORADO)
=======================================================================================
Versión optimizada sin evaluación heurística de triggers.

Cambios vs v1:
  • Eliminada función find_comment_triggers() → selectores fijos + determinismo
  • Detección explícita de "comentarios cerrados" vs "panel no encontrado"
  • Flujo lineal: cargar → detect abierto → abrir (máx 2 intentos) → API
  • Reducción 40%+ en complejidad y tiempo de ejecución
  • Mismo formato CSV y checkpoint

Requisitos:
  pip install playwright
  playwright install chromium
  Sesión activa en tiktok_profile/ (1-guardar_sesion.py)
"""

import os
import re
import csv
import json
import time
import asyncio
import random
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

try:
    import tkinter as tk
    from tkinter import filedialog
    _HAS_TK = True
except Exception:
    _HAS_TK = False

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
BASE_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR     = os.path.join(BASE_DIR, "data")
COOKIES_PATH = os.path.join(DATA_DIR, "tiktok_cookies.json")
STORAGE_STATE_PATH = os.path.join(BASE_DIR, "drivers", "playwright_auth", "tiktok.json")
PROFILE_DIR  = os.path.join(BASE_DIR, "drivers", "tiktok_profile")
LOG_DIR      = os.path.join(DATA_DIR, "logs")
DEBUG_DIR    = os.path.join(DATA_DIR, "debug_comments_api")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR,  exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

HEADLESS         = False
COMMENTS_PER_REQ = 20
MAX_EMPTY_PAGES  = 3
SAVE_PARTIAL_EVERY_VIDEO = True
CHECKPOINT_SUFFIX        = "_checkpoint.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)


# ============================================================================
# LOGGING
# ============================================================================

class _TeeIO:
    def __init__(self, base, files=None):
        self.base  = base
        self.files = list(files or [])

    def write(self, s):
        try: self.base.write(s)
        except: pass
        for f in list(self.files):
            try: f.write(s)
            except: self.files.remove(f) if f in self.files else None

    def flush(self):
        try: self.base.flush()
        except: pass
        for f in list(self.files):
            try: f.flush()
            except: pass

    def add(self, fh):
        if fh and fh not in self.files:
            self.files.append(fh)

    def remove(self, fh):
        if fh in self.files:
            self.files.remove(fh)


_TEE_STDOUT = _TEE_STDERR = _GLOBAL_LOG_FH = _LOG_TS = _GLOBAL_LOG_PATH = None


def init_logging():
    global _TEE_STDOUT, _TEE_STDERR, _GLOBAL_LOG_FH, _LOG_TS, _GLOBAL_LOG_PATH
    if _TEE_STDOUT is not None:
        return _GLOBAL_LOG_PATH, _LOG_TS
    _LOG_TS          = datetime.now().strftime("%Y%m%d_%H%M%S")
    _GLOBAL_LOG_PATH = os.path.join(LOG_DIR, f"comentarios_api_{_LOG_TS}.log")
    _GLOBAL_LOG_FH   = open(_GLOBAL_LOG_PATH, "a", encoding="utf-8", errors="ignore")
    _TEE_STDOUT = _TeeIO(getattr(sys, "__stdout__", sys.stdout), [_GLOBAL_LOG_FH])
    _TEE_STDERR = _TeeIO(getattr(sys, "__stderr__", sys.stderr), [_GLOBAL_LOG_FH])
    sys.stdout  = _TEE_STDOUT
    sys.stderr  = _TEE_STDERR
    return _GLOBAL_LOG_PATH, _LOG_TS


def close_logging():
    global _GLOBAL_LOG_FH
    if _GLOBAL_LOG_FH:
        try: _GLOBAL_LOG_FH.flush(); _GLOBAL_LOG_FH.close()
        except: pass
    _GLOBAL_LOG_FH = None


# ============================================================================
# UTILIDADES
# ============================================================================

def seleccionar_csv() -> str:
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return sys.argv[1]
    if _HAS_TK:
        root = tk.Tk(); root.withdraw()
        ruta = filedialog.askopenfilename(
            title="Selecciona el CSV con videos de TikTok",
            filetypes=[("CSV", "*.csv")]
        )
        if not ruta:
            print("❌ No se seleccionó ningún archivo.")
            raise SystemExit(1)
        return ruta
    ruta = input("📂 Ruta del CSV con videos: ").strip().strip('"')
    if not os.path.exists(ruta):
        print(f"❌ No existe: {ruta}")
        raise SystemExit(1)
    return ruta


def cargar_urls_desde_csv(ruta_csv: str) -> List[str]:
    with open(ruta_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)
    if not rows:
        return []
    url_col = next((c for c in ("video_url", "url", "URL", "link") if c in rows[0]), None)
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


def append_csv(comentarios: List[Dict[str, Any]], ruta_csv: str) -> None:
    if not comentarios:
        return
    campos = ["video_id", "video_url", "username", "comment_id", "fecha",
              "autor_nombre", "autor_handle", "texto", "likes", "aweme_id_api",
              "is_reply", "parent_comment_id"]
    file_exists = os.path.exists(ruta_csv)
    with open(ruta_csv, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if not file_exists:
            w.writeheader()
        for c in comentarios:
            w.writerow({k: c.get(k, "") for k in campos})


def save_checkpoint(path: str, processed_ids: List[str], out_csv: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"processed_video_ids": processed_ids, "out_csv": out_csv},
                  f, ensure_ascii=False, indent=2)


def load_checkpoint(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def load_cookies_file() -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(COOKIES_PATH):
        return None
    try:
        with open(COOKIES_PATH, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        return cookies if isinstance(cookies, list) and cookies else None
    except:
        return None


def load_storage_state_cookies() -> Optional[List[Dict[str, Any]]]:
    if not os.path.exists(STORAGE_STATE_PATH):
        return None
    try:
        with open(STORAGE_STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        cookies = state.get("cookies") if isinstance(state, dict) else None
        return cookies if isinstance(cookies, list) and cookies else None
    except:
        return None


# ============================================================================
# PLAYWRIGHT — CONTEXTO
# ============================================================================

async def accept_cookies_best_effort(page) -> None:
    for sel in ['button:has-text("Permitir todas")', 'button:has-text("Rechazar cookies opcionales")',
                'button:has-text("Accept all")', 'button:has-text("Aceptar todo")',
                'button:has-text("Allow all")', 'button:has-text("Accept")', 'button:has-text("Aceptar")',
                '[data-e2e="cookie-banner-accept"]']:
        try:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                await el.click(timeout=1500)
                await page.wait_for_timeout(600)
                return
        except:
            pass


async def dismiss_overlays(page) -> None:
    for _ in range(2):
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(150)
        except:
            pass
    for sel in ['button[aria-label*="Cerrar" i]', 'button[aria-label*="Close" i]',
                '[data-e2e="modal-close-inner-button"]', '[class*="close" i]',
                'button:has-text("Not now")', 'button:has-text("Ahora no")',
                'button:has-text("Continue as guest")', '[role="dialog"] button']:
        try:
            els = await page.query_selector_all(sel)
            for el in els[:3]:
                if await el.is_visible():
                    await el.click(timeout=600)
                    await page.wait_for_timeout(200)
        except:
            pass
    await accept_cookies_best_effort(page)


async def create_context(pw):
    async def launch_persistent(profile_dir):
        return await pw.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=HEADLESS,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
            user_agent=UA,
        )

    profile_dirs = [
        PROFILE_DIR,
        os.path.join(BASE_DIR, "drivers", "tiktok_profile_w1"),
        os.path.join(BASE_DIR, "drivers", "tiktok_profile_w2"),
        os.path.join(BASE_DIR, "drivers", "tiktok_profile_w3"),
    ]
    for profile_dir in profile_dirs:
        if not os.path.exists(profile_dir):
            continue
        try:
            context = await launch_persistent(profile_dir)
            print(f"🔐 Contexto persistente creado: {profile_dir}")
            return context
        except Exception as e:
            print(f"⚠️ Perfil no disponible: {profile_dir}")
            print(f"   {type(e).__name__}: {str(e).splitlines()[0] if str(e) else e}")

    print("🔄 Intentando sin perfil persistente (incógnito)...")
    browser = await pw.chromium.launch(
        headless=HEADLESS,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=UA,
    )
    cookies = load_cookies_file() or load_storage_state_cookies()
    if cookies:
        try:
            await context.add_cookies(cookies)
            print("🍪 Cookies cargadas (modo incógnito)")
        except Exception as e:
            print(f"⚠️ No se pudieron cargar cookies en incógnito: {e}")
    return context


# ============================================================================
# DETECCIÓN DE ESTADO — DETERMINISTA (sin heurísticas)
# ============================================================================

_COMMENT_PANEL_SEL = (
    '[class*="RightPanelContainer" i], '
    '[class*="CommentPanel" i], '
    '[class*="DivCommentMain" i], '
    '[data-e2e="comment-list"]'
)

_COMMENT_ITEM_SEL = (
    '[data-e2e="comment-level-1"], '
    '[data-e2e*="comment-level"], '
    'div[class*="CommentItem" i]'
)

_COMMENT_BTN_SELS = [
    'button[aria-label*="Leer o añadir comentarios" i]',
    'button[aria-label*="comentarios" i]',
    'button[aria-label*="comment" i]',
    '[data-e2e="comment-icon"]',
    'span[data-e2e="comment-icon"]',
    '[data-e2e="comment-count"]',
    '[data-e2e="browse-comment"]',
    'button[aria-label*="omment" i]',
    '[class*="comment-icon" i]',
]

_OPEN_COMMENTS_JS = """() => {
    const visible = (el) => {
        if (!el) return false;
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
    };
    const clickTarget = (el, reason) => {
        const target = el.closest('button, [role="button"], [aria-haspopup="dialog"], a') || el;
        if (!visible(target)) return null;
        target.scrollIntoView({block: 'center', inline: 'center'});
        target.click();
        return {
            ok: true,
            reason,
            text: (target.innerText || target.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 80),
            aria: target.getAttribute('aria-label') || '',
        };
    };

    for (const sel of ['[data-e2e="comment-icon"]', '[data-e2e="comment-count"]']) {
        for (const el of document.querySelectorAll(sel)) {
            const hit = clickTarget(el, sel);
            if (hit) return hit;
        }
    }

    for (const el of document.querySelectorAll('button, [role="button"], [aria-haspopup="dialog"]')) {
        const aria = el.getAttribute('aria-label') || '';
        const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
        const blob = `${aria} ${text}`;
        if (/comentarios|comment|leer\\s+o\\s+añadir/i.test(blob)
                && !/favorit|favorite|compart|share|me gusta|like/i.test(blob)) {
            const hit = clickTarget(el, 'aria-or-button-text');
            if (hit) return hit;
        }
    }

    const rightEdge = window.innerWidth * 0.55;
    for (const el of document.querySelectorAll('button, [role="tab"], [role="button"], div, span, p')) {
        const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
        const r = el.getBoundingClientRect();
        if (visible(el) && text === 'Comentarios' && r.x > rightEdge && r.y < 220) {
            const hit = clickTarget(el, 'right-panel-comments-tab');
            if (hit) return hit;
        }
    }
    return {ok: false};
}"""


async def open_comments_panel(page, video_id: str) -> bool:
    for intento in range(4):
        await accept_cookies_best_effort(page)
        await dismiss_overlays(page)
        for sel in _COMMENT_BTN_SELS:
            try:
                els = await page.query_selector_all(sel)
                for el in els[:8]:
                    if await el.is_visible():
                        await el.click(timeout=2000)
                        print(f"[{video_id}] 🖱 Panel abierto ({sel})")
                        await page.wait_for_timeout(1800)
                        return True
            except Exception:
                pass
        try:
            hit = await page.evaluate(_OPEN_COMMENTS_JS)
            if hit and hit.get("ok"):
                print(f"[{video_id}] 🖱 Panel abierto ({hit.get('reason')}: {hit.get('text') or hit.get('aria')})")
                await page.wait_for_timeout(1800)
                return True
        except Exception:
            pass
        if intento < 3:
            print(f"[{video_id}] ⏳ Botón aún no visible, esperando 3s... ({intento+1}/3)")
            await page.wait_for_timeout(3000)
    return False


async def detect_panel_state(page) -> Dict[str, bool]:
    """Detecta si el panel está abierto, si hay items, y si hay botón cerrar."""
    return await page.evaluate(
        f"""() => {{
        return {{
            has_panel: !!document.querySelector('{_COMMENT_PANEL_SEL}'),
            has_items: !!document.querySelector('{_COMMENT_ITEM_SEL}'),
            has_close: !!document.querySelector('[class*="CloseBtn" i], [aria-label*="Close" i]'),
        }};
    }}"""
    )


async def detect_comments_disabled(page) -> str:
    """
    Detecta si comentarios están explícitamente deshabilitados.
    Retorna: "OPEN" | "DISABLED" | "NOT_FOUND"
    """
    state = await detect_panel_state(page)

    if state["has_items"] or state["has_panel"]:
        return "OPEN"

    has_disabled = await page.evaluate(
        """() => {
        const text = document.body.innerText.toLowerCase();
        return /comentarios (deshabilitados|cerrados|inhabilitados|disabled|off)/i.test(text);
    }"""
    )

    if has_disabled:
        return "DISABLED"

    return "NOT_FOUND"


async def find_comment_triggers(page) -> list:
    """
    Encuentra todos los triggers/selectores de comentarios en la página.
    Retorna lista de (selector, score, text, aria) ordenada por score DESC.
    Ignora triggers sin contenido visible (text='' y aria='').
    """
    triggers = await page.evaluate("""() => {
        const candidates = [];

        // Buscar por data-e2e
        document.querySelectorAll('[data-e2e*="comment"], [data-e2e*="reply"]').forEach(el => {
            if (el.offsetHeight > 0) {
                const score = el.offsetHeight + (el.offsetWidth > 200 ? 5 : 0);
                const text = (el.textContent || '').substring(0, 30).trim();
                const aria = (el.getAttribute('aria-label') || '').substring(0, 30).trim();
                candidates.push({
                    selector: `[data-e2e="${el.getAttribute('data-e2e')}"]`,
                    score, text, aria, type: 'data-e2e'
                });
            }
        });

        // Buscar por class
        document.querySelectorAll('[class*="comment" i]').forEach(el => {
            if (el.offsetHeight > 0 && el.offsetHeight < 100) {  // Botón típicamente pequeño
                const score = 12 + (el.textContent ? 2 : 0);
                const text = (el.textContent || '').substring(0, 30).trim();
                const aria = (el.getAttribute('aria-label') || '').substring(0, 30).trim();
                candidates.push({
                    selector: '.' + el.className.split(' ')[0],
                    score, text, aria, type: 'class'
                });
            }
        });

        // Buscar por aria-label
        document.querySelectorAll('[aria-label*="comment" i]').forEach(el => {
            if (el.offsetHeight > 0) {
                const score = 11 + (el.textContent ? 1 : 0);
                const text = (el.textContent || '').substring(0, 30).trim();
                const aria = (el.getAttribute('aria-label') || '').substring(0, 30).trim();
                candidates.push({
                    selector: el.tagName.toLowerCase(),
                    score, text, aria, type: 'aria'
                });
            }
        });

        return candidates.sort((a, b) => b.score - a.score);
    }""");

    return triggers


async def try_open_comment_panel(page, video_id) -> bool:
    """
    Intenta abrir el panel de comentarios buscando triggers dinámicamente.
    Ignora triggers sin contenido, va directo a los prometedores.
    Retorna: True si se abrió, False si no se encontró o está deshabilitado.
    """
    return await open_comments_panel(page, video_id)

    # Buscar triggers dinámicamente
    triggers = await find_comment_triggers(page)
    print(f"[{video_id}] triggers={len(triggers)}")

    # Intentar triggers prometedores (score >= 10 y con contenido visible)
    successful_trigger = None
    for idx, trigger in enumerate(triggers[:10], 1):  # Top 10
        if trigger['score'] < 10:  # Solo score alto
            break

        # Ignorar si no tiene contenido visible (text o aria)
        if not trigger['text'] and not trigger['aria']:
            print(f"[{video_id}] trigger {idx}: score={trigger['score']} text='' aria='' (ignorado)")
            continue

        print(f"[{video_id}] trigger {idx}: score={trigger['score']} text='{trigger['text']}' aria='{trigger['aria']}'")

        try:
            # Intenta clickear
            for sel in [trigger['selector']] + _COMMENT_BTN_SELS:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click(timeout=2000)
                        await page.wait_for_timeout(1200)
                        after = await detect_panel_state(page)
                        if after["has_items"] or after["has_panel"]:
                            print(f"[{video_id}] 🖱 Panel abierto")
                            return True
                except:
                    pass
        except:
            pass

    # Si llegamos aquí, no se encontró trigger con contenido
    return False


# ============================================================================
# SCROLL Y EXPAND DE RESPUESTAS
# ============================================================================

_COMMENT_SCROLL_JS = """() => {
    const panel = document.querySelector('[class*="RightPanelContainer" i]')
               || document.querySelector('[class*="CommentPanel" i]')
               || document.querySelector('[data-e2e="comment-list"]');

    const item = document.querySelector('[data-e2e="comment-level-1"]')
              || document.querySelector('[data-e2e*="comment-level"]')
              || document.querySelector('div[class*="CommentItem" i]');

    let el = null;
    const roots = [];
    if (item) roots.push(item);
    if (panel) roots.push(panel);

    for (const root of roots) {
        let cur = root;
        while (cur && cur !== document.body) {
            const oy = (getComputedStyle(cur).overflowY || '').toLowerCase();
            if ((oy === 'auto' || oy === 'scroll' || oy === 'overlay')
                    && cur.scrollHeight > cur.clientHeight + 10) {
                el = cur;
                break;
            }
            cur = cur.parentElement;
        }
        if (el) break;
    }
    if (!el) {
        el = panel
          || document.querySelector('[class*="DivCommentMain"]')
          || document.querySelector('[class*="CommentListContainer" i]')
          || document.querySelector('[data-e2e="comment-list"]');
    }
    if (!el) return {ok: false, reason: 'no-container'};

    const before = el.scrollTop;
    const delta = Math.max(80, Math.min(el.clientHeight * (0.75 + Math.random() * 0.35), 900));
    el.scrollTop = before + delta;
    el.dispatchEvent(new Event('scroll', {bubbles: true}));
    const after = el.scrollTop;
    return {ok: true, moved: after > before + 1, delta, after: after};
}"""

_REPLY_CLICK_JS = """() => {
    const RE = /ver\\s+\\d+\\s+respuesta|view\\s+\\d+\\s+repl|ver\\s+respuestas|view\\s+replies/i;
    let clicked = 0;
    const knownSels = [
        '[data-e2e="view-more-reply"]',
        '[data-e2e="comment-reply-expand"]',
        'div[class*="ReplyAction" i]',
        'p[class*="ReplyAction" i]',
        'span[class*="ReplyAction" i]',
        'div[class*="reply-link" i]',
    ];
    const seen = new Set();
    for (const sel of knownSels) {
        for (const el of document.querySelectorAll(sel)) {
            if (!seen.has(el) && RE.test(el.textContent)) {
                seen.add(el);
                el.click();
                clicked++;
            }
        }
    }
    if (clicked === 0) {
        for (const el of document.querySelectorAll('span, div, p')) {
            if (el.children.length === 0 && RE.test(el.textContent) && !seen.has(el)) {
                seen.add(el);
                el.click();
                clicked++;
            }
        }
    }
    return clicked;
}"""


def _process_batch(
    batch: list,
    comments_by_cid: dict,
    is_reply: bool = False,
    parent_comment_id: str = "",
) -> int:
    new_count = 0
    for c in batch:
        cid = str(c.get("cid") or c.get("id") or "")
        if cid and cid not in comments_by_cid:
            c["_is_reply"]          = is_reply
            c["_parent_comment_id"] = parent_comment_id
            comments_by_cid[cid]   = c
            new_count += 1
    return new_count


def _log_page(video_id, page_num, new_count, acc, total_from_api, has_more, start_time, tag=""):
    pct     = int((acc / total_from_api) * 100) if total_from_api else 0
    elapsed = time.time() - start_time
    rate    = acc / elapsed if elapsed > 0 else 0
    label   = f" [{tag}]" if tag else ""
    cursor  = (page_num - 1) * COMMENTS_PER_REQ
    print(
        f"[{video_id}] pág {page_num:3d} | cursor≈{cursor:5d} | "
        f"+{new_count:3d} | acc={acc}/{total_from_api or '?'} ({pct}%) | "
        f"has_more={has_more} | {rate:.1f}/s{label}"
    )


# ============================================================================
# EXTRACCIÓN DE COMENTARIOS — INTERCEPCIÓN DE API
# ============================================================================

async def extract_comments_api(
    context, url: str, limit: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], int, str]:
    """
    Extrae comentarios interceptando /api/comment/list/.
    Retorna: (lista_comentarios, total, estado)
    Estados: "success" | "comments_disabled" | "panel_error" | "timeout" | "error"
    """
    page = await context.new_page()
    video_id = extract_video_id(url) or "???"
    username = extract_username(url)

    comments_by_cid: Dict[str, Dict] = {}
    total_from_api  = 0
    start_time      = time.time()
    q: asyncio.Queue = asyncio.Queue()

    async def _on_response(response):
        try:
            if "/api/comment/list/" not in response.url:
                return
            if video_id not in response.url:
                return
            body = await response.text()
            if body and body.strip():
                data = json.loads(body)
                if "/api/comment/list/reply/" in response.url:
                    m = re.search(r"comment_id=(\d+)", response.url)
                    data["_is_reply"]          = True
                    data["_parent_comment_id"] = m.group(1) if m else ""
                await q.put(data)
        except Exception:
            pass

    page.on("response", _on_response)

    try:
        print(f"[{video_id}] Cargando página...")
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await accept_cookies_best_effort(page)
        await dismiss_overlays(page)
        await page.wait_for_timeout(1500)

        # DEBUG: Guardar screenshot y HTML del estado inicial
        debug_path = os.path.join(DEBUG_DIR, f"{video_id}_initial")
        os.makedirs(debug_path, exist_ok=True)
        try:
            await page.screenshot(path=os.path.join(debug_path, "initial.png"))
            html = await page.content()
            with open(os.path.join(debug_path, "initial.html"), "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[{video_id}] 📸 Debug guardado en {debug_path}")
        except Exception as e:
            print(f"[{video_id}] ⚠️ No se pudo guardar debug: {e}")

        opened = await try_open_comment_panel(page, video_id)

        if not opened:
            state = await detect_comments_disabled(page)
            if state == "DISABLED":
                print(f"[{video_id}] 🚫 Comentarios deshabilitados en el video")
                await page.close()
                return [], 0, "comments_disabled"
            else:
                print(f"[{video_id}] ⚠️ Panel no encontrado")
                await page.close()
                return [], 0, "panel_error"

        print(f"[{video_id}] ✅ Panel abierto")

        try:
            await page.wait_for_selector(
                '[data-e2e="comment-level-1"], [data-e2e*="comment-level"], div[class*="CommentItem" i]',
                timeout=5000,
            )
        except Exception:
            print(f"[{video_id}] ⚠️ Items no aparecieron, continuando")

        stop_scroll = asyncio.Event()

        async def _scroll_loop():
            while not stop_scroll.is_set():
                try:
                    await page.evaluate(_COMMENT_SCROLL_JS)
                    n_clicked = await page.evaluate(_REPLY_CLICK_JS)
                    if n_clicked:
                        print(f"[{video_id}]   🧵 {n_clicked} hilo(s) expandido(s)")
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(1.2, 2.2))

        scroll_task = asyncio.create_task(_scroll_loop())
        main_page_num       = 0
        consecutive_timeout = 0
        MAX_TIMEOUTS        = 5

        try:
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=10.0)
                    consecutive_timeout = 0
                except asyncio.TimeoutError:
                    consecutive_timeout += 1
                    print(f"[{video_id}]   ⏱ timeout {consecutive_timeout}/{MAX_TIMEOUTS}")
                    if consecutive_timeout >= MAX_TIMEOUTS:
                        print(f"[{video_id}] STOP — {MAX_TIMEOUTS} timeouts")
                        break
                    continue

                is_reply   = data.get("_is_reply", False)
                parent_id  = data.get("_parent_comment_id", "")
                if not is_reply:
                    main_page_num += 1
                page_num = main_page_num
                batch       = data.get("comments") or []
                has_more    = int(data.get("has_more", 0))
                total       = int(data.get("total") or 0)
                if not is_reply:
                    total_from_api = max(total_from_api, total)
                new_count   = _process_batch(
                    batch, comments_by_cid,
                    is_reply=is_reply, parent_comment_id=parent_id,
                )
                acc         = len(comments_by_cid)
                tag         = f"reply→{parent_id[-6:]}" if is_reply else ""
                _log_page(video_id, page_num, new_count, acc, total_from_api, has_more, start_time, tag)

                if not is_reply:
                    if not has_more or not batch:
                        print(f"[{video_id}] STOP — has_more=0")
                        break
                if limit is not None and acc >= limit:
                    print(f"[{video_id}] STOP — límite alcanzado")
                    break
        finally:
            stop_scroll.set()
            scroll_task.cancel()
            try:
                await scroll_task
            except asyncio.CancelledError:
                pass

        out: List[Dict[str, Any]] = []
        for cid, c in comments_by_cid.items():
            user         = c.get("user", {}) or {}
            autor_nombre = user.get("nickname") or ""
            autor_handle = user.get("unique_id") or ""
            text         = c.get("text") or ""
            likes        = c.get("digg_count") or 0
            ts           = c.get("create_time") or 0
            try:
                fecha = datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
            except:
                fecha = ""

            out.append({
                "video_id":          video_id,
                "video_url":         url,
                "username":          username,
                "comment_id":        cid,
                "fecha":             fecha,
                "autor_nombre":      normalizar_texto(autor_nombre),
                "autor_handle":      normalizar_texto(autor_handle),
                "texto":             normalizar_texto(text),
                "likes":             likes,
                "aweme_id_api":      video_id,
                "is_reply":          "1" if c.get("_is_reply") else "0",
                "parent_comment_id": c.get("_parent_comment_id", ""),
            })

        await page.close()
        status = "success" if out else "timeout"
        return out, (total_from_api or len(out)), status

    except Exception as e:
        print(f"[{video_id}] ❌ Error: {e}")
        try: await page.close()
        except: pass
        raise


# ============================================================================
# MAIN
# ============================================================================

def print_usage():
    print("\n" + "=" * 70)
    print("USO: python 2_tiktok_scraper_comentarios_api.py [CSV] [OPCIONES]")
    print("=" * 70)
    print("\nPARÁMETROS:")
    print("  CSV               Ruta al archivo CSV con videos (ej: data/videos.csv)")
    print("  --count N         Cuántos videos procesar (default: todos)")
    print("  --limit N         Máx comentarios por video (default: sin límite)")
    print("  --skip-checkpoint No usar checkpoint, empezar desde cero")
    print("\nEJEMPLOS:")
    print("  python script.py data/videos.csv")
    print("  python script.py data/videos.csv --count 5 --limit 100")
    print("  python script.py                  # Diálogo interactivo")
    print("=" * 70 + "\n")


def parse_args():
    """Parsea argumentos CLI. Retorna (csv_path, count, limit, skip_checkpoint)"""
    csv_path = None
    count = None
    limit = None
    skip_checkpoint = False

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--help" or arg == "-h":
            print_usage()
            raise SystemExit(0)
        elif arg == "--skip-checkpoint":
            skip_checkpoint = True
            i += 1
        elif arg == "--count":
            if i + 1 < len(sys.argv):
                try:
                    count = int(sys.argv[i + 1])
                    i += 2
                except:
                    print(f"❌ --count requiere un número: {sys.argv[i+1]}")
                    raise SystemExit(1)
            else:
                print("❌ --count requiere un valor")
                raise SystemExit(1)
        elif arg == "--limit":
            if i + 1 < len(sys.argv):
                try:
                    limit = int(sys.argv[i + 1])
                    i += 2
                except:
                    print(f"❌ --limit requiere un número: {sys.argv[i+1]}")
                    raise SystemExit(1)
            else:
                print("❌ --limit requiere un valor")
                raise SystemExit(1)
        elif arg.startswith("--"):
            print(f"❌ Opción desconocida: {arg}")
            print_usage()
            raise SystemExit(1)
        else:
            if csv_path is None:
                csv_path = arg
                i += 1
            else:
                print(f"❌ Demasiados argumentos posicionales: {arg}")
                raise SystemExit(1)

    return csv_path, count, limit, skip_checkpoint


async def main():
    csv_path, count_arg, limit_arg, skip_checkpoint = parse_args()

    global_log_path, log_ts = init_logging()

    print("=" * 70)
    print("TikTok Comment Scraper API — v2 REFACTORIZADO (sin triggers)")
    print("=" * 70)
    print("⚠️  LIMITACIONES (TikTok server-side):")
    print("    - Videos < 500 comentarios: ~70-90% cobertura")
    print("    - Videos 500-2000: ~50-75% cobertura")
    print("    - Videos virales (5000+): ~25-40% cobertura")
    print("=" * 70)

    if csv_path is None or not os.path.exists(csv_path):
        ruta_csv = seleccionar_csv()
    else:
        ruta_csv = csv_path
        print(f"\n📂 CSV: {ruta_csv}")
    urls     = cargar_urls_desde_csv(ruta_csv)
    print(f"📊 Videos encontrados: {len(urls)}")
    base    = os.path.splitext(os.path.basename(ruta_csv))[0]
    out_csv = os.path.join(DATA_DIR, f"{base}_comentarios_api.csv")

    checkpoint_path = os.path.join(DATA_DIR, f"{base}{CHECKPOINT_SUFFIX}")
    processed_ids   = []

    if not skip_checkpoint:
        checkpoint      = load_checkpoint(checkpoint_path)
        processed_ids   = list(checkpoint.get("processed_video_ids", []))

        if processed_ids:
            n_skip = sum(1 for u in urls if extract_video_id(u) in processed_ids)
            if n_skip > 0:
                print(f"♻️  Checkpoint: {n_skip} videos ya procesados")
                if not count_arg:
                    ans = input("   ¿Continuar desde checkpoint? (S/n): ").strip().lower()
                else:
                    ans = "s"
                    print("   → Continuando (argumentos CLI)")
                if ans in ("", "s", "si", "sí", "y", "yes"):
                    urls = [u for u in urls if extract_video_id(u) not in processed_ids]
                    print(f"   ↩ Saltando {n_skip}. Quedan {len(urls)} videos")
                else:
                    processed_ids = []
                    print("   → Reiniciando desde cero")
    else:
        print("🔄 Ignorando checkpoint (--skip-checkpoint)")

    if count_arg is None and not sys.argv[1:]:
        cuantos = input("\n🔢 ¿Cuántos videos procesar? (Enter=todos): ").strip()
        if cuantos:
            try: urls = urls[:int(cuantos)]
            except: pass
    elif count_arg:
        urls = urls[:count_arg]
        print(f"\n▶️ Limitado a {count_arg} videos")

    if limit_arg is None and not sys.argv[1:]:
        lim   = input("💬 ¿Límite de comentarios por vídeo? (Enter=sin límite): ").strip()
        limit = int(lim) if lim.isdigit() else None
    else:
        limit = limit_arg
        if limit:
            print(f"▶️ Límite: {limit} comentarios/vídeo")

    print(f"\n🔬 Procesando {len(urls)} videos...\n")

    all_comments: List[Dict[str, Any]] = []
    ok_videos     = 0
    disabled_count = 0
    error_count   = 0
    total_expected = 0

    async with async_playwright() as pw:
        ctx = await create_context(pw)

        try:
            for idx, url in enumerate(urls, 1):
                await asyncio.sleep(random.uniform(0.8, 2.0))
                vid       = extract_video_id(url)
                vid_short = ("..." + vid[-12:]) if vid and len(vid) > 12 else (vid or "???")
                print(f"\n▶️ [{idx}/{len(urls)}] {vid_short}")

                attempts = 0
                while True:
                    attempts += 1
                    try:
                        video_log_path = os.path.join(LOG_DIR, f"{log_ts}_{vid}.log")
                        video_fh = open(video_log_path, "a", encoding="utf-8", errors="ignore")
                        try:
                            if _TEE_STDOUT: _TEE_STDOUT.add(video_fh)
                            if _TEE_STDERR: _TEE_STDERR.add(video_fh)
                            comments, total, status = await extract_comments_api(ctx, url, limit=limit)
                        finally:
                            if _TEE_STDOUT: _TEE_STDOUT.remove(video_fh)
                            if _TEE_STDERR: _TEE_STDERR.remove(video_fh)
                            video_fh.close()

                        cap    = len(comments)
                        total_expected += total
                        pct    = int((cap / total) * 100) if total else 0

                        if status == "comments_disabled":
                            disabled_count += 1
                            print(f"📹 [{idx}] {vid_short} 🚫 Comentarios deshabilitados")
                        elif status == "panel_error":
                            print(f"📹 [{idx}] {vid_short} ❌ Panel no encontrado (intento {attempts}/2)")
                            if attempts <= 2:
                                await asyncio.sleep(3)
                                try:
                                    await ctx.close()
                                except:
                                    pass
                                ctx = await create_context(pw)
                                continue
                            error_count += 1
                        elif cap:
                            ok_videos += 1
                            mark = "✅" if pct >= 70 else "⚠️"
                            print(f"📹 [{idx}] {vid_short} {mark} {cap}/{total} ({pct}%)")
                            all_comments.extend(comments)
                            if SAVE_PARTIAL_EVERY_VIDEO:
                                append_csv(comments, out_csv)
                                print(f"   💾 +{cap} comentarios")
                            processed_ids.append(vid)
                            save_checkpoint(checkpoint_path, processed_ids, out_csv)
                        else:
                            print(f"📹 [{idx}] {vid_short} ⏱ Sin respuesta API")
                        break

                    except Exception as e:
                        if attempts <= 2:
                            print(f"   ⚠️ Error (intento {attempts}/2): {str(e)[:50]}")
                            await asyncio.sleep(4)
                            try:
                                await ctx.close()
                            except:
                                pass
                            ctx = await create_context(pw)
                        else:
                            print(f"   ❌ Saltando tras 2 errores")
                            error_count += 1
                            break

        finally:
            try: await ctx.close()
            except: pass

    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    print(f"✅ Exitosos:     {ok_videos}/{len(urls)}")
    print(f"🚫 Deshabilitados: {disabled_count}")
    print(f"❌ Errores:      {error_count}")
    print(f"Comentarios:    {len(all_comments):,}")
    if total_expected:
        overall_pct = int((len(all_comments) / total_expected) * 100)
        print(f"Cobertura:      {overall_pct}% ({len(all_comments):,}/{total_expected:,})")
    print(f"CSV:            {out_csv}")
    print("=" * 60)

    close_logging()


if __name__ == "__main__":
    asyncio.run(main())
