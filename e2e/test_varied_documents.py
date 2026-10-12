import os
import re

import pytest
from playwright.sync_api import Page, expect

from backend.tests.varied_input_fixtures import DOCUMENT_CASES, FORMATS, REVIEW_CORRECTIONS, document_bytes


@pytest.mark.skipif(os.getenv("RUN_CONTEXTUAL_TESTS") != "1", reason="Requires contextual weights")
@pytest.mark.parametrize("format,media", FORMATS)
@pytest.mark.parametrize("name,text,expected", DOCUMENT_CASES[:2], ids=[case[0] for case in DOCUMENT_CASES[:2]])
def test_real_upload_review_and_trained_scoring(page: Page, app_url: str, name, text, expected, format, media):
    page.goto(app_url)
    field = "#job-pdf" if format == "PDF" else "#job-image"
    page.locator(field).set_input_files({"name": f"{name}.{format.lower()}", "mimeType": media,
                                        "buffer": document_bytes(text, format)})
    expect(page.locator("#job-import-review")).to_be_visible(timeout=30000)
    expect(page.locator("#job-description")).to_have_value("")
    expect(page.locator("#import-warning")).to_contain_text("mistakes or miss lines")
    reviewed = page.locator("#job-import-text").input_value()
    if name == "full-posting":
        assert "Java" not in reviewed
        page.locator("#original-job-document summary").click()
        page.locator("#use-full-job-text").click()
        expect(page.locator("#job-import-text")).to_have_value(re.compile("Java"))
        page.locator("#use-selected-job-text").click()
        expect(page.locator("#job-import-text")).to_have_value(reviewed)
    correction = REVIEW_CORRECTIONS.get((name, format))
    if correction is not None:
        # Real compressed images can omit spaces/headings. The user can repair
        # the imported text before it becomes the job description or a score.
        page.locator("#job-import-text").fill(correction)
        reviewed = correction
    page.locator("#apply-job-upload").click()
    expect(page.locator("#job-description")).to_have_value(reviewed)
    page.locator("#user-skills").fill(expected[0])
    page.locator("#matching-method").select_option("exact")
    page.locator("#analyze-button").click()
    expect(page.locator("#matched-skills .chip")).to_have_text([expected[0]], timeout=30000)
    expect(page.locator("#missing-skills .chip")).to_have_text(expected[1:])
    expect(page.locator("#match-score")).to_have_text("25%")
    page.locator("#skill-review summary").click()
    expect(page.locator("#reviewed-skills")).to_have_value("\n".join(expected))
