"""
Shared utilities — decorators, helpers, template loader.
No Flask app or route logic here.
"""

import functools
import json
import logging
import os
from pathlib import Path

from flask import render_template
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

def allowed_file(filename: str, allowed: set[str]) -> bool:
    """Return True if filename has an allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------

def get_api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def admin_required(f):
    """Decorator: user must be authenticated AND is_admin=True."""
    @functools.wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            return render_template("login.html", error="Admin access required."), 403
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# OCR template loader
# ---------------------------------------------------------------------------

def load_ocr_templates(path: Path) -> tuple[list[dict], dict[str, dict]]:
    """
    Load template definitions from templates.json.
    Returns (templates_list, templates_by_id_dict).
    Falls back to auto-detect only on any read/parse error.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            templates: list[dict] = json.load(fh)["templates"]
    except Exception as exc:
        logger.warning("Could not load templates.json: %s", exc)
        templates = [{"id": "auto", "name": "Auto-detect (generic)", "columns": []}]

    by_id: dict[str, dict] = {t["id"]: t for t in templates}
    return templates, by_id


# ---------------------------------------------------------------------------
# Column header helpers
# ---------------------------------------------------------------------------

def build_headers_and_labels(
    data: dict, template: dict
) -> tuple[list[str], dict[str, str]]:
    """
    Derive ordered column key list and human-readable label map
    from extraction result + template definition.
    """
    tpl_cols: list[dict] = template.get("columns", [])
    all_headers: list[str] = []

    if tpl_cols and template.get("id") != "auto":
        all_headers = [c["key"] for c in tpl_cols]
    else:
        seen: set[str] = set()
        for page in data.get("pages", []):
            for h in page.get("column_headers", []):
                if h not in seen:
                    all_headers.append(h)
                    seen.add(h)
        for row in data.get("all_pickers", []):
            for h in row.get("fields", row.get("quantities", {})):
                if h not in seen:
                    all_headers.append(h)
                    seen.add(h)

    header_labels: dict[str, str] = (
        {c["key"]: c["label"] for c in tpl_cols}
        if tpl_cols
        else {h: h.replace("_", " ") for h in all_headers}
    )
    return all_headers, header_labels
