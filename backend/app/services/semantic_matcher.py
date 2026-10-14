"""Use local sentence embeddings to match short skill descriptions."""

from functools import lru_cache
import json
import re
from threading import Lock

import numpy as np

from backend.app.core.config import get_settings
from backend.app.services.model_assets import MODEL_FILES, MODEL_NAME, MODEL_REVISION
from backend.app.services.scorer import MatchResult, analyze_skill_match
from backend.app.services.skill_extractor import SKILL_ALIASES, canonicalize_skill

# One prototype per skill keeps the mapping small and inspectable.
SKILL_DESCRIPTIONS = {
    "Docker": "Docker: building and running software containers",
    "FastAPI": "FastAPI: developing Python web APIs with FastAPI",
    "Git": "Git: version control, branches, commits and merging source code",
    "HTML": "HTML: creating web page structure using markup and tags",
    "CSS": "CSS: styling web pages with stylesheets, layouts and selectors",
    "Java": "Java: developing applications in the Java programming language",
    "JavaScript": "JavaScript: scripting interactive web pages in the browser",
    "Linux": "Linux: administering Linux systems with shell commands",
    "PostgreSQL": "PostgreSQL: managing and querying PostgreSQL databases",
    "Python": "Python: programming, automation and scripting in Python",
    "React": "React: building web interfaces with React components and hooks",
    "SQL": "SQL: writing database queries, joins and relational data queries",
    "TypeScript": "TypeScript: writing statically typed JavaScript applications",
    "Node.js": "Node.js: building server applications with the Node.js runtime",
    "Django": "Django: building Python web applications using Django",
    "Kubernetes": "Kubernetes: orchestrating, deploying and scaling container workloads",
    "Machine Learning": "Machine learning: training predictive models from data",
    "Natural Language Processing": "Natural language processing: analyzing human language and text",
}
SIMILARITY_THRESHOLD = 0.70
SIMILARITY_MARGIN = 0.08
_model_lock = Lock()


def eligible_semantic_phrase(phrase: str) -> bool:
    # Explicit denials should never add skills to the matched list.
    return bool(phrase.strip()) and not re.search(
        r"\b(no|not|never|without|lack|lacking)\b", phrase, re.IGNORECASE,
    )


class ModelUnavailableError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load_model():
    from fastembed import TextEmbedding

    path = get_settings().semantic_model_path.resolve()
    if not all((path / filename).is_file() for filename in (*MODEL_FILES, "revision.json")):
        raise ModelUnavailableError("The local matching model has not been installed")
    revision = json.loads((path / "revision.json").read_text(encoding="utf-8"))
    if revision.get("revision") != MODEL_REVISION:
        raise ModelUnavailableError("The local matching model revision does not match")
    encoder = TextEmbedding(
        model_name=MODEL_NAME,
        specific_model_path=str(path),
        local_files_only=True,
        threads=2,
        providers=["CPUExecutionProvider"],
    )
    names = list(SKILL_DESCRIPTIONS)
    vectors = np.array(list(encoder.embed(list(SKILL_DESCRIPTIONS.values()))))
    return encoder, names, vectors


def rank_skills(phrases: list[str]) -> list[list[tuple[str, float]]]:
    """Rank the entire catalog, not just the skills mentioned in the current job."""
    if not phrases:
        return []
    if not _model_lock.acquire(timeout=15):
        raise ModelUnavailableError("The local matching model is busy")
    try:
        encoder, names, catalog = _load_model()
        vectors = np.array(list(encoder.embed(phrases, batch_size=32)))
        similarities = np.clip(vectors @ catalog.T, -1.0, 1.0)
        return [
            sorted(zip(names, map(float, row)), key=lambda item: item[1], reverse=True)
            for row in similarities
        ]
    except ModelUnavailableError:
        raise
    except Exception as error:
        raise ModelUnavailableError("The local matching model could not run") from error
    finally:
        _model_lock.release()


def analyze_semantic_match(
    extracted_skills: list[str], user_skills: list[str],
) -> tuple[MatchResult, dict]:
    baseline = analyze_skill_match(extracted_skills, user_skills)
    # Exact known skills must not become different technologies through similarity.
    phrases = [
        skill for skill in user_skills
        if canonicalize_skill(skill) not in SKILL_ALIASES
        and eligible_semantic_phrase(skill)
    ]
    evidence: dict[str, dict] = {}
    if extracted_skills and phrases:
        for phrase, ranking in zip(phrases, rank_skills(phrases)):
            skill, similarity = ranking[0]
            margin = similarity - ranking[1][1]
            if (
                skill in baseline["missing_skills"]
                and similarity >= SIMILARITY_THRESHOLD
                and margin >= SIMILARITY_MARGIN
                and similarity > evidence.get(skill, {}).get("similarity", -1)
            ):
                evidence[skill] = {
                    "skill": skill,
                    "user_skill": phrase,
                    "similarity": round(similarity, 4),
                }
    matched = [
        skill for skill in extracted_skills
        if skill in baseline["matched_skills"] or skill in evidence
    ]
    result: MatchResult = {
        "matched_skills": matched,
        "missing_skills": [skill for skill in extracted_skills if skill not in matched],
        "match_score": round(len(matched) / len(extracted_skills) * 100) if extracted_skills else 0,
    }
    details = {
        "method": "semantic",
        "model": MODEL_NAME,
        "revision": MODEL_REVISION,
        "threshold": SIMILARITY_THRESHOLD,
        "margin": SIMILARITY_MARGIN,
        "exact_match_score": baseline["match_score"],
        "semantic_matches": [evidence[skill] for skill in extracted_skills if skill in evidence],
    }
    return result, details
