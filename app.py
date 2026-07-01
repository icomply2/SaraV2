"""
SARA 2.0 App Service entrypoint.

This lets the same repo run as a normal Azure Web App while api/function_app.py
continues to support Azure Functions local/deployed hosting.
"""

import json
import os
import sys
import uuid
import base64
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, request, send_from_directory

ROOT = Path(__file__).resolve().parent
API_DIR = ROOT / "api"
FRONTEND_DIR = ROOT / "frontend"
sys.path.insert(0, str(API_DIR))

from check_catalog import default_prompts_for_review_type, get_checks  # noqa: E402
from sara_engine import run_prevet  # noqa: E402

app = Flask(__name__, static_folder=None)

PREVET_ERROR_MESSAGE = (
    "SARA could not complete the pre-vet. Please try again or contact support "
    "if the problem continues."
)
USER_LOOKUP_CACHE = {}
USER_DETAIL_NAME_CACHE = {}

SOA_COMPLIANCE_PROMPTS = [
    "OBJ Did the adviser identify the client's objectives? (s961B(2)(a))",
    "FINSIT Did the adviser identify the financial situation and needs? (s961B(2)(a))",
    "RISK Has the adviser identified the client's risk profile? (s961B(2))",
    "SCOPE Did the adviser identify the subject matter and scope of advice, incl. limitations? (s961B(2)(b))",
    "PRODUCT Does the SOA explain how the recommended product meets the client's objective? (s961G)",
    "PROPERTY Is any direct property, a non-financial product, recommended? (Pass / N/A if none)",
    "ALLOC Does the recommended asset allocation meet the risk profile? (s961B / s961G)",
    "JUDGE Are the adviser's judgements based on the client's relevant circumstances? (s961B(2)(f))",
    "NEEDS Has a needs analysis been completed, incl. insurance where in scope? (best interests / s961G)",
    "FEES Are fees payable and remuneration/commissions adequately disclosed? (s947B / conflicted remuneration)",
    "PDS Is a Product Disclosure Statement provided/referenced for recommended products?",
    "OFA Is an ongoing/annual fee agreement and consent to deduct fees present? (s962)",
    "CREDIT Does the SOA avoid unlicensed credit advice? (NCCP Act 2009)",
]

ROA_COMPLIANCE_PROMPTS = [
    "RA-01 Is this further advice suited to an RoA?",
    "RA-02 Can the prior SOA it relies on be located and is it valid?",
    "RA-03 Have the client's relevant personal circumstances changed significantly since the SOA?",
    "RA-04 Does the further advice stay within the basis and product scope of the SOA?",
    "RA-05 Does the RoA record the required content and is it retained?",
]


def _cors_headers():
    return {
        "Access-Control-Allow-Origin": os.environ.get("SARA_ALLOWED_ORIGIN", "*"),
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
        "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    }


def _json(body, status=200):
    return Response(
        json.dumps(body),
        status=status,
        headers={"Content-Type": "application/json", **_cors_headers()},
    )


def _error(code, message, status, request_id=None, extra=None):
    body = {"error": code, "message": message}
    if request_id:
        body["requestId"] = request_id
    if extra:
        body.update(extra)
    return _json(body, status=status)


def _upstream_error_message(raw_body, fallback):
    if not raw_body:
        return fallback
    try:
        payload = json.loads(raw_body)
    except Exception:
        return raw_body.strip()[:500] or fallback

    if not isinstance(payload, dict):
        return fallback

    model_errors = payload.get("modelErrors") or payload.get("ModelErrors") or []
    if model_errors:
        parts = []
        for err in model_errors:
            if not isinstance(err, dict):
                continue
            field = err.get("fieldName") or err.get("FieldName") or "Field"
            message = err.get("errorMessage") or err.get("ErrorMessage") or ""
            parts.append(f"{field}: {message}" if message else str(field))
        if parts:
            return "; ".join(parts)

    return (
        payload.get("message")
        or payload.get("Message")
        or payload.get("error")
        or payload.get("Error")
        or fallback
    )


def _upstream_error_details(raw_body):
    details = {}
    if not raw_body:
        return details

    try:
        payload = json.loads(raw_body)
    except Exception:
        details["upstreamBody"] = raw_body.strip()[:1000]
        return details

    if not isinstance(payload, dict):
        details["upstreamBody"] = raw_body.strip()[:1000]
        return details

    for source, target in (
        ("traceId", "upstreamTraceId"),
        ("TraceId", "upstreamTraceId"),
        ("statusCode", "upstreamStatusCode"),
        ("StatusCode", "upstreamStatusCode"),
        ("status", "upstreamStatus"),
        ("Status", "upstreamStatus"),
        ("modelErrors", "modelErrors"),
        ("ModelErrors", "modelErrors"),
    ):
        if source in payload and payload[source] not in (None, ""):
            details[target] = payload[source]

    message = payload.get("message") or payload.get("Message")
    if message:
        details["upstreamMessage"] = message
    details["upstreamBody"] = raw_body.strip()[:1000]
    return details


def _default_prompts_for_review_type(review_type):
    return default_prompts_for_review_type(review_type)


def _handle(role):
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return _error("invalid_request", "Request body must be a JSON object.", 400)
    try:
        return _json(run_prevet(role, payload))
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("pre-vet failed request_id=%s role=%s", request_id, role)
        return _error("prevet_failed", PREVET_ERROR_MESSAGE, 500, request_id)


def _external_api_base():
    return (
        os.environ.get("SARA_API_BASE_URL")
        or os.environ.get("NEXT_PUBLIC_API_BASE_URL")
        or ""
    ).rstrip("/")


def _review_licencee_name():
    return (
        request.args.get("licenceeName")
        or request.args.get("licenseeName")
        or os.environ.get("SARA_REVIEWS_LICENCEE_NAME")
        or os.environ.get("SARA_LICENSEE_NAME")
        or ""
    ).strip()


def _external_api_headers(content_type=None):
    headers = {"Accept": "application/json"}
    auth_value = os.environ.get("SARA_API_AUTH_VALUE", "").strip()
    auth_header = os.environ.get("SARA_API_AUTH_HEADER", "").strip()
    bearer_token = os.environ.get("SARA_API_BEARER_TOKEN", "").strip()
    api_key = os.environ.get("SARA_API_KEY", "").strip()
    incoming_auth = request.headers.get("Authorization", "").strip()

    if content_type:
        headers["Content-Type"] = content_type

    if auth_value:
        headers[auth_header or "Authorization"] = auth_value
    elif bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif api_key:
        headers[auth_header or "x-api-key"] = api_key
    elif incoming_auth:
        headers["Authorization"] = incoming_auth

    return headers


def _extract_data(payload):
    if isinstance(payload, dict):
        data = payload.get("data")
        if data is None:
            data = payload.get("Data")
        return data
    return None


def _incoming_bearer_token():
    auth = request.headers.get("Authorization", "").strip()
    if not auth.lower().startswith("bearer "):
        return ""
    return auth.split(" ", 1)[1].strip()


def _decode_jwt_claims(token):
    if not token or token.count(".") < 2:
        return {}
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
    except Exception:
        return {}


def _claim(claims, *names):
    for name in names:
        value = claims.get(name)
        if value:
            return str(value)
    return ""


def _current_user_details():
    claims = _decode_jwt_claims(_incoming_bearer_token())
    email = _claim(
        claims,
        "email",
        "Email",
        "preferred_username",
        "unique_name",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    )
    name = _claim(
        claims,
        "name",
        "Name",
        "given_name",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
    )
    user_id = _claim(
        claims,
        "sub",
        "userId",
        "UserId",
        "userID",
        "UserID",
        "id",
        "nameid",
        "oid",
        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier",
    )
    licensee = _claim(claims, "licenseeName", "licenceeName", "LicenseeName", "LicenceeName")
    practice = _claim(claims, "practiceName", "PracticeName")
    return {
        "id": user_id,
        "name": name or email or user_id,
        "email": email,
        "licenseeName": licensee,
        "practiceName": practice,
    }


def _display_user_name(user):
    if not isinstance(user, dict):
        return ""
    first_name = user.get("firstName") or user.get("FirstName") or user.get("givenName") or user.get("GivenName")
    last_name = user.get("lastName") or user.get("LastName") or user.get("surname") or user.get("Surname")
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    return (
        user.get("name")
        or user.get("Name")
        or user.get("fullName")
        or user.get("FullName")
        or full_name
        or user.get("userName")
        or user.get("UserName")
        or user.get("email")
        or user.get("Email")
        or ""
    )


def _extract_user_object(payload):
    user = _extract_data(payload) or payload
    if isinstance(user, dict):
        for key in ("user", "User", "profile", "Profile", "userProfile", "UserProfile"):
            nested = user.get(key)
            if isinstance(nested, dict):
                return nested
    return user


def _display_user_name_without_email(user):
    if not isinstance(user, dict):
        return ""
    email = str(user.get("email") or user.get("Email") or "").strip().lower()
    name = str(_display_user_name(user) or "").strip()
    if name and name.lower() != email:
        return name
    return ""


def _fetch_user_lookup(api_base, headers, licencee_name):
    cache_key = (api_base, licencee_name, headers.get("Authorization", ""), headers.get("x-api-key", ""))
    if cache_key in USER_LOOKUP_CACHE:
        return USER_LOOKUP_CACHE[cache_key]

    payload = {}
    if licencee_name:
        payload["licenseeName"] = licencee_name

    req = urllib.request.Request(
        f"{api_base}/api/Users/Search",
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )

    lookup = {}
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            users_payload = json.loads(resp.read().decode("utf-8"))
        for user in _extract_data(users_payload) or []:
            if not isinstance(user, dict):
                continue
            user_id = str(user.get("id") or user.get("Id") or "").strip()
            name = _display_user_name_without_email(user)
            if user_id and name:
                lookup[user_id] = name
    except Exception:
        app.logger.exception("user lookup API failed")

    USER_LOOKUP_CACHE[cache_key] = lookup
    return lookup


def _fetch_user_detail_name(api_base, headers, user_id):
    user_id = str(user_id or "").strip()
    if not user_id:
        return ""

    cache_key = (api_base, user_id, headers.get("Authorization", ""), headers.get("x-api-key", ""))
    if cache_key in USER_DETAIL_NAME_CACHE:
        return USER_DETAIL_NAME_CACHE[cache_key]

    url = f"{api_base}/api/Users/{urllib.parse.quote(user_id)}"
    req = urllib.request.Request(url, headers=headers)

    name = ""
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        user = _extract_user_object(payload)
        name = _display_user_name(user)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            app.logger.info("created-by user id not found user_id=%s", user_id)
        else:
            app.logger.warning("user detail lookup failed user_id=%s status=%s", user_id, exc.code)
    except Exception:
        app.logger.exception("user detail lookup failed user_id=%s", user_id)

    USER_DETAIL_NAME_CACHE[cache_key] = name
    return name


def _search_users(api_base, headers, licensee_name="", practice_name=""):
    payload = {}
    if licensee_name:
        payload["licenseeName"] = licensee_name
    if practice_name:
        payload["practiceName"] = practice_name

    req = urllib.request.Request(
        f"{api_base}/api/Users/Search",
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return _extract_data(json.loads(resp.read().decode("utf-8"))) or []


def _enrich_reviews_with_usernames(body, api_base, headers, licencee_name):
    try:
        payload = json.loads(body)
    except Exception:
        return body

    rows = _extract_data(payload)
    if not isinstance(rows, list):
        return body

    created_by_ids = {
        str((row or {}).get("createdBy") or (row or {}).get("CreatedBy") or "").strip()
        for row in rows
        if isinstance(row, dict)
    }
    created_by_ids.discard("")
    if not created_by_ids:
        return body

    users = _fetch_user_lookup(api_base, headers, licencee_name)

    for row in rows:
        if not isinstance(row, dict):
            continue
        created_by = str(row.get("createdBy") or row.get("CreatedBy") or "").strip()
        username = users.get(created_by) if users else ""
        if not username:
            username = _fetch_user_detail_name(api_base, headers, created_by)
        if username:
            row["createdByUserName"] = username

    return json.dumps(payload)


def _fetch_user_detail_response(api_base, user_id):
    url = f"{api_base}/api/Users/{urllib.parse.quote(user_id)}"
    req = urllib.request.Request(url, headers=_external_api_headers())

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return Response(
                body,
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        request_id = uuid.uuid4().hex
        message = _upstream_error_message(body, "Could not load user profile.")
        if exc.code == 404:
            app.logger.info(
                "user detail API not found request_id=%s user_id=%s message=%s",
                request_id,
                user_id,
                message,
            )
        else:
            app.logger.warning(
                "user detail API failed request_id=%s status=%s message=%s",
                request_id,
                exc.code,
                message,
            )
        return _error("user_detail_failed", message, exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("user detail API failed request_id=%s", request_id)
        return _error("user_detail_failed", "Could not load user profile.", 502, request_id)


def _proxy_json_request(path, payload, method="POST", timeout=20):
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )
    url = f"{api_base}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=_external_api_headers("application/json"),
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return Response(
                body,
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            return Response(
                body,
                status=exc.code,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
        request_id = uuid.uuid4().hex
        app.logger.exception("JSON proxy failed path=%s request_id=%s status=%s", path, request_id, exc.code)
        return _error("api_proxy_failed", f"Could not complete request to {path}.", exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("JSON proxy failed path=%s request_id=%s", path, request_id)
        return _error("api_proxy_failed", f"Could not complete request to {path}.", 502, request_id)


@app.get("/api/sara/users/me")
def sara_current_user_detail():
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    current_user = _current_user_details()
    email = (
        request.args.get("email")
        or current_user.get("email")
        or ""
    ).strip().lower()
    user_id = current_user.get("id", "").strip()

    if not user_id:
        headers = _external_api_headers()
        licensee_name = (
            current_user.get("licenseeName")
            or request.args.get("licenseeName")
            or os.environ.get("SARA_REVIEWS_LICENCEE_NAME")
            or os.environ.get("SARA_LICENSEE_NAME")
            or ""
        ).strip()
        practice_name = (
            current_user.get("practiceName")
            or request.args.get("practiceName")
            or os.environ.get("SARA_PRACTICE_NAME")
            or os.environ.get("SARA_DEFAULT_PRACTICE_NAME")
            or ""
        ).strip()

        try:
            users = _search_users(api_base, headers, licensee_name, practice_name)
        except Exception:
            request_id = uuid.uuid4().hex
            app.logger.exception("current user search failed request_id=%s", request_id)
            return _error("user_lookup_failed", "Could not search for the current user profile.", 502, request_id)

        match = None
        if email:
            match = next(
                (
                    user for user in users
                    if str(user.get("email") or user.get("Email") or "").strip().lower() == email
                ),
                None,
            )
        if match is None and len(users) == 1:
            match = users[0]
        if not match:
            return _error(
                "user_id_not_found",
                "Your login token did not include a user id, and SARA could not match your email to a user profile.",
                404,
            )
        user_id = str(match.get("id") or match.get("Id") or "").strip()

    if not user_id:
        return _error("user_id_not_found", "SARA could not determine your user id.", 404)

    return _fetch_user_detail_response(api_base, user_id)


@app.get("/api/sara/users/<user_id>")
def sara_user_detail(user_id):
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    return _fetch_user_detail_response(api_base, user_id)


def _escape_multipart_value(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _encode_multipart(fields, files):
    boundary = f"----sara-{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields:
        if value is None or value == "":
            continue
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{_escape_multipart_value(name)}"\r\n\r\n'.encode("utf-8")
        )
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, filename, content_type, data in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{_escape_multipart_value(field_name)}"; '
                f'filename="{_escape_multipart_value(filename)}"\r\n'
            ).encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type or 'application/octet-stream'}\r\n\r\n".encode("utf-8"))
        body.extend(data)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


@app.post("/api/sara/reviews/create")
@app.route("/api/sara/reviews/create", methods=["OPTIONS"])
def sara_create_review():
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())

    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    current_user = _current_user_details()
    form = request.form
    licensee_name = (
        form.get("licenseeName")
        or current_user.get("licenseeName")
        or os.environ.get("SARA_REVIEWS_LICENCEE_NAME")
        or os.environ.get("SARA_LICENSEE_NAME")
        or ""
    ).strip()
    practice_name = (
        form.get("practiceName")
        or current_user.get("practiceName")
        or os.environ.get("SARA_PRACTICE_NAME")
        or os.environ.get("SARA_DEFAULT_PRACTICE_NAME")
        or ""
    ).strip()

    if not licensee_name:
        return _error("missing_licensee", "licenseeName is required to create a SARA review.", 400)
    if not practice_name:
        return _error(
            "missing_practice",
            "practiceName is required to create a SARA review. Open your profile or log in again so SARA can load your user details.",
            400,
        )

    created_at = form.get("createdDateTime") or datetime.now(timezone.utc).isoformat()
    creator = form.get("creator") or current_user.get("id") or current_user.get("name") or current_user.get("email")
    adviser_email = (form.get("adviserEmail") or "").strip()
    adviser = (form.get("adviser") or form.get("adviserName") or "").strip()

    review_type = form.get("reviewType") or "SOA Pre-Vet"
    fields = [
        ("id", form.get("id")),
        ("createdDateTime", created_at),
        ("creator", creator),
        ("adviser", adviser),
        ("adviserEmail", adviser_email),
        ("clientName", form.get("clientName") or "Unknown client"),
        ("licenseeName", licensee_name),
        ("practiceName", practice_name),
        ("soaId", form.get("soaId")),
        ("reviewType", review_type),
    ]
    prompts = form.getlist("prompts") + form.getlist("Prompts")
    if not prompts:
        prompts = _default_prompts_for_review_type(review_type)
    for prompt in prompts:
        fields.append(("Prompts", prompt))

    for key in form.keys():
        lower_key = key.lower()
        if lower_key.startswith("conversations[") or lower_key.startswith("conversations."):
            for value in form.getlist(key):
                fields.append((key, value))

    upload_files = []
    for uploaded in request.files.getlist("files"):
        upload_files.append(
            (
                "files",
                uploaded.filename or "document",
                uploaded.mimetype or "application/octet-stream",
                uploaded.read(),
            )
        )

    if not upload_files:
        return _error("missing_files", "At least one file is required to create a SARA review.", 400)

    body, content_type = _encode_multipart(fields, upload_files)
    app.logger.info(
        "creating SARA review licensee=%s practice=%s client=%s adviser=%s files=%s",
        licensee_name,
        practice_name,
        form.get("clientName") or "Unknown client",
        adviser,
        len(upload_files),
    )
    req = urllib.request.Request(
        f"{api_base}/api/Sara",
        data=body,
        headers=_external_api_headers(content_type),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            response_body = resp.read().decode("utf-8")
            return Response(
                response_body,
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        request_id = uuid.uuid4().hex
        message = _upstream_error_message(body, "Could not create SARA review.")
        details = _upstream_error_details(body)
        details["upstreamHttpStatus"] = exc.code
        app.logger.exception(
            "create SARA review failed request_id=%s status=%s message=%s body=%s",
            request_id,
            exc.code,
            message,
            body[:1000],
        )
        return _error("create_review_failed", message, exc.code, request_id, details)
    except Exception as exc:
        request_id = uuid.uuid4().hex
        message = f"Could not reach SARA review API ({exc.__class__.__name__}: {str(exc)[:180]})."
        app.logger.exception("create SARA review failed request_id=%s message=%s", request_id, message)
        return _error("create_review_failed", message, 502, request_id)


@app.post("/api/sara/login")
@app.route("/api/sara/login", methods=["OPTIONS"])
def sara_login():
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())

    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("invalid_request", "Request body must be a JSON object.", 400)

    url = f"{api_base}/api/Users/Login"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_external_api_headers("application/json"),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return Response(
                body,
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            return Response(
                body,
                status=exc.code,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
        request_id = uuid.uuid4().hex
        app.logger.exception("login API failed request_id=%s status=%s", request_id, exc.code)
        return _error("login_failed", "Login failed.", exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("login API failed request_id=%s", request_id)
        return _error("login_failed", "Login could not be completed.", 502, request_id)


@app.get("/api/sara/checks")
def sara_checks():
    review_type = request.args.get("reviewType") or request.args.get("review_type")
    return _json({"data": get_checks(review_type), "status": True})


@app.post("/api/sara/client-profiles/search")
@app.route("/api/sara/client-profiles/search", methods=["OPTIONS"])
def sara_client_profile_search():
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("invalid_request", "Request body must be a JSON object.", 400)
    return _proxy_json_request("/api/ClientProfiles/SearchClientProfile", payload, timeout=30)


@app.post("/api/sara/client-profiles")
@app.route("/api/sara/client-profiles", methods=["OPTIONS"])
def sara_client_profile_create():
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error("invalid_request", "Request body must be a JSON object.", 400)
    return _proxy_json_request("/api/ClientProfiles", payload, timeout=30)


@app.get("/api/sara/advisers")
def sara_advisers():
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )
    params = {}
    for key in ("licenseeName", "practiceName", "id"):
        value = request.args.get(key, "").strip()
        if value:
            params[key] = value
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{api_base}/api/Advisers{query}"
    req = urllib.request.Request(url, headers=_external_api_headers())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return Response(
                body,
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            return Response(
                body,
                status=exc.code,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
        request_id = uuid.uuid4().hex
        app.logger.exception("advisers API failed request_id=%s status=%s", request_id, exc.code)
        return _error("advisers_failed", "Could not load advisers.", exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("advisers API failed request_id=%s", request_id)
        return _error("advisers_failed", "Could not load advisers.", 502, request_id)


@app.get("/api/sara/reviews")
def sara_reviews():
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    params = {}
    licencee_name = _review_licencee_name()
    if licencee_name:
        params["licenceeName"] = licencee_name

    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{api_base}/api/Sara/Reviews{query}"
    headers = _external_api_headers()
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            body = _enrich_reviews_with_usernames(body, api_base, headers, licencee_name)
            return Response(
                body,
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        request_id = uuid.uuid4().hex
        app.logger.exception(
            "reviews API failed request_id=%s status=%s url=%s",
            request_id,
            exc.code,
            url,
        )
        message = "Could not load SARA reviews."
        if exc.code == 401:
            message = (
                "The SARA Reviews API rejected the request as unauthorised. "
                "Check the SARA_API_AUTH_* settings or API key."
            )
        return _error("reviews_failed", message, exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("reviews API failed request_id=%s url=%s", request_id, url)
        return _error("reviews_failed", "Could not load SARA reviews.", 502, request_id)


@app.get("/api/sara/observations")
def sara_observations():
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    params = {}
    licencee_name = _review_licencee_name()
    if licencee_name:
        params["licenceeName"] = licencee_name

    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{api_base}/api/Sara/Observations{query}"
    headers = _external_api_headers()
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            body = _enrich_reviews_with_usernames(body, api_base, headers, licencee_name)
            return Response(
                body,
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        request_id = uuid.uuid4().hex
        app.logger.exception(
            "observations API failed request_id=%s status=%s url=%s",
            request_id,
            exc.code,
            url,
        )
        message = "Could not load SARA observations."
        if exc.code == 401:
            message = (
                "The SARA Observations API rejected the request as unauthorised. "
                "Check the SARA_API_AUTH_* settings or API key."
            )
        return _error("observations_failed", message, exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("observations API failed request_id=%s url=%s", request_id, url)
        return _error("observations_failed", "Could not load SARA observations.", 502, request_id)


@app.route("/api/sara/reviews/<review_id>", methods=["DELETE", "OPTIONS"])
def sara_delete_review(review_id):
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())

    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    practice_name = (
        request.args.get("practiceName")
        or os.environ.get("SARA_PRACTICE_NAME")
        or os.environ.get("SARA_DEFAULT_PRACTICE_NAME")
        or ""
    ).strip()
    params = {"practiceName": practice_name} if practice_name else {}
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{api_base}/api/Sara/{urllib.parse.quote(review_id)}{query}"
    req = urllib.request.Request(url, headers=_external_api_headers(), method="DELETE")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return Response(
                body or json.dumps({"status": True}),
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            return Response(
                body,
                status=exc.code,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
        request_id = uuid.uuid4().hex
        app.logger.exception("delete SARA review failed request_id=%s status=%s", request_id, exc.code)
        return _error("delete_review_failed", "Could not delete SARA review.", exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("delete SARA review failed request_id=%s", request_id)
        return _error("delete_review_failed", "Could not delete SARA review.", 502, request_id)


@app.route("/api/sara/reviews/<review_id>", methods=["PATCH"])
def sara_update_review(review_id):
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _error("invalid_request", "Request body must be a JSON object.", 400)

    practice_name = (
        payload.get("practiceName")
        or request.args.get("practiceName")
        or os.environ.get("SARA_PRACTICE_NAME")
        or os.environ.get("SARA_DEFAULT_PRACTICE_NAME")
        or ""
    ).strip()
    if not practice_name:
        return _error("missing_practice", "practiceName is required to update a SARA review.", 400)

    update_payload = {
        "reviewStatus": str(payload.get("reviewStatus") or "").strip(),
        "practiceName": practice_name,
        "adviserName": str(payload.get("adviserName") or "").strip(),
        "clientName": str(payload.get("clientName") or "").strip(),
    }
    url = f"{api_base}/api/Sara/{urllib.parse.quote(review_id)}"
    req = urllib.request.Request(
        url,
        data=json.dumps(update_payload).encode("utf-8"),
        headers=_external_api_headers("application/json"),
        method="PATCH",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return Response(
                body or json.dumps({"status": True, "data": True}),
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            return Response(
                body,
                status=exc.code,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
        request_id = uuid.uuid4().hex
        app.logger.exception("update SARA review failed request_id=%s status=%s", request_id, exc.code)
        return _error("update_review_failed", "Could not update SARA review.", exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("update SARA review failed request_id=%s", request_id)
        return _error("update_review_failed", "Could not update SARA review.", 502, request_id)


@app.route("/api/sara/reviews/<review_id>/status", methods=["PATCH"])
def sara_update_review_status(review_id):
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _error("invalid_request", "Request body must be a JSON object.", 400)

    practice_name = (
        payload.get("practiceName")
        or request.args.get("practiceName")
        or os.environ.get("SARA_PRACTICE_NAME")
        or os.environ.get("SARA_DEFAULT_PRACTICE_NAME")
        or ""
    ).strip()
    if not practice_name:
        return _error("missing_practice", "practiceName is required to update SARA review status.", 400)

    update_payload = {
        "reviewStatus": str(payload.get("reviewStatus") or "").strip(),
        "practiceName": practice_name,
    }
    url = f"{api_base}/api/Sara/{urllib.parse.quote(review_id)}/ReviewStatus"
    req = urllib.request.Request(
        url,
        data=json.dumps(update_payload).encode("utf-8"),
        headers=_external_api_headers("application/json"),
        method="PATCH",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return Response(
                body or json.dumps({"status": True, "data": True}),
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            return Response(
                body,
                status=exc.code,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
        request_id = uuid.uuid4().hex
        app.logger.exception("update SARA review status failed request_id=%s status=%s", request_id, exc.code)
        return _error("update_review_status_failed", "Could not update SARA review status.", exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("update SARA review status failed request_id=%s", request_id)
        return _error("update_review_status_failed", "Could not update SARA review status.", 502, request_id)


@app.route("/api/sara/reviews/<review_id>/download", methods=["POST", "OPTIONS"])
def sara_download_review(review_id):
    if request.method == "OPTIONS":
        return Response(status=204, headers=_cors_headers())

    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _error("invalid_request", "Request body must be a JSON object.", 400)

    practice_name = (
        payload.get("practiceName")
        or request.args.get("practiceName")
        or os.environ.get("SARA_PRACTICE_NAME")
        or os.environ.get("SARA_DEFAULT_PRACTICE_NAME")
        or ""
    ).strip()
    if not practice_name:
        return _error("missing_practice", "practiceName is required to download a SARA review report.", 400)

    url = f"{api_base}/api/Sara/{urllib.parse.quote(review_id)}/Download"
    req = urllib.request.Request(
        url,
        data=json.dumps({"practiceName": practice_name}).encode("utf-8"),
        headers=_external_api_headers("application/json"),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            content_type = resp.headers.get("Content-Type", "application/json")
            headers = {"Content-Type": content_type, **_cors_headers()}
            disposition = resp.headers.get("Content-Disposition")
            if disposition:
                headers["Content-Disposition"] = disposition
            return Response(body, status=resp.status, headers=headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            return Response(
                body,
                status=exc.code,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
        request_id = uuid.uuid4().hex
        app.logger.exception("download SARA review failed request_id=%s status=%s", request_id, exc.code)
        return _error("download_review_failed", "Could not download SARA review report.", exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("download SARA review failed request_id=%s", request_id)
        return _error("download_review_failed", "Could not download SARA review report.", 502, request_id)


@app.get("/api/sara/reviews/<review_id>")
def sara_review_detail(review_id):
    api_base = _external_api_base()
    if not api_base:
        return _error(
            "api_not_configured",
            "SARA_API_BASE_URL or NEXT_PUBLIC_API_BASE_URL is not configured.",
            503,
        )

    practice_name = (
        request.args.get("practiceName")
        or os.environ.get("SARA_PRACTICE_NAME")
        or os.environ.get("SARA_DEFAULT_PRACTICE_NAME")
        or ""
    ).strip()
    if not practice_name:
        return _error("missing_practice", "practiceName is required to load a SARA review.", 400)

    query = urllib.parse.urlencode({"practiceName": practice_name})
    url = f"{api_base}/api/Sara/{urllib.parse.quote(review_id)}?{query}"
    req = urllib.request.Request(url, headers=_external_api_headers())

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return Response(
                body,
                status=resp.status,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if body:
            return Response(
                body,
                status=exc.code,
                headers={"Content-Type": "application/json", **_cors_headers()},
            )
        request_id = uuid.uuid4().hex
        app.logger.exception("review detail API failed request_id=%s status=%s", request_id, exc.code)
        return _error("review_detail_failed", "Could not load SARA review.", exc.code, request_id)
    except Exception:
        request_id = uuid.uuid4().hex
        app.logger.exception("review detail API failed request_id=%s", request_id)
        return _error("review_detail_failed", "Could not load SARA review.", 502, request_id)


@app.get("/")
@app.get("/login")
@app.get("/sara")
@app.get("/dashboard")
@app.get("/upload")
@app.get("/settings")
@app.get("/result/<review_id>")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/favicon.png")
@app.get("/favicon.ico")
def favicon():
    return send_from_directory(FRONTEND_DIR, "favicon.png")


@app.post("/api/soa/prevet")
@app.route("/api/soa/prevet", methods=["OPTIONS"])
def soa_prevet():
    return _handle("soa")


@app.post("/api/roa/prevet")
@app.route("/api/roa/prevet", methods=["OPTIONS"])
def roa_prevet():
    return _handle("roa")
