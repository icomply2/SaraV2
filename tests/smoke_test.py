"""
Tiny smoke tests for SARA 2.0 packaging and request handling.

These tests do not call OpenAI. They verify that the Flask and Azure Functions
entrypoints import, route requests into run_prevet with the expected role, and
return the shared JSON error shape for invalid payloads.
"""

import importlib
import importlib.util
import io
import json
import os
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API_DIR))


def sample_result():
    return {
        "roaPermitted": True,
        "requiresComplianceReview": False,
        "summary": "PASS - Smoke test.",
        "adviserSuggestion": "",
        "findings": [],
    }


def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def assert_in(needle, haystack, label):
    if needle not in haystack:
        raise AssertionError(f"{label}: expected {needle!r} in {haystack!r}")


def install_flask_stub():
    flask_module = types.ModuleType("flask")

    class Logger:
        def exception(self, *args, **kwargs):
            return None

    class Flask:
        def __init__(self, *args, **kwargs):
            self.logger = Logger()

        def get(self, *args, **kwargs):
            return self.route(*args, **kwargs)

        def post(self, *args, **kwargs):
            return self.route(*args, **kwargs)

        def route(self, *args, **kwargs):
            def decorator(fn):
                return fn

            return decorator

    class Response:
        def __init__(self, body="", status=200, headers=None):
            self.body = body or ""
            self.status_code = status
            self.headers = headers or {}

        def get_data(self):
            if isinstance(self.body, bytes):
                return self.body
            return str(self.body).encode("utf-8")

    class Request:
        method = "POST"
        payload = {}

        def get_json(self, silent=False):
            return self.payload

    def send_from_directory(*args, **kwargs):
        return Response("")

    flask_module.Flask = Flask
    flask_module.Response = Response
    flask_module.request = Request()
    flask_module.send_from_directory = send_from_directory
    sys.modules["flask"] = flask_module


def install_azure_functions_stub():
    azure_module = types.ModuleType("azure")
    functions_module = types.ModuleType("azure.functions")

    class AuthLevel:
        FUNCTION = "FUNCTION"

    class FunctionApp:
        def __init__(self, http_auth_level=None):
            self.http_auth_level = http_auth_level
            self.routes = []

        def route(self, route=None, methods=None):
            def decorator(fn):
                self.routes.append({"route": route, "methods": methods, "fn": fn})
                return fn

            return decorator

    class HttpRequest:
        pass

    class HttpResponse:
        def __init__(self, body="", status_code=200, headers=None):
            self.body = body or ""
            self.status_code = status_code
            self.headers = headers or {}

        def get_body(self):
            if isinstance(self.body, bytes):
                return self.body
            return str(self.body).encode("utf-8")

    functions_module.AuthLevel = AuthLevel
    functions_module.FunctionApp = FunctionApp
    functions_module.HttpRequest = HttpRequest
    functions_module.HttpResponse = HttpResponse
    azure_module.functions = functions_module
    sys.modules["azure"] = azure_module
    sys.modules["azure.functions"] = functions_module


class FakeHttpRequest:
    def __init__(self, payload, method="POST"):
        self.payload = payload
        self.method = method

    def get_json(self):
        return self.payload


def smoke_engine_request_text():
    sara_engine = importlib.import_module("sara_engine")
    check_catalog = importlib.import_module("check_catalog")
    catalogue_status = check_catalog.validate_catalogue()
    assert_equal(catalogue_status["count"], 17, "soa check catalogue count")
    assert_equal(catalogue_status["uniqueIndexes"], True, "soa check catalogue unique indexes")
    assert_equal(catalogue_status["uniqueTestIds"], True, "soa check catalogue unique test ids")
    assert_equal(catalogue_status["missingFields"], [], "soa check catalogue required fields")

    system_prompt = sara_engine.build_system_prompt("soa")
    assert_in("SOA-01", system_prompt, "soa prompt first schema check")
    assert_in("SOA-17", system_prompt, "soa prompt last schema check")
    assert_in("Pass criteria:", system_prompt, "soa prompt pass criteria")
    assert_in("Review criteria:", system_prompt, "soa prompt review criteria")
    assert_in("Fail criteria:", system_prompt, "soa prompt fail criteria")
    assert_in("criteriaAssessment", system_prompt, "soa prompt structured criteria field")
    assert_in("Do not merely state that a heading or section exists", system_prompt, "soa prompt anti-heading-only instruction")

    finding_schema = sara_engine.RESULT_SCHEMA["properties"]["findings"]["items"]
    for field in ("criteriaAssessment", "evidenceItems", "gaps", "recommendedAction"):
        if field not in finding_schema["required"]:
            raise AssertionError(f"finding schema requires {field}")

    text = sara_engine._build_user_text(
        "roa",
        {
            "classifiedAsFurtherAdvice": False,
            "documents": [
                {
                    "type": "prior_soa",
                    "name": "Prior SOA.pdf",
                    "content": "Client objective text",
                }
            ],
        },
    )

    assert_in("Classified as further advice: False", text, "roa classification")
    assert_in("### [prior_soa] Prior SOA.pdf", text, "document header")
    assert_in("Client objective text", text, "document content")


def smoke_flask_entrypoint():
    use_flask_stub = importlib.util.find_spec("flask") is None
    if use_flask_stub:
        install_flask_stub()

    flask_module = importlib.import_module("app")
    calls = []

    def fake_run_prevet(role, payload):
        calls.append((role, payload))
        return sample_result()

    original = flask_module.run_prevet
    original_urlopen = flask_module.urllib.request.urlopen
    flask_module.run_prevet = fake_run_prevet
    try:
        if use_flask_stub:
            flask_module.request.method = "POST"
            flask_module.request.payload = {"documents": []}
            response = flask_module.soa_prevet()
            body = json.loads(response.get_data().decode("utf-8"))
            assert_equal(response.status_code, 200, "flask soa status")
            assert_equal(calls[0][0], "soa", "flask soa role")
            assert_equal(body["summary"], "PASS - Smoke test.", "flask soa result")

            flask_module.request.payload = []
            bad = flask_module.soa_prevet()
            bad_body = json.loads(bad.get_data().decode("utf-8"))
            assert_equal(bad.status_code, 400, "flask invalid status")
            assert_equal(bad_body["error"], "invalid_request", "flask invalid error")
        else:
            client = flask_module.app.test_client()
            response = client.post("/api/soa/prevet", json={"documents": []})
            assert_equal(response.status_code, 200, "flask soa status")
            assert_equal(calls[0][0], "soa", "flask soa role")
            assert_equal(response.get_json()["summary"], "PASS - Smoke test.", "flask soa result")

            bad = client.post("/api/soa/prevet", data="[]", content_type="application/json")
            assert_equal(bad.status_code, 400, "flask invalid status")
            assert_equal(bad.get_json()["error"], "invalid_request", "flask invalid error")

            for route in ("/login", "/dashboard", "/upload", "/settings", "/result/review-1"):
                page = client.get(route)
                assert_equal(page.status_code, 200, f"flask frontend route {route}")
                assert_in(b"SARA", page.data, f"flask frontend content {route}")

            class FakeUpstreamResponse:
                def __init__(self, body, headers=None):
                    self.body = body
                    self.headers = headers or {"Content-Type": "application/json"}

                status = 200

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

                def read(self):
                    return json.dumps(self.body).encode("utf-8")

            upstream_requests = []

            def fake_urlopen(req, timeout=20):
                upstream_requests.append(req)
                if req.full_url.endswith("/api/Users/Login"):
                    return FakeUpstreamResponse(
                        {
                            "statusCode": 200,
                            "status": True,
                            "data": {
                                "jwtToken": "smoke-jwt",
                                "requiresTwoFactorAuthentication": False,
                            },
                            "message": "",
                        }
                    )
                if req.full_url.endswith("/api/Users/Search"):
                    return FakeUpstreamResponse({"data": [{"id": "user-1", "email": "smoke@example.com"}]})
                if req.full_url.endswith("/api/Users/user-1"):
                    return FakeUpstreamResponse(
                        {
                            "data": {
                                "id": "user-1",
                                "name": "Smoke User",
                                "email": "smoke@example.com",
                                "practice": {"id": "practice-1", "name": "Smoke Practice"},
                                "licensee": {"id": "licensee-1", "name": "Smoke Licensee"},
                            }
                        }
                    )
                if req.full_url.endswith("/api/ClientProfiles/SearchClientProfile"):
                    return FakeUpstreamResponse(
                        {
                            "data": {
                                "items": [
                                    {
                                        "id": "client-profile-1",
                                        "practice": "Smoke Practice",
                                        "licensee": "Smoke Licensee",
                                        "client": {"name": "Smoke Client"},
                                        "adviser": {"id": "adviser-1", "name": "Smoke Adviser", "email": "adviser@example.com"},
                                    }
                                ]
                            }
                        }
                    )
                if req.full_url.endswith("/api/ClientProfiles"):
                    return FakeUpstreamResponse(
                        {
                            "data": {
                                "id": "client-profile-2",
                                "practice": "Smoke Practice",
                                "licensee": "Smoke Licensee",
                                "client": {"name": "New Smoke Client"},
                                "adviser": {"id": "adviser-1", "name": "Smoke Adviser", "email": "adviser@example.com"},
                            }
                        }
                    )
                if "/api/Advisers" in req.full_url:
                    return FakeUpstreamResponse(
                        {"data": [{"id": "adviser-1", "name": "Smoke Adviser", "email": "adviser@example.com"}]}
                    )
                if req.full_url.endswith("/api/Sara") and req.get_method() == "POST":
                    return FakeUpstreamResponse(
                        {
                            "statusCode": 200,
                            "status": True,
                            "data": {"saraReview": {"id": "review-1", "clientName": "Smoke Client"}},
                            "message": "",
                        }
                    )
                if "/api/Sara/review-1" in req.full_url and req.get_method() == "GET":
                    return FakeUpstreamResponse({"data": {"id": "review-1", "clientName": "Smoke Client"}})
                if "/api/Sara/review-1/ReviewStatus" in req.full_url and req.get_method() == "PATCH":
                    return FakeUpstreamResponse({"status": True, "data": True})
                if "/api/Sara/review-1/Download" in req.full_url and req.get_method() == "POST":
                    return FakeUpstreamResponse(
                        {
                            "status": True,
                            "data": {
                                "fileName": "smoke-report.docx",
                                "contentType": "text/plain",
                                "content": "U21va2UgcmVwb3J0",
                            },
                        }
                    )
                if "/api/Sara/review-1" in req.full_url and "/ReviewStatus" not in req.full_url and req.get_method() == "PATCH":
                    return FakeUpstreamResponse({"status": True, "data": True})
                if "/api/Sara/review-1" in req.full_url and req.get_method() == "DELETE":
                    return FakeUpstreamResponse({"status": True})
                if "/api/Sara/Observations" in req.full_url:
                    return FakeUpstreamResponse(
                        {
                            "data": [
                                {
                                    "id": "observation-1",
                                    "clientName": "Smoke Client",
                                    "auditQuestion": "Smoke observation",
                                    "createdBy": "user-1",
                                }
                            ]
                        }
                    )
                return FakeUpstreamResponse(
                    {"data": [{"id": "review-1", "clientName": "Smoke Client", "createdBy": "user-1"}]}
                )

            flask_module.urllib.request.urlopen = fake_urlopen
            old_env = {
                "SARA_API_BASE_URL": os.environ.get("SARA_API_BASE_URL"),
                "SARA_API_AUTH_HEADER": os.environ.get("SARA_API_AUTH_HEADER"),
                "SARA_API_AUTH_VALUE": os.environ.get("SARA_API_AUTH_VALUE"),
            }
            os.environ["SARA_API_BASE_URL"] = "https://example.invalid"
            os.environ["SARA_API_AUTH_HEADER"] = "Authorization"
            os.environ["SARA_API_AUTH_VALUE"] = "Bearer smoke-token"
            login = client.post(
                "/api/sara/login",
                json={"email": "smoke@example.com", "password": "secret"},
            )
            assert_equal(login.status_code, 200, "flask login status")
            assert_equal(login.get_json()["data"]["jwtToken"], "smoke-jwt", "flask login token")
            user = client.get(
                "/api/sara/users/user-1",
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(user.status_code, 200, "flask user detail status")
            assert_equal(user.get_json()["data"]["practice"]["name"], "Smoke Practice", "flask user practice")
            current_user = client.get(
                "/api/sara/users/me?email=smoke@example.com",
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(current_user.status_code, 200, "flask current user detail status")
            assert_equal(
                current_user.get_json()["data"]["licensee"]["name"],
                "Smoke Licensee",
                "flask current user licensee",
            )
            checks = client.get(
                "/api/sara/checks?reviewType=SOA%20Pre-Vet",
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(checks.status_code, 200, "flask checks status")
            assert_equal(len(checks.get_json()["data"]), 17, "flask checks result count")
            assert_equal(checks.get_json()["data"][0]["testId"], "SOA-01", "flask checks first test id")
            client_search = client.post(
                "/api/sara/client-profiles/search",
                json={"clientName": "Smoke", "licenseeName": "Smoke Licensee", "practiceName": "Smoke Practice"},
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(client_search.status_code, 200, "flask client profile search status")
            assert_equal(
                client_search.get_json()["data"]["items"][0]["client"]["name"],
                "Smoke Client",
                "flask client profile search result",
            )
            client_created = client.post(
                "/api/sara/client-profiles",
                json={
                    "licensee": "Smoke Licensee",
                    "practice": "Smoke Practice",
                    "client": {"name": "New Smoke Client"},
                    "adviser": {"id": "adviser-1", "name": "Smoke Adviser"},
                },
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(client_created.status_code, 200, "flask client profile create status")
            assert_equal(client_created.get_json()["data"]["id"], "client-profile-2", "flask client profile create result")
            advisers = client.get(
                "/api/sara/advisers?licenseeName=Smoke%20Licensee&practiceName=Smoke%20Practice",
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(advisers.status_code, 200, "flask advisers status")
            assert_equal(advisers.get_json()["data"][0]["name"], "Smoke Adviser", "flask advisers result")
            created = client.post(
                "/api/sara/reviews/create",
                data={
                    "licenseeName": "Smoke Licensee",
                    "practiceName": "Smoke Practice",
                    "clientName": "Smoke Client",
                    "conversations[0].promptId": "SOA-01",
                    "conversations[0].promptIndex": "1",
                    "conversations[0].auditQuestion": "Smoke audit question",
                    "conversations[0].promptRegRef": "s961B",
                    "conversations[0].content": "Smoke finding content",
                    "conversations[0].passfail": "Review",
                    "files": (io.BytesIO(b"smoke document"), "smoke-soa.txt"),
                },
                headers={"Authorization": "Bearer smoke-token"},
                content_type="multipart/form-data",
            )
            assert_equal(created.status_code, 200, "flask create review status")
            assert_equal(
                created.get_json()["data"]["saraReview"]["id"],
                "review-1",
                "flask create review result",
            )
            reviews = client.get("/api/sara/reviews?licenceeName=Smoke")
            assert_equal(reviews.status_code, 200, "flask reviews status")
            assert_equal(reviews.get_json()["data"][0]["clientName"], "Smoke Client", "flask reviews result")
            assert_equal(
                reviews.get_json()["data"][0]["createdByUserName"],
                "Smoke User",
                "flask reviews created by username",
            )
            observations = client.get("/api/sara/observations?licenceeName=Smoke")
            assert_equal(observations.status_code, 200, "flask observations status")
            assert_equal(
                observations.get_json()["data"][0]["auditQuestion"],
                "Smoke observation",
                "flask observations result",
            )
            assert_equal(
                observations.get_json()["data"][0]["createdByUserName"],
                "Smoke User",
                "flask observations created by username",
            )
            detail = client.get(
                "/api/sara/reviews/review-1?practiceName=Smoke%20Practice",
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(detail.status_code, 200, "flask review detail status")
            assert_equal(detail.get_json()["data"]["id"], "review-1", "flask review detail result")
            updated = client.patch(
                "/api/sara/reviews/review-1",
                json={
                    "reviewStatus": "Done",
                    "practiceName": "Smoke Practice",
                    "adviserName": "Smoke Adviser",
                    "clientName": "Smoke Client",
                },
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(updated.status_code, 200, "flask update review status")
            assert_equal(updated.get_json()["data"], True, "flask update review result")
            status_updated = client.patch(
                "/api/sara/reviews/review-1/status",
                json={"reviewStatus": "Done", "practiceName": "Smoke Practice"},
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(status_updated.status_code, 200, "flask update review status endpoint status")
            assert_equal(status_updated.get_json()["data"], True, "flask update review status endpoint result")
            deleted = client.delete(
                "/api/sara/reviews/review-1?practiceName=Smoke%20Practice",
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(deleted.status_code, 200, "flask delete review status")
            assert_equal(deleted.get_json()["status"], True, "flask delete review result")
            parsed_error = flask_module._upstream_error_message(
                json.dumps(
                    {
                        "message": "Validation failed",
                        "modelErrors": [
                            {"fieldName": "practiceName", "errorMessage": "Practice is required"}
                        ],
                    }
                ),
                "fallback",
            )
            assert_equal(
                parsed_error,
                "practiceName: Practice is required",
                "flask upstream model error parsing",
            )
            assert_equal(
                next(req for req in upstream_requests if req.full_url.endswith("/api/Sara")).get_header("Authorization"),
                "Bearer smoke-token",
                "flask create review auth header",
            )
            create_request = next(req for req in upstream_requests if req.full_url.endswith("/api/Sara"))
            create_body = create_request.data.decode("utf-8", errors="replace")
            assert_equal(
                'name="Prompts"' in create_body,
                True,
                "flask create review prompts field",
            )
            assert_equal(
                "SOA-01 - 1 - Summary of the Advice" in create_body,
                True,
                "flask create review default prompt",
            )
            assert_equal(
                'name="conversations[0].content"' in create_body and "Smoke finding content" in create_body,
                True,
                "flask create review conversations passthrough",
            )
            assert_equal(
                'name="adviser"\r\n\r\nSmoke User' in create_body,
                False,
                "flask create review does not default adviser to current user",
            )
            patch_request = next(req for req in upstream_requests if "/api/Sara/review-1" in req.full_url and "/ReviewStatus" not in req.full_url and req.get_method() == "PATCH")
            assert_equal(
                patch_request.get_header("Authorization"),
                "Bearer smoke-token",
                "flask update review auth header",
            )
            status_patch_request = next(req for req in upstream_requests if "/api/Sara/review-1/ReviewStatus" in req.full_url)
            assert_equal(
                json.loads(status_patch_request.data.decode("utf-8"))["reviewStatus"],
                "Done",
                "flask update review status payload",
            )
            assert_equal(
                json.loads(patch_request.data.decode("utf-8"))["practiceName"],
                "Smoke Practice",
                "flask update review practice payload",
            )
            download = client.post(
                "/api/sara/reviews/review-1/download",
                json={"practiceName": "Smoke Practice"},
                headers={"Authorization": "Bearer smoke-token"},
            )
            assert_equal(download.status_code, 200, "flask download review status")
            assert_equal(download.get_json()["data"]["fileName"], "smoke-report.docx", "flask download review response")
            download_request = next(req for req in upstream_requests if "/api/Sara/review-1/Download" in req.full_url)
            assert_equal(
                json.loads(download_request.data.decode("utf-8"))["practiceName"],
                "Smoke Practice",
                "flask download review practice payload",
            )
            for key, old_value in old_env.items():
                if old_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old_value
    finally:
        flask_module.run_prevet = original
        flask_module.urllib.request.urlopen = original_urlopen


def smoke_functions_entrypoint():
    install_azure_functions_stub()
    functions_module = importlib.import_module("function_app")
    calls = []

    def fake_run_prevet(role, payload):
        calls.append((role, payload))
        return sample_result()

    original = functions_module.run_prevet
    functions_module.run_prevet = fake_run_prevet
    try:
        response = functions_module.roa_prevet(FakeHttpRequest({"documents": []}))
        body = json.loads(response.get_body().decode("utf-8"))
        assert_equal(response.status_code, 200, "functions roa status")
        assert_equal(calls[0][0], "roa", "functions roa role")
        assert_equal(body["summary"], "PASS - Smoke test.", "functions roa result")

        bad = functions_module.roa_prevet(FakeHttpRequest([]))
        bad_body = json.loads(bad.get_body().decode("utf-8"))
        assert_equal(bad.status_code, 400, "functions invalid status")
        assert_equal(bad_body["error"], "invalid_request", "functions invalid error")
    finally:
        functions_module.run_prevet = original


def main():
    smoke_engine_request_text()
    smoke_flask_entrypoint()
    smoke_functions_entrypoint()
    print("Smoke tests passed.")


if __name__ == "__main__":
    main()
