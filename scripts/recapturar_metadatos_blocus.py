"""Recaptura los metadatos ampliados (país, moderación, IA, lugar, recomendador…) de las publicaciones Blocus.

Abre cada publicación de publicaciones.csv con el perfil de Chromium con sesión (las fotos no se sirven
sin sesión), lee el JSON de rehidratación y:
- guarda el itemStruct completo en metadatos_crudos/{id}.json (reanudable: los ya guardados se saltan);
- añade a publicaciones.csv las columnas act_* (foto del estado actual, distinta de la captura del 27/10).
Uso: python -m scripts.recapturar_metadatos_blocus [--limite N]
"""

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/utils"))
from tiktok_utils import COLUMNAS_AMPLIADAS, accept_cookies_banner, ensure_context, metadatos_ampliados, resolve_cookies_path  # noqa: E402

OUT = ROOT / "data/blocus/datos/comentarios_blocus_20261026"
CSV_PATH = OUT / "publicaciones.csv"
CRUDOS = OUT / "metadatos_crudos"
PROFILE_DIR = str(ROOT / "drivers/tiktok_profile")
COLUMNAS = ["act_estado", "act_capturado_utc"] + ["act_" + c for c in COLUMNAS_AMPLIADAS]


async def leer(page, url):
    respuestas = []  # las fotos no traen el item en el HTML: la página lo pide a /api/item/detail/

    async def guardar(r):
        if "/api/item/detail" in r.url:
            try:
                respuestas.append(await r.json())
            except Exception:
                pass
    page.on("response", guardar)
    try:
        await page.goto(url, timeout=60000)
        await accept_cookies_banner(page)
        await asyncio.sleep(2.5)
        raw = await page.evaluate("() => document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent")
    finally:
        page.remove_listener("response", guardar)
    scope = json.loads(raw).get("__DEFAULT_SCOPE__", {}) if raw else {}
    detalle = scope.get("webapp.video-detail") or {}
    if not detalle.get("itemInfo") and respuestas:
        detalle = respuestas[-1]
    return detalle.get("statusCode"), detalle.get("itemInfo", {}).get("itemStruct") or {}


def fila_actual(registro):
    if not registro.get("item"):
        return {"act_estado": f"no_disponible:{registro.get('status')}", "act_capturado_utc": registro["capturado"]}
    return {"act_estado": "ok", "act_capturado_utc": registro["capturado"],
            **{"act_" + k: v for k, v in metadatos_ampliados(registro["item"]).items()}}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite", type=int, default=0)
    args = parser.parse_args()
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f)
        base = [c for c in lector.fieldnames if c not in COLUMNAS]
        filas = list(lector)
    CRUDOS.mkdir(exist_ok=True)
    pendientes = [f for f in filas if not (CRUDOS / f"{f['id']}.json").exists()][:args.limite or None]
    print(f"{len(filas)} publicaciones, {len(pendientes)} por capturar")
    async with async_playwright() as pw:
        context = await ensure_context(pw, PROFILE_DIR, resolve_cookies_path(str(ROOT)), False, True)
        page = await context.new_page()
        for i, fila in enumerate(pendientes, 1):
            try:
                status, item = await leer(page, fila["url"])
            except Exception as e:  # una página que falla no para la captura; se reintenta en la siguiente pasada
                print(f"  {fila['id']}: error {str(e)[:80]}")
                continue
            registro = {"id": fila["id"], "status": status, "capturado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "item": item}
            (CRUDOS / f"{fila['id']}.json").write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
            print(f"  {i}/{len(pendientes)} @{fila['cuenta']} {fila['tipo']} {fila['id']}: "
                  f"{'ok ' + (item.get('locationCreated') or '—') if item else f'no disponible ({status})'}")
            await asyncio.sleep(1)
        await context.close()
    for fila in filas:
        ruta = CRUDOS / f"{fila['id']}.json"
        fila.update({c: "" for c in COLUMNAS})
        if ruta.exists():
            fila.update(fila_actual(json.loads(ruta.read_text(encoding="utf-8"))))
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=base + COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
    estados = {}
    for fila in filas:
        estados[fila["act_estado"] or "pendiente"] = estados.get(fila["act_estado"] or "pendiente", 0) + 1
    print(json.dumps(estados, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
