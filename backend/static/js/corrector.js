const examSelect = document.getElementById("exam_id");
const examHint = document.getElementById("exam-hint");
const uploadSection = document.getElementById("upload-section");
const fileInputs = document.getElementById("file-inputs");
const correctBtn = document.getElementById("correct-btn");
const errorBox = document.getElementById("error-box");
const resultCard = document.getElementById("result-card");
const resultContent = document.getElementById("result-content");
const resultsListCard = document.getElementById("results-list-card");
const resultsListEl = document.getElementById("results-list");
const exportBtn = document.getElementById("export-btn");

let examsData = [];
let currentExam = null;

function getQueryParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

async function loadExams() {
  const res = await fetch("/api/exams");
  const data = await res.json();
  examsData = data.exams;
  examSelect.innerHTML = '<option value="">-- Select an exam --</option>';
  data.exams.forEach((e) => {
    const opt = document.createElement("option");
    opt.value = e.exam_id;
    opt.textContent = `${e.school_name} - ${e.grade} - ${e.num_questions}Q (${e.exam_id})`;
    examSelect.appendChild(opt);
  });

  const preselect = getQueryParam("exam_id");
  if (preselect) {
    examSelect.value = preselect;
    onExamSelected();
  }
}

async function onExamSelected() {
  const examId = examSelect.value;
  errorBox.innerHTML = "";
  resultCard.style.display = "none";
  if (!examId) {
    uploadSection.style.display = "none";
    resultsListCard.style.display = "none";
    return;
  }
  const res = await fetch(`/api/exams/${examId}`);
  if (!res.ok) {
    errorBox.innerHTML = '<div class="alert alert-error">Exam not found.</div>';
    return;
  }
  currentExam = await res.json();
  examHint.textContent = `${currentExam.num_questions} questions across ${currentExam.num_pages} page(s). Upload one photo per page below.`;

  fileInputs.innerHTML = "";
  for (let p = 1; p <= currentExam.num_pages; p++) {
    const wrap = document.createElement("div");
    wrap.innerHTML = `<label for="page_${p}">Page ${p} image</label>
      <input type="file" id="page_${p}" accept="image/*" capture="environment">`;
    fileInputs.appendChild(wrap);
  }
  uploadSection.style.display = "block";
  exportBtn.href = `/api/exams/${examId}/results/export`;
  loadResults(examId);
}

examSelect.addEventListener("change", onExamSelected);

function badgeClass(level) {
  return "badge badge-" + level.toLowerCase().replace(/\s+/g, "-");
}

correctBtn.addEventListener("click", async () => {
  if (!currentExam) return;
  errorBox.innerHTML = "";

  const formData = new FormData();
  formData.append("student_name", document.getElementById("student_name").value);
  let anyFile = false;
  for (let p = 1; p <= currentExam.num_pages; p++) {
    const input = document.getElementById(`page_${p}`);
    if (input && input.files.length > 0) {
      formData.append(`page_${p}`, input.files[0]);
      anyFile = true;
    }
  }
  if (!anyFile) {
    errorBox.innerHTML = '<div class="alert alert-error">Please choose at least one page image.</div>';
    return;
  }

  correctBtn.disabled = true;
  correctBtn.innerHTML = '<span class="spinner"></span> Correcting...';

  try {
    const res = await fetch(`/api/exams/${currentExam.exam_id}/correct`, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      errorBox.innerHTML = `<div class="alert alert-error">${data.error || "Could not correct this sheet."}</div>`;
      return;
    }
    renderResult(data.result, data.student_name);
    loadResults(currentExam.exam_id);
  } catch (e) {
    errorBox.innerHTML = `<div class="alert alert-error">Network error: ${e.message}</div>`;
  } finally {
    correctBtn.disabled = false;
    correctBtn.textContent = "Correct Sheet";
  }
});

function renderResult(result, studentName) {
  const sectionRows = Object.values(result.sections)
    .map((s) => `<tr><td>${s.label}</td><td>${s.correct}/${s.total}</td><td>${s.percentage}%</td></tr>`)
    .join("");

  const questionRows = result.answers
    .map((a) => {
      const status = a.is_correct ? "&#10003;" : (a.selected ? "&#10007;" : "&mdash;");
      const color = a.is_correct ? "color:#065f46" : (a.selected ? "color:#991b1b" : "color:#92400e");
      return `<tr><td>Q${a.number}</td><td>${a.selected || "blank"}</td><td>${a.correct_answer}</td><td style="${color}">${status}</td></tr>`;
    })
    .join("");

  resultContent.innerHTML = `
    <div class="score-box">
      <div class="pct">${result.percentage}%</div>
      <div>${result.correct} / ${result.num_questions} correct</div>
      <div><span class="${badgeClass(result.level)}">${result.level}</span></div>
      ${studentName ? `<div class="muted small">Student: ${studentName}</div>` : ""}
    </div>
    ${result.weak_areas.length ? `<div class="alert alert-info">Weak area(s): ${result.weak_areas.join(", ")}</div>` : ""}
    <h2>By Topic</h2>
    <table><thead><tr><th>Area</th><th>Correct</th><th>%</th></tr></thead><tbody>${sectionRows}</tbody></table>
    <h2 style="margin-top:18px;">Per Question</h2>
    <table><thead><tr><th>Q</th><th>Selected</th><th>Correct</th><th></th></tr></thead><tbody>${questionRows}</tbody></table>
  `;
  resultCard.style.display = "block";
  resultCard.scrollIntoView({ behavior: "smooth" });
}

async function loadResults(examId) {
  const res = await fetch(`/api/exams/${examId}/results`);
  const data = await res.json();
  if (!data.results.length) {
    resultsListCard.style.display = "none";
    return;
  }
  let html = "<table><thead><tr><th>Student</th><th>Score</th><th>Level</th><th>Graded At</th></tr></thead><tbody>";
  data.results.forEach((r) => {
    const res_ = r.result;
    html += `<tr><td>${r.student_name}</td><td>${res_.correct}/${res_.num_questions} (${res_.percentage}%)</td>
      <td><span class="${badgeClass(res_.level)}">${res_.level}</span></td>
      <td class="small muted">${new Date(r.graded_at).toLocaleString()}</td></tr>`;
  });
  html += "</tbody></table>";
  resultsListEl.innerHTML = html;
  resultsListCard.style.display = "block";
}

loadExams();
