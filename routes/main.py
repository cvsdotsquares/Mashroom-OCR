"""
Main routes — upload, results, history, Excel download.
"""

import json
import logging
import uuid
from pathlib import Path

from flask import (
    Blueprint, current_app, jsonify, redirect,
    render_template, request, send_file, url_for,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from excel_exporter import make_excel
from models import Job
from ocr_processor import process_bytes
from utils import allowed_file, get_api_key, build_headers_and_labels

logger   = logging.getLogger(__name__)
main_bp  = Blueprint("main", __name__)


@main_bp.get("/")
@login_required
def index():
    templates = current_app.config["OCR_TEMPLATES"]
    return render_template("index.html", templates=templates)


@main_bp.post("/upload")
@login_required
def upload():
    templates = current_app.config["OCR_TEMPLATES"]
    template_by_id = current_app.config["OCR_TEMPLATE_BY_ID"]

    if "file" not in request.files:
        return render_template("index.html", templates=templates,
                               error="No file selected."), 400

    file = request.files["file"]
    if not file.filename:
        return render_template("index.html", templates=templates,
                               error="No file selected."), 400

    if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        allowed = ", ".join(sorted(current_app.config["ALLOWED_EXTENSIONS"]))
        return render_template("index.html", templates=templates,
                               error=f"Unsupported file type. Allowed: {allowed}"), 400

    api_key = get_api_key()
    if not api_key:
        return render_template("index.html", templates=templates,
                               error="ANTHROPIC_API_KEY is not configured."), 500

    template_id = request.form.get("template_id", "auto")
    template    = template_by_id.get(template_id, template_by_id["auto"])
    raw         = file.read()
    filename    = secure_filename(file.filename)

    try:
        result = process_bytes(raw, filename, api_key=api_key, template=template)
    except Exception as exc:
        logger.exception("Processing failed for '%s'", filename)
        return render_template("index.html", templates=templates,
                               error=f"Processing error: {exc}"), 500

    job = Job(
        id          = str(uuid.uuid4()),
        user_id     = current_user.id,
        filename    = filename,
        template_id = template_id,
        result_json = json.dumps(result, ensure_ascii=False),
    )
    db.session.add(job)
    db.session.commit()

    return redirect(url_for("main.results", job_id=job.id))


@main_bp.get("/results/<job_id>")
@login_required
def results(job_id: str):
    templates      = current_app.config["OCR_TEMPLATES"]
    template_by_id = current_app.config["OCR_TEMPLATE_BY_ID"]

    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first()
    if not job:
        return render_template("index.html", templates=templates,
                               error="Result not found or expired."), 404

    data                    = job.get_data()
    template                = job.get_template(template_by_id)
    all_headers, hdr_labels = build_headers_and_labels(data, template)

    return render_template(
        "index.html",
        templates    = templates,
        filename     = job.filename,
        template     = template,
        summary      = data.get("summary", {}),
        all_headers  = all_headers,
        header_labels= hdr_labels,
        all_pickers  = data.get("all_pickers", []),
        pages        = data.get("pages", []),
        raw_json     = json.dumps(data, indent=2, ensure_ascii=False),
        job_id       = job_id,
    )


@main_bp.get("/history")
@login_required
def history():
    templates = current_app.config["OCR_TEMPLATES"]
    jobs = (
        Job.query
        .filter_by(user_id=current_user.id)
        .order_by(Job.created_at.desc())
        .all()
    )
    return render_template("history.html", jobs=jobs, templates=templates)


@main_bp.get("/download_excel/<job_id>")
@login_required
def download_excel(job_id: str):
    job = Job.query.filter_by(id=job_id, user_id=current_user.id).first()
    if not job:
        return jsonify({"error": "Result not found or expired"}), 404

    buf     = make_excel(job)
    dl_name = f"{Path(job.filename).stem}_extracted.xlsx"

    return send_file(
        buf,
        mimetype     = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment= True,
        download_name= dl_name,
    )
