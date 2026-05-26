"""
API routes — health check + JSON extraction endpoint.
"""

import logging

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from ocr_processor import process_bytes
from utils import allowed_file, get_api_key

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok", "api_key_set": bool(get_api_key())})


@api_bp.post("/api/extract")
def extract():
    """
    Programmatic JSON extraction endpoint.

    Request:  multipart/form-data — field 'file' + optional 'template_id'
    Response: application/json

    curl -X POST http://localhost:5000/api/extract \\
         -F "file=@scan.pdf" \\
         -F "template_id=non_pick_time"
    """
    if "file" not in request.files:
        return jsonify({"error": "No file field in request"}), 400

    file = request.files["file"]
    if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
        return jsonify({"error": "Unsupported file type"}), 400

    api_key = get_api_key()
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    template_id    = request.form.get("template_id", "auto")
    template_by_id = current_app.config["OCR_TEMPLATE_BY_ID"]
    template       = template_by_id.get(template_id, template_by_id["auto"])
    raw            = file.read()
    filename       = secure_filename(file.filename)

    try:
        result = process_bytes(raw, filename, api_key=api_key, template=template)
        return jsonify(result)
    except Exception as exc:
        logger.exception("API extraction failed for '%s'", filename)
        return jsonify({"error": str(exc)}), 500
