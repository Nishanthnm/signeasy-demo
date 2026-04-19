“””
Signeasy eSignature Demo App
Flask backend that orchestrates the full sign workflow:

1. Upload document → Signeasy Originals API
1. Create envelope → send to single signer
1. Poll envelope status (sent / viewed / signed)
1. Resolve signed_id from pending_id once completed
1. Proxy download of the signed PDF back to the browser
   “””

import os
import requests
from flask import Flask, request, jsonify, render_template, Response
from werkzeug.utils import secure_filename

app = Flask(**name**)

# ── Config ────────────────────────────────────────────────────────────────────

SIGNEASY_API_BASE = “https://api.signeasy.com/v3”
BEARER_TOKEN = os.environ.get(“SIGNEASY_TOKEN”, “”)   # never hard-code this
MAX_UPLOAD_BYTES = 25 * 1024 * 1024                    # 25 MB – Signeasy limit
ALLOWED_EXTENSIONS = {“pdf”, “doc”, “docx”}

def _headers():
“”“Return auth headers shared by all Signeasy requests.”””
return {
“Authorization”: f”Bearer {BEARER_TOKEN}”,
“Accept”: “application/json”,
}

def _allowed(filename: str) -> bool:
return “.” in filename and filename.rsplit(”.”, 1)[1].lower() in ALLOWED_EXTENSIONS

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route(”/”)
def index():
return render_template(“index.html”)

@app.route(”/api/upload”, methods=[“POST”])
def upload_document():
“””
Step 1 — Upload the raw file to Signeasy and get back an original_id.
The original_id is later referenced when creating the envelope.
“””
if not BEARER_TOKEN:
return jsonify({“error”: “SIGNEASY_TOKEN env var is not set.”}), 500

```
if "file" not in request.files:
    return jsonify({"error": "No file part in request."}), 400

file = request.files["file"]
if file.filename == "":
    return jsonify({"error": "No file selected."}), 400
if not _allowed(file.filename):
    return jsonify({"error": "Only PDF, DOC, DOCX files are supported."}), 400

filename = secure_filename(file.filename)

# POST multipart/form-data to Signeasy
resp = requests.post(
    f"{SIGNEASY_API_BASE}/original/",
    headers=_headers(),
    files={"file": (filename, file.stream, file.content_type)},
    data={"name": filename, "rename_if_exists": "true"},
    timeout=30,
)

if not resp.ok:
    return jsonify({
        "error": "Signeasy upload failed.",
        "detail": resp.text,
        "status_code": resp.status_code,
    }), resp.status_code

data = resp.json()
# Return both id and name — name is required in the envelope sources[] payload
return jsonify({"original_id": data.get("id"), "original_name": filename})
```

@app.route(”/api/send”, methods=[“POST”])
def send_for_signature():
“””
Step 2 — Create an envelope and send it to a single signer.

```
Payload structure confirmed against the live Signeasy v3 API:
- `sources`         : list of documents (replaces the undocumented `originals` key)
- `is_ordered`      : sequential signing flag (replaces `is_sequential`)
- `embedded_signing`: False = email-based signing link
- `recipients`      : uses `recipient_id` (integer) as the join key with fields_payload
- `fields_payload`  : pre-placed signature field with fixed position on page 1
                      x/y are percentage-based coordinates (0–100) from top-left.

Signature field defaults (page 1, lower-left quadrant) work for most PDFs.
The signer can reposition the field in the Signeasy signing UI if needed.
"""
body = request.get_json(force=True)
original_id   = body.get("original_id")
original_name = body.get("original_name", "document.pdf")
signer_name   = body.get("signer_name", "").strip()
signer_email  = body.get("signer_email", "").strip()
message       = body.get("message", "Please sign this document.").strip()

if not all([original_id, signer_name, signer_email]):
    return jsonify({"error": "original_id, signer_name and signer_email are required."}), 400

# Split name into first / last best-effort
name_parts = signer_name.split(maxsplit=1)
first_name = name_parts[0]
last_name  = name_parts[1] if len(name_parts) > 1 else "-"

# Confirmed working payload shape (matches successful curl test)
payload = {
    "is_ordered":       True,
    "embedded_signing": False,
    "message":          message,
    "sources": [
        {
            "source_id": 1,           # local reference ID, joined with fields_payload
            "type":      "original",
            "id":        original_id,
            "name":      original_name,
        }
    ],
    "recipients": [
        {
            "recipient_id": 1,        # local reference ID, joined with fields_payload
            "first_name":   first_name,
            "email":        signer_email,
        }
    ],
    # Pre-place a required signature field on page 1.
    # Position values are percentages of page width/height.
    # x=60, y=520 matches the Signeasy docs example; adjust if needed.
    "fields_payload": [
        {
            "recipient_id":    1,
            "source_id":       1,
            "type":            "signature",
            "required":        True,
            "page_number":     1,
            "position": {
                "x":      60,
                "y":      520,
                "height": 50,
                "width":  250,
                "mode":   "fixed",
            },
            "additional_info": {},
        }
    ],
}

resp = requests.post(
    f"{SIGNEASY_API_BASE}/rs/envelope/",
    headers={**_headers(), "Content-Type": "application/json"},
    json=payload,
    timeout=30,
)

if not resp.ok:
    return jsonify({
        "error":       "Failed to create envelope.",
        "detail":      resp.text,
        "status_code": resp.status_code,
    }), resp.status_code

data = resp.json()
return jsonify({"pending_id": data.get("id")})
```

@app.route(”/api/status/<int:pending_id>”, methods=[“GET”])
def get_status(pending_id):
“””
Step 3 — Poll the envelope status.
Returns status string + recipient-level view/sign info.
Possible envelope statuses: pending, viewed, signed, declined, voided, expired.
“””
resp = requests.get(
f”{SIGNEASY_API_BASE}/rs/envelope/{pending_id}”,
headers=_headers(),
timeout=15,
)

```
if resp.status_code == 404:
    return jsonify({"error": "Envelope not found."}), 404
if not resp.ok:
    return jsonify({"error": "Status check failed.", "detail": resp.text}), resp.status_code

data = resp.json()

# Flatten what the UI needs
recipients = data.get("recipients", [])
recipient_info = [
    {
        "name": f"{r.get('first_name', '')} {r.get('last_name', '')}".strip(),
        "email": r.get("email"),
        "status": r.get("status"),   # pending / viewed / signed / declined
    }
    for r in recipients
]

return jsonify({
    "pending_id": pending_id,
    "status": data.get("status"),          # envelope-level status
    "created_at": data.get("created_at"),
    "updated_at": data.get("updated_at"),
    "recipients": recipient_info,
})
```

@app.route(”/api/signed-id/<int:pending_id>”, methods=[“GET”])
def get_signed_id(pending_id):
“””
Step 4 — Once the envelope is fully signed, resolve the signed_id
from the pending_id. This is a separate API call in Signeasy’s model.
“””
resp = requests.get(
f”{SIGNEASY_API_BASE}/rs/envelope/signed/pending/{pending_id}”,
headers=_headers(),
timeout=15,
)

```
if not resp.ok:
    return jsonify({"error": "Could not resolve signed ID.", "detail": resp.text}), resp.status_code

data = resp.json()
return jsonify({"signed_id": data.get("id")})
```

@app.route(”/api/download/<int:signed_id>”, methods=[“GET”])
def download_signed(signed_id):
“””
Step 5 — Proxy the signed PDF download through our server.
We proxy it so the browser never needs the Bearer token directly.
Uses: GET /v3/rs/envelope/signed/{signed_id}/download
“””
resp = requests.get(
f”{SIGNEASY_API_BASE}/rs/envelope/signed/{signed_id}/download”,
headers=_headers(),
stream=True,
timeout=60,
)

```
if not resp.ok:
    return jsonify({"error": "Download failed.", "detail": resp.text}), resp.status_code

content_disposition = resp.headers.get(
    "Content-Disposition", f'attachment; filename="signed_{signed_id}.pdf"'
)

return Response(
    resp.iter_content(chunk_size=8192),
    status=200,
    content_type=resp.headers.get("Content-Type", "application/pdf"),
    headers={"Content-Disposition": content_disposition},
)
```

# ── Entry point ───────────────────────────────────────────────────────────────

if **name** == “**main**”:
if not BEARER_TOKEN:
print(“⚠️  WARNING: SIGNEASY_TOKEN is not set. API calls will fail with 401.”)
app.run(debug=True, port=5000)
