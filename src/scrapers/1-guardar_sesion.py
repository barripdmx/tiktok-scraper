"""Guarda una sesión de TikTok desde un inicio de sesión manual y local."""
import argparse
import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
SESSION_NAMES = {
    "principal": ("tiktok.json", "tiktok_cookies.json"),
    "secundaria": ("tiktok_secundaria.json", "tiktok_cookies_secundaria.json"),
}


def output_paths(account):
    state_name, cookies_name = SESSION_NAMES[account]
    return ROOT / "drivers/playwright_auth" / state_name, ROOT / "secrets" / cookies_name


def authenticated_cookies(cookies):
    return any(
        isinstance(cookie, dict)
        and str(cookie.get("domain", "")).lstrip(".").lower() in ("tiktok.com", "www.tiktok.com")
        and cookie.get("name") in ("sessionid", "sessionid_ss", "sid_tt")
        and bool(cookie.get("value"))
        for cookie in cookies
    )


def atomic_private_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


async def capture(account):
    state_path, cookies_path = output_paths(account)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=120000)
            print(f"Inicia sesión con la cuenta {account} en la ventana de TikTok.", flush=True)
            print("Cuando veas tu perfil o feed, vuelve a esta consola y pulsa Enter.", flush=True)
            await asyncio.to_thread(input)
            state = await context.storage_state()
            if not authenticated_cookies(state.get("cookies", [])):
                print("No se detectó una sesión iniciada. No se ha guardado ningún archivo.", flush=True)
                return 2
            atomic_private_json(state_path, state)
            atomic_private_json(cookies_path, state["cookies"])
            print(f"Sesión {account} guardada en {cookies_path}.", flush=True)
            if account == "principal":
                legacy_path = ROOT / "data/tiktok_cookies.json"
                if legacy_path.exists():
                    legacy_path.unlink()
            return 0
        finally:
            await browser.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cuenta", choices=tuple(SESSION_NAMES), default="principal")
    args = parser.parse_args(argv)
    try:
        return asyncio.run(capture(args.cuenta))
    except KeyboardInterrupt:
        print("Inicio de sesión cancelado; las sesiones anteriores se conservan.", flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
