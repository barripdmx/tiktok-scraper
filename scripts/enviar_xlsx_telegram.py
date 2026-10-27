"""Inspecciona destinos Telegram configurados y envía el XLSX a uno elegido.

Los tokens y los ID de chat se leen del entorno y nunca se imprimen.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


FILE = Path(__file__).resolve().parents[1] / "outputs" / "gemini_argon_blocus_20261027" / "blocus_datos_gemini_argon.xlsx"
BOTS = ("TELEGRAM_BOT_TOKEN", "RADAR_TELEGRAM_BOT_TOKEN")
CHATS = ("TELEGRAM_PERSONAL_CHAT_ID", "TELEGRAM_CHAT_ID")


def api(token: str, method: str, data: bytes | None = None, content_type: str | None = None):
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}", data=data)
    if content_type:
        request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            result = json.load(exc)
            return {"ok": False, "description": result.get("description", f"HTTP {exc.code}")}
        except (ValueError, OSError):
            return {"ok": False, "description": f"HTTP {exc.code}"}


def inspect():
    for token_key in BOTS:
        token = os.getenv(token_key)
        if not token:
            continue
        me = api(token, "getMe")
        print(f"{token_key}: @{me.get('result', {}).get('username', '?')}")
        for chat_key in CHATS:
            chat = os.getenv(chat_key)
            if not chat:
                continue
            query = urllib.parse.urlencode({"chat_id": chat})
            result = api(token, f"getChat?{query}")
            if result.get("ok"):
                info = result["result"]
                label = info.get("title") or info.get("username") or info.get("first_name") or "chat"
                print(f"  {chat_key}: disponible, {info.get('type')}, {label}")
            else:
                print(f"  {chat_key}: {result.get('description', 'no disponible')}")


def send(token_key: str, chat_key: str):
    token, chat = os.environ[token_key], os.environ[chat_key]
    if not FILE.is_file():
        raise FileNotFoundError(FILE)
    boundary = "codex" + secrets.token_hex(12)
    chunks = []
    for name, value in (
        ("chat_id", chat),
        ("caption", "Blocus · datos para Gemini Argon (XLSX, 11 pestañas)"),
    ):
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    chunks.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{FILE.name}\"\r\n"
        "Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n".encode()
    )
    chunks.append(FILE.read_bytes())
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    result = api(token, "sendDocument", b"".join(chunks), f"multipart/form-data; boundary={boundary}")
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Error desconocido de Telegram"))
    message = result["result"]
    print(f"Enviado: message_id={message['message_id']}, archivo={FILE.name}, tamaño={FILE.stat().st_size} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--bot", choices=BOTS)
    parser.add_argument("--chat", choices=CHATS)
    args = parser.parse_args()
    if args.inspect:
        inspect()
    elif args.bot and args.chat:
        send(args.bot, args.chat)
    else:
        parser.error("Usa --inspect o --bot y --chat")
