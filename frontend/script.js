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
