from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "accounts.sqlite3"
CONTENT_FILE = ROOT / "site-content.json"
SESSION_COOKIE = "homi_session"
SESSION_TTL = 8 * 60 * 60
PASSWORD_ITERATIONS = 310_000
SESSIONS: dict[str, tuple[str, float]] = {}


def load_dotenv() -> None:
    """Load a local .env file without overriding real environment variables."""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


DEFAULT_CONTENT = {
    "title": "Platinum Optimizer",
    "brand": "Homi",
    "eyebrow": "SYSTEM TOOLS / BUILT BY HOMI",
    "heroText": "A focused collection of system tools and updates.\nPick a build, review the details, and get started.",
    "exampleTitle": "LESS LOAD",
    "examplesDescription": "An illustrative look at busy background activity settling into a steadier, smoother process.",
    "theme": {
        "style": "cyber",
        "accent": "#c6f36a",
        "background": "#10120f",
        "surface": "#151914",
        "text": "#f3f1e9",
    },
    "driverExamples": [
        {"title": "Wi-Fi driver failed", "description": "This optimizer does not install or repair Wi-Fi drivers. Get a compatible driver from your PC or Wi-Fi adapter manufacturer's support page."},
        {"title": "Bluetooth driver failed", "description": "This optimizer does not install or repair Bluetooth drivers. Get a compatible driver from your PC or Bluetooth adapter manufacturer's support page."},
    ],
    "downloadsTitle": "YOUR NEXT",
    "downloadsDescription": "Select a release below. Each button opens the original file on GitHub.",
    "downloads": [
        {"name": "download optimizer BETA V1", "version": "PLATINUM / RELEASE BUILD", "url": "https://github.com/homidark/Optimizer-by-homi/releases/download/Homi/Platinum-Optimizer-Homi.cmd"},
        {"name": "download latest optimizer BETA", "version": "PLATINUM / LATEST BETA", "url": "https://github.com/homidark/Optimizer-by-homi/releases/download/Homi/Platinum-Optimizer-Homi.BETA.cmd"},
        {"name": "download original optimizer", "version": "PLATINUM / ORIGINAL V9.2", "url": "https://github.com/homidark/Optimizer-by-homi/releases/download/Homi/Platinum+Optimizer.V9.2.original.cmd"},
    ],
}


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def initialize() -> None:
    load_dotenv()
    global DATABASE, CONTENT_FILE
    data_dir = Path(os.environ.get("DATA_DIR", str(ROOT))).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    DATABASE = data_dir / "accounts.sqlite3"
    CONTENT_FILE = data_dir / "site-content.json"
    owner_name = os.environ.get("OWNER_USERNAME", "").strip()
    owner_password = os.environ.get("OWNER_PASSWORD", "")
    if not owner_name or not owner_password:
        raise RuntimeError("Set OWNER_USERNAME and OWNER_PASSWORD in .env before starting the server.")
    if len(owner_name) < 3 or len(owner_name) > 32 or not re.fullmatch(r"[A-Za-z0-9_.-]+", owner_name):
        raise RuntimeError("OWNER_USERNAME must be 3-32 letters, numbers, dots, underscores, or hyphens.")
    if len(owner_password) < 12:
        raise RuntimeError("OWNER_PASSWORD must contain at least 12 characters.")

    with connect_db() as database:
        database.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY COLLATE NOCASE, salt BLOB NOT NULL, password_hash BLOB NOT NULL, is_owner INTEGER NOT NULL DEFAULT 0)")
        row = database.execute("SELECT username FROM users WHERE is_owner = 1 LIMIT 1").fetchone()
        if row is None:
            salt = secrets.token_bytes(16)
            database.execute("INSERT INTO users (username, salt, password_hash, is_owner) VALUES (?, ?, ?, 1)", (owner_name, salt, password_hash(owner_password, salt)))

    if not CONTENT_FILE.exists():
        CONTENT_FILE.write_text(json.dumps(DEFAULT_CONTENT, indent=2), encoding="utf-8")
    else:
        content = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
        content.setdefault("exampleTitle", DEFAULT_CONTENT["exampleTitle"])
        content.setdefault("examplesDescription", DEFAULT_CONTENT["examplesDescription"])
        content.setdefault("theme", DEFAULT_CONTENT["theme"])
        content.setdefault("driverExamples", DEFAULT_CONTENT["driverExamples"])
        for removed_field in ("tag", "gallery"):
            content.pop(removed_field, None)
        content = validate_content(content, DEFAULT_CONTENT)
        CONTENT_FILE.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")


def validate_content(candidate: object, template: object, path: str = "content") -> object:
    if isinstance(template, dict):
        if not isinstance(candidate, dict) or candidate.keys() != template.keys():
            raise ValueError(f"{path} has missing or unexpected fields.")
        return {key: validate_content(candidate[key], value, f"{path}.{key}") for key, value in template.items()}
    if isinstance(template, list):
        if not isinstance(candidate, list) or len(candidate) != len(template):
            raise ValueError(f"{path} must contain exactly {len(template)} entries.")
        return [validate_content(value, template[index], f"{path}.{index}") for index, value in enumerate(candidate)]
    if not isinstance(candidate, str) or len(candidate) > 2000:
        raise ValueError(f"{path} must be text with at most 2000 characters.")
    if path == "content.theme.style" and candidate not in {"cyber", "minimal", "terminal"}:
        raise ValueError("Choose a supported UI style.")
    if path.startswith("content.theme.") and path.rsplit(".", 1)[-1] in {"accent", "background", "surface", "text"}:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", candidate):
            raise ValueError(f"{path} must be a six-digit hex color.")
    if path.endswith(".url") or path.endswith(".image"):
        parsed = urlsplit(candidate)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"{path} must be a valid HTTPS URL.")
    return candidate


class SiteHandler(BaseHTTPRequestHandler):
    server_version = "HomiSite/1.0"

    def log_message(self, format: str, *args: object) -> None:
        if sys.stdout is not None:
            print(f"[{self.log_date_time_string()}] {args[0] if args else format}")

    def send_json(self, data: object, status: int = 200, headers: dict[str, str] | None = None) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_paused(self) -> None:
        body = b"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Site paused</title><body style='margin:0;padding:12vh 8vw;background:#10120f;color:#f3f1e9;font:16px system-ui'><p style='color:#c6f36a;font:12px monospace'>HOMI / SERVER CONTROL</p><h1 style='font-size:clamp(36px,8vw,72px)'>SITE PAUSED</h1><p>The server owner paused this site. Refresh after it resumes.</p></body></html>"
        self.send_response(HTTPStatus.SERVICE_UNAVAILABLE)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Retry-After", "5")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> object:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("Invalid request length.") from error
        if length < 1 or length > 100_000:
            raise ValueError("Request body is empty or too large.")
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ValueError("Invalid JSON.") from error

    def validate_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return urlsplit(origin).netloc == self.headers.get("Host")

    def user(self) -> sqlite3.Row | None:
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(SESSION_COOKIE)
        if not morsel:
            return None
        session = SESSIONS.get(morsel.value)
        if not session:
            return None
        username, expiry = session
        if expiry < time.time():
            SESSIONS.pop(morsel.value, None)
            return None
        with connect_db() as database:
            return database.execute("SELECT username, is_owner FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()

    def session_headers(self, token: str, max_age: int = SESSION_TTL) -> dict[str, str]:
        return {"Set-Cookie": f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}"}

    def static_file(self, filename: str) -> None:
        path = ROOT / filename
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        content_type = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml"}.get(path.suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.end_headers()
        self.wfile.write(body)

    def process_svg(self, accent: str) -> None:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        root = ET.fromstring((ROOT / "process-flow.svg").read_bytes())
        default_accent = DEFAULT_CONTENT["theme"]["accent"]
        for element in root.iter():
            for name, value in element.attrib.items():
                if value.lower() == default_accent:
                    element.set(name, accent)
        body = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if getattr(self.server, "paused", False):
            self.send_paused()
            return
        path = urlsplit(self.path).path
        if path == "/":
            self.static_file("index.html")
        elif path == "/styles.css":
            self.static_file("styles.css")
        elif path == "/app.js":
            self.static_file("app.js")
        elif path == "/process-flow.svg":
            accent = parse_qs(urlsplit(self.path).query).get("accent", [DEFAULT_CONTENT["theme"]["accent"]])[0]
            self.process_svg(accent)
        elif path == "/api/content":
            try:
                self.send_json({"content": json.loads(CONTENT_FILE.read_text(encoding="utf-8"))})
            except (OSError, json.JSONDecodeError):
                self.send_json({"error": "Site content could not be loaded."}, HTTPStatus.INTERNAL_SERVER_ERROR)
        elif path == "/api/me":
            user = self.user()
            self.send_json({"user": {"username": user["username"], "isOwner": bool(user["is_owner"])} if user else None})
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if getattr(self.server, "paused", False):
            self.send_paused()
            return
        path = urlsplit(self.path).path
        if not self.validate_origin():
            self.send_json({"error": "Request origin not allowed."}, HTTPStatus.FORBIDDEN)
            return
        if path == "/api/logout":
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            morsel = cookie.get(SESSION_COOKIE)
            if morsel:
                SESSIONS.pop(morsel.value, None)
            self.send_json({"ok": True}, headers=self.session_headers("", 0))
            return
        if path not in ("/api/login", "/api/register"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            data = self.read_json()
            if not isinstance(data, dict):
                raise ValueError("Invalid request.")
            username = data.get("username", "")
            password = data.get("password", "")
            if not isinstance(username, str) or not isinstance(password, str):
                raise ValueError("Enter a username and password.")
            username = username.strip()
            if len(username) < 3 or len(username) > 32 or not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
                raise ValueError("Username must be 3-32 letters, numbers, dots, underscores, or hyphens.")
            if len(password) < 12 or len(password) > 256:
                raise ValueError("Password must be between 12 and 256 characters.")

            with connect_db() as database:
                existing = database.execute("SELECT username, salt, password_hash, is_owner FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
                if path == "/api/register":
                    if existing:
                        raise ValueError("That username is already in use.")
                    salt = secrets.token_bytes(16)
                    database.execute("INSERT INTO users (username, salt, password_hash, is_owner) VALUES (?, ?, ?, 0)", (username, salt, password_hash(password, salt)))
                    existing = database.execute("SELECT username, salt, password_hash, is_owner FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
                elif not existing or not hmac.compare_digest(password_hash(password, existing["salt"]), existing["password_hash"]):
                    self.send_json({"error": "Username or password is incorrect."}, HTTPStatus.UNAUTHORIZED)
                    return

            token = secrets.token_urlsafe(32)
            SESSIONS[token] = (existing["username"], time.time() + SESSION_TTL)
            self.send_json({"user": {"username": existing["username"], "isOwner": bool(existing["is_owner"]) }}, headers=self.session_headers(token))
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except sqlite3.IntegrityError:
            self.send_json({"error": "That username is already in use."}, HTTPStatus.CONFLICT)

    def do_PUT(self) -> None:
        if getattr(self.server, "paused", False):
            self.send_paused()
            return
        if urlsplit(self.path).path != "/api/content":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self.validate_origin():
            self.send_json({"error": "Request origin not allowed."}, HTTPStatus.FORBIDDEN)
            return
        user = self.user()
        if not user or not user["is_owner"]:
            self.send_json({"error": "Owner sign-in is required."}, HTTPStatus.FORBIDDEN)
            return
        try:
            candidate = validate_content(self.read_json(), DEFAULT_CONTENT)
            CONTENT_FILE.write_text(json.dumps(candidate, indent=2, ensure_ascii=False), encoding="utf-8")
            self.send_json({"ok": True, "content": candidate})
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        except OSError:
            self.send_json({"error": "Could not save site content on the server."}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    initialize()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), SiteHandler)
    print(f"Platinum Optimizer + Homi is running at http://{host}:{port}")
    print("Owner credentials are loaded from environment/.env; IP addresses do not grant admin access.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
