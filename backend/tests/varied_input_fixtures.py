"""Repeatable varied inputs for extraction and complete document workflows."""

import random

from backend.tests.image_fixtures import make_image
from backend.tests.pdf_fixtures import make_pdf


SCREENSHOT_TEXT = "we want a diligent team worker, who is also very passionate and a hard-worker."
SCREENSHOT_SKILLS = ["diligent", "team worker", "passionate", "hard-worker"]
DOCUMENT_CASES = [
    ("soft-skills", SCREENSHOT_TEXT, SCREENSHOT_SKILLS),
    ("full-posting", "About us\nWe build Java tools.\nRequirements\nPython, SQL and Git\n"
     "Preferred skills\nDocker\nBenefits\nPaid leave", ["Python", "SQL", "Git", "Docker"]),
    ("case-and-typos", "Required skills\npYtHoN, javscript and postgressql", ["Python", "JavaScript", "PostgreSQL"]),
    ("numbered-list", "Required skills\n1. team worker\n2. diligent\n3. attention to detail",
     ["team worker", "diligent", "attention to detail"]),
]
FORMATS = [("PDF", "application/pdf"), ("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp")]
# These compressed fixtures lose shorter spaces or a heading in the bundled OCR.
# Exercise the correction workflow explicitly instead of claiming perfect OCR.
REVIEW_CORRECTIONS = {
    ("full-posting", "JPEG"): "Requirements\nPython, SQL and Git\nPreferred skills\nDocker",
    ("full-posting", "WEBP"): "Requirements\nPython, SQL and Git\nPreferred skills\nDocker",
    ("numbered-list", "JPEG"): "Required skills\n1. team worker\n2. diligent\n3. attention to detail",
}


def document_bytes(text, format):
    if format == "PDF":
        return make_pdf(text, laid_out=True)
    options = {"quality": 65} if format == "JPEG" else {}
    return make_image(text, format=format, size=(1500, 650), **options)


def varied_descriptions():
    rng = random.Random(20261012)
    names = ["Python", "SQL", "Git", "Java", "JavaScript", "TypeScript", "Docker", "Kubernetes",
             "HTML", "CSS", "React", "Node.js", "FastAPI", "Django", "Linux", "PostgreSQL"]
    templates = [
        "We require {skills}.", "Required skills:\n{lines}", "You should have experience with {skills}.",
        "Our next developer will build internal tools.\nRequirements:\n{lines}\nBenefits:\nPaid leave",
    ]
    cases = []
    for index in range(32):
        selected = rng.sample(names, rng.randint(2, 6))
        shown = [rng.choice([str.lower, str.upper, lambda s: s])(skill) for skill in selected]
        text = templates[index % len(templates)].format(skills=", ".join(shown), lines="\n".join("- " + s for s in shown))
        if index % 5 == 0:
            text = text.replace("\n", "\r\n")
        cases.append((text, selected, selected[::2]))
    return cases
