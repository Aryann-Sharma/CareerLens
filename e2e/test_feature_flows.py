from uuid import uuid4

import pytest
from playwright.sync_api import APIResponse, Page, Route, expect

from e2e.test_user_journey import PASSWORD


def register(page: Page, app_url: str) -> str:
    email = f"student-{uuid4().hex}@example.com"
    response = page.request.post(
        f"{app_url}/api/auth/register",
        data={"email": email, "password": PASSWORD},
    )
    assert response.status == 201
    page.goto(app_url)
    expect(page.locator("#authenticated-app")).to_be_visible()
    return email


def create_analysis(page: Page, app_url: str, description: str) -> None:
    response = page.request.post(
        f"{app_url}/api/analyze",
        data={"job_description": description, "user_skills": ["Python"]},
    )
    assert response.ok


def submit(page: Page, description: str, skills: str = "") -> None:
    page.get_by_label("Job description", exact=True).fill(description)
    page.get_by_label("Your skills", exact=True).fill(skills)
    page.get_by_role("button", name="Analyze my fit").click()


@pytest.mark.parametrize(
    "description,skills,score,matched,missing",
    [
        ("Python and SQL", "", "0%", [], ["Python", "SQL"]),
        ("Communication and teamwork", "Python", "0%", [], []),
        ("React.js, Postgre SQL and JS", "reactjs, postgres, js, JS", "100%",
         ["React", "PostgreSQL", "JavaScript"], []),
        ("Python, SQL, Git", "Python, rust", "33%", ["Python"], ["SQL", "Git"]),
    ],
)
def test_analysis_results_and_saved_details(
    page: Page, app_url: str, description: str, skills: str,
    score: str, matched: list[str], missing: list[str],
) -> None:
    register(page, app_url)
    submit(page, description, skills)
    expect(page.locator("#match-score")).to_have_text(score)
    expect(page.locator("#matched-skills .chip")).to_have_text(matched)
    expect(page.locator("#missing-skills .chip")).to_have_text(missing)
    expect(page.locator(".history-card")).to_have_count(1)
    page.get_by_role("button", name="View details").click()
    expect(page.get_by_role("dialog", name="Analysis details")).to_be_visible()
    expect(page.locator(".saved-description")).to_have_text(description)
    expect(page.locator(".detail-summary strong")).to_have_text(f"{score} match")
    page.keyboard.press("Escape")
    expect(page.locator("#history-dialog")).not_to_be_visible()


def test_history_pagination_and_latest_analysis(page: Page, app_url: str) -> None:
    register(page, app_url)
    for number in range(6):
        create_analysis(page, app_url, f"Role {number}: Python and SQL")
    page.reload()
    expect(page.locator(".history-card")).to_have_count(5)
    expect(page.locator(".history-card").first).to_contain_text("Role 5")
    expect(page.locator("#history-previous")).to_be_disabled()
    page.locator("#history-next").click()
    expect(page.locator("#history-page-status")).to_have_text("Page 2 of 2")
    expect(page.locator(".history-card")).to_have_count(1)
    expect(page.locator(".history-card")).to_contain_text("Role 0")
    expect(page.locator("#history-next")).to_be_disabled()
    page.locator("#history-previous").click()
    expect(page.locator("#history-page-status")).to_have_text("Page 1 of 2")
    submit(page, "Newest Python role", "Python")
    expect(page.locator(".history-card").first).to_contain_text("Newest Python role")


def test_logout_clears_private_draft_and_results(page: Page, app_url: str) -> None:
    register(page, app_url)
    submit(page, "Private Python role", "Python")
    expect(page.locator("#results-content")).to_be_visible()
    page.get_by_role("button", name="Log out").click()
    expect(page.locator("#auth-gate")).to_be_visible()
    expect(page.locator("#job-description")).to_have_value("")
    expect(page.locator("#user-skills")).to_have_value("")
    expect(page.locator("#matched-skills .chip")).to_have_count(0)
    expect(page.locator(".history-card")).to_have_count(0)
    register(page, app_url)
    expect(page.locator("#job-description")).to_have_value("")
    expect(page.locator(".history-card")).to_have_count(0)


@pytest.mark.parametrize("endpoint", ["/api/analyze", "/api/analyses?page=1&page_size=5"])
def test_delayed_private_response_is_ignored_after_logout(
    page: Page, app_url: str, endpoint: str,
) -> None:
    register(page, app_url)
    create_analysis(page, app_url, "Private Python role")
    pending: list[tuple[Route, APIResponse]] = []

    def hold(route: Route) -> None:
        pending.append((route, route.fetch()))

    page.route(f"**{endpoint}", hold)
    if endpoint == "/api/analyze":
        submit(page, "Private Python role", "Python")
    else:
        page.reload()
        expect(page.locator("#authenticated-app")).to_be_visible()
    expect(page.get_by_role("button", name="Log out")).to_be_enabled()
    page.get_by_role("button", name="Log out").click()
    expect(page.locator("#auth-gate")).to_be_visible()
    assert pending
    for route, response in pending:
        route.fulfill(response=response)
    # Wait for the released fetch and its rendering callbacks to finish.
    page.wait_for_load_state("networkidle")
    expect(page.locator(".history-card")).to_have_count(0)
    expect(page.locator("#results-content")).not_to_be_visible()
    expect(page.locator("#matched-skills .chip")).to_have_count(0)


def test_expired_draft_is_cleared_when_a_different_user_logs_in(page: Page, app_url: str) -> None:
    register(page, app_url)
    submit(page, "Python", "Python")
    expect(page.locator("#results-content")).to_be_visible()
    page.request.post(f"{app_url}/api/auth/logout")
    submit(page, "First user's private draft", "SQL")
    expect(page.locator("#auth-dialog")).to_be_visible()
    page.locator("#auth-switch").click()
    page.get_by_label("Email", exact=True).fill(f"second-{uuid4().hex}@example.com")
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.locator("#auth-submit").click()
    expect(page.locator("#authenticated-app")).to_be_visible()
    expect(page.locator("#job-description")).to_have_value("")
    expect(page.locator("#user-skills")).to_have_value("")
    expect(page.locator(".history-card")).to_have_count(0)


@pytest.mark.parametrize("failure", ["network", "server", "validation"])
def test_analysis_errors_allow_retry(page: Page, app_url: str, failure: str) -> None:
    register(page, app_url)
    if failure == "network":
        page.route("**/api/analyze", lambda route: route.abort())
    elif failure == "server":
        page.route("**/api/analyze", lambda route: route.fulfill(status=500, body="Unavailable"))
    submit(page, "   " if failure == "validation" else "Python", "Python")
    expect(page.locator("#form-error")).to_be_visible()
    expect(page.locator("#analyze-button")).to_be_enabled()
    expect(page.locator("#results-panel")).to_have_attribute("aria-busy", "false")
    page.unroute("**/api/analyze")
    submit(page, "Python", "Python")
    expect(page.locator("#results-content")).to_be_visible()
    expect(page.locator("#match-score")).to_have_text("100%")
    expect(page.locator("#form-error")).not_to_be_visible()


def test_history_and_detail_errors(page: Page, app_url: str) -> None:
    register(page, app_url)
    create_analysis(page, app_url, "Python")
    page.route("**/api/analyses?*", lambda route: route.fulfill(status=503))
    page.reload()
    expect(page.locator("#history-status")).to_contain_text("could not be loaded")
    page.unroute("**/api/analyses?*")
    page.reload()
    expect(page.locator(".history-card")).to_have_count(1)
    page.route("**/api/analyses/*", lambda route: route.fulfill(status=404))
    page.get_by_role("button", name="View details").click()
    expect(page.locator("#history-detail")).to_contain_text("could not be loaded")
    page.get_by_role("button", name="Close analysis details").click()
    expect(page.locator("#history-dialog")).not_to_be_visible()


def test_registration_validation_duplicate_account_and_dialog_padding(page: Page, app_url: str) -> None:
    email = register(page, app_url)
    page.get_by_role("button", name="Log out").click()
    page.locator("#open-register").click()
    page.get_by_label("Email", exact=True).fill(email)
    page.get_by_label("Password", exact=True).fill("short")
    page.locator("#auth-submit").click()
    expect(page.locator("#auth-dialog")).to_be_visible()
    assert page.locator("#auth-password").evaluate("input => !input.checkValidity()")
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.locator("#auth-submit").click()
    expect(page.locator("#auth-error")).to_have_text("An account with this email already exists")
    page.locator("#auth-dialog").click(position={"x": 25, "y": 25})
    expect(page.locator("#auth-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#auth-dialog")).not_to_be_visible()


def test_mobile_long_content_and_safe_text_rendering(page: Page, app_url: str) -> None:
    page.set_viewport_size({"width": 375, "height": 812})
    register(page, app_url)
    description = '<img src=x onerror="window.injected=true"> Python ' + "x" * 300
    submit(page, description, "x" * 100)
    expect(page.locator(".history-card")).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.get_by_role("button", name="View details").click()
    expect(page.locator(".saved-description")).to_have_text(description)
    assert page.locator("#history-detail img").count() == 0
    assert page.evaluate("window.injected === undefined")
    assert page.locator("#history-dialog").evaluate("dialog => dialog.scrollWidth <= dialog.clientWidth")
    page.screenshot(path="test-results/mobile-analysis.png", full_page=True)


def test_session_check_failure_keeps_login_available(page: Page, app_url: str) -> None:
    page.route("**/api/auth/me", lambda route: route.fulfill(status=503))
    page.goto(app_url)
    expect(page.locator("#signed-out-message")).to_contain_text("couldn't check your session")
    page.locator("#open-login").click()
    expect(page.get_by_role("dialog", name="Log in to CareerLens")).to_be_visible()


@pytest.mark.parametrize("width", [320, 375, 820, 1440])
def test_responsive_account_and_workspace_layout(page: Page, app_url: str, width: int) -> None:
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(app_url)
    expect(page.locator("#auth-gate")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#open-register").click()
    expect(page.locator("#auth-dialog")).to_be_visible()
    assert page.locator("#auth-dialog").evaluate("dialog => dialog.scrollWidth <= dialog.clientWidth")
    page.keyboard.press("Escape")
    register(page, app_url)
    page.get_by_role("button", name="Use example").click()
    page.get_by_role("button", name="Analyze my fit").click()
    expect(page.locator(".history-card")).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=f"test-results/workspace-{width}.png", full_page=True)


def test_logout_failure_keeps_session_and_allows_retry(page: Page, app_url: str) -> None:
    register(page, app_url)
    page.route("**/api/auth/logout", lambda route: route.abort())
    page.get_by_role("button", name="Log out").click()
    expect(page.locator("#form-error")).to_contain_text("couldn't log you out")
    expect(page.locator("#authenticated-app")).to_be_visible()
    expect(page.get_by_role("button", name="Log out")).to_be_enabled()
    page.unroute("**/api/auth/logout")
    page.get_by_role("button", name="Log out").click()
    expect(page.locator("#auth-gate")).to_be_visible()


@pytest.mark.parametrize("endpoint", ["**/api/analyses?*", "**/api/analyses/*"])
def test_history_session_expiry_prompts_login(page: Page, app_url: str, endpoint: str) -> None:
    register(page, app_url)
    create_analysis(page, app_url, "Python")
    page.reload()
    expect(page.locator(".history-card")).to_have_count(1)
    page.route(endpoint, lambda route: route.fulfill(status=401, json={"detail": "Not authenticated"}))
    if endpoint.endswith("?*"):
        page.reload()
    else:
        page.get_by_role("button", name="View details").click()
    expect(page.get_by_role("dialog", name="Log in to CareerLens")).to_be_visible()
    expect(page.locator("#authenticated-app")).not_to_be_visible()
    expect(page.locator("#history-dialog")).not_to_be_visible()


def test_old_history_cannot_replace_a_newer_refresh(page: Page, app_url: str) -> None:
    register(page, app_url)
    create_analysis(page, app_url, "Older Python role")
    pending: list[tuple[Route, APIResponse]] = []

    def hold_first(route: Route) -> None:
        if pending:
            route.continue_()
        else:
            pending.append((route, route.fetch()))

    page.route("**/api/analyses?*", hold_first)
    page.reload()
    expect(page.locator("#authenticated-app")).to_be_visible()
    submit(page, "Newer SQL role", "SQL")
    expect(page.locator(".history-card")).to_have_count(2)
    route, response = pending[0]
    route.fulfill(response=response)
    page.wait_for_load_state("networkidle")
    expect(page.locator(".history-card")).to_have_count(2)
    expect(page.locator(".history-card").first).to_contain_text("Newer SQL role")


def test_closed_detail_response_cannot_replace_another_detail(page: Page, app_url: str) -> None:
    register(page, app_url)
    create_analysis(page, app_url, "First Python role")
    create_analysis(page, app_url, "Second SQL role")
    page.reload()
    expect(page.locator(".history-card")).to_have_count(2)
    pending: list[tuple[Route, APIResponse]] = []

    def hold_first(route: Route) -> None:
        if pending:
            route.continue_()
        else:
            pending.append((route, route.fetch()))

    page.route("**/api/analyses/*", hold_first)
    page.get_by_role("button", name="View details").first.click()
    expect(page.locator("#history-detail")).to_contain_text("Loading")
    page.get_by_role("button", name="Close analysis details").click()
    page.get_by_role("button", name="View details").last.click()
    expect(page.locator(".saved-description")).to_have_text("First Python role")
    route, response = pending[0]
    route.fulfill(response=response)
    page.wait_for_load_state("networkidle")
    expect(page.locator(".saved-description")).to_have_text("First Python role")
