"""Review-only capability retrieval using local embeddings and nearby duties.

The prototypes are project-authored capability descriptions. They are not
training labels, and similarity is not a probability or proof of a requirement.
"""

from functools import lru_cache
import re

import numpy as np

from backend.app.services.job_document import heading_kind
from backend.app.services.duty_scope import denied_duty, workplace_commentary
from backend.app.services.semantic_matcher import _load_model, _model_lock, ModelUnavailableError

CAPABILITIES = {
    "Programming": "Develop software applications. Write, maintain and refactor source code to implement features.",
    "Debugging": "Investigate software errors, diagnose failures, find root causes and fix bugs in applications.",
    "Software testing": "Test software behaviour, check edge cases and prevent regressions before releasing changes.",
    "Interface design": "Design usable screens, improve page layouts and refine buttons and visual interactions.",
    "Deployment": "Release software to staging and production environments and keep applications running reliably.",
    "Data analysis": "Interpret metrics, compare trends and investigate changes in measured performance using data.",
    "Marketing communication": "Explain product benefits convincingly, write promotional messages and build interest in a brand.",
    "Social media communication": "Create and publish engaging posts for social networks and communicate with online audiences.",
    "Presentation": "Prepare clear slides and deliver presentations that explain updates and ideas to an audience.",
    "Customer support": "Help customers use a product, answer questions and resolve their difficulties with the service.",
    "Written communication": "Write clear professional emails, adapt tone to the reader and explain information politely.",
    "Empathy": "Understand another person's feelings, acknowledge frustration and respond with care and patience.",
    "Conflict resolution": "Resolve disagreements between people or teams, mediate disputes and find common ground.",
    "Teamwork": "Coordinate work with colleagues, collaborate across teams and share responsibility for a common goal.",
    "Active listening": "Listen carefully to people's concerns, ask clarifying questions and understand what they need.",
    "Time management": "Prioritise competing tasks, organise work and meet deadlines with limited time.",
    "Attention to detail": "Check work carefully, notice small mistakes and maintain accurate consistent records.",
    "Problem solving": "Identify a problem, weigh possible solutions and choose practical steps to resolve it.",
    "Teaching": "Explain concepts to learners, demonstrate procedures and help others practise new skills.",
    "Negotiation": "Discuss terms with suppliers or clients, reconcile competing interests and reach an agreement.",
    "Planning": "Define project goals, plan tasks and resources, and track delivery against milestones.",
    "Research": "Find reliable information, compare sources and investigate questions before drawing conclusions.",
    "Adaptability": "Adjust to changing priorities, learn unfamiliar processes and respond constructively to new situations.",
    "Persistence": "Keep working through setbacks, sustain effort and follow through on difficult tasks.",
}
THRESHOLD = 0.43
EXAMPLES = {
    "Programming": "Write clean code, implement application features and improve existing software.",
    "Debugging": "Look up error messages to diagnose and fix software bugs.",
    "Software testing": "Reproduce unexpected results, create automated checks and verify fixes before they reach users.",
    "Interface design": "Improve the position of buttons, spacing and colours so people can use the website easily.",
    "Deployment": "Monitor production alerts, restore failed services and investigate application outages after releases.",
    "Data analysis": "Measure metrics and explain why the numbers go up and down.",
    "Marketing communication": "Persuade potential buyers that a product is valuable and communicate what makes it different.",
    "Social media communication": "Plan content for LinkedIn and other social channels, publish updates and engage followers.",
    "Presentation": "Turn product updates into slide decks, explain the main points and present them to stakeholders.",
    "Customer support": "Respond to customer complaints and guide people through practical steps to solve product issues.",
    "Written communication": "Respond to difficult emails with clear, calm and polite language suited to the recipient.",
    "Empathy": "Support upset people patiently, recognise their feelings and help them feel understood.",
    "Conflict resolution": "Help departments work through disagreements and bring opposing teams to an understanding.",
    "Teamwork": "Work with colleagues from different departments, exchange information and deliver shared tasks together.",
    "Active listening": "Hear people out, clarify their questions and check that their concerns are understood.",
    "Time management": "Balance deadlines and interruptions, decide what comes first and finish tasks on time.",
    "Attention to detail": "Spot inconsistencies in documents, verify small details and correct inaccurate entries.",
    "Problem solving": "Work out what is causing a difficulty and test different ways to address it.",
    "Teaching": "Guide new starters through a process and explain unfamiliar concepts step by step.",
    "Negotiation": "Agree contract prices and delivery terms that work for both parties.",
    "Planning": "Break a large project into manageable tasks and coordinate people, budgets and schedules.",
    "Research": "Search for evidence, compare trustworthy sources and summarise what has been learned.",
    "Adaptability": "Respond to a new process or changing instructions without losing focus on the goal.",
    "Persistence": "Stay committed when tasks become difficult and continue trying after setbacks.",
}
NOTICE = ("Possible skills suggested from the duties and surrounding role context. "
          "These are interpretations, not confirmed requirements. Check the supporting wording, "
          "especially jokes or sarcasm. Only your reviewed skill list affects the score.")
NEGATIVE = re.compile(r"\b(?:no|not|never|without|unnecessary|unneeded|isn't|isnt|don't|dont|doesn't|doesnt)\b", re.I)


def evidence_units(text: str) -> list[dict]:
    """Bound inference work; retain offsets and omit clearly unrelated sections."""
    units = []
    section = None
    offset = 0
    for line in text.splitlines(keepends=True):
        kind, _, inline = heading_kind(line)
        if kind:
            section = kind
        if section == "other":
            offset += len(line)
            continue
        line_units = []
        for match in re.finditer(r"[^.!?;,\n]+(?:[.!?;,]|$)", line):
            raw = match.group()
            value = raw.strip(" \t•-*\r\n")
            start = offset + match.start() + raw.find(value)
            if not 4 <= len(value.split()) <= 85 or len(value) > 500:
                continue
            sentence_start = max(line.rfind(mark, 0, match.start()) for mark in ".!?;") + 1
            sentence = line[sentence_start:match.end()].lstrip(" \t•-*")
            if denied_duty(sentence) or workplace_commentary(sentence):
                continue
            line_units.append({"text": value, "start": start, "end": start + len(value)})
        # Several short duties can all disappear when each comma fragment has
        # fewer than four words. Keep their sentence only when none survived;
        # otherwise retain the more precise original evidence passages.
        for match in re.finditer(r"[^.!?;\n]+(?:[.!?;]|$)", line):
            raw = match.group()
            value = raw.strip(" \t•-*\r\n")
            start = offset + match.start() + raw.find(value)
            end = start + len(value)
            if ("," not in value or not 4 <= len(value.split()) <= 85 or len(value) > 500
                or denied_duty(value) or workplace_commentary(value)
                or any(u["start"] < end and start < u["end"] for u in line_units)):
                continue
            line_units.append({"text": value, "start": start, "end": end})
        units.extend(sorted(line_units, key=lambda u:u["start"]))
        offset += len(line)
    # Spread the bounded sample across the document, rather than ignoring its end.
    if len(units) > 48:
        units = [units[int(i)] for i in np.linspace(0, len(units) - 1, 48)]
    return units


@lru_cache(maxsize=1)
def prototype_vectors():
    encoder, _, _ = _load_model()
    return np.array(list(encoder.embed([value for name in CAPABILITIES for value in
        (f"{name}: {CAPABILITIES[name]}", EXAMPLES[name])]))).reshape(len(CAPABILITIES), 2, -1)


def suggest_from_context(text: str, skills: list[str]) -> tuple[list[dict], str]:
    units = evidence_units(text)
    if not units:
        return [], NOTICE
    if not _model_lock.acquire(timeout=15):
        raise ModelUnavailableError("Context review is busy")
    try:
        encoder, _, _ = _load_model()
        prototypes = prototype_vectors()
        # The second view includes neighbouring duties. A pooled document view
        # carries context from the end as well as the title and first paragraph.
        windows = [" ".join(u["text"] for u in units[max(0, i - 1):i + 2]) for i in range(len(units))]
        vectors = np.array(list(encoder.embed([u["text"] for u in units] + windows, batch_size=32)))
        local, surrounding = vectors[:len(units)], vectors[len(units):]
        document = local.mean(axis=0)
        document /= max(float(np.linalg.norm(document)), 1e-8)
        local_scores = np.einsum("nd,ckd->nck", local, prototypes).max(axis=2)
        contextual_scores = np.einsum("nd,ckd->nck", surrounding, prototypes).max(axis=2)
        document_scores = np.einsum("d,ckd->ck", document, prototypes).max(axis=1)
        scores = 0.75 * local_scores + 0.15 * contextual_scores + 0.10 * document_scores
        for i, unit in enumerate(units):
            if (re.search(r"\b(?:official title|job title)\s*:", unit["text"], re.I)
                or (len(unit["text"].split()) <= 6 and "/" in unit["text"])):
                scores[i, :] = -1
        found = []
        known = {s.casefold() for s in skills}
        for j, skill in enumerate(CAPABILITIES):
            if skill.casefold() in known:
                continue
            i = int(np.argmax(scores[:, j]))
            score = float(scores[i, j])
            # A job title alone or diffuse document similarity is insufficient.
            threshold = 0.50 if skill == "Debugging" else THRESHOLD
            if score >= threshold and float(local_scores[i, j]) >= 0.40 and score >= float(scores[i].max()) - 0.04:
                found.append({"skill": skill, "evidence": units[i]["text"], "start": units[i]["start"],
                              "end": units[i]["end"], "similarity": round(score, 4)})
        return sorted(found, key=lambda item: (-item["similarity"], item["skill"]))[:6], NOTICE
    except ModelUnavailableError:
        raise
    except Exception as error:
        raise ModelUnavailableError("Context review could not run") from error
    finally:
        _model_lock.release()
