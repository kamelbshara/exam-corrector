"""Stores the class roster (student list) uploaded for one exam, so a
teacher can correct sheets against a known list of students instead of
re-typing a name each time, and see at a glance who's been graded."""
import json
import os
import uuid

from openpyxl import load_workbook

BASE_DIR = os.path.dirname(__file__)
ROSTERS_DIR = os.path.join(BASE_DIR, "data", "rosters")
os.makedirs(ROSTERS_DIR, exist_ok=True)


def _path(exam_id):
    return os.path.join(ROSTERS_DIR, f"{exam_id}.json")


def parse_roster_file(file_stream):
    """Reads an uploaded .xlsx roster: first column = student name,
    second column (optional) = class/section. First row is treated as a
    header only if its first cell isn't itself a plausible name (we just
    skip a row whose first cell is blank)."""
    wb = load_workbook(file_stream, read_only=True, data_only=True)
    ws = wb.active
    students = []
    header_skipped = False
    for row in ws.iter_rows(values_only=True):
        if not row or not row[0]:
            continue
        name = str(row[0]).strip()
        class_name = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        if not header_skipped and name.lower() in ("name", "student name", "student"):
            header_skipped = True
            continue
        header_skipped = True
        students.append(
            {
                "student_id": uuid.uuid4().hex[:8],
                "name": name,
                "class_name": class_name,
            }
        )
    return students


def save_roster(exam_id, students):
    with open(_path(exam_id), "w", encoding="utf-8") as f:
        json.dump({"exam_id": exam_id, "students": students}, f, ensure_ascii=False, indent=2)
    return students


def load_roster(exam_id):
    path = _path(exam_id)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["students"]


def delete_roster(exam_id):
    path = _path(exam_id)
    if os.path.exists(path):
        os.remove(path)
