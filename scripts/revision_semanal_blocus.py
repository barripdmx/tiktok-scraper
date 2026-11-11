"""Revisión semanal de cuentas Blocus: censo por user_id, búsqueda de cuentas nuevas y balance de seguidores.

Cada pasada: busca usuarios con los términos de TERMINOS, vuelve a abrir el perfil de cada cuenta del censo,
actualiza data/blocus/datos/revision_semanal/censo.json y guarda la captura con fecha en capturas/AAAAMMDD_HHMM/
(JSON crudo de la búsqueda + informe.md). «Nueva» = ausente del censo de la pasada anterior; «desaparecida» =
no disponible en dos pasadas seguidas; «renombrada» = mismo user_id con otro nombre de usuario.
Primera vez: siembra el censo desde data/blocus/datos/revision_cuentas_20261104/.
Uso: python -m scripts.revision_semanal_blocus [--sin-perfiles] [--sembrar]
"""

import argparse
import asyncio
import json
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/utils"))
DIR = ROOT / "data/blocus/datos/revision_semanal"
CENSO = DIR / "censo.json"
SEMILLA = ROOT / "data/blocus/datos/revision_cuentas_20261104"
PROFILE_DIR = str(ROOT / "drivers/tiktok_profile")
TERMINOS = ["blocus", "blocus españa", "blocus madrid", "blocus barcelona", "blocus catalunya", "blocus france",
            "blocus belgique", "blocus manifestation", "team blocus", "blocus 31 octubre", "bl0cus", "blokus"]
NOMBRE_BLOCUS = re.compile(r"bl[o0u]cu?s|blokus|bloquu", re.I)
COORDINACION = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me|discord\.gg|discord\.com/invite|signal\.group|signal\.me|chat\.whatsapp\.com|wa\.me|snapchat\.com/t)/?[\w\-./#+=?&%~]*", re.I)
MIN_BASE = 50# por debajo, el porcentaje de crecimiento no es comparable
FALLOS_BAJA = 2


def alta_estimada(uid):
    """Fecha de alta de la cuenta: los 32 bits altos del user_id son un timestamp Unix."""
    return datetime.fromtimestamp(int(uid) >> 32, timezone.utc).strftime("%Y-%m-%d")


def pct(antes, ahora):
    return (ahora - antes) / antes * 100


def actualizar(censo, obs, ahora, informe):
    """Aplica observaciones [{uid, usuario, apodo, bio, seguidores, seguidos, videos, estado}] al censo y anota cambios."""
    for o in obs:
        uid = str(o["uid"])
        c = censo.get(uid)
        if c is None:
            c = censo[uid] = {"usuario": o["usuario"], "nombres": [], "primera": ahora, "alta": alta_estimada(uid),
                              "fallos": 0, "baja": None, "etiqueta": "", "historial": []}
            informe["nuevas"].append(o["usuario"])
            informe["altas"][o["usuario"]] = c["alta"]
            if reciente(c["alta"], ahora):
                informe["nuevas_recientes"].append(o["usuario"])
        elif c["usuario"] != o["usuario"]:
            informe["renombradas"].append((c["usuario"], o["usuario"]))
            c["nombres"].append(c["usuario"])
            c["usuario"] = o["usuario"]
        # solo se compara con la medición inmediatamente anterior, y solo si fue válida
        ultimo = c["historial"][-1] if c["historial"] and c["historial"][-1]["estado"] == "ok" else None
        c["historial"].append({"fecha": ahora, **{k: o.get(k) for k in ("usuario", "apodo", "bio", "enlaces", "seguidores", "seguidos", "videos", "estado")}})
        if o["estado"] == "ok":
            if c["baja"]:
                informe["reaparecidas"].append(o["usuario"])
                c["baja"] = None
            c["fallos"] = 0
            if o.get("enlaces") and o["enlaces"] != (ultimo or {}).get("enlaces"):
                informe["enlaces"].append((o["usuario"], o["enlaces"]))
            if ultimo and ultimo["seguidores"] and ultimo["seguidores"] >= MIN_BASE and o.get("seguidores") is not None:
                informe["crecimiento"].append((o["usuario"], ultimo["seguidores"], o["seguidores"]))
        else:
            c["fallos"] += 1
            if c["fallos"] >= FALLOS_BAJA and not c["baja"]:
                c["baja"] = ahora
                informe["bajas"].append(o["usuario"])
    return informe


def informe_vacio():
    return {"nuevas": [], "nuevas_recientes": [], "altas": {}, "renombradas": [], "reaparecidas": [], "bajas": [], "crecimiento": [], "enlaces": []}


def reciente(alta, ahora, dias=30):
    """¿La cuenta se creó en los últimos `dias` días respecto a la fecha de la pasada?"""
    try:
        return 0 <= (datetime.fromisoformat(ahora[:10]) - datetime.fromisoformat(alta)).days <= dias
    except ValueError:
        return False


def enlaces(bio, enlace_bio=""):
    """Canales de coordinación (Signal, Telegram, Discord, WhatsApp, Snapchat) en la bio o en el enlace del perfil."""
    return sorted(set(COORDINACION.findall(f"{bio or ''} {enlace_bio or ''}")))


def miles(n):
    return f"{n:,}".replace(",", ".")


def coma(p):
    """Porcentaje con signo y coma decimal: +6,8"""
    p = round(p, 1) + 0.0  # evita «-0,0»
    return ("0,0" if p == 0 else f"{p:+.1f}").replace(".", ",")


def texto_informe(informe, ahora, n_censo, etiquetadas=()):
    suben = [x for x in informe["crecimiento"] if x[2] > x[1]]
    bajan = [x for x in informe["crecimiento"] if x[2] < x[1]]
    t0 = sum(x[1] for x in informe["crecimiento"])
    t1 = sum(x[2] for x in informe["crecimiento"])
    lineas = [f"# Revisión Blocus — {ahora}", "", f"Censo: {miles(n_censo)} cuentas. Análisis: @barripdmx.", ""]
    if t0:
        lineas.append(f"Conjunto (cuentas con ≥{MIN_BASE} seguidores en la pasada anterior): {miles(t0)} → {miles(t1)} "
                      f"({coma(pct(t0, t1))} %); suben {len(suben)}, bajan {len(bajan)}.")
        resto = [x for x in informe["crecimiento"] if x[0] not in etiquetadas]
        r0, r1 = sum(x[1] for x in resto), sum(x[2] for x in resto)
        if r0 and len(resto) < len(informe["crecimiento"]):
            lineas.append(f"Sin las {len(informe['crecimiento']) - len(resto)} cuentas etiquetadas (contenido o monetización, no movimiento): "
                          f"{miles(r0)} → {miles(r1)} ({coma(pct(r0, r1))} %).")
    lineas += ["", f"## Nuevas en el censo: {len(informe['nuevas'])} (creadas en los últimos 30 días: {len(informe['nuevas_recientes'])})"]
    lineas += [f"- @{u} (alta estimada {informe['altas'][u]})" + (" ← reciente" if u in informe["nuevas_recientes"] else "") for u in informe["nuevas"]]
    for titulo, clave in (("Desaparecidas (2 fallos sin éxito entre medias)", "bajas"), ("Reaparecidas", "reaparecidas")):
        lineas += ["", f"## {titulo}: {len(informe[clave])}"] + [f"- @{u}" for u in informe[clave]]
    lineas += ["", f"## Enlaces de coordinación nuevos o cambiados: {len(informe['enlaces'])}"] + [f"- @{u}: {' '.join(e)}" for u, e in informe["enlaces"]]
    lineas += ["", f"## Renombradas: {len(informe['renombradas'])}"] + [f"- @{a} → @{b}" for a, b in informe["renombradas"]]
    lineas += ["", "## Crecimiento por cuenta"]
    for u, a, b in sorted(informe["crecimiento"], key=lambda x: -pct(x[1], x[2])):
        lineas.append(f"- @{u}: {miles(a)} → {miles(b)} ({coma(pct(a, b))} %)")
    return "\n".join(lineas) + "\n"


def sembrar():
    """Censo inicial desde la revisión del 04/11/2026 (base del 25/10, perfiles del 04/11 y búsqueda)."""
    base = json.loads((SEMILLA / "base_perfiles.json").read_text(encoding="utf-8"))
    actual = json.loads((SEMILLA / "actual_perfiles.json").read_text(encoding="utf-8"))
    busq = json.loads((SEMILLA / "busqueda.json").read_text(encoding="utf-8"))
    censo, informe = {}, informe_vacio()
    sin_uid = [u for u, b in base.items() if not b.get("user_id") and not actual.get(u, {}).get("uid")]
    if sin_uid:
        print(f"Sin user_id, fuera del censo (se añadirán si la búsqueda las encuentra): {', '.join('@' + u for u in sin_uid)}")
    for u, b in base.items():
        if b.get("user_id"):
            actualizar(censo, [{"uid": b["user_id"], "usuario": u, "apodo": b.get("nickname"), "bio": b.get("bio"), "seguidores": b.get("followers"),
                                "seguidos": b.get("following"), "videos": b.get("video_count"), "estado": "ok"}], b["observed_at"][:10], informe)
    for u, a in actual.items():
        uid = str(base.get(u, {}).get("user_id") or a.get("uid") or "")
        if uid:
            ok = a.get("status") == 0
            actualizar(censo, [{"uid": uid, "usuario": u, "apodo": a.get("nick"), "seguidores": a.get("seg"), "seguidos": a.get("sigo"),
                                "videos": a.get("vid"), "estado": "ok" if ok else f"no_disponible:{a.get('status')}"}], "2026-11-04", informe)
    for u, x in busq.items():
        if x.get("uid") and NOMBRE_BLOCUS.search(f"{u} {x.get('nick') or ''}") and str(x["uid"]) not in censo:
            actualizar(censo, [{"uid": x["uid"], "usuario": u, "apodo": x["nick"], "bio": x["bio"], "seguidores": x["seg"], "estado": "ok"}], "2026-11-04", informe)
    return censo


async def buscar(pw, context):
    """Búsqueda de usuarios por término; devuelve (observaciones filtradas por nombre, JSON crudo por término)."""
    crudo, vistos = {}, {}
    for q in TERMINOS:
        resultados = []
        page = await context.new_page()

        async def guardar(r):
            if "/api/search/user" in r.url:
                try:
                    resultados.extend((await r.json()).get("user_list", []))
                except Exception:
                    pass
        page.on("response", guardar)
        try:
            await page.goto("https://www.tiktok.com/search/user?q=" + urllib.parse.quote(q), timeout=60000)
            await asyncio.sleep(3)
            for _ in range(6):
                await page.mouse.wheel(0, 4000)
                await asyncio.sleep(1.5)
        except Exception as e:  # una página caída no para la pasada
            print(f"  búsqueda «{q}»: error {str(e)[:60]}")
        await page.close()
        crudo[q] = resultados
        for rango, e in enumerate(resultados, 1):
            u = e.get("user_info", {})
            if u.get("uid") and NOMBRE_BLOCUS.search(f"{u.get('unique_id')} {u.get('nickname')}"):
                vistos.setdefault(str(u["uid"]), {"uid": u["uid"], "usuario": u["unique_id"], "apodo": u.get("nickname"), "bio": (u.get("signature") or "")[:200],
                                                  "enlaces": enlaces(u.get("signature")), "seguidores": u.get("follower_count"), "estado": "ok"})
        print(f"  «{q}»: {len(resultados)} resultados")
    return list(vistos.values()), crudo


async def perfiles(context, censo, saltar):
    """Abre el perfil de cada cuenta del censo no vista en la búsqueda."""
    obs = []
    page = await context.new_page()
    for uid, c in censo.items():
        if uid in saltar:
            continue
        try:
            await page.goto(f"https://www.tiktok.com/@{c['usuario']}", timeout=60000)
            await asyncio.sleep(2)
            raw = await page.evaluate("() => document.getElementById('__UNIVERSAL_DATA_FOR_REHYDRATION__')?.textContent")
            d = (json.loads(raw).get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail") or {}) if raw else {}
        except Exception as e:
            print(f"  @{c['usuario']}: error {str(e)[:60]}")
            continue  # un fallo de red no cuenta como baja
        if d.get("statusCode") is None:  # captcha, página incompleta o cambio de HTML: sin dato, no es una baja
            print(f"  @{c['usuario']}: sin respuesta de perfil, se omite")
            continue
        ui = d.get("userInfo") or {}
        us, st = ui.get("user", {}), ui.get("stats", {})
        if d.get("statusCode") == 0 and str(us.get("id")) == uid:
            obs.append({"uid": uid, "usuario": us.get("uniqueId") or c["usuario"], "apodo": us.get("nickname"), "bio": (us.get("signature") or "")[:200],
                        "enlaces": enlaces(us.get("signature"), (us.get("bioLink") or {}).get("link")),
                        "seguidores": st.get("followerCount"), "seguidos": st.get("followingCount"), "videos": st.get("videoCount"), "estado": "ok"})
        else:  # estado distinto de 0, o el nombre lo usa ahora otro user_id
            estado = f"no_disponible:{d.get('statusCode')}" if d.get("statusCode") != 0 else "nombre_reutilizado"
            obs.append({"uid": uid, "usuario": c["usuario"], "estado": estado})
        print(f"  @{c['usuario']}: {obs[-1]['estado']}", flush=True)
    return obs


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sin-perfiles", action="store_true", help="solo búsqueda, sin reabrir los perfiles del censo")
    parser.add_argument("--sembrar", action="store_true", help="rehace el censo desde la revisión del 04/11/2026 (pisa el actual)")
    args = parser.parse_args()
    from playwright.async_api import async_playwright
    from tiktok_utils import ensure_context, resolve_cookies_path
    DIR.mkdir(parents=True, exist_ok=True)
    if args.sembrar or not CENSO.exists():
        censo = sembrar()
        print(f"Censo sembrado: {len(censo)} cuentas")
    else:
        censo = json.loads(CENSO.read_text(encoding="utf-8"))
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    informe = informe_vacio()
    async with async_playwright() as pw:
        context = await ensure_context(pw, PROFILE_DIR, resolve_cookies_path(str(ROOT)), False, True)
        obs_busqueda, crudo = await buscar(pw, context)
        actualizar(censo, obs_busqueda, ahora, informe)
        if not args.sin_perfiles:
            actualizar(censo, await perfiles(context, censo, {str(o["uid"]) for o in obs_busqueda}), ahora, informe)
        await context.close()
    carpeta = DIR / "capturas" / datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    carpeta.mkdir(parents=True)
    (carpeta / "busqueda_cruda.json").write_text(json.dumps(crudo, ensure_ascii=False), encoding="utf-8")
    (carpeta / "informe.md").write_text(texto_informe(informe, ahora, len(censo), {c["usuario"] for c in censo.values() if c.get("etiqueta")}), encoding="utf-8")
    CENSO.write_text(json.dumps(censo, ensure_ascii=False, indent=1), encoding="utf-8")
    print((carpeta / "informe.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    asyncio.run(main())
