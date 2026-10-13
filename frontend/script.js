const form = document.querySelector("#analysis-form");
const descriptionInput = document.querySelector("#job-description");
const jobImage = document.querySelector("#job-image");
const jobPdf = document.querySelector("#job-pdf");
const addPdfButton = document.querySelector("#add-job-pdf");
let jobUploadFile = null;
let jobUploadKind = "image";
let fullJobText = "";
let selectedJobText = "";
const importPanel = document.querySelector("#job-import");
const addImageButton = document.querySelector("#add-job-image");
const importStatus = document.querySelector("#job-import-status");
const importReview = document.querySelector("#job-import-review");
const importText = document.querySelector("#job-import-text");
const readUploadButton = document.querySelector("#read-job-upload");
let importRevision = 0;
let importController = null;
const skillsInput = document.querySelector("#user-skills");
const matchingMethod = document.querySelector("#matching-method");
const extractionMethod = document.querySelector("#extraction-method");
const reviewInput = document.querySelector("#reviewed-skills");
const updateAnalysisButton = document.querySelector("#update-analysis");
const resumeFile = document.querySelector("#resume-file");
const resumeStatus = document.querySelector("#resume-status");
const resumeReview = document.querySelector("#resume-review");
const resumeSkills = document.querySelector("#resume-skills");
const savedResumePanel = document.querySelector("#saved-resume");
const savedResumeStatus = document.querySelector("#saved-resume-status");
const saveResumeButton = document.querySelector("#save-resume");
const resumeDeleteDialog = document.querySelector("#delete-resume-dialog");
let savedResume = null;
let resumeCandidate = null;
let savedResumeRevision = 0;
let resumeBusy = false;
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
    : "Match skill names and common abbreviations only.";
});

extractionMethod.addEventListener("change", () => {
  document.querySelector("#extraction-hint").textContent = extractionMethod.value === "trained"
    ? "Find skill phrases in context, then review and correct the suggestions."
    : "Look for 18 common technical skills, such as Python, SQL, and Git. Add any missed skills during review.";
});

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
    interpret_duties: extractionMethod.value === "trained",
  };
  await runAnalysis(request);
});

async function runAnalysis(request) {
  learning.pause();
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
    learning.setAnalysis(lastAnalysis);
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
      learning.panel.hidden = false;
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
  learning.saved.sessionChanged(user);
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
  updateResumeControls();
  void loadSavedResume();
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
  learning.saved.sessionChanged(null);
  authLoading.hidden = true;
  signedOutActions.hidden = false;
  signedInActions.hidden = true;
  authGate.hidden = false;
  authenticatedApp.hidden = false;
  historySection.hidden = true;
  currentUserEmail.textContent = "";
  signedOutMessage.textContent = message;
  if (!initial) clearPrivateViews();
  updateResumeControls();
}

function clearDraft() {
  form.reset();
  matchingMethod.dispatchEvent(new Event("change"));
  extractionMethod.dispatchEvent(new Event("change"));
  descriptionInput.dispatchEvent(new Event("input"));
  draftOwnerId = null;
}

function clearPrivateViews() {
  learning.clear();
  lastAnalysis = null;
  pendingSave = null;
  analysisRevision += 1;
  clearResume();
  clearJobImport();
  deleteTarget = null;
  if (deleteDialog.open) deleteDialog.close();
  document.querySelector("#skill-review").open = false;
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
  document.querySelector("#learning-chip-hint").hidden = !result.missing_skills.length;
  reviewInput.value = result.extracted_skills.join("\n");
  renderContextSuggestions(document.querySelector("#context-suggestions"), result.extraction_details, true);
  document.querySelector("#context-review").hidden = !result.extraction_details?.context_notice;
  const contextCount = result.extraction_details?.context_suggestions?.length || 0;
  document.querySelector("#context-review summary").textContent = `Check the wider role context${contextCount ? ` (${contextCount} ${contextCount === 1 ? "suggestion" : "suggestions"})` : ""}`;
  renderSpellingChecks(document.querySelector("#spelling-checks"), result.extraction_details?.spelling, (original, candidate) => {
    applySpellingChoice(reviewInput, original, candidate);
    openSkillsReview();
    return "Added to your review. Choose Update analysis to recalculate the score.";
  });
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
    ? `Including similar wording. With skill names alone: ${details.exact_match_score}%. ` +
      "Suggested matches count toward this score. Review them to check they describe your experience."
    : "Matching skill names and common abbreviations only.";
  container.append(explanation);
  if (!details?.semantic_matches.length) return;
  const list = document.createElement("ul");
  details.semantic_matches.forEach((match) => {
    const item = document.createElement("li");
    item.textContent = `${match.skill} — suggested from “${match.user_skill}”`;
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
    const chip = document.createElement(variant === "missing" ? "button" : "span");
    chip.className = `chip ${variant}`;
    chip.textContent = skill;
    if (variant === "missing") {
      chip.type = "button";
      chip.classList.add("learning-chip");
      chip.setAttribute("aria-label", `Learning guide for ${skill}`);
      chip.addEventListener("click", () => void learning.openGuide(skill));
    }
    container.append(chip);
  });
}

function openSkillsReview() {
  const review = document.querySelector("#skill-review");
  review.open = true;
  reviewInput.focus({ preventScroll: true });
  reviewInput.scrollIntoView({ block: "center" });
}

const learning = new LearningWorkspace({
  signIn: () => openAuthDialog("login"),
  expired: () => handleExpiredSession(),
});
document.querySelector("#edit-result-skills").addEventListener("click", openSkillsReview);

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
  const spelling = document.createElement("div");
  spelling.className = "spelling-checks";
  renderSpellingChecks(spelling, analysis.extraction_details?.spelling);
  historyDetail.append(spelling);
  const context = document.createElement("div");
  renderContextSuggestions(context, analysis.extraction_details);
  historyDetail.append(context);
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
  if (details?.method === "trained") return "Skills found using the wording of the description. Check the highlighted phrases and correct any mistakes below.";
  return "Skills found from a list of 18 common technologies. Add any other requirements that were missed.";
}

function renderContextSuggestions(container, details, editable = false) {
  container.replaceChildren();
  container.hidden = !details?.context_notice;
  if (!details?.context_notice) return;
  const title = document.createElement("h3");
  title.textContent = "Skills suggested by the duties";
  const notice = document.createElement("p");
  notice.textContent = details.context_notice;
  container.append(title, notice);
  for (const suggestion of details.context_suggestions || []) {
    const row = document.createElement("div");
    row.className = "context-choice";
    const label = document.createElement("strong");
    label.textContent = suggestion.skill;
    const evidence = document.createElement("p");
    evidence.textContent = `Based on: “${suggestion.evidence}”`;
    row.append(label, evidence);
    if (editable) {
      const actions = document.createElement("div");
      actions.className = "resume-actions";
      const add = document.createElement("button");
      add.type = "button";
      add.className = "secondary-button";
      add.textContent = `Add ${suggestion.skill}`;
      add.addEventListener("click", () => {
        applySpellingChoice(reviewInput, suggestion.skill, suggestion.skill);
        openSkillsReview();
        const status = document.createElement("p");
        status.textContent = "Added to your review. Remove any literal or duplicate phrases, then choose Update analysis.";
        actions.replaceWith(status);
      });
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.className = "text-button";
      dismiss.textContent = "Dismiss";
      dismiss.addEventListener("click", () => {
        actions.remove();
        evidence.textContent = "Dismissed. Your skill list and score have not changed.";
        evidence.tabIndex = -1;
        evidence.focus();
      });
      actions.append(add, dismiss);
      row.append(actions);
    }
    container.append(row);
  }
  if (!details.context_suggestions?.length) {
    const empty = document.createElement("p");
    empty.textContent = "No additional suggestions to review. Indirect wording may still be missed; add or remove skills in the editor.";
    container.append(empty);
  }
}

function applySpellingChoice(input, original, candidate) {
  const escaped = original.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`\\b${escaped}\\b`, "gi");
  let replaced = false;
  const lines = input.value.split("\n").map((line) => line.replace(pattern, () => {
    replaced = true;
    return candidate;
  }).trim()).filter(Boolean);
  if (!replaced) lines.push(candidate);
  const seen = new Set();
  input.value = lines.filter((line) => {
    const key = line.toLocaleLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).join("\n");
}

function renderSpellingChecks(container, checks, onChoose) {
  container.replaceChildren();
  container.hidden = !checks?.length;
  if (!checks?.length) return;
  const heading = document.createElement("h3");
  heading.textContent = "Spelling checks";
  container.append(heading);
  for (const check of checks) {
    const row = document.createElement("div");
    const note = document.createElement("p");
    note.textContent = check.applied
      ? `Read “${check.original}” as ${check.candidates[0]}.`
      : `Did you mean ${check.candidates.map((candidate) => `“${candidate}”`).join(" or ")} instead of “${check.original}”? No correction has been applied.`;
    row.append(note);
    if (!check.applied && onChoose) {
      const actions = document.createElement("div");
      actions.className = "resume-actions";
      for (const candidate of check.candidates) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary-button";
        button.textContent = `Use ${candidate}`;
        button.addEventListener("click", () => {
          note.textContent = onChoose(check.original, candidate);
          actions.remove();
        });
        actions.append(button);
      }
      const keepButton = document.createElement("button");
      keepButton.type = "button";
      keepButton.className = "text-button";
      keepButton.textContent = "Keep original";
      keepButton.addEventListener("click", () => {
        note.textContent = `Kept “${check.original}”. No correction has been applied.`;
        actions.remove();
        note.tabIndex = -1;
        note.focus();
      });
      actions.append(keepButton);
      row.append(actions);
    }
    container.append(row);
  }
  if (onChoose) {
    const hint = document.createElement("p");
    hint.className = "field-hint";
    hint.textContent = "Check the suggested spellings. You can edit the skill list if a correction is wrong.";
    container.append(hint);
  }
}

function renderResumeSpelling(checks) {
  renderSpellingChecks(document.querySelector("#resume-spelling"), checks, (original, candidate) => {
    applySpellingChoice(resumeSkills, original, candidate);
    resumeSkills.focus();
    return "Updated the list below. Choose Add to my skills when you have finished reviewing.";
  });
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
  savedResumeRevision += 1;
  savedResume = null;
  resumeCandidate = null;
  resumeBusy = false;
  savedResumeStatus.textContent = "";
  document.querySelector("#retry-saved-resume").hidden = true;
  if (resumeDeleteDialog.open) resumeDeleteDialog.close();
  updateResumeControls();
  resumeFile.value = "";
  resumeStatus.textContent = "";
  resumeSkills.value = "";
  resumeReview.hidden = true;
  renderResumeSpelling([]);
}

resumeFile.addEventListener("change", async () => {
  const file = resumeFile.files[0];
  resumeCandidate = null;
  updateResumeControls();
  const revision = ++resumeRevision;
  const session = sessionRevision;
  resumeReview.hidden = true;
  resumeSkills.value = "";
  renderResumeSpelling([]);
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
    resumeCandidate = file;
    updateResumeControls();
    resumeSkills.value = body.skills.join("\n");
    renderResumeSpelling(body.spelling);
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

function clearJobImport(message = "") {
  importRevision += 1;
  importController?.abort();
  importController = null;
  jobUploadFile = null;
  jobImage.value = "";
  jobPdf.value = "";
  fullJobText = "";
  selectedJobText = "";
  importText.value = "";
  importReview.hidden = true;
  importPanel.hidden = true;
  importStatus.textContent = message;
  document.querySelector("#original-job-text").textContent = "";
  document.querySelector("#original-job-document").open = false;
  document.querySelector("#job-section-note").textContent = "";
  document.querySelector("#job-section-actions").hidden = true;
  readUploadButton.disabled = true;
  readUploadButton.textContent = "Read upload again";
}

async function readJobUpload() {
  importController?.abort();
  const revision = ++importRevision;
  const session = sessionRevision;
  const file = jobUploadFile;
  const isPdf = jobUploadKind === "pdf";
  const source = isPdf ? "PDF" : "image";
  importText.value = "";
  fullJobText = "";
  selectedJobText = "";
  document.querySelector("#original-job-text").textContent = "";
  document.querySelector("#original-job-document").open = false;
  importReview.hidden = true;
  readUploadButton.disabled = true;
  if (!file) { clearJobImport(); return; }
  importPanel.hidden = false;
  document.querySelector("#import-file-hint").textContent = isPdf
    ? "PDF with selectable text, up to 5 MB and 10 pages. The file is read on this server and is not saved. For a scanned PDF, add a photo or screenshot of the page instead."
    : "PNG, JPEG, or WebP, up to 5 MB. The image is read on this server and is not saved. Clear, upright images work best.";
  if (file.size > 5 * 1024 * 1024) {
    importStatus.textContent = `Choose ${isPdf ? "a PDF" : "an image"} no larger than 5 MB.`;
    return;
  }
  const media = file.type || ({ pdf: "application/pdf", png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp" })[file.name.split(".").pop().toLowerCase()];
  const allowed = isPdf ? ["application/pdf"] : ["image/png", "image/jpeg", "image/webp"];
  if (!allowed.includes(media)) {
    importStatus.textContent = isPdf ? "Choose a PDF file." : "Choose a PNG, JPEG, or WebP image.";
    return;
  }
  importController = new AbortController();
  importStatus.textContent = `Reading text from the ${source}… This may take a few seconds.`;
  readUploadButton.textContent = "Reading…";
  try {
    const response = await apiFetch(isPdf ? "/api/job-pdf" : "/api/job-image", {
      method: "POST", headers: { "Content-Type": media }, body: file, signal: importController.signal,
    });
    const body = await response.json().catch(() => null);
    if (revision !== importRevision || session !== sessionRevision) return;
    if (!response.ok) throw new Error(readErrorMessage(body, `This ${source} could not be read.`));
    selectedJobText = body.text;
    fullJobText = body.full_text ?? body.text;
    importText.value = selectedJobText;
    document.querySelector("#original-job-text").textContent = fullJobText;
    document.querySelector("#job-section-note").textContent = body.selection_applied
      ? "Suggested role sections are shown below. Clearly labelled company, benefits, or application sections were set aside. The full text is still available below."
      : "The full text is shown below because there were no clearly separate extra sections to remove. You can edit it before adding it.";
    document.querySelector("#job-section-actions").hidden = !body.selection_applied;
    importReview.hidden = false;
    importStatus.textContent = "Text found. Check and edit it below before adding it to the job description.";
  } catch (error) {
    if (revision !== importRevision || session !== sessionRevision || error.name === "AbortError") return;
    importStatus.textContent = error instanceof TypeError ? "Unable to reach the server. Try reading the upload again." : error.message;
  } finally {
    if (revision === importRevision) {
      importController = null;
      readUploadButton.disabled = false;
      readUploadButton.textContent = "Read upload again";
      if (session !== sessionRevision) importStatus.textContent = "Your session changed. Read the upload again to continue.";
    }
  }
}

addImageButton.addEventListener("click", () => jobImage.click());
addPdfButton.addEventListener("click", () => jobPdf.click());
for (const [input, kind] of [[jobImage, "image"], [jobPdf, "pdf"]]) {
  input.addEventListener("change", () => {
    if (!input.files[0]) return;
    jobUploadFile = input.files[0];
    jobUploadKind = kind;
    void readJobUpload();
  });
}
readUploadButton.addEventListener("click", () => void readJobUpload());
document.querySelector("#discard-job-upload").addEventListener("click", () => {
  const button = jobUploadKind === "pdf" ? addPdfButton : addImageButton;
  clearJobImport();
  button.focus();
});
for (const [id, full] of [["use-full-job-text", true], ["use-selected-job-text", false]]) {
  document.getElementById(id).addEventListener("click", () => {
    importText.value = full ? fullJobText : selectedJobText;
    importStatus.textContent = full ? "Full text copied to the review box. You can edit it before adding it." : "Suggested sections restored in the review box. Check them before adding.";
    importText.focus();
    importText.setSelectionRange(0, 0);
    importText.scrollTop = 0;
  });
}
document.querySelector("#apply-job-upload").addEventListener("click", () => {
  const text = importText.value.trim();
  if (!text) { importStatus.textContent = "Add some text to the review box first."; importText.focus(); return; }
  const existing = descriptionInput.value;
  const combined = existing ? `${existing}\n\n${text}` : text;
  if (combined.length > 50000) {
    importStatus.textContent = "The combined description is too long. Shorten it to 50,000 characters before adding this text.";
    return;
  }
  descriptionInput.value = combined;
  descriptionInput.dispatchEvent(new Event("input"));
  clearJobImport("Reviewed text added. Check the full description, then choose Analyze my fit when ready.");
  descriptionInput.focus();
});

function updateResumeControls() {
  savedResumePanel.hidden = !currentUser || !savedResume;
  document.querySelector("#saved-resume-info").textContent = savedResume
    ? `${savedResume.filename} · ${savedResume.pages} ${savedResume.pages === 1 ? "page" : "pages"} · Saved to your account`
    : "";
  saveResumeButton.hidden = !resumeCandidate || !currentUser;
  saveResumeButton.disabled = resumeBusy || !document.querySelector("#retry-saved-resume").hidden;
  saveResumeButton.textContent = savedResume ? "Replace saved résumé with this PDF" : "Save résumé to my account";
  document.querySelector("#resume-save-hint").textContent = currentUser
    ? "Keep one PDF in your account. You can replace or delete it at any time. Saving keeps the original PDF; edits to the skills below do not change it."
    : "Sign in to keep a résumé for your next visit.";
  resumeFile.disabled = resumeBusy;
  for (const id of ["use-saved-resume", "delete-resume", "retry-saved-resume", "confirm-delete-resume"]) {
    document.getElementById(id).disabled = resumeBusy;
  }
}

async function loadSavedResume() {
  if (!currentUser || resumeBusy) return;
  const session = sessionRevision;
  const operation = ++savedResumeRevision;
  resumeBusy = true;
  updateResumeControls();
  savedResumeStatus.textContent = "Checking for a saved résumé…";
  document.querySelector("#retry-saved-resume").hidden = true;
  try {
    const response = await apiFetch("/api/resume/saved", { cache: "no-store" });
    const body = await response.json().catch(() => null);
    if (session !== sessionRevision || operation !== savedResumeRevision) return;
    if (response.status === 401) { handleExpiredSession(); return; }
    if (!response.ok && response.status !== 404) throw new Error("We couldn't check your saved résumé.");
    savedResume = response.ok ? body : null;
    savedResumeStatus.textContent = savedResume ? "" : "No saved résumé yet. Upload a PDF below to get started.";
  } catch {
    if (session !== sessionRevision || operation !== savedResumeRevision) return;
    savedResumeStatus.textContent = "We couldn't check your saved résumé. Check again before saving a replacement.";
    document.querySelector("#retry-saved-resume").hidden = false;
  } finally {
    if (session === sessionRevision && operation === savedResumeRevision) {
      resumeBusy = false;
      updateResumeControls();
      // Avoid replacing a file the user has not been able to inspect.
      saveResumeButton.disabled = !document.querySelector("#retry-saved-resume").hidden;
    }
  }
}

document.querySelector("#retry-saved-resume").addEventListener("click", () => void loadSavedResume());

async function resumeAction(action) {
  if (!currentUser || resumeBusy) return;
  const file = resumeCandidate;
  if (action === "save" && (!file || !document.querySelector("#retry-saved-resume").hidden)) return;
  const session = sessionRevision;
  const operation = ++savedResumeRevision;
  const revision = ++resumeRevision;
  resumeBusy = true;
  updateResumeControls();
  savedResumeStatus.textContent = action === "save" ? "Saving résumé…" : action === "delete" ? "Deleting résumé…" : "Finding skills in your saved résumé…";
  const deleteError = document.querySelector("#delete-resume-error");
  deleteError.hidden = true;
  try {
    const url = action === "save" ? `/api/resume/saved?filename=${encodeURIComponent(file.name)}`
      : action === "use" ? `/api/resume/saved/skills?method=${extractionMethod.value}` : "/api/resume/saved";
    const response = await apiFetch(url, action === "save"
      ? { method: "PUT", headers: { "Content-Type": "application/pdf" }, body: file }
      : { method: action === "use" ? "POST" : "DELETE" });
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (session !== sessionRevision || operation !== savedResumeRevision || revision !== resumeRevision) return;
    if (response.status === 401) { handleExpiredSession(); return; }
    if (!response.ok && !(action === "delete" && response.status === 404)) {
      throw new Error(readErrorMessage(body, "We couldn't complete that request. Please try again."));
    }
    if (action === "save") {
      savedResume = body;
      resumeCandidate = null;
      savedResumeStatus.textContent = "Résumé saved. You can use it again on your next visit.";
    } else if (action === "use") {
      resumeCandidate = null;
      resumeFile.value = "";
      resumeSkills.value = body.skills.join("\n");
      renderResumeSpelling(body.spelling);
      resumeReview.hidden = false;
      resumeStatus.textContent = "Review these skills, then choose Add to my skills.";
      savedResumeStatus.textContent = "Skills loaded from your saved résumé.";
      resumeSkills.focus();
    } else {
      savedResume = null;
      resumeCandidate = null;
      resumeFile.value = "";
      resumeSkills.value = "";
      resumeReview.hidden = true;
      renderResumeSpelling([]);
      resumeStatus.textContent = "";
      savedResumeStatus.textContent = "Saved résumé deleted. Your analyses are unchanged.";
      resumeDeleteDialog.close();
    }
  } catch (error) {
    if (session !== sessionRevision || operation !== savedResumeRevision) return;
    const message = error instanceof TypeError ? "Unable to reach the server. Please try again." : error.message;
    savedResumeStatus.textContent = message;
    if (action === "delete") { deleteError.textContent = message; deleteError.hidden = false; }
  } finally {
    if (session === sessionRevision && operation === savedResumeRevision) {
      resumeBusy = false;
      updateResumeControls();
    }
  }
}

saveResumeButton.addEventListener("click", () => void resumeAction("save"));
document.querySelector("#use-saved-resume").addEventListener("click", () => void resumeAction("use"));
document.querySelector("#delete-resume").addEventListener("click", () => {
  document.querySelector("#delete-resume-error").hidden = true;
  resumeDeleteDialog.showModal();
});
document.querySelector("#cancel-delete-resume").addEventListener("click", () => resumeDeleteDialog.close());
document.querySelector("#confirm-delete-resume").addEventListener("click", () => void resumeAction("delete"));
resumeDeleteDialog.addEventListener("click", (event) => closeOnBackdrop(event, resumeDeleteDialog));

void restoreSession();
