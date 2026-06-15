# SARA 2.0 — Standalone Pre-Vet (for icomply2app.com.au/sara)

A self-contained, upload-only compliance pre-vet that any adviser can use from the iComply2
website. **No client ID, entity ID or adviser ID** — the adviser picks a check, drops in the
file(s), and runs. Two checks are included:

- **SOA pre-vet** — appropriateness & disclosure of a Statement of Advice (13 questions across
  s961B / s961G, fees, PDS, OFA, credit).
- **RoA pre-vet** — whether a Record of Advice may rely on a prior SOA under s946B (RA-01..RA-05).

This runs **side by side with the existing SARA** (the Azure AI Search–integrated version).
Badge the existing one "SARA" and this one "SARA 2.0" in your site navigation. This version never
touches the client database — it only reads the files the adviser uploads, runs the check, and
returns the result. Nothing is stored.

```
sara2-standalone/
├── frontend/
│   └── index.html          ← the whole UI, one file, no build step
├── api/                    ← Azure Functions app (Python v2 model)
│   ├── function_app.py     ← /api/soa/prevet and /api/roa/prevet
│   ├── sara_engine.py      ← prompts + Claude call + Key Vault key lookup
│   ├── requirements.txt
│   ├── host.json
│   ├── local.settings.json.sample
│   └── .funcignore
└── README.md
```

## Architecture

```
  Adviser's browser                Azure Function (api/)              Azure Key Vault
 ┌──────────────────┐   POST      ┌──────────────────────┐  managed   ┌────────────────┐
 │ index.html       │ ─ JSON ───▶ │ /api/soa|roa/prevet  │  identity  │ anthropic-     │
 │ (extracts text   │             │  run_prevet()        │ ─ get ───▶ │ api-key secret │
 │  from PDF/DOCX)  │ ◀─ result ─ │  → Claude (Opus 4.8) │            └────────────────┘
 └──────────────────┘             └──────────┬───────────┘
                                             │ HTTPS
                                             ▼
                                    Anthropic API
```

The Anthropic key is **never** in the browser or in the code. The Function reads it from Key
Vault using the Function App's managed identity.

---

## 1. Deploy the Function (`api/`)

### One-time Azure setup

```bash
# pick names that suit your tenant
RG=rg-icomply2
LOC=australiaeast
KV=kv-icomply2
FUNC=sara2-func
STG=sara2func$RANDOM        # storage account, lowercase, globally unique

az group create -n $RG -l $LOC
az storage account create -n $STG -g $RG -l $LOC --sku Standard_LRS

# Key Vault + store the Anthropic key as a secret
az keyvault create -n $KV -g $RG -l $LOC
az keyvault secret set --vault-name $KV -n anthropic-api-key --value "sk-ant-XXXX"

# Python Functions app (Linux, consumption plan), v4 runtime
az functionapp create -n $FUNC -g $RG -s $STG \
  --consumption-plan-location $LOC \
  --runtime python --runtime-version 3.11 --functions-version 4 --os-type Linux

# give the Function a managed identity and let it read Key Vault secrets
az functionapp identity assign -n $FUNC -g $RG
PRINCIPAL=$(az functionapp identity show -n $FUNC -g $RG --query principalId -o tsv)
KV_ID=$(az keyvault show -n $KV --query id -o tsv)
az role assignment create --assignee $PRINCIPAL \
  --role "Key Vault Secrets User" --scope $KV_ID
# (if your vault uses access policies instead of RBAC:)
# az keyvault set-policy -n $KV --object-id $PRINCIPAL --secret-permissions get

# tell the Function where the vault is (it reads the key at runtime via managed identity)
az functionapp config appsettings set -n $FUNC -g $RG --settings \
  KEY_VAULT_URI="https://$KV.vault.azure.net/" \
  ANTHROPIC_SECRET_NAME="anthropic-api-key" \
  SARA_MODEL="claude-opus-4-8"
```

> **Alternative key wiring (Key Vault *reference*):** instead of `KEY_VAULT_URI`, you can set
> `ANTHROPIC_API_KEY` as a Key Vault reference app setting:
> `@Microsoft.KeyVault(SecretUri=https://kv-icomply2.vault.azure.net/secrets/anthropic-api-key/)`.
> The code handles both — it checks `ANTHROPIC_API_KEY` first, then falls back to a direct
> Key Vault fetch via `KEY_VAULT_URI`.

### Publish the code

```bash
cd api
func azure functionapp publish $FUNC          # needs Azure Functions Core Tools v4
```

### CORS

Allow the website origin to call the Function:

```bash
az functionapp cors add -n $FUNC -g $RG --allowed-origins https://icomply2app.com.au
```

### Get the function key (if using AuthLevel.FUNCTION, the default here)

```bash
az functionapp keys list -n $FUNC -g $RG --query "functionKeys.default" -o tsv
```

---

## 2. Configure & deploy the frontend (`frontend/index.html`)

Open `frontend/index.html` and edit the `CONFIG` block near the top of the `<script>`:

```js
const CONFIG = {
  API_BASE: "https://sara2-func.azurewebsites.net",  // your Function host
  FUNCTION_KEY: ""                                    // see note below
};
```

Then host the file at **`https://icomply2app.com.au/sara`** (drop it into that route on your
existing site — it is a static page, no build step).

### Auth choice — important

`AuthLevel.FUNCTION` (the default in `function_app.py`) means callers must send a function key.
Embedding that key in a public page leaks it. Pick the option that matches your site:

- **Recommended (advisers log in to the portal):** set the Function to **`AuthLevel.ANONYMOUS`**
  (edit the `app = func.FunctionApp(...)` line), and protect it instead by either
  (a) serving it **same-origin** behind your authenticated site and setting `API_BASE: ""`, or
  (b) putting **Azure API Management / Front Door / Easy Auth** in front of it. Leave
  `FUNCTION_KEY: ""`.
- **Quick internal pilot:** keep `AuthLevel.FUNCTION`, paste the key into `FUNCTION_KEY`, and lock
  CORS to your domain. Fine while access is restricted; rotate the key before any public exposure.

---

## 3. Run it locally first (optional)

```bash
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.json.sample local.settings.json   # then put your key in it
func start                                            # serves http://localhost:7071/api/...
```

Point the frontend at it for a smoke test: `API_BASE: "http://localhost:7071"`, then open
`frontend/index.html` in a browser. (For local file:// testing, CORS is permissive by default.)

---

## Request / response contract

Both endpoints return the same `RelianceResult` JSON the UI renders:

```jsonc
{
  "roaPermitted": true,                 // = eligible for adviser self-approval (no Fail)
  "requiresComplianceReview": false,    // true if ANY finding is Review or Fail
  "summary": "PASS — File Meets Requirements.",
  "adviserSuggestion": "- coaching point one\n- coaching point two",
  "findings": [
    { "testId": "OBJ", "question": "... (s961B(2)(a))",
      "outcome": "Pass", "reasoning": "...", "evidence": "short quote" }
  ]
}
```

Request bodies:

| Endpoint | Body |
|----------|------|
| `POST /api/soa/prevet` | `{ "role": "soa", "documents": [ { "type", "name", "content" } ] }` |
| `POST /api/roa/prevet` | `{ "classifiedAsFurtherAdvice": true, "content": "...", "documents": [ ... ] }` |

`content` is the extracted plain text of each file (the browser extracts PDF/DOCX/TXT text
client-side via pdf.js / mammoth.js, so raw files are never uploaded).

---

## Notes & guardrails

- **Privacy:** the Function does not persist documents — it forwards the extracted text to the
  Anthropic API for the check and returns the result. If you require data to stay entirely within
  your tenant, use the existing Azure AI Search–integrated SARA for that workflow.
- **Scope:** this standalone is adviser self-serve (SOA + RoA). The compliance-staff "client file
  review" stays in the main SARA app, where it has the full client file.
- **Model:** `claude-opus-4-8` with adaptive thinking. Override via the `SARA_MODEL` app setting.
- **Disclaimer:** SARA 2.0 is a first-pass aid; it does not replace adviser judgement or compliance
  sign-off. This is surfaced in the UI footer and on every exported Word result.
