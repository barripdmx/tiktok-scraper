"""Descarga paginada de seguidores/seguidos, individual o desde CSV/TXT.

Transporte probado el 25/10/2026 a partir de night-0909/tiktokfollowers.
No ejecuta código remoto, genera firmas, rota proxies ni resuelve captchas.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from itertools import count
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.rutas import DATA_BASE
from src.utils.tiktok_relaciones import (
    DIRECTIONS, LIST_FIELDS, PayloadError, RelationStore, atomic_json, parse_list,
    profile_from_hydration, utcnow,
)
from src.utils.tiktok_relaciones_entrada import account_name, read_accounts


class FetchError(Exception):
    def __init__(self, reason, halt_batch=False):
        super().__init__(reason)
        self.reason, self.halt_batch = reason, halt_batch


def check_cancel(options):
    path = getattr(options, "cancel_file", None)
    if path and path.exists():
        raise KeyboardInterrupt


class HydrationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active, self.parts = False, []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = dict(attrs).get("id") == "__UNIVERSAL_DATA_FOR_REHYDRATION__"

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)


def session_cookie_path(options):
    if options.cookies is not None:
        return options.cookies
    name = "tiktok_cookies_secundaria.json" if options.sesion == "secundaria" else "tiktok_cookies.json"
    return ROOT / "secrets" / name


class TikTokClient:
    def __init__(self, options):
        from curl_cffi import requests
        self.session = requests.Session(impersonate="chrome", trust_env=False, timeout=20)
        self.options = options
        self.last_request = 0.0
        try:
            if options.sesion != "anonima":
                try:
                    cookies = json.loads(session_cookie_path(options).read_text(encoding="utf-8-sig"))
                    if not isinstance(cookies, list):
                        raise ValueError
                    accepted = 0
                    for cookie in cookies:
                        if not isinstance(cookie, dict):
                            raise ValueError
                        domain = str(cookie.get("domain", "")).lstrip(".").lower()
                        if domain in ("tiktok.com", "www.tiktok.com"):
                            self.session.cookies.set(cookie["name"], cookie["value"],
                                                     domain=cookie["domain"], path=cookie.get("path", "/"))
                            accepted += 1
                    if not accepted:
                        raise ValueError
                except (OSError, ValueError, KeyError, TypeError):
                    raise ValueError("No se pudo cargar la sesión guardada de TikTok.") from None
        except BaseException:
            self.close()
            raise

    def close(self):
        self.session.close()

    def _get(self, path, params=None):
        check_cancel(self.options)
        delay = 2 - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)
        check_cancel(self.options)
        try:
            response = self.session.get("https://www.tiktok.com" + path, params=params,
                                        allow_redirects=False)
        except Exception:
            raise FetchError("network_error", halt_batch=True) from None
        finally:
            self.last_request = time.monotonic()
        if response.status_code != 200:
            raise FetchError(f"http_{response.status_code}",
                             halt_batch=response.status_code in (403, 429) or response.status_code >= 500)
        if not response.content:
            raise FetchError("empty_response", halt_batch=True)
        return response

    def profile(self, username):
        response = self._get("/@" + username)
        parser = HydrationParser()
        parser.feed(response.text)
        raw = "".join(parser.parts)
        if not raw:
            raise FetchError("profile_not_available", halt_batch=True)
        try:
            detail = json.loads(raw)["__DEFAULT_SCOPE__"]["webapp.user-detail"]
            code = detail.get("statusCode", 0)
            if code != 0:
                raise FetchError(f"profile_status_{code}" if isinstance(code, int) else "profile_error")
            profile = profile_from_hydration(raw, username)
            if not profile or not isinstance(profile.get("_sec_uid"), str) or not profile["_sec_uid"]:
                raise FetchError("profile_identity_missing")
            user = detail["userInfo"]["user"]
            profile["private_account"] = user.get("privateAccount") is True
            profile["following_visibility"] = user.get("followingVisibility")
            creation = user.get("createTime")
            if type(creation) is int and 1388534400 <= creation <= time.time():
                profile["created_at"] = datetime.fromtimestamp(creation, timezone.utc).isoformat()
                profile["creation_time"] = creation
                profile["creation_source"] = "public_profile_createTime"
            return profile
        except (ValueError, KeyError, TypeError):
            raise FetchError("profile_invalid") from None

    def user_list(self, sec_uid, direction, cursor):
        response = self._get("/api/user/list/", {"count": 30, "maxCursor": 0,
            "minCursor": cursor, "scene": 67 if direction == "seguidores" else 21, "secUid": sec_uid})
        try:
            payload = response.json()
        except ValueError:
            raise FetchError("non_json_response", halt_batch=True) from None
        if not isinstance(payload, dict):
            raise FetchError("invalid_payload", halt_batch=True)
        code = payload.get("statusCode", payload.get("status_code", 0))
        if code not in (None, 0, "0"):
            private = code in (10222, "10222")
            raise FetchError("private_list" if private else "api_error", halt_batch=not private)
        # TikTok omite userList tanto en listas vacías como en una última
        # página sin identidades disponibles. Exigir éxito y fin explícito;
        # una primera página ausente con contador positivo sigue siendo error.
        terminal_cursor = payload.get("minCursor")
        terminal_continuation = (str(cursor).isascii() and str(cursor).isdigit()
            and int(cursor) > 0 and type(terminal_cursor) is int
            and -1 <= terminal_cursor <= int(cursor))
        if (not any(field in payload for field in LIST_FIELDS)
                and code in (0, "0") and type(payload.get("total")) is int
                and payload["total"] >= 0 and (payload["total"] == 0 or terminal_continuation)
                and payload.get("hasMore") is False
                and payload.get("isTruncated") is False):
            payload = {**payload, "userList": []}
        try:
            return parse_list(payload), payload
        except PayloadError as exc:
            raise FetchError(str(exc), halt_batch=True) from None


def collect_direction(client, store, profile, direction, options):
    metric = "followers" if direction == "seguidores" else "following"
    store.state(direction, status="running", advertised_count=profile.get(metric))
    if profile.get("private_account") or (direction == "seguidos" and
            profile.get("following_visibility") not in (None, 1, "1")):
        store.state(direction, status="unavailable", stop_reason="private_list", finished_at=utcnow())
        return False
    cursor, seen, reason = "0", {"0"}, "page_limit"
    deadline = time.monotonic() + options.max_segundos if options.max_segundos else float("inf")
    try:
        for number in count(1):
            check_cancel(options)
            if options.max_paginas and number > options.max_paginas:
                break
            if time.monotonic() >= deadline:
                reason = "time_limit"
                break
            page, payload = client.user_list(profile["_sec_uid"], direction, cursor)
            added = store.record_page(direction, page, max_accounts=options.max_cuentas)
            total = payload.get("total")
            store.state(direction, pages_requested=number,
                        upstream_total=total if isinstance(total, int) and not isinstance(total, bool) else None)
            print(f"@{store.username} · {direction}: página {number}, "
                  f"{store.count(direction)} cuentas guardadas, {page.rejected} registros sin identidad válida.", flush=True)
            store.export()  # Los resultados parciales sobreviven al botón Detener.
            if payload.get("isTruncated"):
                reason = "upstream_truncated"
                break
            if store.get(direction).get("limit_reached"):
                reason = "account_limit"
                break
            if page.has_more is False:
                store.state(direction, status="pagination_exhausted", stop_reason="has_more_false", finished_at=utcnow())
                return False
            if options.max_cuentas and store.count(direction) >= options.max_cuentas:
                reason = "account_limit"
                break
            next_cursor = payload.get("minCursor")
            if page.has_more is not True or isinstance(next_cursor, bool) or not isinstance(next_cursor, (str, int)):
                reason = "missing_pagination"
                break
            if not str(next_cursor).isascii() or not str(next_cursor).lstrip("-").isdigit():
                reason = "invalid_cursor"
                break
            if str(next_cursor) in seen or not added:
                reason = "no_progress_or_repeated_cursor"
                break
            cursor = str(next_cursor)
            seen.add(cursor)
        store.state(direction, status="partial", stop_reason=reason, finished_at=utcnow())
        return False
    except FetchError as exc:
        store.state(direction, status="partial" if store.count(direction) else "unavailable",
                    stop_reason=exc.reason, finished_at=utcnow())
        return exc.halt_batch
    finally:
        store.export()


def capture_account(client, username, directory, options):
    store = RelationStore(directory, username, method="http_curl_" + options.sesion)
    directions = DIRECTIONS if options.lista == "ambas" else (options.lista,)
    halt = False
    store.set_profile({"username": username, "user_id": "", "nickname": ""})
    try:
        profile = client.profile(username)
        store.set_profile(profile)
        for direction in directions:
            if halt:
                store.state(direction, status="not_run", stop_reason="source_unavailable")
                continue
            halt = collect_direction(client, store, profile, direction, options)
        if not halt:
            try:
                end_profile = client.profile(username)
                for direction in directions:
                    metric = "followers" if direction == "seguidores" else "following"
                    store.state(direction, advertised_count_end=end_profile.get(metric))
            except FetchError as exc:
                halt = exc.halt_batch
                for direction in directions:
                    store.state(direction, count_end_error=exc.reason)
    except FetchError as exc:
        halt = exc.halt_batch
        for direction in directions:
            store.state(direction, status="unavailable", stop_reason=exc.reason)
    except BaseException:
        for direction in directions:
            if store.get(direction).get("status") in ("running", "not_requested"):
                store.state(direction, status="partial", stop_reason="interrupted")
        raise
    finally:
        store.set_capture_window(store.get("started_at"), utcnow())
        try:
            result = store.export()
        finally:
            store.close()
    return result, halt


def write_job_summary(directory, job):
    atomic_json(directory / "resumen.json", job)
    path = directory / "resumen.csv"
    tmp = path.with_suffix(".csv.tmp")
    fields = ["username", "lista", "estado", "cuentas", "contador_inicio", "contador_final",
              "sin_identidad", "motivo", "carpeta"]
    with tmp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for account in job["accounts"]:
            for direction, state in account.get("lists", {}).items():
                writer.writerow(dict(zip(fields, [account["username"], direction, state.get("status"),
                    state.get("total_observed", 0), state.get("advertised_count"), state.get("advertised_count_end"),
                    state.get("rejected_records", 0), state.get("stop_reason"), account.get("directory", "")])))
    tmp.replace(path)


def run_job(options, client_factory=TikTokClient):
    source = read_accounts(options.archivo) if options.archivo else None
    usernames = source.usernames if source else (options.user,)
    directions = DIRECTIONS if options.lista == "ambas" else (options.lista,)
    data_root = (options.salida or Path(DATA_BASE)).resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    paths = {name: data_root / ("user_" + name) / "relaciones" / run_id for name in usernames}
    summary_dir = data_root / "lotes_relaciones" / run_id if source else paths[usernames[0]]
    # Comprobar dependencias/sesión antes de crear un lote vacío.
    client = client_factory(options)
    try:
        summary_dir.mkdir(parents=True, exist_ok=True)
    except BaseException:
        client.close()
        raise
    job = {"schema_version": 1, "started_at": utcnow(), "status": "running",
           "input_accounts": len(usernames), "duplicates_ignored": source.duplicates if source else 0,
           "accounts": [{"username": name, "directory": str(paths[name]),
                         "lists": {d: {"status": "pending"} for d in directions}} for name in usernames]}
    code = 0
    try:
        write_job_summary(summary_dir, job)
        print(f"Entrada: {len(usernames)} cuentas; {job['duplicates_ignored']} duplicados omitidos.", flush=True)
        print(f"Salida: {summary_dir}", flush=True)
        for index, account in enumerate(job["accounts"], 1):
            check_cancel(options)
            print(f"[{index}/{len(usernames)}] Descargando @{account['username']}…", flush=True)
            result, halt = capture_account(client, account["username"], paths[account["username"]], options)
            account["lists"] = {d: result["lists"][d] for d in directions}
            for direction, state in account["lists"].items():
                if (state["status"] != "pagination_exhausted" or state.get("rejected_records", 0) or
                    state.get("matches_displayed_count") is not True or state.get("matches_displayed_count_end") is not True):
                    code = 2
                print(f"@{account['username']} · {direction}: {state['total_observed']} guardadas; "
                      f"contador {state.get('advertised_count_end', state.get('advertised_count'))}; "
                      f"{state['stop_reason']}.", flush=True)
            write_job_summary(summary_dir, job)
            if halt:
                code = 2
                job["status"] = "stopped_source_unavailable"
                for remaining in job["accounts"][index:]:
                    remaining["lists"] = {d: {"status": "not_run", "stop_reason": "source_unavailable"} for d in directions}
                print("La fuente no está disponible o limita las solicitudes. Se detiene el lote; conserva lo descargado.", flush=True)
                break
        if job["status"] == "running":
            job["status"] = "finished_with_observations" if code else "finished"
    except BaseException:
        job["status"] = "interrupted"
        # Recuperar el último estado confirmado por SQLite/export del usuario activo.
        for account in job["accounts"]:
            manifest = Path(account["directory"]) / "ejecucion.json"
            if manifest.is_file():
                result = json.loads(manifest.read_text(encoding="utf-8"))
                account["lists"] = {d: result["lists"][d] for d in directions}
            else:
                account["lists"] = {d: {"status": "not_run", "stop_reason": "interrupted"} for d in directions}
        raise
    finally:
        client.close()
        job["finished_at"] = utcnow()
        write_job_summary(summary_dir, job)
    print(f"Resumen: {summary_dir / 'resumen.csv'}", flush=True)
    print("Finalizado. Consulta los contadores y las observaciones del resumen; la cobertura absoluta no se presupone.", flush=True)
    return code


def nonnegative(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Introduce un número entero.") from None
    if number < 0:
        raise argparse.ArgumentTypeError("Debe ser cero o positivo.")
    return number


def parser():
    p = argparse.ArgumentParser(description="Descarga seguidores/seguidos de una cuenta o de un CSV/TXT.")
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--user", type=account_name, help="Usuario, @usuario o URL de perfil.")
    target.add_argument("--archivo", type=Path, help="CSV con columna username/cuenta/URL o TXT con una cuenta por línea.")
    p.add_argument("--lista", choices=("ambas", *DIRECTIONS), default="ambas")
    p.add_argument("--max-cuentas", type=nonnegative, default=0, help="Por cuenta y lista; 0 recorre hasta el final disponible.")
    p.add_argument("--max-paginas", type=nonnegative, default=0, help="Por lista; 0 sin límite de páginas.")
    p.add_argument("--max-segundos", type=nonnegative, default=0, help="Por lista; 0 sin límite de tiempo.")
    p.add_argument("--sesion", choices=("anonima", "guardada", "principal", "secundaria"), default="anonima")
    p.add_argument("--cookies", type=Path, default=None, help="Archivo alternativo a la sesión seleccionada.")
    p.add_argument("--salida", type=Path, help="Carpeta base alternativa a data/.")
    p.add_argument("--no-prompt", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--cancel-file", type=Path, help=argparse.SUPPRESS)
    return p


def main(argv=None):
    options = parser().parse_args(argv)
    try:
        return run_job(options)
    except KeyboardInterrupt:
        print("Interrumpido. Las páginas ya guardadas permanecen en la carpeta de salida.", flush=True)
        return 130
    except ImportError:
        print("Falta una dependencia. Instala requirements.txt en este entorno de Python.", flush=True)
        return 1
    except ValueError as exc:
        print(f"Entrada no válida: {exc}", flush=True)
        return 1
    except OSError:
        print("No se pudo leer o guardar un archivo. Revisa las rutas y permisos.", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
