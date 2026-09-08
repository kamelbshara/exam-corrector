"""
Renders a generated exam to PDF in two flavors, each a single combined
document with two sections:
  1. Question Paper -- the question text, diagrams, and options (as plain
     labeled text, A/B/C/D, no bubbles) for the student to read from.
  2. Answer Sheet -- a compact bubble-only grid ("N. (A)(B)(C)(D)"), the
     ONLY page(s) the OMR corrector reads. Its layout is a pure function
     of the question count (not of question content), so it's identical
     regardless of how long any question's text or diagram is.

  - "teacher": the question paper highlights the correct option, the
    answer sheet shows the correct bubble filled in, and a text answer
    key follows on the last page.
  - "student": both sections are blank, for the student to fill in.

Bubble geometry is recorded into the exam JSON as `layout` -- the OMR
corrector uses those coordinates (scaled by the scanned image's size) to
know exactly where to sample each bubble. Coordinates are stored as
fractions of the page (0-1, origin top-left) so they are
resolution-independent. `layout["questions"][n]["page"]` is 1-indexed
*within the answer sheet section only* (never the question paper), since
that's what a teacher photographs and uploads for correction.

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

# ---- Answer-sheet grid geometry (pure function of question count) --------
ANS_ROWS_PER_COL = 20
ANS_ROW_H = 24
ANS_NUM_W = 26
ANS_BUBBLE_R = 7
ANS_CENTER_GAP = 20
ANS_COL_W = ANS_NUM_W + 4 * ANS_CENTER_GAP + 14
ANS_COL_GAP = 24
ANS_LETTERS = ["A", "B", "C", "D"]


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


# ============================================================ Question Paper
def _draw_paper_header(c, exam, page_num, total_pages, flavor):
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
    label = "TEACHER / ANSWER KEY COPY" if flavor == "teacher" else "QUESTION PAPER"
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


def _draw_paper_instructions(c, y, flavor):
    c.setFont("Helvetica-Oblique", 8)
    text = (
        "Mark your answers on the separate Answer Sheet -- fill each bubble completely, one answer per question."
        if flavor == "student"
        else "Correct answers are highlighted below; the bubbled answer key and a text list follow this paper."
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

    max_opt_w = opt_col_width - 6
    option_images = {}
    option_row_h = [0, 0]
    for i, letter in enumerate(ANS_LETTERS):
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


def _render_question_paper(c, exam, flavor):
    """Draws the question paper section. Returns the number of pages used."""
    questions = exam["questions"]
    left_x = MARGIN + MARKER_SIZE + 6
    right_x = PAGE_W - MARGIN - MARKER_SIZE - 6
    content_width = right_x - left_x
    col_width = (content_width - COL_GAP) / 2
    opt_col_width = (col_width - 10) / 2

    bottom_limit = 22 + MARKER_SIZE + 18

    prepared = [_prepare_question(q, col_width, opt_col_width) for q in questions]

    def simulate():
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

    total_paper_pages = simulate()

    page_num = 1
    col = 0
    _draw_corner_markers(c)
    header_bottom = _draw_paper_header(c, exam, page_num, total_paper_pages, flavor)
    header_bottom = _draw_paper_instructions(c, header_bottom, flavor)

    col_x = [left_x, left_x + col_width + COL_GAP]
    cur_y = [header_bottom, header_bottom]

    def new_page():
        nonlocal page_num, col, cur_y, header_bottom
        c.showPage()
        page_num += 1
        _draw_corner_markers(c)
        header_bottom = _draw_paper_header(c, exam, page_num, total_paper_pages, flavor)
        header_bottom = _draw_paper_instructions(c, header_bottom, flavor)
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
        for i, letter in enumerate(ANS_LETTERS):
            row = i // 2
            colpos = i % 2
            bx = x0 + colpos * (opt_col_width + 10)
            row_top = options_top if row == 0 else options_top - p["option_row_h"][0] - 4

            if flavor == "teacher" and letter == q["correct"]:
                imgs = p["option_images"][letter]
                w = max((im[1] for im in imgs), default=opt_col_width - 8)
                h = sum(im[2] for im in imgs)
                c.setFillColorRGB(0.82, 0.96, 0.87)
                c.roundRect(bx - 2, row_top - h - 2, min(w, opt_col_width - 4) + 8, h + 6, 3, fill=1, stroke=0)
                c.setFillColorRGB(0, 0, 0)

            oy = row_top
            for img_png, img_w, img_h in p["option_images"][letter]:
                _draw_image(c, img_png, bx + 4, oy, img_w, img_h)
                oy -= img_h

        cur_y[col] = options_top - p["option_row_h"][0] - 4 - p["option_row_h"][1] - GAP_AFTER_OPTIONS

    return total_paper_pages


# ============================================================= Answer Sheet
def _answer_sheet_geometry(num_questions):
    """Pure function of question count: returns
    {q_number: (page_index_0based, col_index, row_index_within_col)}
    and the number of answer-sheet pages needed."""
    left_x = MARGIN + MARKER_SIZE + 6
    right_x = PAGE_W - MARGIN - MARKER_SIZE - 6
    content_width = right_x - left_x
    max_cols = max(1, int((content_width + ANS_COL_GAP) // (ANS_COL_W + ANS_COL_GAP)))
    per_page = max_cols * ANS_ROWS_PER_COL

    positions = {}
    for i in range(num_questions):
        qnum = i + 1
        page = i // per_page
        within_page = i % per_page
        col = within_page // ANS_ROWS_PER_COL
        row = within_page % ANS_ROWS_PER_COL
        positions[qnum] = (page, col, row)
    total_pages = max(1, -(-num_questions // per_page)) if num_questions else 1
    return positions, total_pages, max_cols


def _draw_answer_sheet_header(c, exam, page_num, total_pages):
    left_x = MARGIN + MARKER_SIZE + 6
    right_x = PAGE_W - MARGIN - MARKER_SIZE - 6
    top = PAGE_H - 22 - MARKER_SIZE - 6

    c.setFont(FONT_BOLD, 20)
    c.drawString(left_x, top - 18, "Answer Sheet")

    box_w, box_h = 190, 40
    box_x, box_y = right_x - box_w, top - box_h
    c.setLineWidth(1)
    c.setStrokeColorRGB(0.2, 0.2, 0.2)
    c.rect(box_x, box_y, box_w, box_h, fill=0, stroke=1)
    c.setFont(FONT, 10)
    c.drawString(box_x + 8, box_y + box_h - 15, "Name: " + "_" * 22)
    c.drawString(box_x + 8, box_y + 8, "Date: " + "_" * 22)

    sub_y = min(top - 34, box_y - 12)
    c.setFont(FONT, HEADER_FONT_SIZE)
    total_marks = exam.get("total_marks", exam["num_questions"])
    c.drawString(
        left_x, sub_y,
        f"{exam['school_name']}  |  {exam['grade']}  |  Exam ID: {exam['exam_id']}  |  {exam['num_questions']} questions, {total_marks} marks"
    )

    sub_y -= 16
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(left_x, sub_y, "Fill each bubble completely with a dark pen or pencil. One answer per question.")
    if total_pages > 1:
        c.setFont(FONT, HEADER_FONT_SIZE)
        c.drawRightString(right_x, sub_y, f"Page {page_num}/{total_pages}")

    return sub_y - 20


def _render_answer_sheet(c, exam, flavor, is_first_section_page):
    """Draws the answer sheet section (1+ pages). Returns
    (layout_questions, total_pages, markers_by_page) where layout_questions
    is {q_number: {"page": 1-based within this section, "options": {letter: [fx, fy]}}}
    and markers_by_page[page_idx] is the [TL, TR, BL, BR] marker-center
    fractions for that answer-sheet page."""
    questions = exam["questions"]
    num_questions = len(questions)
    positions, total_pages, _max_cols = _answer_sheet_geometry(num_questions)

    left_x = MARGIN + MARKER_SIZE + 6

    layout_questions = {}
    markers_by_page = []

    for page_idx in range(total_pages):
        if not is_first_section_page or page_idx > 0:
            c.showPage()
        markers = _draw_corner_markers(c)
        markers_by_page.append([_to_frac(x + MARKER_SIZE / 2, y + MARKER_SIZE / 2) for x, y in markers])
        grid_top = _draw_answer_sheet_header(c, exam, page_idx + 1, total_pages)

        for q in questions:
            qnum = q["number"]
            p_idx, col, row = positions[qnum]
            if p_idx != page_idx:
                continue

            col_x = left_x + col * (ANS_COL_W + ANS_COL_GAP)
            row_y = grid_top - row * ANS_ROW_H

            c.setFont(FONT_BOLD, 10)
            c.drawRightString(col_x + ANS_NUM_W - 6, row_y - 4, f"{qnum}.")

            option_positions = {}
            for i, letter in enumerate(ANS_LETTERS):
                cx = col_x + ANS_NUM_W + i * ANS_CENTER_GAP + ANS_CENTER_GAP / 2
                cy = row_y - ANS_ROW_H / 2 + 6
                is_correct = flavor == "teacher" and letter == q["correct"]
                c.setLineWidth(0.9)
                c.setStrokeColorRGB(0, 0, 0)
                if is_correct:
                    c.setFillColorRGB(0, 0, 0)
                    c.circle(cx, cy, ANS_BUBBLE_R, stroke=1, fill=1)
                    c.setFillColorRGB(1, 1, 1)
                else:
                    c.setFillColorRGB(0, 0, 0)
                    c.circle(cx, cy, ANS_BUBBLE_R, stroke=1, fill=0)
                c.setFont(FONT, 7.5)
                c.drawCentredString(cx, cy - 2.6, letter)
                c.setFillColorRGB(0, 0, 0)
                option_positions[letter] = list(_to_frac(cx, cy))

            layout_questions[str(qnum)] = {"page": page_idx + 1, "options": option_positions}

    return layout_questions, total_pages, markers_by_page


# ================================================================ Entrypoint
def render_exam_pdf(exam, flavor="student"):
    """Returns (pdf_bytes, layout). `layout["questions"][n]["page"]` is
    1-indexed within the answer sheet section only."""
    assert flavor in ("teacher", "student")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    _render_question_paper(c, exam, flavor)
    c.showPage()
    layout_questions, sheet_pages, markers_by_page = _render_answer_sheet(c, exam, flavor, is_first_section_page=True)

    if flavor == "teacher":
        c.showPage()
        _draw_corner_markers(c)
        c.setFont(FONT_BOLD, 13)
        c.drawCentredString(PAGE_W / 2, PAGE_H - 60, "Answer Key")
        c.setFont(FONT, 10)
        y = PAGE_H - 90
        col_w = (PAGE_W - 2 * MARGIN) / 4
        for i, q in enumerate(exam["questions"]):
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
        "sheet_pages": sheet_pages,
        "markers_by_page": markers_by_page,
        "questions": layout_questions,
    }
    return pdf_bytes, layout
