"""
Curriculum configuration: grades in scope, their cycle, and the relative
weight of each math area for that grade (from the school's math-area
weighting table). Only Cycle 2 (General track) and Cycle 3 (Advanced +
General tracks) are in scope; Cycle 1 and every Applied/Elective track are
intentionally excluded.
"""

AREAS = ["numbers", "algebra", "functions", "statistics", "geometry", "calculus"]

AREA_LABELS = {
    "numbers": "Numbers and Operations",
    "algebra": "Algebra",
    "functions": "Functions",
    "statistics": "Statistics and Probability",
    "geometry": "Geometry",
    "calculus": "Calculus",
}

AREA_LABELS_AR = {
    "numbers": "الأعداد والعمليات",
    "algebra": "الجبر",
    "functions": "الدوال",
    "statistics": "الإحصاء والاحتمالات",
    "geometry": "الهندسة",
    "calculus": "التفاضل والتكامل",
}

# grade -> (cycle, track_label, {area: weight_percent})
GRADES = {
    "G5Gen":  (2, "General",  {"numbers": 60, "statistics": 5,  "geometry": 35}),
    "G6Gen":  (2, "General",  {"numbers": 45, "algebra": 10, "statistics": 5,  "geometry": 40}),
    "G7Gen":  (2, "General",  {"numbers": 40, "algebra": 30, "statistics": 15, "geometry": 15}),
    "G8Gen":  (2, "General",  {"numbers": 35, "algebra": 25, "statistics": 20, "geometry": 20}),

    "G9Adv":  (3, "Advanced", {"numbers": 25, "algebra": 15, "statistics": 10, "geometry": 50}),
    "G9Gen":  (3, "General",  {"numbers": 25, "algebra": 15, "statistics": 10, "geometry": 50}),
    "G10Adv": (3, "Advanced", {"algebra": 40, "functions": 15, "geometry": 45}),
    "G10Gen": (3, "General",  {"algebra": 20, "functions": 35, "geometry": 45}),
    "G11Adv": (3, "Advanced", {"numbers": 5, "algebra": 10, "functions": 40, "statistics": 20, "geometry": 25}),
    "G11Gen": (3, "General",  {"algebra": 45, "statistics": 5, "geometry": 50}),
    "G12Adv": (3, "Advanced", {"algebra": 45, "functions": 15, "geometry": 40}),
    "G12Gen": (3, "General",  {"algebra": 55, "functions": 20, "geometry": 25}),
}

# Sanity check: every grade's weights must sum to 100.
for _g, (_c, _t, _w) in GRADES.items():
    assert sum(_w.values()) == 100, f"{_g} weights sum to {sum(_w.values())}, not 100"

MAX_QUESTIONS_PER_EXAM = 25
QUESTIONS_PER_AREA_PER_CYCLE = 20


def grades_for_cycle(cycle: int):
    return [g for g, (c, _t, _w) in GRADES.items() if c == cycle]


TOTAL_MARKS = 100


def allocate_marks(num_questions: int):
    """Largest-remainder apportionment of TOTAL_MARKS across num_questions,
    so the exam is always out of 100 regardless of how many questions it
    has. Returns a list of per-question integer marks summing to 100."""
    if num_questions <= 0:
        return []
    base = TOTAL_MARKS // num_questions
    remainder = TOTAL_MARKS % num_questions
    return [base + 1 if i < remainder else base for i in range(num_questions)]


def allocate_question_counts(grade: str, total_questions: int):
    """Largest-remainder apportionment of `total_questions` across the
    grade's weighted areas, so the split always sums exactly to total."""
    if grade not in GRADES:
        raise ValueError(f"Unknown grade: {grade}")
    if not (1 <= total_questions <= MAX_QUESTIONS_PER_EXAM):
        raise ValueError(f"total_questions must be between 1 and {MAX_QUESTIONS_PER_EXAM}")

    _cycle, _track, weights = GRADES[grade]
    areas = list(weights.keys())

    raw = {a: (weights[a] / 100.0) * total_questions for a in areas}
    floors = {a: int(raw[a]) for a in areas}
    remainder = total_questions - sum(floors.values())

    order = sorted(areas, key=lambda a: (raw[a] - floors[a]), reverse=True)
    for a in order[:remainder]:
        floors[a] += 1

    return {a: c for a, c in floors.items() if c > 0}
