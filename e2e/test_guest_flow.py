from pathlib import Path
from uuid import uuid4

from playwright.sync_api import Page, Route, expect

from e2e.test_user_journey import PASSWORD


def guest_analysis(page: Page, app_url: str):
    page.goto(app_url)
    expect(page.locator("#signed-out-actions")).to_be_visible()
    page.locator("#job-description").fill("Python and SQL")
    page.locator("#user-skills").fill("Python")
    page.locator("#matching-method").select_option("exact")
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("50%")
    expect(page.locator("#results-content")).to_be_visible()
    expect(page.locator("#history-section")).to_be_hidden()
    expect(page.locator("#auth-dialog")).to_be_hidden()


def complete_registration(page: Page):
    email = f"guest-{uuid4().hex}@example.com"
    page.locator("#auth-switch").click()
    page.locator("#auth-email").fill(email)
    page.locator("#auth-password").fill(PASSWORD)
    page.locator("#auth-submit").click()
    expect(page.locator("#current-user-email")).to_have_text(email)


def test_guest_can_analyze_then_register_and_save_the_displayed_result(page: Page, app_url: str):
    guest_analysis(page, app_url)
    # Saving uses the analyzed snapshot, even if the input form has since changed.
    page.locator("#job-description").fill("Java only")
    page.locator("#save-analysis").click()
    expect(page.locator("#auth-dialog-copy")).to_contain_text("save this analysis")
    complete_registration(page)
    expect(page.locator("#save-analysis")).to_have_text("Saved")
    expect(page.locator(".history-card")).to_have_count(1)
    expect(page.locator("#match-score")).to_have_text("50%")
    page.get_by_role("button", name="View details").click()
    expect(page.locator(".saved-description")).to_have_text("Python and SQL")
    page.keyboard.press("Escape")
    page.reload()
    expect(page.locator(".history-card")).to_have_count(1)


def test_cancelled_save_and_header_login_do_not_save_implicitly(page: Page, app_url: str):
    guest_analysis(page, app_url)
    page.locator("#save-analysis").click()
    page.keyboard.press("Escape")
    expect(page.locator("#results-content")).to_be_visible()
    page.locator("#open-login").click()
    complete_registration(page)
    expect(page.locator("#history-status")).to_contain_text("No saved analyses")
    expect(page.locator(".history-card")).to_have_count(0)
    expect(page.locator("#save-analysis")).to_have_text("Save analysis")
    page.locator("#save-analysis").click()
    expect(page.locator("#save-analysis")).to_have_text("Saved")
    expect(page.locator(".history-card")).to_have_count(1)


def test_failed_save_keeps_the_result_and_allows_retry(page: Page, app_url: str):
    guest_analysis(page, app_url)
    page.route("**/api/analyze", lambda route: route.fulfill(status=503, json={"detail": "Please try again."}))
    page.locator("#save-analysis").click()
    complete_registration(page)
    expect(page.locator("#save-status")).to_have_text("Please try again.")
    expect(page.locator("#results-content")).to_be_visible()
    page.unroute("**/api/analyze")
    page.locator("#save-analysis").click()
    expect(page.locator(".history-card")).to_have_count(1)
    expect(page.locator("#save-analysis")).to_be_disabled()


def test_slow_session_check_does_not_erase_guest_input_or_results(page: Page, app_url: str):
    pending: list[Route] = []
    page.route("**/api/auth/me", lambda route: pending.append(route))
    page.goto(app_url)
    page.locator("#job-description").fill("Python")
    page.locator("#user-skills").fill("Python")
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("100%")
    assert len(pending) == 1
    pending[0].fulfill(status=401, json={"detail": "Not authenticated"})
    expect(page.locator("#signed-out-actions")).to_be_visible()
    expect(page.locator("#job-description")).to_have_value("Python")
    expect(page.locator("#results-content")).to_be_visible()
    expect(page.locator("#match-score")).to_have_text("100%")


def test_guest_semantic_matching_and_mobile_save_layout(page: Page, app_url: str):
    page.set_viewport_size({"width": 375, "height": 900})
    page.goto(app_url)
    page.locator("#use-example").click()
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("57%")
    expect(page.locator("#matching-evidence")).to_contain_text("writing relational database queries")
    expect(page.locator("#save-analysis")).to_be_enabled()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    Path(".review-tests").mkdir(exist_ok=True)
    page.screenshot(path=".review-tests/guest-mobile.png", full_page=True)
    page.reload()
    expect(page.locator("#job-description")).to_have_value("")
    expect(page.locator("#results-content")).to_be_hidden()
