"""
SARA 2.0 (standalone) - pre-vet engine.

Runs the SOA and RoA pre-vets with an OpenAI-compatible endpoint, returning the
RelianceResult shape the front-end renders.

Local development can use a repo-root .env.local file. Production should set the
same OPENAI_* values as App Service / Function App environment variables.
"""

import json
import os
from pathlib import Path

from check_catalog import render_soa_prompt

MAX_DOC_CHARS = 200_000
MAX_TOTAL_CHARS = 700_000

_client = None


def _load_env_local():
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / ".env.local",
        here.parents[1] / "env.local",
        here.parent / ".env.local",
        here.parent / "env.local",
        Path.cwd() / ".env.local",
        Path.cwd() / "env.local",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


_load_env_local()


def _get_model(role):
    role_key = f"OPENAI_{role.upper()}_INTAKE_MODEL"
    return (
        os.environ.get(role_key)
        or os.environ.get("OPENAI_SOA_INTAKE_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-5-mini"
    )


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")
        if not base_url:
            raise RuntimeError("OPENAI_BASE_URL is not set.")
        _client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
    return _client


RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "roaPermitted": {"type": "boolean"},
        "requiresComplianceReview": {"type": "boolean"},
        "summary": {"type": "string"},
        "adviserSuggestion": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "testId": {"type": "string"},
                    "question": {"type": "string"},
                    "outcome": {"type": "string", "enum": ["Pass", "Review", "Fail"]},
                    "reasoning": {"type": "string"},
                    "evidence": {"type": "string"},
                    "criteriaAssessment": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "criterion": {"type": "string"},
                                "finding": {"type": "string", "enum": ["Met", "Partly met", "Not met", "Not applicable"]},
                                "reason": {"type": "string"},
                            },
                            "required": ["criterion", "finding", "reason"],
                            "additionalProperties": False,
                        },
                    },
                    "evidenceItems": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sourceText": {"type": "string"},
                                "whyItMatters": {"type": "string"},
                            },
                            "required": ["sourceText", "whyItMatters"],
                            "additionalProperties": False,
                        },
                    },
                    "gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "recommendedAction": {"type": "string"},
                },
                "required": [
                    "testId",
                    "question",
                    "outcome",
                    "reasoning",
                    "evidence",
                    "criteriaAssessment",
                    "evidenceItems",
                    "gaps",
                    "recommendedAction",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["roaPermitted", "requiresComplianceReview", "summary", "adviserSuggestion", "findings"],
    "additionalProperties": False,
}

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "reliance_result",
        "schema": RESULT_SCHEMA,
        "strict": True,
    },
}

_BASE = """You are SARA 2.0, an AI compliance reviewer for an Australian AFSL financial-advice business (Insight Management Partners / IIP). You assess the appropriateness and disclosure of advice against the Corporations Act 2001 and the firm's audit framework - you do NOT merely check that sections exist.

Scoring scheme for every test:
- "Pass" = the obligation appears met on the evidence provided.
- "Review" = ambiguous or insufficient evidence - a human reviewer must confirm.
- "Fail" = the obligation appears not met.

Rules:
- Base findings ONLY on the documents provided. Anything not provided is "not provided" - flag it as Review, or Fail if mandatory for the role. Never invent evidence.
- Do not merely state that a heading or section exists. Test whether the content satisfies the compliance obligation.
- For every finding, provide a compliance basis that explains the facts extracted, the criteria applied, and why the result follows.
- Quote short evidence in evidenceItems.sourceText where you can; use [] if no evidence is available.
- Keep reasoning as a concise compatibility summary of the same analysis. Keep evidence as a short semicolon-separated compatibility summary of the evidenceItems.
- Use criteriaAssessment for criterion-by-criterion analysis. Use gaps for weaknesses, ambiguity, missing evidence, or residual compliance risk. Use recommendedAction for the adviser/compliance next step.
- roaPermitted/eligibility is true only if NO test failed.
- requiresComplianceReview is true if ANY test is Review or Fail.
- adviserSuggestion should give concrete remediation coaching for concerns or low-level tidy-up observations.
- Be precise and conservative; a false Pass is worse than a cautious Review.
"""

_ROLE_PROMPTS = {
    "roa": _BASE + """
ROLE: RoA pre-vet - decide whether this Record of Advice may rely on the prior SOA under s946B as further advice. Run these tests, one finding each, in order:
RA-01 Is this further advice suited to an RoA? Pass if classified as further advice; else Review.
RA-02 Can the prior SOA it relies on be located and is it valid? Fail if no prior Final/Signed SOA is provided dated before the RoA.
RA-03 Have the client's relevant personal circumstances changed significantly since the SOA?
RA-04 Does the further advice stay within the basis and product scope of the SOA?
RA-05 Does the RoA record the required content and is it retained? Review if content is thin or absent.
Set summary to a one-line determination.
""",
    "soa": _BASE + "\n" + render_soa_prompt(),
}


def _truncate(text, limit):
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def _build_user_text(role, payload):
    lines = []
    if role == "roa":
        lines.append(f"Classified as further advice: {payload.get('classifiedAsFurtherAdvice', True)}")

    docs = payload.get("documents") or []
    if not docs and payload.get("content"):
        docs = [{"type": "roa_vetted", "name": "Record of Advice", "content": payload["content"]}]

    if not docs:
        lines.append("\nNo documents were provided.")
    else:
        lines.append("\nDocuments provided (type - name):")
        budget = MAX_TOTAL_CHARS
        for d in docs:
            if budget <= 0:
                body = "[omitted - total size budget reached]"
            else:
                body = _truncate(d.get("content", ""), min(MAX_DOC_CHARS, budget))
            budget -= len(body)
            lines.append(
                f"\n### [{d.get('type', 'other')}] {d.get('name', '(unnamed)')}\n"
                f"{body or '[no text extracted]'}"
            )

    lines.append("\nReturn the structured pre-vet result.")
    return "\n".join(lines)


def build_system_prompt(role):
    return _ROLE_PROMPTS.get(role, _ROLE_PROMPTS["soa"])


def run_prevet(role, payload):
    if role not in _ROLE_PROMPTS:
        role = "soa"
    client = _get_client()
    resp = client.chat.completions.create(
        model=_get_model(role),
        messages=[
            {"role": "system", "content": build_system_prompt(role)},
            {"role": "user", "content": _build_user_text(role, payload)},
        ],
        response_format=RESPONSE_FORMAT,
        max_completion_tokens=16000,
    )
    text = resp.choices[0].message.content or ""
    return json.loads(text)
