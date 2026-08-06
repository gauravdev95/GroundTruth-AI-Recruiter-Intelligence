"""Skill detection against a canonical vocabulary.

Category classification is NOT redone here — `verification/skills.py::
guess_category` already owns that, and it is what repository technology
detection uses. This module's job is narrower and different: turn the
surface forms a human writes on a resume ("ReactJS", "react.js", "React 18")
into the one canonical name the rest of the platform stores, so that a skill
claimed on a resume and the same skill detected in a `package.json` land on
the same `skills` row rather than two near-duplicates.

WHY CANONICALISATION IS THE WHOLE POINT

`matching/scoring.py` averages `evidence_weight` across the skills a job
requires, matching by case-folded name. If a resume contributes "ReactJS"
and a verified repository contributes "React", the candidate holds two
skills with half the evidence each and matches a "React" requirement with
neither. Canonicalising at the point of extraction is the cheapest place to
prevent that, and the only place that sees the raw surface form at all.

THE SHORT-NAME PROBLEM

"R", "Go", "C", and "D" are real language names and also extremely common
English words or letters. Matching them by substring produces a skill list
where every student knows R (from "R&D"), Go (from "Go-to-market") and C
(from a middle initial). They are gated behind `_SHORT_NAMES` below, which
requires either an exact standalone token in a skills section or an
adjacent corroborating token. Getting this wrong is not a small error — it
puts a fabricated language on a student's verified profile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.domains.resume.extraction.confidence import Provenance, Scored

#: Canonical name → the surface forms that mean it.
#:
#: Deliberately not exhaustive. This table covers what appears on student
#: resumes in this product's market; anything outside it still reaches the
#: profile through the LLM fallback or through the student typing it, and
#: both of those paths are visible on the review screen. An enormous
#: auto-generated vocabulary would raise recall and destroy precision, and
#: precision is what a *verified* profile is selling.
#:
#: Surface forms are matched case-insensitively after punctuation folding, so
#: "Node.js", "nodejs" and "node js" all reach one entry without three keys.
_VOCABULARY: dict[str, tuple[str, ...]] = {
    # languages
    "Python": ("python", "python3"),
    "JavaScript": ("javascript", "js", "es6", "ecmascript"),
    "TypeScript": ("typescript", "ts"),
    "Java": ("java",),
    "C++": ("c++", "cpp", "cplusplus"),
    "C#": ("c#", "csharp"),
    "C": ("c",),
    "Go": ("go", "golang"),
    "Rust": ("rust",),
    "Ruby": ("ruby",),
    "PHP": ("php",),
    "Swift": ("swift",),
    "Kotlin": ("kotlin",),
    "Scala": ("scala",),
    "R": ("r",),
    "MATLAB": ("matlab",),
    "Dart": ("dart",),
    "SQL": ("sql",),
    "HTML": ("html", "html5"),
    "CSS": ("css", "css3"),
    "Shell": ("bash", "shell", "shell scripting", "zsh"),
    # frontend
    # "react.js" is listed explicitly: `_fold` preserves dots (removing them
    # would collapse Node.js into Node and C++ into C), so the dotted form is
    # a distinct key rather than one the folder normalises away.
    "React": ("react", "reactjs", "react.js", "react native"),
    "Next.js": ("next.js", "nextjs"),
    "Vue.js": ("vue", "vuejs", "vue.js"),
    "Angular": ("angular", "angularjs"),
    "Svelte": ("svelte", "sveltekit"),
    "Redux": ("redux",),
    "Tailwind CSS": ("tailwind", "tailwindcss", "tailwind css"),
    "Bootstrap": ("bootstrap",),
    "jQuery": ("jquery",),
    # backend
    "Node.js": ("node", "nodejs", "node.js"),
    "Express.js": ("express", "expressjs", "express.js"),
    "Django": ("django",),
    "Flask": ("flask",),
    "FastAPI": ("fastapi", "fast api"),
    "Spring Boot": ("spring", "spring boot", "springboot"),
    "Laravel": ("laravel",),
    "Rails": ("rails", "ruby on rails"),
    "GraphQL": ("graphql",),
    "REST APIs": ("rest", "rest api", "restful", "rest apis"),
    "gRPC": ("grpc",),
    # data
    "PostgreSQL": ("postgresql", "postgres", "psql"),
    "MySQL": ("mysql",),
    "MongoDB": ("mongodb", "mongo"),
    "Redis": ("redis",),
    "SQLite": ("sqlite",),
    "Elasticsearch": ("elasticsearch", "elastic search"),
    "Firebase": ("firebase",),
    "Supabase": ("supabase",),
    "Kafka": ("kafka", "apache kafka"),
    # ml
    "TensorFlow": ("tensorflow", "tensor flow"),
    "PyTorch": ("pytorch", "torch"),
    "scikit-learn": ("scikit-learn", "sklearn", "scikit learn"),
    "Pandas": ("pandas",),
    "NumPy": ("numpy",),
    "OpenCV": ("opencv", "open cv"),
    "Keras": ("keras",),
    "Hugging Face": ("hugging face", "huggingface", "transformers"),
    "LangChain": ("langchain", "lang chain"),
    # infra
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure", "microsoft azure"),
    "GCP": ("gcp", "google cloud", "google cloud platform"),
    "Terraform": ("terraform",),
    "Jenkins": ("jenkins",),
    "GitHub Actions": ("github actions",),
    "CI/CD": ("ci/cd", "cicd", "ci cd", "continuous integration"),
    "Nginx": ("nginx",),
    "Linux": ("linux", "unix"),
    "Git": ("git",),
    # practice
    "Machine Learning": ("machine learning", "ml"),
    "Deep Learning": ("deep learning", "dl"),
    "NLP": ("nlp", "natural language processing"),
    "Computer Vision": ("computer vision", "cv"),
    "Data Structures": ("data structures", "dsa", "data structures and algorithms"),
    "Algorithms": ("algorithms",),
    "System Design": ("system design",),
    "Agile": ("agile", "scrum"),
    "Figma": ("figma",),
}

#: Canonical names whose surface forms are too short or too word-like to
#: match by substring. See the module docstring.
_SHORT_NAMES = frozenset({"C", "R", "Go", "D", "C#", "CV", "ML", "DL", "TS", "JS"})

#: Tokens that, when adjacent to a short name, corroborate it as a skill.
#: "C, C++, Java" corroborates C; "R&D" does not.
_SKILL_CONTEXT = frozenset(
    {
        "programming", "language", "languages", "proficient", "familiar",
        "experienced", "skills", "coding", "development",
    }
)

#: Built once at import. Maps a folded surface form to its canonical name.
#: A plain dict lookup on the folded token is what makes detection linear in
#: document length rather than in vocabulary size — a regex alternation over
#: ~400 surface forms was measurably slower and no more accurate.
_SURFACE_TO_CANONICAL: dict[str, str] = {}
for _canonical, _forms in _VOCABULARY.items():
    for _form in _forms:
        # Later entries must not silently overwrite earlier ones: "cv" means
        # both Computer Vision and curriculum vitae, and "ml"/"dl" are
        # ambiguous too. First registration wins, and the vocabulary is
        # ordered so the intended meaning is registered first.
        _SURFACE_TO_CANONICAL.setdefault(_form, _canonical)

#: Longest surface form in tokens. Bounds the n-gram window so "amazon web
#: services" is found without scanning every possible span.
_MAX_NGRAM = max(len(form.split()) for forms in _VOCABULARY.values() for form in forms)


def _fold(token: str) -> str:
    """Case-fold and strip decoration, preserving the characters that
    distinguish real skills from each other.

    `+`, `#` and `.` survive because removing them collapses C++ into C,
    C# into C, and Node.js into Node — three distinct skills becoming one.
    """
    return re.sub(r"[^\w+#.\-/]", "", token).strip(".-/").casefold()


def _tokenise(text: str) -> list[str]:
    """Split on separators resumes use between skills.

    Commas, pipes, slashes, bullets and semicolons are all list separators in
    practice. Whitespace alone is not enough because "React, Node.js, Docker"
    is one whitespace-delimited run in some extracted PDFs.
    """
    return [token for token in re.split(r"[,\|;·•\n\t]+|\s{2,}|\s", text) if token.strip()]


@dataclass(frozen=True)
class DetectedSkill:
    canonical: str
    #: Exactly as the student wrote it. Shown on the review screen so they
    #: can see *why* a skill was attributed, and kept out of storage.
    surface: str
    scored: Scored[str]


def detect_skills(
    text: str, *, in_skills_section: bool, evidence: str = ""
) -> list[DetectedSkill]:
    """Find canonical skills in one block of text.

    `in_skills_section` is the structural signal and it changes two things:
    provenance (STRUCTURAL vs PATTERN), and whether short names are admitted
    at all. A "C" token inside a Technical Skills list is a language; the
    same token in a project description is a letter.

    Returns at most one entry per canonical name, keeping the first surface
    form seen — a resume listing "React" three times is one skill.
    """
    tokens = _tokenise(text)
    folded = [_fold(token) for token in tokens]

    found: dict[str, DetectedSkill] = {}

    for position in range(len(tokens)):
        # Longest n-gram first, so "amazon web services" is matched as one
        # skill rather than yielding a spurious "Amazon" plus "Services".
        for size in range(min(_MAX_NGRAM, len(tokens) - position), 0, -1):
            window = " ".join(part for part in folded[position : position + size] if part)
            if not window:
                continue

            canonical = _SURFACE_TO_CANONICAL.get(window)
            if canonical is None:
                continue
            if canonical in found:
                break

            if canonical in _SHORT_NAMES:
                if not in_skills_section:
                    break
                neighbourhood = {
                    *folded[max(0, position - 3) : position],
                    *folded[position + size : position + size + 3],
                }
                # Admitted either because a neighbouring word is skill
                # vocabulary, or because a neighbouring token is itself a
                # recognised skill — "C, C++, Java" corroborates via the
                # latter, which is by far the common case in a skills list.
                corroborated = bool(neighbourhood & _SKILL_CONTEXT) or any(
                    _SURFACE_TO_CANONICAL.get(other) for other in neighbourhood if other
                )
                if not corroborated:
                    break

            surface = " ".join(tokens[position : position + size]).strip(" ,;|")
            found[canonical] = DetectedSkill(
                canonical=canonical,
                surface=surface,
                scored=Scored(
                    value=canonical,
                    provenance=Provenance.STRUCTURAL if in_skills_section else Provenance.PATTERN,
                    evidence=evidence
                    or (
                        "Listed in a skills section"
                        if in_skills_section
                        else "Mentioned in body text"
                    ),
                ),
            )
            break

    return list(found.values())


def canonicalise(name: str) -> str:
    """Map one free-typed skill name to its canonical form.

    Used on the confirmation path when a student adds a skill by hand, so a
    typed "reactjs" merges with the extracted "React" instead of creating a
    second `skills` row. Unknown names pass through with their original
    casing preserved — an unrecognised skill is not an invalid one, and
    lowercasing it would make the student's own profile look sloppy.
    """
    return _SURFACE_TO_CANONICAL.get(_fold(name), name.strip())
