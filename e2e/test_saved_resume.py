from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect

from backend.tests.pdf_fixtures import make_pdf
from e2e.test_feature_flows import register


def open_resume(page: Page):
    page.locator("#extraction-method").select_option("catalog")
    page.locator(".resume-upload summary").click()
    expect(page.locator("#resume-file")).to_be_enabled()


def upload(page: Page, name="resume.pdf", text="Python SQL"):
    page.locator("#resume-file").set_input_files({"name": name, "mimeType": "application/pdf", "buffer": make_pdf(text)})
    expect(page.locator("#resume-review")).to_be_visible()


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_saved_resume_lifecycle_and_layout(page: Page, app_url: str, width: int):
    page.set_viewport_size({"width": width, "height": 950})
    register(page, app_url)
    open_resume(page)
    upload(page, "my-résumé.pdf")
    page.locator("#save-resume").click()
    expect(page.locator("#saved-resume-info")).to_contain_text("my-résumé.pdf")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    Path(".review-tests").mkdir(exist_ok=True)
    page.screenshot(path=f".review-tests/saved-resume-{width}.png", full_page=True)
    with page.expect_download() as download:
        page.locator("#download-resume").click()
    assert download.value.suggested_filename == "my-résumé.pdf"
    assert Path(download.value.path()).read_bytes() == make_pdf("Python SQL")
    page.reload()
    open_resume(page)
    page.locator("#user-skills").fill("Java")
    page.locator("#use-saved-resume").click()
    expect(page.locator("#resume-skills")).to_have_value("Python\nSQL")
    expect(page.locator("#user-skills")).to_have_value("Java")
    page.locator("#apply-resume").click()
    expect(page.locator("#user-skills")).to_have_value("Java, Python, SQL")
    upload(page, "updated.pdf", "Git")
    expect(page.locator("#save-resume")).to_have_text("Replace saved résumé with this PDF")
    page.locator("#save-resume").click()
    expect(page.locator("#saved-resume-info")).to_contain_text("updated.pdf")
    page.locator("#delete-resume").click()
    page.locator("#cancel-delete-resume").click()
    expect(page.locator("#saved-resume")).to_be_visible()
    page.locator("#delete-resume").click()
    page.locator("#confirm-delete-resume").click()
    expect(page.locator("#delete-resume-dialog")).to_be_hidden()
    expect(page.locator("#saved-resume")).to_be_hidden()
    page.reload()
    open_resume(page)
    expect(page.locator("#saved-resume-status")).to_contain_text("No saved résumé")


def test_guest_upload_can_be_saved_after_sign_in(page: Page, app_url: str):
    page.goto(app_url)
    expect(page.locator("#signed-out-actions")).to_be_visible()
    open_resume(page)
    upload(page)
    expect(page.locator("#save-resume")).to_be_hidden()
    page.locator("#open-register").click()
    from uuid import uuid4
    page.locator("#auth-email").fill(f"resume-{uuid4().hex}@example.com")
    page.locator("#auth-password").fill("Test-password-27")
    page.locator("#auth-submit").click()
    expect(page.locator("#save-resume")).to_be_enabled()
    page.locator("#save-resume").click()
    expect(page.locator("#saved-resume")).to_be_visible()


@pytest.mark.parametrize("action", ["save", "use", "delete"])
def test_resume_failure_can_be_retried(page: Page, app_url: str, action: str):
    register(page, app_url)
    open_resume(page)
    upload(page)
    if action != "save":
        page.locator("#save-resume").click()
        expect(page.locator("#saved-resume")).to_be_visible()
    pattern = "**/api/resume/saved**"
    page.route(pattern, lambda route: route.abort())
    selector = {"save": "#save-resume", "use": "#use-saved-resume", "delete": "#confirm-delete-resume"}[action]
    if action == "delete": page.locator("#delete-resume").click()
    page.locator(selector).click()
    expect(page.locator("#saved-resume-status")).to_contain_text("Unable to reach")
    expect(page.locator(selector)).to_be_enabled()
    page.unroute(pattern)
    page.locator(selector).click()
    expect(page.locator("#saved-resume-status")).to_contain_text({"save": "Résumé saved", "use": "Skills loaded", "delete": "Saved résumé deleted"}[action])


@pytest.mark.parametrize("action", ["metadata", "save", "use"])
def test_late_resume_response_after_logout_is_ignored(page: Page, app_url: str, action: str):
    register(page, app_url)
    open_resume(page)
    upload(page)
    if action == "use":
        page.locator("#save-resume").click()
        expect(page.locator("#saved-resume")).to_be_visible()
    pending: list[Route] = []
    page.route("**/api/resume/saved**", lambda route: pending.append(route))
    if action == "metadata":
        page.reload()
        expect(page.locator("#current-user-email")).not_to_have_text("")
    else:
        page.locator("#save-resume" if action == "save" else "#use-saved-resume").click()
    expect(page.locator("#resume-file")).to_be_disabled()
    page.locator("#logout-button").click()
    expect(page.locator("#signed-out-actions")).to_be_visible()
    assert len(pending) == 1
    pending[0].fulfill(json={"filename": "private.pdf", "pages": 1, "skills": ["private skill"]})
    page.wait_for_load_state("networkidle")
    expect(page.locator("#saved-resume")).to_be_hidden()
    expect(page.locator("#saved-resume-info")).to_have_text("")
    expect(page.locator("#resume-skills")).to_have_value("")
    expect(page.locator("#resume-file")).to_be_enabled()


def test_failed_metadata_does_not_silently_replace_saved_file(page: Page, app_url: str):
    page.route("**/api/resume/saved", lambda route: route.abort())
    register(page, app_url)
    open_resume(page)
    upload(page)
    expect(page.locator("#retry-saved-resume")).to_be_visible()
    expect(page.locator("#save-resume")).to_be_disabled()
    page.unroute("**/api/resume/saved")
    page.locator("#retry-saved-resume").click()
    expect(page.locator("#save-resume")).to_be_enabled()


def test_plain_language_and_integrated_review(page: Page, app_url: str):
    page.goto(app_url)
    expect(page.locator("#extraction-method option:checked")).to_have_text("Find skills in context")
    expect(page.locator("#matching-method option:checked")).to_have_text("Include similar wording")
    expect(page.locator("#extraction-preview")).to_have_count(0)
    assert "Experimental" not in page.locator("body").inner_text()
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#matching-method").select_option("exact")
    page.locator("#job-description").fill("Python and SQL")
    page.locator("#user-skills").fill("Python")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("50%")
    page.get_by_text("Review the skills found", exact=True).click()
    expect(page.locator("#source-evidence")).to_have_text("Python and SQL")
    page.locator("#reviewed-skills").fill("Python")
    page.locator("#update-analysis").click()
    expect(page.locator("#match-score")).to_have_text("100%")
