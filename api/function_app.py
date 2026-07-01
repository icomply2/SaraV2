"""
SARA 2.0 (standalone) - Azure Functions app.
"""

import json
import logging
import os
import uuid

import azure.functions as func

from check_catalog import get_checks
from sara_engine import run_prevet

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

PREVET_ERROR_MESSAGE = (
    "SARA could not complete the pre-vet. Please try again or contact support "
    "if the problem continues."
)

_CORS = {
    "Access-Control-Allow-Origin": os.environ.get("SARA_ALLOWED_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "Content-Type, x-functions-key",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
}


def _json(body, status=200):
    headers = {"Content-Type": "application/json", **_CORS}
    return func.HttpResponse(json.dumps(body), status_code=status, headers=headers)


def _error(code, message, status, request_id=None):
    body = {"error": code, "message": message}
    if request_id:
        body["requestId"] = request_id
    return _json(body, status=status)


def _handle(role, req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_CORS)
    try:
        payload = req.get_json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        return _error("invalid_request", "Request body must be a JSON object.", 400)
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
    except Exception:
        request_id = uuid.uuid4().hex
        logging.exception("pre-vet failed request_id=%s role=%s", request_id, role)
        return _error("prevet_failed", PREVET_ERROR_MESSAGE, 500, request_id)


@app.route(route="soa/prevet", methods=["POST", "OPTIONS"])
def soa_prevet(req: func.HttpRequest) -> func.HttpResponse:
    return _handle("soa", req)


@app.route(route="roa/prevet", methods=["POST", "OPTIONS"])
def roa_prevet(req: func.HttpRequest) -> func.HttpResponse:
    return _handle("roa", req)


@app.route(route="sara/checks", methods=["GET", "OPTIONS"])
def sara_checks(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_CORS)
    review_type = req.params.get("reviewType") or req.params.get("review_type")
    return _json({"data": get_checks(review_type), "status": True})
