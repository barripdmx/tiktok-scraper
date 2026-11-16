"""Validación compartida de cuentas y archivos de entrada, sin red."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from src.utils.tiktok_relaciones import normalize_username

HEADERS = {"username", "user", "cuenta", "uniqueid", "unique_id", "profile_url",
           "url", "perfil", "tiktok", "account"}
MAX_BYTES = 5 * 1024 * 1024
MAX_ACCOUNTS = 10000


def account_name(value):
    value = str(value or "").strip()
    if value.lower().startswith(("https://", "http://", "www.tiktok.com/", "tiktok.com/")):
        parsed = urlsplit(value if "://" in value else "https://" + value)
        if parsed.hostname not in ("www.tiktok.com", "tiktok.com") or parsed.username or parsed.password or parsed.port:
            raise ValueError("Usa una URL de perfil de tiktok.com.")
        path = parsed.path.rstrip("/")
        if not path.startswith("/@") or "/" in path[2:]:
            raise ValueError("Usa la URL del perfil, no la de un vídeo.")
        value = path[2:]
    return normalize_username(value)


@dataclass(frozen=True)
class AccountInput:
    usernames: tuple[str, ...]
    duplicates: int


def read_accounts(path):
    path = Path(path)
    if path.suffix.lower() not in (".csv", ".txt"):
        raise ValueError("Selecciona un archivo CSV o TXT.")
    try:
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("El archivo supera 5 MB.")
        raw = path.read_bytes()
    except OSError:
        raise ValueError("No se puede leer el archivo de cuentas.") from None
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            content = raw.decode("cp1252")
        except UnicodeDecodeError:
            raise ValueError("El archivo debe ser texto UTF-8 o Windows-1252.") from None
    if "\x00" in content:
        raise ValueError("El archivo debe ser texto UTF-8 o Windows-1252.")
    rows = []
    if path.suffix.lower() == ".txt":
        rows = [(i, line.strip()) for i, line in enumerate(content.splitlines(), 1)
                if line.strip() and not line.lstrip().startswith("#")]
    else:
        try:
            try:
                dialect = csv.Sniffer().sniff(content[:8192], delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.reader(io.StringIO(content, newline=""), dialect, strict=True)
            records = [(reader.line_num, row) for row in reader if any(cell.strip() for cell in row)]
        except csv.Error:
            raise ValueError("CSV mal formado; revisa las comillas y separadores.") from None
        if records:
            first = records[0][1]
            columns = [i for i, cell in enumerate(first) if cell.strip().lower() in HEADERS]
            if len(columns) > 1:
                raise ValueError("El CSV tiene varias columnas de cuenta; deja una columna username o cuenta.")
            if columns:
                column = columns[0]
                records = records[1:]
            elif len(first) == 1:
                column = 0
            else:
                raise ValueError("El CSV necesita una columna username, cuenta o URL; sin cabecera, usa una sola columna.")
            for number, row in records:
                if column >= len(row) or not row[column].strip():
                    raise ValueError(f"Falta la cuenta en la fila {number}.")
                if not columns and len(row) != 1:
                    raise ValueError(f"La fila {number} debe contener una sola cuenta.")
                rows.append((number, row[column]))
    users, seen, duplicates = [], set(), 0
    for number, value in rows:
        try:
            name = account_name(value)
        except ValueError:
            raise ValueError(f"Cuenta no válida en la fila {number}; usa usuario, @usuario o URL de perfil TikTok.") from None
        if name in seen:
            duplicates += 1
        else:
            seen.add(name)
            users.append(name)
        if len(users) > MAX_ACCOUNTS:
            raise ValueError(f"El archivo supera {MAX_ACCOUNTS} cuentas distintas.")
    if not users:
        raise ValueError("El archivo no contiene cuentas.")
    return AccountInput(tuple(users), duplicates)
