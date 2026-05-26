"""
Unit tests for ocr_processor.py — no API calls required.

Tests cover:
  1. Image preprocessing (resize logic)
  2. JPEG encoding size guard
  3. JSON parse + fallback on bad JSON
  4. Result-merging logic (process_file return shape)
  5. Row/header routing — all 5 document structure types:
       a. Single-row headers (Non-Pick Time Record)
       b. Merged parent + sub-columns (MS Pre-start Checks)
       c. Stacked sub-rows under product (Hughes Group picking)
       d. Blank first column → row_label
       e. Mixed: multi-level + blank first col
  6. Backward-compat: legacy "pickers" + "quantities" keys still work
"""

import base64
import io
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image

# ---------------------------------------------------------------------------
# Import module under test
# ---------------------------------------------------------------------------
sys.path.insert(0, ".")
import ocr_processor as ocrm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image(w=800, h=600, color=(200, 200, 200)) -> Image.Image:
    return Image.new("RGB", (w, h), color)


def _fake_claude_response(payload: dict):
    """Build a mock anthropic response object wrapping payload as JSON."""
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(payload))]
    return msg


def _fake_html_response(html: str = "<table><tr><td>ok</td></tr></table>"):
    """Build a mock anthropic response wrapping HTML for stage-1 tests."""
    msg = MagicMock()
    msg.content = [MagicMock(text=html)]
    return msg


# ---------------------------------------------------------------------------
# 1. Preprocessing
# ---------------------------------------------------------------------------

class TestPreprocess(unittest.TestCase):

    def test_small_image_upscaled(self):
        img = _make_image(400, 300)
        out = ocrm._preprocess(img)
        self.assertGreaterEqual(min(out.size), 1000 * 300 // 400)  # proportional

    def test_large_image_downscaled(self):
        img = _make_image(5000, 4000)
        out = ocrm._preprocess(img)
        self.assertLessEqual(max(out.size), ocrm.MAX_DIM)

    def test_already_in_range_unchanged(self):
        img = _make_image(1200, 900)
        out = ocrm._preprocess(img)
        self.assertEqual(max(out.size), 1200)

    def test_rgba_converted_to_rgb(self):
        img = Image.new("RGBA", (800, 600), (100, 100, 100, 128))
        out = ocrm._preprocess(img)
        self.assertEqual(out.mode, "RGB")


# ---------------------------------------------------------------------------
# 2. JPEG size guard
# ---------------------------------------------------------------------------

class TestPilToBase64(unittest.TestCase):

    def test_output_is_valid_base64_jpeg(self):
        img = _make_image(200, 200)
        b64 = ocrm._pil_to_base64(img)
        raw = base64.standard_b64decode(b64)
        # JPEG magic bytes
        self.assertEqual(raw[:2], b"\xff\xd8")

    def test_output_under_size_limit(self):
        img = _make_image(2000, 2000)
        b64 = ocrm._pil_to_base64(img)
        self.assertLess(len(base64.standard_b64decode(b64)), 4_500_000)


# ---------------------------------------------------------------------------
# 3. JSON parse + fallback
# ---------------------------------------------------------------------------

class TestCallClaude(unittest.TestCase):
    """Two-stage pipeline: stage 1 returns HTML, stage 2 returns JSON."""

    def _run(self, payload):
        """Helper: wire stage-1 HTML mock + stage-2 JSON mock, run _call_claude."""
        client = MagicMock()
        client.messages.create.side_effect = [
            _fake_html_response(),              # stage 1 → HTML
            _fake_claude_response(payload),     # stage 2 → JSON
        ]
        return ocrm._call_claude(client, _make_image())

    def test_valid_json_returned_as_dict(self):
        payload = {"document_info": {}, "column_headers": ["Date"], "rows": [], "raw_text": "test"}
        result = self._run(payload)
        self.assertIsInstance(result, dict)
        self.assertIn("column_headers", result)

    def test_bad_json_returns_fallback(self):
        client = MagicMock()
        client.messages.create.side_effect = [
            _fake_html_response(),
            MagicMock(content=[MagicMock(text="NOT JSON {{{")]),
        ]
        result = ocrm._call_claude(client, _make_image())
        self.assertIn("parse_error", result)
        self.assertIn("raw_text", result)

    def test_markdown_fences_stripped(self):
        client = MagicMock()
        payload = {"document_info": {}, "column_headers": [], "rows": [], "raw_text": "x"}
        fenced = "```json\n" + json.dumps(payload) + "\n```"
        client.messages.create.side_effect = [
            _fake_html_response(),
            MagicMock(content=[MagicMock(text=fenced)]),
        ]
        result = ocrm._call_claude(client, _make_image())
        self.assertNotIn("parse_error", result)
        self.assertEqual(result["rows"], [])


# ---------------------------------------------------------------------------
# 4. Document structure types — row/header routing
#    These simulate what Claude returns and verify app.py can consume it.
# ---------------------------------------------------------------------------

# Simulate app.py's all_headers builder (copy of the logic in results())
def _build_headers(data: dict) -> list:
    all_headers = []
    for page in data.get("pages", []):
        for h in page.get("column_headers", []):
            if h not in all_headers:
                all_headers.append(h)
    for row in data.get("all_pickers", []):
        for h in row.get("fields", row.get("quantities", {})).keys():
            if h not in all_headers:
                all_headers.append(h)
    return all_headers


def _simulate_process(pages: list[dict]) -> dict:
    """Simulate what process_file() returns given a list of per-page dicts."""
    all_pickers = []
    summary_info = {}
    for i, page in enumerate(pages, 1):
        page["page_number"] = i
        if not summary_info and page.get("document_info"):
            summary_info = page["document_info"]
        for row in page.get("rows", page.get("pickers", [])):
            row["_page"] = i
            all_pickers.append(row)
    return {"pages": pages, "summary": summary_info, "all_pickers": all_pickers}


class TestDocumentStructures(unittest.TestCase):

    # 4a. Single-row headers — Non-Pick Time Record
    def test_single_row_headers(self):
        page = {
            "document_info": {"title": "Non-Pick Time Record", "date": "15/04/2024"},
            "column_headers": [
                "Date", "Week_End", "House_Fill_ID", "House", "Platform",
                "Flush", "Day_No", "Picker", "Payroll_No", "System_Belt",
                "Picking_Placing", "Start", "End", "Non_Pick_Time_Mins"
            ],
            "rows": [
                {
                    "row_label": None,
                    "fields": {
                        "Date": "15/04", "Week_End": "19/04", "House_Fill_ID": "HF001",
                        "House": "3", "Platform": "A", "Flush": "2", "Day_No": "5",
                        "Picker": "J Smith", "Payroll_No": "1042", "System_Belt": "ok",
                        "Picking_Placing": "Picking", "Start": "06:00", "End": "07:30",
                        "Non_Pick_Time_Mins": "90"
                    }
                }
            ],
            "raw_text": "Non-pick time record sheet"
        }
        data = _simulate_process([page])
        headers = _build_headers(data)
        self.assertEqual(len(headers), 14)
        self.assertIn("Non_Pick_Time_Mins", headers)
        self.assertEqual(len(data["all_pickers"]), 1)

    # 4b. Merged parent + sub-columns — MS Pre-start Checks
    def test_merged_parent_sub_columns(self):
        page = {
            "document_info": {"title": "MS Pre-start Checks", "date": "15/04/2024"},
            "column_headers": [
                "Emergency_Stop_Result",
                "GateSensor_Check_Result_L_Side_Front",
                "GateSensor_Check_Result_L_Side_Back",
                "GateSensor_Check_Result_R_Side_Front",
                "GateSensor_Check_Result_R_Side_Back",
            ],
            "rows": [
                {
                    "row_label": "Platform A",
                    "fields": {
                        "Emergency_Stop_Result": "ok",
                        "GateSensor_Check_Result_L_Side_Front": "ok",
                        "GateSensor_Check_Result_L_Side_Back": "ok",
                        "GateSensor_Check_Result_R_Side_Front": "ok",
                        "GateSensor_Check_Result_R_Side_Back": "ok",
                    }
                },
                {
                    "row_label": "Platform B",
                    "fields": {
                        "Emergency_Stop_Result": "ok",
                        "GateSensor_Check_Result_L_Side_Front": "not ok",
                        "GateSensor_Check_Result_L_Side_Back": "ok",
                        "GateSensor_Check_Result_R_Side_Front": "ok",
                        "GateSensor_Check_Result_R_Side_Back": "ok",
                    }
                }
            ],
            "raw_text": "Machine safety pre-start checklist"
        }
        data = _simulate_process([page])
        headers = _build_headers(data)
        self.assertEqual(len(headers), 5)
        self.assertIn("GateSensor_Check_Result_L_Side_Front", headers)
        self.assertEqual(len(data["all_pickers"]), 2)
        self.assertEqual(data["all_pickers"][0]["row_label"], "Platform A")
        self.assertEqual(
            data["all_pickers"][1]["fields"]["GateSensor_Check_Result_L_Side_Front"],
            "not ok"
        )

    # 4c. Stacked sub-rows under product — Hughes Group picking record
    def test_stacked_sub_rows_under_product(self):
        products = ["300g_Coop_Cup", "400g_Aldi_Cup", "300g_Tesco", "3kg_Buttons"]
        sub_rows = ["Amount", "Traceability", "Punnet"]
        headers = [f"{p}_{s}" for p in products for s in sub_rows]

        row = {"row_label": "John Doe", "fields": {h: str(i) for i, h in enumerate(headers)}}
        page = {
            "document_info": {"title": "Hughes Group Daily Picking Record"},
            "column_headers": headers,
            "rows": [row]
        }
        data = _simulate_process([page])
        hdrs = _build_headers(data)
        self.assertEqual(len(hdrs), 12)  # 4 products × 3 sub-rows
        self.assertIn("300g_Coop_Cup_Amount", hdrs)
        self.assertIn("3kg_Buttons_Punnet", hdrs)

    # 4d. Blank first column → row_label (no key in column_headers)
    def test_blank_first_col_is_row_label_not_header(self):
        page = {
            "document_info": {},
            "column_headers": ["Check_A", "Check_B"],  # first col NOT listed
            "rows": [
                {"row_label": "Platform A", "fields": {"Check_A": "ok", "Check_B": "ok"}},
                {"row_label": "Platform B", "fields": {"Check_A": "ok", "Check_B": "fail"}},
            ],
            "raw_text": "Pre-start check"
        }
        data = _simulate_process([page])
        hdrs = _build_headers(data)
        # row_label must NOT appear as a column header
        self.assertNotIn("row_label", hdrs)
        self.assertNotIn("Platform A", hdrs)
        self.assertEqual(len(hdrs), 2)

    # 4e. Multi-page: headers merged across pages, _page tag set
    def test_multi_page_header_merge(self):
        page1 = {
            "document_info": {"date": "01/04/2024"},
            "column_headers": ["Col_A", "Col_B"],
            "rows": [{"row_label": "R1", "fields": {"Col_A": "1", "Col_B": "2"}}],
            "raw_text": "page 1"
        }
        page2 = {
            "document_info": {},
            "column_headers": ["Col_B", "Col_C"],  # Col_B overlap
            "rows": [{"row_label": "R2", "fields": {"Col_B": "3", "Col_C": "4"}}],
            "raw_text": "page 2"
        }
        data = _simulate_process([page1, page2])
        hdrs = _build_headers(data)
        self.assertEqual(set(hdrs), {"Col_A", "Col_B", "Col_C"})
        self.assertEqual(data["all_pickers"][0]["_page"], 1)
        self.assertEqual(data["all_pickers"][1]["_page"], 2)


# ---------------------------------------------------------------------------
# 5. Backward compat — legacy "pickers" + "quantities" keys
# ---------------------------------------------------------------------------

class TestBackwardCompat(unittest.TestCase):

    def test_legacy_pickers_key(self):
        page = {
            "document_info": {"title": "Legacy"},
            "column_headers": ["Qty"],
            "pickers": [  # old key
                {"name": "Alice", "quantities": {"Qty": "10"}}
            ],
            "raw_text": "legacy"
        }
        data = _simulate_process([page])
        self.assertEqual(len(data["all_pickers"]), 1)
        self.assertEqual(data["all_pickers"][0]["name"], "Alice")

    def test_legacy_quantities_in_headers(self):
        page = {
            "document_info": {},
            "column_headers": [],  # empty — quantities used as fallback
            "pickers": [
                {"name": "Bob", "quantities": {"HCrop": "5", "Buttons": "3"}}
            ],
            "raw_text": "legacy"
        }
        data = _simulate_process([page])
        hdrs = _build_headers(data)
        self.assertIn("HCrop", hdrs)
        self.assertIn("Buttons", hdrs)


# ---------------------------------------------------------------------------
# 6. Prompt sanity checks — no hardcoded domain terms
# ---------------------------------------------------------------------------

class TestPromptHardcoding(unittest.TestCase):
    # Exact domain-specific terms that must NOT appear anywhere in the prompts.
    # These are client/crop/product names — not generic OCR vocabulary.
    FORBIDDEN = [
        "harvest", "hcrop", "mushroom", "mashroom",
        "punnet", "traceability", "coop", "aldi", "tesco",
        "picker_no",  # renamed to record_id — must not appear in prompts
        "hughes", "pre-start checks",
    ]

    def _check_prompt(self, prompt: str, label: str):
        prompt_lower = prompt.lower()
        for term in self.FORBIDDEN:
            self.assertNotIn(
                term.lower(), prompt_lower,
                msg=f"Hardcoded domain term '{term}' found in {label}"
            )

    def test_system_prompt_no_hardcoded_domain_terms(self):
        self._check_prompt(ocrm.SYSTEM_PROMPT, "SYSTEM_PROMPT")

    def test_extraction_prompt_no_hardcoded_domain_terms(self):
        self._check_prompt(ocrm.EXTRACTION_PROMPT, "EXTRACTION_PROMPT")


# ---------------------------------------------------------------------------
# 7. templates.json — structure + column integrity
#    3 real document types + auto = 4 templates total
# ---------------------------------------------------------------------------

import os

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "templates.json")

def _load_templates() -> list[dict]:
    with open(TEMPLATES_PATH, encoding="utf-8") as f:
        return json.load(f)["templates"]


class TestTemplatesJson(unittest.TestCase):

    def setUp(self):
        self.templates = _load_templates()
        self.by_id = {t["id"]: t for t in self.templates}

    # 7a. Exactly 4 templates — auto + 3 real document types
    def test_exactly_4_templates(self):
        self.assertEqual(len(self.templates), 4,
            msg=f"Expected 4 templates, got {len(self.templates)}: {[t['id'] for t in self.templates]}")

    def test_required_template_ids_present(self):
        required = {"auto", "ms_prestart", "hughes_daily_picking", "non_pick_time"}
        found = {t["id"] for t in self.templates}
        self.assertEqual(required, found, msg=f"Missing: {required - found}, extra: {found - required}")

    # 7b. Old split MS Pre-start templates removed
    def test_old_split_ms_templates_removed(self):
        ids = {t["id"] for t in self.templates}
        self.assertNotIn("ms_prestart_machine", ids)
        self.assertNotIn("ms_prestart_picker",  ids)
        self.assertNotIn("ms_prestart_full",    ids)

    # 7c. Every template has id, name, columns list
    def test_every_template_has_required_fields(self):
        for t in self.templates:
            self.assertIn("id",      t, msg=f"Template missing 'id': {t}")
            self.assertIn("name",    t, msg=f"Template '{t['id']}' missing 'name'")
            self.assertIn("columns", t, msg=f"Template '{t['id']}' missing 'columns'")

    # 7d. Every column has key + label
    def test_every_column_has_key_and_label(self):
        for t in self.templates:
            for col in t.get("columns", []):
                self.assertIn("key",   col, msg=f"Column in '{t['id']}' missing 'key': {col}")
                self.assertIn("label", col, msg=f"Column in '{t['id']}' missing 'label': {col}")

    # 7e. No duplicate keys within a template
    def test_no_duplicate_column_keys(self):
        for t in self.templates:
            keys = [c["key"] for c in t.get("columns", [])]
            dupes = [k for k in keys if keys.count(k) > 1]
            self.assertEqual(dupes, [], msg=f"Duplicate keys in '{t['id']}': {dupes}")

    # 7f. auto template has empty columns (fallback)
    def test_auto_template_has_no_columns(self):
        self.assertEqual(self.by_id["auto"]["columns"], [])

    # ── Non-Pick Time ─────────────────────────────────────────────
    # 7g. Exact 14 columns in exact order
    def test_non_pick_time_has_14_columns(self):
        t = self.by_id["non_pick_time"]
        self.assertEqual(len(t["columns"]), 14)

    def test_non_pick_time_column_keys_exact_order(self):
        t = self.by_id["non_pick_time"]
        keys = [c["key"] for c in t["columns"]]
        expected = [
            "Date", "Week_End", "House_Fill_ID", "House", "Platform",
            "Flush", "Day_No", "Picker", "Payroll_No", "System",
            "Picking_Placing", "Start", "End", "Non_Pick_Time_Mins",
        ]
        self.assertEqual(keys, expected)

    def test_non_pick_time_first_and_last_col(self):
        t = self.by_id["non_pick_time"]
        keys = [c["key"] for c in t["columns"]]
        self.assertEqual(keys[0],  "Date")
        self.assertEqual(keys[-1], "Non_Pick_Time_Mins")

    # ── Hughes Group ──────────────────────────────────────────────
    # 7h. Exact 15 columns, alternating Amount / Punnet_Traceability for first 12
    def test_hughes_has_15_columns(self):
        t = self.by_id["hughes_daily_picking"]
        self.assertEqual(len(t["columns"]), 15)

    def test_hughes_amount_traceability_alternation(self):
        t = self.by_id["hughes_daily_picking"]
        keys = [c["key"] for c in t["columns"]]
        for i in range(0, 12, 2):
            self.assertTrue(keys[i].endswith("_Amount"),
                msg=f"Col {i} should end _Amount: {keys[i]}")
            self.assertTrue(keys[i+1].endswith("_Punnet_Traceability"),
                msg=f"Col {i+1} should end _Punnet_Traceability: {keys[i+1]}")

    def test_hughes_product_prefix_consistent_per_pair(self):
        t = self.by_id["hughes_daily_picking"]
        keys = [c["key"] for c in t["columns"]]
        for i in range(0, 12, 2):
            prefix_amount = keys[i].replace("_Amount", "")
            prefix_tracea = keys[i+1].replace("_Punnet_Traceability", "")
            self.assertEqual(prefix_amount, prefix_tracea,
                msg=f"Pair {i//2}: '{prefix_amount}' vs '{prefix_tracea}'")

    def test_hughes_last_3_are_3kg_products(self):
        t = self.by_id["hughes_daily_picking"]
        keys = [c["key"] for c in t["columns"]]
        self.assertEqual(keys[12], "3Kg_Buttons")
        self.assertEqual(keys[13], "3Kg_Cup")
        self.assertEqual(keys[14], "3Kg_Upgrade")

    # ── MS Pre-start (combined) ───────────────────────────────────
    # 7i. Exact 16 columns covering BOTH tables
    def test_ms_prestart_has_16_columns(self):
        t = self.by_id["ms_prestart"]
        self.assertEqual(len(t["columns"]), 16)

    def test_ms_prestart_first_col_is_table_section(self):
        t = self.by_id["ms_prestart"]
        self.assertEqual(t["columns"][0]["key"], "Table_Section")

    def test_ms_prestart_last_col_is_initials(self):
        t = self.by_id["ms_prestart"]
        self.assertEqual(t["columns"][-1]["key"], "Initials")

    def test_ms_prestart_has_top_table_gate_sensor_cols(self):
        t = self.by_id["ms_prestart"]
        keys = [c["key"] for c in t["columns"]]
        for k in ["GateSensor_Side1_Front", "GateSensor_Side1_Back",
                  "GateSensor_Side2_Front", "GateSensor_Side2_Back"]:
            self.assertIn(k, keys, msg=f"Missing top-table key: {k}")

    def test_ms_prestart_has_bottom_table_gate_sensor_cols(self):
        t = self.by_id["ms_prestart"]
        keys = [c["key"] for c in t["columns"]]
        for k in ["GateSensor_L_Side_Front", "GateSensor_L_Side_Back",
                  "GateSensor_R_Side_Front", "GateSensor_R_Side_Back"]:
            self.assertIn(k, keys, msg=f"Missing bottom-table key: {k}")

    def test_ms_prestart_has_picker_detail_cols(self):
        t = self.by_id["ms_prestart"]
        keys = [c["key"] for c in t["columns"]]
        for k in ["Pickers_Name", "Pickers_Signature",
                  "All_Glass_Hard_Plastic_Intact", "Start_of_Shift", "End_of_Shift"]:
            self.assertIn(k, keys, msg=f"Missing picker-detail key: {k}")

    def test_ms_prestart_has_emergency_stop_col(self):
        t = self.by_id["ms_prestart"]
        keys = [c["key"] for c in t["columns"]]
        self.assertIn("Emergency_Stop_Check_Result", keys)

    # 7j. All real templates have a note field (important for prompt context)
    def test_real_templates_have_note(self):
        for tid in ["ms_prestart", "hughes_daily_picking", "non_pick_time"]:
            t = self.by_id[tid]
            self.assertIn("note", t, msg=f"Template '{tid}' missing 'note' field")
            self.assertTrue(len(t["note"]) > 10, msg=f"Template '{tid}' note too short")


# ---------------------------------------------------------------------------
# 8. _build_template_prompt — output correctness
# ---------------------------------------------------------------------------

class TestBuildTemplatePrompt(unittest.TestCase):

    def _get_template(self, tid: str) -> dict:
        return next(t for t in _load_templates() if t["id"] == tid)

    # 8a. auto → generic EXTRACTION_PROMPT
    def test_auto_returns_generic_prompt(self):
        prompt = ocrm._build_template_prompt(self._get_template("auto"))
        self.assertEqual(prompt, ocrm.EXTRACTION_PROMPT)

    # 8b. All keys present in prompt for all 3 real templates
    def test_prompt_contains_all_column_keys(self):
        for tid in ["ms_prestart", "hughes_daily_picking", "non_pick_time"]:
            t = self._get_template(tid)
            prompt = ocrm._build_template_prompt(t)
            for col in t["columns"]:
                self.assertIn(col["key"], prompt,
                    msg=f"Key '{col['key']}' missing from prompt for '{tid}'")

    # 8c. Label base words present
    def test_prompt_contains_column_label_base_words(self):
        for tid in ["non_pick_time", "ms_prestart"]:
            t = self._get_template(tid)
            prompt = ocrm._build_template_prompt(t)
            for col in t["columns"]:
                base = col["label"].split(":")[0].strip().split("(")[0].strip()
                self.assertIn(base, prompt,
                    msg=f"Label base '{base}' missing from prompt for '{tid}'")

    # 8d. TEMPLATE MODE marker present
    def test_prompt_has_template_mode_marker(self):
        for tid in ["ms_prestart", "hughes_daily_picking", "non_pick_time"]:
            prompt = ocrm._build_template_prompt(self._get_template(tid))
            self.assertIn("TEMPLATE MODE", prompt, msg=f"Missing in '{tid}'")

    # 8e. Key invention forbidden
    def test_prompt_forbids_inventing_keys(self):
        prompt = ocrm._build_template_prompt(self._get_template("hughes_daily_picking"))
        self.assertIn("Do NOT invent", prompt)

    # 8f. Note injected for all real templates
    def test_prompt_includes_template_note(self):
        for tid in ["ms_prestart", "hughes_daily_picking", "non_pick_time"]:
            t = self._get_template(tid)
            prompt = ocrm._build_template_prompt(t)
            self.assertIn("DOCUMENT NOTE", prompt, msg=f"Missing DOCUMENT NOTE in '{tid}'")

    # 8g. column_headers JSON array matches template keys exactly
    def test_column_headers_json_matches_template(self):
        for tid in ["non_pick_time", "hughes_daily_picking", "ms_prestart"]:
            t = self._get_template(tid)
            keys = [c["key"] for c in t["columns"]]
            prompt = ocrm._build_template_prompt(t)
            self.assertIn(json.dumps(keys, ensure_ascii=False), prompt,
                msg=f"column_headers JSON not found in prompt for '{tid}'")

    # 8h. Numbered entry count matches column count
    def test_numbered_entries_match_column_count(self):
        import re
        for tid, expected_count in [
            ("non_pick_time", 14),
            ("hughes_daily_picking", 15),
            ("ms_prestart", 16),
        ]:
            t = self._get_template(tid)
            prompt = ocrm._build_template_prompt(t)
            entries = re.findall(r"^\s+\d+\.\s+key=", prompt, re.MULTILINE)
            self.assertEqual(len(entries), expected_count,
                msg=f"'{tid}': expected {expected_count} entries, got {len(entries)}")

    # 8i. Template prompt does not contain generic step headers
    def test_template_prompt_differs_from_generic(self):
        for tid in ["ms_prestart", "hughes_daily_picking", "non_pick_time"]:
            prompt = ocrm._build_template_prompt(self._get_template(tid))
            self.assertNotIn("STEP 2 — IDENTIFY HEADER STRUCTURE", prompt,
                msg=f"Generic prompt leaked into '{tid}'")

    # 8j. MS Pre-start prompt contains two-table note
    def test_ms_prestart_prompt_mentions_two_tables(self):
        t = self._get_template("ms_prestart")
        prompt = ocrm._build_template_prompt(t)
        self.assertIn("TWO tables", prompt)


# ---------------------------------------------------------------------------
# 9. _call_claude respects template parameter
# ---------------------------------------------------------------------------

class TestCallClaudeTemplate(unittest.TestCase):

    def _tpl(self, tid):
        return next(t for t in _load_templates() if t["id"] == tid)

    def _sent_prompt(self, template, payload):
        """Return the stage-2 user message string (contains extraction instructions)."""
        client = MagicMock()
        client.messages.create.side_effect = [
            _fake_html_response(),          # stage 1 → HTML
            _fake_claude_response(payload), # stage 2 → JSON
        ]
        ocrm._call_claude(client, _make_image(), template=template)
        # Template / extraction prompt lives in stage-2 user message (second call)
        stage2_kwargs = client.messages.create.call_args_list[1].kwargs
        return stage2_kwargs["messages"][0]["content"]  # plain string

    def _empty_payload(self):
        return {"document_info": {}, "column_headers": [], "rows": [], "raw_text": "x"}

    def test_auto_sends_generic_prompt(self):
        sent = self._sent_prompt(self._tpl("auto"), self._empty_payload())
        self.assertNotIn("TEMPLATE MODE", sent)
        self.assertIn("STEP", sent)

    def test_none_sends_generic_prompt(self):
        sent = self._sent_prompt(None, self._empty_payload())
        self.assertNotIn("TEMPLATE MODE", sent)

    def test_non_pick_time_sends_locked_prompt(self):
        sent = self._sent_prompt(self._tpl("non_pick_time"), self._empty_payload())
        self.assertIn("TEMPLATE MODE", sent)
        self.assertIn("Non_Pick_Time_Mins", sent)
        self.assertIn("House_Fill_ID", sent)

    def test_hughes_sends_locked_prompt_with_all_products(self):
        sent = self._sent_prompt(self._tpl("hughes_daily_picking"), self._empty_payload())
        self.assertIn("TEMPLATE MODE", sent)
        self.assertIn("300g_Coop_Cup_Amount", sent)
        self.assertIn("200g_Buttons_Tesco_Punnet_Traceability", sent)
        self.assertIn("3Kg_Upgrade", sent)

    def test_ms_prestart_sends_locked_prompt_with_both_tables(self):
        sent = self._sent_prompt(self._tpl("ms_prestart"), self._empty_payload())
        self.assertIn("TEMPLATE MODE", sent)
        self.assertIn("GateSensor_Side1_Front", sent)   # top table
        self.assertIn("GateSensor_L_Side_Front", sent)  # bottom table
        self.assertIn("Pickers_Name", sent)
        self.assertIn("Table_Section", sent)


# ---------------------------------------------------------------------------
# 10. Phase 1 — merge_table instruction present in all extraction prompts
# ---------------------------------------------------------------------------

class TestPhase1MergeInstruction(unittest.TestCase):
    """Verify cross-page merge instruction is present in all prompts that
    face the extraction stage (both generic and HTML-parse paths)."""

    _MERGE_KEYWORDS = ("continues across", "continuous table", "carry over", "merge all parts")

    def _has_merge_instruction(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in self._MERGE_KEYWORDS)

    def test_extraction_prompt_has_merge_instruction(self):
        self.assertTrue(
            self._has_merge_instruction(ocrm.EXTRACTION_PROMPT),
            msg="EXTRACTION_PROMPT missing cross-page merge instruction (Phase 1)",
        )

    def test_parse_user_prompt_has_merge_instruction(self):
        self.assertTrue(
            self._has_merge_instruction(ocrm.PARSE_USER_PROMPT),
            msg="PARSE_USER_PROMPT missing cross-page merge instruction",
        )


# ---------------------------------------------------------------------------
# 11. Phase 2 — ParseBench system prompt guidelines
# ---------------------------------------------------------------------------

class TestParsePrompts(unittest.TestCase):
    """Verify ParseBench-derived prompts contain required guidelines."""

    def test_parse_system_prompt_instructs_html_tables(self):
        self.assertIn("<table>", ocrm.PARSE_SYSTEM_PROMPT)

    def test_parse_system_prompt_instructs_colspan(self):
        self.assertIn("colspan", ocrm.PARSE_SYSTEM_PROMPT)

    def test_parse_system_prompt_instructs_rowspan(self):
        self.assertIn("rowspan", ocrm.PARSE_SYSTEM_PROMPT)

    def test_parse_system_prompt_covers_multi_level_headers(self):
        lower = ocrm.PARSE_SYSTEM_PROMPT.lower()
        self.assertTrue(
            "multi-level" in lower or "sub-column" in lower,
            msg="PARSE_SYSTEM_PROMPT missing multi-level header instruction",
        )

    def test_parse_system_prompt_no_commentary_instruction(self):
        lower = ocrm.PARSE_SYSTEM_PROMPT.lower()
        self.assertTrue(
            "no commentary" in lower or "do not add commentary" in lower,
            msg="PARSE_SYSTEM_PROMPT missing no-commentary instruction",
        )

    def test_parse_user_prompt_requests_html_output(self):
        self.assertIn("html", ocrm.PARSE_USER_PROMPT.lower())

    def test_parse_user_prompt_forbids_markdown_fences(self):
        self.assertIn("no markdown", ocrm.PARSE_USER_PROMPT.lower())


# ---------------------------------------------------------------------------
# 12. Phase 2 — _parse_image_to_html (Stage 1)
# ---------------------------------------------------------------------------

class TestParseImageToHtml(unittest.TestCase):
    """Stage 1: image → HTML (vision call)."""

    def test_returns_string(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_html_response("<table></table>")
        result = ocrm._parse_image_to_html(client, _make_image())
        self.assertIsInstance(result, str)

    def test_strips_html_markdown_fences(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_html_response(
            "```html\n<table></table>\n```"
        )
        result = ocrm._parse_image_to_html(client, _make_image())
        self.assertNotIn("```", result)
        self.assertIn("<table>", result)

    def test_uses_parse_system_prompt(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_html_response("<p>x</p>")
        ocrm._parse_image_to_html(client, _make_image())
        self.assertEqual(
            client.messages.create.call_args.kwargs["system"],
            ocrm.PARSE_SYSTEM_PROMPT,
        )

    def test_sends_image_block_in_message(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_html_response("<p>x</p>")
        ocrm._parse_image_to_html(client, _make_image())
        content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        image_blocks = [c for c in content if isinstance(c, dict) and c.get("type") == "image"]
        self.assertEqual(len(image_blocks), 1)


# ---------------------------------------------------------------------------
# 13. Phase 2 — _extract_json_from_html (Stage 2)
# ---------------------------------------------------------------------------

class TestExtractJsonFromHtml(unittest.TestCase):
    """Stage 2: HTML → JSON (text-only call)."""

    _HTML  = "<table><tr><th>Date</th></tr><tr><td>15/04</td></tr></table>"
    _EMPTY = {"document_info": {}, "column_headers": ["Date"], "rows": [], "raw_text": "x"}

    def test_valid_json_returned_as_dict(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_claude_response(self._EMPTY)
        result = ocrm._extract_json_from_html(client, self._HTML)
        self.assertIsInstance(result, dict)
        self.assertIn("column_headers", result)

    def test_bad_json_returns_fallback(self):
        client = MagicMock()
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="NOT JSON {{{")]
        )
        result = ocrm._extract_json_from_html(client, self._HTML)
        self.assertIn("parse_error", result)
        self.assertIn("raw_text", result)

    def test_html_content_present_in_user_message(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_claude_response(self._EMPTY)
        ocrm._extract_json_from_html(client, self._HTML)
        user_content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn(self._HTML, user_content)

    def test_uses_ocr_system_prompt(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_claude_response(self._EMPTY)
        ocrm._extract_json_from_html(client, self._HTML)
        self.assertEqual(
            client.messages.create.call_args.kwargs["system"],
            ocrm.SYSTEM_PROMPT,
        )

    def test_message_content_is_plain_string_no_image(self):
        """Stage 2 must be text-only — no image blocks, content is a str."""
        client = MagicMock()
        client.messages.create.return_value = _fake_claude_response(self._EMPTY)
        ocrm._extract_json_from_html(client, self._HTML)
        content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIsInstance(content, str)

    def test_template_mode_injects_locked_prompt(self):
        tpl = next(t for t in _load_templates() if t["id"] == "non_pick_time")
        client = MagicMock()
        client.messages.create.return_value = _fake_claude_response(self._EMPTY)
        ocrm._extract_json_from_html(client, self._HTML, template=tpl)
        user_content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("TEMPLATE MODE", user_content)
        self.assertIn("Non_Pick_Time_Mins", user_content)

    def test_auto_template_uses_generic_prompt(self):
        tpl = next(t for t in _load_templates() if t["id"] == "auto")
        client = MagicMock()
        client.messages.create.return_value = _fake_claude_response(self._EMPTY)
        ocrm._extract_json_from_html(client, self._HTML, template=tpl)
        user_content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertNotIn("TEMPLATE MODE", user_content)

    def test_none_template_uses_generic_prompt(self):
        client = MagicMock()
        client.messages.create.return_value = _fake_claude_response(self._EMPTY)
        ocrm._extract_json_from_html(client, self._HTML, template=None)
        user_content = client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertNotIn("TEMPLATE MODE", user_content)


# ---------------------------------------------------------------------------
# 14. Phase 2 — two-stage _call_claude orchestration
# ---------------------------------------------------------------------------

class TestTwoStagePipeline(unittest.TestCase):
    """_call_claude must make exactly two API calls and pass HTML between stages."""

    _PAYLOAD = {"document_info": {}, "column_headers": [], "rows": [], "raw_text": "x"}

    def _run(self, html="<table></table>", template=None):
        client = MagicMock()
        client.messages.create.side_effect = [
            _fake_html_response(html),
            _fake_claude_response(self._PAYLOAD),
        ]
        result = ocrm._call_claude(client, _make_image(), template=template)
        return client, result

    def test_makes_exactly_two_api_calls(self):
        client, _ = self._run()
        self.assertEqual(client.messages.create.call_count, 2)

    def test_first_call_contains_image_block(self):
        client, _ = self._run()
        content = client.messages.create.call_args_list[0].kwargs["messages"][0]["content"]
        image_blocks = [c for c in content if isinstance(c, dict) and c.get("type") == "image"]
        self.assertEqual(len(image_blocks), 1)

    def test_second_call_is_text_only(self):
        client, _ = self._run()
        content = client.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
        self.assertIsInstance(content, str)

    def test_returns_json_dict(self):
        _, result = self._run()
        self.assertIsInstance(result, dict)
        self.assertIn("column_headers", result)

    def test_html_from_stage1_passed_to_stage2(self):
        """HTML produced by stage 1 must appear verbatim in stage-2 user message."""
        html = "<table><tr><th colspan='2'>Gate Sensor</th></tr></table>"
        client, _ = self._run(html=html)
        stage2_content = client.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
        self.assertIn(html, stage2_content)

    def test_template_forwarded_to_stage2(self):
        """Template must reach stage 2 — locked prompt appears in user message."""
        tpl = next(t for t in _load_templates() if t["id"] == "non_pick_time")
        client, _ = self._run(template=tpl)
        stage2_content = client.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
        self.assertIn("TEMPLATE MODE", stage2_content)
        self.assertIn("Non_Pick_Time_Mins", stage2_content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
