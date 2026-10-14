import pytest

from backend.app.services.job_document import prepare_job_document

POSTING = """About us
We build Java platforms.
Responsibilities
Build Python services and write SQL queries.
Required qualifications
Experience with Git.
Preferred qualifications
Docker experience is helpful.
Benefits
Java training allowance and paid leave.
How to apply
Apply through our React portal.
"""


def test_full_posting_keeps_required_and_preferred_skills():
    result = prepare_job_document(POSTING)
    assert result["selection_applied"]
    assert result["full_text"] == POSTING
    assert result["selected_sections"] == ["Responsibilities", "Required qualifications", "Preferred qualifications"]
    for phrase in ("Python", "SQL", "Git", "Docker"):
        assert phrase in result["text"]
    for phrase in ("Java", "React", "paid leave"):
        assert phrase not in result["text"]


@pytest.mark.parametrize("heading", ["REQUIREMENTS", "## Requirements", "2. Requirements:", "Requirements & qualifications", "What you’ll do", "What we're looking for"])
def test_heading_variations_and_case(heading):
    result = prepare_job_document(f"About us\nJava company\n{heading}\nPython skills\nBenefits\nPaid leave")
    assert result["selection_applied"]
    assert "Python" in result["text"] and "Java" not in result["text"]


@pytest.mark.parametrize("text", [
    "Python, SQL and team communication. Salary depends on experience.",
    "Benefits\nPaid leave and Python training.",
    "Requirements\nPython and SQL.",
    "About us\nJava platforms.\nRequirements\nBenefits\nPaid leave.",
    "We discuss benefits with customers and use Python.",
    "Descripción del puesto\nPython\nBeneficios\nCursos de Java",
])
def test_unclear_or_unneeded_selection_keeps_complete_original(text):
    result = prepare_job_document(text)
    assert not result["selection_applied"]
    assert result["text"] == result["full_text"] == text


@pytest.mark.parametrize("heading", ["SPECIAL CONDITIONS:", "Special Conditions", "# Special conditions"])
def test_inline_headings_and_unknown_sections_preserve_requirements(heading):
    text = f"Requirements: Python and SQL\nBenefits: Paid leave\n{heading}\nWeekend work and on-call support\nHow to apply: Email us"
    result = prepare_job_document(text)
    assert "Python and SQL" in result["text"]
    assert "Weekend work" in result["text"]
    assert "Paid leave" not in result["text"]
    assert "Email us" not in result["text"]


def test_selection_does_not_invent_or_expand_source_text():
    text = "Requirements\n" + "x" * 49940 + "\nBenefits\nPaid leave\n"
    result = prepare_job_document(text)
    assert len(result["text"]) <= len(text)
    assert result["text"] in text


@pytest.mark.parametrize("heading", ["Why you'll love it here", "Why you’ll love it here:",
    "Benefits that work for you", "Extra perks that matter"])
def test_conversational_posting_headings_keep_duties_and_exclude_perks(heading):
    from backend.app.services.context_suggestions import evidence_units
    text = ("About us\nOur software team builds Java services.\n"
            "What you'll be doing:\nWrite Python code for customer applications.\n"
            f"{heading}\nEnjoy optional presentation and negotiation classes.\n"
            "Who you are:\nYou can check records carefully and find mistakes.")
    selected = prepare_job_document(text)
    assert selected["selection_applied"] and selected["full_text"] == text
    assert "Python" in selected["text"] and "check records" in selected["text"]
    assert "Java" not in selected["text"] and "optional" not in selected["text"]
    units = evidence_units(text)
    assert all("optional" not in u["text"] and "Java" not in u["text"] for u in units)
    assert all(text[u["start"]:u["end"]] == u["text"] for u in units)
