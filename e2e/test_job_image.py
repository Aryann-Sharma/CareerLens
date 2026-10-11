from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect

from backend.tests.image_fixtures import make_image
from e2e.test_feature_flows import register


def upload(page: Page, content=None, name="job.png", media="image/png"):
    with page.expect_file_chooser() as chooser:
        page.get_by_role("button", name="Add a photo or screenshot").click()
    chooser.value.set_files({"name": name, "mimeType": media, "buffer": make_image() if content is None else content})


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_photo_text_requires_review_and_preserves_typed_description(page: Page, app_url: str, width: int):
    page.set_viewport_size({"width": width, "height": 950})
    page.goto(app_url)
    page.locator("#job-description").fill("Existing requirements")
    upload(page)
    expect(page.locator("#job-import-review")).to_be_visible(timeout=30000)
    assert "Python" in page.locator("#job-import-text").input_value()
    expect(page.locator("#job-description")).to_have_value("Existing requirements")
    expect(page.locator("#results-content")).to_be_hidden()
    expect(page.locator("#import-warning")).to_contain_text("mistakes or miss lines")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if width == 320:
        Path(".review-tests").mkdir(exist_ok=True)
        page.locator("#job-import").screenshot(path=".review-tests/job-image-mobile.png")
    page.locator("#job-import-text").fill("Python and SQL")
    # Preserve edits made in the main description while reviewing the photo.
    page.locator("#job-description").fill("Updated requirements")
    page.locator("#apply-job-upload").click()
    expect(page.locator("#job-description")).to_have_value("Updated requirements\n\nPython and SQL")
    expect(page.locator("#job-import-review")).to_be_hidden()
    expect(page.locator("#job-import")).to_be_hidden()
    expect(page.locator("#job-description")).to_be_focused()
    page.locator("#job-description").fill("Updated requirements\n\nPython and SQL\nGit is helpful.")
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#user-skills").fill("Python, SQL, Git")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("100%")


@pytest.mark.parametrize("failure", ["invalid", "network", "busy"])
def test_image_failure_can_be_retried_without_losing_draft(page: Page, app_url: str, failure: str):
    page.goto(app_url)
    page.locator("#job-description").fill("My existing text")
    if failure == "network": page.route("**/api/job-image", lambda route: route.abort())
    if failure == "busy": page.route("**/api/job-image", lambda route: route.fulfill(status=503, json={"detail": "Image reading is busy. Please try again shortly."}))
    upload(page, b"invalid" if failure == "invalid" else None)
    expect(page.locator("#job-import-status")).to_contain_text({"invalid": "could not be read", "network": "Unable to reach", "busy": "busy"}[failure])
    expect(page.locator("#read-job-upload")).to_be_enabled()
    expect(page.locator("#job-description")).to_have_value("My existing text")
    page.unroute("**/api/job-image")
    if failure == "invalid": upload(page)
    else: page.locator("#read-job-upload").click()
    expect(page.locator("#job-import-review")).to_be_visible(timeout=30000)


def test_image_review_can_be_discarded_and_cannot_exceed_text_limit(page: Page, app_url: str):
    page.goto(app_url)
    page.route("**/api/job-image", lambda route: route.fulfill(json={"text": "Python"}))
    upload(page)
    expect(page.locator("#job-import-review")).to_be_visible()
    page.locator("#job-import-text").fill(" ")
    page.locator("#apply-job-upload").click()
    expect(page.locator("#job-import-status")).to_contain_text("Add some text")
    page.locator("#job-description").fill("x" * 49999)
    page.locator("#job-import-text").fill("Python")
    page.locator("#apply-job-upload").click()
    expect(page.locator("#job-import-status")).to_contain_text("too long")
    expect(page.locator("#job-description")).to_have_value("x" * 49999)
    page.locator("#discard-job-upload").click()
    expect(page.locator("#job-import-text")).to_have_value("")
    expect(page.locator("#job-import-review")).to_be_hidden()


def test_changing_image_and_logging_out_cannot_restore_old_text(page: Page, app_url: str):
    register(page, app_url)
    pending: list[Route] = []
    def intercept(route: Route):
        pending.append(route)
        page.evaluate("count => { window.interceptedImageRequests = count; }", len(pending))
    page.route("**/api/job-image", intercept)
    with page.expect_request("**/api/job-image"):
        upload(page, name="first.png")
    expect(page.locator("#job-import-status")).to_contain_text("Reading text")
    with page.expect_request("**/api/job-image"):
        upload(page, name="second.png")
    page.wait_for_function("window.interceptedImageRequests === 2")
    assert len(pending) == 2
    pending[0].fulfill(json={"text": "old private text"})
    page.locator("#logout-button").click()
    expect(page.locator("#signed-out-actions")).to_be_visible()
    pending[1].fulfill(json={"text": "new private text"})
    page.wait_for_load_state("networkidle")
    expect(page.locator("#job-import-review")).to_be_hidden()
    expect(page.locator("#job-import-text")).to_have_value("")
    expect(page.locator("#job-description")).to_have_value("")


def test_text_read_from_image_is_never_rendered_as_markup(page: Page, app_url: str):
    page.goto(app_url)
    text = '<img src=x onerror="window.injected=true"> Python'
    page.route("**/api/job-image", lambda route: route.fulfill(json={"text": text}))
    upload(page)
    expect(page.locator("#job-import-text")).to_have_value(text)
    page.locator("#apply-job-upload").click()
    expect(page.locator("#job-description")).to_have_value(text)
    assert page.evaluate("window.injected !== true")


def test_letter_case_alone_does_not_show_spelling_prompts(page: Page, app_url: str):
    page.goto(app_url)
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#job-description").fill("pYtHoN JAVASCRIPT FAST API NODE.JS")
    page.locator("#user-skills").fill("Python, JavaScript, FastAPI, Node.js")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("100%")
    expect(page.locator("#spelling-checks")).to_be_hidden()


def test_camera_keyboard_upload_and_multiple_photos_keep_editable_text(page: Page, app_url: str):
    page.goto(app_url)
    expect(page.locator("#job-import")).to_be_hidden()
    page.locator("#job-description").fill("  My original text\n")
    page.route("**/api/job-image", lambda route: route.fulfill(json={"text": "Python"}))
    camera = page.get_by_role("button", name="Add a photo or screenshot")
    camera.focus()
    with page.expect_file_chooser() as chooser:
        page.keyboard.press("Enter")
    chooser.value.set_files({"name": "first.png", "mimeType": "image/png", "buffer": make_image()})
    expect(page.locator("#job-import-review")).to_be_visible()
    page.locator("#apply-job-upload").click()
    expect(page.locator("#job-description")).to_have_value("  My original text\n\n\nPython")
    upload(page, name="second.png")
    expect(page.locator("#job-import-review")).to_be_visible()
    page.locator("#job-import-text").fill("SQL")
    page.locator("#apply-job-upload").click()
    combined = "  My original text\n\n\nPython\n\nSQL"
    expect(page.locator("#job-description")).to_have_value(combined)
    expect(page.locator("#character-count")).to_have_text(f"{len(combined)} characters")
    expect(page.locator("#results-content")).to_be_hidden()


def test_discard_during_reading_ignores_late_response_and_restores_focus(page: Page, app_url: str):
    page.goto(app_url)
    page.locator("#job-description").fill("Keep this draft")
    pending: list[Route] = []
    def intercept(route: Route):
        pending.append(route)
        page.evaluate("window.imageRequestWaiting = true")
    page.route("**/api/job-image", intercept)
    upload(page)
    page.wait_for_function("window.imageRequestWaiting === true")
    expect(page.locator("#job-import-status")).to_contain_text("Reading text")
    page.locator("#discard-job-upload").click()
    expect(page.locator("#add-job-image")).to_be_focused()
    pending[0].fulfill(json={"text": "Discarded text"})
    page.wait_for_load_state("networkidle")
    expect(page.locator("#job-import")).to_be_hidden()
    expect(page.locator("#job-import-text")).to_have_value("")
    expect(page.locator("#job-description")).to_have_value("Keep this draft")
