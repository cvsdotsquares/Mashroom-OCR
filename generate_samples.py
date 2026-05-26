"""
generate_samples.py — v4  (landscape A4, proper cell separation)
================================================================
• Landscape A4 gives enough width for each quantity cell
• Every qty cell has full 4-sided border — numbers never bleed together
• Caveat-Bold / Kalam-Bold for handwritten data; Helvetica for labels
• Per-number rotation, size & position jitter
"""

import os, random
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Fonts ──────────────────────────────────────────────────────────────────
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
pdfmetrics.registerFont(TTFont("Caveat",      os.path.join(FONT_DIR,"Caveat-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Caveat-Bold", os.path.join(FONT_DIR,"Caveat-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Kalam",       os.path.join(FONT_DIR,"Kalam-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Kalam-Bold",  os.path.join(FONT_DIR,"Kalam-Bold.ttf")))

OUT_DIR = os.path.join(os.path.dirname(__file__), "samples")
os.makedirs(OUT_DIR, exist_ok=True)

# Landscape A4
PW, PH = landscape(A4)   # 841 × 595 pts  ≈  297 × 210 mm
MAR    = 12 * mm

# ── Palette ────────────────────────────────────────────────────────────────
PAPER     = colors.HexColor("#f3ede1")
HDR_BG    = colors.HexColor("#d6e8d2")
CELL_ALT  = colors.HexColor("#eae6da")
GRID_DARK = colors.HexColor("#5a7a60")     # prominent cell borders
GRID_LITE = colors.HexColor("#9ab09e")     # light separators
INK_PRINT = colors.HexColor("#0d0d0d")
INK_BLUE  = colors.HexColor("#1b3570")
INK_DARK  = colors.HexColor("#151515")
INK_RED   = colors.HexColor("#8b0000")
INK_GREEN = colors.HexColor("#145214")

# ── Data ───────────────────────────────────────────────────────────────────
SAMPLES = [
    {"doc_ref":"Harvest004","date":"10.04.26","day_no":"1",
     "location":"Block A – North Field","supervisor":"J. Hargreaves",
     "pickers":[
        {"team":"B","name":"Olha B.",    "no":"2969","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"14:05"},
        {"team":"B","name":"Maria K.",   "no":"5216","start":"6:30","b1":"10:05","b2":"13:05","b3":"—","end":"18:00"},
        {"team":"B","name":"Meerim N.",  "no":"4236","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:40"},
        {"team":"B","name":"Svitlana M.","no":"5766","start":"6:30","b1":"10:10","b2":"13:10","b3":"—","end":"18:00"},
        {"team":"A","name":"Maryam T.",  "no":"4509","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:40"},
        {"team":"A","name":"Tansuluu A.","no":"5147","start":"6:30","b1":"10:05","b2":"13:05","b3":"—","end":"17:40"},
        {"team":"B","name":"Nuridin S.", "no":"3812","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:40"},
     ]},
    {"doc_ref":"Harvest004","date":"11.04.26","day_no":"2",
     "location":"Block B – South Polytunnel","supervisor":"R. Flanagan",
     "pickers":[
        {"team":"B","name":"Lena W.",   "no":"3041","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:30"},
        {"team":"A","name":"Fatima Z.", "no":"6120","start":"6:30","b1":"10:10","b2":"13:10","b3":"—","end":"18:10"},
        {"team":"B","name":"Hassan M.", "no":"4478","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:30"},
        {"team":"A","name":"Petra V.",  "no":"5891","start":"6:30","b1":"10:05","b2":"13:05","b3":"—","end":"18:05"},
        {"team":"B","name":"Rohan P.",  "no":"4002","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:30"},
        {"team":"A","name":"Irina C.",  "no":"5334","start":"6:30","b1":"10:15","b2":"13:15","b3":"—","end":"18:00"},
     ]},
    {"doc_ref":"Harvest005","date":"12.04.26","day_no":"3",
     "location":"Block C – Glasshouse 3","supervisor":"M. O'Brien",
     "pickers":[
        {"team":"A","name":"Yuki T.",   "no":"7201","start":"6:00","b1":"09:45","b2":"12:45","b3":"—","end":"16:45"},
        {"team":"B","name":"Carlos R.", "no":"3367","start":"6:00","b1":"09:50","b2":"12:50","b3":"—","end":"17:00"},
        {"team":"A","name":"Amara O.",  "no":"6045","start":"6:00","b1":"09:45","b2":"12:45","b3":"—","end":"16:45"},
        {"team":"B","name":"Dmitri K.", "no":"4890","start":"6:00","b1":"09:55","b2":"12:55","b3":"—","end":"17:10"},
        {"team":"A","name":"Selin Y.",  "no":"5512","start":"6:00","b1":"09:45","b2":"12:45","b3":"—","end":"16:50"},
        {"team":"B","name":"Ngozi A.",  "no":"3788","start":"6:00","b1":"09:50","b2":"12:50","b3":"—","end":"17:00"},
        {"team":"A","name":"Pawel J.",  "no":"6233","start":"6:00","b1":"09:45","b2":"12:45","b3":"—","end":"16:45"},
        {"team":"B","name":"Alinta W.", "no":"4129","start":"6:00","b1":"09:55","b2":"12:55","b3":"—","end":"17:05"},
     ]},
    {"doc_ref":"Harvest005","date":"13.04.26","day_no":"4",
     "location":"Block A – North Field","supervisor":"J. Hargreaves",
     "pickers":[
        {"team":"B","name":"Olha B.",    "no":"2969","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:50"},
        {"team":"B","name":"Meerim N.",  "no":"4236","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:45"},
        {"team":"A","name":"Tansuluu A.","no":"5147","start":"6:30","b1":"10:05","b2":"13:05","b3":"—","end":"17:55"},
        {"team":"B","name":"Hassan M.",  "no":"4478","start":"6:30","b1":"10:00","b2":"13:00","b3":"—","end":"17:40"},
        {"team":"A","name":"Irina C.",   "no":"5334","start":"6:30","b1":"10:15","b2":"13:15","b3":"—","end":"18:00"},
     ]},
    {"doc_ref":"Harvest006","date":"14.04.26","day_no":"5",
     "location":"Block D – Tunnel Row 7","supervisor":"S. McCarthy",
     "pickers":[
        {"team":"A","name":"Yuki T.",    "no":"7201","start":"6:15","b1":"10:00","b2":"13:00","b3":"—","end":"17:30"},
        {"team":"B","name":"Carlos R.",  "no":"3367","start":"6:15","b1":"10:05","b2":"13:05","b3":"—","end":"17:40"},
        {"team":"A","name":"Fatima Z.",  "no":"6120","start":"6:15","b1":"10:00","b2":"13:00","b3":"—","end":"17:35"},
        {"team":"B","name":"Svitlana M.","no":"5766","start":"6:15","b1":"10:10","b2":"13:10","b3":"—","end":"17:50"},
        {"team":"A","name":"Pawel J.",   "no":"6233","start":"6:15","b1":"10:00","b2":"13:00","b3":"—","end":"17:30"},
        {"team":"B","name":"Ngozi A.",   "no":"3788","start":"6:15","b1":"10:05","b2":"13:05","b3":"—","end":"17:45"},
        {"team":"A","name":"Rohan P.",   "no":"4002","start":"6:15","b1":"10:00","b2":"13:00","b3":"—","end":"17:30"},
     ]},
]

QTY_GROUPS = [
    {"label":"Aldi 200g\nButton", "intervals":["07:00","08:00","09:00","10:30","11:30","12:30","14:00","15:00"], "lo":22,"hi":38,"ink":INK_BLUE,  "font":"Caveat-Bold"},
    {"label":"Big\nButtons",      "intervals":["07:00","08:00","09:00","10:30","11:30","12:30","14:00","15:00"], "lo":22,"hi":36,"ink":INK_BLUE,  "font":"Caveat-Bold"},
    {"label":"H. Crop",           "intervals":["07:00","08:00","09:00","10:30","11:30","12:30","14:00","15:00"], "lo":18,"hi":27,"ink":INK_DARK,  "font":"Kalam-Bold"},
]

# ═══════════════════════════════════════════════════════════════════════════
# PRIMITIVES
# ═══════════════════════════════════════════════════════════════════════════

def jx(v, r=1.2):  return v + random.uniform(-r, r)
def js(v, r=0.6):  return v + random.uniform(-r, r)

def hw_cell(cv, text, cx, cy, font, size, color, rng_):
    """Draw one handwritten value with tilt + jitter."""
    angle = rng_.uniform(-4, 4)
    size  = size + rng_.uniform(-0.7, 0.7)
    ox    = rng_.uniform(-1.0, 1.0)
    oy    = rng_.uniform(-1.3, 1.3)
    cv.saveState()
    cv.translate(cx + ox, cy + oy)
    cv.rotate(angle)
    cv.setFillColor(color)
    cv.setFont(font, size)
    cv.drawCentredString(0, 0, text)
    cv.restoreState()

def box(cv, x, y, w, h, fill=None, stroke=GRID_DARK, lw=0.55):
    """Draw a filled & stroked rectangle."""
    if fill:
        cv.setFillColor(fill)
        cv.rect(x, y - h, w, h, fill=1, stroke=0)
    cv.setStrokeColor(stroke)
    cv.setLineWidth(lw)
    cv.rect(x, y - h, w, h, fill=0, stroke=1)

def hdr_cell(cv, x, y, w, h, text, fsize=6.5, bg=HDR_BG):
    """Printed header cell with background."""
    box(cv, x, y, w, h, fill=bg, stroke=GRID_DARK, lw=0.6)
    cv.setFillColor(INK_PRINT)
    cv.setFont("Helvetica-Bold", fsize)
    lines = text.split("\n")
    lh    = fsize * 1.4
    ty    = y - h/2 + (len(lines) * lh)/2 - lh * 0.85
    for ln in lines:
        cv.drawCentredString(x + w/2, ty, ln)
        ty -= lh

# ═══════════════════════════════════════════════════════════════════════════
# PAGE SECTIONS
# ═══════════════════════════════════════════════════════════════════════════

def draw_bg(cv):
    cv.setFillColor(PAPER)
    cv.rect(0, 0, PW, PH, fill=1, stroke=0)
    # scanner shadow (left)
    cv.setFillColor(colors.HexColor("#ddd5c5"))
    cv.rect(0, 0, 7*mm, PH, fill=1, stroke=0)
    # subtle scan lines
    cv.saveState()
    cv.setStrokeColor(colors.HexColor("#e8e0d0"))
    cv.setLineWidth(0.07)
    for y in range(int(MAR), int(PH - MAR), 11):
        cv.line(MAR, y + random.uniform(-.2,.2),
                PW - MAR, y + random.uniform(-.2,.2))
    cv.restoreState()
    # top-right dog-ear
    cv.setFillColor(colors.HexColor("#ddd5c0"))
    p = cv.beginPath()
    p.moveTo(PW-18*mm, PH); p.lineTo(PW, PH-18*mm); p.lineTo(PW, PH); p.close()
    cv.drawPath(p, fill=1, stroke=0)


def draw_header(cv, data, rng_):
    top = PH - MAR

    # Title band
    cv.setFillColor(HDR_BG)
    cv.rect(MAR, top - 14*mm, PW - 2*MAR, 14*mm, fill=1, stroke=0)
    cv.setFillColor(INK_PRINT); cv.setFont("Helvetica-Bold", 9)
    cv.drawString(MAR+2*mm, top-5.5*mm, f"Doc Ref: {data['doc_ref']}")
    cv.setFont("Helvetica-Bold", 13)
    cv.drawCentredString(PW/2, top-5.5*mm, "Daily Pre-Start Checks & Picking Record")
    cv.setFont("Helvetica", 7)
    cv.drawString(MAR+2*mm, top-11*mm, "Authorised by: Farm Manager")

    # Info row — printed label, handwritten value
    y_info = top - 25*mm
    fields = [("Date:",       data["date"],       18*mm),
              ("DAY No:",     data["day_no"],      20*mm),
              ("Location:",   data["location"],    23*mm),
              ("Supervisor:", data["supervisor"],  26*mm)]
    cw = (PW - 2*MAR) / len(fields)
    for i,(lbl,val,lw) in enumerate(fields):
        x = MAR + i*cw
        cv.setFillColor(INK_PRINT); cv.setFont("Helvetica-Bold", 8)
        cv.drawString(x, y_info, lbl)
        cv.setFillColor(INK_BLUE)
        cv.setFont("Caveat-Bold", js(13, 0.5))
        cv.drawString(x+lw, jx(y_info, 0.8), val)

    cv.setStrokeColor(GRID_DARK); cv.setLineWidth(0.5)
    cv.line(MAR, y_info-4*mm, PW-MAR, y_info-4*mm)

    # Pre-start check boxes
    y_chk = y_info - 16*mm;  bh = 11*mm
    chk_labels = [
        "All aliens & land please (items)\nInspect & free from damage",
        "Planner's\nsignature", "1st BREAK:", "2nd BREAK:",
        "3rd BREAK:", "Start of shift", "End of shift", "Initials"
    ]
    bw = (PW - 2*MAR) / len(chk_labels)
    for i, lbl in enumerate(chk_labels):
        bx = MAR + i*bw
        cv.setFillColor(colors.white)
        box(cv, bx, y_chk, bw-0.5*mm, bh, fill=colors.white,
            stroke=GRID_DARK, lw=0.5)
        cv.setFillColor(INK_PRINT); cv.setFont("Helvetica", 5.5)
        for j,ln in enumerate(lbl.split("\n")):
            cv.drawString(bx+1.5*mm, y_chk-4*mm-j*4*mm, ln)
        if i == 1:
            cv.setFillColor(INK_BLUE); cv.setFont("Caveat-Bold", js(11,0.5))
            cv.drawString(bx+2*mm, jx(y_chk-8*mm, 0.7),
                          "✓ "+data["supervisor"].split(".")[0])
        elif i in (5,6):
            cv.saveState()
            cx = bx+bw/2; cy = y_chk-7*mm
            cv.translate(cx, cy)
            cv.rotate(rng_.uniform(-5,5))
            cv.setFillColor(INK_GREEN); cv.setFont("Caveat-Bold", 15)
            cv.drawCentredString(0, 0, "✓")
            cv.restoreState()

    return y_chk - bh - 5*mm


def draw_table(cv, data, top_y, rng_):
    pickers = data["pickers"]

    # ── Column widths (landscape gives us ~273mm usable) ──────────
    name_w  = 30*mm
    no_w    = 14*mm
    start_w = 13*mm
    brk_w   = 12*mm
    end_w   = 13*mm
    fixed_w = name_w + no_w + start_w + 3*brk_w + end_w  # 106mm

    n_sub_total = sum(len(g["intervals"]) for g in QTY_GROUPS)  # 24
    avail_qty   = PW - 2*MAR - fixed_w                           # ~167mm
    sub_w       = avail_qty / n_sub_total                        # ~6.96mm each

    RH1 = 9*mm   # group header row
    RH2 = 6*mm   # interval sub-header row
    RD  = 9*mm   # data row height

    total_w = PW - 2*MAR

    # ── Build column x-positions ───────────────────────────────────
    xs = []; x = MAR
    for w in (name_w, no_w, start_w):
        xs.append(x); x += w
    for g in QTY_GROUPS:
        for _ in g["intervals"]:
            xs.append(x); x += sub_w
    qi_base = len(xs)          # index of first break column
    for _ in range(3):
        xs.append(x); x += brk_w
    xs.append(x)               # end-time column

    # ── Header row 1: group labels ─────────────────────────────────
    y1 = top_y
    hdr_cell(cv, xs[0], y1, name_w,  RH1, "Picker's\nName")
    hdr_cell(cv, xs[1], y1, no_w,    RH1, "Picker\nNo.")
    hdr_cell(cv, xs[2], y1, start_w, RH1, "Start")
    ci = 3
    for g in QTY_GROUPS:
        gw = sub_w * len(g["intervals"])
        hdr_cell(cv, xs[ci], y1, gw, RH1, g["label"], fsize=6)
        ci += len(g["intervals"])
    hdr_cell(cv, xs[qi_base],   y1, brk_w, RH1, "1st\nBreak")
    hdr_cell(cv, xs[qi_base+1], y1, brk_w, RH1, "2nd\nBreak")
    hdr_cell(cv, xs[qi_base+2], y1, brk_w, RH1, "3rd\nBreak")
    hdr_cell(cv, xs[qi_base+3], y1, end_w,  RH1, "End\nTime")

    # ── Header row 2: interval labels ─────────────────────────────
    y2 = y1 - RH1
    for w in (name_w, no_w, start_w):
        hdr_cell(cv, xs[len([name_w,no_w,start_w])-
                       [name_w,no_w,start_w].index(w)-
                       (3-[name_w,no_w,start_w].index(w))],
                 y2, w, RH2, "")
    # simpler: iterate directly
    hdr_cell(cv, xs[0], y2, name_w,  RH2, "")
    hdr_cell(cv, xs[1], y2, no_w,    RH2, "")
    hdr_cell(cv, xs[2], y2, start_w, RH2, "")
    ci = 3
    for g in QTY_GROUPS:
        for iv in g["intervals"]:
            hdr_cell(cv, xs[ci], y2, sub_w, RH2, iv, fsize=5)
            ci += 1
    for j in range(3):
        hdr_cell(cv, xs[qi_base+j], y2, brk_w, RH2, "")
    hdr_cell(cv, xs[qi_base+3], y2, end_w, RH2, "")

    # ── Data rows ──────────────────────────────────────────────────
    lrng = random.Random(int(data["date"].replace(".","")) * 37)

    for ri, p in enumerate(pickers):
        yr    = y2 - RH2 - ri * RD
        row_bg = CELL_ALT if ri % 2 == 0 else PAPER
        mid_y  = yr - RD * 0.52

        # Row background + outer border
        cv.setFillColor(row_bg)
        cv.rect(MAR, yr - RD, total_w, RD, fill=1, stroke=0)
        cv.setStrokeColor(GRID_DARK); cv.setLineWidth(0.5)
        cv.rect(MAR, yr - RD, total_w, RD, fill=0, stroke=1)

        # — Team prefix ——
        cv.setFillColor(INK_PRINT); cv.setFont("Helvetica-Bold", 7.5)
        cv.drawString(xs[0]+1.5*mm, mid_y-1, p["team"])

        # — Name (Kalam) ——
        cv.setFillColor(INK_DARK)
        cv.setFont("Kalam-Bold", js(11, 0.4))
        cv.drawString(xs[0]+6.5*mm, jx(mid_y-1, 0.9), p["name"])
        cv.setStrokeColor(GRID_DARK); cv.setLineWidth(0.5)
        cv.line(xs[0], yr-RD, xs[0], yr)

        # — Picker no (Caveat-Bold, blue) ——
        cv.line(xs[1], yr-RD, xs[1], yr)
        hw_cell(cv, p["no"], xs[1]+no_w/2, mid_y-1,
                "Caveat-Bold", 12, INK_BLUE, lrng)

        # — Start (Caveat) ——
        cv.line(xs[2], yr-RD, xs[2], yr)
        hw_cell(cv, p["start"]+"K", xs[2]+start_w/2, mid_y-1,
                "Caveat", 10.5, INK_DARK, lrng)

        # — Quantity cells — each has its own full border ——
        ci = 3
        for g in QTY_GROUPS:
            for si, _ in enumerate(g["intervals"]):
                cx = xs[ci]
                # Draw full cell box (all 4 sides, dark border)
                cv.setFillColor(row_bg)
                cv.setStrokeColor(GRID_DARK); cv.setLineWidth(0.55)
                cv.rect(cx, yr-RD, sub_w, RD, fill=1, stroke=1)

                # Decide value
                blank = si >= 6 and lrng.random() < 0.25
                if blank:
                    hw_cell(cv, "—", cx+sub_w/2, mid_y-1,
                            "Caveat", 9, colors.HexColor("#b0a898"), lrng)
                else:
                    val = str(lrng.randint(g["lo"], g["hi"]))
                    hw_cell(cv, val, cx+sub_w/2, mid_y-1,
                            g["font"], 11.5, g["ink"], lrng)
                ci += 1

        # — Break times ——
        for j, bv in enumerate([p["b1"], p["b2"], p["b3"]]):
            cx = xs[qi_base+j]
            cv.setStrokeColor(GRID_DARK); cv.setLineWidth(0.5)
            cv.line(cx, yr-RD, cx, yr)
            col = colors.HexColor("#aaa") if bv=="—" else INK_DARK
            hw_cell(cv, bv, cx+brk_w/2, mid_y-1, "Caveat", 9.5, col, lrng)

        # — End time (RED) ——
        cx = xs[qi_base+3]
        cv.setStrokeColor(GRID_DARK); cv.setLineWidth(0.5)
        cv.line(cx, yr-RD, cx, yr)
        hw_cell(cv, p["end"], cx+end_w/2, mid_y-1,
                "Caveat-Bold", 11.5, INK_RED, lrng)

    # Outer table border (heavy)
    table_h = RH1 + RH2 + len(pickers) * RD
    cv.setStrokeColor(INK_PRINT); cv.setLineWidth(1.2)
    cv.rect(MAR, top_y - table_h, total_w, table_h)

    return top_y - table_h


def draw_footer(cv, data, y):
    cv.setFillColor(INK_PRINT); cv.setFont("Helvetica-Bold", 7.5)
    cv.drawString(MAR, y-8*mm,
        f"Supervisor sign-off: _______________________     "
        f"Date: {data['date']}     Doc Ref: {data['doc_ref']}")
    cv.setFont("Helvetica", 6)
    cv.drawRightString(PW-MAR, y-8*mm, "Page 1 of 1")
    cv.setFillColor(colors.HexColor("#aaa090"))
    cv.setFont("Helvetica-Oblique", 5)
    cv.drawString(MAR, MAR/2,
        "CONFIDENTIAL — Internal harvest record — do not distribute")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def generate(idx, data):
    random.seed(idx * 113 + 7)
    rng_ = random.Random(idx * 77)
    path = os.path.join(OUT_DIR, f"sample_{idx:02d}.pdf")
    cv   = canvas.Canvas(path, pagesize=landscape(A4))
    cv.setTitle(f"Picking Record {data['date']}")
    draw_bg(cv)
    y = draw_header(cv, data, rng_)
    y = draw_table(cv, data, y - 2*mm, rng_)
    draw_footer(cv, data, y)
    cv.save()
    return path


if __name__ == "__main__":
    print("Generating handwritten picking-record PDFs (landscape A4) …\n")
    for i, s in enumerate(SAMPLES, 1):
        p = generate(i, s)
        print(f"  ✓  sample_{i:02d}.pdf  —  {s['date']}  |  {len(s['pickers'])} pickers")
    print(f"\n5 files → {OUT_DIR}")
