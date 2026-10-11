from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect

from backend.tests.pdf_fixtures import make_pdf
from backend.tests.test_job_document import POSTING
from e2e.test_job_image import upload as upload_image
from e2e.test_feature_flows import register


def upload_pdf(page: Page, content=None):
    with page.expect_file_chooser() as chooser:
        page.get_by_role("button", name="Attach PDF", exact=True).click()
    chooser.value.set_files({"name": "job.pdf", "mimeType": "application/pdf", "buffer": make_pdf(POSTING) if content is None else content})


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_pdf_selects_role_sections_with_original_and_editable_combined_text(page: Page, app_url: str, width: int):
    page.set_viewport_size({"width": width, "height": 1000})
    page.goto(app_url)
    page.locator("#job-description").fill("Additional requirements: Linux.")
    upload_pdf(page)
    expect(page.locator("#job-import-review")).to_be_visible()
    selected = page.locator("#job-import-text").input_value()
    assert "Docker" in selected and "Java" not in selected and "React" not in selected
    expect(page.locator("#job-section-note")).to_contain_text("set aside")
    expect(page.locator("#import-warning")).to_contain_text("may also miss relevant details")
    page.locator("#original-job-document summary").click()
    expect(page.locator("#original-job-text")).to_contain_text("Java training")
    page.locator("#use-full-job-text").click()
    assert "Java training" in page.locator("#job-import-text").input_value()
    page.locator("#use-selected-job-text").click()
    expect(page.locator("#job-import-text")).to_have_value(selected)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    Path(".review-tests").mkdir(exist_ok=True)
    page.locator("#job-import").screenshot(path=f".review-tests/job-pdf-{width}.png")
    page.locator("#apply-job-upload").click()
    expect(page.locator("#job-description")).to_have_value("Additional requirements: Linux.\n\n" + selected)
    expect(page.locator("#results-content")).to_be_hidden()
    page.locator("#job-description").fill(page.locator("#job-description").input_value() + "\nHTML is helpful.")
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#matching-method").select_option("exact")
    page.locator("#user-skills").fill("Python, SQL, Git, Docker, Linux, HTML")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("100%")
    expect(page.locator("#missing-count")).to_have_text("0")


@pytest.mark.parametrize("content,message", [(b"bad", "valid PDF"), (make_pdf(text=""), "Scanned PDFs"), (make_pdf(encrypted=True), "password protected")], ids=["invalid", "scanned", "encrypted"])
def test_pdf_errors_keep_draft_and_allow_a_new_upload(page: Page, app_url: str, content, message):
    page.goto(app_url)
    page.locator("#job-description").fill("My draft")
    upload_pdf(page, content)
    expect(page.locator("#job-import-status")).to_contain_text(message)
    expect(page.locator("#job-description")).to_have_value("My draft")
    upload_pdf(page, make_pdf("Python"))
    expect(page.locator("#job-import-text")).to_have_value("Python")
    expect(page.locator("#job-section-note")).to_contain_text("full text is shown")
    page.locator("#discard-job-upload").click()
    expect(page.locator("#add-job-pdf")).to_be_focused()
    expect(page.locator("#job-description")).to_have_value("My draft")


def test_pdf_and_photo_append_to_the_same_description(page: Page, app_url: str):
    page.goto(app_url)
    upload_pdf(page, make_pdf("Python"))
    expect(page.locator("#job-import-text")).to_have_value("Python")
    page.locator("#apply-job-upload").click()
    page.route("**/api/job-image", lambda route: route.fulfill(json={"text": "SQL"}))
    upload_image(page)
    expect(page.locator("#job-import-text")).to_have_value("SQL")
    page.locator("#apply-job-upload").click()
    expect(page.locator("#job-description")).to_have_value("Python\n\nSQL")


def test_switching_to_pdf_ignores_late_image_and_logout_clears_original(page: Page, app_url: str):
    register(page, app_url)
    pending: list[Route] = []
    def hold(route: Route):
        pending.append(route)
        page.evaluate("window.imageWaiting = true")
    page.route("**/api/job-image", hold)
    upload_image(page)
    page.wait_for_function("window.imageWaiting === true")
    upload_pdf(page)
    expect(page.locator("#job-section-note")).to_contain_text("set aside")
    selected = page.locator("#job-import-text").input_value()
    pending[0].fulfill(json={"text": "Old image text"})
    page.wait_for_load_state("networkidle")
    expect(page.locator("#job-import-text")).to_have_value(selected)
    page.locator("#logout-button").click()
    expect(page.locator("#signed-out-actions")).to_be_visible()
    expect(page.locator("#original-job-text")).to_be_empty()
    expect(page.locator("#job-import-text")).to_have_value("")
    expect(page.locator("#job-import")).to_be_hidden()


def test_original_pdf_text_is_literal_and_retry_handles_network_failure(page: Page, app_url: str):
    page.goto(app_url)
    page.route("**/api/job-pdf", lambda route: route.abort())
    upload_pdf(page)
    expect(page.locator("#job-import-status")).to_contain_text("Unable to reach")
    page.unroute("**/api/job-pdf")
    text = '<img src=x onerror="window.injected=true"> Python'
    page.route("**/api/job-pdf", lambda route: route.fulfill(json={"text": "Python", "full_text": text, "selection_applied": True}))
    page.locator("#read-job-upload").click()
    expect(page.locator("#job-import-review")).to_be_visible()
    page.locator("#original-job-document summary").click()
    expect(page.locator("#original-job-text")).to_have_text(text)
    assert page.evaluate("window.injected !== true")
