"""
SARA 2.0 (standalone) - Azure Functions app.
"""

import json
import logging
import os

import azure.functions as func

from sara_engine import run_prevet

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

_CORS = {
    "Access-Control-Allow-Origin": os.environ.get("SARA_ALLOWED_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "Content-Type, x-functions-key",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
}


def _json(body, status=200):
    headers = {"Content-Type": "application/json", **_CORS}
    return func.HttpResponse(json.dumps(body), status_code=status, headers=headers)


def _handle(role, req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_CORS)
    try:
        payload = req.get_json()
    except ValueError:
        payload = {}
    try:
        result = run_prevet(role, payload)
        logging.info(
            "[%s] permitted=%s review=%s findings=%d",
            role,
            result.get("roaPermitted"),
            result.get("requiresComplianceReview"),
            len(result.get("findings", [])),
        )
        return _json(result)
    except Exception as exc:
        logging.exception("pre-vet failed")
        return func.HttpResponse(
            f"{type(exc).__name__}: {exc}",
            status_code=500,
            headers={"Content-Type": "text/plain", **_CORS},
        )


@app.route(route="soa/prevet", methods=["POST", "OPTIONS"])
def soa_prevet(req: func.HttpRequest) -> func.HttpResponse:
    return _handle("soa", req)


@app.route(route="roa/prevet", methods=["POST", "OPTIONS"])
def roa_prevet(req: func.HttpRequest) -> func.HttpResponse:
    return _handle("roa", req)
