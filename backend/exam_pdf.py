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
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

PAGE_W, PAGE_H = A4

MARGIN = 42
MARKER_SIZE = 16          # corner alignment squares, in points
CONTENT_TOP_MARGIN = 42   # extra space below header before the grid starts
COL_GAP = 18
BUBBLE_R = 5.2
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
Q_FONT_SIZE = 9
OPT_FONT_SIZE = 8.5
HEADER_FONT_SIZE = 9


def _wrap(text, font, size, max_width):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if stringWidth(trial, font, size) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


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
    c.drawRightString(right_x, top, f"Questions: {exam['num_questions']}")

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

    TEXT_LINE_H = 11
    GAP_TEXT_TO_OPTIONS = 9
    OPTION_ROW_H = 16
    GAP_AFTER_OPTIONS = 16

    def question_row_height(lines):
        return len(lines) * TEXT_LINE_H + GAP_TEXT_TO_OPTIONS + 2 * OPTION_ROW_H + GAP_AFTER_OPTIONS

    layout_questions = {}
    markers_by_page = []

    # First pass to know page count isn't trivial without simulating layout,
    # so we simulate first, then render with the known total page count.
    def simulate():
        page = 1
        col = 0
        y = PAGE_H - 170  # approx header height, refined below per real header
        pages = 1
        col_x = [left_x, left_x + col_width + COL_GAP]
        cur_y = [y, y]
        for q in questions:
            lines = _wrap(q["text"], FONT, Q_FONT_SIZE, col_width)
            row_h = question_row_height(lines)
            if cur_y[col] - row_h < bottom_limit:
                col += 1
                if col > 1:
                    col = 0
                    pages += 1
                    cur_y = [PAGE_H - 170, PAGE_H - 170]
            cur_y[col] -= row_h
        return pages

    total_pages = simulate() + (1 if flavor == "teacher" else 0)  # +1 for the trailing answer-key page (teacher only)

    page_num = 1
    col = 0
    markers = _draw_corner_markers(c)
    markers_by_page.append([_to_frac(x + MARKER_SIZE / 2, y + MARKER_SIZE / 2) for x, y in markers])
    header_bottom = _draw_header(c, exam, page_num, total_pages, flavor)
    header_bottom = _draw_instructions(c, header_bottom, flavor)

    col_x = [left_x, left_x + col_width + COL_GAP]
    col_top = header_bottom
    cur_y = [col_top, col_top]

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

    for q in questions:
        lines = _wrap(q["text"], FONT, Q_FONT_SIZE, col_width)
        row_h = question_row_height(lines)

        if cur_y[col] - row_h < bottom_limit:
            col += 1
            if col > 1:
                new_page()
            else:
                pass

        x0 = col_x[col]
        y = cur_y[col]

        c.setFont(FONT_BOLD, Q_FONT_SIZE)
        c.drawString(x0, y, f"Q{q['number']}.")
        c.setFont(FONT, Q_FONT_SIZE)
        num_w = stringWidth(f"Q{q['number']}. ", FONT_BOLD, Q_FONT_SIZE)
        for i, line in enumerate(lines):
            tx = x0 + (num_w if i == 0 else 8)
            c.drawString(tx, y - i * TEXT_LINE_H, line)

        options_top = y - len(lines) * TEXT_LINE_H - GAP_TEXT_TO_OPTIONS

        option_positions = {}
        letters = ["A", "B", "C", "D"]
        for i, letter in enumerate(letters):
            row = i // 2
            colpos = i % 2
            bx = x0 + 8 + colpos * (opt_col_width + 10)
            by = options_top - row * OPTION_ROW_H
            cx, cy = bx + BUBBLE_R, by
            c.setLineWidth(0.8)
            c.setStrokeColorRGB(0, 0, 0)
            is_correct = (letter == q["correct"])
            fill_this = flavor == "teacher" and is_correct
            c.circle(cx, cy, BUBBLE_R, stroke=1, fill=1 if fill_this else 0)
            opt_text = f"{letter}. {q['options'][letter]}"
            max_opt_w = opt_col_width - (2 * BUBBLE_R + 6)
            opt_lines = _wrap(opt_text, FONT, OPT_FONT_SIZE, max_opt_w)
            c.setFont(FONT, OPT_FONT_SIZE)
            c.drawString(cx + BUBBLE_R + 5, cy - 3, opt_lines[0])
            option_positions[letter] = list(_to_frac(cx, cy))

        cur_y[col] = options_top - 2 * OPTION_ROW_H - GAP_AFTER_OPTIONS

        layout_questions[str(q["number"])] = {
            "page": page_num,
            "options": option_positions,
        }

    # Trailing answer-key page (both flavors, so the teacher copy is
    # self-contained; harmless duplication on the student copy since that
    # copy is never distributed with answers... actually only include on
    # teacher flavor)
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
            c.drawString(x, yy, f"Q{q['number']}: {q['correct']}  ({q['area_label']})")

    c.save()
    pdf_bytes = buf.getvalue()

    layout = {
        "page_size": [PAGE_W, PAGE_H],
        "markers_by_page": markers_by_page,
        "questions": layout_questions,
    }
    return pdf_bytes, layout
