from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "accounts.sqlite3"
CONTENT_FILE = ROOT / "site-content.json"
SESSION_COOKIE = "homi_session"
SESSION_TTL = 8 * 60 * 60
PASSWORD_ITERATIONS = 310_000
SESSIONS: dict[str, tuple[str, float]] = {}
app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 100_000
app.config["SITE_PAUSED"] = False
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)


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


def validate_origin() -> bool:
    origin = request.headers.get("Origin")
    return not origin or urlsplit(origin).netloc == request.host


def current_user() -> sqlite3.Row | None:
    token = request.cookies.get(SESSION_COOKIE)
    session = SESSIONS.get(token) if token else None
    if not session:
        return None
    username, expiry = session
    if expiry < time.time():
        SESSIONS.pop(token, None)
        return None
    with connect_db() as database:
        return database.execute(
            "SELECT username, is_owner FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()


@app.before_request
def reject_requests_while_paused():
    if not app.config.get("SITE_PAUSED"):
        return None
    body = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Site paused</title><body style="margin:0;padding:12vh 8vw;background:#10120f;color:#f3f1e9;font:16px system-ui"><p style="color:#c6f36a;font:12px monospace">HOMI / SERVER CONTROL</p><h1 style="font-size:clamp(36px,8vw,72px)">SITE PAUSED</h1><p>The server owner paused this site. Refresh after it resumes.</p></body></html>"""
    return Response(body, status=503, content_type="text/html; charset=utf-8", headers={"Retry-After": "5", "Cache-Control": "no-store"})


@app.after_request
def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/")
def home():
    return send_from_directory(ROOT, "index.html")


@app.get("/styles.css")
def styles():
    return send_from_directory(ROOT, "styles.css")


@app.get("/app.js")
def javascript():
    return send_from_directory(ROOT, "app.js")


@app.get("/process-flow.svg")
def process_svg():
    accent = request.args.get("accent", DEFAULT_CONTENT["theme"]["accent"])
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        return Response(status=400)
    root = ET.fromstring((ROOT / "process-flow.svg").read_bytes())
    default_accent = DEFAULT_CONTENT["theme"]["accent"]
    for element in root.iter():
        for name, value in element.attrib.items():
            if value.lower() == default_accent:
                element.set(name, accent)
    return Response(ET.tostring(root, encoding="utf-8", xml_declaration=True), mimetype="image/svg+xml")


@app.get("/api/content")
def get_content():
    try:
        return jsonify(content=json.loads(CONTENT_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return jsonify(error="Site content could not be loaded."), 500


@app.get("/api/me")
def get_current_user():
    user = current_user()
    return jsonify(user={"username": user["username"], "isOwner": bool(user["is_owner"])} if user else None)


def set_session_cookie(response, token: str, max_age: int = SESSION_TTL):
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        path="/",
        secure=request.is_secure,
        httponly=True,
        samesite="Strict",
    )
    return response


@app.post("/api/logout")
def logout():
    if not validate_origin():
        return jsonify(error="Request origin not allowed."), 403
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        SESSIONS.pop(token, None)
    return set_session_cookie(jsonify(ok=True), "", 0)


@app.post("/api/login")
@app.post("/api/register")
def authenticate():
    if not validate_origin():
        return jsonify(error="Request origin not allowed."), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid JSON."), 400
    username = data.get("username", "")
    password = data.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="Enter a username and password."), 400
    username = username.strip()
    if len(username) < 3 or len(username) > 32 or not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return jsonify(error="Username must be 3-32 letters, numbers, dots, underscores, or hyphens."), 400
    if len(password) < 12 or len(password) > 256:
        return jsonify(error="Password must be between 12 and 256 characters."), 400

    try:
        with connect_db() as database:
            existing = database.execute(
                "SELECT username, salt, password_hash, is_owner FROM users WHERE username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
            if request.path == "/api/register":
                if existing:
                    return jsonify(error="That username is already in use."), 400
                salt = secrets.token_bytes(16)
                database.execute(
                    "INSERT INTO users (username, salt, password_hash, is_owner) VALUES (?, ?, ?, 0)",
                    (username, salt, password_hash(password, salt)),
                )
                existing = database.execute(
                    "SELECT username, salt, password_hash, is_owner FROM users WHERE username = ? COLLATE NOCASE",
                    (username,),
                ).fetchone()
            elif not existing or not hmac.compare_digest(
                password_hash(password, existing["salt"]), existing["password_hash"]
            ):
                return jsonify(error="Username or password is incorrect."), 401
    except sqlite3.IntegrityError:
        return jsonify(error="That username is already in use."), 409

    token = secrets.token_urlsafe(32)
    SESSIONS[token] = (existing["username"], time.time() + SESSION_TTL)
    response = jsonify(user={"username": existing["username"], "isOwner": bool(existing["is_owner"])})
    return set_session_cookie(response, token)


@app.put("/api/content")
def save_content():
    if not validate_origin():
        return jsonify(error="Request origin not allowed."), 403
    user = current_user()
    if not user or not user["is_owner"]:
        return jsonify(error="Owner sign-in is required."), 403
    candidate = request.get_json(silent=True)
    if candidate is None:
        return jsonify(error="Invalid JSON."), 400
    try:
        content = validate_content(candidate, DEFAULT_CONTENT)
        CONTENT_FILE.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
        return jsonify(ok=True, content=content)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except OSError:
        return jsonify(error="Could not save site content on the server."), 500


@app.errorhandler(413)
def request_too_large(_error):
    return jsonify(error="Request body is too large."), 413


def main() -> None:
    initialize()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Platinum Optimizer + Homi is running at http://{host}:{port}")
    print("Owner credentials are loaded from environment/.env; IP addresses do not grant admin access.")
    app.run(host=host, port=port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
