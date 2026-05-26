# Mashroom OCR — Developer Guide

> **Version:** 1.0 · **Last updated:** May 2026  
> Complete reference for developers setting up, extending, or maintaining the Mashroom OCR system.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Prerequisites](#3-prerequisites)
4. [Environment Setup](#4-environment-setup)
5. [Local Setup — Step by Step](#5-local-setup--step-by-step)
6. [Project Structure](#6-project-structure)
7. [Architecture](#7-architecture)
8. [Module Reference](#8-module-reference)
9. [Database Schema](#9-database-schema)
10. [OCR Template System](#10-ocr-template-system)
11. [API Reference](#11-api-reference)
12. [Web Routes Reference](#12-web-routes-reference)
13. [Excel Export](#13-excel-export)
14. [Common Workflows](#14-common-workflows)
15. [Running Tests](#15-running-tests)
16. [Deployment Guide](#16-deployment-guide)
17. [Troubleshooting](#17-troubleshooting)

---

## 1. Project Overview

**Mashroom OCR** is a web application that extracts structured data from handwritten or printed tabular forms (PDF scans, images) using **Claude AI Vision**. It is purpose-built for agricultural operations forms but is designed to handle any tabular document automatically.

### Key Features

| Feature | Description |
|---|---|
| Multi-format ingestion | PDF, PNG, JPG, TIFF, BMP, WebP |
| AI-powered extraction | Claude Sonnet Vision — reads complex merged headers, multi-row headers, and handwritten values |
| Template system | Pre-configured column maps for known form types; auto-detect for unknown forms |
| Ambiguity flagging | Uncertain readings marked with `?`; highlighted amber in UI and Excel |
| Excel export | Formatted `.xlsx` with Summary, Flagged for Review, and per-page sheets |
| Job history | Every extraction saved to PostgreSQL; re-downloadable at any time |
| Multi-user auth | Admin-only user creation; bcrypt-hashed passwords; Flask-Login session management |
| REST API | Programmatic extraction endpoint for integration with other systems |

---

## 2. Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.11+ |
| Web framework | Flask | 3.0.3 |
| ORM | Flask-SQLAlchemy | 3.1.1 |
| Database | PostgreSQL | 14+ |
| Migrations | Flask-Migrate (Alembic) | 4.0.7 |
| Auth | Flask-Login + Flask-Bcrypt | 0.6.3 / 1.0.1 |
| AI / Vision | Anthropic Claude Sonnet | claude-sonnet-4-6 |
| PDF → Image | pdf2image + poppler | 1.17.0 |
| Image processing | Pillow | 10.4.0 |
| Excel generation | openpyxl | 3.1.5 |
| Config management | python-dotenv | 1.0.1 |

---

## 3. Prerequisites

Install these before starting:

### 3.1 Python 3.11+

```bash
python3 --version   # must be 3.11 or higher
```

Install via [python.org](https://www.python.org/downloads/) or `brew install python@3.11` (macOS).

### 3.2 PostgreSQL 14+

**macOS:**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Ubuntu / Debian:**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 3.3 Poppler (PDF rendering)

Required by `pdf2image` to convert PDF pages to images.

**macOS:**
```bash
brew install poppler
```

**Ubuntu / Debian:**
```bash
sudo apt-get install poppler-utils
```

### 3.4 Anthropic API Key

Sign up at [console.anthropic.com](https://console.anthropic.com) and create an API key.  
The key starts with `sk-ant-...`.

---

## 4. Environment Setup

### 4.1 Clone / Download the project

```bash
# If using git:
git clone <repository-url>
cd Mashroom-OCR

# Or unzip the downloaded archive and cd into it
```

### 4.2 Create a Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows PowerShell
```

### 4.3 Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4.4 Create the PostgreSQL database

```bash
createdb mashroom_ocr
```

If your PostgreSQL has a password-protected user:
```bash
psql -U postgres -c "CREATE DATABASE mashroom_ocr;"
```

### 4.5 Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# Required — Anthropic API key
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Required — PostgreSQL connection
DATABASE_URL=postgresql://localhost/mashroom_ocr
# With credentials: postgresql://username:password@localhost:5432/mashroom_ocr

# Required in production, optional in development
FLASK_SECRET_KEY=change-me-to-a-long-random-string

# "development" | "production" | "testing"
FLASK_ENV=development

# "true" in development, "false" in production
FLASK_DEBUG=true

# HTTP port (default 5000)
PORT=5000
```

> **Security note:** Never commit `.env` to version control. It is listed in `.gitignore`.

### 4.6 Run database migrations

```bash
flask db upgrade
```

This creates the `users` and `jobs` tables.

### 4.7 Create the first admin user

```bash
flask create-admin admin@example.com 'YourSecurePassword123'
```

> **Shell note:** If your password contains `#`, `?`, `!`, or `*`, always wrap it in **single quotes** to prevent shell glob expansion.

---

## 5. Local Setup — Step by Step

Full sequence from zero to running application:

```bash
# 1. Enter project directory
cd /path/to/Mashroom-OCR

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create database
createdb mashroom_ocr

# 5. Copy and edit config
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and other values

# 6. Apply migrations
flask db upgrade

# 7. Create admin user
flask create-admin admin@yourcompany.com 'StrongPassword!'

# 8. Start the application
python3 app.py
```

The app is now running at: **http://localhost:5000**

Log in with the admin credentials created in step 7.

---

## 6. Project Structure

```
Mashroom-OCR/
│
├── app.py                  # Application factory + CLI + entry point
├── config.py               # Environment-specific config classes
├── extensions.py           # Flask extension singletons (Singleton pattern)
├── models.py               # SQLAlchemy ORM models (User, Job)
├── auth.py                 # Authentication blueprint (login, logout)
├── utils.py                # Shared utilities and decorators
├── ocr_processor.py        # Core OCR logic — Claude API integration
├── excel_exporter.py       # Excel (.xlsx) generation
│
├── routes/
│   ├── __init__.py         # Package marker
│   ├── main.py             # Main user routes (upload, results, history, download)
│   ├── admin.py            # Admin routes (user management)
│   └── api.py              # REST API routes (health, /api/extract)
│
├── templates/
│   ├── index.html          # Main app page (upload form + results table)
│   ├── login.html          # Login form
│   ├── register.html       # Registration disabled page
│   ├── history.html        # Job history list
│   └── admin_users.html    # Admin user management panel
│
├── fonts/                  # Font files (Caveat, Kalam) for UI rendering
│
├── samples/                # Sample PDF files for testing
│   ├── sample_01.pdf
│   └── ...
│
├── templates.json          # OCR template definitions (column maps)
├── requirements.txt        # Python package dependencies
├── test_ocr.py             # Unit test suite (55 tests)
│
├── .env                    # Local secrets — NOT committed to git
├── .env.example            # Template for .env
│
└── migrations/             # Alembic migration scripts (auto-generated)
    └── versions/
```

---

## 7. Architecture

### 7.1 Design Patterns

**Application Factory Pattern**  
`create_app()` in `app.py` creates and configures the Flask app. This allows multiple app instances (e.g., testing vs. production) without global state conflicts.

```
create_app(config_name)
  ├── Load config class from config_map
  ├── init_app() all extensions (db, bcrypt, migrate, login_manager)
  ├── Load OCR templates → store in app.config
  └── Register blueprints (auth, main, admin, api)
```

**Singleton Pattern**  
All Flask extensions are instantiated once in `extensions.py` without an app object, then bound to a concrete app via `.init_app()`. Every other module imports from `extensions.py` — never re-instantiates.

```python
# extensions.py — instantiate once
db            = SQLAlchemy()
bcrypt        = Bcrypt()
login_manager = LoginManager()
migrate       = Migrate()

# app.py — bind to app
db.init_app(app)
bcrypt.init_app(app)
```

**Blueprint Pattern**  
Routes are separated into focused blueprints. No route logic lives in `app.py`.

| Blueprint | Prefix | Responsibility |
|---|---|---|
| `auth_bp` | *(none)* | `/login`, `/logout` |
| `main_bp` | *(none)* | `/`, `/upload`, `/results`, `/history`, `/download_excel` |
| `admin_bp` | `/admin` | `/admin/users`, `/admin/users/create`, `/admin/users/<id>/delete` |
| `api_bp` | *(none)* | `/health`, `/api/extract` |

### 7.2 Module Dependency Graph

```
config.py
    ↓
extensions.py
    ↓
models.py          utils.py
    ↓                  ↓
auth.py        excel_exporter.py    ocr_processor.py
    ↓                  ↓                  ↓
             routes/main.py
             routes/admin.py
             routes/api.py
                      ↓
                   app.py  ←  creates and wires everything
```

**Key rule:** No circular imports. `extensions.py` is the shared hub — models and auth import from it, never from each other.

### 7.3 Request Lifecycle (Upload)

```
Browser POST /upload
    → routes/main.py: upload()
        → validate file type (utils.allowed_file)
        → fetch api_key (utils.get_api_key)
        → resolve template from app.config["OCR_TEMPLATE_BY_ID"]
        → ocr_processor.process_bytes(raw, filename, api_key, template)
            → write temp file
            → pdf2image or PIL open → list of PIL images
            → for each image:
                → _preprocess (resize to ≤ 2000px)
                → _pil_to_base64 (JPEG encode, auto-reduce quality if > 4.5 MB)
                → Claude API call (SYSTEM_PROMPT + EXTRACTION_PROMPT or template prompt)
                → parse JSON response
            → merge pages → return {pages, summary, all_pickers, template_id}
            → delete temp file
        → save Job to PostgreSQL (result_json stored as TEXT)
        → redirect to /results/<job_id>
    → routes/main.py: results()
        → load Job from DB
        → build_headers_and_labels (utils.py)
        → render index.html with data
```

---

## 8. Module Reference

### 8.1 `app.py` — Application Factory

**Purpose:** Creates and configures the Flask app; exposes CLI commands.

**Key functions:**

| Function | Description |
|---|---|
| `create_app(config_name)` | Factory — returns configured Flask app |
| `create_admin` (CLI) | `flask create-admin <email> <password>` — creates first admin |

**Usage:**
```bash
# Run directly
python3 app.py

# Flask CLI (uses module-level app = create_app())
flask run
flask db upgrade
flask create-admin admin@example.com 'password'
```

---

### 8.2 `config.py` — Configuration Classes

Three config classes selected via `FLASK_ENV` environment variable:

| Class | `FLASK_ENV` value | Database | Debug |
|---|---|---|---|
| `DevelopmentConfig` | `development` (default) | PostgreSQL (from `DATABASE_URL`) | True |
| `ProductionConfig` | `production` | PostgreSQL (required) | False |
| `TestingConfig` | `testing` | SQLite in-memory | True |

**`ProductionConfig.validate()`** — called at startup in production mode. Raises `EnvironmentError` if any of `FLASK_SECRET_KEY`, `DATABASE_URL`, or `ANTHROPIC_API_KEY` are missing.

**Shared config values:**

| Key | Value | Description |
|---|---|---|
| `SECRET_KEY` | env `FLASK_SECRET_KEY` | Flask session signing key |
| `MAX_CONTENT_LENGTH` | 50 MB | Maximum upload file size |
| `ALLOWED_EXTENSIONS` | pdf, png, jpg, jpeg, tiff, tif, bmp, webp | Accepted file types |
| `TEMPLATES_JSON_PATH` | `./templates.json` | Path to template definitions |

---

### 8.3 `extensions.py` — Singleton Extensions

Defines all Flask extensions as module-level singletons. Import from here everywhere.

```python
from extensions import db, bcrypt, login_manager, migrate
```

Never do `db = SQLAlchemy()` in any other file.

---

### 8.4 `models.py` — Database Models

#### `User`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | Integer | PK, auto | Primary key |
| `email` | String(255) | UNIQUE, NOT NULL, indexed | Login identifier |
| `password_hash` | String(255) | NOT NULL | bcrypt hash |
| `is_admin` | Boolean | NOT NULL, default False | Admin flag |
| `created_at` | DateTime | NOT NULL, default now | Creation timestamp |

Relationship: `User.jobs` → one-to-many → `Job` (cascade delete)

#### `Job`

| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | String(36) | PK | UUID v4 |
| `user_id` | Integer | FK → users.id, indexed | Owner |
| `filename` | String(255) | NOT NULL | Original filename |
| `template_id` | String(50) | nullable | Template used (`"auto"` or template ID) |
| `result_json` | Text | nullable | Full extraction result as JSON string |
| `created_at` | DateTime | NOT NULL, default now | Extraction timestamp |

**Key methods:**
- `job.get_data()` → deserializes `result_json` to dict
- `job.get_template(template_by_id)` → resolves template dict from `template_id`

---

### 8.5 `utils.py` — Shared Utilities

| Function / Decorator | Signature | Description |
|---|---|---|
| `allowed_file` | `(filename, allowed_set) → bool` | Validates file extension |
| `get_api_key` | `() → str \| None` | Reads `ANTHROPIC_API_KEY` from env |
| `admin_required` | decorator | Requires `is_admin=True`; returns 403 otherwise |
| `load_ocr_templates` | `(path) → (list, dict)` | Loads `templates.json`; returns list + id-keyed dict |
| `build_headers_and_labels` | `(data, template) → (list, dict)` | Derives column key list and human-readable label map |

**`admin_required` decorator:**
```python
@admin_bp.get("/users")
@admin_required          # ← stacks login_required + is_admin check
def users():
    ...
```

---

### 8.6 `ocr_processor.py` — Core OCR

**Public API:**

```python
process_file(file_path, api_key=None, template=None) → dict
process_bytes(file_bytes, filename, api_key=None, template=None) → dict
```

`process_bytes` is used by the web app (file comes from HTTP upload).  
`process_file` is used for direct CLI/script usage.

**Return structure:**
```json
{
  "pages": [
    {
      "page_number": 1,
      "document_info": { "title": "...", "date": "...", ... },
      "column_headers": ["Col_A", "Col_B", ...],
      "rows": [
        {
          "row_label": "Platform A",
          "name": null,
          "record_id": null,
          "start_time": null,
          "end_time": null,
          "fields": { "Col_A": "ok", "Col_B": "47?" },
          "notes": null
        }
      ],
      "raw_text": "Machine safety pre-start checklist"
    }
  ],
  "summary": { "title": "...", "date": "...", ... },
  "all_pickers": [ /* flattened rows from all pages, each has _page tag */ ],
  "template_id": "non_pick_time"
}
```

**Internal pipeline:**

```
process_bytes()
  → write to temp file
  → process_file()
      → _load_images()        PDF: pdf2image / Image: PIL open
          → _images_from_pdf() uses poppler via pdf2image
      → for each image:
          → _preprocess()     resize: scale up if < 1000px, scale down if > 2000px
          → _call_claude()
              → _pil_to_base64()   JPEG encode, quality steps: 88→75→60→45
              → build prompt:      _build_template_prompt() or EXTRACTION_PROMPT
              → client.messages.create()  Claude API call
              → strip markdown fences
              → json.loads()
  → merge pages
  → return result dict
  → (finally) os.unlink(tmp_path)
```

**Ambiguity convention:** Claude appends `"?"` to uncertain readings (e.g., `"47?"`, `"ok?"`). The app detects `"?"` in cell values to trigger amber highlighting.

**Claude model:** `claude-sonnet-4-6` — best vision accuracy at 5x lower cost than Opus.

---

### 8.7 `excel_exporter.py` — Excel Generation

**Public API:**
```python
make_excel(job) → io.BytesIO
```

Returns a `BytesIO` buffer containing the `.xlsx` file. Caller is responsible for streaming it; the buffer is not closed here (Flask's `send_file` handles it).

**Workbook structure:**

| Sheet | Content |
|---|---|
| **Summary** | Document metadata + total pages + total records + flagged count |
| **Flagged for Review** | All cells containing `"?"` — Page, Row #, Name/Label, Column, Value |
| **Page N** | Full data table for each scanned page |

**Style constants** (module-level, created once):

| Constant | Usage |
|---|---|
| `_HDR_FILL` | Dark green (`#2D6A4F`) — main header background |
| `_SUB_FILL` | Medium green (`#52B788`) — quantity column headers |
| `_ALT_FILL` | Light green (`#F0F7F2`) — alternating row background |
| `_AMBER_FILL` | Light amber (`#FFF3E0`) — flagged cell background |
| `_AMBER_HDR_FILL` | Orange (`#F4A261`) — "Flagged for Review" sheet header |
| `_AMBER_FONT` | Bold orange (`#F4A261`) — ambiguous value text |

---

### 8.8 `auth.py` — Authentication Blueprint

| Route | Method | Description |
|---|---|---|
| `/login` | GET | Render login form |
| `/login` | POST | Authenticate user; redirect to `main.index` on success |
| `/logout` | GET | Invalidate session; redirect to login |
| `/register` | GET/POST | Always returns 403 — registration closed |

Login uses bcrypt to verify the password against `user.password_hash`.  
Successful login calls `login_user(user, remember=True)` — session persists across browser close.

---

## 9. Database Schema

### Entity Relationship

```
users
  id          INTEGER PK
  email       VARCHAR(255) UNIQUE
  password_hash VARCHAR(255)
  is_admin    BOOLEAN
  created_at  DATETIME

jobs
  id          VARCHAR(36) PK  ← UUID
  user_id     INTEGER FK → users.id  (CASCADE DELETE)
  filename    VARCHAR(255)
  template_id VARCHAR(50)
  result_json TEXT           ← full JSON blob
  created_at  DATETIME
```

One user → many jobs. Deleting a user cascades to delete all their jobs.

### Migration Commands

```bash
# Apply all pending migrations (run on first install and after updates)
flask db upgrade

# Create a new migration after changing models.py
flask db migrate -m "describe what changed"
flask db upgrade

# Downgrade one step
flask db downgrade

# Show migration history
flask db history
```

---

## 10. OCR Template System

Templates live in `templates.json`. They tell Claude exactly which columns to extract, eliminating column key guessing for known form types.

### Template Structure

```json
{
  "id": "non_pick_time",
  "name": "Non-Pick Time Record",
  "description": "Human-readable description",
  "note": "Document-specific reading instructions for Claude",
  "columns": [
    { "key": "Date",           "label": "Date" },
    { "key": "Non_Pick_Time_Mins", "label": "Non Pick time Mins" }
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique identifier; used in URLs and DB |
| `name` | Yes | Displayed in UI dropdown |
| `description` | No | UI tooltip / help text |
| `note` | Yes (real templates) | Injected into Claude prompt; explain document quirks |
| `columns` | Yes | Ordered column definitions |
| `columns[].key` | Yes | Snake_case key used in extracted JSON |
| `columns[].label` | Yes | Human label matching the printed column header |

### Built-in Templates

| ID | Name | Columns |
|---|---|---|
| `auto` | Auto-detect (generic) | None — Claude reads headers from document |
| `ms_prestart` | MS Pre-start Checks | 16 — machine gate sensor + picker safety check |
| `hughes_daily_picking` | Hughes Group Daily Picking Record | 15 — product amounts + punnet traceability |
| `non_pick_time` | Non-Pick Time Record | 14 — date through non-pick time mins |

### Adding a New Template

1. Open `templates.json`
2. Add a new object to the `"templates"` array
3. Restart the application — templates are loaded at startup into `app.config`
4. No migration needed; templates are file-based

Example:
```json
{
  "id": "my_new_form",
  "name": "My New Form Type",
  "description": "Description for users",
  "note": "This form has two header rows. Top row = category, bottom row = sub-column.",
  "columns": [
    { "key": "Category_A_Count",  "label": "Category A: Count" },
    { "key": "Category_A_Weight", "label": "Category A: Weight" }
  ]
}
```

---

## 11. API Reference

### `GET /health`

Health check endpoint. No authentication required.

**Response:**
```json
{ "status": "ok", "api_key_set": true }
```

---

### `POST /api/extract`

Programmatic extraction. No web session required; accessible from external systems.

**Request:** `multipart/form-data`

| Field | Required | Description |
|---|---|---|
| `file` | Yes | PDF or image file |
| `template_id` | No | Template ID from `templates.json` (default: `"auto"`) |

**Response:** `application/json` — same structure as `ocr_processor.process_bytes()` return value.

**Example:**
```bash
curl -X POST http://localhost:5000/api/extract \
     -F "file=@scan.pdf" \
     -F "template_id=non_pick_time"
```

**Error responses:**

| Status | Condition |
|---|---|
| 400 | No `file` field in request, or unsupported file type |
| 500 | `ANTHROPIC_API_KEY` not configured, or processing exception |

---

## 12. Web Routes Reference

All routes below require authentication (`@login_required`) unless noted.

### Main Blueprint (`routes/main.py`)

| Route | Method | Auth | Description |
|---|---|---|---|
| `/` | GET | User | Upload form; lists templates in dropdown |
| `/upload` | POST | User | Process file; save Job; redirect to results |
| `/results/<job_id>` | GET | User | Show extraction results for a specific job |
| `/history` | GET | User | List all jobs for current user |
| `/download_excel/<job_id>` | GET | User | Stream `.xlsx` file for a job |

### Admin Blueprint (`routes/admin.py`) — prefix `/admin`

| Route | Method | Auth | Description |
|---|---|---|---|
| `/admin/users` | GET | Admin | List all users |
| `/admin/users/create` | POST | Admin | Create a new user account |
| `/admin/users/<id>/delete` | POST | Admin | Delete a user and all their jobs |

> Admin routes use `@admin_required` which chains `@login_required` + `is_admin=True` check.

### Auth Blueprint (`auth.py`)

| Route | Method | Auth | Description |
|---|---|---|---|
| `/login` | GET | Public | Login form |
| `/login` | POST | Public | Authenticate |
| `/logout` | GET | User | Sign out |
| `/register` | GET/POST | Public | Always 403 — registration closed |

---

## 13. Excel Export

Generated by `excel_exporter.make_excel(job)`. Called from `GET /download_excel/<job_id>`.

### Sheet Layout

**Sheet 1 — Summary**
- Source file name, total pages, total records, flagged reading count
- Document metadata (date, location, supervisor, etc.)

**Sheet 2 — Flagged for Review**
- Every cell where Claude indicated uncertainty (`?` in value)
- Columns: Page | Row # | Name/Label | Column | Extracted Value
- Amber background + bold orange text on the value column
- If no uncertain readings: shows "No uncertain readings ✓" in green italic

**Sheets 3+ — Page N**
- One sheet per scanned page
- Fixed columns: `#` (row number) + `Page` + optional Team/Name/RecordID/Start
- Data columns: all extracted fields (green sub-header background)
- Tail columns: optional End Time, Notes
- Alternating row backgrounds (white/light green)
- Ambiguous values (`?`) rendered in bold amber text inline
- Frozen header row + frozen fixed columns

### Download Flow

```
GET /download_excel/<job_id>
  → load Job from DB (scoped to current_user)
  → make_excel(job) → BytesIO buffer
  → send_file(buf, as_attachment=True, download_name="<filename>_extracted.xlsx")
```

---

## 14. Common Workflows

### 14.1 Uploading a Document

1. User navigates to `/` (index)
2. Selects file from file picker
3. Selects template from dropdown (or leaves on "Auto-detect")
4. Clicks "Extract Data"
5. `POST /upload` fires → OCR runs (5–30 seconds depending on page count)
6. Redirects to `/results/<job_id>` with extracted table
7. User can click "Download Excel" → `GET /download_excel/<job_id>`

### 14.2 Creating a New User (Admin)

**Option A — Admin web panel:**
1. Log in as admin
2. Click "Admin" in nav bar → `/admin/users`
3. Fill in email, password, optionally tick "Admin"
4. Click "Create User"

**Option B — CLI (first admin):**
```bash
flask create-admin user@example.com 'SecurePassword!'
```

### 14.3 Adding a New OCR Template

1. Edit `templates.json` — add entry to `"templates"` array
2. Ensure each column has `key` (snake_case) and `label` (matches printed header text)
3. Add a `note` field explaining document structure quirks
4. Restart Flask: `python3 app.py`
5. New template appears in the upload dropdown immediately

### 14.4 Extending the Data Model

1. Edit `models.py` — add column(s)
2. Generate migration:
   ```bash
   flask db migrate -m "add column X to jobs"
   ```
3. Review the generated file in `migrations/versions/`
4. Apply:
   ```bash
   flask db upgrade
   ```

### 14.5 Adding a New Blueprint

1. Create `routes/myfeature.py`
2. Define `myfeature_bp = Blueprint("myfeature", __name__, url_prefix="/myfeature")`
3. Add routes with `@myfeature_bp.get(...)` etc.
4. Register in `app.py` inside `create_app()`:
   ```python
   from routes.myfeature import myfeature_bp
   app.register_blueprint(myfeature_bp)
   ```

---

## 15. Running Tests

The test suite covers OCR processor logic, prompt correctness, template integrity, and backward compatibility. No real API calls are made — Claude responses are mocked.

### Run all tests

```bash
python3 -m pytest test_ocr.py -v
```

### Run a specific test class

```bash
python3 -m pytest test_ocr.py::TestPreprocess -v
python3 -m pytest test_ocr.py::TestTemplatesJson -v
```

### Test coverage summary

| Test Class | Tests | What it covers |
|---|---|---|
| `TestPreprocess` | 4 | Image resize (scale up, scale down, no-op, RGBA→RGB) |
| `TestPilToBase64` | 2 | JPEG encoding, size guard under 4.5 MB |
| `TestCallClaude` | 3 | Valid JSON, bad JSON fallback, markdown fence stripping |
| `TestDocumentStructures` | 5 | All 5 header structure types + multi-page merge |
| `TestBackwardCompat` | 2 | Legacy `pickers` + `quantities` keys |
| `TestPromptHardcoding` | 2 | No client-specific domain terms in prompts |
| `TestTemplatesJson` | 20 | Template count, structure, column integrity |
| `TestBuildTemplatePrompt` | 10 | Prompt generation for all 3 real templates |
| `TestCallClaudeTemplate` | 5 | Correct prompt routing per template |

**Total: 53 tests**

### Syntax check all modules

```bash
python3 -m py_compile app.py config.py extensions.py models.py \
    auth.py utils.py ocr_processor.py excel_exporter.py \
    routes/main.py routes/admin.py routes/api.py
echo "All files syntax OK"
```

---

## 16. Deployment Guide

### 16.1 Server Requirements

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 2 GB | 4 GB |
| Disk | 20 GB SSD | 40 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Python | 3.11+ | 3.12 |
| PostgreSQL | 14+ | 15 |

### 16.2 Required Software on Server

```bash
# System packages
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip \
    postgresql postgresql-contrib poppler-utils nginx

# Start PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create DB and user
sudo -u postgres psql -c "CREATE USER mashroom WITH PASSWORD 'strongpassword';"
sudo -u postgres psql -c "CREATE DATABASE mashroom_ocr OWNER mashroom;"
```

### 16.3 Production Environment Variables

```ini
FLASK_ENV=production
FLASK_SECRET_KEY=<64-char random string>
DATABASE_URL=postgresql://mashroom:strongpassword@localhost:5432/mashroom_ocr
ANTHROPIC_API_KEY=sk-ant-your-key
FLASK_DEBUG=false
PORT=8000
```

Generate a secure secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 16.4 Running with Gunicorn

```bash
pip install gunicorn

# Test run
gunicorn --workers 2 --bind 0.0.0.0:8000 "app:create_app('production')"

# Production (systemd service recommended)
gunicorn --workers 4 --bind unix:/tmp/mashroom.sock \
         --timeout 120 \
         "app:create_app('production')"
```

`--timeout 120` — important: OCR on multi-page PDFs can take 30–60 seconds.

### 16.5 Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    client_max_body_size 50M;   # match MAX_CONTENT_LENGTH

    location / {
        proxy_pass http://unix:/tmp/mashroom.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

### 16.6 Deploy Checklist

- [ ] `FLASK_ENV=production` set
- [ ] `FLASK_SECRET_KEY` set to a long random value
- [ ] `DATABASE_URL` points to production PostgreSQL
- [ ] `ANTHROPIC_API_KEY` set
- [ ] `flask db upgrade` run on server
- [ ] `flask create-admin` run to create first admin account
- [ ] `FLASK_DEBUG=false`
- [ ] Nginx `client_max_body_size 50M` configured
- [ ] Gunicorn `--timeout 120` set
- [ ] `.env` file not publicly accessible (outside web root)
- [ ] PostgreSQL not exposed on public network

---

## 17. Troubleshooting

### App won't start — missing env vars

```
EnvironmentError: Missing required env vars for production: FLASK_SECRET_KEY, DATABASE_URL
```

**Fix:** Ensure `.env` is present and contains all required variables. Check `FLASK_ENV` is set correctly.

---

### Database connection error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Fix:**
```bash
# Check PostgreSQL is running
brew services list | grep postgresql    # macOS
sudo systemctl status postgresql        # Linux

# Start it
brew services start postgresql@14       # macOS
sudo systemctl start postgresql         # Linux

# Verify DATABASE_URL format
# postgresql://username:password@host:port/dbname
# Local no-password: postgresql://localhost/mashroom_ocr
```

---

### `flask db upgrade` — relation does not exist

```
sqlalchemy.exc.ProgrammingError: table "alembic_version" does not exist
```

**Fix:** Database may not exist. Create it first:
```bash
createdb mashroom_ocr
flask db upgrade
```

---

### PDF fails — poppler not found

```
RuntimeError: pdf2image is not installed. ... Also install poppler
```
or
```
pdf2image.exceptions.PDFInfoNotInstalledError
```

**Fix:**
```bash
brew install poppler           # macOS
sudo apt-get install poppler-utils  # Ubuntu
```

---

### File upload rejected — wrong type

```
Unsupported file type. Allowed: bmp, jpeg, jpg, pdf, png, tiff, tif, webp
```

**Fix:** Ensure file has correct extension. MIME type is not checked — only extension.  
To add a new extension, edit `ALLOWED_EXTENSIONS` in `config.py`.

---

### Claude returns invalid JSON

```
JSON parse failed — returning raw text. Error: ...
```

This is handled gracefully. The raw Claude text is returned under `raw_text`, and `parse_error` is added to the result dict. The page still appears in results but with empty data.

**Diagnosis:** Enable debug logging and inspect the raw Claude response. Usually caused by very complex or illegible documents.

---

### `flask create-admin` — zsh glob error

```
zsh: no matches found: Dots@123#?
```

**Fix:** Wrap password in single quotes to prevent shell interpretation:
```bash
flask create-admin admin@example.com 'Dots@123#?'
```

---

### Excel download — empty or broken file

Symptoms: `.xlsx` downloads but opens as empty or corrupted.

**Diagnosis:**
1. Check that `result_json` is not null in the DB:
   ```python
   job = Job.query.get("job-id-here")
   print(job.result_json[:200])
   ```
2. Check `job.get_data()` returns non-empty dict
3. Ensure `pages` and `all_pickers` arrays are populated

---

### Admin panel — "Admin access required" error

User sees 403 when accessing `/admin/users`.

**Fix:** The logged-in user's `is_admin` column is `False`. Either:
- Use `flask create-admin` CLI to create a proper admin
- Or update via psql: `UPDATE users SET is_admin = true WHERE email = 'user@example.com';`

---

### Image quality / OCR accuracy poor

- Increase scan DPI (300 DPI minimum recommended)
- Ensure document is not rotated more than 45° (Claude handles up to 90°/270° rotation)
- Use a named template instead of "Auto-detect" for known form types
- Check if the `note` field in the template accurately describes the document structure

---

*End of Developer Guide*
