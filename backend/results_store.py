"""Persists graded results (one per corrected student sheet) to disk,
grouped by exam_id, so a teacher can correct a whole class and then
export one combined report."""
import json
import os
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(__file__)
RESULTS_DIR = os.path.join(BASE_DIR, "data", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def _exam_dir(exam_id):
    d = os.path.join(RESULTS_DIR, exam_id)
    os.makedirs(d, exist_ok=True)
    return d


def save_result(exam_id, student_name, grading_result, student_id=None):
    result_id = uuid.uuid4().hex[:10]
    record = {
        "result_id": result_id,
        "exam_id": exam_id,
        "student_id": student_id,
        "student_name": (student_name or "").strip() or "Unnamed",
        "graded_at": datetime.now(timezone.utc).isoformat(),
        "result": grading_result,
    }
    path = os.path.join(_exam_dir(exam_id), f"{result_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


def delete_result(exam_id, result_id):
    path = os.path.join(_exam_dir(exam_id), f"{result_id}.json")
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True


def list_results(exam_id):
    d = _exam_dir(exam_id)
    records = []
    for fname in sorted(os.listdir(d)):
        if fname.endswith(".json"):
            with open(os.path.join(d, fname), "r", encoding="utf-8") as f:
                records.append(json.load(f))
    records.sort(key=lambda r: r["graded_at"], reverse=True)
    return records


def get_result(exam_id, result_id):
    path = os.path.join(_exam_dir(exam_id), f"{result_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
