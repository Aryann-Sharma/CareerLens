/* Private roadmap storage is separate from analysis history. */
class SavedRoadmaps {
  constructor(workspace, account) {
    this.workspace = workspace;
    this.account = account;
    this.userId = null;
    this.operation = 0;
    this.listRevision = 0;
    this.accountRevision = 0;
    this.page = 1;
    this.name = document.querySelector("#roadmap-name");
    this.saveButton = document.querySelector("#save-roadmap");
    this.status = document.querySelector("#roadmap-save-status");
    this.library = document.querySelector("#saved-roadmaps");
    this.list = document.querySelector("#saved-roadmaps-list");
    this.listStatus = document.querySelector("#saved-roadmaps-status");
    this.dialog = document.querySelector("#roadmap-action-dialog");
    this.confirm = document.querySelector("#confirm-roadmap-action");
    this.name.addEventListener("input", () => this.changed());
    this.saveButton.addEventListener("click", () => void this.save());
    document.querySelector("#refresh-roadmaps").addEventListener("click", () => void this.loadList(this.page));
    document.querySelector("#roadmaps-previous").addEventListener("click", () => void this.loadList(this.page - 1));
    document.querySelector("#roadmaps-next").addEventListener("click", () => void this.loadList(this.page + 1));
    document.querySelector("#cancel-roadmap-action").addEventListener("click", () => this.dialog.close());
    this.dialog.addEventListener("cancel", (event) => { if (this.deleting) event.preventDefault(); });
    this.dialog.addEventListener("close", () => { this.action = null; });
    this.confirm.addEventListener("click", () => {
      const action = this.action;
      if (!action || action.userId !== this.userId) return;
      if (action.kind === "open") {
        this.dialog.close();
        void this.open(action.item.id);
      } else void this.remove(action);
    });
    this.resetDraft();
  }

  cancelDraftRequests() {
    this.operation += 1;
    this.busy = false;
    this.renderControls();
  }

  resetDraft() {
    this.cancelDraftRequests();
    this.record = null;
    this.baseline = null;
    this.clientId = crypto.randomUUID();
    this.name.value = "";
    this.status.textContent = "";
    this.renderControls();
  }

  sessionChanged(user) {
    this.accountRevision += 1;
    this.cancelDraftRequests();
    this.listRevision += 1;
    this.userId = user?.id ?? null;
    this.library.hidden = !user;
    this.list.replaceChildren();
    this.listStatus.textContent = "";
    document.querySelector("#roadmap-pagination").hidden = true;
    if (this.dialog.open) this.dialog.close();
    this.action = null;
    this.deleting = null;
    document.querySelector("#cancel-roadmap-action").disabled = false;
    document.querySelector("#roadmap-action-title").textContent = "";
    document.querySelector("#roadmap-action-copy").textContent = "";
    document.querySelector("#roadmap-action-status").textContent = "";
    this.renderControls();
    if (user) {
      if (this.workspace.plan) this.changed();
      void this.loadList(1);
    }
  }

  state() {
    return { title: this.name.value.trim(), completed: [...this.workspace.completed].sort() };
  }

  dirty() {
    return Boolean(this.workspace.plan) && JSON.stringify(this.state()) !== this.baseline;
  }

  changed() {
    this.status.textContent = this.dirty()
      ? (this.record ? "Unsaved changes. Choose Save progress to keep them." : "Not saved. Save this roadmap to continue on another visit.")
      : "Saved to your account.";
    this.renderControls();
  }

  renderControls() {
    this.saveButton.textContent = this.busy ? "Saving…" : !this.userId ? "Sign in to save roadmap" : this.record ? "Save progress" : "Save roadmap";
    this.saveButton.disabled = this.busy || (Boolean(this.userId) && !this.dirty());
    this.name.disabled = this.busy;
    document.querySelectorAll("#learning-steps input").forEach((input) => { input.disabled = this.busy; });
  }

  async request(path, options = {}) {
    const accountRevision = this.accountRevision;
    const response = await fetch(path, { ...options, credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-Account-ID": String(this.userId), ...options.headers } });
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    if (accountRevision !== this.accountRevision) throw new Error("This request belongs to an earlier session.");
    if (response.status === 401 || body?.detail?.code === "account_changed") {
      this.account.expired();
      throw new Error("Please sign in again.");
    }
    if (options.method === "DELETE" && response.status === 404) return null;
    if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "This request could not be completed. Please retry.");
    return body;
  }

  async save() {
    if (!this.workspace.plan || this.busy) return;
    if (!this.userId) {
      this.status.textContent = "Sign in, then choose Save roadmap to keep this plan and its checked steps.";
      this.account.signIn();
      return;
    }
    const state = this.state();
    if (!state.title || state.title.length > 100) {
      this.status.textContent = "Give this roadmap a name of 1–100 characters.";
      this.name.focus();
      return;
    }
    const operation = ++this.operation;
    const userId = this.userId;
    const record = this.record;
    this.busy = true;
    this.status.textContent = "Saving your roadmap…";
    this.renderControls();
    try {
      const body = record ? { ...state, version: record.version }
        : { ...state, client_id: this.clientId, request: this.workspace.planRequest, plan_revision: this.workspace.plan.revision };
      const saved = await this.request(`/api/learning/saved${record ? `/${record.id}` : ""}`, {
        method: record ? "PUT" : "POST", body: JSON.stringify(body),
      });
      if (operation !== this.operation || userId !== this.userId) return;
      this.record = { id: saved.id, version: saved.version };
      this.baseline = JSON.stringify({ title: saved.title, completed: [...saved.completed].sort() });
      this.changed();
      void this.loadList(1);
    } catch (error) {
      if (operation === this.operation && userId === this.userId) {
        this.status.textContent = error instanceof TypeError ? "Unable to reach the server. Your progress is still here; try saving again." : error.message;
      }
    } finally {
      if (operation === this.operation && userId === this.userId) {
        this.busy = false;
        this.renderControls();
      }
    }
  }

  async loadList(page) {
    if (!this.userId) return;
    const revision = ++this.listRevision;
    const userId = this.userId;
    this.listStatus.textContent = "Loading saved roadmaps…";
    document.querySelector("#roadmap-pagination").hidden = true;
    try {
      const result = await this.request(`/api/learning/saved?page=${Math.max(1, page)}&page_size=5`);
      if (revision !== this.listRevision || userId !== this.userId) return;
      const pages = Math.max(1, Math.ceil(result.total / result.page_size));
      if (result.page > pages) { void this.loadList(pages); return; }
      this.page = result.page;
      this.list.replaceChildren();
      for (const item of result.items) {
        const row = this.workspace.node("article", undefined, "roadmap-row");
        const info = this.workspace.node("div");
        info.append(this.workspace.node("h3", item.title), this.workspace.node("p", `${item.completed_count} of ${item.total_count} practice steps checked`, "field-hint"));
        const actions = this.workspace.node("div", undefined, "resume-actions");
        const open = this.workspace.node("button", "Open roadmap", "secondary-button");
        open.type = "button";
        open.addEventListener("click", () => {
          if (this.dirty()) this.ask("open", item); else void this.open(item.id);
        });
        const remove = this.workspace.node("button", "Delete", "text-button danger-button");
        remove.type = "button";
        remove.setAttribute("aria-label", `Delete roadmap ${item.title}`);
        remove.addEventListener("click", () => this.ask("delete", item));
        actions.append(open, remove);
        row.append(info, actions);
        this.list.append(row);
      }
      this.listStatus.textContent = result.total ? `${result.total} saved ${result.total === 1 ? "roadmap" : "roadmaps"}.` : "No saved roadmaps yet. Build one from an analysis, then save it here.";
      document.querySelector("#roadmap-pagination").hidden = pages <= 1;
      document.querySelector("#roadmaps-page").textContent = `Page ${this.page} of ${pages}`;
      document.querySelector("#roadmaps-previous").disabled = this.page <= 1;
      document.querySelector("#roadmaps-next").disabled = this.page >= pages;
    } catch (error) {
      if (revision === this.listRevision && userId === this.userId) {
        this.listStatus.textContent = error instanceof TypeError ? "Saved roadmaps could not load. Use Refresh list to try again." : error.message;
      }
    }
  }

  ask(kind, item) {
    this.action = { kind, item, userId: this.userId };
    document.querySelector("#roadmap-action-title").textContent = kind === "delete" ? "Delete this roadmap?" : "Open another roadmap?";
    document.querySelector("#roadmap-action-copy").textContent = kind === "delete"
      ? `This permanently removes “${item.title}” and its saved progress. Your analyses will stay in your history.`
      : `Opening “${item.title}” replaces the current roadmap. Save or download your unsaved changes first if you want to keep them.`;
    document.querySelector("#roadmap-action-status").textContent = "";
    this.confirm.textContent = kind === "delete" ? "Delete roadmap" : "Discard changes and open";
    this.confirm.disabled = false;
    this.dialog.showModal();
  }

  async open(id) {
    const operation = ++this.operation;
    const userId = this.userId;
    try {
      const saved = await this.request(`/api/learning/saved/${id}`);
      if (operation !== this.operation || userId !== this.userId) return;
      this.workspace.clear();
      this.record = { id: saved.id, version: saved.version };
      this.workspace.plan = saved.plan;
      this.workspace.completed = new Set(saved.completed);
      this.name.value = saved.title;
      this.baseline = JSON.stringify({ title: saved.title, completed: [...saved.completed].sort() });
      this.workspace.panel.hidden = false;
      document.querySelector(".learning-controls").hidden = true;
      this.workspace.renderPlan();
      this.changed();
      this.name.focus({ preventScroll: true });
      this.workspace.panel.scrollIntoView({ block: "start" });
    } catch (error) {
      if (operation === this.operation && userId === this.userId) {
        this.listStatus.textContent = error instanceof TypeError ? "This roadmap could not load. Try opening it again." : error.message;
      }
    }
  }

  async remove(action) {
    if (this.confirm.disabled) return;
    this.confirm.disabled = true;
    this.deleting = action;
    document.querySelector("#cancel-roadmap-action").disabled = true;
    try {
      await this.request(`/api/learning/saved/${action.item.id}?version=${action.item.version}`, { method: "DELETE" });
      if (this.action !== action || action.userId !== this.userId) return;
      this.dialog.close();
      if (this.record?.id === action.item.id) this.workspace.clear();
      void this.loadList(this.page);
    } catch (error) {
      if (this.action === action && action.userId === this.userId) {
        document.querySelector("#roadmap-action-status").textContent = error instanceof TypeError ? "Unable to delete the roadmap. Please retry." : error.message;
      }
    } finally {
      if (this.deleting === action) {
        this.deleting = null;
        document.querySelector("#cancel-roadmap-action").disabled = false;
      }
      if (this.action === action) this.confirm.disabled = false;
    }
  }
}
