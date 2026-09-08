"""
Builds a full exam (question selection + metadata) for a given grade and
question count, using the area weights in curriculum.py and the question
bank in data/question_bank.json. The finished exam (including the answer
key) is persisted to data/exams/<exam_id>.json so it can be looked up
later by the OMR corrector.
"""
import json
import os
import random
import uuid
from datetime import datetime, timezone

from curriculum import GRADES, allocate_question_counts, AREA_LABELS
from exam_pdf import render_exam_pdf

BASE_DIR = os.path.dirname(__file__)
BANK_PATH = os.path.join(BASE_DIR, "data", "question_bank.json")
EXAMS_DIR = os.path.join(BASE_DIR, "data", "exams")

os.makedirs(EXAMS_DIR, exist_ok=True)

_bank_cache = None


def load_bank():
    global _bank_cache
    if _bank_cache is None:
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            _bank_cache = json.load(f)
    return _bank_cache


def _pool(area, cycle):
    return [q for q in load_bank() if q["area"] == area and q["cycle"] == cycle]


def pick_questions_for_area(area, cycle, count, rnd, used_texts):
    pool = _pool(area, cycle)
    if count > len(pool):
        raise ValueError(
            f"Not enough questions in bank for area '{area}' cycle {cycle}: "
            f"need {count}, have {len(pool)}"
        )
    rnd.shuffle(pool)
    chosen = []
    for q in pool:
        if len(chosen) == count:
            break
        if q["text"] in used_texts:
            continue
        chosen.append(q)
        used_texts.add(q["text"])
    if len(chosen) < count:
        # Ran out of non-duplicate-text options (very unlikely); fill with
        # whatever remains rather than under-filling the exam.
        for q in pool:
            if len(chosen) == count:
                break
            if q not in chosen:
                chosen.append(q)
    return chosen


def generate_exam(school_name: str, grade: str, num_questions: int, seed=None):
    if grade not in GRADES:
        raise ValueError(f"Unknown or out-of-scope grade: {grade}")
    if not school_name or not school_name.strip():
        raise ValueError("School name is required")

    cycle, track, _weights = GRADES[grade]
    counts = allocate_question_counts(grade, num_questions)

    rnd = random.Random(seed)
    used_texts = set()
    selected = []
    for area, count in counts.items():
        for q in pick_questions_for_area(area, cycle, count, rnd, used_texts):
            selected.append(q)

    rnd.shuffle(selected)

    questions = []
    for idx, q in enumerate(selected, start=1):
        questions.append(
            {
                "number": idx,
                "bank_id": q["id"],
                "area": q["area"],
                "area_label": AREA_LABELS[q["area"]],
                "text": q["text"],
                "options": dict(q["options"]),
                "correct": q["correct"],
            }
        )

    exam_id = uuid.uuid4().hex[:10]
    exam = {
        "exam_id": exam_id,
        "school_name": school_name.strip(),
        "grade": grade,
        "cycle": cycle,
        "track": track,
        "num_questions": len(questions),
        "area_breakdown": counts,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "questions": questions,
    }
    _, layout = render_exam_pdf(exam, "student")
    exam["num_pages"] = max(v["page"] for v in layout["questions"].values())
    save_exam(exam)
    return exam


def save_exam(exam):
    path = os.path.join(EXAMS_DIR, f"{exam['exam_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(exam, f, ensure_ascii=False, indent=2)


def load_exam(exam_id):
    path = os.path.join(EXAMS_DIR, f"{exam_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_exams():
    exams = []
    for fname in sorted(os.listdir(EXAMS_DIR), reverse=True):
        if fname.endswith(".json"):
            with open(os.path.join(EXAMS_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            exams.append(
                {
                    "exam_id": data["exam_id"],
                    "school_name": data["school_name"],
                    "grade": data["grade"],
                    "num_questions": data["num_questions"],
                    "created_at": data["created_at"],
                }
            )
    return exams
