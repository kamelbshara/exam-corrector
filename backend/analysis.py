"""Aggregates a set of graded results for one exam into a class-wide grade
analysis: performance-level distribution and per-topic averages, so a
learning gap that recurs across the class (not just one student) is
visible on top of each student's own weak-area list (already computed per
result by omr_corrector.grade_exam)."""

LEVELS = ["Advanced", "Proficient", "Acceptable", "Needs Support"]
GAP_THRESHOLD = 70


def build_class_analysis(exam, records):
    total_marks = exam.get("total_marks", exam["num_questions"])
    area_labels = {q["area"]: q["area_label"] for q in exam["questions"]}
    areas = sorted(area_labels)

    level_counts = {lvl: 0 for lvl in LEVELS}
    area_correct = {a: 0 for a in areas}
    area_total = {a: 0 for a in areas}
    sum_pct = 0.0
    sum_marks = 0
    students = []

    for rec in records:
        r = rec["result"]
        level_counts[r["level"]] = level_counts.get(r["level"], 0) + 1
        sum_pct += r["percentage"]
        marks_earned = r.get("marks_earned", r["correct"])
        sum_marks += marks_earned
        for area, sec in r["sections"].items():
            area_correct[area] = area_correct.get(area, 0) + sec["correct"]
            area_total[area] = area_total.get(area, 0) + sec["total"]
        students.append(
            {
                "result_id": rec["result_id"],
                "student_id": rec.get("student_id"),
                "student_name": rec["student_name"],
                "percentage": r["percentage"],
                "marks_earned": marks_earned,
                "total_marks": r.get("total_marks", r["num_questions"]),
                "level": r["level"],
                "weak_areas": r["weak_areas"],
            }
        )

    students.sort(key=lambda s: s["percentage"])

    n = len(records)
    area_breakdown = []
    for a in areas:
        total = area_total.get(a, 0)
        correct = area_correct.get(a, 0)
        pct = round((correct / total) * 100, 1) if total else 0.0
        area_breakdown.append(
            {
                "area": a,
                "label": area_labels[a],
                "correct": correct,
                "total": total,
                "percentage": pct,
                "is_gap": bool(total) and pct < GAP_THRESHOLD,
            }
        )
    area_breakdown.sort(key=lambda x: x["percentage"])
    class_weak_areas = [a["label"] for a in area_breakdown if a["is_gap"]]

    return {
        "exam_id": exam["exam_id"],
        "num_graded": n,
        "class_average_percentage": round(sum_pct / n, 1) if n else 0.0,
        "class_average_marks": round(sum_marks / n, 1) if n else 0.0,
        "total_marks": total_marks,
        "level_distribution": level_counts,
        "areas": area_breakdown,
        "class_weak_areas": class_weak_areas,
        "students": students,
    }
