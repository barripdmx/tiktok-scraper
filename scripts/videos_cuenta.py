"""Vídeos recientes de una o varias cuentas de TikTok, con el contexto y las cookies del scraper del proyecto.

Uso: python -m scripts.videos_cuenta usuario1 usuario2 ...   (stdin desde un fichero vacío)
Guarda data/blocus/datos/revision_semanal/videos/{fecha}.json y resume en pantalla.
Una cuenta con 0 vídeos puede ser captura vacía (bloqueo de TikTok), no prueba de que no tenga: no concluir nada.
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from src.utils.tiktok_utils import accept_cookies_banner, ensure_context, handle_verification, resolve_cookies_path

ROOT = Path(__file__).resolve().parent.parent
SALIDA = ROOT / "data/blocus/datos/revision_semanal/videos"
PROFILE_DIR = str(ROOT / "drivers/tiktok_profile")


def resumen(item):
    s = item["stats"]
    return {"id": item["id"], "fecha": datetime.fromtimestamp(int(item["createTime"])).strftime("%Y-%m-%d"),
            "desc": item.get("desc", "")[:200], "vistas": s["playCount"], "likes": s["diggCount"],
            "coment": s["commentCount"], "comp": s["shareCount"]}


async def capturar(ctx, usuario):
    items = {}
    page = await ctx.new_page()

    async def on_resp(r):
        if "/api/post/item_list" in r.url:
            try:
                for it in (await r.json()).get("itemList", []):
                    items[it["id"]] = it
            except Exception:
                pass

    page.on("response", on_resp)
    await page.goto(f"https://www.tiktok.com/@{usuario}", timeout=60000)
    await accept_cookies_banner(page)
    await handle_verification(page, 30)
    await asyncio.sleep(4)
    for _ in range(4):
        await page.mouse.wheel(0, 3000)
        await asyncio.sleep(2)
    await page.close()
    return sorted((resumen(i) for i in items.values()), key=lambda v: v["fecha"])


async def main(usuarios):
    res = {}
    async with async_playwright() as pw:
        ctx = await ensure_context(pw, PROFILE_DIR, resolve_cookies_path(str(ROOT)), False, False)
        for u in usuarios:
            res[u] = await capturar(ctx, u)
            print(f"@{u}: {len(res[u])} vídeos")
        await ctx.close()
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / f"{datetime.now():%Y%m%d_%H%M}.json"
    destino.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Guardado en {destino}")


if __name__ == "__main__":
    asyncio.run(main([u.lstrip("@") for u in sys.argv[1:]]))
