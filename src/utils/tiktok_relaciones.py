"""Contratos y persistencia de relaciones TikTok, sin dependencias de navegador."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DIRECTIONS = ("seguidores", "seguidos")
USER_RE = re.compile(r"[a-zA-Z0-9_.]{1,24}")
LIST_FIELDS = ("userList", "user_list", "user_followers", "user_following")


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def observation_time(value):
    if value is None:
        return utcnow()
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result.astimezone(timezone.utc).isoformat()
    except ValueError:
        raise ValueError("Fecha de observacion no valida; usa ISO 8601 con zona horaria.") from None


def normalize_username(value):
    value = str(value or "").strip().lstrip("@").lower()
    if not USER_RE.fullmatch(value):
        raise ValueError("Usuario de TikTok no valido; usa el handle sin URL.")
    return value


def exact_id(value):
    """Rechaza floats y notacion decimal: los UID no son magnitudes numericas."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("UID impreciso")
    text = str(value)
    if not text.isascii() or not text.isdigit() or int(text) <= 0:
        raise ValueError("UID no valido")
    return text


def account_from_user(entry):
    if not isinstance(entry, dict):
        raise ValueError("Cuenta no valida")
    user = entry.get("user", entry)
    if not isinstance(user, dict):
        raise ValueError("Cuenta no valida")
    uid = exact_id(user.get("id") or user.get("uid") or user.get("user_id"))
    name = user.get("uniqueId") or user.get("unique_id") or user.get("username")
    name = normalize_username(name) if name else ""
    if not uid and not name:
        raise ValueError("Cuenta sin identidad")
    verified = user.get("verified", user.get("is_verified"))
    return {
        "user_id": uid, "username": name,
        "nickname": str(user.get("nickname") or user.get("display_name") or ""),
        "verified": verified if isinstance(verified, bool) else None,
    }


class PayloadError(ValueError):
    pass


@dataclass
class ListPage:
    users: list[dict]
    has_more: bool | None = None
    cursor: str | None = None
    rejected: int = 0


def parse_list(payload):
    """Contratos web y Research; una respuesta vacia/invalida nunca es lista vacia."""
    if not isinstance(payload, dict):
        raise PayloadError("invalid_payload")
    error = payload.get("error") or {}
    if isinstance(error, dict) and error.get("code") not in (None, 0, "0", "ok"):
        raise PayloadError("api_error")
    for key in ("statusCode", "status_code"):
        if payload.get(key) not in (None, 0, "0"):
            raise PayloadError("api_error")
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        raise PayloadError("invalid_payload")
    field = next((f for f in LIST_FIELDS if f in data), None)
    if field is None or not isinstance(data[field], list):
        raise PayloadError("missing_user_list")
    users, rejected = [], 0
    for item in data[field]:
        try:
            users.append(account_from_user(item))
        except ValueError:
            rejected += 1
    more = data.get("hasMore", data.get("has_more"))
    if more is None:
        has_more = None
    elif isinstance(more, (bool, int)) and more in (0, 1):
        has_more = bool(more)
    else:
        raise PayloadError("invalid_has_more")
    cursors = {k: data[k] for k in ("cursor", "minCursor", "maxCursor")
               if k in data and isinstance(data[k], (str, int)) and not isinstance(data[k], bool)}
    cursor = json.dumps(cursors, sort_keys=True, separators=(",", ":")) if cursors else None
    return ListPage(users, has_more, cursor, rejected)


def profile_from_hydration(raw, username):
    """El JSON se parsea en Python para conservar IDs de 64 bits sin redondeo JS."""
    try:
        detail = json.loads(raw or "{}").get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail", {})
        info = detail.get("userInfo", {})
        user = info.get("user", {})
        if not user:
            return {}
        account = account_from_user(user)
        if account["username"] != normalize_username(username):
            return {}
        stats = info.get("stats", {})
        result = {**account, "observed_at": utcnow()}
        for source, dest in (("followerCount", "followers"), ("followingCount", "following"),
                             ("heartCount", "likes"), ("videoCount", "video_count")):
            value = stats.get(source)
            result[dest] = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
        # Solo para asociar trafico al perfil objetivo; no se exporta.
        result["_sec_uid"] = user.get("secUid", "")
        return result
    except (ValueError, TypeError, AttributeError):
        return {}


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class RelationStore:
    """SQLite es la fuente de verdad; miembros y checkpoint se confirman juntos."""
    def __init__(self, directory, username, resume=False, method="web_browser"):
        self.directory = Path(directory)
        username = normalize_username(username)
        if method not in ("web_browser", "chrome_visible_dom", "http_curl_anonima", "http_curl_guardada"):
            raise ValueError("Metodo de captura no valido")
        database = self.directory / "relaciones.sqlite3"
        if resume and not database.is_file():
            raise ValueError("No existe una ejecucion que reanudar en esa carpeta.")
        if not resume and database.exists():
            raise ValueError("La carpeta ya contiene una ejecucion; usa --reanudar.")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS accounts (
                account_key TEXT PRIMARY KEY, user_id TEXT, username TEXT NOT NULL,
                nickname TEXT NOT NULL, verified INTEGER, observed_at TEXT NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS uid_unique ON accounts(user_id) WHERE user_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS members (
                direction TEXT NOT NULL, account_key TEXT NOT NULL REFERENCES accounts(account_key),
                observed_at TEXT NOT NULL, source TEXT NOT NULL,
                PRIMARY KEY(direction, account_key));
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY, direction TEXT NOT NULL, observed_at TEXT NOT NULL,
                source TEXT NOT NULL, cursor TEXT, has_more INTEGER,
                received INTEGER NOT NULL, rejected INTEGER NOT NULL, added INTEGER NOT NULL);
        """)
        if resume:
            if self.get("username") != username:
                self.db.close()
                raise ValueError("La cuenta no coincide con la ejecucion guardada.")
            if self.get("method") != method:
                self.db.close()
                raise ValueError("El metodo de captura no coincide; crea otra ejecucion.")
        else:
            with self.db:
                self._put("username", username)
                self._put("run_id", self.directory.name)
                self._put("started_at", utcnow())
                self._put("method", method)
                for direction in DIRECTIONS:
                    self._put(direction, {"status": "not_requested", "stop_reason": None})
        self.username = username

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def _put(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))

    def state(self, direction, **updates):
        if direction not in DIRECTIONS:
            raise ValueError("Direccion no valida")
        state = {**self.get(direction, {}), **updates}
        with self.db:
            self._put(direction, state)
        return state

    def _account(self, user):
        uid, name = user.get("user_id") or "", user.get("username") or ""
        if not uid and not name:
            raise ValueError("Identidad vacia")
        uid = exact_id(uid) if uid else ""
        name = normalize_username(name) if name else ""
        existing = self.db.execute("SELECT account_key FROM accounts WHERE user_id=?", (uid,)).fetchone() if uid else None
        if not existing and name:
            existing = self.db.execute(
                "SELECT account_key FROM accounts WHERE username=? AND user_id IS NULL", (name,)).fetchone()
        if not existing and not uid and name:
            matches = self.db.execute("SELECT account_key FROM accounts WHERE username=?", (name,)).fetchall()
            if len(matches) == 1:
                existing = matches[0]
        key = existing["account_key"] if existing else ("uid:" + uid if uid else "handle:" + name)
        self.db.execute("""
            INSERT INTO accounts VALUES (?,?,?,?,?,?)
            ON CONFLICT(account_key) DO UPDATE SET
                user_id=COALESCE(excluded.user_id,accounts.user_id),
                username=CASE WHEN excluded.username='' THEN accounts.username ELSE excluded.username END,
                nickname=CASE WHEN excluded.nickname='' THEN accounts.nickname ELSE excluded.nickname END,
                verified=COALESCE(excluded.verified,accounts.verified), observed_at=excluded.observed_at
        """, (key, uid or None, name, user.get("nickname") or "", user.get("verified"), utcnow()))
        return key

    def set_profile(self, profile):
        safe = {k: v for k, v in profile.items() if not k.startswith("_")}
        if normalize_username(safe.get("username")) != self.username:
            raise ValueError("Perfil distinto de la cuenta solicitada")
        with self.db:
            self._put("profile", safe)
            self._put("target_key", self._account(safe))

    def set_capture_window(self, started_at, finished_at=None):
        with self.db:
            self._put("started_at", observation_time(started_at))
            if finished_at:
                self._put("finished_at", observation_time(finished_at))

    def count(self, direction):
        return self.db.execute("SELECT COUNT(*) FROM members WHERE direction=?", (direction,)).fetchone()[0]

    def record_page(self, direction, page, source="api", max_accounts=0, observed_at=None):
        if direction not in DIRECTIONS:
            raise ValueError("Direccion no valida")
        observed_at = observation_time(observed_at)
        before = self.count(direction)
        added, limited = 0, False
        with self.db:
            for user in page.users:
                key = self._account(user)
                if key == self.get("target_key"):
                    continue
                exists = self.db.execute("SELECT 1 FROM members WHERE direction=? AND account_key=?", (direction, key)).fetchone()
                if exists:
                    if source == "api":
                        self.db.execute("UPDATE members SET source='api' WHERE direction=? AND account_key=?", (direction, key))
                    continue
                if max_accounts and before + added >= max_accounts:
                    limited = True
                    continue
                self.db.execute("INSERT INTO members VALUES (?,?,?,?)", (direction, key, observed_at, source))
                added += 1
            self.db.execute(
                "INSERT INTO pages(direction,observed_at,source,cursor,has_more,received,rejected,added) VALUES (?,?,?,?,?,?,?,?)",
                (direction, observed_at, source, page.cursor, page.has_more, len(page.users), page.rejected, added))
            state = {**self.get(direction, {}), "last_observed_at": observed_at, "total_observed": before + added}
            if source == "api":
                state.update(cursor=page.cursor, has_more=page.has_more)
            state["rejected_records"] = state.get("rejected_records", 0) + page.rejected
            state["limit_reached"] = state.get("limit_reached", False) or limited
            self._put(direction, state)
        return added

    def _csv(self, name, fields, records):
        path = self.directory / name
        tmp = path.with_suffix(".csv.tmp")
        with tmp.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        tmp.replace(path)

    def export(self):
        profile = self.get("profile", {"username": self.username})
        manifest = {"schema_version": 1, "run_id": self.get("run_id"), "username": self.username,
                    "started_at": self.get("started_at"), "finished_at": self.get("finished_at"), "exported_at": utcnow(),
                    "method": self.get("method"), "coverage_validated": False, "profile": profile, "lists": {}}
        edges = []
        all_rows = []
        for direction in DIRECTIONS:
            state = self.get(direction, {}).copy()
            records = [dict(row) for row in self.db.execute("""
                SELECT a.*,m.observed_at AS relation_observed_at,m.source
                FROM members m JOIN accounts a USING(account_key) WHERE m.direction=? ORDER BY m.rowid
            """, (direction,))]
            state["total_observed"] = len(records)
            state["api_pages"] = self.db.execute("SELECT COUNT(*) FROM pages WHERE direction=? AND source='api'", (direction,)).fetchone()[0]
            state["dom_pages"] = self.db.execute("SELECT COUNT(*) FROM pages WHERE direction=? AND source!='api'", (direction,)).fetchone()[0]
            advertised = state.get("advertised_count")
            state["matches_displayed_count"] = (len(records) == advertised) if advertised is not None else None
            advertised_end = state.get("advertised_count_end")
            state["matches_displayed_count_end"] = (len(records) == advertised_end) if advertised_end is not None else None
            state["coverage_validated"] = False
            manifest["lists"][direction] = state
            for record in records:
                record["observed_at"] = record["relation_observed_at"]
                record["run_id"] = self.get("run_id")
                record["target_username"] = self.username
                account = {"account_key": record["account_key"], "user_id": record["user_id"] or "", "username": record["username"]}
                target = {"account_key": self.get("target_key", "handle:" + self.username), "user_id": profile.get("user_id") or "", "username": self.username}
                src, dst = (account, target) if direction == "seguidores" else (target, account)
                edges.append({**{"source_" + k: v for k, v in src.items()}, **{"target_" + k: v for k, v in dst.items()},
                              "relation": "follows", "observed_at": record["observed_at"], "run_id": record["run_id"],
                              "observed_in": direction, "source": record["source"]})
            self._csv(direction + ".csv", ["run_id", "target_username", "user_id", "username", "nickname", "verified", "observed_at", "source"], records)
            all_rows.extend(records)
        self._csv("relaciones.csv", ["source_account_key", "source_user_id", "source_username", "target_account_key", "target_user_id",
                                    "target_username", "relation", "observed_at", "run_id", "observed_in", "source"], edges)
        atomic_json(self.directory / "perfil.json", profile)
        atomic_json(self.directory / "ejecucion.json", manifest)
        atomic_json(self.directory / "checkpoint.json", {"username": self.username, "lists": manifest["lists"],
                    "resume_strategy": ("El descargador HTTP conserva cada página; una nueva ejecución crea una captura independiente."
                                        if self.get("method").startswith("http_curl_") else
                                        "Reabrir listas desde el inicio y deduplicar contra SQLite; no repetir URLs firmadas.")})
        # Los ID son atributos de texto tambien en Gephi.
        import networkx as nx
        graph = nx.DiGraph(run_id=self.get("run_id"), coverage_validated="false")
        target_key = self.get("target_key", "handle:" + self.username)
        graph.add_node(target_key, label=self.username, username=self.username, user_id=profile.get("user_id") or "")
        for row in all_rows:
            graph.add_node(row["account_key"], label=row["username"] or row["account_key"],
                           username=row["username"], user_id=row["user_id"] or "")
        for edge in edges:
            graph.add_edge(edge["source_account_key"], edge["target_account_key"], relation="follows",
                           observed_at=edge["observed_at"], observed_in=edge["observed_in"])
        graph_tmp = self.directory / "relaciones.gexf.tmp"
        nx.write_gexf(graph, graph_tmp)
        graph_tmp.replace(self.directory / "relaciones.gexf")
        return manifest

    def close(self):
        self.db.close()
