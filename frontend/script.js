const form = document.querySelector("#analysis-form");
const descriptionInput = document.querySelector("#job-description");
const skillsInput = document.querySelector("#user-skills");
const characterCount = document.querySelector("#character-count");
const analyzeButton = document.querySelector("#analyze-button");
const formError = document.querySelector("#form-error");
const resultsPanel = document.querySelector("#results-panel");
const emptyState = document.querySelector("#empty-state");
const loadingState = document.querySelector("#loading-state");
const resultsContent = document.querySelector("#results-content");
const historyStatus = document.querySelector("#history-status");
const historyList = document.querySelector("#history-list");
const historyPagination = document.querySelector("#history-pagination");
const historyPrevious = document.querySelector("#history-previous");
const historyNext = document.querySelector("#history-next");
const historyPageStatus = document.querySelector("#history-page-status");
const historyDialog = document.querySelector("#history-dialog");
const historyDetail = document.querySelector("#history-detail");

const HISTORY_PAGE_SIZE = 5;
let currentHistoryPage = 1;

const example = {
  description:
    "We are looking for a software engineer with strong Python and SQL skills. You will build APIs with FastAPI, work with PostgreSQL, use Git and Docker, and collaborate with our React frontend team.",
  skills: "Python, Java, SQL, Git, FastAPI",
};

descriptionInput.addEventListener("input", () => {
  const count = descriptionInput.value.length;
  characterCount.textContent = `${count.toLocaleString()} ${count === 1 ? "character" : "characters"}`;
});

document.querySelector("#use-example").addEventListener("click", () => {
  descriptionInput.value = example.description;
  skillsInput.value = example.skills;
  descriptionInput.dispatchEvent(new Event("input"));
  formError.hidden = true;
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setView("loading");
  setSubmitting(true);

  const userSkills = skillsInput.value
    .split(",")
    .map((skill) => skill.trim())
    .filter(Boolean);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_description: descriptionInput.value,
        user_skills: userSkills,
      }),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail?.[0]?.msg || "We couldn't analyze this role.");
    }

    renderResults(await response.json());
    setView("results");
    resultsContent.focus();
    void loadHistory(1);
  } catch (error) {
    if (error instanceof TypeError) {
      formError.textContent =
        "Unable to reach the server. Check that CareerLens is running and try again.";
    } else {
      formError.textContent =
        error instanceof Error && error.message
          ? error.message
          : "Something went wrong. Please try again.";
    }
    formError.hidden = false;
    setView("empty");
    formError.focus();
  } finally {
    setSubmitting(false);
  }
});

historyPrevious.addEventListener("click", () => {
  void loadHistory(currentHistoryPage - 1);
});

historyNext.addEventListener("click", () => {
  void loadHistory(currentHistoryPage + 1);
});

historyList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-analysis-id]");
  if (button) void openHistoryDetail(button.dataset.analysisId);
});

document.querySelector("#close-history-dialog").addEventListener("click", () => {
  historyDialog.close();
});

historyDialog.addEventListener("click", (event) => {
  if (event.target === historyDialog) historyDialog.close();
});

function setSubmitting(isSubmitting) {
  analyzeButton.disabled = isSubmitting;
  analyzeButton.querySelector("span").textContent = isSubmitting
    ? "Analyzing…"
    : "Analyze my fit";
  resultsPanel.setAttribute("aria-busy", String(isSubmitting));
  if (isSubmitting) formError.hidden = true;
}

function setView(view) {
  emptyState.hidden = view !== "empty";
  loadingState.hidden = view !== "loading";
  resultsContent.hidden = view !== "results";
}

function renderResults(result) {
  document.querySelector("#match-score").textContent = `${result.match_score}%`;
  document
    .querySelector("#score-ring")
    .style.setProperty("--score", `${result.match_score * 3.6}deg`);
  document.querySelector("#matched-count").textContent = result.matched_skills.length;
  document.querySelector("#missing-count").textContent = result.missing_skills.length;

  const missingSkillsMessage = result.extracted_skills.length
    ? "Nothing missing — excellent fit"
    : "No skills to compare";

  renderChips("#matched-skills", result.matched_skills, "matched", "No matches yet");
  renderChips(
    "#missing-skills",
    result.missing_skills,
    "missing",
    missingSkillsMessage,
  );
  renderChips(
    "#extracted-skills",
    result.extracted_skills,
    "neutral",
    "No known skills detected",
  );

  const summary = document.querySelector("#score-summary");
  if (!result.extracted_skills.length) {
    summary.textContent =
      "No skills from our current vocabulary were found in this description.";
  } else if (result.match_score >= 80) {
    summary.textContent =
      "Strong alignment. Your current profile covers most of this role’s detected skills.";
  } else if (result.match_score >= 50) {
    summary.textContent =
      "Promising fit. Focus on the missing skills to make your application more competitive.";
  } else {
    summary.textContent =
      "This role has a meaningful skills gap. Use the list below as a focused learning roadmap.";
  }
}

function renderChips(selector, skills, variant, emptyMessage) {
  const container = document.querySelector(selector);
  container.replaceChildren();
  appendSkills(container, skills, variant, emptyMessage);
}

function appendSkills(container, skills, variant, emptyMessage) {
  if (!skills.length) {
    const empty = document.createElement("span");
    empty.className = "none-found";
    empty.textContent = emptyMessage;
    container.append(empty);
    return;
  }
  skills.forEach((skill) => {
    const chip = document.createElement("span");
    chip.className = `chip ${variant}`;
    chip.textContent = skill;
    container.append(chip);
  });
}

async function loadHistory(page) {
  historyStatus.hidden = false;
  historyStatus.textContent = "Loading recent analyses…";
  historyPagination.hidden = true;

  try {
    const response = await fetch(
      `/api/analyses?page=${page}&page_size=${HISTORY_PAGE_SIZE}`,
    );
    if (!response.ok) throw new Error("History request failed");

    renderHistory(await response.json());
  } catch {
    historyList.replaceChildren();
    historyStatus.textContent =
      "Recent analyses could not be loaded. Please try again later.";
  }
}

function renderHistory(history) {
  currentHistoryPage = history.page;
  historyList.replaceChildren();

  if (!history.items.length) {
    historyStatus.hidden = false;
    historyStatus.textContent = history.total
      ? "There are no analyses on this page."
      : "No saved analyses yet. Complete your first analysis above.";
  } else {
    historyStatus.hidden = true;
    history.items.forEach((item) => historyList.append(createHistoryCard(item)));
  }

  historyPagination.hidden = history.total_pages <= 1;
  historyPageStatus.textContent = `Page ${history.page} of ${history.total_pages}`;
  historyPrevious.disabled = history.page <= 1;
  historyNext.disabled = history.page >= history.total_pages;
}

function createHistoryCard(item) {
  const card = document.createElement("article");
  card.className = "history-card";

  const topRow = document.createElement("div");
  topRow.className = "history-card-top";

  const score = document.createElement("strong");
  score.textContent = `${item.match_score}%`;

  const date = document.createElement("time");
  date.dateTime = item.created_at;
  date.textContent = formatDate(item.created_at);

  topRow.append(score, date);

  const description = document.createElement("p");
  description.textContent = item.job_description_preview;

  const footer = document.createElement("div");
  footer.className = "history-card-footer";

  const summary = document.createElement("span");
  summary.textContent = `${item.matched_skills.length} matched · ${item.missing_skills.length} to build`;

  const detailsButton = document.createElement("button");
  detailsButton.type = "button";
  detailsButton.dataset.analysisId = item.id;
  detailsButton.textContent = "View details";

  footer.append(summary, detailsButton);
  card.append(topRow, description, footer);
  return card;
}

async function openHistoryDetail(analysisId) {
  historyDetail.replaceChildren();
  const loading = document.createElement("p");
  loading.className = "history-status";
  loading.textContent = "Loading analysis details…";
  historyDetail.append(loading);
  historyDialog.setAttribute("aria-busy", "true");
  if (!historyDialog.open) historyDialog.showModal();

  try {
    const response = await fetch(`/api/analyses/${analysisId}`);
    if (!response.ok) throw new Error("Detail request failed");
    renderHistoryDetail(await response.json());
  } catch {
    loading.textContent = "This analysis could not be loaded.";
  } finally {
    historyDialog.removeAttribute("aria-busy");
  }
}

function renderHistoryDetail(analysis) {
  historyDetail.replaceChildren();

  const summary = document.createElement("div");
  summary.className = "detail-summary";

  const score = document.createElement("strong");
  score.textContent = `${analysis.match_score}% match`;

  const date = document.createElement("time");
  date.dateTime = analysis.created_at;
  date.textContent = formatDate(analysis.created_at);
  summary.append(score, date);

  const descriptionHeading = document.createElement("h3");
  descriptionHeading.textContent = "Job description";

  const description = document.createElement("p");
  description.className = "saved-description";
  description.textContent = analysis.job_description;

  historyDetail.append(summary, descriptionHeading, description);
  appendDetailGroup("Your skills", analysis.user_skills, "neutral");
  appendDetailGroup("Matched skills", analysis.matched_skills, "matched");
  appendDetailGroup("Skills to build", analysis.missing_skills, "missing");
}

function appendDetailGroup(title, skills, variant) {
  const group = document.createElement("section");
  group.className = "detail-group";

  const heading = document.createElement("h3");
  heading.textContent = title;

  const chips = document.createElement("div");
  chips.className = "chips";
  appendSkills(chips, skills, variant, "None listed");

  group.append(heading, chips);
  historyDetail.append(group);
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

void loadHistory(1);
