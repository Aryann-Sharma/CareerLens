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

const authLoading = document.querySelector("#auth-loading");
const signedOutActions = document.querySelector("#signed-out-actions");
const signedInActions = document.querySelector("#signed-in-actions");
const currentUserEmail = document.querySelector("#current-user-email");
const authGate = document.querySelector("#auth-gate");
const signedOutMessage = document.querySelector("#signed-out-message");
const authenticatedApp = document.querySelector("#authenticated-app");
const authDialog = document.querySelector("#auth-dialog");
const authDialogStep = document.querySelector("#auth-dialog-step");
const authDialogTitle = document.querySelector("#auth-dialog-title");
const authDialogCopy = document.querySelector("#auth-dialog-copy");
const authForm = document.querySelector("#auth-form");
const authEmail = document.querySelector("#auth-email");
const authPassword = document.querySelector("#auth-password");
const passwordHint = document.querySelector("#password-hint");
const authSubmit = document.querySelector("#auth-submit");
const authError = document.querySelector("#auth-error");
const authSwitchCopy = document.querySelector("#auth-switch-copy");
const authSwitch = document.querySelector("#auth-switch");
const logoutButton = document.querySelector("#logout-button");

const HISTORY_PAGE_SIZE = 5;
let currentHistoryPage = 1;
let currentUser = null;
let authMode = "login";
let sessionRevision = 0;
let historyRevision = 0;
let detailRevision = 0;
let draftOwnerId = null;

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

document.querySelectorAll("#open-login, #gate-login").forEach((button) => {
  button.addEventListener("click", () => openAuthDialog("login"));
});

document.querySelectorAll("#open-register, #gate-register").forEach((button) => {
  button.addEventListener("click", () => openAuthDialog("register"));
});

document.querySelector("#close-auth-dialog").addEventListener("click", () => {
  authDialog.close();
});

authDialog.addEventListener("click", (event) => {
  closeOnBackdrop(event, authDialog);
});

authSwitch.addEventListener("click", () => {
  setAuthMode(authMode === "login" ? "register" : "login");
  authPassword.focus();
});

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (authSubmit.disabled) return;
  setAuthSubmitting(true);
  authError.hidden = true;

  try {
    const response = await apiFetch(`/api/auth/${authMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: authEmail.value,
        password: authPassword.value,
      }),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(readErrorMessage(body, "We couldn't complete that request."));
    }

    const user = await response.json();
    authForm.reset();
    authDialog.close();
    showSignedIn(user);
  } catch (error) {
    authError.textContent =
      error instanceof TypeError
        ? "Unable to reach the server. Check your connection and try again."
        : error.message;
    authError.hidden = false;
    authError.focus();
  } finally {
    setAuthSubmitting(false);
  }
});

logoutButton.addEventListener("click", async () => {
  logoutButton.disabled = true;
  logoutButton.textContent = "Logging out…";

  try {
    const response = await apiFetch("/api/auth/logout", { method: "POST" });
    if (!response.ok && response.status !== 401) {
      throw new Error("Logout request failed");
    }
    showSignedOut();
  } catch {
    formError.textContent = "We couldn't log you out. Please try again.";
    formError.hidden = false;
    formError.focus();
  } finally {
    logoutButton.disabled = false;
    logoutButton.textContent = "Log out";
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentUser || analyzeButton.disabled) return;
  const revision = sessionRevision;
  setView("loading");
  setSubmitting(true);

  const userSkills = skillsInput.value
    .split(",")
    .map((skill) => skill.trim())
    .filter(Boolean);

  try {
    const response = await apiFetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_description: descriptionInput.value,
        user_skills: userSkills,
      }),
    });
    const body = await response.json().catch(() => null);
    if (revision !== sessionRevision) return;

    if (response.status === 401) {
      handleExpiredSession();
      return;
    }

    if (!response.ok) {
      throw new Error(readErrorMessage(body, "We couldn't analyze this role."));
    }

    renderResults(body);
    setView("results");
    resultsContent.focus();
    void loadHistory(1);
  } catch (error) {
    if (revision !== sessionRevision) return;
    formError.textContent =
      error instanceof TypeError
        ? "Unable to reach the server. Check that CareerLens is running and try again."
        : error.message || "Something went wrong. Please try again.";
    formError.hidden = false;
    setView("empty");
    formError.focus();
  } finally {
    if (revision === sessionRevision) setSubmitting(false);
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
  closeOnBackdrop(event, historyDialog);
});

historyDialog.addEventListener("close", () => {
  detailRevision += 1;
  historyDialog.removeAttribute("aria-busy");
});

function closeOnBackdrop(event, dialog) {
  if (event.target !== dialog) return;
  const bounds = dialog.getBoundingClientRect();
  if (
    event.clientX < bounds.left || event.clientX > bounds.right ||
    event.clientY < bounds.top || event.clientY > bounds.bottom
  ) {
    dialog.close();
  }
}

async function apiFetch(path, options = {}) {
  return fetch(path, { credentials: "same-origin", ...options });
}

async function restoreSession() {
  try {
    const response = await apiFetch("/api/auth/me");
    if (response.ok) {
      showSignedIn(await response.json());
      return;
    }

    if (response.status === 401) {
      showSignedOut();
    } else {
      showSignedOut("We couldn't check your session. You can still try logging in.");
    }
  } catch {
    showSignedOut("We couldn't check your session. You can still try logging in.");
  }
}

function showSignedIn(user) {
  sessionRevision += 1;
  if (draftOwnerId !== null && draftOwnerId !== user.id) clearDraft();
  draftOwnerId = user.id;
  currentUser = user;
  authLoading.hidden = true;
  signedOutActions.hidden = true;
  signedInActions.hidden = false;
  authGate.hidden = true;
  authenticatedApp.hidden = false;
  currentUserEmail.textContent = user.email;
  formError.hidden = true;
  void loadHistory(1);
}

function showSignedOut(
  message = "Your analyses are saved to your account and are only visible to you.",
  preserveDraft = false,
) {
  sessionRevision += 1;
  if (!preserveDraft) clearDraft();
  currentUser = null;
  authLoading.hidden = true;
  signedOutActions.hidden = false;
  signedInActions.hidden = true;
  authGate.hidden = false;
  authenticatedApp.hidden = true;
  currentUserEmail.textContent = "";
  signedOutMessage.textContent = message;
  clearPrivateViews();
}

function clearDraft() {
  form.reset();
  descriptionInput.dispatchEvent(new Event("input"));
  draftOwnerId = null;
}

function clearPrivateViews() {
  historyRevision += 1;
  detailRevision += 1;
  setSubmitting(false);
  formError.textContent = "";
  formError.hidden = true;
  renderResults({
    match_score: 0,
    extracted_skills: [],
    matched_skills: [],
    missing_skills: [],
  });
  setView("empty");
  historyList.replaceChildren();
  historyPagination.hidden = true;
  historyStatus.hidden = false;
  historyStatus.textContent = "Loading recent analyses…";
  historyDetail.replaceChildren();
  if (historyDialog.open) historyDialog.close();
}

function handleExpiredSession() {
  showSignedOut("Your session ended. Log in again to continue.", true);
  openAuthDialog("login");
}

function openAuthDialog(mode) {
  setAuthMode(mode);
  authError.hidden = true;
  authPassword.value = "";
  if (!authDialog.open) authDialog.showModal();
  authEmail.focus();
}

function setAuthMode(mode) {
  authMode = mode;
  const isRegistering = mode === "register";

  authDialogStep.textContent = isRegistering ? "Get started" : "Welcome back";
  authDialogTitle.textContent = isRegistering
    ? "Create your CareerLens account"
    : "Log in to CareerLens";
  authDialogCopy.textContent = isRegistering
    ? "Save each analysis privately and return to it later."
    : "Continue to your saved analyses and private history.";
  authPassword.minLength = isRegistering ? 12 : 1;
  authPassword.autocomplete = isRegistering ? "new-password" : "current-password";
  passwordHint.textContent = isRegistering
    ? "Use at least 12 characters."
    : "";
  authSubmit.querySelector("span").textContent = isRegistering
    ? "Create account"
    : "Log in";
  authSwitchCopy.textContent = isRegistering
    ? "Already have an account?"
    : "New to CareerLens?";
  authSwitch.textContent = isRegistering ? "Log in" : "Create an account";
  authError.hidden = true;
}

function setAuthSubmitting(isSubmitting) {
  authSubmit.disabled = isSubmitting;
  authSwitch.disabled = isSubmitting;
  const isRegistering = authMode === "register";
  const idleText = isRegistering ? "Create account" : "Log in";
  const busyText = isRegistering ? "Creating account…" : "Logging in…";
  authSubmit.querySelector("span").textContent = isSubmitting
    ? busyText
    : idleText;
}

function readErrorMessage(body, fallback) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
    return body.detail[0].msg;
  }
  return fallback;
}

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
    ? "You match all detected skills"
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
      "Your skills cover most of the supported skills found in this description.";
  } else if (result.match_score >= 50) {
    summary.textContent =
      "You match at least half of the detected skills. Review the remaining skills below.";
  } else {
    summary.textContent =
      "You match fewer than half of the detected skills. The list below shows what is missing.";
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
  if (!currentUser) return;
  const revision = ++historyRevision;

  historyStatus.hidden = false;
  historyStatus.textContent = "Loading recent analyses…";
  historyPagination.hidden = true;

  try {
    const response = await apiFetch(
      `/api/analyses?page=${page}&page_size=${HISTORY_PAGE_SIZE}`,
    );
    const body = await response.json().catch(() => null);
    if (revision !== historyRevision) return;
    if (response.status === 401) {
      handleExpiredSession();
      return;
    }
    if (!response.ok) throw new Error("History request failed");

    renderHistory(body);
  } catch {
    if (revision !== historyRevision) return;
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
  if (!currentUser) return;
  const revision = ++detailRevision;
  historyDetail.replaceChildren();
  const loading = document.createElement("p");
  loading.className = "history-status";
  loading.textContent = "Loading analysis details…";
  historyDetail.append(loading);
  historyDialog.setAttribute("aria-busy", "true");
  if (!historyDialog.open) historyDialog.showModal();

  try {
    const response = await apiFetch(`/api/analyses/${analysisId}`);
    const body = await response.json().catch(() => null);
    if (revision !== detailRevision) return;
    if (response.status === 401) {
      handleExpiredSession();
      return;
    }
    if (!response.ok) throw new Error("Detail request failed");
    renderHistoryDetail(body);
  } catch {
    if (revision !== detailRevision) return;
    loading.textContent = "This analysis could not be loaded.";
  } finally {
    if (revision === detailRevision) historyDialog.removeAttribute("aria-busy");
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

void restoreSession();
