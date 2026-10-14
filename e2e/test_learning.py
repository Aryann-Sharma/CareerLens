from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from e2e.test_feature_flows import register


def analyze(page, app_url, text="Java and SQL", profile="SQL"):
    page.goto(app_url)
    page.locator("#job-description").fill(text)
    page.locator("#user-skills").fill(profile)
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#matching-method").select_option("exact")
    page.locator("#analyze-button").click()
    expect(page.locator("#learning-workspace")).to_be_visible()
    expect(page.locator("#learning-direction option")).to_have_count(7)


@pytest.mark.parametrize("width", [320, 768, 1440])
def test_learning_guide_and_downloadable_roadmap(page: Page, app_url, tmp_path: Path, width):
    page.set_viewport_size({"width": width, "height": 900})
    analyze(page, app_url)
    chip = page.locator("#missing-skills").get_by_role("button", name="Learning guide for Java")
    chip.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#learning-dialog")).to_be_visible()
    expect(page.locator("#learning-guide-content a")).to_have_attribute("href", "https://dev.java/learn/")
    expect(page.locator("#learning-guide-content")).to_contain_text("library lending")
    page.keyboard.press("Escape")
    expect(chip).to_be_focused()
    page.locator("#build-learning-plan").click()
    expect(page.locator("#learning-steps .learning-card")).to_have_count(1)
    page.locator("#learning-steps input").first.check()
    expect(page.locator("#learning-progress")).to_contain_text("1 of 3")
    with page.expect_download() as download_info:
        page.locator("#download-learning-plan").click()
    path = tmp_path / "checklist.txt"
    download_info.value.save_as(path)
    content = path.read_text(encoding="utf-8")
    assert "[x] Practice control flow" in content and "https://dev.java/learn/" in content
    expect(page.locator("#match-score")).to_have_text("50%")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_vague_description_can_get_direction_without_inventing_scored_skills(page: Page, app_url):
    analyze(page, app_url, "Web developer: good at programming", "")
    expect(page.locator("#missing-count")).to_have_text("0")
    page.locator("#learning-direction").select_option("web")
    page.locator("#build-learning-plan").click()
    expect(page.locator(".learning-skill")).to_have_text(["HTML", "CSS", "JavaScript", "Git"])
    expect(page.locator("#learning-steps")).to_contain_text("Suggested for your direction")
    expect(page.locator("#missing-count")).to_have_text("0")
    expect(page.locator("#match-score")).to_have_text("0%")
    page.reload()
    expect(page.locator("#learning-workspace")).to_be_hidden()


def test_rebuild_uses_analyzed_snapshot_and_resets_progress(page: Page, app_url):
    analyze(page, app_url, "React", "JS")
    page.locator("#build-learning-plan").click()
    expect(page.locator(".learning-skill")).to_have_text(["HTML", "CSS", "React"])
    page.locator("#learning-steps input").first.check()
    page.locator("#user-skills").fill("HTML, CSS, React")
    page.locator("#learning-direction").select_option("web")
    page.locator("#build-learning-plan").click()
    expect(page.locator(".learning-skill")).to_have_text(["HTML", "CSS", "React", "Git"])
    expect(page.locator("#learning-progress")).to_contain_text("0 of 12")
    page.locator("#analyze-button").click()
    expect(page.locator("#match-score")).to_have_text("100%")
    expect(page.locator("#learning-plan")).to_be_hidden()


def test_guide_errors_retry_and_unknown_typo_does_not_change_analysis(page: Page, app_url):
    analyze(page, app_url)
    page.locator("#edit-result-skills").click()
    page.locator("#reviewed-skills").fill("Pythom\n<script>alert(1)</script>")
    page.locator("#update-analysis").click()
    expect(page.locator("#missing-count")).to_have_text("2")
    page.route("**/api/learning/guide?**", lambda route: route.fulfill(status=503))
    page.locator("#missing-skills .chip").first.click()
    expect(page.locator("#learning-guide-content")).to_contain_text("could not load")
    page.unroute("**/api/learning/guide?**")
    page.get_by_role("button", name="Retry learning guide").click()
    page.get_by_role("button", name="Did you mean Python? View its guide").click()
    expect(page.locator("#learning-dialog-title")).to_have_text("Learn Python")
    page.keyboard.press("Escape")
    expect(page.locator("#missing-skills .chip")).to_have_text(["Pythom", "<script>alert(1)</script>"])
    page.locator("#missing-skills .chip").last.click()
    expect(page.locator("#learning-guide-content")).to_contain_text("No reviewed learning guide")
    expect(page.locator("#learning-dialog script")).to_have_count(0)


def test_roadmap_failure_can_retry_and_logout_clears_progress(page: Page, app_url):
    register(page, app_url)
    analyze(page, app_url)
    page.route("**/api/learning/plan", lambda route: route.fulfill(status=503))
    page.locator("#build-learning-plan").click()
    expect(page.locator("#learning-status")).to_contain_text("could not be built")
    page.unroute("**/api/learning/plan")
    page.locator("#build-learning-plan").click()
    expect(page.locator("#learning-plan")).to_be_visible()
    page.locator("#learning-steps input").first.check()
    page.locator("#logout-button").click()
    expect(page.locator("#learning-workspace")).to_be_hidden()
    expect(page.locator("#learning-steps")).to_be_empty()
    expect(page.locator("#learning-progress")).to_be_empty()
    expect(page.locator("#learning-plan-title")).to_be_empty()
    expect(page.locator("#learning-guide-content")).to_be_empty()
    expect(page.locator("#learning-dialog-title")).to_have_text("Learning guide")


def test_late_plan_response_cannot_restore_previous_analysis(page: Page, app_url):
    analyze(page, app_url)
    held = []
    page.route("**/api/learning/plan", lambda route: held.append(route))
    page.locator("#build-learning-plan").click()
    page.wait_for_function("document.querySelector('#build-learning-plan').disabled")
    page.locator("#job-description").fill("Python")
    page.locator("#analyze-button").click()
    expect(page.locator("#missing-skills .chip")).to_have_text(["Python"])
    assert len(held) == 1
    held[0].fulfill(json={"direction": None, "steps": [], "notice": "OLD RESPONSE"})
    expect(page.locator("#learning-plan")).to_be_hidden()
    expect(page.locator("#learning-notice")).not_to_have_text("OLD RESPONSE")


def test_direction_loading_failure_does_not_block_existing_missing_skills(page: Page, app_url):
    page.route("**/api/learning/directions", lambda route: route.fulfill(status=503))
    page.goto(app_url)
    page.locator("#job-description").fill("Java")
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#matching-method").select_option("exact")
    page.locator("#analyze-button").click()
    expect(page.locator("#learning-status")).to_contain_text("could not load")
    page.unroute("**/api/learning/directions")
    page.locator("#build-learning-plan").click()
    expect(page.locator(".learning-skill")).to_have_text(["Java"])
    expect(page.locator("#learning-direction option")).to_have_count(7)


@pytest.mark.parametrize("width", [320, 1440])
def test_spelling_correction_brings_editor_and_update_button_into_view(page: Page, app_url, width):
    page.set_viewport_size({"width": width, "height": 900})
    analyze(page, app_url, "pasionate about work", "passionate")
    page.get_by_role("button", name="Use passionate", exact=True).click()
    expect(page.locator("#reviewed-skills")).to_be_focused()
    expect(page.locator("#reviewed-skills")).to_be_in_viewport()
    expect(page.locator("#update-analysis")).to_be_in_viewport()
    assert page.locator("#skill-review").bounding_box()["y"] < page.locator("#matched-skills").bounding_box()["y"]
    page.locator("#update-analysis").click()
    expect(page.locator("#match-score")).to_have_text("100%")
