import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect

from backend.tests.pdf_fixtures import make_pdf
from e2e.test_feature_flows import register, create_analysis


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
@pytest.mark.parametrize("text,expected", [
    ("Skills to build\na\nteam worker\ndiligent", ["team worker", "diligent"]),
    ("a diligent team worker", ["diligent", "team worker"]),
    ("we want a diligent team worker, who is also very passionate and a hard-worker.",
     ["diligent", "team worker", "passionate", "hard-worker"]),
])
def test_complete_short_skill_phrases_are_shown_and_scored(page: Page, app_url: str, text, expected):
    page.goto(app_url)
    page.locator("#job-description").fill(text)
    page.locator("#analyze-button").click()
    expect(page.locator("#missing-skills .chip")).to_have_text(expected, timeout=30000)
    expect(page.locator("#missing-count")).to_have_text(str(len(expected)))
    page.locator("#skill-review summary").click()
    expect(page.locator("#source-evidence mark")).to_have_text(expected)
    expect(page.locator("#reviewed-skills")).to_have_value("\n".join(expected))
    page.locator("#user-skills").fill("team worker")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text(f"{round(100 / len(expected))}%")
    expect(page.locator("#matched-skills .chip")).to_have_text(["team worker"])
    expect(page.locator("#missing-skills .chip")).to_have_text([skill for skill in expected if skill != "team worker"])


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
def test_filler_prediction_is_not_displayed_or_scored(page: Page, app_url: str):
    page.goto(app_url)
    page.locator("#job-description").fill("be a team worker, and be diligent")
    page.locator("#analyze-button").click()
    expect(page.locator("#missing-skills .chip")).to_have_text(["team worker", "diligent"], timeout=30000)
    expect(page.locator("#missing-count")).to_have_text("2")
    page.locator("#skill-review summary").click()
    expect(page.locator("#reviewed-skills")).to_have_value("team worker\ndiligent")
    expect(page.locator("#source-evidence mark")).to_have_text(["team worker", "diligent"])
    page.locator("#user-skills").fill("team worker")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("50%")
    expect(page.locator("#missing-skills .chip")).to_have_text(["diligent"])


def test_guest_can_review_predictions_and_recalculate_from_original_input(page: Page, app_url: str):
    page.goto(app_url)
    text = "🧭 Python and stakeholder communication <b>required</b>"
    response = {"extracted_skills": ["Python", "stakeholder communication"], "matched_skills": ["Python"],
                "missing_skills": ["stakeholder communication"], "match_score": 50,
                "extraction_details": {"method": "trained", "model": "test", "revision": "test",
                    "spans": [{"text": "stakeholder communication", "label": "skill", "start": 13, "end": 38}]}}
    page.route("**/api/preview", lambda route: route.fulfill(json=response))
    page.locator("#job-description").fill(text)
    page.locator("#user-skills").fill("Python")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("50%")
    page.locator("#skill-review summary").click()
    expect(page.locator("#source-evidence mark")).to_have_text("stakeholder communication")
    expect(page.locator("#source-evidence b")).to_have_count(0)
    page.unroute("**/api/preview")
    page.locator("#reviewed-skills").fill("Python")
    page.locator("#job-description").fill("Unrelated changed draft")
    page.locator("#user-skills").fill("Java")
    page.locator("#update-analysis").click()
    expect(page.locator("#match-score")).to_have_text("100%")
    expect(page.locator("#source-evidence")).to_have_text(text)
    expect(page.locator("#extraction-method-note")).to_contain_text("your corrections")
    expect(page.locator("#save-analysis")).to_be_enabled()


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_pdf_import_review_and_layout(page: Page, app_url: str, width: int):
    page.set_viewport_size({"width": width, "height": 950})
    page.goto(app_url)
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#user-skills").fill("Java")
    page.locator(".resume-upload summary").click()
    page.locator("#resume-file").set_input_files({"name": "resume.pdf", "mimeType": "application/pdf", "buffer": make_pdf()})
    expect(page.locator("#resume-review")).to_be_visible()
    expect(page.locator("#user-skills")).to_have_value("Java")
    page.locator("#resume-skills").fill("Python\nGit\nPython")
    page.locator("#apply-resume").click()
    expect(page.locator("#user-skills")).to_have_value("Java, Python, Git")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if width == 320:
        Path(".review-tests").mkdir(exist_ok=True)
        page.screenshot(path=".review-tests/resume-mobile.png", full_page=True)


def test_pdf_error_and_late_response_after_logout(page: Page, app_url: str):
    register(page, app_url)
    page.locator(".resume-upload summary").click()
    page.locator("#resume-file").set_input_files({"name": "invalid.pdf", "mimeType": "application/pdf", "buffer": b"invalid"})
    expect(page.locator("#resume-status")).to_contain_text("valid PDF")
    pending: list[Route] = []
    page.route("**/api/resume?*", lambda route: pending.append(route))
    page.locator("#resume-file").set_input_files({"name": "resume.pdf", "mimeType": "application/pdf", "buffer": make_pdf()})
    expect(page.locator("#resume-status")).to_contain_text("Reading")
    page.locator("#logout-button").click()
    expect(page.locator("#signed-out-actions")).to_be_visible()
    assert len(pending) == 1
    pending[0].fulfill(json={"pages": 1, "skills": ["private phrase"]})
    page.wait_for_load_state("networkidle")
    expect(page.locator("#resume-review")).to_be_hidden()
    expect(page.locator("#resume-skills")).to_have_value("")


def test_delete_cancel_failure_and_last_page_recovery(page: Page, app_url: str):
    register(page, app_url)
    for index in range(6):
        create_analysis(page, app_url, f"Python role {index}")
    page.reload()
    page.locator("#history-next").click()
    expect(page.locator(".history-card")).to_have_count(1)
    page.get_by_role("button", name="Delete", exact=True).click()
    page.locator("#cancel-delete").click()
    expect(page.locator(".history-card")).to_have_count(1)
    page.route("**/api/analyses/*", lambda route: route.abort() if route.request.method == "DELETE" else route.continue_())
    page.get_by_role("button", name="Delete", exact=True).click()
    page.locator("#confirm-delete").click()
    expect(page.locator("#delete-error")).to_contain_text("Unable to reach")
    expect(page.locator("#confirm-delete")).to_be_enabled()
    page.unroute("**/api/analyses/*")
    page.locator("#confirm-delete").click()
    expect(page.locator("#delete-dialog")).to_be_hidden()
    expect(page.locator(".history-card")).to_have_count(5)
    expect(page.locator("#history-pagination")).to_be_hidden()


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
def test_real_contextual_analysis_and_pdf(page: Page, app_url: str):
    page.goto(app_url)
    page.locator("#job-description").fill("Experience with Python and SQL. Excellent communication skills.")
    page.locator("#user-skills").fill("Python, SQL")
    page.locator("#analyze-button").click()
    expect(page.locator("#results-content")).to_be_visible(timeout=30000)
    page.locator("#skill-review summary").click()
    expect(page.locator("#extraction-method-note")).to_contain_text("Skills found using the wording")
    assert page.locator("#source-evidence mark").count() > 0
    page.locator(".resume-upload summary").click()
    page.locator("#resume-file").set_input_files({"name": "resume.pdf", "mimeType": "application/pdf", "buffer": make_pdf("Experience with Python and SQL. Excellent communication skills.")})
    expect(page.locator("#resume-review")).to_be_visible(timeout=30000)
    assert "Python" in page.locator("#resume-skills").input_value()
    Path(".review-tests").mkdir(exist_ok=True)
    page.screenshot(path=".review-tests/contextual-desktop.png", full_page=True)
