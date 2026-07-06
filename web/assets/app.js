const state = {
  records: [],
  overview: null,
  engine: "heuristic",
};

const kpiGrid = document.getElementById("kpi-grid");
const categoryChart = document.getElementById("category-chart");
const areaChart = document.getElementById("area-chart");
const urgentTable = document.getElementById("urgent-table");
const recentTable = document.getElementById("recent-table");
const allComplaintsTable = document.getElementById("all-complaints-table");
const insightSummary = document.getElementById("insight-summary");
const anomalyList = document.getElementById("anomaly-list");
const actionList = document.getElementById("action-list");
const statusMessage = document.getElementById("status-message");
const chatResponse = document.getElementById("chat-response");
const engineBadge = document.getElementById("engine-badge");

function formatTimestamp(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value || "Unknown";
  }
  const day = parsed.getUTCDate();
  const month = parsed.toLocaleString("en-US", { month: "long", timeZone: "UTC" });
  const year = parsed.getUTCFullYear();
  return `${day}, ${month} ${year}`;
}

function setStatus(message) {
  statusMessage.textContent = message;
}

function renderKpis(kpis = {}) {
  const cards = [
    ["Total Issues", kpis.totalIssues ?? "0"],
    ["Urgent Issues", kpis.urgentIssues ?? "0"],
    ["Top Category", kpis.topCategory ?? "N/A"],
    ["Priority Area", kpis.topArea ?? "N/A"],
  ];

  kpiGrid.innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="kpi-card">
          <div class="panel-subtitle">${label}</div>
          <div class="kpi-value">${value}</div>
          <div class="kpi-label">Decision intelligence snapshot</div>
        </article>
      `
    )
    .join("");
}

function renderBars(container, data, fallback) {
  if (!data || !data.length) {
    container.classList.add("empty-state");
    container.textContent = fallback;
    return;
  }

  container.classList.remove("empty-state");
  const max = Math.max(...data.map((item) => item.value), 1);
  container.innerHTML = data
    .map(
      (item) => `
        <div class="bar-row">
          <div>${item.label}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${(item.value / max) * 100}%"></div></div>
          <div>${item.value}</div>
        </div>
      `
    )
    .join("");
}

function renderInsightList(container, items, fallback) {
  container.innerHTML = "";
  if (!items || !items.length) {
    container.innerHTML = `<li>${fallback}</li>`;
    return;
  }
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    container.appendChild(li);
  });
}

function renderUrgentTable(records) {
  if (!records.length) {
    urgentTable.innerHTML = '<tr><td colspan="4" class="empty-row">No urgent issues yet.</td></tr>';
    return;
  }

  urgentTable.innerHTML = records
    .map(
      (record) => `
        <tr>
          <td>${record.area}</td>
          <td>${record.ai_category}</td>
          <td><span class="pill ${record.urgency_score >= 80 ? "urgent" : ""}">${record.urgency_score}</span></td>
          <td>${record.recommended_action}</td>
        </tr>
      `
    )
    .join("");
}

function renderRecentTable(records) {
  if (!records.length) {
    recentTable.innerHTML = '<tr><td colspan="4" class="empty-row">No complaint data loaded.</td></tr>';
    return;
  }
  recentTable.innerHTML = records
    .map(
      (record) => `
        <tr>
          <td>${formatTimestamp(record.timestamp)}</td>
          <td>${record.area}</td>
          <td>${record.summary}</td>
          <td>${record.department}</td>
        </tr>
      `
    )
    .join("");
}

function renderAllComplaints(records) {
  if (!records.length) {
    allComplaintsTable.innerHTML = '<tr><td colspan="6" class="empty-row">No complaints available yet.</td></tr>';
    return;
  }

  allComplaintsTable.innerHTML = records
    .map(
      (record) => `
        <tr>
          <td>${formatTimestamp(record.timestamp)}</td>
          <td>${record.area}</td>
          <td>${record.ai_category}</td>
          <td>${record.summary}</td>
          <td><span class="pill ${record.urgency_score >= 80 ? "urgent" : ""}">${record.urgency_score}</span></td>
          <td>${record.department}</td>
        </tr>
      `
    )
    .join("");
}

function renderDashboard() {
  const overview = state.overview || {};
  renderKpis(overview.kpis);
  renderBars(categoryChart, overview.categoryCounts, "Load data to view category trends.");
  renderBars(areaChart, overview.areaCounts, "No hotspot analysis yet.");
  renderUrgentTable(overview.urgentRecords || []);
  renderRecentTable(overview.recentRecords || []);
  renderAllComplaints(state.records || []);

  insightSummary.textContent = overview.insights?.summary || "Upload or load a dataset to generate an overview.";
  renderInsightList(anomalyList, overview.insights?.anomalies, "No anomalies detected yet.");
  renderInsightList(actionList, overview.insights?.recommendedActions, "No recommendations yet.");
  engineBadge.textContent = formatEngineLabel(state.engine);
}

function formatEngineLabel(engine) {
  if (engine === "vertex-ai") {
    return "Vertex AI analysis active";
  }
  if (engine === "gemini-api") {
    return "Gemini-assisted analysis active";
  }
  return "Heuristic analysis active";
}

async function loadSampleData() {
  setStatus("Loading sample dataset...");
  const response = await fetch("/api/sample-data");
  const payload = await response.json();
  state.records = payload.records;
  state.overview = payload.overview;
  state.engine = payload.engine;
  renderDashboard();
  chatResponse.textContent = "Sample data loaded. Ask a question about what the city should prioritize.";
  setStatus(`Loaded ${state.records.length} complaints from the sample dataset.`);
}

async function uploadCsv(file) {
  const formData = new FormData();
  formData.append("file", file);
  setStatus(`Uploading ${file.name}...`);
  const response = await fetch("/api/analyze", { method: "POST", body: formData });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Upload failed.");
  }
  state.records = payload.records;
  state.overview = payload.overview;
  state.engine = payload.engine;
  renderDashboard();
  chatResponse.textContent = "CSV analyzed successfully. Try asking which area needs attention first.";
  setStatus(`Analyzed ${state.records.length} uploaded complaints.`);
}

async function askQuestion(question) {
  if (!state.records.length) {
    chatResponse.textContent = "Load a dataset first so CivicSignal has context.";
    return;
  }
  chatResponse.textContent = "Generating answer...";
  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, records: state.records }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Question failed.");
  }
  chatResponse.textContent = payload.answer;
  engineBadge.textContent = formatEngineLabel(payload.engine);
}

document.getElementById("load-sample").addEventListener("click", () => {
  loadSampleData().catch((err) => {
    setStatus(err.message);
    chatResponse.textContent = "Could not load the sample dataset.";
  });
});

document.getElementById("csv-upload").addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  uploadCsv(file).catch((err) => {
    setStatus(err.message);
    chatResponse.textContent = "CSV upload failed. Check the required columns and try again.";
  });
});

document.getElementById("ask-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("question-input");
  const question = input.value.trim();
  if (!question) {
    chatResponse.textContent = "Enter a question to get a decision-ready answer.";
    return;
  }
  askQuestion(question).catch((err) => {
    chatResponse.textContent = `Could not answer the question: ${err.message}`;
  });
});

renderDashboard();
