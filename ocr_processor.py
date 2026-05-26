"""
OCR Processor — uses Claude Vision API to extract handwritten data from
scanned harvest picking-record sheets (PDF or image).

Supports:
  • PDF  → converted to images via pdf2image (requires poppler)
  • JPEG / PNG / TIFF / BMP → processed directly

Returns a dict with:
  document_info  – header fields (date, doc ref, day no …)
  pickers        – list of per-picker rows with all extracted columns
  raw_text       – verbatim transcription returned by Claude
"""

import base64
import io
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import anthropic
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
SUPPORTED_PDF_TYPES   = {".pdf"}

CLAUDE_MODEL = "claude-sonnet-4-6"  # great vision accuracy, 5x cheaper than Opus

SYSTEM_PROMPT = """You are an expert OCR system for ANY handwritten or printed tabular form.
You must handle every document structure you encounter. NEVER assume field names — derive ALL column keys from the actual document headers.

━━━ ORIENTATION ━━━
Documents may be landscape, portrait, or rotated 90°/270°.
If text runs sideways, mentally rotate first, then read normally.

━━━ HEADER STRUCTURES (handle all of these) ━━━

1. SINGLE-ROW HEADERS — simplest case.
   Use each header cell text as the column key.

2. MERGED PARENT + SUB-COLUMNS — parent spans multiple columns:
   ┌──────────────┬────────────────────────────────────┐
   │              │    Gate sensor - Check result      │
   │ Emergency    ├──────────┬──────────┬──────────────┤
   │ Stop Result  │ L Side   │ R Side   │ R Side       │
   │              │ (Front)  │ (Front)  │ (Back)       │
   ├──────────────┼──────────┼──────────┼──────────────┤
   → keys: "Emergency_Stop_Result", "GateSensor_L_Side_Front",
           "GateSensor_R_Side_Front", "GateSensor_R_Side_Back"

3. STACKED SUB-ROWS UNDER ONE COLUMN — multiple label rows under a group header:
   ┌─────────────────┐
   │   Category A    │  ← group / product name
   ├────────┬────────┤
   │ Count  │ Weight │  ← sub-row labels become part of the key
   ├────────┼────────┤
   → keys: "Category_A_Count", "Category_A_Weight"

4. BLANK FIRST COLUMN — no header text in leftmost column:
   That column holds row identifiers (Platform A, item name, record ID, etc.).
   Use it as "row_label". Do NOT invent a column key for it.

5. DARK / SHADED HEADER ROWS — read white-on-dark text carefully.
   Header text color doesn't change interpretation.

━━━ ORIENTATION OF DATA ━━━
- Normal: rows = records, columns = fields → output one row per data row.
- Rotated / transposed: if columns are records and rows are fields, transpose mentally so each record becomes one output row.

━━━ READING RULES ━━━
- Column keys come ONLY from the document. Never invent names.
- Handwritten values: ok / not ok / pass / fail / working / numbers — read carefully.
- Empty or dash cell → null. Illegible → best guess + "?" suffix.
- Preserve numbers exactly — misread digits corrupt records.
"""

EXTRACTION_PROMPT = """Analyse this form image. Return ONE valid JSON object only.
No markdown fences, no prose — raw JSON only.

STEP 1 — ORIENT THE DOCUMENT
Is the document rotated? If text runs sideways, rotate mentally so headers are at top.

STEP 2 — IDENTIFY HEADER STRUCTURE
Count header rows (may be 1, 2, or 3 levels). For each column, build the full key by
joining ALL ancestor header text with underscores, outermost (top/left) parent FIRST,
then sub-column, removing special chars, colons, and extra spaces.

KEY NAMING RULE — parent always comes first, sub-column always comes last:
  • Single level: "Date" → "Date"
  • Parent + sub: parent="Gate sensor Check result", sub="L Side Front" → "GateSensor_Check_Result_L_Side_Front"
  • Group + sub-row: group="Category A", sub="Count" → "Category_A_Count"
  • Group + sub-row: group="Category A", sub="Batch Ref" → "Category_A_Batch_Ref"
  • NEVER put the sub-column name before the parent: "Batch_Ref_Category_A" is WRONG
  • Blank first col header → that column = row_label, exclude from column_headers

CONSISTENCY CHECK: Every column key in column_headers must follow the same
parent_first → sub_last order. Review before outputting.

STEP 3 — EXTRACT EVERY ROW
One entry in "rows" per data record. Map each cell to its full combined key.
If data layout is transposed (columns = records), transpose before outputting.

OUTPUT SCHEMA — return exactly this structure, all keys present:
{
  "document_info": {
    "title": null,
    "doc_ref": null,
    "date": null,
    "location": null,
    "supervisor": null,
    "additional_fields": {}
  },
  "column_headers": [
    "<full combined column key, exactly as used in fields{}>"
  ],
  "rows": [
    {
      "row_label": "<leftmost cell value: platform / name / identifier — or null if not applicable>",
      "team": null,
      "name": null,
      "record_id": null,
      "start_time": null,
      "end_time": null,
      "fields": {
        "<column_header_key>": "<cell value or null>"
      },
      "notes": null
    }
  ],
  "raw_text": "<one-sentence description of what type of document this is>"
}

STRICT RULES:
- "column_headers" must list EVERY key that appears in any row's fields{}
- fields{} keys must match column_headers entries exactly — no extras, no omissions
- Do NOT invent field names — use only what the document contains
- Ambiguous handwriting → best guess with "?" suffix, e.g. "ok?" or "47?"
- Blank / dash / empty cell → null
- If a table continues across multiple pages, treat it as one continuous table — rows carry over from previous pages.
- document_info.additional_fields: capture any header fields not covered by standard keys
- Return ONLY the raw JSON object — no markdown, no prose, no explanation
"""

# ---------------------------------------------------------------------------
# Stage 1 constants — ParseBench-derived document structure prompts
# Source: LlamaIndex ParseBench study (prompts by Umair Ali Khan, Ph.D.)
# Proven to outperform specialised parsers on messy real-world documents by
# asking the LLM to encode tables as HTML with colspan/rowspan rather than
# flat Markdown — preserving merged cells and multi-level headers exactly.
# ---------------------------------------------------------------------------

PARSE_SYSTEM_PROMPT = """You are a document parser. Your task is to accurately \
extract all content from the document image, preserving the exact layout and structure.

Guidelines:
- Preserve the document structure, including headings, paragraphs, and tables.
- Convert ALL tables to HTML using <table>, <tr>, <th>, and <td> tags.
- For merged or spanned cells, use colspan and rowspan to encode the exact 2-D
  structure as it appears in the document.
- For multi-level headers (a parent header spanning sub-columns), use
  <th colspan="N"> for the parent and place sub-column headers in a subsequent <tr>.
- For charts or graphs converted to tables, use flat combined column headers so
  each data cell includes all its labels.
- Describe images and figures briefly in square brackets, e.g. [Figure: company logo].
- Maintain reading order: left to right, top to bottom.
- Do not add commentary or explanations. Output only the parsed content.

Wrap each layout element in a <div data-label="<category>"> tag where category is
one of: Title, Heading, Table, Paragraph, Figure, Caption, Header, Footer.
Place elements in reading order. Every piece of content must be included."""

PARSE_USER_PROMPT = """Parse this document page and output its full content as structured HTML.
Use HTML tables with colspan and rowspan for ALL tabular data.
If a table continues across multiple pages, merge all parts into one complete table — do not repeat headers for continuations.
Output only the structured HTML — no markdown fences, no commentary."""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pil_to_base64(img: Image.Image, quality: int = 88) -> str:
    """Encode PIL image as JPEG base64. Auto-reduce quality if > 4.5 MB."""
    data = b""
    for q in (quality, 75, 60, 45):
        buf = io.BytesIO()
        try:
            img.save(buf, format="JPEG", quality=q, optimize=True)
            data = buf.getvalue()
        finally:
            buf.close()
        if len(data) < 4_500_000:          # stay under Claude 5 MB limit
            return base64.standard_b64encode(data).decode()
    raise ValueError(f"Image too large even at lowest quality: {len(data):,} bytes")


def _images_from_pdf(path: str) -> list[Image.Image]:
    """Convert all pages of a PDF to PIL images (requires poppler)."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError(
            "pdf2image is not installed. Run: pip install pdf2image\n"
            "Also install poppler: brew install poppler (macOS) "
            "or apt-get install poppler-utils (Linux)"
        )
    return convert_from_path(path, dpi=300)


def _load_images(file_path: str) -> list[Image.Image]:
    """Return a list of PIL images from the given file (PDF or image)."""
    suffix = Path(file_path).suffix.lower()
    if suffix in SUPPORTED_PDF_TYPES:
        return _images_from_pdf(file_path)
    elif suffix in SUPPORTED_IMAGE_TYPES:
        return [Image.open(file_path).convert("RGB")]
    else:
        raise ValueError(
            f"Unsupported file type '{suffix}'. "
            f"Supported: {SUPPORTED_PDF_TYPES | SUPPORTED_IMAGE_TYPES}"
        )


MAX_DIM = 2000   # Claude reads fine at 2000px; beyond this = diminishing returns

def _preprocess(img: Image.Image) -> Image.Image:
    """Resize to safe dimensions + convert to RGB."""
    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    long = max(w, h)

    # Scale UP only if very small (below 1000px)
    if long < 1000:
        scale = 1000 / long
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        w, h = img.size
        long = max(w, h)

    # Always scale DOWN if above MAX_DIM
    if long > MAX_DIM:
        scale = MAX_DIM / long
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    return img


def _build_template_prompt(template: dict) -> str:
    """Build a column-locked extraction prompt from a template definition."""
    cols = template.get("columns", [])
    if not cols:
        return EXTRACTION_PROMPT  # fall back to generic

    keys      = [c["key"]   for c in cols]
    labels    = [c["label"] for c in cols]
    note      = template.get("note", "")
    tpl_name  = template.get("name", "")

    col_lines = "\n".join(
        f'    "{k}":  null   // reads from column headed "{l}"'
        for k, l in zip(keys, labels)
    )
    keys_list = json.dumps(keys, ensure_ascii=False)

    col_index = "\n".join(
        f'  {i+1:>2}. key="{k}"  ←  column headed "{l}"'
        for i, (k, l) in enumerate(zip(keys, labels))
    )

    note_block = f"\nDOCUMENT NOTE: {note}\n" if note else ""

    return f"""Analyse this form image. Return ONE valid JSON object only.
No markdown fences, no prose — raw JSON only.

TEMPLATE MODE — document type: {tpl_name}
Column names are PRE-DEFINED. Do NOT invent, rename, or reorder keys.{note_block}

COLUMN MAP (use these exact keys):
{col_index}

READING RULES:
1. Locate each column by matching its label text in the printed document header.
2. The header may span 2–3 rows (merged cells) — read ALL header rows to identify columns.
3. Handwritten values appear in the DATA rows BELOW the printed header — read those.
4. If a printed header contains handwritten text mixed in, treat printed text = column name,
   handwritten text = cell value for that row.
5. row_label = leftmost identifier cell (Platform A / Platform B / name) if present, else null.
6. Empty / dash / blank cell → null. Illegible → best guess + "?" suffix.
7. Use ONLY the keys listed above — no extras.

OUTPUT SCHEMA:
{{
  "document_info": {{
    "title": null,
    "doc_ref": null,
    "date": null,
    "location": null,
    "supervisor": null,
    "additional_fields": {{}}
  }},
  "column_headers": {keys_list},
  "rows": [
    {{
      "row_label": "<Platform A / Platform B / name / null>",
      "name": null,
      "record_id": null,
      "start_time": null,
      "end_time": null,
      "fields": {{
{col_lines}
      }},
      "notes": null
    }}
  ],
  "raw_text": "<one-sentence description of this document>"
}}

RULES:
- fields keys must EXACTLY match column_headers list — no extras, no missing
- Ambiguous cell → append "?" e.g. "ok?" or "47?"
- Return ONLY raw JSON — no markdown, no explanation
"""


def _parse_image_to_html(client: anthropic.Anthropic, img: Image.Image) -> str:
    """Stage 1 — vision call: convert page image to structured HTML.

    Uses ParseBench-derived prompts so tables are encoded with colspan/rowspan,
    preserving merged cells and multi-level headers exactly.
    """
    img = _preprocess(img)
    b64 = _pil_to_base64(img)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8096,
        system=PARSE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": PARSE_USER_PROMPT},
                ],
            }
        ],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:html)?\s*", "", raw)
    raw = re.sub(r"\s*```$",          "", raw)
    return raw


def _extract_json_from_html(
    client: anthropic.Anthropic,
    html: str,
    template: dict | None = None,
) -> dict[str, Any]:
    """Stage 2 — text-only call: extract structured JSON from HTML content.

    Cheaper than a vision call (no image payload).  The HTML from stage 1
    encodes the full table structure via colspan/rowspan, so Claude can derive
    correct multi-level column keys without guessing from pixel layout.
    """
    extraction_schema = (
        _build_template_prompt(template)
        if template and template.get("id") != "auto" and template.get("columns")
        else EXTRACTION_PROMPT
    )

    user_message = (
        "The document page below has been parsed into structured HTML.\n"
        "Tables use colspan and rowspan to encode merged cells and multi-level headers exactly.\n\n"
        f"{html}\n\n"
        "Using the HTML above as the source of truth for all table structure and cell values:\n"
        f"{extraction_schema}"
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$",          "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Stage-2 JSON parse failed — returning raw text. Error: %s", exc)
        return {
            "document_info": {},
            "column_headers": [],
            "rows": [],
            "raw_text": raw,
            "parse_error": str(exc),
        }


def _call_claude(
    client: anthropic.Anthropic,
    img: Image.Image,
    template: dict | None = None,
) -> dict[str, Any]:
    """Two-stage extraction: image → HTML (stage 1) → JSON (stage 2).

    Stage 1 uses ParseBench HTML prompts for accurate structure preservation.
    Stage 2 is a cheap text-only call that extracts JSON from the clean HTML.
    """
    html = _parse_image_to_html(client, img)
    return _extract_json_from_html(client, html, template=template)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_file(
    file_path: str,
    api_key: str | None = None,
    template: dict | None = None,
) -> dict[str, Any]:
    """
    Main entry point.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the uploaded file (PDF or image).
    api_key : str | None
        Anthropic API key. Falls back to the ANTHROPIC_API_KEY env variable.
    template : dict | None
        Template definition from templates.json. When supplied (and not "auto"),
        Claude is given exact column keys — no key naming guesswork.

    Returns
    -------
    dict
        {
          "pages":        [ <per-page extraction dict> ],
          "summary":      <merged top-level document_info>,
          "all_pickers":  [ <combined row list> ],
          "template_id":  <id of template used, or "auto">
        }
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Set it in your .env file or export it as an environment variable."
        )

    client = anthropic.Anthropic(api_key=key)
    images = _load_images(file_path)

    logger.info(
        "Processing %d page(s) from '%s' [template=%s]",
        len(images), file_path,
        template.get("id", "auto") if template else "auto",
    )

    pages: list[dict] = []
    all_pickers: list[dict] = []
    summary_info: dict = {}

    for page_num, img in enumerate(images, start=1):
        logger.info("  → page %d / %d", page_num, len(images))
        result = _call_claude(client, img, template=template)
        result["page_number"] = page_num
        pages.append(result)

        if not summary_info and result.get("document_info"):
            summary_info = result["document_info"]

        for row in result.get("rows", result.get("pickers", [])):
            row["_page"] = page_num
            all_pickers.append(row)

    return {
        "pages":       pages,
        "summary":     summary_info,
        "all_pickers": all_pickers,
        "template_id": template.get("id", "auto") if template else "auto",
    }


def process_bytes(
    file_bytes: bytes,
    filename: str,
    api_key: str | None = None,
    template: dict | None = None,
) -> dict[str, Any]:
    """
    Process a file supplied as raw bytes (e.g. from a web upload).
    Writes a temporary file, delegates to process_file, then cleans up.
    """
    import tempfile

    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        return process_file(tmp_path, api_key=api_key, template=template)
    finally:
        os.unlink(tmp_path)
