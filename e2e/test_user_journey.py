import httpx
from playwright.sync_api import Page, expect


PASSWORD = "Student-password-27"


def test_new_user_can_analyze_a_role_and_restore_the_session(
    page: Page,
    app_url: str,
) -> None:
    email = "new-student@example.com"

    page.goto(app_url)
    expect(
        page.get_by_role("heading", name="Sign in to analyze a role")
    ).to_be_visible()

    page.get_by_role("button", name="Create account", exact=True).first.click()
    page.get_by_label("Email", exact=True).fill(email)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Create account", exact=True).last.click()

    expect(page.get_by_text(email, exact=True)).to_be_visible()
    expect(page.get_by_role("region", name="Job analysis workspace")).to_be_visible()

    page.get_by_role("button", name="Use example").click()
    page.get_by_role("button", name="Analyze my fit").click()

    results = page.locator("#results-content")
    expect(results.get_by_text("57%", exact=True)).to_be_visible()
    missing_skills = page.locator("#missing-skills")
    expect(missing_skills.get_by_text("PostgreSQL", exact=True)).to_be_visible()
    expect(missing_skills.get_by_text("Docker", exact=True)).to_be_visible()
    expect(missing_skills.get_by_text("React", exact=True)).to_be_visible()

    history_card = page.locator(".history-card")
    expect(history_card).to_have_count(1)
    expect(history_card.get_by_text("57%", exact=True)).to_be_visible()
    history_card.get_by_role("button", name="View details").click()

    expect(page.get_by_text("57% match", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Matched skills")).to_be_visible()
    page.get_by_role("button", name="Close analysis details").click()

    page.reload()
    expect(page.get_by_text(email, exact=True)).to_be_visible()
    expect(page.locator(".history-card")).to_have_count(1)

    page.get_by_role("button", name="Log out").click()
    expect(
        page.get_by_role("heading", name="Sign in to analyze a role")
    ).to_be_visible()
    expect(page.get_by_role("region", name="Job analysis workspace")).to_be_hidden()


def test_login_errors_and_expired_sessions_keep_the_draft(
    page: Page,
    app_url: str,
) -> None:
    email = "returning-student@example.com"
    draft = "This role requires Python, SQL, FastAPI, and Docker experience."

    response = httpx.post(
        f"{app_url}/api/auth/register",
        json={"email": email, "password": PASSWORD},
        timeout=5,
    )
    assert response.status_code == 201

    page.goto(app_url)
    page.get_by_role("button", name="Log in", exact=True).first.click()
    page.get_by_label("Email", exact=True).fill(email)
    page.get_by_label("Password", exact=True).fill("wrong-password")
    page.get_by_role("button", name="Log in", exact=True).last.click()

    expect(page.get_by_role("alert")).to_have_text("Invalid email or password")

    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Log in", exact=True).last.click()
    expect(page.get_by_text(email, exact=True)).to_be_visible()

    description = page.get_by_label("Job description")
    description.fill(draft)
    page.get_by_label("Your skills").fill("Python, SQL")

    logout = page.request.post(f"{app_url}/api/auth/logout")
    assert logout.ok

    page.get_by_role("button", name="Analyze my fit").click()
    expect(page.get_by_text("Your session ended. Log in again to continue.")).to_be_visible()
    expect(page.get_by_role("dialog", name="Log in to CareerLens")).to_be_visible()
    assert description.input_value() == draft

    page.get_by_label("Email", exact=True).fill(email)
    page.get_by_label("Password", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Log in", exact=True).last.click()

    expect(page.get_by_text(email, exact=True)).to_be_visible()
    assert description.input_value() == draft
