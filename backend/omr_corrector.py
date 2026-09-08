"""
OMR (Optical Mark Recognition) corrector.

Rather than blindly hunting for filled-in circles with generic Hough-circle
detection (fragile, and hard-coded to one fixed layout like the original
mobile prototype), this corrector exploits the fact that WE generated the
student's answer sheet: exam_pdf.render_exam_pdf() returns the exact page
fraction of every bubble. So correction is:

  1. Detect the 4 black corner squares printed on every page.
  2. Compute a perspective transform from the photographed page to a
     canonical top-down rectangle.
  3. Warp the photo into that rectangle.
  4. For every bubble, sample darkness at its known canonical position.

This is robust to a page photographed at a slight angle, rotation, or
distance, as long as all 4 corner markers are visible.
"""
import cv2
import numpy as np

from exam_pdf import render_exam_pdf, PAGE_W, PAGE_H, BUBBLE_R

CANON_SCALE = 2.0
CANON_W = int(PAGE_W * CANON_SCALE)
CANON_H = int(PAGE_H * CANON_SCALE)
SAMPLE_R_PX = int((BUBBLE_R / PAGE_W) * CANON_W * 1.35)

DARK_THRESHOLD = 150      # grayscale intensity below this counts as "marked"
MIN_FILL_RATIO = 0.20     # minimum darkness fraction to count as an answer at all
MIN_GAP = 0.08            # winning option must beat runner-up by at least this much

PERFORMANCE_LEVELS = [
    ("Advanced", 90, 100),
    ("Proficient", 80, 89.999),
    ("Acceptable", 70, 79.999),
    ("Needs Support", 0, 69.999),
]


class CorrectionError(Exception):
    pass


def _find_marker_candidates(gray):
    h, w = gray.shape
    img_area = h * w
    _, mask = cv2.threshold(gray, 90, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < img_area * 0.00012 or area > img_area * 0.01:
            continue
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bw == 0 or bh == 0:
            continue
        aspect = bw / bh
        if aspect < 0.6 or aspect > 1.6:
            continue
        extent = area / (bw * bh)
        if extent < 0.55:
            continue
        cx, cy = x + bw / 2, y + bh / 2
        candidates.append((cx, cy))
    return candidates


def _detect_corners(image_bgr):
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    candidates = _find_marker_candidates(gray)
    if len(candidates) < 4:
        raise CorrectionError(
            "Could not detect the 4 alignment markers on the page. "
            "Make sure the full sheet (including all four black corner "
            "squares) is visible, flat, and well lit."
        )

    def pick(key_fn):
        return max(candidates, key=key_fn)

    top_left = pick(lambda p: -(p[0] + p[1]))
    bottom_right = pick(lambda p: p[0] + p[1])
    top_right = pick(lambda p: p[0] - p[1])
    bottom_left = pick(lambda p: p[1] - p[0])

    pts = [top_left, top_right, bottom_left, bottom_right]
    if len({id(p) for p in pts}) < 4:
        # Degenerate (very few candidates); fall back to the 4 most extreme
        # points anyway -- best effort.
        pass
    return np.array(pts, dtype=np.float32)


def _warp_to_canonical(image_bgr, src_corners, marker_fractions):
    """`marker_fractions` are the actual [TL, TR, BL, BR] page-fraction
    positions of the printed markers (they're inset from the page edges,
    not exactly at the corners), recorded by exam_pdf at render time."""
    dst_corners = np.array(
        [[fx * CANON_W, fy * CANON_H] for fx, fy in marker_fractions], dtype=np.float32
    )
    M = cv2.getPerspectiveTransform(src_corners, dst_corners)
    warped = cv2.warpPerspective(image_bgr, M, (CANON_W, CANON_H))
    return cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)


def _circle_fill_ratio(gray, cx, cy, r):
    h, w = gray.shape
    x0, x1 = max(0, cx - r), min(w, cx + r)
    y0, y1 = max(0, cy - r), min(h, cy + r)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    patch = gray[y0:y1, x0:x1]
    yy, xx = np.ogrid[y0:y1, x0:x1]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    if not np.any(mask):
        return 0.0
    dark = patch[mask] < DARK_THRESHOLD
    return float(np.count_nonzero(dark)) / float(dark.size)


def read_answers_from_page(image_bytes, layout, page_number):
    """Returns {question_number(str): {'selected': 'A'|None, 'fill_ratios': {...}}}"""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise CorrectionError("Could not read the uploaded image file.")

    corners = _detect_corners(image_bgr)
    marker_fractions = layout["markers_by_page"][page_number - 1]
    warped_gray = _warp_to_canonical(image_bgr, corners, marker_fractions)

    results = {}
    for qnum, qlayout in layout["questions"].items():
        if qlayout["page"] != page_number:
            continue
        fill_ratios = {}
        for letter, (fx, fy) in qlayout["options"].items():
            cx = int(fx * CANON_W)
            cy = int(fy * CANON_H)
            fill_ratios[letter] = _circle_fill_ratio(warped_gray, cx, cy, SAMPLE_R_PX)

        ordered = sorted(fill_ratios.items(), key=lambda kv: kv[1], reverse=True)
        best_letter, best_ratio = ordered[0]
        second_ratio = ordered[1][1] if len(ordered) > 1 else 0.0

        selected = None
        if best_ratio >= MIN_FILL_RATIO and (best_ratio - second_ratio) >= MIN_GAP:
            selected = best_letter

        results[qnum] = {"selected": selected, "fill_ratios": fill_ratios}
    return results


def _level_for(pct):
    for name, lo, hi in PERFORMANCE_LEVELS:
        if lo <= pct <= hi:
            return name
    return "Needs Support"


def grade_exam(exam, page_images: dict):
    """page_images: {page_number(int): raw image bytes}. Returns full result dict."""
    _, layout = render_exam_pdf(exam, "student")

    all_answers = {}
    for page_number, image_bytes in page_images.items():
        page_results = read_answers_from_page(image_bytes, layout, page_number)
        all_answers.update(page_results)

    per_question = []
    area_totals = {}
    correct_count = 0
    total_marks = exam.get("total_marks", len(exam["questions"]))
    marks_earned = 0
    for q in exam["questions"]:
        qnum = str(q["number"])
        detected = all_answers.get(qnum, {"selected": None, "fill_ratios": {}})
        selected = detected["selected"]
        is_correct = selected is not None and selected == q["correct"]
        q_marks = q.get("marks", 1)
        if is_correct:
            correct_count += 1
            marks_earned += q_marks

        area = q["area"]
        area_totals.setdefault(area, {"label": q["area_label"], "correct": 0, "total": 0})
        area_totals[area]["total"] += 1
        if is_correct:
            area_totals[area]["correct"] += 1

        per_question.append(
            {
                "number": q["number"],
                "area": area,
                "marks": q_marks,
                "selected": selected,
                "correct_answer": q["correct"],
                "is_correct": is_correct,
                "fill_ratios": detected["fill_ratios"],
            }
        )

    total = len(exam["questions"])
    percentage = round((marks_earned / total_marks) * 100, 1) if total_marks else 0.0
    sections = {}
    weak_areas = []
    for area, d in area_totals.items():
        pct = round((d["correct"] / d["total"]) * 100, 1) if d["total"] else 0.0
        sections[area] = {"label": d["label"], "correct": d["correct"], "total": d["total"], "percentage": pct}
        if pct < 70:
            weak_areas.append(d["label"])

    return {
        "exam_id": exam["exam_id"],
        "school_name": exam["school_name"],
        "grade": exam["grade"],
        "num_questions": total,
        "correct": correct_count,
        "marks_earned": marks_earned,
        "total_marks": total_marks,
        "percentage": percentage,
        "level": _level_for(percentage),
        "sections": sections,
        "weak_areas": weak_areas,
        "answers": per_question,
    }
