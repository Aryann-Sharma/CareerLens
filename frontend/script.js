const form = document.querySelector("#analysis-form");
const descriptionInput = document.querySelector("#job-description");
const skillsInput = document.querySelector("#user-skills");
const matchingMethod = document.querySelector("#matching-method");
const extractionMethod = document.querySelector("#extraction-method");
const reviewInput = document.querySelector("#reviewed-skills");
const updateAnalysisButton = document.querySelector("#update-analysis");
const resumeFile = document.querySelector("#resume-file");
const resumeStatus = document.querySelector("#resume-status");
const resumeReview = document.querySelector("#resume-review");
const resumeSkills = document.querySelector("#resume-skills");
const deleteDialog = document.querySelector("#delete-dialog");
const deleteError = document.querySelector("#delete-error");
const confirmDelete = document.querySelector("#confirm-delete");
let resumeRevision = 0;
let deleteTarget = null;
let analysisRevision = 0;
const matchingHint = document.querySelector("#matching-hint");
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
const historySection = document.querySelector("#history-section");
const saveButton = document.querySelector("#save-analysis");
const saveStatus = document.querySelector("#save-status");

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
const extractButton = document.querySelector("#extract-button");
const extractionStatus = document.querySelector("#extraction-status");
const extractionResults = document.querySelector("#extraction-results");
let extractionRevision = 0;

const HISTORY_PAGE_SIZE = 5;
let currentHistoryPage = 1;
let currentUser = null;
let authMode = "login";
let sessionRevision = 0;
let historyRevision = 0;
let detailRevision = 0;
let draftOwnerId = null;
let lastAnalysis = null;
let pendingSave = null;

const example = {
  description:
    "We are looking for a software engineer with strong Python and SQL skills. You will build APIs with FastAPI, work with PostgreSQL, use Git and Docker, and collaborate with our React frontend team.",
  skills: "Python, writing relational database queries, Git, FastAPI",
};

matchingMethod.addEventListener("change", () => {
  matchingHint.textContent = matchingMethod.value === "semantic"
    ? "Compare skill descriptions by meaning. Suggested matches may need review."
    : "Match skill names and supported aliases only.";
});

extractionMethod.addEventListener("change", () => {
  document.querySelector("#extraction-hint").textContent = extractionMethod.value === "trained"
    ? "Find skill phrases in context, then review and correct the suggestions."
    : "Recognize 18 supported technologies and their aliases. You can add other skills during review.";
});

descriptionInput.addEventListener("input", () => {
  clearExtraction();
  const count = descriptionInput.value.length;
  characterCount.textContent = `${count.toLocaleString()} ${count === 1 ? "character" : "characters"}`;
});

document.querySelector("#use-example").addEventListener("click", () => {
  descriptionInput.value = example.description;
  skillsInput.value = example.skills;
  descriptionInput.dispatchEvent(new Event("input"));
  formError.hidden = true;
});

document.querySelectorAll("#open-login").forEach((button) => {
  button.addEventListener("click", () => openAuthDialog("login"));
});

document.querySelectorAll("#open-register").forEach((button) => {
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
    const analysisToSave = pendingSave;
    pendingSave = null;
    authForm.reset();
    authDialog.close();
    showSignedIn(user);
    if (analysisToSave && lastAnalysis === analysisToSave) await saveCurrentAnalysis();
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
  if (analyzeButton.disabled) return;

  const userSkills = skillsInput.value
    .split(",")
    .map((skill) => skill.trim())
    .filter(Boolean);

  const request = {
    job_description: descriptionInput.value,
    user_skills: userSkills,
    matching_method: matchingMethod.value,
    extraction_method: extractionMethod.value,
  };
  await runAnalysis(request);
});

async function runAnalysis(request) {
  const revision = sessionRevision;
  const operation = ++analysisRevision;
  const previous = lastAnalysis;
  setView("loading");
  setSubmitting(true);
  lastAnalysis = null;
  pendingSave = null;
  const ownerId = currentUser?.id ?? null;
  try {
    const response = await apiFetch(currentUser ? "/api/analyze" : "/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const body = await response.json().catch(() => null);
    if (revision !== sessionRevision || operation !== analysisRevision) return;

    if (response.status === 401) {
      handleExpiredSession();
      return;
    }

    if (!response.ok) {
      throw new Error(readErrorMessage(body, "We couldn't analyze this role."));
    }

    lastAnalysis = { request, result: body, saved: ownerId !== null, ownerId,
      savedId: response.headers.get("Location")?.split("/").pop() };
    renderResults(body);
    updateSaveControl();
    setView("results");
    resultsContent.focus();
    void loadHistory(1);
  } catch (error) {
    if (revision !== sessionRevision || operation !== analysisRevision) return;
    formError.textContent =
      error instanceof TypeError
        ? "Unable to reach the server. Check that CareerLens is running and try again."
        : error.message || "Something went wrong. Please try again.";
    formError.hidden = false;
    if (previous && request.reviewed_job_skills) {
      lastAnalysis = previous;
      updateSaveControl();
      setView("results");
    } else setView("empty");
    formError.focus();
  } finally {
    if (revision === sessionRevision && operation === analysisRevision) setSubmitting(false);
  }
}

updateAnalysisButton.addEventListener("click", () => {
  if (!lastAnalysis || analyzeButton.disabled) return;
  const reviewed = reviewInput.value.split("\n").map((skill) => skill.trim()).filter(Boolean);
  void runAnalysis({ ...lastAnalysis.request, reviewed_job_skills: reviewed });
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

function clearExtraction() {
  extractionRevision += 1;
  extractionStatus.textContent = "";
  extractionResults.hidden = true;
  document.querySelector("#extracted-activities").replaceChildren();
  document.querySelector("#extracted-knowledge").replaceChildren();
  extractButton.disabled = false;
  extractButton.textContent = "Extract from job description";
}

function updateSaveControl() {
  saveButton.disabled = !lastAnalysis || lastAnalysis.saved;
  saveButton.textContent = lastAnalysis?.saved ? "Saved" : "Save analysis";
  saveStatus.textContent = lastAnalysis?.saved
    ? "Saved to your private history."
    : "Not saved. This result stays here until you leave or refresh.";
}

authDialog.addEventListener("close", () => {
  pendingSave = null;
});

saveButton.addEventListener("click", () => {
  if (!lastAnalysis || saveButton.disabled) return;
  if (!currentUser) {
    pendingSave = lastAnalysis;
    openAuthDialog("login");
    return;
  }
  void saveCurrentAnalysis();
});

async function saveCurrentAnalysis() {
  const snapshot = lastAnalysis;
  if (!currentUser || !snapshot || snapshot.saved || saveButton.disabled) return;
  const revision = sessionRevision;
  saveButton.disabled = true;
  saveButton.textContent = "Saving…";
  saveStatus.textContent = "Saving to your private history…";
  try {
    const response = await apiFetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(snapshot.request),
    });
    const body = await response.json().catch(() => null);
    if (revision !== sessionRevision || lastAnalysis !== snapshot) return;
    if (response.status === 401) {
      handleExpiredSession();
      if (snapshot.ownerId === null) {
        lastAnalysis = snapshot;
        pendingSave = snapshot;
        renderResults(snapshot.result);
        setView("results");
        updateSaveControl();
        setAuthMode(authMode);
      }
      return;
    }
    if (!response.ok) throw new Error(readErrorMessage(body, "We couldn't save this analysis. Please try again."));
    lastAnalysis = { ...snapshot, result: body, saved: true, ownerId: currentUser.id,
      savedId: response.headers.get("Location")?.split("/").pop() };
    renderResults(body);
    updateSaveControl();
    void loadHistory(1);
  } catch (error) {
    if (revision !== sessionRevision || lastAnalysis !== snapshot) return;
    saveStatus.textContent = error instanceof TypeError
      ? "Unable to reach the server. Your result is still here; try saving again."
      : error.message;
    saveButton.disabled = false;
    saveButton.textContent = "Save analysis";
  }
}

extractButton.addEventListener("click", async () => {
  if (extractButton.disabled) return;
  clearExtraction();
  const text = descriptionInput.value.trim();
  if (!text || Array.from(text).length > 50000) {
    extractionStatus.textContent = "Enter a job description of 1 to 50,000 characters above.";
    descriptionInput.focus();
    return;
  }
  const revision = extractionRevision;
  const session = sessionRevision;
  extractButton.disabled = true;
  extractButton.textContent = "Extracting…";
  extractionStatus.textContent = "Looking for skill phrases…";
  try {
    const response = await apiFetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_description: text }),
    });
    const body = await response.json().catch(() => null);
    if (revision !== extractionRevision || session !== sessionRevision) return;
    if (response.status === 401) {
      handleExpiredSession();
      return;
    }
    if (!response.ok) throw new Error(readErrorMessage(body, "We couldn't extract skill phrases."));
    const phrases = (label) => [...new Set(body.spans.filter((span) => span.label === label).map((span) => span.text))];
    renderChips("#extracted-activities", phrases("skill"), "neutral", "No activity phrases detected.");
    renderChips("#extracted-knowledge", phrases("knowledge"), "neutral", "No knowledge phrases detected.");
    extractionResults.hidden = false;
    extractionStatus.textContent = body.spans.length
      ? "Preview ready. These are model predictions and may be incomplete or incorrect."
      : "No phrases detected. This does not mean the description has no skills.";
  } catch (error) {
    if (revision !== extractionRevision || session !== sessionRevision) return;
    extractionStatus.textContent = error instanceof TypeError
      ? "Unable to reach the server. Please try again."
      : error.message;
  } finally {
    if (revision === extractionRevision && session === sessionRevision) {
      extractButton.disabled = false;
      extractButton.textContent = "Extract from job description";
    }
  }
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
  const revision = sessionRevision;
  try {
    const response = await apiFetch("/api/auth/me");
    if (revision !== sessionRevision) return;
    if (response.ok) {
      const user = await response.json();
      if (revision === sessionRevision) showSignedIn(user);
      return;
    }

    if (response.status === 401) {
      showSignedOut(undefined, true, true);
    } else {
      showSignedOut("You can analyze now. Sign in to save; your session could not be checked.", true, true);
    }
  } catch {
    if (revision !== sessionRevision) return;
    showSignedOut("You can analyze now. Sign in to save; your session could not be checked.", true, true);
  }
}

function showSignedIn(user) {
  document.body.classList.add("is-signed-in");
  sessionRevision += 1;
  if (draftOwnerId !== null && draftOwnerId !== user.id) {
    clearDraft();
    clearPrivateViews();
  }
  draftOwnerId = user.id;
  currentUser = user;
  authLoading.hidden = true;
  signedOutActions.hidden = true;
  signedInActions.hidden = false;
  authGate.hidden = true;
  authenticatedApp.hidden = false;
  historySection.hidden = false;
  setSubmitting(false);
  if (!lastAnalysis) setView("empty");
  updateSaveControl();
  currentUserEmail.textContent = user.email;
  formError.hidden = true;
  void loadHistory(1);
}

function showSignedOut(
  message = "No account needed. Sign in when you want to save an analysis.",
  preserveDraft = false,
  initial = false,
) {
  document.body.classList.remove("is-signed-in");
  if (!initial) sessionRevision += 1;
  if (!preserveDraft) clearDraft();
  currentUser = null;
  authLoading.hidden = true;
  signedOutActions.hidden = false;
  signedInActions.hidden = true;
  authGate.hidden = false;
  authenticatedApp.hidden = false;
  historySection.hidden = true;
  currentUserEmail.textContent = "";
  signedOutMessage.textContent = message;
  if (!initial) clearPrivateViews();
}

function clearDraft() {
  form.reset();
  matchingMethod.dispatchEvent(new Event("change"));
  extractionMethod.dispatchEvent(new Event("change"));
  descriptionInput.dispatchEvent(new Event("input"));
  draftOwnerId = null;
}

function clearPrivateViews() {
  lastAnalysis = null;
  pendingSave = null;
  analysisRevision += 1;
  clearResume();
  deleteTarget = null;
  if (deleteDialog.open) deleteDialog.close();
  document.querySelector("#skill-review").open = false;
  clearExtraction();
  document.querySelector("#extraction-preview").open = false;
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
  if (pendingSave) authDialogCopy.textContent = "Sign in to save this analysis. Your result will stay here.";
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
  updateAnalysisButton.disabled = isSubmitting;
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
  reviewInput.value = result.extracted_skills.join("\n");
  renderSourceEvidence(document.querySelector("#source-evidence"), lastAnalysis?.request.job_description || "", result.extraction_details);
  document.querySelector("#extraction-method-note").textContent = extractionExplanation(result.extraction_details);
  renderMatchingEvidence(document.querySelector("#matching-evidence"), result.matching_details);
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
      "No skills were detected. Review the description and add any missing skills.";
  } else if (result.match_score >= 80) {
    summary.textContent =
      "Your skills cover most of the detected skills in this description.";
  } else if (result.match_score >= 50) {
    summary.textContent =
      "You match at least half of the detected skills. Review the remaining skills below.";
  } else {
    summary.textContent =
      "You match fewer than half of the detected skills. The list below shows what is missing.";
  }
}

function renderMatchingEvidence(container, details) {
  container.replaceChildren();
  container.hidden = false;
  const explanation = document.createElement("p");
  explanation.textContent = details
    ? `Semantic matching · Exact-match baseline: ${details.exact_match_score}%. ` +
      "Suggested matches count toward this score. Similarity is not proof of proficiency."
    : "Exact matching · Skill names and supported aliases only.";
  container.append(explanation);
  if (!details?.semantic_matches.length) return;
  const list = document.createElement("ul");
  details.semantic_matches.forEach((match) => {
    const item = document.createElement("li");
    item.textContent = `${match.skill} ← “${match.user_skill}” ` +
      `(similarity ${match.similarity.toFixed(2)})`;
    list.append(item);
  });
  container.append(list);
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
  const session = sessionRevision;

  historyStatus.hidden = false;
  historyStatus.textContent = "Loading recent analyses…";
  historyPagination.hidden = true;

  try {
    const response = await apiFetch(
      `/api/analyses?page=${page}&page_size=${HISTORY_PAGE_SIZE}`,
    );
    const body = await response.json().catch(() => null);
    if (session !== sessionRevision || revision !== historyRevision) return;
    if (response.status === 401) {
      handleExpiredSession();
      return;
    }
    if (!response.ok) throw new Error("History request failed");

    if (page > Math.max(1, body.total_pages)) {
      await loadHistory(Math.max(1, body.total_pages));
      return;
    }
    renderHistory(body);
  } catch {
    if (session !== sessionRevision || revision !== historyRevision) return;
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

  const deleteButton = document.createElement("button");
  deleteButton.type = "button";
  deleteButton.textContent = "Delete";
  deleteButton.className = "delete-history-button";
  deleteButton.addEventListener("click", () => {
    deleteTarget = { id: item.id, revision: sessionRevision };
    document.querySelector("#delete-preview").textContent = item.job_description_preview;
    deleteError.hidden = true;
    confirmDelete.disabled = false;
    confirmDelete.textContent = "Delete analysis";
    deleteDialog.showModal();
  });
  const actions = document.createElement("div");
  actions.className = "history-card-actions";
  actions.append(detailsButton, deleteButton);
  footer.append(summary, actions);
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
  renderSourceEvidence(description, analysis.job_description, analysis.extraction_details);

  historyDetail.append(summary, descriptionHeading, description);
  const evidence = document.createElement("div");
  evidence.className = "matching-evidence";
  renderMatchingEvidence(evidence, analysis.matching_details);
  historyDetail.append(evidence);
  const methodNote = document.createElement("p");
  methodNote.textContent = extractionExplanation(analysis.extraction_details);
  historyDetail.append(methodNote);
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

function extractionExplanation(details) {
  if (details?.method === "reviewed") return "Reviewed skill list · The score uses your corrections.";
  if (details?.method === "trained") return "Trained extraction + technology catalog. Highlighted phrases are predictions; review them for errors and duplicates.";
  return "Catalog extraction · Only supported technology names and aliases are detected.";
}

function renderSourceEvidence(container, text, details) {
  container.replaceChildren();
  const chars = Array.from(text);
  const ranges = (details?.spans || []).map((span) => [span.start, span.end])
    .filter(([start, end]) => start >= 0 && end > start && end <= chars.length)
    .sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const range of ranges) {
    const previous = merged[merged.length - 1];
    if (previous && range[0] <= previous[1]) previous[1] = Math.max(previous[1], range[1]);
    else merged.push([...range]);
  }
  let cursor = 0;
  for (const [start, end] of merged) {
    container.append(document.createTextNode(chars.slice(cursor, start).join("")));
    const mark = document.createElement("mark");
    mark.textContent = chars.slice(start, end).join("");
    container.append(mark);
    cursor = end;
  }
  container.append(document.createTextNode(chars.slice(cursor).join("")));
}

function clearResume() {
  resumeRevision += 1;
  resumeFile.value = "";
  resumeStatus.textContent = "";
  resumeSkills.value = "";
  resumeReview.hidden = true;
}

resumeFile.addEventListener("change", async () => {
  const file = resumeFile.files[0];
  const revision = ++resumeRevision;
  const session = sessionRevision;
  resumeReview.hidden = true;
  resumeSkills.value = "";
  if (!file) { resumeStatus.textContent = ""; return; }
  if (file.size > 5 * 1024 * 1024) {
    resumeStatus.textContent = "Choose a PDF smaller than 5 MB.";
    return;
  }
  resumeStatus.textContent = "Reading résumé and finding skills…";
  try {
    const response = await apiFetch(`/api/resume?method=${extractionMethod.value}`, {
      method: "POST", headers: { "Content-Type": "application/pdf" }, body: file,
    });
    const body = await response.json().catch(() => null);
    if (revision !== resumeRevision || session !== sessionRevision) return;
    if (!response.ok) throw new Error(readErrorMessage(body, "This PDF could not be read."));
    resumeSkills.value = body.skills.join("\n");
    resumeReview.hidden = false;
    resumeStatus.textContent = `Read ${body.pages} ${body.pages === 1 ? "page" : "pages"}. Review the suggestions below; add any skills that were missed.`;
  } catch (error) {
    if (revision !== resumeRevision || session !== sessionRevision) return;
    resumeStatus.textContent = error instanceof TypeError ? "Unable to reach the server. Please try again." : error.message;
  } finally {
    if (revision === resumeRevision && session !== sessionRevision) {
      resumeStatus.textContent = "Your session changed. Upload the PDF again to continue.";
    }
  }
});

document.querySelector("#apply-resume").addEventListener("click", () => {
  const skills = [...skillsInput.value.split(","), ...resumeSkills.value.split("\n")];
  const seen = new Set();
  const combined = skills.map((skill) => skill.trim()).filter((skill) => {
    const key = skill.toLocaleLowerCase();
    if (!skill || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  if (combined.length > 200 || combined.some((skill) => skill.length > 100 || skill.includes(","))) {
    resumeStatus.textContent = "Use up to 200 short skills, each under 101 characters. Put comma-separated skills on separate lines.";
    return;
  }
  skillsInput.value = combined.join(", ");
  resumeStatus.textContent = "Added to your skills. You can edit your profile before analyzing.";
  skillsInput.focus();
});

document.querySelector("#cancel-delete").addEventListener("click", () => deleteDialog.close());
deleteDialog.addEventListener("close", () => { deleteTarget = null; });
deleteDialog.addEventListener("click", (event) => closeOnBackdrop(event, deleteDialog));
confirmDelete.addEventListener("click", async () => {
  const target = deleteTarget;
  if (!target || !currentUser || confirmDelete.disabled) return;
  confirmDelete.disabled = true;
  confirmDelete.textContent = "Deleting…";
  deleteError.hidden = true;
  try {
    const response = await apiFetch(`/api/analyses/${target.id}`, { method: "DELETE" });
    if (target.revision !== sessionRevision) return;
    if (response.status === 401) { handleExpiredSession(); return; }
    if (!response.ok && response.status !== 404) throw new Error("We couldn't delete this analysis. Please try again.");
    if (lastAnalysis?.savedId === String(target.id)) {
      lastAnalysis.saved = false;
      lastAnalysis.savedId = null;
      updateSaveControl();
    }
    if (deleteTarget === target) deleteDialog.close();
    await loadHistory(currentHistoryPage);
  } catch (error) {
    if (target.revision !== sessionRevision || deleteTarget !== target) return;
    deleteError.textContent = error instanceof TypeError ? "Unable to reach the server. Please try again." : error.message;
    deleteError.hidden = false;
  } finally {
    if (deleteTarget === target) {
      confirmDelete.disabled = false;
      confirmDelete.textContent = "Delete analysis";
    }
  }
});

void restoreSession();
