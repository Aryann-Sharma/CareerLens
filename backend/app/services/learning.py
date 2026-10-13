"""Reviewed learning guides and prerequisite ordering, separate from fit scoring."""

import hashlib
import json

from backend.app.services.skill_extractor import canonicalize_skill
from backend.app.services.skill_spelling import spelling_checks

CHECKED_ON = "2026-10-13"


def guide(skill, prerequisites, goal, milestones, project, resource, url, note=""):
    return {"skill": skill, "prerequisites": prerequisites, "goal": goal,
            "milestones": milestones, "project": project, "note": note,
            "resources": [{"title": resource, "url": url}], "checked_on": CHECKED_ON,
            "available": True}


# These are suggested starting sequences, not a complete curriculum or job requirements.
GUIDES = {item["skill"]: item for item in [
    guide("HTML", [], "Structure an accessible web page.",
          ["Use headings, landmarks, lists, and meaningful links.", "Build a labelled form with helpful validation messages.", "Check keyboard navigation and document structure."],
          "Create a profile page with a contact form; explain the purpose of each element.",
          "MDN web development curriculum", "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core"),
    guide("CSS", ["HTML"], "Make layouts work on small and large screens.",
          ["Explain the box model, cascade, and selectors.", "Build layouts with Flexbox or Grid.", "Check narrow screens, zoom, contrast, and visible focus."],
          "Style your profile page at phone and desktop widths without horizontal scrolling.",
          "MDN web development curriculum", "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core"),
    guide("JavaScript", ["HTML"], "Add behavior to a web page and handle errors.",
          ["Practice variables, functions, arrays, and objects.", "Use DOM events and validate user input.", "Handle a request with loading, success, and failure states."],
          "Build a searchable list that stays usable when a request fails.",
          "MDN web development curriculum", "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core",
          "This guide follows a browser-based route; JavaScript is also used outside browsers."),
    guide("TypeScript", ["JavaScript"], "Use types to catch mistakes before running code.",
          ["Describe objects, function arguments, and return values.", "Use unions and narrow unknown values safely.", "Enable strict checks and fix errors without bypassing types."],
          "Convert a small JavaScript app and validate data received from a server.",
          "TypeScript Handbook", "https://www.typescriptlang.org/docs/handbook/intro.html"),
    guide("React", ["JavaScript", "CSS"], "Build a small interface with reusable components.",
          ["Split a page into components with clear props.", "Manage input, state, and derived values.", "Test user interactions and empty or error states."],
          "Build a task board with filters and an accessible edit form.",
          "React Learn", "https://react.dev/learn"),
    guide("Node.js", ["JavaScript"], "Write a server-side JavaScript application.",
          ["Use modules, packages, and environment settings.", "Handle asynchronous operations and errors.", "Validate requests and test successful and failing responses."],
          "Build a small notes service with input validation and automated request tests.",
          "Node.js introduction", "https://nodejs.org/learn/getting-started/introduction-to-nodejs"),
    guide("Python", [], "Write clear programs that process data reliably.",
          ["Practice functions, collections, loops, and exceptions.", "Read files and separate reusable code into modules.", "Test normal inputs, empty data, and invalid values."],
          "Build a command-line expense tracker with file storage and tests.",
          "Python getting started", "https://www.python.org/about/gettingstarted/",
          "Start with the beginner resources if programming is new to you."),
    guide("Java", [], "Build a small application using Java's core language and libraries.",
          ["Practice control flow, methods, classes, and objects.", "Use collections and handle exceptions.", "Test expected behavior and invalid input; explain your design."],
          "Build a library lending application with search, borrowing, and overdue checks.",
          "Learn Java", "https://dev.java/learn/"),
    guide("SQL", [], "Ask useful questions of a relational database.",
          ["Filter, sort, and aggregate rows.", "Join tables and handle missing values correctly.", "Use keys and constraints; verify results against a small known dataset."],
          "Model orders and customers, then write and check five business queries.",
          "PostgreSQL SQL tutorial", "https://www.postgresql.org/docs/current/tutorial.html",
          "The exercises use PostgreSQL. SQL dialects differ between database systems."),
    guide("PostgreSQL", ["SQL"], "Use PostgreSQL to store and query application data.",
          ["Create a schema with keys, constraints, and migrations.", "Use transactions and inspect a query plan.", "Practice backup and restore on a disposable database."],
          "Add a database to a small app and demonstrate a tested migration and restore.",
          "PostgreSQL tutorial", "https://www.postgresql.org/docs/current/tutorial.html"),
    guide("Git", [], "Keep a readable history of changes and collaborate safely.",
          ["Inspect changes and create focused commits.", "Work on branches and resolve a practice conflict.", "Review a diff and safely undo a local mistake."],
          "Maintain a project with clear commits and a documented contribution workflow.",
          "Pro Git book", "https://git-scm.com/book/en/v2"),
    guide("Linux", [], "Navigate and work safely in a command-line environment.",
          ["Navigate files and understand paths and permissions.", "Use pipes, search tools, and environment variables.", "Inspect processes and logs in a disposable practice environment."],
          "Write a script that summarizes application logs and handles missing files.",
          "Ubuntu command-line tutorial", "https://ubuntu.com/tutorials/command-line-for-beginners"),
    guide("Docker", ["Linux"], "Package a small application in a reproducible container.",
          ["Explain images, containers, ports, and volumes.", "Build an image and configure a local service.", "Check logs, persistence, and graceful shutdown."],
          "Containerize an existing app and document how someone else can run it locally.",
          "Docker getting started", "https://docs.docker.com/get-started/",
          "Use local exercises; hosted services and some product plans may charge separately."),
    guide("Kubernetes", ["Docker"], "Understand the basics of running containers in a cluster.",
          ["Explain pods, deployments, and services.", "Deploy and inspect a small app in a local practice cluster.", "Practice a rollout, rollback, and a failing health check."],
          "Run a sample app locally and document recovery from a failed deployment.",
          "Kubernetes Basics", "https://kubernetes.io/docs/tutorials/kubernetes-basics/",
          "A local cluster needs sufficient memory. Cloud clusters can incur costs."),
    guide("FastAPI", ["Python"], "Build and test an HTTP API with validated inputs.",
          ["Define routes and request and response schemas.", "Use dependencies and return useful validation errors.", "Test success, invalid input, and unauthorized requests."],
          "Build a task API with documentation and tests for each endpoint.",
          "FastAPI tutorial", "https://fastapi.tiangolo.com/tutorial/"),
    guide("Django", ["Python"], "Build a database-backed web application.",
          ["Connect URLs, views, and templates.", "Create models and apply migrations.", "Validate forms and test permissions and common user journeys."],
          "Build an event planner with private accounts and tested editing permissions.",
          "Django first application tutorial", "https://docs.djangoproject.com/en/stable/intro/tutorial01/"),
    guide("Machine Learning", ["Python"], "Evaluate a small supervised model against a baseline.",
          ["Review basic statistics, arrays, and data cleaning.", "Separate training, validation, and test data before fitting.", "Compare a baseline, inspect errors, and report limitations."],
          "Train a classifier on a licensed labelled dataset and publish a reproducible evaluation.",
          "scikit-learn getting started", "https://scikit-learn.org/stable/getting_started.html",
          "This resource assumes basic modelling knowledge; review probability and linear algebra first."),
    guide("Natural Language Processing", ["Machine Learning"], "Process text and evaluate a small language task.",
          ["Explore tokenization and text normalization.", "Build a text classification or tagging baseline.", "Evaluate unseen examples, typos, and domain changes."],
          "Build a small text classifier with source attribution and a documented error analysis.",
          "NLTK book", "https://www.nltk.org/book/",
          "The book covers foundational methods; library examples may need version adjustments."),
]}

DIRECTIONS = {
    "web": {"title": "Web development: browser foundations", "skills": ["HTML", "CSS", "JavaScript", "Git"]},
    "java": {"title": "Application development with Java", "skills": ["Java", "SQL", "Git"]},
    "python": {"title": "Web services with Python", "skills": ["Python", "SQL", "FastAPI", "Git"]},
    "data": {"title": "Data and modelling foundations", "skills": ["Python", "SQL", "Machine Learning", "Git"]},
    "database": {"title": "Relational databases", "skills": ["SQL", "PostgreSQL", "Git"]},
    "infrastructure": {"title": "Containers and infrastructure", "skills": ["Linux", "Docker", "Git"]},
}


def get_guide(skill: str) -> dict:
    canonical = canonicalize_skill(skill)
    if canonical in GUIDES:
        return GUIDES[canonical]
    suggestions = list(dict.fromkeys(candidate for check in spelling_checks(skill)
                                     for candidate in check["candidates"] if candidate in GUIDES))
    return {"skill": skill, "available": False, "suggestions": suggestions,
            "goal": "Define what this skill means for the role before choosing a course.",
            "prerequisites": [], "resources": [], "checked_on": None,
            "milestones": ["Write a concrete example of this skill used at work.",
                           "Choose a small practice task with a clear success criterion.",
                           "Complete the task, seek feedback, and record what to improve."],
            "project": "Keep a short record of the task, your approach, and the result.",
            "note": "No reviewed learning guide is available for this phrase. Check its wording in the skills review."}


def build_plan(missing: list[str], known: list[str], direction: str | None) -> dict:
    known_keys = {canonicalize_skill(skill).casefold() for skill in known}
    roots = {}
    for skill in missing:
        name = canonicalize_skill(skill)
        if name.casefold() not in known_keys:
            roots.setdefault(name.casefold(), (name, "From your analysis"))
    if direction:
        for name in DIRECTIONS[direction]["skills"]:
            if name.casefold() not in known_keys:
                roots.setdefault(name.casefold(), (name, "Suggested for your direction"))
    steps, seen = [], set()

    def visit(name):
        key = name.casefold()
        if key in seen or key in known_keys:
            return
        seen.add(key)
        item = get_guide(name)
        for prerequisite in item["prerequisites"]:
            visit(prerequisite)
        steps.append({**item, "reason": roots.get(key, (name, "Suggested foundation"))[1]})

    for name, _ in roots.values():
        visit(name)
    plan = {"direction": direction, "direction_title": DIRECTIONS[direction]["title"] if direction else "Skills from your analysis", "steps": steps,
            "notice": "This is a starting plan, not a list of extra job requirements. It does not change your fit score. Skip foundations you already know; completing a checklist does not certify proficiency."}
    plan["revision"] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()[:16]
    return plan
