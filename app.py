"""
SARA 2.0 App Service entrypoint.

This lets the same repo run as a normal Azure Web App while api/function_app.py
continues to support Azure Functions local/deployed hosting.
"""

import json
import os
import sys
from pathlib import Path

from flask import Flask, Response, request, send_from_directory

ROOT = Path(__file__).resolve().parent
API_DIR = ROOT / "api"
FRONTEND_DIR = ROOT / "frontend"
sys.path.insert(0, str(API_DIR))

from sara_engine import run_prevet  # noqa: E402

app = Flask(__name__, static_folder=None)


def _cors_headers():
    return {
        "Access-Control-Allow-Origin": os.environ.get("SARA_ALLOWED_ORIGIN", "*"),
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
    }


def _json(body, status=200):
    return Response(
        json.dumps(body),
        status=status,
        headers={"Content-Type": "application/json", **_cors_headers()},
    )


def _handle(role):
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())
    payload = request.get_json(silent=True) or {}
    try:
        return _json(run_prevet(role, payload))
    except Exception as exc:
        app.logger.exception("pre-vet failed")
        return Response(
            f"{type(exc).__name__}: {exc}",
            status=500,
            headers={"Content-Type": "text/plain", **_cors_headers()},
        )


@app.get("/")
@app.get("/sara")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.post("/api/soa/prevet")
@app.route("/api/soa/prevet", methods=["OPTIONS"])
def soa_prevet():
    return _handle("soa")


@app.post("/api/roa/prevet")
@app.route("/api/roa/prevet", methods=["OPTIONS"])
def roa_prevet():
    return _handle("roa")
