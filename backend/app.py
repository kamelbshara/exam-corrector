"""
Exam Generator + Exam Corrector web app. No authentication -- intended to
run on a school's internal network / a teacher's own server.
"""
import io
import os

from flask import Flask, jsonify, request, send_file, render_template
from flask_cors import CORS

from curriculum import GRADES, AREA_LABELS, MAX_QUESTIONS_PER_EXAM, grades_for_cycle
import exam_generator
from exam_pdf import render_exam_pdf
from omr_corrector import grade_exam, CorrectionError
import results_store
import roster_store
import report

app = Flask(__name__)
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32MB, generous for a few scanned pages

APK_DOWNLOAD_URL = os.environ.get(
    "APK_DOWNLOAD_URL",
    "https://github.com/kamelbshara/exam-corrector/releases/latest/download/exam-corrector.apk",
)


# ---------------------------------------------------------------- pages ----
@app.route("/")
def index():
    return render_template("index.html", apk_url=APK_DOWNLOAD_URL)


@app.route("/corrector")
def corrector_page():
    return render_template("corrector.html", apk_url=APK_DOWNLOAD_URL)


@app.route("/privacy")
def privacy_page():
    return render_template("privacy.html", apk_url=APK_DOWNLOAD_URL)


@app.route("/terms")
def terms_page():
    return render_template("terms.html", apk_url=APK_DOWNLOAD_URL)


# ------------------------------------------------------------------ API ----
@app.route("/api/grades", methods=["GET"])
def api_grades():
    out = []
    for grade, (cycle, track, weights) in GRADES.items():
        out.append(
            {
                "grade": grade,
                "cycle": cycle,
                "track": track,
                "areas": {AREA_LABELS[a]: w for a, w in weights.items()},
            }
        )
    out.sort(key=lambda g: (g["cycle"], g["grade"]))
    return jsonify({"grades": out, "max_questions": MAX_QUESTIONS_PER_EXAM})


@app.route("/api/generate-exam", methods=["POST"])
def api_generate_exam():
    data = request.get_json(force=True, silent=True) or {}
    school_name = data.get("school_name", "")
    grade = data.get("grade", "")
    try:
        num_questions = int(data.get("num_questions", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "num_questions must be an integer"}), 400

    try:
        exam = exam_generator.generate_exam(school_name, grade, num_questions)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(
        {
            "exam_id": exam["exam_id"],
            "school_name": exam["school_name"],
            "grade": exam["grade"],
            "cycle": exam["cycle"],
            "track": exam["track"],
            "num_questions": exam["num_questions"],
            "num_pages": exam["num_pages"],
            "total_marks": exam.get("total_marks", exam["num_questions"]),
            "area_breakdown": {AREA_LABELS[a]: c for a, c in exam["area_breakdown"].items()},
            "created_at": exam["created_at"],
            "teacher_pdf_url": f"/api/exams/{exam['exam_id']}/pdf/teacher",
            "student_pdf_url": f"/api/exams/{exam['exam_id']}/pdf/student",
        }
    )


@app.route("/api/exams", methods=["GET"])
def api_list_exams():
    return jsonify({"exams": exam_generator.list_exams()})


@app.route("/api/exams/<exam_id>", methods=["GET"])
def api_get_exam(exam_id):
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    return jsonify(
        {
            "exam_id": exam["exam_id"],
            "school_name": exam["school_name"],
            "grade": exam["grade"],
            "num_questions": exam["num_questions"],
            "num_pages": exam["num_pages"],
            "created_at": exam["created_at"],
        }
    )


@app.route("/api/exams/<exam_id>/questions", methods=["GET"])
def api_exam_questions(exam_id):
    """Full question list (text, options, marks, diagram, correct answer)
    for the web preview. Not linked from anywhere public -- same exposure
    level as the teacher PDF, which already includes the answer key."""
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    return jsonify(
        {
            "exam_id": exam["exam_id"],
            "school_name": exam["school_name"],
            "grade": exam["grade"],
            "track": exam["track"],
            "num_questions": exam["num_questions"],
            "total_marks": exam.get("total_marks", exam["num_questions"]),
            "questions": exam["questions"],
        }
    )


@app.route("/api/exams/<exam_id>/pdf/<flavor>", methods=["GET"])
def api_exam_pdf(exam_id, flavor):
    if flavor not in ("teacher", "student"):
        return jsonify({"error": "flavor must be 'teacher' or 'student'"}), 400
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    pdf_bytes, _layout = render_exam_pdf(exam, flavor)
    filename = f"{exam['school_name']}_{exam['grade']}_{flavor}_{exam_id}.pdf".replace(" ", "_")
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=filename,
    )


@app.route("/api/exams/<exam_id>/correct", methods=["POST"])
def api_correct(exam_id):
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404

    student_name = request.form.get("student_name", "")
    student_id = request.form.get("student_id") or None

    page_images = {}
    for key, file in request.files.items():
        if not key.startswith("page_"):
            continue
        try:
            page_num = int(key.split("_", 1)[1])
        except ValueError:
            continue
        page_images[page_num] = file.read()

    if not page_images:
        return jsonify({"error": "No page images uploaded. Use form fields named page_1, page_2, ..."}), 400

    try:
        result = grade_exam(exam, page_images)
    except CorrectionError as e:
        return jsonify({"error": str(e)}), 422

    record = results_store.save_result(exam_id, student_name, result, student_id=student_id)
    return jsonify(record)


@app.route("/api/exams/<exam_id>/results", methods=["GET"])
def api_list_results(exam_id):
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    return jsonify({"results": results_store.list_results(exam_id)})


@app.route("/api/exams/<exam_id>/results/<result_id>", methods=["DELETE"])
def api_delete_result(exam_id, result_id):
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    ok = results_store.delete_result(exam_id, result_id)
    if not ok:
        return jsonify({"error": "Result not found"}), 404
    return jsonify({"deleted": True, "result_id": result_id})


@app.route("/api/exams/<exam_id>/students", methods=["POST"])
def api_upload_roster(exam_id):
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        return jsonify({"error": "Please upload an .xlsx file (column 1: name, column 2: class - optional)"}), 400
    try:
        students = roster_store.parse_roster_file(file.stream)
    except Exception as e:
        return jsonify({"error": f"Could not read the Excel file: {e}"}), 400
    if not students:
        return jsonify({"error": "No student names found in the file"}), 400
    roster_store.save_roster(exam_id, students)
    return jsonify({"students": students, "count": len(students)})


@app.route("/api/exams/<exam_id>/students", methods=["GET"])
def api_get_roster(exam_id):
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    students = roster_store.load_roster(exam_id)
    results = results_store.list_results(exam_id)
    latest_by_student = {}
    for rec in results:
        sid = rec.get("student_id")
        if sid and sid not in latest_by_student:
            latest_by_student[sid] = rec
    out = []
    for s in students:
        rec = latest_by_student.get(s["student_id"])
        out.append(
            {
                **s,
                "graded": rec is not None,
                "result_id": rec["result_id"] if rec else None,
                "percentage": rec["result"]["percentage"] if rec else None,
                "level": rec["result"]["level"] if rec else None,
            }
        )
    return jsonify({"students": out})


@app.route("/api/exams/<exam_id>/students", methods=["DELETE"])
def api_delete_roster(exam_id):
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    roster_store.delete_roster(exam_id)
    return jsonify({"deleted": True})


@app.route("/api/exams/<exam_id>/results/export", methods=["GET"])
def api_export_results(exam_id):
    exam = exam_generator.load_exam(exam_id)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    records = results_store.list_results(exam_id)
    if not records:
        return jsonify({"error": "No corrected sheets yet for this exam"}), 400
    xlsx_bytes = report.build_report(exam, records)
    filename = f"Report_{exam['school_name']}_{exam['grade']}_{exam_id}.xlsx".replace(" ", "_")
    return send_file(
        io.BytesIO(xlsx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
