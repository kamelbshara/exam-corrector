"""
Renders a generated exam to PDF in two flavors:
  - "teacher": includes the correct answer bubble filled in + an answer key
    table at the end, for grading reference.
  - "student": identical layout but every bubble is empty, for the student
    to fill in with a pen/pencil.

Both flavors share IDENTICAL bubble geometry (same coordinates on the same
page), which is recorded into the exam JSON as `layout` -- the OMR
corrector uses those coordinates (scaled by the scanned image's size) to
know exactly where to sample each bubble, instead of guessing with blind
circle detection.

Coordinates are stored as fractions of the page (0-1, origin top-left) so
they are resolution-independent.

Question/option text (which contains inline LaTeX math, see
question_bank_gen.py) is rendered to small raster images via
mathtext_render.py and placed with drawImage, rather than reportlab's
native (non-math) drawString -- this is what gives proper fractions,
exponents, radicals, etc. in the printed sheet. Diagrams (also base64 PNG,
baked into the question bank) are embedded the same way.
"""
import base64
import io

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

from mathtext_render import render_to_png

PAGE_W, PAGE_H = A4

MARGIN = 42
MARKER_SIZE = 16          # corner alignment squares, in points
COL_GAP = 18
BUBBLE_R = 5.2
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
Q_FONT_SIZE = 9
OPT_FONT_SIZE = 8.5
HEADER_FONT_SIZE = 9

GAP_TEXT_TO_DIAGRAM = 6
GAP_AFTER_DIAGRAM = 6
GAP_TEXT_TO_OPTIONS = 8
GAP_AFTER_OPTIONS = 14
MAX_DIAGRAM_H = 92


def _wrap_math_tokens(text, fontsize, first_width, rest_width):
    """Greedy word-wrap using actual rendered widths of each space-separated
    token (our LaTeX strings never contain spaces inside $...$, so a token
    is always one atomic math expression or one plain word)."""
    tokens = text.split(" ")
    space_w = fontsize * 0.32
    lines, cur, cur_w, budget = [], [], 0.0, first_width
    for tok in tokens:
        _png, tw, _th = render_to_png(tok, fontsize=fontsize)
        added = tw + (space_w if cur else 0)
        if cur and cur_w + added > budget:
            lines.append(" ".join(cur))
            cur, cur_w, budget = [tok], tw, rest_width
        else:
            cur.append(tok)
            cur_w += added
    if cur:
        lines.append(" ".join(cur))
    return lines


def _render_lines(lines, fontsize):
    return [render_to_png(line, fontsize=fontsize) for line in lines]


def _draw_corner_markers(c):
    """Four filled squares near each page corner used by the OMR corrector
    to detect page orientation/skew via a perspective transform."""
    inset = 22
    positions = [
        (inset, PAGE_H - inset - MARKER_SIZE),                     # top-left
        (PAGE_W - inset - MARKER_SIZE, PAGE_H - inset - MARKER_SIZE),  # top-right
        (inset, inset),                                            # bottom-left
        (PAGE_W - inset - MARKER_SIZE, inset),                      # bottom-right
    ]
    c.setFillColorRGB(0, 0, 0)
    for x, y in positions:
        c.rect(x, y, MARKER_SIZE, MARKER_SIZE, fill=1, stroke=0)
    return positions


def _to_frac(x, y):
    """Convert PDF point coords (origin bottom-left) to page fractions
    with origin top-left, matching how images are read (row 0 = top)."""
    return (x / PAGE_W, (PAGE_H - y) / PAGE_H)


def _draw_image(c, png_bytes, x, top_y, w, h):
    """Draws an image with its TOP-LEFT at (x, top_y) (reportlab drawImage
    positions by bottom-left, so we convert)."""
    c.drawImage(ImageReader(io.BytesIO(png_bytes)), x, top_y - h, width=w, height=h, mask="auto")


def _draw_header(c, exam, page_num, total_pages, flavor):
    top = PAGE_H - 22 - MARKER_SIZE - 10
    c.setFont(FONT_BOLD, 13)
    c.drawCentredString(PAGE_W / 2, top, exam["school_name"])
    c.setFont(FONT_BOLD, 11)
    top -= 16
    subtitle = f"Mathematics Exam - {exam['grade']} ({exam['track']} track)"
    c.drawCentredString(PAGE_W / 2, top, subtitle)

    top -= 16
    c.setFont(FONT, HEADER_FONT_SIZE)
    left_x = MARGIN + MARKER_SIZE + 6
    right_x = PAGE_W - MARGIN - MARKER_SIZE - 6
    c.drawString(left_x, top, f"Exam ID: {exam['exam_id']}")
    total_marks = exam.get("total_marks", exam["num_questions"])
    c.drawRightString(right_x, top, f"Questions: {exam['num_questions']}  |  Total: {total_marks} marks")

    top -= 16
    label = "TEACHER / ANSWER KEY COPY" if flavor == "teacher" else "STUDENT ANSWER SHEET"
    c.setFont(FONT_BOLD, 9)
    c.drawCentredString(PAGE_W / 2, top, label)

    top -= 18
    c.setFont(FONT, HEADER_FONT_SIZE)
    c.drawString(left_x, top, "Student Name: " + "_" * 42)
    top -= 16
    c.drawString(left_x, top, "Class / Section: " + "_" * 30)
    c.drawRightString(right_x, top, f"Page {page_num}/{total_pages}")
    top -= 10
    c.setStrokeColorRGB(0.4, 0.4, 0.4)
    c.line(left_x, top, right_x, top)
    return top - 14


def _draw_instructions(c, y, flavor):
    c.setFont("Helvetica-Oblique", 8)
    text = (
        "Fill each bubble completely with a dark pen or pencil. Choose only one answer per question."
        if flavor == "student"
        else "Correct answers are shown filled in below; the full answer key is listed on the last page."
    )
    c.drawString(MARGIN + MARKER_SIZE + 6, y, text)
    return y - 16


def _prepare_question(q, col_width, opt_col_width):
    """Renders everything for one question (text lines, diagram, options)
    up front so we know its exact height before deciding placement."""
    marks = q.get("marks")
    prefix = f"Q{q['number']}. "
    if marks is not None:
        prefix = f"Q{q['number']}. ({marks} mark{'s' if marks != 1 else ''}) "
    num_w = stringWidth(prefix, FONT_BOLD, Q_FONT_SIZE)

    lines = _wrap_math_tokens(q["text"], Q_FONT_SIZE, col_width - num_w, col_width)
    text_images = _render_lines(lines, Q_FONT_SIZE)
    text_h = sum(h for _p, _w, h in text_images)

    diagram_img = None
    diagram_w = diagram_h = 0
    if q.get("diagram"):
        raw = base64.b64decode(q["diagram"])
        im = Image.open(io.BytesIO(raw))
        px_w, px_h = im.size
        target_w = min(col_width * 0.62, px_w)
        target_h = target_w * (px_h / px_w)
        if target_h > MAX_DIAGRAM_H:
            target_h = MAX_DIAGRAM_H
            target_w = target_h * (px_w / px_h)
        diagram_img = raw
        diagram_w, diagram_h = target_w, target_h

    letters = ["A", "B", "C", "D"]
    max_opt_w = opt_col_width - (2 * BUBBLE_R + 6)
    option_images = {}
    option_row_h = [0, 0]
    for i, letter in enumerate(letters):
        opt_text = f"{letter}. {q['options'][letter]}"
        opt_lines = _wrap_math_tokens(opt_text, OPT_FONT_SIZE, max_opt_w, max_opt_w)
        imgs = _render_lines(opt_lines, OPT_FONT_SIZE)
        option_images[letter] = imgs
        row = i // 2
        h = sum(im[2] for im in imgs)
        option_row_h[row] = max(option_row_h[row], h, 14)

    row_h = (
        text_h
        + (GAP_TEXT_TO_DIAGRAM + diagram_h + GAP_AFTER_DIAGRAM if diagram_img else GAP_TEXT_TO_OPTIONS)
        + option_row_h[0] + 4 + option_row_h[1]
        + GAP_AFTER_OPTIONS
    )

    return {
        "prefix": prefix,
        "num_w": num_w,
        "text_images": text_images,
        "diagram_img": diagram_img,
        "diagram_w": diagram_w,
        "diagram_h": diagram_h,
        "option_images": option_images,
        "option_row_h": option_row_h,
        "row_h": row_h,
    }


def render_exam_pdf(exam, flavor="student"):
    """Returns (pdf_bytes, layout) where layout records the page/x/y
    fraction of every bubble for use by the OMR corrector."""
    assert flavor in ("teacher", "student")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    questions = exam["questions"]
    left_x = MARGIN + MARKER_SIZE + 6
    right_x = PAGE_W - MARGIN - MARKER_SIZE - 6
    content_width = right_x - left_x
    col_width = (content_width - COL_GAP) / 2
    opt_col_width = (col_width - 10) / 2

    bottom_limit = 22 + MARKER_SIZE + 18

    prepared = [_prepare_question(q, col_width, opt_col_width) for q in questions]

    layout_questions = {}
    markers_by_page = []

    def simulate():
        page = 1
        col = 0
        y0 = PAGE_H - 178
        pages = 1
        cur_y = [y0, y0]
        for p in prepared:
            if cur_y[col] - p["row_h"] < bottom_limit:
                col += 1
                if col > 1:
                    col = 0
                    pages += 1
                    cur_y = [y0, y0]
            cur_y[col] -= p["row_h"]
        return pages

    total_pages = simulate() + (1 if flavor == "teacher" else 0)

    page_num = 1
    col = 0
    markers = _draw_corner_markers(c)
    markers_by_page.append([_to_frac(x + MARKER_SIZE / 2, y + MARKER_SIZE / 2) for x, y in markers])
    header_bottom = _draw_header(c, exam, page_num, total_pages, flavor)
    header_bottom = _draw_instructions(c, header_bottom, flavor)

    col_x = [left_x, left_x + col_width + COL_GAP]
    cur_y = [header_bottom, header_bottom]

    def new_page():
        nonlocal page_num, col, cur_y, header_bottom
        c.showPage()
        page_num += 1
        markers = _draw_corner_markers(c)
        markers_by_page.append([_to_frac(x + MARKER_SIZE / 2, y + MARKER_SIZE / 2) for x, y in markers])
        header_bottom = _draw_header(c, exam, page_num, total_pages, flavor)
        header_bottom = _draw_instructions(c, header_bottom, flavor)
        col = 0
        cur_y = [header_bottom, header_bottom]

    for q, p in zip(questions, prepared):
        if cur_y[col] - p["row_h"] < bottom_limit:
            col += 1
            if col > 1:
                new_page()

        x0 = col_x[col]
        y = cur_y[col]

        first_line_h = p["text_images"][0][2] if p["text_images"] else Q_FONT_SIZE
        label_offset = min(max(first_line_h * 0.78, Q_FONT_SIZE * 0.7), first_line_h * 0.92)
        c.setFont(FONT_BOLD, Q_FONT_SIZE)
        c.drawString(x0, y - label_offset, p["prefix"])

        ty = y
        for i, (png, w, h) in enumerate(p["text_images"]):
            tx = x0 + (p["num_w"] if i == 0 else 8)
            _draw_image(c, png, tx, ty, w, h)
            ty -= h

        if p["diagram_img"]:
            ty -= GAP_TEXT_TO_DIAGRAM
            _draw_image(c, p["diagram_img"], x0 + 4, ty, p["diagram_w"], p["diagram_h"])
            ty -= p["diagram_h"] + GAP_AFTER_DIAGRAM
        else:
            ty -= GAP_TEXT_TO_OPTIONS

        options_top = ty
        option_positions = {}
        letters = ["A", "B", "C", "D"]
        for i, letter in enumerate(letters):
            row = i // 2
            colpos = i % 2
            bx = x0 + 8 + colpos * (opt_col_width + 10)
            row_top = options_top if row == 0 else options_top - p["option_row_h"][0] - 4
            cx = bx + BUBBLE_R
            cy = row_top - BUBBLE_R
            c.setLineWidth(0.8)
            c.setStrokeColorRGB(0, 0, 0)
            is_correct = (letter == q["correct"])
            fill_this = flavor == "teacher" and is_correct
            c.circle(cx, cy, BUBBLE_R, stroke=1, fill=1 if fill_this else 0)

            oy = row_top
            for img_png, img_w, img_h in p["option_images"][letter]:
                _draw_image(c, img_png, cx + BUBBLE_R + 5, oy, img_w, img_h)
                oy -= img_h

            option_positions[letter] = list(_to_frac(cx, cy))

        cur_y[col] = options_top - p["option_row_h"][0] - 4 - p["option_row_h"][1] - GAP_AFTER_OPTIONS

        layout_questions[str(q["number"])] = {
            "page": page_num,
            "options": option_positions,
        }

    if flavor == "teacher":
        c.showPage()
        page_num += 1
        _draw_corner_markers(c)
        c.setFont(FONT_BOLD, 13)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 60, "Answer Key")
        c.setFont(FONT, 10)
        y = PAGE_H - 90
        col_w = (PAGE_W - 2 * MARGIN) / 4
        for i, q in enumerate(questions):
            col_i = i // 25
            row_i = i % 25
            x = MARGIN + col_i * col_w
            yy = y - row_i * 20
            marks = q.get("marks", 1)
            c.drawString(x, yy, f"Q{q['number']}: {q['correct']}  ({marks} pt, {q['area_label']})")

    c.save()
    pdf_bytes = buf.getvalue()

    layout = {
        "page_size": [PAGE_W, PAGE_H],
        "markers_by_page": markers_by_page,
        "questions": layout_questions,
    }
    return pdf_bytes, layout
