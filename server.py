"""HTTP API for the WhatsApp bot.
Run (dev):  API_KEY=secret python server.py
Run (prod): gunicorn -w 2 -b 0.0.0.0:8000 server:app
"""
import hmac
import logging
import os

from flask import Flask, jsonify, request, render_template

from crop_advisor import service, chat_parser

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("crop-api")

API_KEY = os.environ.get("API_KEY", "")
if not API_KEY and os.environ.get("ALLOW_NO_AUTH") != "1":
    raise SystemExit("Set API_KEY (or ALLOW_NO_AUTH=1 for local testing only).")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

PUBLIC_PATHS = {"/health", "/", "/chat", "/chat/reset", "/options"}


@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
    return response


@app.before_request
def check_key():
    if request.method == "OPTIONS":
        return "", 204
    if request.path in PUBLIC_PATHS or request.path.startswith("/static/") or not API_KEY:
        return None
    sent = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(sent, API_KEY):
        return jsonify(error="unauthorized"), 401
    return None


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/chat")
def chat_route():
    body = request.get_json(silent=True) or {}
    message = str(body.get("message", "")).strip()
    profile = body.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    result = chat_parser.handle_chat(message, profile)
    return jsonify(result)


@app.post("/chat/reset")
def chat_reset_route():
    result = chat_parser.handle_chat("reset", {})
    return jsonify(result)


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/options")
def options():
    return jsonify(service.meta())


def _handle(fn):
    body = request.get_json(silent=True)
    if body is None:
        return jsonify(error="send a JSON body with Content-Type: application/json"), 400
    try:
        return jsonify(fn(body))
    except service.ValidationError as e:
        return jsonify(error=str(e)), 400
    except Exception:
        log.exception("unexpected error")
        return jsonify(error="internal error"), 500


@app.post("/recommend")
def recommend_route():
    """Quick answer: best crop + top 3 + WhatsApp-ready 'message'."""
    return _handle(service.get_recommendation)


@app.post("/plan")
def plan_route():
    """Full answer: ranking, 6-season rotation, land allocation, schedule."""
    return _handle(service.get_full_plan)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
