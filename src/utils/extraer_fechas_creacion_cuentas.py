# -*- coding: utf-8 -*-
"""
Extrae la fecha de creación de un pool de cuentas de TikTok.

Fuente principal:
    webapp.user-detail.userInfo.user.createTime

Fallback:
    fecha inferida desde user.id >> 32 cuando createTime no venga y el ID sea válido.
"""

import csv
import json
import os
import re
from datetime import datetime

import requests


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCRIPT_TAG_RE = re.compile(
    r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>',
    re.S,
)


def ensure_data_dir() -> str:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        return DATA_DIR
    except OSError:
        return os.getcwd()


def normalize_username(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""

    value = value.rstrip("/").strip()
    if "tiktok.com/@" in value.lower():
        m = re.search(r'tiktok\.com/@([^/?#]+)', value, re.I)
        if m:
            value = m.group(1)

    return value.lstrip("@").strip()


def read_usernames_from_file(path: str):
    ext = os.path.splitext(path)[1].lower()
    usernames = []

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        if ext == ".csv":
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                username = normalize_username(row[0])
                if username:
                    usernames.append(username)
        else:
            for line in f:
                username = normalize_username(line)
                if username:
                    usernames.append(username)

    return list(dict.fromkeys(usernames))


def parse_user_create_dt(user_obj: dict):
    raw = user_obj.get("createTime")
    if raw not in (None, "", 0, "0"):
        try:
            return datetime.fromtimestamp(int(raw)), "createTime"
        except Exception:
            pass

    user_id = user_obj.get("id")
    try:
        uid = int(str(user_id).strip())
        ts = uid >> 32
        if ts > 0:
            dt = datetime.fromtimestamp(ts)
            if 2015 <= dt.year <= datetime.now().year + 1:
                return dt, "id>>32"
    except Exception:
        pass

    return None, ""


def extract_user_payload(html: str):
    match = SCRIPT_TAG_RE.search(html or "")
    if not match:
        raise ValueError("No se encontró el JSON de hidratación del perfil")

    data = json.loads(match.group(1))
    scope = data.get("__DEFAULT_SCOPE__", {})
    return scope.get("webapp.user-detail", {}).get("userInfo", {})


def fetch_account_info(session: requests.Session, username: str):
    url = f"https://www.tiktok.com/@{username}"
    resp = session.get(
        url,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
    )
    resp.raise_for_status()

    user_info = extract_user_payload(resp.text)
    user = user_info.get("user", {})
    stats = user_info.get("stats", {})
    create_dt, create_source = parse_user_create_dt(user)

    return {
        "username_consulta": username,
        "username_real": user.get("uniqueId", username),
        "nickname": user.get("nickname", ""),
        "verified": "Sí" if user.get("verified") else "No",
        "user_id": str(user.get("id", "") or ""),
        "sec_uid": user.get("secUid", ""),
        "fecha_creacion_cuenta": (
            create_dt.strftime("%d-%m-%Y %H:%M:%S") if create_dt else ""
        ),
        "fuente_fecha_creacion": create_source,
        "followers": int(stats.get("followerCount", 0) or 0),
        "following": int(stats.get("followingCount", 0) or 0),
        "likes": int(stats.get("heart", 0) or 0),
        "video_count": int(stats.get("videoCount", 0) or 0),
        "bio": user.get("signature", ""),
        "profile_url": url,
        "error": "",
    }


def save_results(rows):
    out_dir = ensure_data_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(out_dir, f"cuentas_fechas_creacion_{ts}.csv")
    json_path = os.path.join(out_dir, f"cuentas_fechas_creacion_{ts}.json")

    fields = [
        "username_consulta",
        "username_real",
        "nickname",
        "verified",
        "user_id",
        "sec_uid",
        "fecha_creacion_cuenta",
        "fuente_fecha_creacion",
        "followers",
        "following",
        "likes",
        "video_count",
        "bio",
        "profile_url",
        "error",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "scraped_at": datetime.now().isoformat(),
                "accounts_count": len(rows),
                "accounts": rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return csv_path, json_path


def load_usernames():
    raw = input(
        "Ruta de archivo (.csv/.txt) o cuentas separadas por comas: "
    ).strip()
    if not raw:
        return []

    if os.path.isfile(raw):
        return read_usernames_from_file(raw)

    usernames = [normalize_username(part) for part in raw.split(",")]
    return [u for u in dict.fromkeys(usernames) if u]


def main():
    print("=" * 72)
    print("Extractor de fechas de creación de cuentas TikTok")
    print("=" * 72)

    usernames = load_usernames()
    if not usernames:
        print("❌ No se proporcionaron cuentas válidas")
        return

    print(f"\n🔎 Cuentas a consultar: {len(usernames)}")
    rows = []

    with requests.Session() as session:
        for i, username in enumerate(usernames, 1):
            print(f"\n[{i}/{len(usernames)}] @{username}")
            try:
                row = fetch_account_info(session, username)
                rows.append(row)

                fecha = row["fecha_creacion_cuenta"] or "N/D"
                fuente = row["fuente_fecha_creacion"] or "sin fuente"
                print(f"   ✅ @{row['username_real']} | creada: {fecha} | fuente: {fuente}")
            except Exception as e:
                error = str(e).strip() or type(e).__name__
                rows.append({
                    "username_consulta": username,
                    "username_real": "",
                    "nickname": "",
                    "verified": "",
                    "user_id": "",
                    "sec_uid": "",
                    "fecha_creacion_cuenta": "",
                    "fuente_fecha_creacion": "",
                    "followers": 0,
                    "following": 0,
                    "likes": 0,
                    "video_count": 0,
                    "bio": "",
                    "profile_url": f"https://www.tiktok.com/@{username}",
                    "error": error,
                })
                print(f"   ⚠️ Error: {error[:120]}")

    csv_path, json_path = save_results(rows)

    ok_count = sum(1 for row in rows if not row.get("error"))
    print(f"\n✅ Cuentas resueltas: {ok_count}/{len(rows)}")
    print(f"📄 CSV:  {csv_path}")
    print(f"📁 JSON: {json_path}")


if __name__ == "__main__":
    main()
