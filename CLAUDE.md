# Mashroom OCR — Project Context

## Purpose
Web app extracting structured data from handwritten/printed agricultural forms
using Claude Vision AI. Client: agricultural operations company.

## Tech Stack
| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | Flask 3.0.3 — App Factory + Blueprint pattern |
| Database | PostgreSQL via Flask-SQLAlchemy 3.1.1 |
| Auth | Flask-Login + Flask-Bcrypt |
| Migrations | Flask-Migrate (Alembic) |
| AI | Anthropic Claude claude-sonnet-4-6 (Vision) |
| PDF→Image | pdf2image + poppler |
| Excel | openpyxl 3.1.5 |
| Config | python-dotenv |

## Architecture Patterns
- **App Factory:** `create_app()` in `app.py`
- **Singleton:** `extensions.py` — db, bcrypt, login_manager, migrate (never re-instantiate elsewhere)
- **Blueprints:** auth_bp, main_bp (prefix: none), admin_bp (prefix: /admin), api_bp
- **No circular imports:** extensions.py is the shared hub

## OCR Pipeline (Two-Stage — Phase 2)
```
Image
  → Stage 1: _parse_image_to_html()   — vision call, ParseBench prompts
      outputs HTML with colspan/rowspan (merged cells preserved exactly)
  → Stage 2: _extract_json_from_html() — text-only call (cheap)
      HTML → JSON matching existing schema
```
Phase 1: merge_table instruction in EXTRACTION_PROMPT + PARSE_USER_PROMPT.

## Key Files
| File | Role |
|---|---|
| `app.py` | Factory + CLI (`flask create-admin`) |
| `config.py` | Dev/Prod/Test config classes + `config_map` |
| `extensions.py` | Singleton Flask extensions |
| `models.py` | User, Job ORM models |
| `auth.py` | Login/logout blueprint |
| `utils.py` | `admin_required` decorator, `allowed_file`, template loader |
| `ocr_processor.py` | Core OCR — two-stage Claude pipeline |
| `excel_exporter.py` | .xlsx generation (Summary + Flagged for Review + Page sheets) |
| `routes/main.py` | Upload, results, history, Excel download |
| `routes/admin.py` | User management (admin only) |
| `routes/api.py` | `/health` + `/api/extract` REST API |
| `templates.json` | OCR column maps (auto, ms_prestart, hughes_daily_picking, non_pick_time) |
| `test_ocr.py` | 82 unit tests — no real API calls, all mocked |
| `DEVELOPER_GUIDE.md` | 1146-line full developer documentation |

## Database
- Local: `postgresql://localhost/mashroom_ocr`
- Tables: `users` (id, email, password_hash, is_admin, created_at)
          `jobs` (id UUID, user_id FK, filename, template_id, result_json TEXT, created_at)
- First admin: `flask create-admin email@x.com 'password'`
- **zsh gotcha:** wrap passwords with special chars (#?!) in single quotes

## Known Issues / Backlog
- `_DOC_FIELD_MAP` dict recreated inside page loop in `excel_exporter.py:138` → move to module level
- `/api/extract` has no auth → add API key header check before public deployment
- `make_excel()` is 191 lines → refactor `_write_page_sheet()` helper (low priority)
- **Phase 3 (future):** replace pdf2image/poppler with direct PDF base64 → Claude document API

## Hosting (for client)
- 2–4 vCPU, 2–4 GB RAM, 20–40 GB SSD, Ubuntu 22.04 LTS
- poppler-utils, nginx, Gunicorn `--timeout 120`
- Anthropic API key required
