# Mashroom OCR

Mashroom OCR is a Flask web application for extracting structured data from scanned PDF and image forms. It uses Claude Vision to interpret handwritten or printed tables, stores extraction jobs per user, and exports results to formatted Excel workbooks.

## Features

- PDF and image uploads (`pdf`, `png`, `jpg`, `jpeg`, `tiff`, `bmp`, `webp`)
- Two-stage OCR pipeline: document image to structured HTML, then HTML to JSON
- Generic auto-detection plus fixed extraction templates for known forms
- User authentication with admin-managed accounts
- Per-user extraction history and result viewing
- Excel export with uncertain values flagged for review
- JSON extraction API for integrations

## Supported Templates

| Template ID | Document Type | Columns |
| --- | --- | ---: |
| `auto` | Generic auto-detection | Determined from document |
| `ms_prestart` | MS Pre-start Checks | 16 |
| `hughes_daily_picking` | Hughes Group Daily Picking Record | 15 |
| `non_pick_time` | Non-Pick Time Record | 14 |

Template definitions are stored in `templates.json` and loaded when the application starts.

## Requirements

- Python 3.11+
- PostgreSQL
- An Anthropic API key
- Poppler for PDF uploads

On Windows, ensure the Poppler `Library\bin` directory is on `PATH`. For example:

```text
C:\poppler\Library\bin
```

Verify Poppler is available:

```powershell
pdfinfo -v
pdftoppm -v
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your local values:

```env
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=postgresql://username:password@localhost:5432/mashroom_ocr
FLASK_SECRET_KEY=replace-with-a-long-random-secret
FLASK_DEBUG=true
PORT=5000
```

Create the database before starting the application. The project includes Flask-Migrate setup, but this checkout does not currently include generated migration revision files. For local development, running `app.py` creates the defined tables when needed.

Create the initial admin user:

```powershell
$env:FLASK_APP = "app.py"
flask create-admin admin@example.com "StrongPassword123"
```

## Run

```powershell
.\.venv\Scripts\python.exe app.py
```

Open `http://localhost:5000`, sign in, choose a template, and upload a document.

## How Extraction Works

1. An authenticated user uploads an image or PDF and optionally selects a template.
2. PDF pages are rendered to images through Poppler.
3. Claude converts each page image to structured HTML, preserving table layout and merged headers.
4. Claude converts the structured HTML to JSON using either detected headings or fixed template column keys.
5. The application saves the extraction as a job associated with the user.
6. Users can view results, review uncertain readings marked with `?`, or download Excel output.

## API

Health check:

```http
GET /health
```

Extract a document:

```powershell
curl.exe -X POST http://localhost:5000/api/extract `
  -F "file=@samples/sample_01.pdf" `
  -F "template_id=non_pick_time"
```

The API endpoint uses the same OCR pipeline as the web interface and returns JSON.

## Tests

The OCR test suite mocks Claude API responses and does not transmit documents externally.

```powershell
.\.venv\Scripts\python.exe -m unittest test_ocr -v
```

The current suite contains 82 passing tests covering image preprocessing, template prompts, table structure handling, and the two-stage extraction pipeline.

## Project Structure

```text
app.py                 Flask application factory and CLI
auth.py                Login and logout routes
config.py              Environment configuration
models.py              User and extraction job models
ocr_processor.py       OCR and Claude integration
excel_exporter.py      XLSX generation
routes/                Main, admin, and API routes
templates/             HTML user interface
templates.json         Document extraction templates
samples/               Example PDF files
test_ocr.py            OCR unit tests
DEVELOPER_GUIDE.md     Detailed developer documentation
```

## Deployment Notes

- Do not commit `.env`; it may contain API keys and database credentials.
- `POST /api/extract` is currently unauthenticated and should be protected before public deployment.
- Form submissions do not currently include active CSRF protection; add it before exposing the administration interface publicly.
- Generate and commit database migration revisions before deploying to a clean environment.
