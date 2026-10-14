from uuid import uuid4

import pytest
from playwright.sync_api import Page, expect

from e2e.test_feature_flows import register
from e2e.test_learning import analyze
from e2e.test_user_journey import PASSWORD


def build(page, app_url):
    analyze(page, app_url)
    page.locator("#build-learning-plan").click()
    expect(page.locator("#learning-plan")).to_be_visible()
    page.locator("#roadmap-name").fill("Java library project")
    page.locator("#learning-steps input").first.check()


def save(page):
    page.locator("#save-roadmap").click()
    expect(page.locator("#roadmap-save-status")).to_have_text("Saved to your account.")
    expect(page.locator("#saved-roadmaps-list .roadmap-row")).to_have_count(1)


@pytest.mark.parametrize("width", [320, 1440])
def test_save_resume_rename_progress_and_confirmed_delete(page: Page, app_url, width):
    page.set_viewport_size({"width": width, "height": 950})
    register(page, app_url)
    build(page, app_url)
    save(page)
    expect(page.locator("#match-score")).to_have_text("50%")
    page.reload()
    page.get_by_role("button", name="Open roadmap", exact=True).click()
    expect(page.locator("#roadmap-name")).to_have_value("Java library project")
    expect(page.locator("#learning-steps input").first).to_be_checked()
    expect(page.locator("#learning-progress")).to_contain_text("1 of 3")
    page.locator("#roadmap-name").fill("Java project finished")
    page.locator("#learning-steps input").nth(1).check()
    page.locator("#save-roadmap").click()
    expect(page.locator("#roadmap-save-status")).to_have_text("Saved to your account.")
    expect(page.locator("#saved-roadmaps-list")).to_contain_text("Java project finished")
    expect(page.locator("#saved-roadmaps-list")).to_contain_text("2 of 3")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.get_by_role("button", name="Delete roadmap Java project finished", exact=True).click()
    page.locator("#cancel-roadmap-action").click()
    expect(page.locator("#saved-roadmaps-list .roadmap-row")).to_have_count(1)
    page.get_by_role("button", name="Delete roadmap Java project finished", exact=True).click()
    page.locator("#confirm-roadmap-action").click()
    expect(page.locator("#saved-roadmaps-list .roadmap-row")).to_have_count(0)
    expect(page.locator("#learning-workspace")).to_be_hidden()


def test_guest_sign_in_retains_draft_and_requires_explicit_save(page: Page, app_url):
    build(page, app_url)
    page.locator("#save-roadmap").click()
    expect(page.locator("#auth-dialog")).to_be_visible()
    page.locator("#auth-switch").click()
    page.locator("#auth-email").fill(f"roadmap-{uuid4().hex}@example.com")
    page.locator("#auth-password").fill(PASSWORD)
    page.locator("#auth-submit").click()
    expect(page.locator("#signed-in-actions")).to_be_visible()
    expect(page.locator("#learning-steps input").first).to_be_checked()
    expect(page.locator("#roadmap-name")).to_have_value("Java library project")
    expect(page.locator("#saved-roadmaps-status")).to_contain_text("No saved roadmaps")
    save(page)


def test_lost_create_response_retry_does_not_duplicate_plan(page: Page, app_url):
    register(page, app_url)
    build(page, app_url)

    def lose_response(route):
        response = route.fetch()
        assert response.status == 201
        route.abort("failed")

    page.route("**/api/learning/saved", lose_response)
    page.locator("#save-roadmap").click()
    expect(page.locator("#roadmap-save-status")).to_contain_text("Unable to reach")
    page.unroute("**/api/learning/saved")
    save(page)
    expect(page.locator("#learning-steps input").first).to_be_checked()
    assert page.request.get(f"{app_url}/api/learning/saved").json()["total"] == 1


def test_stale_tab_save_requires_reopening_without_overwriting_newer_progress(page: Page, app_url):
    register(page, app_url)
    build(page, app_url)
    save(page)
    saved = page.request.get(f"{app_url}/api/learning/saved").json()["items"][0]
    assert page.request.put(f"{app_url}/api/learning/saved/{saved['id']}", data={"title": "Updated in another tab", "version": 1, "completed": ["0:2"]}).ok
    page.locator("#learning-steps input").nth(1).check()
    page.locator("#save-roadmap").click()
    expect(page.locator("#roadmap-save-status")).to_contain_text("changed in another tab")
    page.get_by_role("button", name="Open roadmap", exact=True).click()
    expect(page.locator("#roadmap-action-dialog")).to_be_visible()
    page.locator("#cancel-roadmap-action").click()
    expect(page.locator("#learning-steps input").nth(1)).to_be_checked()
    page.get_by_role("button", name="Open roadmap", exact=True).click()
    page.locator("#confirm-roadmap-action").click()
    expect(page.locator("#roadmap-name")).to_have_value("Updated in another tab")
    expect(page.locator("#learning-steps input").nth(1)).not_to_be_checked()
    expect(page.locator("#learning-steps input").nth(2)).to_be_checked()


@pytest.mark.parametrize("late_status", [200, 401])
def test_account_switch_clears_plan_list_and_delayed_private_response(page: Page, app_url, late_status):
    register(page, app_url)
    build(page, app_url)
    save(page)
    saved = page.request.get(f"{app_url}/api/learning/saved").json()["items"][0]
    held = []
    page.route(f"**/api/learning/saved/{saved['id']}", lambda route: held.append((route, route.fetch())))
    page.get_by_role("button", name="Open roadmap", exact=True).click()
    page.locator("#logout-button").click()
    expect(page.locator("#saved-roadmaps")).to_be_hidden()
    expect(page.locator("#saved-roadmaps-list")).to_be_empty()
    new_email = f"new-roadmap-owner-{uuid4().hex}@example.com"
    page.locator("#open-register").click()
    page.locator("#auth-email").fill(new_email)
    page.locator("#auth-password").fill(PASSWORD)
    page.locator("#auth-submit").click()
    expect(page.locator("#current-user-email")).to_have_text(new_email)
    assert len(held) == 1
    if late_status == 200:
        held[0][0].fulfill(response=held[0][1])
    else:
        held[0][0].fulfill(status=401, json={"detail": "Not authenticated"})
    expect(page.locator("#saved-roadmaps-status")).to_contain_text("No saved roadmaps")
    expect(page.locator("#learning-workspace")).to_be_hidden()
    expect(page.locator("#learning-steps")).to_be_empty()
    expect(page.locator("#current-user-email")).to_have_text(new_email)


def test_new_analysis_creates_a_separate_plan_without_replacing_saved_progress(page: Page, app_url):
    register(page, app_url)
    build(page, app_url)
    save(page)
    page.locator("#job-description").fill("Python")
    page.locator("#analyze-button").click()
    expect(page.locator("#missing-skills .chip")).to_have_text(["Python"])
    page.locator("#build-learning-plan").click()
    expect(page.locator(".learning-skill")).to_have_text(["Python"])
    page.locator("#roadmap-name").fill("Python practice")
    page.locator("#save-roadmap").click()
    expect(page.locator("#saved-roadmaps-list .roadmap-row")).to_have_count(2)
    rows = page.locator("#saved-roadmaps-list .roadmap-row")
    expect(rows.filter(has_text="Java library project")).to_contain_text("1 of 3")
    expect(rows.filter(has_text="Python practice")).to_contain_text("0 of 3")


def test_changed_cookie_cannot_save_private_plan_into_another_account(page: Page, app_url):
    register(page, app_url)
    build(page, app_url)
    page.request.post(f"{app_url}/api/auth/logout")
    response = page.request.post(f"{app_url}/api/auth/register", data={"email": f"changed-{uuid4().hex}@example.com", "password": PASSWORD})
    assert response.ok
    page.locator("#save-roadmap").click()
    expect(page.locator("#auth-dialog")).to_be_visible()
    expect(page.locator("#learning-workspace")).to_be_hidden()
    assert page.request.get(f"{app_url}/api/learning/saved").json()["total"] == 0


def test_paginated_library_and_literal_titles(page: Page, app_url):
    register(page, app_url)
    revision = page.request.post(f"{app_url}/api/learning/plan", data={"missing_skills": ["Java"]}).json()["revision"]
    for index in range(6):
        response = page.request.post(f"{app_url}/api/learning/saved", data={"client_id": str(uuid4()), "plan_revision": revision, "title": f"<b>Plan {index}</b>",
             "completed": [], "request": {"missing_skills": ["Java"]}})
        assert response.status == 201
    page.locator("#refresh-roadmaps").click()
    expect(page.locator("#saved-roadmaps-list .roadmap-row")).to_have_count(5)
    expect(page.locator("#saved-roadmaps-list h3").first).to_have_text("<b>Plan 5</b>")
    expect(page.locator("#saved-roadmaps-list b")).to_have_count(0)
    page.locator("#roadmaps-next").click()
    expect(page.locator("#saved-roadmaps-list .roadmap-row")).to_have_count(1)
    page.get_by_role("button", name="Delete roadmap <b>Plan 0</b>", exact=True).click()
    page.locator("#confirm-roadmap-action").click()
    expect(page.locator("#saved-roadmaps-list .roadmap-row")).to_have_count(5)
    expect(page.locator("#roadmap-pagination")).to_be_hidden()
