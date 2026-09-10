"""Builds an Excel workbook summarizing every corrected sheet for one exam:
a raw per-question grid, and a summary grouped by performance level."""
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from analysis import build_class_analysis

HEADER_FILL = PatternFill(start_color="1f3a8a", end_color="1f3a8a", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
GAP_FILL = PatternFill(start_color="fee2e2", end_color="fee2e2", fill_type="solid")
BORDER = Border(*(Side(style="thin"),) * 4)
CENTER = Alignment(horizontal="center", vertical="center")


def build_report(exam, records):
    """`records` is the list of saved result records (from results_store)."""
    wb = Workbook()
    ws_raw = wb.active
    ws_raw.title = "Raw Data"
    ws_analysis = wb.create_sheet("Class Analysis")
    ws_summary = wb.create_sheet("Summary")

    num_q = exam["num_questions"]
    areas = sorted({q["area"] for q in exam["questions"]})
    area_labels = {q["area"]: q["area_label"] for q in exam["questions"]}

    headers = ["Student Name", "Graded At"] + [f"Q{i}" for i in range(1, num_q + 1)] + \
        ["Correct", "Marks", "Score (/100)", "Level"] + [area_labels[a] for a in areas] + ["Weak Areas"]

    for col, header in enumerate(headers, 1):
        cell = ws_raw.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = CENTER

    row = 2
    for rec in records:
        result = rec["result"]
        answers_by_num = {a["number"]: a for a in result["answers"]}
        col = 1
        ws_raw.cell(row, col, rec["student_name"]); col += 1
        ws_raw.cell(row, col, rec["graded_at"]); col += 1
        for i in range(1, num_q + 1):
            ans = answers_by_num.get(i)
            ws_raw.cell(row, col, ans["selected"] if ans else "")
            col += 1
        ws_raw.cell(row, col, f"{result['correct']}/{result['num_questions']}"); col += 1
        ws_raw.cell(row, col, f"{result.get('marks_earned', result['correct'])}/{result.get('total_marks', result['num_questions'])}"); col += 1
        ws_raw.cell(row, col, f"{result['percentage']}%"); col += 1
        ws_raw.cell(row, col, result["level"]); col += 1
        for a in areas:
            sec = result["sections"].get(a)
            ws_raw.cell(row, col, f"{sec['percentage']}%" if sec else "")
            col += 1
        ws_raw.cell(row, col, ", ".join(result["weak_areas"]))
        row += 1

    for col_idx in range(1, len(headers) + 1):
        ws_raw.column_dimensions[ws_raw.cell(1, col_idx).column_letter].width = 14

    # ---- Class Analysis sheet: grade analysis + class-wide learning gaps ----
    analysis = build_class_analysis(exam, records)

    ws_analysis["A1"] = f"Class Grade Analysis - {exam['school_name']} - {exam['grade']}"
    ws_analysis["A1"].font = Font(size=14, bold=True)
    ws_analysis["A2"] = (
        f"Exam ID: {exam['exam_id']}  |  Sheets graded: {analysis['num_graded']}  |  "
        f"Class average: {analysis['class_average_marks']}/{analysis['total_marks']} "
        f"({analysis['class_average_percentage']}%)"
    )

    r = 4
    ws_analysis.cell(r, 1, "Performance Level Distribution").font = Font(bold=True, size=12)
    r += 1
    for col, header in enumerate(["Level", "Students", "% of Class"], 1):
        cell = ws_analysis.cell(r, col, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = CENTER
    r += 1
    n = analysis["num_graded"] or 1
    for lvl, count in analysis["level_distribution"].items():
        ws_analysis.cell(r, 1, lvl)
        ws_analysis.cell(r, 2, count)
        ws_analysis.cell(r, 3, f"{round(count / n * 100, 1)}%")
        r += 1

    r += 2
    ws_analysis.cell(r, 1, "Class-wide Learning Gap Analysis (by topic, weakest first)").font = Font(bold=True, size=12)
    r += 1
    for col, header in enumerate(["Area", "Correct", "Total", "Class Average %"], 1):
        cell = ws_analysis.cell(r, col, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = CENTER
    r += 1
    for a in analysis["areas"]:
        ws_analysis.cell(r, 1, a["label"])
        ws_analysis.cell(r, 2, a["correct"])
        ws_analysis.cell(r, 3, a["total"])
        pct_cell = ws_analysis.cell(r, 4, f"{a['percentage']}%")
        if a["is_gap"]:
            for col in range(1, 5):
                ws_analysis.cell(r, col).fill = GAP_FILL
        r += 1

    if analysis["class_weak_areas"]:
        r += 1
        ws_analysis.cell(r, 1, f"Class-wide weak area(s): {', '.join(analysis['class_weak_areas'])}").font = Font(
            italic=True, color="991b1b"
        )

    r += 2
    ws_analysis.cell(r, 1, "Per-Student Learning Gaps (weakest first)").font = Font(bold=True, size=12)
    r += 1
    for col, header in enumerate(["Student", "Score", "Level", "Weak Area(s)"], 1):
        cell = ws_analysis.cell(r, col, header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = CENTER
    r += 1
    for s in analysis["students"]:
        ws_analysis.cell(r, 1, s["student_name"])
        ws_analysis.cell(r, 2, f"{s['marks_earned']}/{s['total_marks']} ({s['percentage']}%)")
        ws_analysis.cell(r, 3, s["level"])
        ws_analysis.cell(r, 4, ", ".join(s["weak_areas"]) or "-")
        r += 1

    ws_analysis.column_dimensions["A"].width = 34
    ws_analysis.column_dimensions["B"].width = 20
    ws_analysis.column_dimensions["C"].width = 14
    ws_analysis.column_dimensions["D"].width = 40

    # ---- Summary sheet ----
    ws_summary["A1"] = f"Summary - {exam['school_name']} - {exam['grade']}"
    ws_summary["A1"].font = Font(size=14, bold=True)
    ws_summary["A2"] = f"Exam ID: {exam['exam_id']}  |  Questions: {num_q}  |  Sheets graded: {len(records)}"

    levels = ["Advanced", "Proficient", "Acceptable", "Needs Support"]
    grouped = {lvl: [] for lvl in levels}
    for rec in records:
        grouped.setdefault(rec["result"]["level"], []).append(rec)

    r = 4
    for lvl in levels:
        items = grouped.get(lvl, [])
        ws_summary.cell(r, 1, f"{lvl}: {len(items)} student(s)").font = Font(bold=True, size=11)
        r += 1
        for rec in items:
            ws_summary.cell(r, 2, f"{rec['student_name']}: {rec['result']['percentage']}%")
            r += 1
        r += 1

    ws_summary.column_dimensions["A"].width = 22
    ws_summary.column_dimensions["B"].width = 32

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
