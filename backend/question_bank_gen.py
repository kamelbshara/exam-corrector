"""
Generates the full question bank: 20 multiple-choice questions for every
(area, cycle) combination -> 6 areas x 2 cycles x 20 = 240 questions.

Cycle 2 pools are pitched at grades 5-8 (General track), Cycle 3 pools at
grades 9-12 (Advanced/General tracks). Cycle-2 "functions" and "calculus"
pools use age-appropriate pre-algebra / rate-of-change content rather than
true function notation or derivatives, since those topics are not yet
introduced at that level.

Question/option text uses inline math wrapped in $...$ with NO literal
spaces inside the delimiters (matplotlib mathtext and MathJax both accept
this "TeX-like" syntax and add correct spacing automatically around
operators) -- the same source string is rendered by matplotlib mathtext
for the printed PDF (exam_pdf.py / mathtext_render.py) and by MathJax for
the on-screen web preview, so there is exactly one source of truth for
every question's math.

Run directly to (re)write backend/data/question_bank.json:
    python3 question_bank_gen.py
"""
import json
import os
import random
from fractions import Fraction
from math import comb

import diagrams

QUESTIONS_PER_POOL = 20
LETTERS = ["A", "B", "C", "D"]


# --------------------------------------------------------------------------
# LaTeX helpers
# --------------------------------------------------------------------------

def tex(body):
    """Wrap a LaTeX body in $...$. Body must contain no literal spaces."""
    return f"${body}$"


def tex_term(coef, var):
    """Format coef*var without an ugly leading '1' or doubled sign."""
    if coef == 1:
        return var
    if coef == -1:
        return f"-{var}"
    return f"{coef}{var}"


def tex_signed(value, var=""):
    """' +N<var>' / ' -N<var>' as a LaTeX fragment (no leading space)."""
    if value >= 0:
        return f"+{tex_term(value, var) if var else value}"
    return f"-{tex_term(-value, var) if var else -value}"


def frac_body(v: Fraction):
    if v.denominator == 1:
        return str(v.numerator)
    sign = "-" if v.numerator < 0 else ""
    n = abs(v.numerator)
    return f"{sign}\\frac{{{n}}}{{{v.denominator}}}"


def tex_frac(v: Fraction):
    return tex(frac_body(v))


def build_mcq(qid, area, cycle, text, correct, distractors, fmt=str, diagram=None):
    """Shuffle correct + 3 distractors deterministically into A-D."""
    values = [correct] + list(distractors)
    rnd = random.Random(qid * 7919 + 17)
    order = [0, 1, 2, 3]
    rnd.shuffle(order)
    options = {}
    correct_letter = None
    for pos, orig_i in enumerate(order):
        letter = LETTERS[pos]
        options[letter] = fmt(values[orig_i])
        if orig_i == 0:
            correct_letter = letter
    return {
        "id": qid,
        "area": area,
        "cycle": cycle,
        "text": text,
        "options": options,
        "correct": correct_letter,
        "diagram": diagram,
    }


def unique_int_distractors(correct, rnd, spread, count=3, min_val=None):
    """Return `count` unique ints near `correct`, all != correct."""
    out = set()
    guard = 0
    while len(out) < count and guard < 200:
        guard += 1
        candidate = correct + rnd.randint(-spread, spread)
        if min_val is not None and candidate < min_val:
            continue
        if candidate == correct or candidate in out:
            continue
        out.add(candidate)
    filler = correct + spread + 1
    while len(out) < count:
        filler += 1
        if filler != correct:
            out.add(filler)
    return list(out)[:count]


def unique_frac_distractors(correct: Fraction, rnd, count=3):
    out = set()
    guard = 0
    while len(out) < count and guard < 200:
        guard += 1
        num_delta = rnd.randint(-3, 3)
        den_delta = rnd.choice([0, 0, 1, -1])
        cand = Fraction(correct.numerator + num_delta, max(1, correct.denominator + den_delta))
        if cand != correct and cand not in out and cand.denominator != 0:
            out.add(cand)
    return list(out)[:count]


def tex_frac_fmt(v: Fraction):
    return tex_frac(v)


# --------------------------------------------------------------------------
# Cycle 2 (grades 5-8) generators
# --------------------------------------------------------------------------

def gen_numbers_c2(qid_start):
    qs = []
    qid = qid_start
    templates = [
        "fraction_add", "decimal_mul", "percent_of", "order_ops",
        "integer_ops", "ratio_simplify",
    ]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(1000 + i)
        kind = templates[i % len(templates)]
        if kind == "fraction_add":
            d = rnd.choice([5, 6, 8, 10, 12])
            a = rnd.randint(1, d - 1)
            b = rnd.randint(1, d - 1)
            correct = Fraction(a, d) + Fraction(b, d)
            text = f"Calculate {tex(frac_body(Fraction(a, d)) + '+' + frac_body(Fraction(b, d)))} (simplest form)"
            distractors = unique_frac_distractors(correct, rnd)
            qs.append(build_mcq(qid, "numbers", 2, text, correct, distractors, tex_frac_fmt))
        elif kind == "decimal_mul":
            a = round(rnd.uniform(1.1, 9.9), 1)
            b = round(rnd.uniform(1.1, 9.9), 1)
            correct = round(a * b, 2)
            mul_body = f"{a}" + "\\times" + f"{b}"
            text = f"Calculate: {tex(mul_body)}"
            distractors = []
            while len(distractors) < 3:
                d = round(correct + rnd.choice([-5, -2, -1, 1, 2, 5]) * rnd.uniform(0.5, 1.5), 2)
                if d != correct and d not in distractors and d > 0:
                    distractors.append(d)
            qs.append(build_mcq(qid, "numbers", 2, text, correct, distractors))
        elif kind == "percent_of":
            pct = rnd.choice([10, 20, 25, 40, 50, 75])
            n = rnd.choice([40, 60, 80, 120, 160, 200])
            correct = int(pct / 100 * n)
            text = f"What is {pct}% of {n}?"
            distractors = unique_int_distractors(correct, rnd, spread=max(6, correct // 4), min_val=0)
            qs.append(build_mcq(qid, "numbers", 2, text, correct, distractors))
        elif kind == "order_ops":
            a = rnd.randint(2, 9)
            b = rnd.randint(2, 9)
            c = rnd.randint(2, 9)
            d = rnd.randint(1, 9)
            correct = a + b * c - d
            ops_body = f"{a}+{b}" + "\\times" + f"{c}-{d}"
            text = f"Calculate: {tex(ops_body)}"
            distractors = unique_int_distractors(correct, rnd, spread=8)
            qs.append(build_mcq(qid, "numbers", 2, text, correct, distractors))
        elif kind == "integer_ops":
            a = rnd.randint(-15, -2)
            b = rnd.randint(2, 15)
            op = rnd.choice(["+", "-"])
            correct = a + b if op == "+" else a - b
            text = f"Calculate: {tex(f'({a}){op}({b})')}"
            distractors = unique_int_distractors(correct, rnd, spread=10)
            qs.append(build_mcq(qid, "numbers", 2, text, correct, distractors))
        else:  # ratio_simplify
            base = rnd.randint(2, 9)
            k = rnd.choice([2, 3, 4, 5])
            a, b = base * k, (base + rnd.randint(1, 5)) * k

            def gcd(x, y):
                while y:
                    x, y = y, x % y
                return x

            gval = gcd(a, b)
            sa, sb = a // gval, b // gval
            correct = f"{sa}:{sb}"
            text = f"Simplify the ratio {a}:{b} to its simplest form."
            options_pool = [f"{sa+1}:{sb}", f"{sa}:{sb+1}", f"{sa}:{sb-1 if sb>1 else sb+2}"]
            qs.append(build_mcq(qid, "numbers", 2, text, correct, options_pool))
        qid += 1
    return qs


def gen_algebra_c2(qid_start):
    qs = []
    qid = qid_start
    templates = ["one_step", "two_step", "evaluate_expr", "simplify_like_terms"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(2000 + i)
        kind = templates[i % len(templates)]
        if kind == "one_step":
            x = rnd.randint(2, 20)
            a = rnd.randint(2, 9)
            rhs = a * x
            eq_body = f"{tex_term(a, 'x')}={rhs}"
            text = f"Solve for x: {tex(eq_body)}"
            correct = x
            distractors = unique_int_distractors(correct, rnd, spread=6, min_val=0)
            qs.append(build_mcq(qid, "algebra", 2, text, correct, distractors))
        elif kind == "two_step":
            x = rnd.randint(2, 15)
            a = rnd.randint(2, 8)
            b = rnd.randint(1, 20)
            rhs = a * x + b
            eq_body = f"{tex_term(a, 'x')}{tex_signed(b)}={rhs}"
            text = f"Solve for x: {tex(eq_body)}"
            correct = x
            distractors = unique_int_distractors(correct, rnd, spread=5, min_val=0)
            qs.append(build_mcq(qid, "algebra", 2, text, correct, distractors))
        elif kind == "evaluate_expr":
            x = rnd.randint(1, 10)
            a = rnd.randint(2, 6)
            b = rnd.randint(1, 15)
            correct = a * x + b
            expr_body = f"{tex_term(a, 'x')}{tex_signed(b)}"
            text = f"If x = {x}, what is the value of {tex(expr_body)}?"
            distractors = unique_int_distractors(correct, rnd, spread=7)
            qs.append(build_mcq(qid, "algebra", 2, text, correct, distractors))
        else:  # simplify_like_terms
            a = rnd.randint(2, 9)
            b = rnd.randint(2, 9)
            c = rnd.randint(1, 9)
            correct_sum = a + b
            correct = tex(f"{tex_term(correct_sum, 'x')}+{c}")
            simplify_body = f"{tex_term(a, 'x')}+{tex_term(b, 'x')}+{c}"
            text = f"Simplify: {tex(simplify_body)}"
            wrong_sums = unique_int_distractors(correct_sum, rnd, spread=4, min_val=1, count=3)
            distractors = [tex(f"{tex_term(ws, 'x')}+{c}") for ws in wrong_sums]
            qs.append(build_mcq(qid, "algebra", 2, text, correct, distractors, fmt=str))
        qid += 1
    return qs


def gen_functions_c2(qid_start):
    """Pre-algebra intro: input/output tables and evaluating simple
    linear expressions as a function machine (no formal notation)."""
    qs = []
    qid = qid_start
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(3000 + i)
        a = rnd.randint(2, 6)
        b = rnd.randint(0, 10)
        x = rnd.randint(1, 12)
        correct = a * x + b
        text = (
            f"A function machine multiplies the input by {a} and then adds {b}. "
            f"What is the output when the input is {x}?"
        )
        distractors = unique_int_distractors(correct, rnd, spread=8)
        qs.append(build_mcq(qid, "functions", 2, text, correct, distractors))
        qid += 1
    return qs


def gen_statistics_c2(qid_start):
    qs = []
    qid = qid_start
    templates = ["mean", "median", "range", "probability"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(4000 + i)
        kind = templates[i % len(templates)]
        if kind == "mean":
            vals = [rnd.randint(2, 20) for _ in range(5)]
            correct = sum(vals) / len(vals)
            correct = round(correct, 1) if correct != int(correct) else int(correct)
            text = f"Find the mean of: {', '.join(map(str, vals))}"
            distractors = unique_int_distractors(int(round(correct)), rnd, spread=4) if isinstance(correct, int) else [round(correct + d, 1) for d in [-2, 1, 3]]
            diagram = diagrams.bar_chart(vals)
            qs.append(build_mcq(qid, "statistics", 2, text, correct, distractors, diagram=diagram))
        elif kind == "median":
            vals = sorted(rnd.sample(range(1, 40), 5))
            correct = vals[2]
            text = f"Find the median of: {', '.join(map(str, vals))}"
            distractors = unique_int_distractors(correct, rnd, spread=6, min_val=0)
            diagram = diagrams.bar_chart(vals, highlight_idx=2)
            qs.append(build_mcq(qid, "statistics", 2, text, correct, distractors, diagram=diagram))
        elif kind == "range":
            vals = [rnd.randint(1, 50) for _ in range(6)]
            correct = max(vals) - min(vals)
            text = f"Find the range of: {', '.join(map(str, vals))}"
            distractors = unique_int_distractors(correct, rnd, spread=5, min_val=0)
            diagram = diagrams.bar_chart(vals)
            qs.append(build_mcq(qid, "statistics", 2, text, correct, distractors, diagram=diagram))
        else:  # probability
            total = rnd.choice([6, 8, 10, 12])
            favorable = rnd.randint(1, total - 1)
            correct = Fraction(favorable, total)
            text = f"A bag has {total} equally likely balls, {favorable} of which are red. What is the probability of picking a red ball?"
            distractors = unique_frac_distractors(correct, rnd)
            diagram = diagrams.probability_pie(favorable, total)
            qs.append(build_mcq(qid, "statistics", 2, text, correct, distractors, tex_frac_fmt, diagram=diagram))
        qid += 1
    return qs


def gen_geometry_c2(qid_start):
    qs = []
    qid = qid_start
    templates = ["rect_area", "rect_perimeter", "triangle_area", "angle_sum", "cube_volume"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(5000 + i)
        kind = templates[i % len(templates)]
        if kind == "rect_area":
            l, w = rnd.randint(3, 15), rnd.randint(2, 12)
            correct = l * w
            text = f"A rectangle has length {l} cm and width {w} cm. What is its area?"
            distractors = unique_int_distractors(correct, rnd, spread=max(6, correct // 5), min_val=1)
            diagram = diagrams.rectangle_diagram(l, w)
            qs.append(build_mcq(qid, "geometry", 2, text, correct, distractors, lambda v: f"{v} cm²", diagram=diagram))
        elif kind == "rect_perimeter":
            l, w = rnd.randint(3, 20), rnd.randint(2, 15)
            correct = 2 * (l + w)
            text = f"A rectangle has length {l} cm and width {w} cm. What is its perimeter?"
            distractors = unique_int_distractors(correct, rnd, spread=8, min_val=1)
            diagram = diagrams.rectangle_diagram(l, w)
            qs.append(build_mcq(qid, "geometry", 2, text, correct, distractors, lambda v: f"{v} cm", diagram=diagram))
        elif kind == "triangle_area":
            b, h = rnd.choice([4, 6, 8, 10, 12]), rnd.choice([3, 5, 7, 9, 11])
            correct = Fraction(b * h, 2)
            text = f"A triangle has base {b} cm and height {h} cm. What is its area?"
            distractors = unique_frac_distractors(correct, rnd)
            diagram = diagrams.triangle_base_height(b, h)
            qs.append(build_mcq(qid, "geometry", 2, text, correct, distractors, lambda v: f"{tex_frac(v)} cm²", diagram=diagram))
        elif kind == "angle_sum":
            a1 = rnd.randint(30, 100)
            a2 = rnd.randint(30, 100)
            correct = 180 - a1 - a2
            text = f"In a triangle, two of the angles measure {a1}° and {a2}°. What is the third angle?"
            distractors = unique_int_distractors(correct, rnd, spread=10, min_val=1)
            diagram = diagrams.triangle_with_angles(a1, a2)
            qs.append(build_mcq(qid, "geometry", 2, text, correct, distractors, lambda v: f"{v}°", diagram=diagram))
        else:  # cube_volume
            s = rnd.randint(2, 9)
            correct = s ** 3
            text = f"A cube has a side length of {s} cm. What is its volume?"
            distractors = unique_int_distractors(correct, rnd, spread=max(10, correct // 4), min_val=1)
            qs.append(build_mcq(qid, "geometry", 2, text, correct, distractors, lambda v: f"{v} cm³"))
        qid += 1
    return qs


def gen_calculus_c2(qid_start):
    """Foundational rate-of-change content (no derivatives) appropriate up
    to grade 8: average rate of change from a table, and identifying
    increasing/decreasing trends."""
    qs = []
    qid = qid_start
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(6000 + i)
        x1 = rnd.randint(0, 5)
        x2 = x1 + rnd.randint(1, 4)
        rate = rnd.choice([-3, -2, 2, 3, 4, 5])
        b = rnd.randint(0, 10)
        y1 = rate * x1 + b
        y2 = rate * x2 + b
        correct = Fraction(y2 - y1, x2 - x1)
        text = (
            f"A quantity measures {y1} units at time {x1}s and {y2} units at time {x2}s. "
            f"What is the average rate of change per second?"
        )
        distractors = unique_frac_distractors(correct, rnd)
        diagram = diagrams.function_graph(rate, b, mark_x=x2)
        qs.append(build_mcq(qid, "calculus", 2, text, correct, distractors, lambda v: f"{tex_frac(v)} units/s", diagram=diagram))
        qid += 1
    return qs


# --------------------------------------------------------------------------
# Cycle 3 (grades 9-12) generators
# --------------------------------------------------------------------------

def gen_numbers_c3(qid_start):
    qs = []
    qid = qid_start
    templates = ["exponent", "sci_notation", "radical", "abs_value"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(7000 + i)
        kind = templates[i % len(templates)]
        if kind == "exponent":
            base = rnd.randint(2, 5)
            e1 = rnd.randint(2, 4)
            e2 = rnd.randint(1, 3)
            correct = base ** (e1 + e2)
            exp_body = f"{base}^{{{e1}}}" + "\\times" + f"{base}^{{{e2}}}"
            text = f"Simplify: {tex(exp_body)}"
            distractors = unique_int_distractors(correct, rnd, spread=max(10, correct // 3), min_val=1)
            qs.append(build_mcq(qid, "numbers", 3, text, correct, distractors))
        elif kind == "sci_notation":
            mant = round(rnd.uniform(1.1, 9.9), 1)
            exp = rnd.randint(-4, 6)
            correct = tex(f"{mant}\\times10^{{{exp}}}")
            wrong_exp = [exp + 1, exp - 1, exp + 2]
            distractors = [tex(f"{mant}\\times10^{{{e}}}") for e in wrong_exp]
            value_str = f"{mant * (10 ** exp):.10g}"
            text = f"Write {value_str} in scientific notation."
            qs.append(build_mcq(qid, "numbers", 3, text, correct, distractors, fmt=str))
        elif kind == "radical":
            n = rnd.choice([4, 9, 16, 25, 36, 49, 64, 81, 100, 121, 144, 169])
            correct = int(n ** 0.5)
            sqrt_body = "\\sqrt{" + f"{n}" + "}"
            text = f"Simplify: {tex(sqrt_body)}"
            distractors = unique_int_distractors(correct, rnd, spread=4, min_val=1)
            qs.append(build_mcq(qid, "numbers", 3, text, correct, distractors))
        else:  # abs_value
            a = rnd.randint(-25, -1)
            b = rnd.randint(1, 15)
            correct = abs(a) - b
            text = f"Evaluate: {tex(f'|{a}|-{b}')}"
            distractors = unique_int_distractors(correct, rnd, spread=8)
            qs.append(build_mcq(qid, "numbers", 3, text, correct, distractors))
        qid += 1
    return qs


def gen_algebra_c3(qid_start):
    qs = []
    qid = qid_start
    templates = ["quadratic_factor", "system_linear", "exponent_law", "polynomial_expand"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(8000 + i)
        kind = templates[i % len(templates)]
        if kind == "quadratic_factor":
            r1, r2 = rnd.randint(-8, 8), rnd.randint(-8, 8)
            while r1 == r2:
                r2 = rnd.randint(-8, 8)
            b = -(r1 + r2)
            c = r1 * r2
            quad_body = f"x^2{tex_signed(b, 'x')}{tex_signed(c)}=0"
            text = f"Solve for x: {tex(quad_body)} (give the larger root)"
            correct = max(r1, r2)
            distractors = unique_int_distractors(correct, rnd, spread=6)
            qs.append(build_mcq(qid, "algebra", 3, text, correct, distractors))
        elif kind == "system_linear":
            x = rnd.randint(-6, 8)
            y = rnd.randint(-6, 8)
            a1, b1 = rnd.randint(1, 5), rnd.randint(1, 5)
            a2, b2 = rnd.randint(1, 5), -rnd.randint(1, 5)
            c1 = a1 * x + b1 * y
            c2 = a2 * x + b2 * y
            eq1 = f"{tex_term(a1, 'x')}{tex_signed(b1, 'y')}={c1}"
            eq2 = f"{tex_term(a2, 'x')}{tex_signed(b2, 'y')}={c2}"
            text = f"Solve the system for x: {tex(eq1)}, {tex(eq2)}"
            correct = x
            distractors = unique_int_distractors(correct, rnd, spread=6)
            qs.append(build_mcq(qid, "algebra", 3, text, correct, distractors))
        elif kind == "exponent_law":
            base = rnd.randint(2, 5)
            e1 = rnd.randint(3, 7)
            e2 = rnd.randint(1, e1 - 1)
            correct = base ** (e1 - e2)
            text = f"Simplify: {tex(f'{base}^{{{e1}}}/{base}^{{{e2}}}')}"
            distractors = unique_int_distractors(correct, rnd, spread=max(8, correct // 3), min_val=1)
            qs.append(build_mcq(qid, "algebra", 3, text, correct, distractors))
        else:  # polynomial_expand
            a, b = rnd.randint(1, 6), rnd.randint(1, 9)
            c, d = rnd.randint(1, 6), rnd.randint(1, 9)
            const = b * d
            expand_body = f"({tex_term(a, 'x')}+{b})({tex_term(c, 'x')}+{d})"
            text = f"Expand and simplify: {tex(expand_body)} -- what is the constant term?"
            correct = const
            distractors = unique_int_distractors(correct, rnd, spread=max(8, const // 3), min_val=0)
            qs.append(build_mcq(qid, "algebra", 3, text, correct, distractors))
        qid += 1
    return qs


def gen_functions_c3(qid_start):
    qs = []
    qid = qid_start
    templates = ["evaluate_quad", "domain", "composition", "linear_intercept"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(9000 + i)
        kind = templates[i % len(templates)]
        if kind == "evaluate_quad":
            a = rnd.randint(1, 4)
            b = rnd.randint(-5, 5)
            c = rnd.randint(-5, 5)
            x = rnd.randint(-4, 5)
            correct = a * x ** 2 + b * x + c
            fx_body = f"f(x)={tex_term(a, 'x^2')}{tex_signed(b, 'x')}{tex_signed(c)}"
            text = f"If {tex(fx_body)}, find f({x})."
            distractors = unique_int_distractors(correct, rnd, spread=max(8, abs(correct) // 3 + 4))
            diagram = diagrams.function_graph(a, b, c=c, mark_x=x, quadratic=True)
            qs.append(build_mcq(qid, "functions", 3, text, correct, distractors, diagram=diagram))
        elif kind == "domain":
            k = rnd.randint(2, 12)
            correct = k
            text = f"What value must x NOT equal for {tex(f'f(x)=1/(x-{k})')} to be defined?"
            distractors = unique_int_distractors(correct, rnd, spread=5)
            qs.append(build_mcq(qid, "functions", 3, text, correct, distractors))
        elif kind == "composition":
            a = rnd.randint(2, 5)
            b = rnd.randint(1, 6)
            c = rnd.randint(1, 5)
            x = rnd.randint(1, 6)
            correct = a * (c * x) + b
            f_body = f"f(x)={tex_term(a, 'x')}{tex_signed(b)}"
            g_body = f"g(x)={tex_term(c, 'x')}"
            text = f"If {tex(f_body)} and {tex(g_body)}, find f(g({x}))."
            distractors = unique_int_distractors(correct, rnd, spread=max(8, correct // 4))
            qs.append(build_mcq(qid, "functions", 3, text, correct, distractors))
        else:  # linear_intercept
            m = rnd.randint(-6, 6)
            while m == 0:
                m = rnd.randint(-6, 6)
            b = rnd.randint(-10, 10)
            correct = Fraction(-b, m)
            lin_body = f"f(x)={tex_term(m, 'x')}{tex_signed(b)}"
            text = f"For {tex(lin_body)}, find the x-intercept (the value of x when f(x) = 0)."
            distractors = unique_frac_distractors(correct, rnd)
            diagram = diagrams.function_graph(m, b)
            qs.append(build_mcq(qid, "functions", 3, text, correct, distractors, tex_frac_fmt, diagram=diagram))
        qid += 1
    return qs


def gen_statistics_c3(qid_start):
    qs = []
    qid = qid_start
    templates = ["combined_prob", "combinations", "std_range", "expected_value"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(10000 + i)
        kind = templates[i % len(templates)]
        if kind == "combined_prob":
            p1_num, p1_den = rnd.randint(1, 4), rnd.randint(5, 8)
            p2_num, p2_den = rnd.randint(1, 4), rnd.randint(5, 8)
            correct = Fraction(p1_num, p1_den) * Fraction(p2_num, p2_den)
            text = (
                f"Two independent events A and B have probabilities "
                f"{tex(frac_body(Fraction(p1_num, p1_den)))} and {tex(frac_body(Fraction(p2_num, p2_den)))}. "
                f"What is P(A and B)?"
            )
            distractors = unique_frac_distractors(correct, rnd)
            qs.append(build_mcq(qid, "statistics", 3, text, correct, distractors, tex_frac_fmt))
        elif kind == "combinations":
            n = rnd.randint(4, 8)
            r = rnd.randint(2, n - 1)
            correct = comb(n, r)
            binom_body = "\\binom{" + f"{n}" + "}{" + f"{r}" + "}"
            text = f"In how many ways can you choose {r} items from a group of {n} items (order doesn't matter)? {tex(binom_body)}"
            distractors = unique_int_distractors(correct, rnd, spread=max(10, correct // 4), min_val=1)
            qs.append(build_mcq(qid, "statistics", 3, text, correct, distractors))
        elif kind == "std_range":
            vals = sorted(rnd.sample(range(10, 60), 5))
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            correct = round(variance, 1)
            text = f"Find the variance of the data set: {', '.join(map(str, vals))} (round to 1 decimal place)"
            distractors = [round(correct + d, 1) for d in [-4.5, 3.2, 7.1]]
            distractors = list({d for d in distractors if d != correct and d > 0}) or [round(correct + 1, 1)]
            while len(distractors) < 3:
                distractors.append(round(correct + len(distractors) + 2, 1))
            diagram = diagrams.bar_chart(vals)
            qs.append(build_mcq(qid, "statistics", 3, text, correct, distractors[:3], diagram=diagram))
        else:  # expected_value
            outcomes = [(rnd.randint(-10, 20), rnd.randint(1, 5)) for _ in range(3)]
            total_w = sum(w for _, w in outcomes)
            correct = round(sum(v * w for v, w in outcomes) / total_w, 2)
            desc = ", ".join(f"{v} (weight {w})" for v, w in outcomes)
            text = f"A random variable takes values {desc} out of a total weight of {total_w}. Find its expected value (round to 2 dp)."
            distractors = [round(correct + d, 2) for d in [-3.5, 2.25, 5.1]]
            qs.append(build_mcq(qid, "statistics", 3, text, correct, distractors))
        qid += 1
    return qs


def gen_geometry_c3(qid_start):
    qs = []
    qid = qid_start
    templates = ["distance", "slope", "trig_ratio", "cylinder_volume", "similarity"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(11000 + i)
        kind = templates[i % len(templates)]
        if kind == "distance":
            x1, y1 = rnd.randint(-5, 5), rnd.randint(-5, 5)
            dx, dy = rnd.choice([3, 4, 6, 8]), rnd.choice([4, 3, 8, 6])
            x2, y2 = x1 + dx, y1 + dy
            correct = int((dx ** 2 + dy ** 2) ** 0.5)
            text = f"Find the distance between points {tex(f'({x1},{y1})')} and {tex(f'({x2},{y2})')}."
            distractors = unique_int_distractors(correct, rnd, spread=4, min_val=1)
            diagram = diagrams.coordinate_points_diagram((x1, y1), (x2, y2))
            qs.append(build_mcq(qid, "geometry", 3, text, correct, distractors, diagram=diagram))
        elif kind == "slope":
            x1, y1 = rnd.randint(-6, 6), rnd.randint(-6, 6)
            x2 = x1 + rnd.randint(1, 8)
            m = rnd.choice([-3, -2, -1, 2, 3, 4])
            y2 = y1 + m * (x2 - x1)
            correct = m
            text = f"Find the slope of the line through {tex(f'({x1},{y1})')} and {tex(f'({x2},{y2})')}."
            distractors = unique_int_distractors(correct, rnd, spread=4)
            diagram = diagrams.coordinate_points_diagram((x1, y1), (x2, y2))
            qs.append(build_mcq(qid, "geometry", 3, text, correct, distractors, diagram=diagram))
        elif kind == "trig_ratio":
            opp, hyp = rnd.choice([(3, 5), (4, 5), (6, 10), (8, 10), (5, 13), (12, 13)])
            correct = Fraction(opp, hyp)
            ratio_name = rnd.choice(["sine", "cosine"])
            adj = int((hyp ** 2 - opp ** 2) ** 0.5)
            if ratio_name == "cosine":
                correct = Fraction(adj, hyp)
            text = f"In the right triangle shown, find the {ratio_name} of the marked angle."
            distractors = unique_frac_distractors(correct, rnd)
            diagram = diagrams.right_triangle_diagram(opp, adj, hyp)
            qs.append(build_mcq(qid, "geometry", 3, text, correct, distractors, tex_frac_fmt, diagram=diagram))
        elif kind == "cylinder_volume":
            r = rnd.randint(2, 8)
            h = rnd.randint(3, 15)
            correct = round(3.14159 * r * r * h)
            text = f"A cylinder has radius {r} cm and height {h} cm. Find its volume (use π = 3.14, round to the nearest whole number)."
            distractors = unique_int_distractors(correct, rnd, spread=max(15, correct // 6), min_val=1)
            diagram = diagrams.cylinder_diagram(r, h)
            qs.append(build_mcq(qid, "geometry", 3, text, correct, distractors, lambda v: f"{v} cm³", diagram=diagram))
        else:  # similarity
            scale = rnd.choice([Fraction(1, 2), Fraction(2, 3), Fraction(3, 4), Fraction(5, 2)])
            side = rnd.randint(4, 20)
            correct = side * scale
            text = f"Two similar triangles have a scale factor of {tex_frac(scale)}. If a side of the smaller triangle is {side} cm, find the corresponding side of the larger triangle."
            distractors = unique_frac_distractors(correct, rnd)
            diagram = diagrams.similar_triangles_diagram(side, correct if correct.denominator == 1 else side * 2)
            qs.append(build_mcq(qid, "geometry", 3, text, correct, distractors, lambda v: f"{tex_frac(v)} cm", diagram=diagram))
        qid += 1
    return qs


def gen_calculus_c3(qid_start):
    qs = []
    qid = qid_start
    templates = ["derivative_power", "derivative_at_point", "simple_limit", "power_rule_integral"]
    for i in range(QUESTIONS_PER_POOL):
        rnd = random.Random(12000 + i)
        kind = templates[i % len(templates)]
        if kind == "derivative_power":
            a = rnd.randint(2, 6)
            n = rnd.randint(2, 5)
            b = rnd.randint(1, 8)
            correct_coef = a * n
            new_pow = n - 1
            deriv_body = f"f(x)={a}x^{{{n}}}{tex_signed(b, 'x')}"
            text = f"Find the derivative of {tex(deriv_body)} with respect to x."
            correct_body = f"{tex_term(correct_coef, 'x')}" if new_pow == 1 else f"{tex_term(correct_coef, f'x^{{{new_pow}}}')}"
            correct = tex(f"{correct_body}+{b}")
            distractors = [
                tex(f"{tex_term(a, f'x^{{{n-1}}}')}+{b}"),
                tex(f"{tex_term(correct_coef, f'x^{{{n}}}')}+{b}"),
                tex(f"{tex_term(correct_coef * n, f'x^{{{new_pow}}}')}+{b}"),
            ]
            qs.append(build_mcq(qid, "calculus", 3, text, correct, distractors, fmt=str))
        elif kind == "derivative_at_point":
            a = rnd.randint(1, 5)
            b = rnd.randint(-6, 6)
            x0 = rnd.randint(-3, 4)
            correct = 2 * a * x0 + b
            fx2_body = f"f(x)={tex_term(a, 'x^2')}{tex_signed(b, 'x')}"
            text = f"If {tex(fx2_body)}, find f'({x0})."
            distractors = unique_int_distractors(correct, rnd, spread=max(6, abs(correct) // 2 + 3))
            diagram = diagrams.function_graph(a, b, mark_x=x0, quadratic=True)
            qs.append(build_mcq(qid, "calculus", 3, text, correct, distractors, diagram=diagram))
        elif kind == "simple_limit":
            a = rnd.randint(2, 6)
            x0 = rnd.randint(1, 5)
            b = rnd.randint(1, 10)
            correct = a * x0 + b
            limit_body = "\\lim_{x\\to" + str(x0) + "}(" + tex_term(a, "x") + tex_signed(b) + ")"
            text = f"Evaluate the limit: {tex(limit_body)}"
            distractors = unique_int_distractors(correct, rnd, spread=6)
            diagram = diagrams.function_graph(a, b, mark_x=x0)
            qs.append(build_mcq(qid, "calculus", 3, text, correct, distractors, diagram=diagram))
        else:  # power_rule_integral
            a = rnd.randint(2, 8)
            n = rnd.randint(1, 4)
            new_pow = n + 1
            coef = Fraction(a, new_pow)
            text = f"Find the indefinite integral of {tex(f'f(x)={a}x^{{{n}}}')} with respect to x (ignore the constant of integration)."
            correct = tex(f"{frac_body(coef)}x^{{{new_pow}}}")
            distractors = [
                tex(f"{a}x^{{{new_pow}}}"),
                tex(f"{frac_body(coef)}x^{{{n}}}"),
                tex(f"{frac_body(Fraction(a, n))}x^{{{new_pow}}}"),
            ]
            qs.append(build_mcq(qid, "calculus", 3, text, correct, distractors, fmt=str))
        qid += 1
    return qs


GENERATORS = [
    ("numbers", 2, gen_numbers_c2),
    ("algebra", 2, gen_algebra_c2),
    ("functions", 2, gen_functions_c2),
    ("statistics", 2, gen_statistics_c2),
    ("geometry", 2, gen_geometry_c2),
    ("calculus", 2, gen_calculus_c2),
    ("numbers", 3, gen_numbers_c3),
    ("algebra", 3, gen_algebra_c3),
    ("functions", 3, gen_functions_c3),
    ("statistics", 3, gen_statistics_c3),
    ("geometry", 3, gen_geometry_c3),
    ("calculus", 3, gen_calculus_c3),
]


def build_bank():
    bank = []
    qid = 1
    for area, cycle, fn in GENERATORS:
        questions = fn(qid)
        assert len(questions) == QUESTIONS_PER_POOL, f"{area} c{cycle} produced {len(questions)}"
        bank.extend(questions)
        qid += QUESTIONS_PER_POOL
    return bank


def main():
    bank = build_bank()
    out_path = os.path.join(os.path.dirname(__file__), "data", "question_bank.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(bank)} questions to {out_path}")


if __name__ == "__main__":
    main()
