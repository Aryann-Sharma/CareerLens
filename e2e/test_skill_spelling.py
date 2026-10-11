import pytest
from playwright.sync_api import Page, expect

from backend.tests.pdf_fixtures import make_pdf
from e2e.test_feature_flows import register


def analyze(page: Page, text: str, skills: str):
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#job-description").fill(text)
    page.locator("#user-skills").fill(skills)
    page.locator("#analyze-button").click()
    expect(page.locator("#results-content")).to_be_visible()


@pytest.mark.parametrize("width", [320, 1440])
def test_common_typos_are_explained_and_saved(page: Page, app_url: str, width: int):
    page.set_viewport_size({"width": width, "height": 950})
    register(page, app_url)
    analyze(page, "Pyhton and Javascrip. Python is also mentioned.", "Python, JavaScript")
    expect(page.locator("#match-score")).to_have_text("100%")
    expect(page.locator("#matched-skills .chip")).to_have_text(["Python", "JavaScript"])
    expect(page.locator("#spelling-checks")).to_contain_text("Read “Pyhton” as Python.")
    expect(page.locator("#job-description")).to_have_value("Pyhton and Javascrip. Python is also mentioned.")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.reload()
    page.get_by_role("button", name="View details").first.click()
    expect(page.locator("#history-detail .spelling-checks")).to_contain_text("Read “Javascrip” as JavaScript.")
    expect(page.locator("#history-detail .saved-description")).to_contain_text("Pyhton and Javascrip")


def test_uncertain_spelling_requires_review_and_recalculation(page: Page, app_url: str):
    page.goto(app_url)
    analyze(page, "Pythom and SQL", "Python, SQL")
    expect(page.locator("#matched-skills .chip")).to_have_text(["SQL"])
    expect(page.locator("#spelling-checks")).to_contain_text("No correction has been applied")
    page.locator("#spelling-checks").get_by_role("button", name="Use Python").click()
    expect(page.locator("#reviewed-skills")).to_have_value("SQL\nPython")
    expect(page.locator("#matched-skills .chip")).to_have_text(["SQL"])
    expect(page.locator("#spelling-checks")).to_contain_text("Choose Update analysis")
    page.locator("#update-analysis").click()
    expect(page.locator("#matched-skills .chip")).to_have_text(["SQL", "Python"])
    expect(page.locator("#spelling-checks")).to_be_hidden()
    expect(page.locator("#extraction-method-note")).to_contain_text("your corrections")


def test_review_can_reject_an_automatic_correction(page: Page, app_url: str):
    page.goto(app_url)
    analyze(page, "Pyhton", "Python")
    expect(page.locator("#match-score")).to_have_text("100%")
    page.locator("#skill-review summary").click()
    page.locator("#reviewed-skills").fill("Pyhton")
    page.locator("#update-analysis").click()
    expect(page.locator("#match-score")).to_have_text("0%")
    expect(page.locator("#missing-skills .chip")).to_have_text(["Pyhton"])


def test_resume_spelling_review_preserves_original_pdf_and_manual_skills(page: Page, app_url: str):
    register(page, app_url)
    page.locator("#extraction-method").select_option("catalog")
    page.locator("#user-skills").fill("C++")
    page.locator(".resume-upload summary").click()
    page.locator("#resume-file").set_input_files({"name": "resume.pdf", "mimeType": "application/pdf", "buffer": make_pdf("Pyhton Reactt")})
    expect(page.locator("#resume-spelling")).to_contain_text("Read “Pyhton” as Python.")
    page.locator("#resume-spelling").get_by_role("button", name="Use React").click()
    expect(page.locator("#resume-skills")).to_have_value("Python\nReact")
    expect(page.locator("#user-skills")).to_have_value("C++")
    page.locator("#apply-resume").click()
    expect(page.locator("#user-skills")).to_have_value("C++, Python, React")
    page.locator("#save-resume").click()
    expect(page.locator("#saved-resume")).to_be_visible()
    page.locator("#use-saved-resume").click()
    expect(page.locator("#resume-spelling")).to_contain_text("No correction has been applied")
    expect(page.locator("#resume-skills")).to_have_value("Python")
    page.locator("#logout-button").click()
    expect(page.locator("#resume-spelling")).to_be_hidden()
    expect(page.locator("#resume-spelling")).to_have_text("")


def test_uncertain_model_phrase_is_replaced_without_duplicates(page: Page, app_url: str):
    page.goto(app_url)
    response = {"extracted_skills": ["Pythom", "Python"], "matched_skills": ["Python"], "missing_skills": ["Pythom"], "match_score": 50,
        "extraction_details": {"method": "trained", "spelling": [
            {"original": "Pythom", "candidates": ["Python"], "applied": False, "start": 0, "end": 6}
        ]}}
    page.route("**/api/preview", lambda route: route.fulfill(json=response))
    analyze(page, "Pythom Python", "Python")
    page.locator("#spelling-checks").get_by_role("button", name="Use Python").click()
    expect(page.locator("#reviewed-skills")).to_have_value("Python")
