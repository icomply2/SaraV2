# SARA 2.0 - Standalone Pre-Vet

A self-contained, upload-only compliance pre-vet for SOA and RoA advice documents.
It can run two ways from the same repo:

- **Azure Web App / Flask mode**: serves `frontend/index.html` and `/api/...` from `app.py`.
- **Azure Functions mode**: serves `/api/soa/prevet` and `/api/roa/prevet` from `api/function_app.py`.

The browser extracts document text from PDF/DOCX/TXT files, sends that text to the
backend, and the backend calls your Azure OpenAI/OpenAI-compatible endpoint.

## Repo Layout

```text
sara2-standalone/
├── app.py                         # Azure Web App / Flask entrypoint
├── requirements.txt               # Web App dependencies
├── frontend/
│   └── index.html                 # Static UI
├── api/
│   ├── function_app.py            # Azure Functions entrypoint
│   ├── sara_engine.py             # Prompts + OpenAI call
│   ├── requirements.txt           # Functions dependencies
│   ├── host.json
│   ├── local.settings.json.sample
│   └── .funcignore
└── README.md
```

## Required Settings

Set these locally in `.env.local`, and in production as Azure Web App application
settings:

```env
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1
OPENAI_API_KEY=your-key
OPENAI_SOA_INTAKE_MODEL=gpt-5-mini
```

Optional:

```env
OPENAI_ROA_INTAKE_MODEL=gpt-5-mini
SARA_ALLOWED_ORIGIN=https://your-domain.example
```

For local Azure Functions, `api/local.settings.json` can contain the same values.
That file is ignored by git.

## Local Test - Web App Mode

This is the easiest local test because it serves the frontend and API from one origin.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m flask --app app run --host 127.0.0.1 --port 5000
```

Open:

```text
http://127.0.0.1:5000/
```

## Local Test - Azure Functions Mode

Requires Azure Functions Core Tools v4.

```powershell
npm install -g azure-functions-core-tools@4 --unsafe-perm true
cd api
..\.venv\Scripts\python -m pip install -r requirements.txt
func start --python
```

The endpoints are:

```text
http://127.0.0.1:7071/api/soa/prevet
http://127.0.0.1:7071/api/roa/prevet
```

When `frontend/index.html` is opened from `file://`, it automatically points to
`http://127.0.0.1:7071`.

## Azure Web App Deployment

For Azure App Service:

1. Use a Linux Web App with runtime stack **Python 3.11** or **Python 3.12**.
2. Add app settings:
   - `OPENAI_BASE_URL`
   - `OPENAI_API_KEY`
   - `OPENAI_SOA_INTAKE_MODEL`
   - optional `OPENAI_ROA_INTAKE_MODEL`
   - optional `SARA_ALLOWED_ORIGIN`
3. Use the root `requirements.txt`.
4. Use startup command:

```bash
gunicorn --bind=0.0.0.0 --timeout 300 app:app
```

On Windows App Service, prefer switching the app to Linux/Python for this repo. If
you keep a .NET Windows stack, Azure will not run this Python/Flask app as-is.

## Response Contract

Both endpoints return:

```json
{
  "roaPermitted": true,
  "requiresComplianceReview": false,
  "summary": "PASS - File Meets Requirements.",
  "adviserSuggestion": "- coaching point one\n- coaching point two",
  "findings": [
    {
      "testId": "OBJ",
      "question": "Did the adviser identify the client's objectives? (s961B(2)(a))",
      "outcome": "Pass",
      "reasoning": "...",
      "evidence": "short quote"
    }
  ]
}
```

## Notes

- `.env.local` and `api/local.settings.json` are ignored so API keys do not get committed.
- Documents are not persisted by this app; extracted text is forwarded to the configured LLM endpoint for assessment.
- SARA 2.0 is a first-pass aid and does not replace adviser judgement or compliance sign-off.
