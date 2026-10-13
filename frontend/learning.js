/* Learning plans are page-local. They never modify the analysis or profile. */
class LearningWorkspace {
  constructor() {
    this.panel = document.querySelector("#learning-workspace");
    this.direction = document.querySelector("#learning-direction");
    this.status = document.querySelector("#learning-status");
    this.buildButton = document.querySelector("#build-learning-plan");
    this.dialog = document.querySelector("#learning-dialog");
    this.content = document.querySelector("#learning-guide-content");
    this.revision = 0;
    this.guideRevision = 0;
    this.directions = null;
    this.completed = new Set();
    this.buildButton.addEventListener("click", () => void this.build());
    document.querySelector("#download-learning-plan").addEventListener("click", () => this.download());
    document.querySelector("#close-learning-dialog").addEventListener("click", () => this.dialog.close());
    this.dialog.addEventListener("close", () => {
      this.guideRevision += 1;
      this.guideController?.abort();
    });
    this.direction.addEventListener("change", () => {
      this.status.textContent = "Choose Build roadmap to use this direction. An existing checklist stays unchanged until you rebuild.";
    });
  }

  node(tag, text, className) {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  }

  pause() {
    this.revision += 1;
    this.controller?.abort();
    this.guideRevision += 1;
    this.guideController?.abort();
    if (this.dialog.open) this.dialog.close();
    this.panel.hidden = true;
    this.buildButton.disabled = false;
    this.buildButton.textContent = this.plan ? "Rebuild roadmap (resets progress)" : "Build roadmap";
  }

  clear() {
    this.pause();
    this.snapshot = null;
    this.plan = null;
    this.completed.clear();
    this.direction.value = "";
    this.content.replaceChildren();
    document.querySelector("#learning-dialog-title").textContent = "Learning guide";
    document.querySelector("#learning-steps").replaceChildren();
    document.querySelector("#learning-plan-title").textContent = "";
    document.querySelector("#learning-notice").textContent = "";
    document.querySelector("#learning-progress").textContent = "";
    document.querySelector("#learning-plan").hidden = true;
    this.status.textContent = "";
    this.buildButton.textContent = "Build roadmap";
  }

  setAnalysis(analysis) {
    this.clear();
    this.snapshot = analysis;
    this.panel.hidden = false;
    void this.loadDirections();
  }

  async loadDirections() {
    if (this.directions) return;
    const revision = this.revision;
    try {
      const response = await fetch("/api/learning/directions");
      if (!response.ok) throw new Error();
      const body = await response.json();
      if (revision !== this.revision) return;
      this.directions = body;
      for (const [id, value] of Object.entries(body)) {
        const option = this.node("option", value.title);
        option.value = id;
        this.direction.append(option);
      }
    } catch {
      if (revision === this.revision) this.status.textContent = "Learning directions could not load. You can still build from your analysis; building will also retry loading directions.";
    }
  }

  async build() {
    if (!this.snapshot || this.buildButton.disabled) return;
    const revision = ++this.revision;
    this.controller?.abort();
    this.controller = new AbortController();
    this.buildButton.disabled = true;
    this.buildButton.textContent = "Building…";
    this.status.textContent = "";
    void this.loadDirections();
    try {
      const response = await fetch("/api/learning/plan", {
        method: "POST", headers: { "Content-Type": "application/json" }, signal: this.controller.signal,
        body: JSON.stringify({ missing_skills: this.snapshot.result.missing_skills,
          user_skills: this.snapshot.request.user_skills, direction: this.direction.value || null }),
      });
      if (!response.ok) throw new Error("The roadmap could not be built. Please try again.");
      const body = await response.json();
      if (revision !== this.revision) return;
      this.plan = body;
      this.completed.clear();
      this.renderPlan();
      this.status.textContent = body.steps.length
        ? "Roadmap ready. Work through the practice steps at your own pace."
        : "No remaining steps in this plan. Choose a direction to explore something new.";
    } catch (error) {
      if (revision !== this.revision || error.name === "AbortError") return;
      this.status.textContent = error instanceof TypeError ? "Unable to reach the server. Please try again." : error.message;
    } finally {
      if (revision === this.revision) {
        this.buildButton.disabled = false;
        this.buildButton.textContent = this.plan ? "Rebuild roadmap (resets progress)" : "Build roadmap";
      }
    }
  }

  renderPlan() {
    const list = document.querySelector("#learning-steps");
    list.replaceChildren();
    document.querySelector("#learning-plan").hidden = false;
    document.querySelector("#learning-plan-title").textContent = this.directions?.[this.plan.direction]?.title || "Skills from your analysis";
    document.querySelector("#learning-notice").textContent = this.plan.notice;
    for (const [index, step] of this.plan.steps.entries()) {
      const item = this.node("li", undefined, "learning-card");
      item.append(this.node("p", step.reason, "learning-reason"));
      const heading = this.node("h4");
      const button = this.node("button", step.skill, "text-button learning-skill");
      button.type = "button";
      button.setAttribute("aria-label", `Learning guide for ${step.skill}`);
      button.addEventListener("click", () => void this.openGuide(step.skill));
      heading.append(button);
      item.append(heading, this.node("p", step.goal));
      if (!step.available) item.append(this.node("p", step.note, "field-hint"));
      for (const [number, text] of step.milestones.entries()) {
        const label = this.node("label", undefined, "milestone-check");
        const input = this.node("input");
        input.type = "checkbox";
        const key = `${index}:${number}`;
        input.addEventListener("change", () => {
          if (input.checked) this.completed.add(key); else this.completed.delete(key);
          this.updateProgress();
        });
        label.append(input, this.node("span", text));
        item.append(label);
      }
      item.append(this.node("p", `Practice project: ${step.project}`, "learning-project"));
      list.append(item);
    }
    this.updateProgress();
  }

  updateProgress() {
    const total = this.plan.steps.reduce((sum, step) => sum + step.milestones.length, 0);
    document.querySelector("#learning-progress").textContent = total
      ? `${this.completed.size} of ${total} practice steps checked. This records practice, not proficiency.`
      : "No remaining steps. Choose a direction if you want to explore more skills.";
  }

  async openGuide(skill) {
    const revision = ++this.guideRevision;
    this.guideController?.abort();
    this.guideController = new AbortController();
    document.querySelector("#learning-dialog-title").textContent = `Learn ${skill}`;
    this.content.replaceChildren(this.node("p", "Loading learning guide…"));
    if (!this.dialog.open) this.dialog.showModal();
    try {
      const response = await fetch(`/api/learning/guide?skill=${encodeURIComponent(skill)}`, { signal: this.guideController.signal });
      if (!response.ok) throw new Error();
      const body = await response.json();
      if (revision !== this.guideRevision || !this.dialog.open) return;
      this.content.replaceChildren(this.node("p", body.goal));
      if (body.prerequisites.length) this.content.append(this.node("p", `Suggested foundations: ${body.prerequisites.join(", ")}. Skip these if you already know them.`, "field-hint"));
      if (body.note) this.content.append(this.node("p", body.note, "field-hint"));
      for (const suggestion of body.suggestions || []) {
        const button = this.node("button", `Did you mean ${suggestion}? View its guide`, "text-button");
        button.type = "button";
        button.addEventListener("click", () => void this.openGuide(suggestion));
        this.content.append(button);
      }
      this.content.append(this.node("h3", "Practice steps"));
      const list = this.node("ol");
      body.milestones.forEach((text) => list.append(this.node("li", text)));
      this.content.append(list, this.node("h3", "Build something"), this.node("p", body.project));
      if (body.resources.length) {
        this.content.append(this.node("h3", "Learning resources"));
        for (const resource of body.resources) {
          const link = this.node("a", `${resource.title} ↗`);
          const url = new URL(resource.url);
          if (url.protocol !== "https:") continue;
          link.href = url.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          this.content.append(link);
        }
        this.content.append(this.node("p", `Free reading resources, checked ${body.checked_on}. Optional services, certificates, or hosting may cost extra.`, "field-hint"));
      }
    } catch (error) {
      if (revision !== this.guideRevision || error.name === "AbortError") return;
      const retry = this.node("button", "Retry learning guide", "secondary-button");
      retry.type = "button";
      retry.addEventListener("click", () => void this.openGuide(skill));
      this.content.replaceChildren(this.node("p", "The guide could not load. Your analysis has not changed."), retry);
    }
  }

  download() {
    if (!this.plan) return;
    const lines = ["CareerLens learning checklist", document.querySelector("#learning-plan-title").textContent,
      this.plan.notice, "Progress is self-reported practice, not proof of proficiency.", ""];
    this.plan.steps.forEach((step, index) => {
      lines.push(`${index + 1}. ${step.skill} — ${step.reason}`, step.goal);
      step.milestones.forEach((text, number) => lines.push(`[${this.completed.has(`${index}:${number}`) ? "x" : " "}] ${text}`));
      lines.push(`Practice project: ${step.project}`);
      if (step.note) lines.push(step.note);
      step.resources.forEach((resource) => lines.push(`${resource.title}: ${resource.url}`));
      if (step.checked_on) lines.push(`Resources checked: ${step.checked_on}`);
      lines.push("");
    });
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" }));
    const link = this.node("a");
    link.href = url;
    link.download = "careerlens-learning-checklist.txt";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
