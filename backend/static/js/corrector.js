const examSelect = document.getElementById("exam_id");
const examHint = document.getElementById("exam-hint");
const uploadSection = document.getElementById("upload-section");
const fileInputs = document.getElementById("file-inputs");
const correctBtn = document.getElementById("correct-btn");
const clearSelectionBtn = document.getElementById("clear-selection-btn");
const errorBox = document.getElementById("error-box");
const resultCard = document.getElementById("result-card");
const resultContent = document.getElementById("result-content");
const resultsListCard = document.getElementById("results-list-card");
const resultsListEl = document.getElementById("results-list");
const exportBtn = document.getElementById("export-btn");
const studentNameInput = document.getElementById("student_name");
const studentIdField = document.getElementById("student_id_field");
const correctingForHint = document.getElementById("correcting-for-hint");

const rosterCard = document.getElementById("roster-card");
const rosterUploadSection = document.getElementById("roster-upload-section");
const rosterFileInput = document.getElementById("roster-file");
const uploadRosterBtn = document.getElementById("upload-roster-btn");
const rosterListEl = document.getElementById("roster-list");
const rosterActions = document.getElementById("roster-actions");
const replaceRosterBtn = document.getElementById("replace-roster-btn");

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
  clearStudentSelection();
  if (!examId) {
    uploadSection.style.display = "none";
    resultsListCard.style.display = "none";
    rosterCard.style.display = "none";
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
  rosterCard.style.display = "block";
  exportBtn.href = `/api/exams/${examId}/results/export`;
  loadResults(examId);
  loadRoster(examId);
}

examSelect.addEventListener("change", onExamSelected);

function badgeClass(level) {
  return "badge badge-" + level.toLowerCase().replace(/\s+/g, "-");
}

function clearStudentSelection() {
  studentNameInput.value = "";
  studentIdField.value = "";
  correctingForHint.textContent = "";
  clearSelectionBtn.style.display = "none";
}

clearSelectionBtn.addEventListener("click", clearStudentSelection);

function selectStudentForCorrection(student) {
  studentNameInput.value = student.name;
  studentIdField.value = student.student_id;
  correctingForHint.textContent = student.graded
    ? `Re-correcting ${student.name} (previous result will remain until you delete it, or a new one is added alongside it).`
    : `Correcting for ${student.name}${student.class_name ? " (" + student.class_name + ")" : ""}.`;
  clearSelectionBtn.style.display = "inline-block";
  uploadSection.scrollIntoView({ behavior: "smooth" });
}

correctBtn.addEventListener("click", async () => {
  if (!currentExam) return;
  errorBox.innerHTML = "";

  const formData = new FormData();
  formData.append("student_name", studentNameInput.value);
  if (studentIdField.value) {
    formData.append("student_id", studentIdField.value);
  }
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
    loadRoster(currentExam.exam_id);
    clearStudentSelection();
    for (let p = 1; p <= currentExam.num_pages; p++) {
      const input = document.getElementById(`page_${p}`);
      if (input) input.value = "";
    }
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
      return `<tr><td>Q${a.number}</td><td>${a.marks}</td><td>${a.selected || "blank"}</td><td>${a.correct_answer}</td><td style="${color}">${status}</td></tr>`;
    })
    .join("");

  const totalMarks = result.total_marks || result.num_questions;
  const marksEarned = result.marks_earned !== undefined ? result.marks_earned : result.correct;

  resultContent.innerHTML = `
    <div class="score-box">
      <div class="pct">${marksEarned} / ${totalMarks}</div>
      <div>${result.percentage}% &middot; ${result.correct} / ${result.num_questions} questions correct</div>
      <div><span class="${badgeClass(result.level)}">${result.level}</span></div>
      ${studentName ? `<div class="muted small">Student: ${studentName}</div>` : ""}
    </div>
    ${result.weak_areas.length ? `<div class="alert alert-info">Weak area(s): ${result.weak_areas.join(", ")}</div>` : ""}
    <h2>By Topic</h2>
    <table><thead><tr><th>Area</th><th>Correct</th><th>%</th></tr></thead><tbody>${sectionRows}</tbody></table>
    <h2 style="margin-top:18px;">Per Question</h2>
    <table><thead><tr><th>Q</th><th>Marks</th><th>Selected</th><th>Correct</th><th></th></tr></thead><tbody>${questionRows}</tbody></table>
  `;
  resultCard.style.display = "block";
  resultCard.scrollIntoView({ behavior: "smooth" });
}

async function deleteResult(examId, resultId, label) {
  if (!confirm(`Delete the graded sheet for "${label}"? You can correct it again afterwards.`)) return;
  const res = await fetch(`/api/exams/${examId}/results/${resultId}`, { method: "DELETE" });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    errorBox.innerHTML = `<div class="alert alert-error">${data.error || "Could not delete this result."}</div>`;
    return;
  }
  loadResults(examId);
  loadRoster(examId);
}

async function loadResults(examId) {
  const res = await fetch(`/api/exams/${examId}/results`);
  const data = await res.json();
  if (!data.results.length) {
    resultsListCard.style.display = "none";
    return;
  }
  let html = "<table><thead><tr><th>Student</th><th>Score</th><th>Level</th><th>Graded At</th><th></th></tr></thead><tbody>";
  data.results.forEach((r) => {
    const res_ = r.result;
    const marksEarned = res_.marks_earned !== undefined ? res_.marks_earned : res_.correct;
    const totalMarks = res_.total_marks || res_.num_questions;
    html += `<tr><td>${r.student_name}</td><td>${marksEarned}/${totalMarks} (${res_.percentage}%)</td>
      <td><span class="${badgeClass(res_.level)}">${res_.level}</span></td>
      <td class="small muted">${new Date(r.graded_at).toLocaleString()}</td>
      <td><button class="btn btn-outline btn-delete" data-exam="${examId}" data-result="${r.result_id}" data-label="${r.student_name}" style="padding:4px 10px;font-size:0.78rem;color:#991b1b;border-color:#991b1b;">Delete</button></td></tr>`;
  });
  html += "</tbody></table>";
  resultsListEl.innerHTML = html;
  resultsListEl.querySelectorAll(".btn-delete").forEach((btn) => {
    btn.addEventListener("click", () => deleteResult(btn.dataset.exam, btn.dataset.result, btn.dataset.label));
  });
  resultsListCard.style.display = "block";
}

async function loadRoster(examId) {
  const res = await fetch(`/api/exams/${examId}/students`);
  if (!res.ok) return;
  const data = await res.json();
  if (!data.students.length) {
    rosterListEl.innerHTML = "";
    rosterUploadSection.style.display = "block";
    rosterActions.style.display = "none";
    return;
  }
  rosterUploadSection.style.display = "none";
  rosterActions.style.display = "flex";

  const gradedCount = data.students.filter((s) => s.graded).length;
  let html = `<p class="muted small">${gradedCount} / ${data.students.length} graded</p>`;
  html += "<table><thead><tr><th>Name</th><th>Class</th><th>Status</th><th></th></tr></thead><tbody>";
  data.students.forEach((s) => {
    const status = s.graded
      ? `<span class="${badgeClass(s.level)}">${s.level}</span> <span class="muted small">${s.percentage}%</span>`
      : `<span class="badge" style="background:#f1f2f6;color:#667085;">Not graded</span>`;
    html += `<tr>
      <td>${s.name}</td>
      <td class="small muted">${s.class_name || ""}</td>
      <td>${status}</td>
      <td><button class="btn btn-outline btn-select-student" style="padding:4px 10px;font-size:0.78rem;">${s.graded ? "Re-correct" : "Correct"}</button></td>
    </tr>`;
  });
  html += "</tbody></table>";
  rosterListEl.innerHTML = html;

  const rows = rosterListEl.querySelectorAll("tbody tr");
  rows.forEach((row, i) => {
    row.querySelector(".btn-select-student").addEventListener("click", () => selectStudentForCorrection(data.students[i]));
  });
}

uploadRosterBtn.addEventListener("click", async () => {
  if (!currentExam) return;
  const file = rosterFileInput.files[0];
  if (!file) {
    errorBox.innerHTML = '<div class="alert alert-error">Please choose an .xlsx file first.</div>';
    return;
  }
  errorBox.innerHTML = "";
  uploadRosterBtn.disabled = true;
  uploadRosterBtn.innerHTML = '<span class="spinner"></span> Uploading...';
  try {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`/api/exams/${currentExam.exam_id}/students`, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) {
      errorBox.innerHTML = `<div class="alert alert-error">${data.error || "Could not upload the student list."}</div>`;
      return;
    }
    rosterFileInput.value = "";
    loadRoster(currentExam.exam_id);
  } catch (e) {
    errorBox.innerHTML = `<div class="alert alert-error">Network error: ${e.message}</div>`;
  } finally {
    uploadRosterBtn.disabled = false;
    uploadRosterBtn.textContent = "Upload Student List";
  }
});

replaceRosterBtn.addEventListener("click", async () => {
  if (!currentExam) return;
  if (!confirm("Replace the current student list? This does not delete any graded results.")) return;
  await fetch(`/api/exams/${currentExam.exam_id}/students`, { method: "DELETE" });
  loadRoster(currentExam.exam_id);
});

loadExams();
