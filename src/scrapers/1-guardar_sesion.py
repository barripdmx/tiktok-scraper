# 1-guardar_sesion.py
import asyncio, os, json
from playwright.async_api import async_playwright

async def main():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    auth_dir = os.path.join(BASE_DIR, "drivers", "playwright_auth")
    os.makedirs(auth_dir, exist_ok=True)
    state_path = os.path.join(auth_dir, "tiktok.json")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled"
        ])
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=120000)
        print("Inicia sesión manualmente en la ventana. Pulsa Enter aquí cuando veas tu feed/perfil...")
        input()
        state = await context.storage_state(path=state_path)
        print("✅ Storage state guardado en:", state_path)

        # Exportar cookies en el formato que esperan los scrapers.
        # SEC-01: la sesión se guarda en secrets/ (fuera de data/), de modo que
        # compartir/comprimir data/ con los datasets ya no expone la sesión viva.
        secrets_dir = os.path.join(BASE_DIR, "secrets")
        os.makedirs(secrets_dir, exist_ok=True)
        cookies_path = os.path.join(secrets_dir, "tiktok_cookies.json")
        with open(cookies_path, "w", encoding="utf-8") as f:
            json.dump(state["cookies"], f, ensure_ascii=False, indent=2)
        print("🍪 Cookies exportadas en:", cookies_path)

        # Limpieza: si quedaba una sesión legacy en data/, eliminarla para no
        # dejar copias de la sesión dentro de la carpeta que se comparte.
        legacy_path = os.path.join(BASE_DIR, "data", "tiktok_cookies.json")
        if os.path.exists(legacy_path):
            try:
                os.remove(legacy_path)
                print("🧹 Sesión legacy eliminada de data/:", legacy_path)
            except OSError:
                pass

        await browser.close()

asyncio.run(main())
