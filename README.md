# SignFlow — Signeasy eSignature Demo

A single-page application demonstrating an end-to-end eSignature workflow using the [Signeasy v3 API](https://docs.signeasy.com/).

-----

## What it does

The app walks a user through five steps in a single UI:

|Step|What happens                              |Signeasy API call                                |
|----|------------------------------------------|-------------------------------------------------|
|1   |Upload a document                         |`POST /v3/original/`                             |
|2   |Enter signer name + email, send           |`POST /v3/rs/envelope/`                          |
|3   |Track status live (sent → viewed → signed)|`GET /v3/rs/envelope/{pending_id}`               |
|4   |Resolve the signed document ID            |`GET /v3/rs/envelope/signed/pending/{pending_id}`|
|5   |Download the signed PDF                   |`GET /v3/rs/envelope/signed/{signed_id}/download`|

-----

## Project structure

```
signeasy-demo/
├── app.py              # Flask backend — all API integration logic
├── requirements.txt    # Python dependencies
├── .env.example        # Template for environment variables
├── .gitignore          # Excludes .env and venv from git
├── README.md
└── templates/
    └── index.html      # Single-page frontend (HTML + CSS + vanilla JS)
```

-----

## Setup — step by step

### Step 1: Get your Signeasy Bearer token

1. Go to https://developer.signeasy.com and sign up / log in
1. Click **Create Application** → give it any name (e.g. “SignFlow Demo”)
1. Under **Sandbox credentials**, copy the **Access Token** — this is your Bearer token
1. It looks like: `eyJhbGciOiJSUzI1NiIsInR5cCI6...` (a long JWT string)

> The sandbox token is valid for ~30 days. If API calls start returning 401, generate a new one.

-----

### Step 2: Clone and set up the project

```bash
# 1. Clone the repo
git clone https://github.com/your-username/signeasy-demo.git
cd signeasy-demo

# 2. Create a virtual environment
python3 -m venv venv

# 3. Activate it
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows (Command Prompt)
# venv\Scripts\Activate.ps1     # Windows (PowerShell)

# 4. Install dependencies
pip install -r requirements.txt
```

-----

### Step 3: Set your Bearer token

**Option A — export in terminal (simplest):**

```bash
# macOS / Linux
export SIGNEASY_TOKEN="paste_your_token_here"

# Windows PowerShell
$env:SIGNEASY_TOKEN="paste_your_token_here"
```

**Option B — use a .env file:**

```bash
cp .env.example .env
# Open .env and replace the placeholder with your real token
```

Then load it:

```bash
# macOS / Linux
export $(cat .env | xargs)
```

> Never commit `.env` to git. The `.gitignore` already excludes it.

-----

### Step 4: Run the app

```bash
python app.py
```

You should see:

```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
```

Open http://localhost:5000 in your browser.

-----

### Step 5: Test the full flow

1. **Upload** — drag and drop any PDF (the Signeasy sample PDF works well)
1. **Signer** — enter your own name + a second email you can access (e.g. yourname+test@gmail.com)
1. **Send** — click “Send for Signature”; the signer receives an email with a signing link
1. **Track** — the status panel polls every 10 s; open the email and sign the document
1. **Download** — once signed, the download button appears; click it to get the signed PDF

-----

## Flask API routes

|Method|Route                        |Purpose                                                       |
|------|-----------------------------|--------------------------------------------------------------|
|`GET` |`/`                          |Serves the single-page UI                                     |
|`POST`|`/api/upload`                |Receives file from browser, forwards to Signeasy Originals API|
|`POST`|`/api/send`                  |Builds envelope payload, calls Signeasy envelope API          |
|`GET` |`/api/status/<pending_id>`   |Polls envelope + recipient status                             |
|`GET` |`/api/signed-id/<pending_id>`|Resolves signed_id from pending_id                            |
|`GET` |`/api/download/<signed_id>`  |Proxies signed PDF download (token stays server-side)         |

-----

## Assumptions made

**1. Single signer only.**
The assignment specifies one signer. `recipient_id: 1` and `source_id: 1` are hardcoded as local join keys. Extending to multiple signers would require looping recipients with incrementing IDs.

**2. Pre-placed signature field at a fixed position.**
The envelope payload includes a `fields_payload` entry placing a signature box at `x: 60, y: 520` on page 1 — coordinates confirmed against the live API. Without `fields_payload`, the API returns a 400 error. The signer can reposition the field in the Signeasy UI.

**3. `sources[]` not `originals[]`.**
The Signeasy docs example shows an `originals` key but the live v3 API requires `sources` with `source_id`, `type`, `name`, and `id` fields. Confirmed by direct curl testing against the sandbox.

**4. Polling instead of webhooks.**
Status is checked every 10 seconds via client-side polling. A production integration would use Signeasy webhook events (`rs.signed`, `rs.viewed`) for real-time push updates — polling was chosen here because it needs no public URL, making local dev frictionless.

**5. Bearer token is server-side only.**
Token is read from the `SIGNEASY_TOKEN` environment variable and never sent to the browser. The download endpoint proxies the PDF through Flask for the same reason.

**6. No file persistence on the server.**
Uploaded files stream directly from the browser to Signeasy’s Originals API. Nothing is written to disk on the Flask server.

**7. Supported formats: PDF, DOC, DOCX** — matching Signeasy’s accepted types, max 25 MB.

-----

## Known limitations

- **No webhook handler.** Polling replaces real-time events. A `/webhook/signeasy` endpoint receiving `rs.signed` events would be the production approach.
- **No session persistence.** Refreshing the browser resets all state. A lightweight store (SQLite, Redis) mapping `pending_id → session` is needed for multi-user use.
- **No auth on Flask routes.** Any client that reaches the server can trigger API calls. Route protection is needed before public deployment.
- **Signeasy error messages surfaced verbatim** — useful for debugging, needs sanitising in production.

-----

## If I had more time

- Webhook support with ngrok for local HTTPS tunnelling, replacing polling
- SQLite session store so browser refresh doesn’t lose pending_id
- Dynamic signer list — add/remove recipients before sending
- Embedded signing mode (iframe) as alternative to email-link signing
- “Remind signer” button via `POST /v3/rs/envelope/{pending_id}/remind`
- `pytest` + `responses` mock library test suite covering all Flask routes
- `python-dotenv` integration so `.env` loads automatically on startup

-----

## Dependencies

```
flask>=3.0.0
requests>=2.31.0
werkzeug>=3.0.0
```

Python 3.9+ required.
