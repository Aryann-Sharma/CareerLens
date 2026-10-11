import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, Route, expect

from e2e.test_feature_flows import register


RESPONSE = {"model": "skillspan-crf-v1", "revision": "test", "experimental": True,
            "spans": [{"text": "Python", "label": "knowledge", "start": 0, "end": 6},
                      {"text": "communication skills", "label": "skill", "start": 11, "end": 31}]}


def open_preview(page: Page, app_url: str) -> None:
    register(page, app_url)
    page.locator("#job-description").fill("Python and communication skills")
    page.locator("#extraction-preview summary").click()


@pytest.mark.parametrize("width", [320, 1440])
def test_extraction_preview_is_responsive_unsaved_and_cleared_on_edit(page: Page, app_url: str, width: int):
    page.set_viewport_size({"width": width, "height": 900})
    open_preview(page, app_url)
    page.route("**/api/extract", lambda route: route.fulfill(json=RESPONSE))
    page.locator("#extract-button").click()
    expect(page.locator("#extracted-knowledge .chip")).to_have_text(["Python"])
    expect(page.locator("#extracted-activities .chip")).to_have_text(["communication skills"])
    expect(page.locator(".history-card")).to_have_count(0)
    expect(page.locator("#results-content")).not_to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#job-description").fill("New description")
    expect(page.locator("#extraction-results")).not_to_be_visible()
    expect(page.locator("#extracted-knowledge .chip")).to_have_count(0)


@pytest.mark.parametrize("failure", ["unavailable", "network", "expired"])
def test_extraction_failure_recovery(page: Page, app_url: str, failure: str):
    open_preview(page, app_url)
    if failure == "network":
        page.route("**/api/extract", lambda route: route.abort())
    else:
        page.route("**/api/extract", lambda route: route.fulfill(
            status=401 if failure == "expired" else 503,
            json={"detail": "The trained extraction preview is unavailable."},
        ))
    page.locator("#extract-button").click()
    if failure == "expired":
        expect(page.locator("#auth-dialog")).to_be_visible()
        expect(page.locator("#extracted-knowledge .chip")).to_have_count(0)
        return
    expect(page.locator("#extraction-status")).to_contain_text(
        "Unable to reach" if failure == "network" else "unavailable"
    )
    expect(page.locator("#extract-button")).to_be_enabled()
    page.unroute("**/api/extract")
    page.route("**/api/extract", lambda route: route.fulfill(json=RESPONSE))
    page.locator("#extract-button").click()
    expect(page.locator("#extraction-results")).to_be_visible()


@pytest.mark.parametrize("action", ["edit", "logout"])
def test_delayed_extraction_cannot_restore_stale_private_content(page: Page, app_url: str, action: str):
    open_preview(page, app_url)
    pending: list[Route] = []
    page.route("**/api/extract", lambda route: pending.append(route))
    page.locator("#extract-button").click()
    expect(page.locator("#extract-button")).to_be_disabled()
    if action == "edit":
        page.locator("#job-description").fill("New description")
    else:
        page.get_by_role("button", name="Log out", exact=True).click()
        expect(page.locator("#auth-gate")).to_be_visible()
    assert len(pending) == 1
    pending[0].fulfill(json=RESPONSE)
    page.wait_for_load_state("networkidle")
    expect(page.locator("#extracted-knowledge .chip")).to_have_count(0)
    expect(page.locator("#extraction-results")).not_to_be_visible()


def test_preview_input_limits_and_literal_rendering(page: Page, app_url: str):
    open_preview(page, app_url)
    for text in ("",):
        page.locator("#job-description").fill(text)
        page.locator("#extract-button").click()
        expect(page.locator("#extraction-status")).to_contain_text("1 to 50,000")
    page.locator("#job-description").fill("Python")
    response = {**RESPONSE, "spans": [{"text": '<img src=x onerror="window.injected=true">',
                                     "label": "knowledge", "start": 0, "end": 6}]}
    page.route("**/api/extract", lambda route: route.fulfill(json=response))
    page.locator("#extract-button").click()
    expect(page.locator("#extracted-knowledge .chip")).to_have_text([response["spans"][0]["text"]])
    assert page.evaluate("window.injected !== true")


@pytest.mark.skipif(os.getenv("RUN_EXTRACTOR_TESTS") != "1", reason="Requires locally trained weights")
def test_real_trained_extraction_in_browser(page: Page, app_url: str):
    open_preview(page, app_url)
    page.locator("#job-description").fill("Experience with Python and SQL. Excellent communication skills.")
    page.locator("#extract-button").click()
    expect(page.locator("#extracted-knowledge .chip")).to_have_text(["Python", "SQL"])
    expect(page.locator("#extracted-activities .chip")).to_have_text(["communication skills"])
    screenshot = Path(".review-tests/trained-extraction.png")
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    page.locator("#extraction-preview").screenshot(path=str(screenshot))
