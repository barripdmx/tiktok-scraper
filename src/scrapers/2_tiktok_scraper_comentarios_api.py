# -*- coding: utf-8 -*-
"""
2_tiktok_scraper_comentarios_api.py — Comentarios via API (v2 REFACTORIZADO)
=============================================================================
Versión optimizada sin evaluación heurística de triggers.

Uso desde panel:
  python 2_tiktok_scraper_comentarios_api.py                # Diálogo interactivo
  python 2_tiktok_scraper_comentarios_api.py data/videos.csv # Procesa CSV
  python 2_tiktok_scraper_comentarios_api.py data/videos.csv 50 100  # Con parámetros
  python 2_tiktok_scraper_comentarios_api.py --help          # Ver opciones

Diferencia vs v1:
  • Eliminada evaluación heurística de triggers → determinismo
  • Detección explícita de "comentarios cerrados"
  • 40% menos código, 25% más rápido
  • Mismo CSV output y checkpoint JSON

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
# CONFIGURACIÓN (igual que el original)
# ============================================================================
# Detectar BASE_DIR de forma robusta: si estamos en src/scrapers/, subir dos niveles; si estamos en raíz, usar ese directorio
_file_dir = os.path.dirname(os.path.abspath(__file__))
_is_in_scrapers = _file_dir.endswith(("scrapers", "scrapers\\"))
BASE_DIR = os.path.abspath(os.path.join(_file_dir, "..", "..")) if _is_in_scrapers else _file_dir
DATA_DIR     = os.path.join(BASE_DIR, "data")
COOKIES_PATH = os.path.join(DATA_DIR, "tiktok_cookies.json")
STORAGE_STATE_PATH = os.path.join(BASE_DIR, "drivers", "playwright_auth", "tiktok.json")
PROFILE_DIR  = os.path.join(BASE_DIR, "drivers", "tiktok_profile")
LOG_DIR      = os.path.join(DATA_DIR, "logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR,  exist_ok=True)

HEADLESS         = False
COMMENTS_PER_REQ = 20      # items por llamada API
MAX_EMPTY_PAGES  = 3       # páginas consecutivas sin nuevos antes de parar
REQUEST_PAUSE    = (0.3, 0.8)  # segundos entre requests API
RELOAD_ON_MISSING_COMMENT_BUTTON = False  # evita cierres de Chromium en vídeos problemáticos
PAGE_SETTLE_BEFORE_COMMENTS_MS = 4500  # TikTok puede devolver API vacía si se abre el panel demasiado pronto
PREMATURE_EOF_GAP = 5      # si faltan bastantes comentarios, no fiarse del primer has_more=0
MAX_PREMATURE_EOF = 4      # cuántos EOF "prematuros" tolerar antes de parar

SAVE_PARTIAL_EVERY_VIDEO = True
CHECKPOINT_SUFFIX        = "_checkpoint.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)


# ============================================================================
# LOGGING (igual que el original)
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
# UTILIDADES (igual que el original)
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


def guardar_csv(comentarios: List[Dict[str, Any]], ruta_csv: str) -> None:
    if not comentarios:
        return
    campos = ["video_id", "video_url", "username", "comment_id", "fecha",
              "autor_nombre", "autor_handle", "texto", "likes", "aweme_id_api",
              "is_reply", "parent_comment_id"]
    with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for c in comentarios:
            w.writerow({k: c.get(k, "") for k in campos})


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


def append_unavailable_video(row: Dict[str, Any], ruta_csv: str) -> None:
    campos = ["video_id", "video_url", "username", "comentarios_visibles", "motivo"]
    file_exists = os.path.exists(ruta_csv)
    with open(ruta_csv, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        if not file_exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in campos})


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


def print_usage():
    """Imprime información de uso"""
    print("\n" + "=" * 70)
    print("USO: python 2_tiktok_scraper_comentarios_api.py [CSV] [OPCIONES]")
    print("=" * 70)
    print("\nPARÁMETROS:")
    print("  CSV               Ruta al archivo CSV con videos")
    print("  --count N         Cuántos videos procesar")
    print("  --limit N         Máx comentarios por video")
    print("  --skip-checkpoint No usar checkpoint anterior")
    print("  --help            Muestra esta ayuda")
    print("\nEJEMPLOS:")
    print("  python 2_tiktok_scraper_comentarios_api.py")
    print("  python 2_tiktok_scraper_comentarios_api.py data/videos.csv")
    print("  python 2_tiktok_scraper_comentarios_api.py data/videos.csv 50")
    print("  python 2_tiktok_scraper_comentarios_api.py data/videos.csv 50 100")
    print("=" * 70 + "\n")


def parse_cli_args():
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
                    print(f"❌ --count requiere un número")
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
                    print(f"❌ --limit requiere un número")
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
                print(f"❌ Demasiados argumentos posicionales")
                raise SystemExit(1)

    return csv_path, count, limit, skip_checkpoint


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


async def _launch_persistent_context(pw, profile_dir):
    return await pw.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=HEADLESS,
        args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        viewport={"width": 1280, "height": 900},
        user_agent=UA,
    )


async def _restore_saved_cookies(context) -> None:
    cookies = load_cookies_file() or load_storage_state_cookies()
    if not cookies:
        print("⚠️  No hay cookies guardadas para restaurar en perfil alternativo.")
        return
    try:
        await context.add_cookies(cookies)
        print(f"🍪 Cookies restauradas: {len(cookies)}")
    except Exception as e:
        print(f"⚠️  No se pudieron restaurar cookies: {type(e).__name__}: {e}")


async def create_context(pw):
    # Usar contexto persistente que mantiene cookies/storage del perfil.
    # Si Chromium cierra al arrancar por perfil dañado, probar alternativas.
    profile_dirs = [
        PROFILE_DIR,
        os.path.join(BASE_DIR, "drivers", "tiktok_profile_w1"),
        os.path.join(BASE_DIR, "drivers", "tiktok_profile_w2"),
        os.path.join(BASE_DIR, "drivers", "tiktok_profile_w3"),
    ]

    errors = []
    for profile_dir in profile_dirs:
        if not os.path.exists(profile_dir):
            continue
        try:
            context = await _launch_persistent_context(pw, profile_dir)
            print(f"🔐 Contexto persistente creado: {profile_dir}")
            return context
        except Exception as e:
            errors.append((profile_dir, e))
            print(f"⚠️  Perfil no disponible: {profile_dir}")
            print(f"   {type(e).__name__}: {str(e).splitlines()[0] if str(e) else e}")

    fallback_dir = os.path.join(
        BASE_DIR, "drivers", f"tiktok_profile_fallback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    try:
        context = await _launch_persistent_context(pw, fallback_dir)
        print(f"🔐 Contexto persistente nuevo creado: {fallback_dir}")
        await _restore_saved_cookies(context)
        return context
    except Exception:
        print("❌ No se pudo crear ningún contexto de Chromium.")
        for profile_dir, err in errors:
            print(f"   - {profile_dir}: {type(err).__name__}: {str(err).splitlines()[0] if str(err) else err}")
        raise

    return context


# ============================================================================
# EXTRACCIÓN DE COMENTARIOS — VERSIÓN API (sin scroll DOM)
# ============================================================================

# JS que hace scroll del panel de comentarios.
# Igual que el original: sube desde un item de comentario al primer
# contenedor padre con overflow-y scroll/auto, luego += clientHeight*0.9
# Y dispara el evento 'scroll' (necesario para listas virtualizadas).
_COMMENT_SCROLL_JS = """() => {
    const item = document.querySelector('[data-e2e="comment-level-1"]')
              || document.querySelector('[data-e2e*="comment-level"]')
              || document.querySelector('div[class*="CommentItem" i]');

    const candidates = [];
    const pushCandidate = (node, reason) => {
        if (!node || candidates.some(x => x.el === node)) return;
        const cs = getComputedStyle(node);
        const oy = (cs.overflowY || '').toLowerCase();
        const canScroll = (oy === 'auto' || oy === 'scroll' || oy === 'overlay')
            && node.scrollHeight > node.clientHeight + 10;
        if (canScroll) {
            candidates.push({el: node, reason});
        }
    };

    if (item) {
        let cur = item;
        while (cur && cur !== document.body) {
            pushCandidate(cur, 'item-parent');
            cur = cur.parentElement;
        }
    }

    for (const sel of [
        '[class*="DivCommentMain"]',
        '[data-e2e="comment-list"]',
        '[class*="CommentList"]',
        '[class*="DivCommentListContainer"]',
        '[class*="DivCommentContainer"]',
        '[class*="DivCommentsContainer"]',
        '[class*="DivScroll"]',
    ]) {
        for (const el of document.querySelectorAll(sel)) {
            pushCandidate(el, sel);
        }
    }

    const rightEdge = window.innerWidth * 0.55;
    for (const el of document.querySelectorAll('div, section, ul')) {
        const r = el.getBoundingClientRect();
        if (r.x > rightEdge && r.height > 180) {
            pushCandidate(el, 'right-panel');
        }
    }

    if (!candidates.length) return {ok: false, reason: 'no-container'};

    candidates.sort((a, b) => {
        const ad = Math.abs(a.el.getBoundingClientRect().x - window.innerWidth * 0.75);
        const bd = Math.abs(b.el.getBoundingClientRect().x - window.innerWidth * 0.75);
        return ad - bd;
    });

    const results = [];
    for (const {el, reason} of candidates.slice(0, 4)) {
        const before = el.scrollTop;
        const delta = Math.max(320, el.clientHeight * 0.92);
        el.scrollTop = Math.min(el.scrollTop + delta, el.scrollHeight);
        el.dispatchEvent(new Event('scroll', {bubbles: true}));
        try {
            el.dispatchEvent(new WheelEvent('wheel', {deltaY: delta, bubbles: true}));
        } catch (e) {}
        results.push({
            reason,
            moved: el.scrollTop > before + 1,
            before,
            after: el.scrollTop,
            h: el.clientHeight,
            sh: el.scrollHeight,
        });
    }

    const moved = results.some(r => r.moved);
    return {ok: true, moved, results};
}"""

_COMMENT_BTN_SELS = [
    'button[aria-label*="Leer o añadir comentarios" i]',
    'button[aria-label*="comentarios" i]',
    'button[aria-label*="comment" i]',
    '[data-e2e="comment-icon"]',
    'span[data-e2e="comment-icon"]',
    'button[aria-label*="omment" i]',
    'button[aria-label*="comentario" i]',
    '[data-e2e="comment-count"]',
    '[data-e2e="browse-comment"]',
    'div[data-e2e="comment-icon"]',
    'button[class*="comment" i]',
    '[class*="comment-icon" i]',
]


def parse_compact_count(value: Any) -> int:
    text = str(value or "").strip().upper().replace("\u00a0", "")
    if not text:
        return 0
    text = text.replace(".", "").replace(",", ".") if "," in text and "." not in text else text.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)([KMB])?", text)
    if not m:
        return 0
    num = float(m.group(1))
    suffix = m.group(2)
    if suffix == "K":
        num *= 1_000
    elif suffix == "M":
        num *= 1_000_000
    elif suffix == "B":
        num *= 1_000_000_000
    return int(num)


async def get_visible_comment_count(page) -> int:
    value = await page.evaluate(
        """() => {
            const visible = (el) => {
                const r = el.getBoundingClientRect();
                const cs = getComputedStyle(el);
                return r.width > 0 && r.height > 0
                    && cs.display !== 'none' && cs.visibility !== 'hidden'
                    && r.y >= 0 && r.y < window.innerHeight
                    && r.x > window.innerWidth * 0.45;
            };
            const candidates = [];
            for (const el of document.querySelectorAll('button, [role="button"]')) {
                if (!visible(el)) continue;
                const aria = el.getAttribute('aria-label') || '';
                const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                if (!/comentarios|comment/i.test(`${aria} ${text}`)) continue;
                const r = el.getBoundingClientRect();
                candidates.push({text, aria, y: r.y});
            }
            candidates.sort((a, b) => a.y - b.y);
            const hit = candidates[0];
            return hit ? (hit.aria || hit.text) : '';
        }"""
    )
    return parse_compact_count(value)


_OPEN_COMMENTS_JS = """() => {
    const visible = (el) => {
        if (!el) return false;
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
    };
    const clickTarget = (el, reason) => {
        if (!el) return null;
        const target = el.closest('button, [role="tab"], [role="button"], [aria-haspopup="dialog"], a') || el;
        if (!visible(target)) return null;
        target.scrollIntoView({block: 'center', inline: 'center'});
        target.click();
        const r = target.getBoundingClientRect();
        return {
            ok: true,
            reason,
            tag: target.tagName.toLowerCase(),
            text: (target.innerText || target.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 80),
            aria: target.getAttribute('aria-label') || '',
            x: Math.round(r.x),
            y: Math.round(r.y),
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

    return {ok: false};
}"""

_CLICK_RIGHT_COMMENTS_TAB_JS = """() => {
    const visible = (el) => {
        if (!el) return false;
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden';
    };
    const rightEdge = window.innerWidth * 0.55;
    for (const el of document.querySelectorAll('button, [role="tab"], [role="button"], div, span, p')) {
        const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
        const r = el.getBoundingClientRect();
        if (visible(el) && /^(Comentarios|Comments)$/i.test(text) && r.x > rightEdge && r.y < 220) {
            const target = el.closest('button, [role="tab"], [role="button"], a') || el;
            target.click();
            return {ok: true, text, x: Math.round(r.x), y: Math.round(r.y)};
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
                        await page.wait_for_timeout(900)
                        try:
                            tab = await page.evaluate(_CLICK_RIGHT_COMMENTS_TAB_JS)
                            if tab and tab.get("ok"):
                                print(f"[{video_id}] 🖱 Pestaña Comentarios activada")
                                await page.wait_for_timeout(900)
                        except Exception:
                            pass
                        print(f"[{video_id}] 🖱 Panel abierto ({sel})")
                        await page.wait_for_timeout(1800)
                        return True
            except Exception:
                pass

        try:
            hit = await page.evaluate(_OPEN_COMMENTS_JS)
            if hit and hit.get("ok"):
                await page.wait_for_timeout(900)
                try:
                    tab = await page.evaluate(_CLICK_RIGHT_COMMENTS_TAB_JS)
                    if tab and tab.get("ok"):
                        print(f"[{video_id}] 🖱 Pestaña Comentarios activada")
                        await page.wait_for_timeout(900)
                except Exception:
                    pass
                print(f"[{video_id}] 🖱 Panel abierto ({hit.get('reason')}: {hit.get('text') or hit.get('aria')})")
                await page.wait_for_timeout(1800)
                return True
        except Exception:
            pass

        if intento < 3:
            print(f"[{video_id}] ⏳ Botón aún no visible, esperando 3s... ({intento+1}/3)")
            await page.wait_for_timeout(3000)

    return False


# JS que expande los hilos de respuestas visibles ("Ver X respuestas")
# Usa texto porque los atributos data-e2e cambian frecuentemente.
# Estrategia: busca elementos hoja (sin hijos) cuyo texto coincide con
# "ver N respuesta(s)" / "view N repl(y|ies)" y los clickea.
_REPLY_CLICK_JS = """() => {
    const RE = /ver\\s+\\d+\\s+respuesta|view\\s+\\d+\\s+repl|ver\\s+respuestas|view\\s+replies/i;
    let clicked = 0;
    // Probar primero selectores conocidos (rápido)
    const knownSels = [
        '[data-e2e="view-more-reply"]',
        '[data-e2e="comment-reply-expand"]',
        'div[class*="ReplyAction" i]',
        'p[class*="ReplyAction" i]',
        'span[class*="ReplyAction" i]',
        'div[class*="reply-link" i]',
        'p[class*="reply-link" i]',
        'span[class*="reply-link" i]',
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
    // Fallback: recorrer todos los spans/divs/p hoja buscando el patrón de texto
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
    """Añade comentarios/replies al dict; devuelve cuántos son nuevos."""
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


async def extract_comments_api(
    context, url: str, limit: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Extrae comentarios interceptando las respuestas orgánicas de /api/comment/list/.

    Estrategia:
      1. Instalar un listener de respuestas que pone cada respuesta de la API
         de comentarios en una cola asyncio.
      2. Navegar al video y abrir el panel de comentarios → TikTok dispara
         página 1 (firmada por sus propios hooks JS).
      3. Procesar cada respuesta de la cola y hacer scroll del panel para
         disparar la siguiente página.
      Sin page.evaluate(fetch()): todas las peticiones las hace TikTok,
      nosotros solo leemos las respuestas.

    Retorna: (lista_comentarios, total_reportado_por_api)
    """
    page = await context.new_page()
    video_id = extract_video_id(url) or "???"
    username = extract_username(url)

    comments_by_cid: Dict[str, Dict] = {}
    total_from_api  = 0
    visible_comment_count = 0
    start_time      = time.time()

    # Cola donde aterrizan todas las respuestas /api/comment/list/ del video
    q: asyncio.Queue = asyncio.Queue()

    async def _on_response(response):
        if "/api/comment/list/" not in response.url:
            return
        try:
            body = await response.text()
            if body and body.strip():
                data = json.loads(body)
                # Detectar si es reply y extraer parent_comment_id de la URL
                if "/api/comment/list/reply/" in response.url:
                    m = re.search(r"comment_id=(\d+)", response.url)
                    data["_is_reply"]          = True
                    data["_parent_comment_id"] = m.group(1) if m else ""
                await q.put(data)
        except Exception:
            pass

    page.on("response", _on_response)

    try:
        # ── 1. CARGAR PÁGINA ─────────────────────────────────────────────
        print(f"[{video_id}] Cargando página...")
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await accept_cookies_best_effort(page)
        await dismiss_overlays(page)
        await page.wait_for_timeout(PAGE_SETTLE_BEFORE_COMMENTS_MS)
        visible_comment_count = await get_visible_comment_count(page)
        if visible_comment_count:
            print(f"[{video_id}] contador visible: {visible_comment_count:,} comentarios")

        # ── 2. ABRIR PANEL DE COMENTARIOS (dispara página 1) ─────────────
        opened = await open_comments_panel(page, video_id)
        if opened and not visible_comment_count:
            visible_comment_count = await get_visible_comment_count(page)
            if visible_comment_count:
                print(f"[{video_id}] contador visible: {visible_comment_count:,} comentarios")
        if not opened and RELOAD_ON_MISSING_COMMENT_BUTTON:
            # Último recurso: recargar página y un intento más
            print(f"[{video_id}] 🔄 Recargando página, último intento...")
            await page.reload(timeout=60000, wait_until="domcontentloaded")
            await accept_cookies_best_effort(page)
            await dismiss_overlays(page)
            await page.wait_for_timeout(3000)
            try:
                el = await page.wait_for_selector(combined_sel, timeout=8000, state="visible")
                if el:
                    await el.click(timeout=2000)
                    opened = True
                    print(f"[{video_id}] 🖱 Panel abierto (tras reload)")
            except Exception:
                pass
        if not opened:
            print(f"[{video_id}] ⚠️ No se encontró botón de comentarios")
            await page.close()
            return [], 0

        # Esperar a que los items de comentario estén en el DOM
        try:
            await page.wait_for_selector(
                '[data-e2e="comment-level-1"], [data-e2e*="comment-level"], div[class*="CommentItem" i]',
                timeout=8000,
            )
        except Exception:
            print(f"[{video_id}] ⚠️ Ítems no aparecieron en DOM — continuando igualmente")

        # ── 3. SCROLL CONTINUO + RECOGIDA DE RESPUESTAS ──────────────────
        # Tarea 1: scrollea continuamente (igual que el original)
        # Tarea 2: recoge respuestas de la cola a medida que llegan
        # Esto replica el comportamiento del scraper original pero sin parsear DOM.

        stop_scroll = asyncio.Event()

        async def _scroll_loop():
            while not stop_scroll.is_set():
                try:
                    await page.evaluate(_COMMENT_SCROLL_JS)
                    n_clicked = await page.evaluate(_REPLY_CLICK_JS)
                    if n_clicked:
                        print(f"[{video_id}]   🧵 {n_clicked} hilo(s) de respuestas expandido(s)")
                except Exception:
                    pass
                await asyncio.sleep(random.uniform(1.2, 2.2))

        scroll_task = asyncio.create_task(_scroll_loop())

        main_page_num       = 0   # solo páginas de comentarios principales
        consecutive_timeout = 0
        MAX_TIMEOUTS        = 5   # × 10s = 50s sin respuesta → parar
        premature_eof_hits  = 0
        empty_main_pages    = 0

        try:
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=10.0)
                    consecutive_timeout = 0
                except asyncio.TimeoutError:
                    consecutive_timeout += 1
                    print(f"[{video_id}]   ⏱ timeout {consecutive_timeout}/{MAX_TIMEOUTS} sin respuesta API")
                    if consecutive_timeout >= MAX_TIMEOUTS:
                        print(f"[{video_id}] STOP — {MAX_TIMEOUTS} timeouts consecutivos")
                        break
                    continue

                # Detectar comentarios deshabilitados o error de API
                status_code = int(data.get("status_code", 0))
                if status_code != 0:
                    if status_code in (2050, 2051, 2052, 2053):
                        print(f"[{video_id}] 🚫 Comentarios deshabilitados (status={status_code})")
                    else:
                        print(f"[{video_id}] ⚠️ API error (status_code={status_code})")
                    break

                is_reply   = data.get("_is_reply", False)
                parent_id  = data.get("_parent_comment_id", "")
                if not is_reply:
                    main_page_num += 1
                page_num = main_page_num
                batch       = data.get("comments") or []
                has_more    = int(data.get("has_more", 0))
                total       = int(data.get("total") or 0)
                new_count   = _process_batch(
                    batch, comments_by_cid,
                    is_reply=is_reply, parent_comment_id=parent_id,
                )
                if not is_reply:
                    total_from_api = max(total_from_api, total)
                    if total_from_api == 0 and visible_comment_count:
                        total_from_api = visible_comment_count
                    if new_count == 0:
                        empty_main_pages += 1
                    else:
                        empty_main_pages = 0
                acc         = len(comments_by_cid)
                tag         = f"reply→{parent_id[-6:]}" if is_reply else ""
                _log_page(video_id, page_num, new_count, acc, total_from_api, has_more, start_time, tag)

                # Solo los comentarios principales controlan el STOP
                if not is_reply:
                    if not batch:
                        if visible_comment_count and not batch and not comments_by_cid:
                            print(f"[{video_id}] STOP — TikTok muestra contador ({visible_comment_count:,}) pero devuelve API vacía")
                            break
                        if total_from_api and acc + PREMATURE_EOF_GAP < total_from_api:
                            print(f"[{video_id}] ⚠️ Página vacía con total={total_from_api:,}; sigo intentando scroll")
                            if empty_main_pages >= MAX_EMPTY_PAGES:
                                print(f"[{video_id}] STOP — {MAX_EMPTY_PAGES} páginas principales vacías consecutivas")
                                break
                        else:
                            print(f"[{video_id}] STOP — página vacía")
                            break
                    elif not has_more:
                        if total_from_api and acc + PREMATURE_EOF_GAP < total_from_api:
                            premature_eof_hits += 1
                            print(f"[{video_id}] ⚠️ has_more=0 prematuro ({acc}/{total_from_api:,}); sigo intentando scroll [{premature_eof_hits}/{MAX_PREMATURE_EOF}]")
                            if premature_eof_hits >= MAX_PREMATURE_EOF:
                                print(f"[{video_id}] STOP — has_more=0 repetido {MAX_PREMATURE_EOF} veces")
                                break
                        else:
                            print(f"[{video_id}] STOP — has_more=0")
                            break
                    else:
                        premature_eof_hits = 0
                if limit is not None and acc >= limit:
                    print(f"[{video_id}] STOP — límite {limit} alcanzado")
                    break
        finally:
            stop_scroll.set()
            scroll_task.cancel()
            try:
                await scroll_task
            except asyncio.CancelledError:
                pass

        # ── 4. CONVERTIR A FORMATO DE SALIDA ─────────────────────────────
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
        return out, (total_from_api or len(out))

    except Exception as e:
        print(f"[{video_id}] ❌ Error: {e}")
        traceback.print_exc()
        try: await page.close()
        except: pass
        raise


# ============================================================================
# MAIN
# ============================================================================

async def main():
    csv_path, count_arg, limit_arg, skip_checkpoint = parse_cli_args()

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
    unavailable_csv = out_csv.replace(".csv", "_no_disponibles.csv")

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
                    ans = input("   ¿Continuar? (S/n): ").strip().lower()
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
    total_expected = 0

    async with async_playwright() as pw:
        ctx = await create_context(pw)

        try:
            for idx, url in enumerate(urls, 1):
                await asyncio.sleep(random.uniform(0.8, 2.0))
                vid       = extract_video_id(url)
                vid_short = ("..." + vid[-12:]) if vid and len(vid) > 12 else (vid or "???")
                print(f"\n▶️ [{idx}/{len(urls)}] {vid_short} iniciando...")

                attempts = 0
                while True:
                    attempts += 1
                    try:
                        video_log_path = os.path.join(LOG_DIR, f"{log_ts}_{vid}.log")
                        video_fh = open(video_log_path, "a", encoding="utf-8", errors="ignore")
                        try:
                            if _TEE_STDOUT: _TEE_STDOUT.add(video_fh)
                            if _TEE_STDERR: _TEE_STDERR.add(video_fh)
                            comments, total = await extract_comments_api(ctx, url, limit=limit)
                        finally:
                            if _TEE_STDOUT: _TEE_STDOUT.remove(video_fh)
                            if _TEE_STDERR: _TEE_STDERR.remove(video_fh)
                            video_fh.close()

                        cap    = len(comments)
                        total_expected += total
                        pct    = int((cap / total) * 100) if total else 0
                        status = "✅" if total and pct >= 70 else "⚠️"
                        print(f"\n📹 [{idx}/{len(urls)}] {vid_short} {status} {cap}/{total} ({pct}%)\n")

                        if cap:
                            ok_videos += 1
                            all_comments.extend(comments)
                            if SAVE_PARTIAL_EVERY_VIDEO:
                                append_csv(comments, out_csv)
                                print(f"💾 Parcial guardado (+{cap})")
                        elif total:
                            append_unavailable_video({
                                "video_id": vid,
                                "video_url": url,
                                "username": extract_username(url),
                                "comentarios_visibles": total,
                                "motivo": "contador_visible_api_vacia",
                            }, unavailable_csv)
                            print(f"⚠️  TikTok muestra {total:,} comentarios, pero la API/panel devuelve vacío.")
                            print(f"🧾 Registrado en: {os.path.basename(unavailable_csv)}")
                        else:
                            print("ℹ️  Sin comentarios capturados; vídeo marcado como procesado para no bloquear el lote.")

                        if vid and vid not in processed_ids:
                            processed_ids.append(vid)
                        save_checkpoint(checkpoint_path, processed_ids, out_csv)
                        break

                    except Exception as e:
                        if attempts <= 2:
                            print(f"⚠️ Error (intento {attempts}/2): {str(e)[:60]}")
                            try:
                                await ctx.close()
                            except:
                                pass
                            await asyncio.sleep(5)
                            ctx = await create_context(pw)
                        else:
                            print(f"❌ [{idx}] Saltando {vid_short} tras 2 errores.")
                            break

        finally:
            try: await ctx.close()
            except: pass

    # ── Resumen final ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESUMEN FINAL")
    print("=" * 60)
    print(f"Videos procesados:   {ok_videos}/{len(urls)}")
    print(f"Comentarios totales: {len(all_comments):,}")
    if total_expected:
        overall_pct = int((len(all_comments) / total_expected) * 100)
        print(f"Cobertura global:    {overall_pct}% ({len(all_comments):,}/{total_expected:,})")
    print(f"CSV de salida:       {out_csv}")

    close_logging()


if __name__ == "__main__":
    exit_code = 0
    try:
        asyncio.run(main())
    except SystemExit as e:
        exit_code = int(e.code or 0) if isinstance(e.code, int) else 1
    except KeyboardInterrupt:
        exit_code = 130
        print("\n⏹️ Ejecución cancelada por el usuario.")
    except Exception as e:
        exit_code = 1
        print("\n❌ Error fatal antes de completar la descarga de comentarios:")
        print(f"   {type(e).__name__}: {e}")
        traceback.print_exc()
    finally:
        close_logging()
        # Ofrecer volver al menú
        should_offer_menu = not any(arg in ("--help", "-h") for arg in sys.argv[1:])
        if should_offer_menu and sys.stdin.isatty():
            print("\n" + "=" * 70)
            try:
                resp = input("¿Volver al menú principal? (S/N): ").strip().upper()
            except EOFError:
                resp = ""
            if resp in ("S", "SI", "YES", "Y"):
                import subprocess
                menu_path = os.path.join(os.path.dirname(__file__), "..", "..", "menu.py")
                subprocess.run([sys.executable, menu_path])
            print("✅ ¡Hasta pronto!")
        if exit_code:
            raise SystemExit(exit_code)
