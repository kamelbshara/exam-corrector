const gradeSelect = document.getElementById("grade");
const gradeHint = document.getElementById("grade-hint");
const form = document.getElementById("generate-form");
const errorBox = document.getElementById("error-box");
const resultCard = document.getElementById("result-card");
const resultContent = document.getElementById("result-content");
const examListEl = document.getElementById("exam-list");
const generateBtn = document.getElementById("generate-btn");
const previewCard = document.getElementById("preview-card");
const previewContent = document.getElementById("preview-content");
const showAnswersToggle = document.getElementById("show-answers-toggle");

let gradesData = [];

function cycleTrackLabel(g) {
  return `Cycle ${g.cycle} - ${g.track}`;
}

async function loadGrades() {
  const res = await fetch("/api/grades");
  const data = await res.json();
  gradesData = data.grades;
  gradeSelect.innerHTML = "";
  let lastGroup = null;
  data.grades.forEach((g) => {
    const groupLabel = cycleTrackLabel(g);
    if (groupLabel !== lastGroup) {
      lastGroup = groupLabel;
    }
    const opt = document.createElement("option");
    opt.value = g.grade;
    opt.textContent = `${g.grade} (${groupLabel})`;
    gradeSelect.appendChild(opt);
  });
  updateGradeHint();
}

function updateGradeHint() {
  const g = gradesData.find((x) => x.grade === gradeSelect.value);
  if (!g) { gradeHint.textContent = ""; return; }
  const areas = Object.entries(g.areas).map(([label, pct]) => `${label} ${pct}%`).join(", ");
  gradeHint.textContent = `Area weights: ${areas}`;
}

gradeSelect.addEventListener("change", updateGradeHint);

function badgeClass(level) {
  return "badge badge-" + level.toLowerCase().replace(/\s+/g, "-");
}

async function loadExamList() {
  const res = await fetch("/api/exams");
  const data = await res.json();
  if (!data.exams.length) {
    examListEl.innerHTML = '<p class="muted small">No exams generated yet.</p>';
    return;
  }
  let html = "<table><thead><tr><th>School</th><th>Grade</th><th>Questions</th><th>Exam ID</th><th>Created</th><th></th></tr></thead><tbody>";
  data.exams.forEach((e) => {
    const date = new Date(e.created_at).toLocaleString();
    html += `<tr>
      <td>${e.school_name}</td>
      <td>${e.grade}</td>
      <td>${e.num_questions}</td>
      <td><code>${e.exam_id}</code></td>
      <td class="small muted">${date}</td>
      <td>
        <a class="btn btn-outline" style="padding:4px 10px;font-size:0.8rem" href="/api/exams/${e.exam_id}/pdf/teacher" target="_blank">Teacher PDF</a>
        <a class="btn btn-outline" style="padding:4px 10px;font-size:0.8rem" href="/api/exams/${e.exam_id}/pdf/student" target="_blank">Student PDF</a>
        <a class="btn btn-outline" style="padding:4px 10px;font-size:0.8rem" href="/corrector?exam_id=${e.exam_id}">Correct</a>
      </td>
    </tr>`;
  });
  html += "</tbody></table>";
  examListEl.innerHTML = html;
}

function areaBadgeClass(area) {
  return "badge-area badge-area-" + area;
}

async function loadPreview(examId) {
  previewContent.innerHTML = '<p class="muted small"><span class="spinner"></span> Loading preview...</p>';
  previewCard.style.display = "block";
  const res = await fetch(`/api/exams/${examId}/questions`);
  if (!res.ok) {
    previewContent.innerHTML = '<p class="alert alert-error">Could not load preview.</p>';
    return;
  }
  const data = await res.json();
  let html = `<p class="muted small">${data.school_name} - ${data.grade} - ${data.num_questions} questions - ${data.total_marks} marks total</p>`;
  data.questions.forEach((q) => {
    html += `<div class="preview-q" data-correct="${q.correct}">
      <div class="preview-q-header">
        <span class="preview-q-num">Q${q.number}.</span>
        <span class="small muted">${q.area_label} &middot; ${q.marks} mark${q.marks !== 1 ? "s" : ""}</span>
      </div>
      <div class="preview-q-text">${q.text}</div>`;
    if (q.diagram) {
      html += `<img class="preview-diagram" src="data:image/png;base64,${q.diagram}" alt="diagram">`;
    }
    html += '<div class="preview-options">';
    for (const letter of ["A", "B", "C", "D"]) {
      const correctClass = letter === q.correct ? " preview-opt-correct" : "";
      html += `<div class="preview-opt${correctClass}" data-letter="${letter}">${letter}. ${q.options[letter]}</div>`;
    }
    html += "</div></div>";
  });
  previewContent.innerHTML = html;
  applyAnswerVisibility();
  if (window.MathJax && window.MathJax.typesetPromise) {
    window.MathJax.typesetPromise([previewContent]);
  }
}

function applyAnswerVisibility() {
  previewContent.classList.toggle("show-answers", showAnswersToggle.checked);
}

showAnswersToggle.addEventListener("change", applyAnswerVisibility);

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  errorBox.innerHTML = "";
  generateBtn.disabled = true;
  generateBtn.innerHTML = '<span class="spinner"></span> Generating...';

  const payload = {
    school_name: document.getElementById("school_name").value,
    grade: gradeSelect.value,
    num_questions: parseInt(document.getElementById("num_questions").value, 10),
  };

  try {
    const res = await fetch("/api/generate-exam", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      errorBox.innerHTML = `<div class="alert alert-error">${data.error || "Something went wrong."}</div>`;
      return;
    }

    const areaRows = Object.entries(data.area_breakdown)
      .map(([label, count]) => `<tr><td>${label}</td><td>${count} question(s)</td></tr>`)
      .join("");

    resultContent.innerHTML = `
      <div class="alert alert-success">Exam generated for <strong>${data.school_name}</strong> - ${data.grade}</div>
      <p><strong>Exam ID:</strong> <code>${data.exam_id}</code> &middot; ${data.num_questions} questions across ${data.num_pages} page(s) &middot; <strong>${data.total_marks || 100} marks total</strong></p>
      <table><thead><tr><th>Area</th><th>Questions</th></tr></thead><tbody>${areaRows}</tbody></table>
      <div class="btn-row">
        <a class="btn btn-primary" href="${data.teacher_pdf_url}" target="_blank">Download Teacher Copy (with answers)</a>
        <a class="btn btn-accent" href="${data.student_pdf_url}" target="_blank">Download Student Copy (blank)</a>
        <a class="btn btn-outline" href="/corrector?exam_id=${data.exam_id}">Go to Corrector for this Exam</a>
      </div>
      <p class="hint">Keep the Exam ID &mdash; you'll need it (or pick it from the list below) to correct scanned sheets later.</p>
    `;
    resultCard.style.display = "block";
    resultCard.scrollIntoView({ behavior: "smooth" });
    loadExamList();
    loadPreview(data.exam_id);
  } catch (e) {
    errorBox.innerHTML = `<div class="alert alert-error">Network error: ${e.message}</div>`;
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "Generate Exam";
  }
});

loadGrades();
loadExamList();
