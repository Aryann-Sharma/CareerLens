import os
import re

import pytest
from playwright.sync_api import expect

from backend.tests.varied_input_fixtures import document_bytes


def response():
    text = "Negotiate peace treaties between the frontend and backend teams."
    return {"extracted_skills":["peace treaties"],"matched_skills":[],"missing_skills":["peace treaties"],"match_score":0,
            "extraction_details":{"method":"trained","context_notice":"Review interpretations before updating the score.",
              "context_suggestions":[{"skill":"Conflict resolution","evidence":text,"start":0,"end":len(text),"similarity":0.55}]}}


@pytest.mark.parametrize("width", [320, 1440])
def test_context_choices_are_visible_review_only_and_use_analysis_snapshot(page, app_url, width):
    page.set_viewport_size({"width":width,"height":950})
    requests = []
    def preview(route):
        body = route.request.post_data_json
        requests.append(body)
        if "reviewed_job_skills" in body:
            result = {"extracted_skills":body["reviewed_job_skills"],"matched_skills":[],"missing_skills":body["reviewed_job_skills"],"match_score":0,"extraction_details":{"method":"reviewed"}}
        else:
            result = response()
        route.fulfill(json=result)
    page.route("**/api/preview", preview)
    page.goto(app_url)
    original = response()["extraction_details"]["context_suggestions"][0]["evidence"]
    page.locator("#job-description").fill(original)
    page.locator("#analyze-button").click()
    expect(page.locator("#context-review summary")).to_contain_text("1 suggestion")
    page.locator("#context-review summary").click()
    expect(page.locator("#context-suggestions")).to_contain_text(original)
    page.locator("#job-description").fill("Changed draft that has not been analyzed")
    page.get_by_role("button",name="Add Conflict resolution",exact=True).click()
    expect(page.locator("#reviewed-skills")).to_be_focused()
    expect(page.locator("#missing-skills .chip")).to_have_text(["peace treaties"])
    page.locator("#reviewed-skills").fill("Conflict resolution")
    page.locator("#update-analysis").click()
    expect(page.locator("#missing-skills .chip")).to_have_text(["Conflict resolution"])
    assert requests[0]["interpret_duties"] is True
    assert requests[-1]["job_description"] == original
    expect(page.locator("#context-review")).to_be_hidden()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_context_dismiss_and_literal_text(page, app_url):
    body = response()
    body["extraction_details"]["context_suggestions"][0]["evidence"] = '<img src=x onerror="window.bad=true">'
    page.route("**/api/preview", lambda route: route.fulfill(json=body))
    page.goto(app_url)
    page.locator("#job-description").fill("A sufficiently long job description")
    page.locator("#analyze-button").click()
    page.locator("#context-review summary").click()
    expect(page.locator("#context-suggestions img")).to_have_count(0)
    page.locator("#context-suggestions").get_by_role("button",name="Dismiss",exact=True).click()
    expect(page.locator("#reviewed-skills")).to_have_value("peace treaties")
    expect(page.locator("#context-suggestions")).to_contain_text("have not changed")


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
@pytest.mark.parametrize("format,media", [("PDF","application/pdf"),("PNG","image/png")])
def test_real_imports_can_suggest_duties_without_changing_scores(page, app_url, format, media):
    text = "Help colleagues resolve disagreements.\nBring competing departments together\naround a shared solution."
    page.goto(app_url)
    selector = "#job-pdf" if format == "PDF" else "#job-image"
    page.locator(selector).set_input_files({"name":f"duties.{format.lower()}","mimeType":media,"buffer":document_bytes(text,format)})
    expect(page.locator("#job-import-review")).to_be_visible(timeout=30000)
    page.locator("#apply-job-upload").click()
    imported = page.locator("#job-description").input_value()
    page.locator("#matching-method").select_option("exact")
    page.locator("#analyze-button").click()
    expect(page.locator("#context-review summary")).to_contain_text("suggestion",timeout=30000)
    page.locator("#context-review summary").click()
    add = page.locator("#context-suggestions").get_by_role("button",name="Add Conflict resolution",exact=True)
    expect(add).to_be_visible()
    before = page.locator("#missing-skills .chip").all_text_contents()
    add.click()
    expect(page.locator("#missing-skills .chip")).to_have_text(before)
    expect(page.locator("#job-description")).to_have_value(imported)


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
def test_both_typos_and_complete_phrase_in_real_browser(page, app_url):
    page.goto(app_url)
    page.locator("#job-description").fill("pasionate about work, and a hardworker. also need to be diligent with tasks and punctual.")
    page.locator("#matching-method").select_option("exact")
    page.locator("#analyze-button").click()
    checks = page.locator("#spelling-checks")
    expect(checks.get_by_role("button",name="Use passionate",exact=True)).to_be_visible(timeout=30000)
    checks.get_by_role("button",name="Use hard worker",exact=True).click()
    expect(page.locator("#reviewed-skills")).to_have_value(re.compile("hard worker"))
    page.locator("#update-analysis").click()
    expect(page.locator("#missing-skills")).to_contain_text("hard worker")
