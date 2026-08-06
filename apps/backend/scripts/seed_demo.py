"""The scripted demo cohort: one recruiter, ten students, one open role.

Separate from `seed.py`'s original fixture because the two answer different
questions. That one exercises *states* — a rejected claim, a pending repo, a
half-finished profile — and its personas are deliberately uneven. This one
exercises the *end-to-end hiring flow* on a cohort dense enough that a
recruiter opening the pipeline sees a real spread of real candidates.

Both run from `make seed`, each behind its own marker check, so having run
one before does not prevent the other from appearing.

## Three constraints this data is shaped by, all enforced elsewhere

1. **`experience_level` is `mid`, not `senior`, on a role titled "Senior
   Backend Engineer".** `matching/service.py::_graduation_year_window`
   returns `None` for `SENIOR` — no student on this platform reports years of
   professional experience, so a `senior` posting is eligible to *nobody* and
   its pipeline renders empty. The title is free text and says what the
   recruiter means; the enum is a matching input and says what the matcher can
   act on. Changing the enum to `senior` to make the two agree would silently
   empty the demo.

2. **The role is remote.** A non-remote job filters candidates by a substring
   of `job.location`, and this cohort is spread across eight cities. Remote is
   also just true of the role as written.

3. **Every skill named in `DEMO_JOB` is a skill some candidate actually
   holds.** `skill_evidence` is a quarter of the score and averages over the
   job's *required* skills, so a requirement nobody holds drags the whole
   pool toward the threshold rather than discriminating between candidates.

## Why the score spread comes out where it does

Nothing here writes a `match_score`. Scores are computed by the real
`matching/scoring.py` from five weighted terms, so the spread is a
*consequence* of the evidence below, not a target typed into a column. What
is deliberate is the evidence: Rahul and Roshni hold all three required
skills with strong repository backing; Ananya and Aditya hold none of them
and fall under `MATCH_THRESHOLD` entirely, which is what makes them the two
who never appear on the board.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from scripts import seed_helpers as helpers
from src.domains.auth.models import User
from src.domains.skills.models import ProficiencyLevel, SkillCategory
from src.domains.student.models import CodingPlatform, EmploymentType, VerificationStatus

#: NOT the brief's `test1234`, which this platform's own signup rejects:
#: `auth/schemas.py::_validate_password_strength` requires an uppercase
#: letter and a special character, and `test1234` has neither. The options
#: were to weaken a password policy on a hiring platform holding student PII,
#: or to move two characters in a demo credential. This is the two characters.
#: The login screen's test-credentials panel reads this constant, so the value
#: on screen cannot drift from the value that works.
DEMO_PASSWORD = "Test1234!"
DEMO_RECRUITER_EMAIL = "recruiter@test.com"
#: Presence of this account means the demo cohort is already seeded.
DEMO_MARKER_EMAIL = "rahul@test.com"

#: Skill rows are shared across the whole platform, so the demo taxonomy is
#: declared once here and get-or-created. Categories match how the skill is
#: actually used, which is what the recruiter's requirement editor groups by.
SKILL_CATALOGUE: dict[str, SkillCategory] = {
    "Rust": SkillCategory.LANGUAGE,
    "Go": SkillCategory.LANGUAGE,
    "Java": SkillCategory.LANGUAGE,
    "Python": SkillCategory.LANGUAGE,
    "TypeScript": SkillCategory.LANGUAGE,
    "JavaScript": SkillCategory.LANGUAGE,
    "C++": SkillCategory.LANGUAGE,
    "Dart": SkillCategory.LANGUAGE,
    "PostgreSQL": SkillCategory.DATABASE,
    "MongoDB": SkillCategory.DATABASE,
    # `SkillCategory` has no CONCEPT member, so the engineering disciplines
    # below land in OTHER. That is the taxonomy's existing answer for a skill
    # that is not a language, framework, store, or tool — widening the enum
    # would be a migration on a shared table for a labelling nicety.
    "Distributed Systems": SkillCategory.OTHER,
    "Systems Programming": SkillCategory.OTHER,
    "Microservices": SkillCategory.OTHER,
    "Algorithms": SkillCategory.OTHER,
    "Machine Learning": SkillCategory.OTHER,
    "WebAssembly": SkillCategory.OTHER,
    "React": SkillCategory.FRAMEWORK,
    "Next.js": SkillCategory.FRAMEWORK,
    "Node.js": SkillCategory.FRAMEWORK,
    "Express": SkillCategory.FRAMEWORK,
    "Spring Boot": SkillCategory.FRAMEWORK,
    "TensorFlow": SkillCategory.FRAMEWORK,
    "Flutter": SkillCategory.FRAMEWORK,
    "Tailwind CSS": SkillCategory.FRAMEWORK,
    "pandas": SkillCategory.FRAMEWORK,
    "Kubernetes": SkillCategory.DEVOPS,
    "Docker": SkillCategory.DEVOPS,
    "CI/CD": SkillCategory.DEVOPS,
    "AWS": SkillCategory.CLOUD,
    "Firebase": SkillCategory.CLOUD,
    "gRPC": SkillCategory.TOOL,
    "Figma": SkillCategory.TOOL,
}

DEMO_JOB: dict = {
    "title": "Senior Backend Engineer",
    "description": (
        "TechNova Solutions is hiring a backend engineer to own the settlement and "
        "ledger services behind our payments platform. You will work in Rust on "
        "services that hold correctness guarantees under concurrency, model financial "
        "state in PostgreSQL with careful transaction and index design, and reason "
        "about distributed systems problems — consensus, idempotency, partial failure, "
        "and exactly-once delivery across service boundaries. "
        "Expect to own a service end to end: schema, migrations, the API surface, the "
        "background workers behind it, and the observability that makes an incident "
        "debuggable at 3am. We care about engineers who can explain why a lock is held "
        "where it is held, and who reach for a database constraint before an "
        "application-level check. "
        "Experience with gRPC service meshes and running workloads on Kubernetes is a "
        "plus, but we would rather hire someone with deep systems instincts and teach "
        "them our deployment story."
    ),
    "job_type": "full_time",
    # See the module docstring, constraint 1. This is the single most
    # load-bearing line in the file.
    "experience_level": "mid",
    "location": "Delhi",
    "is_remote": True,
    "skills": [
        ("Rust", "advanced", True),
        ("PostgreSQL", "advanced", True),
        ("Distributed Systems", "advanced", True),
        ("gRPC", "intermediate", False),
        ("Kubernetes", "intermediate", False),
    ],
}


def _years_ago(years: int, months: int = 0) -> date:
    return date.today() - timedelta(days=years * 365 + months * 30)


#: The cohort. Ordered as the brief lists them, not by score — the score is an
#: output, and ordering the source by it would invite editing the source when
#: the number moved.
#:
#: `about` is worth understanding before editing: it reaches the candidate
#: embedding (`matching/embeddings.py::build_candidate_embedding_text`) and is
#: therefore a real input to the semantic term. It is the student's own words
#: about their own work, which is exactly what that term is meant to read —
#: but it does mean a persona whose `about` is written in a different
#: vocabulary from the job description will score lower on semantics, and that
#: is intended rather than accidental.
STUDENTS: list[dict] = [
    {
        "name": "Rahul Sharma",
        "email": "rahul@test.com",
        "headline": "Backend engineer — Rust services, PostgreSQL, distributed settlement systems",
        "college": "IIT Delhi",
        "degree": "btech",
        "branch": "cse",
        "grad_year": 2027,
        "location": "Delhi, India",
        "target_roles": ["backend"],
        "about": (
            "I work on backend services in Rust where correctness under concurrency "
            "actually matters. Most of my time goes to settlement and ledger code: "
            "modelling financial state in PostgreSQL, getting transaction boundaries and "
            "index design right, and reasoning about distributed systems failure modes "
            "like idempotency, partial failure and exactly-once delivery."
        ),
        "github": "rahul-sharma-dev",
        "github_score": 95.0,
        "coding": [(CodingPlatform.CODEFORCES, "rahul_cf", 1850, 45), (CodingPlatform.LEETCODE, "rahul_lc", None, None)],
        "projects": [
            {
                "title": "payments-api",
                "repo": "https://github.com/rahul-sharma-dev/payments-api",
                "description": "Settlement engine handling batch reconciliation in Rust, with per-item transaction isolation and an append-only ledger in PostgreSQL.",
                "tech": ["Rust", "PostgreSQL", "gRPC"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.91,
                "score": 94.0,
                "commits": 312,
            },
            {
                "title": "raft-kv",
                "repo": "https://github.com/rahul-sharma-dev/raft-kv",
                "description": "A Raft-backed key-value store used to teach myself consensus properly — leader election, log compaction, and a deterministic failure-injection harness.",
                "tech": ["Rust", "Distributed Systems"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.97,
                "score": 89.0,
                "commits": 341,
            },
            {
                "title": "pg-index-advisor",
                "repo": "https://github.com/rahul-sharma-dev/pg-index-advisor",
                "description": "Reads pg_stat_statements and suggests missing indexes, with an explain-plan diff so the suggestion is auditable rather than trusted.",
                "tech": ["Rust", "PostgreSQL"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.88,
                "score": 85.0,
                "commits": 154,
            },
        ],
        "skills": [
            ("Rust", ProficiencyLevel.EXPERT, 0.94),
            ("PostgreSQL", ProficiencyLevel.ADVANCED, 0.81),
            ("Distributed Systems", ProficiencyLevel.ADVANCED, 0.88),
            ("gRPC", ProficiencyLevel.INTERMEDIATE, 0.62),
        ],
        "certificates": [
            ("AWS Solutions Architect Associate", "Amazon Web Services", VerificationStatus.VERIFIED),
            ("Coursera Machine Learning", "Coursera", VerificationStatus.UNVERIFIED),
        ],
        "experience": [
            {
                "company": "Razorpay",
                "title": "Backend Engineering Intern",
                "type": EmploymentType.INTERNSHIP,
                "start": date(2026, 5, 1),
                "end": date(2026, 7, 31),
                "tech": ["Rust", "gRPC", "PostgreSQL"],
                "description": "Worked on the settlement service's retry path, moving idempotency keys out of application code and into a unique partial index.",
            }
        ],
        "interview": {
            "score": 87.0,
            "dimensions": {"technical_accuracy": 92.0, "code_understanding": 88.0, "problem_solving": 85.0, "repository_knowledge": 90.0, "communication": 78.0},
            "highlights": [
                {
                    "prompt": "settle_batch takes a write lock for the whole batch. What happens when one settlement fails halfway?",
                    "transcript": "We wrap each settlement in its own transaction so a single failure rolls back only that item, not the batch. The outer lock is only there to stop two workers claiming the same batch — it's a claim lock, not a correctness lock. The failed item goes back to pending with its attempt count incremented, and the batch completes with a partial-success status the caller has to handle.",
                    "grounded_in": "src/settlement/batch.rs",
                    "rationale": "Distinguished the claim lock from the correctness boundary without being led there.",
                },
                {
                    "prompt": "Your ledger table has a unique index on (account_id, idempotency_key). Why not check for duplicates in application code first?",
                    "transcript": "Because the check and the insert wouldn't be atomic — two concurrent retries both read 'not present' and both insert. The unique index makes the database the arbiter, and we catch the constraint violation and treat it as success, since the key existing means the work already happened. It also means a bug in a future caller can't corrupt the ledger.",
                    "grounded_in": "migrations/0012_ledger_idempotency.sql",
                    "rationale": "Reached for the constraint over the application check and explained the race precisely.",
                },
                {
                    "prompt": "In raft-kv, how do you avoid a stale leader serving reads after a partition?",
                    "transcript": "A leader that's been partitioned doesn't know it's been deposed, so it can't serve a linearizable read from local state. I implemented read-index: before answering, the leader confirms it still has a quorum heartbeat, and only then reads. It costs a round trip. The alternative is lease-based reads, which is faster but leans on bounded clock drift, and I didn't want that assumption in a teaching implementation.",
                    "grounded_in": "src/raft/read_index.rs",
                    "rationale": "Named both approaches and justified the tradeoff he actually took.",
                },
            ],
        },
    },
    {
        "name": "Priya Patel",
        "email": "priya@test.com",
        "headline": "Full-stack engineer — React and TypeScript front ends on Node.js and PostgreSQL",
        "college": "BITS Pilani",
        "degree": "btech",
        "branch": "cse",
        "grad_year": 2027,
        "location": "Hyderabad, India",
        "target_roles": ["frontend", "fullstack"],
        "about": (
            "I build product interfaces in React and TypeScript and own the Node.js API "
            "and PostgreSQL schema behind them. I care a lot about the seam between the "
            "two — typed contracts, sensible pagination, and not letting the database "
            "shape leak into component state."
        ),
        "github": "priya-patel",
        "github_score": 88.0,
        "coding": [(CodingPlatform.CODEFORCES, "priya_cf", 1400, 22), (CodingPlatform.LEETCODE, "priya_lc", None, None)],
        "projects": [
            {
                "title": "orders-dashboard",
                "repo": "https://github.com/priya-patel/orders-dashboard",
                "description": "Operations console for a D2C brand — React and TypeScript over a Node.js API, with server-driven filters so a 40k-row order table stays interactive.",
                "tech": ["React", "TypeScript", "Node.js", "PostgreSQL"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.86,
                "score": 87.0,
                "commits": 268,
            },
            {
                "title": "schema-contracts",
                "repo": "https://github.com/priya-patel/schema-contracts",
                "description": "Generates TypeScript types from PostgreSQL schemas so the API and the client cannot disagree about a column that was renamed.",
                "tech": ["TypeScript", "PostgreSQL", "Node.js"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.93,
                "score": 82.0,
                "commits": 191,
            },
        ],
        "skills": [
            ("React", ProficiencyLevel.EXPERT, 0.91),
            ("TypeScript", ProficiencyLevel.ADVANCED, 0.87),
            ("Node.js", ProficiencyLevel.ADVANCED, 0.83),
            ("PostgreSQL", ProficiencyLevel.INTERMEDIATE, 0.64),
        ],
        "certificates": [
            ("Meta Front-End Developer Professional Certificate", "Meta", VerificationStatus.VERIFIED),
        ],
        "experience": [
            {
                "company": "Zeta",
                "title": "Frontend Engineering Intern",
                "type": EmploymentType.INTERNSHIP,
                "start": date(2026, 1, 15),
                "end": date(2026, 4, 30),
                "tech": ["React", "TypeScript"],
                "description": "Rebuilt the card-issuance flow and cut its p95 interaction latency by moving validation off the render path.",
            }
        ],
        "interview": {
            "score": 81.0,
            "dimensions": {"technical_accuracy": 84.0, "code_understanding": 82.0, "problem_solving": 78.0, "repository_knowledge": 83.0, "communication": 86.0},
            "highlights": [
                {
                    "prompt": "orders-dashboard sends filters to the server rather than filtering in the client. What drove that?",
                    "transcript": "The table is around forty thousand rows for the bigger tenants. Shipping that to the browser to filter it was about four megabytes and a visible freeze on the main thread. Moving filters into the query means the server returns a page, and the client only holds what it renders. The tradeoff is a round trip per filter change, so I debounce and keep the last result visible while the next one loads.",
                    "grounded_in": "src/api/orders/query.ts",
                    "rationale": "Grounded the decision in a measured number from her own repo.",
                },
                {
                    "prompt": "schema-contracts generates types at build time. What breaks if someone changes the database without rerunning it?",
                    "transcript": "The build fails, which is what I wanted. The generated file is committed, and CI regenerates and diffs it — if the checked-in types don't match the live schema the pipeline stops. If I'd generated at runtime instead you'd get a type that silently matched whatever the database said, and the mismatch would surface as a null in production instead of a red build.",
                    "grounded_in": ".github/workflows/schema-check.yml",
                    "rationale": "Understood the failure mode she designed for, not just the happy path.",
                },
                {
                    "prompt": "How do you paginate a table the user is also sorting and filtering?",
                    "transcript": "Offset pagination breaks when rows shift between pages, so I use keyset pagination on the sort column plus the primary key as a tiebreaker. The cursor encodes both. It means you can't jump to page 40 directly, which the product was fine with — the operators scroll, they don't page-jump.",
                    "grounded_in": "src/api/orders/cursor.ts",
                    "rationale": "Named the correct technique and the constraint it imposes.",
                },
            ],
        },
    },
    {
        "name": "Arjun Mehta",
        "email": "arjun@test.com",
        "headline": "Platform engineer — Go services, Kubernetes, and the CI/CD that ships them",
        "college": "NIT Trichy",
        "degree": "btech",
        "branch": "cse",
        "grad_year": 2026,
        "location": "Chennai, India",
        "target_roles": ["devops", "backend"],
        "about": (
            "I write backend services in Go and own how they get deployed. That means "
            "Kubernetes manifests and operators, Docker build pipelines, and CI/CD that "
            "fails loudly before a bad image reaches production. I've spent enough time "
            "debugging partial failure across services to respect distributed systems "
            "problems, and I keep state in PostgreSQL rather than inventing storage."
        ),
        "github": "arjun-mehta",
        "github_score": 90.0,
        "coding": [(CodingPlatform.CODEFORCES, "arjun_cf", 1600, 31)],
        "projects": [
            {
                "title": "deploy-operator",
                "repo": "https://github.com/arjun-mehta/deploy-operator",
                "description": "A Kubernetes operator that does progressive rollouts with automatic rollback driven by real error-rate SLOs rather than a fixed timer.",
                "tech": ["Go", "Kubernetes", "Docker"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.94,
                "score": 91.0,
                "commits": 247,
            },
            {
                "title": "job-runner",
                "repo": "https://github.com/arjun-mehta/job-runner",
                "description": "Distributed background job runner in Go with at-least-once delivery, PostgreSQL-backed leases, and a dead-letter path that keeps the failing payload.",
                "tech": ["Go", "PostgreSQL", "Distributed Systems"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.89,
                "score": 86.0,
                "commits": 178,
            },
        ],
        "skills": [
            ("Go", ProficiencyLevel.EXPERT, 0.92),
            ("Kubernetes", ProficiencyLevel.ADVANCED, 0.88),
            ("Docker", ProficiencyLevel.ADVANCED, 0.85),
            ("CI/CD", ProficiencyLevel.ADVANCED, 0.80),
            ("Distributed Systems", ProficiencyLevel.INTERMEDIATE, 0.71),
            ("PostgreSQL", ProficiencyLevel.INTERMEDIATE, 0.66),
        ],
        "certificates": [
            ("Certified Kubernetes Administrator", "Cloud Native Computing Foundation", VerificationStatus.VERIFIED),
            ("Docker Certified Associate", "Docker Inc.", VerificationStatus.FLAGGED),
        ],
        "experience": [
            {
                "company": "Freshworks",
                "title": "Platform Engineering Intern",
                "type": EmploymentType.INTERNSHIP,
                "start": date(2025, 6, 1),
                "end": date(2025, 8, 31),
                "tech": ["Go", "Kubernetes"],
                "description": "Cut deploy time from 18 minutes to 6 by splitting a monolithic image build into cached layers.",
            }
        ],
        "interview": {
            "score": 84.0,
            "dimensions": {"technical_accuracy": 86.0, "code_understanding": 84.0, "problem_solving": 87.0, "repository_knowledge": 85.0, "communication": 76.0},
            "highlights": [
                {
                    "prompt": "job-runner promises at-least-once delivery. Why not exactly-once?",
                    "transcript": "Exactly-once across a process boundary isn't something I can promise honestly — the worker can die after doing the work and before acknowledging, and nothing on my side distinguishes that from dying before. So I promise at-least-once and require handlers to be idempotent. The lease row carries an attempt count so a handler can tell it's a retry.",
                    "grounded_in": "internal/queue/lease.go",
                    "rationale": "Refused to overclaim a guarantee the architecture cannot make.",
                },
                {
                    "prompt": "Your operator rolls back on error rate. What stops it flapping?",
                    "transcript": "Two things. The SLO window is five minutes, so a single spike doesn't trip it, and after a rollback the deployment is marked held — it won't retry the same image digest without a human clearing it. Early on I had it retry automatically and it rolled the same broken build four times before anyone noticed.",
                    "grounded_in": "controllers/rollout_controller.go",
                    "rationale": "Described a real failure he hit and the specific guard he added.",
                },
                {
                    "prompt": "Where does PostgreSQL fit in job-runner, and why not Redis?",
                    "transcript": "The lease table and the job payloads both live in Postgres. I wanted the job state and the business data the job touches to be in the same transaction — with Redis I'd have had a two-system commit and no clean story for a crash between them. Redis would be faster, but the throughput here is hundreds a second, not hundreds of thousands.",
                    "grounded_in": "migrations/003_leases.sql",
                    "rationale": "Justified the storage choice against the actual load, not a benchmark.",
                },
            ],
        },
    },
    {
        "name": "Sneha Gupta",
        "email": "sneha@test.com",
        "headline": "ML engineer — Python, TensorFlow, and the data pipelines behind the models",
        "college": "IIIT Hyderabad",
        "degree": "btech",
        "branch": "aiml",
        "grad_year": 2027,
        "location": "Hyderabad, India",
        "target_roles": ["ml_engineer", "data_scientist"],
        "about": (
            "I train and ship models in Python — mostly TensorFlow, with pandas for the "
            "feature work — and I've learned that the pipeline matters more than the "
            "architecture. I keep feature stores and training data in PostgreSQL so a "
            "model run is reproducible from a query rather than from a notebook someone "
            "has to remember to rerun."
        ),
        "github": "sneha-gupta",
        "github_score": 93.0,
        "coding": [(CodingPlatform.LEETCODE, "sneha_lc", None, None), (CodingPlatform.CODEFORCES, "sneha_cf", 1200, 14)],
        "projects": [
            {
                "title": "feature-store",
                "repo": "https://github.com/sneha-gupta/feature-store",
                "description": "Point-in-time correct feature store on PostgreSQL — training queries reconstruct exactly the feature values that existed at prediction time, so offline and online scores agree.",
                "tech": ["Python", "PostgreSQL", "pandas"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.90,
                "score": 88.0,
                "commits": 402,
            },
            {
                "title": "churn-models",
                "repo": "https://github.com/sneha-gupta/churn-models",
                "description": "Subscription churn models in TensorFlow with a calibration layer, because the ranking was fine but the probabilities were not usable as probabilities.",
                "tech": ["Python", "TensorFlow", "Machine Learning"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.95,
                "score": 90.0,
                "commits": 511,
            },
            {
                "title": "pandas-profiler",
                "repo": "https://github.com/sneha-gupta/pandas-profiler",
                "description": "Profiles a dataframe pipeline and flags the steps that silently change row counts — the class of bug that quietly halves a training set.",
                "tech": ["Python", "pandas"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.87,
                "score": 79.0,
                "commits": 288,
            },
        ],
        "skills": [
            ("Python", ProficiencyLevel.EXPERT, 0.93),
            ("Machine Learning", ProficiencyLevel.ADVANCED, 0.87),
            ("TensorFlow", ProficiencyLevel.ADVANCED, 0.84),
            ("pandas", ProficiencyLevel.EXPERT, 0.89),
            ("PostgreSQL", ProficiencyLevel.INTERMEDIATE, 0.68),
        ],
        "certificates": [
            ("DeepLearning.AI TensorFlow Developer", "DeepLearning.AI", VerificationStatus.VERIFIED),
            ("Kaggle Advanced SQL", "Kaggle", VerificationStatus.UNVERIFIED),
        ],
        "experience": [
            {
                "company": "Sigmoid",
                "title": "Machine Learning Intern",
                "type": EmploymentType.INTERNSHIP,
                "start": date(2026, 5, 15),
                "end": date(2026, 7, 15),
                "tech": ["Python", "TensorFlow", "PostgreSQL"],
                "description": "Built the point-in-time join that removed target leakage from a forecasting model's training set.",
            }
        ],
        "interview": {
            "score": 85.0,
            "dimensions": {"technical_accuracy": 87.0, "code_understanding": 86.0, "problem_solving": 88.0, "repository_knowledge": 84.0, "communication": 80.0},
            "highlights": [
                {
                    "prompt": "What does 'point-in-time correct' mean in feature-store, and what goes wrong without it?",
                    "transcript": "It means when I build a training row for an event at time T, every feature value is what it was at T, not what it is now. Without it you leak the future into training — a feature like 'total lifetime orders' computed today includes orders that happened after the label. The model looks brilliant offline and does nothing in production. The query joins on an as-of timestamp against a history table rather than the current-state table.",
                    "grounded_in": "featurestore/asof.py",
                    "rationale": "Explained the leakage mechanism concretely rather than naming the term.",
                },
                {
                    "prompt": "churn-models has a calibration layer. Why wasn't the raw model output enough?",
                    "transcript": "The model ranked well — AUC was fine — but the outputs weren't calibrated, so a predicted 0.8 wasn't an 80% chance. That's fine if you only rank, but the business wanted to threshold on expected value and multiply the probability by a rupee amount. So I fit isotonic regression on a held-out set. Ranking is unchanged; the numbers became usable.",
                    "grounded_in": "models/calibrate.py",
                    "rationale": "Correctly separated discrimination from calibration and tied it to the use case.",
                },
                {
                    "prompt": "Why keep the feature store in PostgreSQL rather than a purpose-built system?",
                    "transcript": "Scale didn't demand one. The whole history is a few hundred million rows, which Postgres handles with the right partitioning, and keeping it there meant the as-of join is plain SQL that anyone on the team can read and audit. A dedicated store would have added an operational surface for a problem I didn't have yet.",
                    "grounded_in": "migrations/002_feature_history.sql",
                    "rationale": "Sized the solution to the actual problem.",
                },
            ],
        },
    },
    {
        "name": "Vikram Singh",
        "email": "vikram@test.com",
        "headline": "Backend engineer — Java and Spring Boot microservices on PostgreSQL",
        "college": "Delhi Technological University",
        "degree": "btech",
        "branch": "cse",
        "grad_year": 2027,
        "location": "Delhi, India",
        "target_roles": ["backend"],
        "about": (
            "I build backend services in Java with Spring Boot, split along domain "
            "boundaries rather than by layer. Most of what I've learned the hard way is "
            "about distributed systems — retries that amplify load, transactions that "
            "don't span services, and why the saga you write is easier to reason about "
            "than the two-phase commit you wish you had. State lives in PostgreSQL."
        ),
        "github": "vikram-singh",
        "github_score": 82.0,
        "coding": [(CodingPlatform.CODEFORCES, "vikram_cf", 1700, 38), (CodingPlatform.LEETCODE, "vikram_lc", None, None)],
        "projects": [
            {
                "title": "inventory-services",
                "repo": "https://github.com/vikram-singh/inventory-services",
                "description": "Four Spring Boot services behind an inventory domain, coordinated with sagas and an outbox table so a publish and a commit cannot disagree.",
                "tech": ["Java", "Spring Boot", "PostgreSQL", "Distributed Systems"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.88,
                "score": 84.0,
                "commits": 223,
            },
            {
                "title": "outbox-relay",
                "repo": "https://github.com/vikram-singh/outbox-relay",
                "description": "Transactional outbox relay — polls the outbox in the same database as the business write and republishes, so an event is never lost to a crash between commit and publish.",
                "tech": ["Java", "PostgreSQL", "Distributed Systems"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.92,
                "score": 80.0,
                "commits": 96,
            },
        ],
        "skills": [
            ("Java", ProficiencyLevel.ADVANCED, 0.86),
            ("Spring Boot", ProficiencyLevel.ADVANCED, 0.84),
            ("Microservices", ProficiencyLevel.ADVANCED, 0.79),
            ("PostgreSQL", ProficiencyLevel.ADVANCED, 0.76),
            ("Distributed Systems", ProficiencyLevel.INTERMEDIATE, 0.69),
        ],
        "certificates": [
            ("Oracle Certified Professional: Java SE 17 Developer", "Oracle", VerificationStatus.VERIFIED),
        ],
        "experience": [],
        "interview": {
            "score": 79.0,
            "dimensions": {"technical_accuracy": 81.0, "code_understanding": 80.0, "problem_solving": 77.0, "repository_knowledge": 82.0, "communication": 74.0},
            "highlights": [
                {
                    "prompt": "Why an outbox table instead of publishing to the broker directly after commit?",
                    "transcript": "Because those are two systems and there's no transaction across them. If I commit and then the process dies before publishing, the event is gone and the other services never learn. Writing the event into the same transaction as the business change makes it atomic, and a relay publishes it afterwards. The relay can publish twice, which is why consumers are idempotent.",
                    "grounded_in": "src/main/java/outbox/OutboxRelay.java",
                    "rationale": "Identified the dual-write problem and its standard resolution.",
                },
                {
                    "prompt": "Your saga compensates rather than rolling back. What's the cost of that?",
                    "transcript": "Intermediate states are visible. With a real rollback nobody sees the partial state; with a saga, between the reserve and the compensate, a user can genuinely see stock reserved that's about to be released. We made compensations fast and made the UI treat reserved-not-confirmed as pending rather than final.",
                    "grounded_in": "src/main/java/saga/ReservationSaga.java",
                    "rationale": "Named the semantic cost, not just the mechanics.",
                },
                {
                    "prompt": "How do you stop retries from amplifying load during an incident?",
                    "transcript": "Exponential backoff with jitter, and a circuit breaker on the client side so a service that's already failing stops receiving traffic. Without jitter all the retries synchronise and you get a thundering herd on the exact moment the service recovers.",
                    "grounded_in": "src/main/java/client/RetryPolicy.java",
                    "rationale": "Correct on both backoff and the synchronisation failure mode.",
                },
            ],
        },
    },
    {
        "name": "Ananya Reddy",
        "email": "ananya@test.com",
        "headline": "Frontend engineer — React, Next.js and design systems in Tailwind and Figma",
        "college": "VIT Vellore",
        "degree": "btech",
        "branch": "it",
        "grad_year": 2027,
        "location": "Bangalore, India",
        "target_roles": ["frontend"],
        "about": (
            "I build product interfaces in React and Next.js and I care most about the "
            "design system underneath them — tokens in Tailwind, components that compose, "
            "and a Figma library that stays in step with what actually shipped. I work "
            "close to designers and I prototype in the browser rather than in mockups."
        ),
        "github": "ananya-reddy",
        "github_score": 86.0,
        "coding": [],
        "projects": [
            {
                "title": "aurora-ds",
                "repo": "https://github.com/ananya-reddy/aurora-ds",
                "description": "Design system of 40 components with tokens generated from Figma variables, so a colour change in design lands in code as a diff rather than a ticket.",
                "tech": ["React", "TypeScript", "Tailwind CSS", "Figma"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.93,
                "score": 89.0,
                "commits": 316,
            },
            {
                "title": "next-commerce",
                "repo": "https://github.com/ananya-reddy/next-commerce",
                "description": "Storefront in Next.js with streaming server components, built to see how far the interaction budget stretches on a mid-range Android device.",
                "tech": ["Next.js", "React", "Tailwind CSS"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.90,
                "score": 83.0,
                "commits": 204,
            },
        ],
        "skills": [
            ("React", ProficiencyLevel.EXPERT, 0.90),
            ("Next.js", ProficiencyLevel.ADVANCED, 0.85),
            ("Tailwind CSS", ProficiencyLevel.ADVANCED, 0.82),
            ("Figma", ProficiencyLevel.ADVANCED, 0.78),
            ("TypeScript", ProficiencyLevel.INTERMEDIATE, 0.70),
        ],
        "certificates": [
            ("Google UX Design Certificate", "Google", VerificationStatus.VERIFIED),
        ],
        "experience": [
            {
                "company": "Freelance",
                "title": "Frontend Developer",
                "type": EmploymentType.FREELANCE,
                "start": date(2025, 9, 1),
                "end": None,
                "tech": ["React", "Next.js", "Tailwind CSS"],
                "description": "Design-system and marketing-site work for three early-stage startups.",
            }
        ],
        "interview": {
            "score": 82.0,
            "dimensions": {"technical_accuracy": 83.0, "code_understanding": 84.0, "problem_solving": 79.0, "repository_knowledge": 85.0, "communication": 88.0},
            "highlights": [
                {
                    "prompt": "aurora-ds generates tokens from Figma variables. What happens when a designer renames one?",
                    "transcript": "The generator emits the new name and the old one disappears, so anything still importing it fails to compile. That's deliberate — a rename should be a breaking change you see at build time, not a colour that silently falls back to a default. We keep a deprecation shim for one release when it's a widely-used token.",
                    "grounded_in": "scripts/generate-tokens.ts",
                    "rationale": "Chose loud failure over silent fallback and could say why.",
                },
                {
                    "prompt": "Where did streaming server components actually help in next-commerce?",
                    "transcript": "The product grid needs a pricing call that's slow for logged-in users. Streaming let me send the layout and the images immediately and stream prices in, so the largest contentful paint stopped waiting on pricing. It didn't help the category pages at all — those were already fast and the added complexity wasn't worth it.",
                    "grounded_in": "app/products/page.tsx",
                    "rationale": "Reported where the technique did not help, which is the harder half.",
                },
                {
                    "prompt": "How do you keep a 40-component library from becoming 40 special cases?",
                    "transcript": "Components take tokens, not raw values, and there's a lint rule that fails on a hardcoded hex or pixel value inside the library. If something genuinely needs a new value it becomes a token first. It's annoying in the moment and it's the only reason the library is still coherent.",
                    "grounded_in": ".eslintrc.ds.cjs",
                    "rationale": "Enforced the constraint mechanically rather than by convention.",
                },
            ],
        },
    },
    {
        "name": "Karan Joshi",
        "email": "karan@test.com",
        "headline": "Competitive programmer — C++ and algorithms, Codeforces candidate master",
        "college": "IIT Bombay",
        "degree": "btech",
        "branch": "cse",
        "grad_year": 2027,
        "location": "Mumbai, India",
        "target_roles": ["backend", "other"],
        "about": (
            "Competitive programming is most of what I do — C++, data structures and "
            "algorithms, and a lot of contest practice. I'm strongest on the algorithmic "
            "side and I'm deliberately working outward from there into systems: my recent "
            "reading has been on distributed systems and I've started keeping problem "
            "data in PostgreSQL rather than flat files."
        ),
        "github": "karan-joshi",
        "github_score": 71.0,
        "coding": [(CodingPlatform.CODEFORCES, "karan_cf", 2100, 78), (CodingPlatform.CODECHEF, "karan_cc", None, None)],
        "projects": [
            {
                "title": "cp-library",
                "repo": "https://github.com/karan-joshi/cp-library",
                "description": "Contest template library in C++ — segment trees, flow, suffix structures — with a stress-testing harness that fuzzes each against a brute-force reference.",
                "tech": ["C++", "Algorithms"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.99,
                "score": 88.0,
                "commits": 156,
            },
        ],
        "skills": [
            ("C++", ProficiencyLevel.EXPERT, 0.92),
            ("Algorithms", ProficiencyLevel.EXPERT, 0.94),
            ("Distributed Systems", ProficiencyLevel.NOVICE, 0.42),
            ("PostgreSQL", ProficiencyLevel.NOVICE, 0.38),
        ],
        "certificates": [],
        "experience": [],
        "interview": {
            "score": 76.0,
            "dimensions": {"technical_accuracy": 88.0, "code_understanding": 82.0, "problem_solving": 93.0, "repository_knowledge": 64.0, "communication": 62.0},
            "highlights": [
                {
                    "prompt": "Your cp-library stress-tests against a brute force. Why is that worth the effort?",
                    "transcript": "Because a segment tree that's wrong on one edge case passes every sample and fails the contest. The harness generates small random inputs, runs both, and diffs. Small is the point — if it fails on an array of size six I can read the failure directly. I've caught three off-by-ones in lazy propagation that way that reading the code never would have.",
                    "grounded_in": "stress/run.sh",
                    "rationale": "Strong testing instinct, grounded in specific bugs it caught.",
                },
                {
                    "prompt": "How would you apply that instinct to a backend service rather than a contest problem?",
                    "transcript": "I think it's the same idea — property-based testing against a simpler model. I haven't built a service that way yet, so I'd be guessing about what the model looks like when there's a database and concurrency involved. That's honestly the gap I'm working on.",
                    "grounded_in": "cp-library README",
                    "rationale": "Transferred the principle and marked the boundary of his experience.",
                },
                {
                    "prompt": "What's your PostgreSQL experience beyond storing contest data?",
                    "transcript": "Limited. I use it as a place to put rows — I can write joins and I've added an index when a query got slow, but I haven't designed a schema anyone else depends on, and I haven't dealt with transactions under contention.",
                    "grounded_in": "tools/store.cpp",
                    "rationale": "Accurate self-assessment; the claim matches the evidence in the repo.",
                },
            ],
        },
    },
    {
        "name": "Meera Krishnan",
        "email": "meera@test.com",
        "headline": "Backend engineer — Node.js and Express APIs on MongoDB and AWS",
        "college": "Manipal Institute of Technology",
        "degree": "btech",
        "branch": "cse",
        "grad_year": 2026,
        "location": "Bangalore, India",
        "target_roles": ["backend"],
        "about": (
            "I build backend APIs in Node.js and Express and run them on AWS. Most of my "
            "data work has been MongoDB, though the service I'm proudest of moved to "
            "PostgreSQL when we needed real transactions. I've dealt with enough queue "
            "and retry behaviour across services to have opinions about distributed "
            "systems failure modes."
        ),
        "github": "meera-krishnan",
        "github_score": 84.0,
        "coding": [(CodingPlatform.LEETCODE, "meera_lc", None, None), (CodingPlatform.CODEFORCES, "meera_cf", 1300, 19)],
        "projects": [
            {
                "title": "notify-service",
                "repo": "https://github.com/meera-krishnan/notify-service",
                "description": "Multi-channel notification service in Node.js — per-channel rate limits, provider failover, and a delivery log that survives a provider outage.",
                "tech": ["Node.js", "Express", "MongoDB", "AWS"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.87,
                "score": 83.0,
                "commits": 219,
            },
            {
                "title": "ledger-lite",
                "repo": "https://github.com/meera-krishnan/ledger-lite",
                "description": "Double-entry ledger that started on MongoDB and moved to PostgreSQL once it needed multi-document transactions it could actually trust.",
                "tech": ["Node.js", "PostgreSQL", "Distributed Systems"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.91,
                "score": 78.0,
                "commits": 134,
            },
        ],
        "skills": [
            ("Node.js", ProficiencyLevel.ADVANCED, 0.85),
            ("Express", ProficiencyLevel.ADVANCED, 0.81),
            ("MongoDB", ProficiencyLevel.ADVANCED, 0.79),
            ("AWS", ProficiencyLevel.INTERMEDIATE, 0.72),
            ("PostgreSQL", ProficiencyLevel.INTERMEDIATE, 0.63),
            ("Distributed Systems", ProficiencyLevel.NOVICE, 0.51),
        ],
        "certificates": [
            ("AWS Certified Developer Associate", "Amazon Web Services", VerificationStatus.VERIFIED),
            ("MongoDB Associate Developer", "MongoDB Inc.", VerificationStatus.UNVERIFIED),
        ],
        "experience": [
            {
                "company": "Postman",
                "title": "Backend Engineering Intern",
                "type": EmploymentType.INTERNSHIP,
                "start": date(2025, 5, 1),
                "end": date(2025, 7, 31),
                "tech": ["Node.js", "AWS"],
                "description": "Owned the webhook retry pipeline and added the dead-letter path that stopped silent drops.",
            }
        ],
        "interview": {
            "score": 74.0,
            "dimensions": {"technical_accuracy": 76.0, "code_understanding": 75.0, "problem_solving": 73.0, "repository_knowledge": 78.0, "communication": 72.0},
            "highlights": [
                {
                    "prompt": "ledger-lite moved from MongoDB to PostgreSQL. What forced it?",
                    "transcript": "Double-entry means every transfer writes two rows that must both land or neither. On the Mongo version I was doing it in application code with a compensating delete if the second write failed, and a crash between them left the ledger unbalanced. I'd built a worse transaction. Postgres already had the one I needed.",
                    "grounded_in": "src/ledger/transfer.js",
                    "rationale": "Recognised he had reimplemented a database primitive badly.",
                },
                {
                    "prompt": "How does notify-service handle a provider that's up but slow?",
                    "transcript": "That was the case I got wrong first. A timeout counts as a failure and fails over to the secondary, but I originally had no timeout at all, so a slow provider just consumed the worker pool and everything queued behind it. Now there's a per-request deadline and the circuit opens on sustained slowness, not just errors.",
                    "grounded_in": "src/providers/circuit.js",
                    "rationale": "Distinguished slow from down, which is the harder failure.",
                },
                {
                    "prompt": "What would you need to learn to work on a Rust settlement service?",
                    "transcript": "Rust itself, honestly — I've read it, I haven't shipped it. The domain I'd be less lost in, because a ledger with idempotent retries is what ledger-lite is, just smaller and in a language I already know.",
                    "grounded_in": "ledger-lite README",
                    "rationale": "Separated the language gap from the domain gap accurately.",
                },
            ],
        },
    },
    {
        "name": "Aditya Chauhan",
        "email": "aditya@test.com",
        "headline": "Mobile engineer — Flutter and Dart apps backed by Firebase",
        "college": "Amity University",
        "degree": "btech",
        "branch": "cse",
        "grad_year": 2027,
        "location": "Noida, India",
        "target_roles": ["mobile"],
        "about": (
            "I build mobile apps in Flutter and Dart, usually with Firebase behind them "
            "for auth, storage and push. I care about the things that make an app feel "
            "native — offline-first sync, gesture handling, and keeping frame times "
            "under budget on cheap Android hardware."
        ),
        "github": "aditya-chauhan",
        "github_score": 80.0,
        "coding": [],
        "projects": [
            {
                "title": "fieldkit",
                "repo": "https://github.com/aditya-chauhan/fieldkit",
                "description": "Offline-first field survey app in Flutter — local-first writes with conflict resolution on reconnect, built for surveyors with no signal.",
                "tech": ["Flutter", "Dart", "Firebase"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.94,
                "score": 85.0,
                "commits": 231,
            },
            {
                "title": "gesture-lab",
                "repo": "https://github.com/aditya-chauhan/gesture-lab",
                "description": "Custom gesture recognisers for Flutter, with a frame-timing overlay to see which interactions blow the 16ms budget.",
                "tech": ["Flutter", "Dart"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.96,
                "score": 81.0,
                "commits": 119,
            },
        ],
        "skills": [
            ("Flutter", ProficiencyLevel.ADVANCED, 0.88),
            ("Dart", ProficiencyLevel.ADVANCED, 0.86),
            ("Firebase", ProficiencyLevel.INTERMEDIATE, 0.74),
        ],
        "certificates": [
            ("Google Associate Android Developer", "Google", VerificationStatus.FLAGGED),
        ],
        "experience": [],
        "interview": {
            "score": 77.0,
            "dimensions": {"technical_accuracy": 79.0, "code_understanding": 78.0, "problem_solving": 76.0, "repository_knowledge": 80.0, "communication": 73.0},
            "highlights": [
                {
                    "prompt": "fieldkit resolves conflicts on reconnect. What rule do you use?",
                    "transcript": "Last-write-wins per field rather than per record, with the device clock replaced by a server timestamp assigned at sync. Per-record would throw away a surveyor's edit to one field because someone else touched a different field of the same record. Some conflicts still need a human, and those get flagged rather than resolved.",
                    "grounded_in": "lib/sync/resolver.dart",
                    "rationale": "Chose field-level granularity and knew what it costs.",
                },
                {
                    "prompt": "Why not trust the device clock?",
                    "transcript": "Field devices drift, and a couple of them had the date set wrong by months. A device clock would let one bad phone win every conflict forever. The server stamps on receipt, which isn't perfect ordering either but is at least one consistent clock.",
                    "grounded_in": "lib/sync/clock.dart",
                    "rationale": "Grounded in a real failure from real deployment.",
                },
                {
                    "prompt": "What's blowing the frame budget in gesture-lab?",
                    "transcript": "Mostly rebuilds — a gesture that sets state on the whole subtree instead of an animated leaf. The overlay makes it visible, and the fix is usually pushing the animation into a controller so only the painted layer changes rather than the widget tree.",
                    "grounded_in": "lib/overlay/frame_timing.dart",
                    "rationale": "Diagnosed the common Flutter performance cause correctly.",
                },
            ],
        },
    },
    {
        "name": "Roshni Iyer",
        "email": "roshni@test.com",
        "headline": "Systems engineer — Rust, WebAssembly, and low-level systems programming",
        "college": "IIIT Bangalore",
        "degree": "btech",
        "branch": "cse",
        "grad_year": 2027,
        "location": "Bangalore, India",
        "target_roles": ["backend"],
        "about": (
            "I write systems software in Rust — runtimes, allocators, and the kind of "
            "code where the borrow checker is the point rather than the obstacle. A lot "
            "of my work compiles to WebAssembly. I think about distributed systems "
            "through the same lens: what invariant holds, who enforces it, and what "
            "happens on partial failure. I keep durable state in PostgreSQL."
        ),
        "github": "roshni-iyer",
        "github_score": 94.0,
        "coding": [(CodingPlatform.CODEFORCES, "roshni_cf", 1900, 52), (CodingPlatform.LEETCODE, "roshni_lc", None, None)],
        "projects": [
            {
                "title": "wasm-runtime",
                "repo": "https://github.com/roshni-iyer/wasm-runtime",
                "description": "A WebAssembly runtime in Rust with a bytecode interpreter, fuel metering, and a sandbox that survives a hostile module.",
                "tech": ["Rust", "WebAssembly", "Systems Programming"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.96,
                "score": 93.0,
                "commits": 428,
            },
            {
                "title": "shard-router",
                "repo": "https://github.com/roshni-iyer/shard-router",
                "description": "Consistent-hashing shard router in Rust in front of PostgreSQL, with online resharding that moves ranges without dropping writes.",
                "tech": ["Rust", "PostgreSQL", "Distributed Systems"],
                "status": VerificationStatus.VERIFIED,
                "share": 0.93,
                "score": 90.0,
                "commits": 276,
            },
        ],
        "skills": [
            ("Rust", ProficiencyLevel.EXPERT, 0.93),
            ("WebAssembly", ProficiencyLevel.ADVANCED, 0.87),
            ("Systems Programming", ProficiencyLevel.EXPERT, 0.90),
            ("Distributed Systems", ProficiencyLevel.ADVANCED, 0.83),
            ("PostgreSQL", ProficiencyLevel.INTERMEDIATE, 0.72),
        ],
        "certificates": [
            ("Stanford CS140 Operating Systems (Audit)", "Stanford Online", VerificationStatus.UNVERIFIED),
        ],
        "experience": [
            {
                "company": "Cloudflare",
                "title": "Systems Engineering Intern",
                "type": EmploymentType.INTERNSHIP,
                "start": date(2026, 6, 1),
                "end": date(2026, 8, 31),
                "tech": ["Rust", "WebAssembly"],
                "description": "Worked on isolate startup cost in the edge runtime, cutting cold-start allocation by reusing pre-warmed linear memory.",
            }
        ],
        "interview": {
            "score": 89.0,
            "dimensions": {"technical_accuracy": 93.0, "code_understanding": 91.0, "problem_solving": 90.0, "repository_knowledge": 88.0, "communication": 79.0},
            "highlights": [
                {
                    "prompt": "shard-router reshards online. How do you move a range without dropping writes?",
                    "transcript": "The range goes into a dual-write state first — writes go to both old and new shard while a background copy catches up the history. Once the copy is caught up and lag is under a threshold, reads flip to the new shard, then writes stop going to the old one. The window where both accept writes is the price of not taking downtime. It needs the writes to be idempotent, which the router enforces by requiring a key on every write.",
                    "grounded_in": "src/resharding/plan.rs",
                    "rationale": "Complete migration protocol including the invariant it depends on.",
                },
                {
                    "prompt": "Your runtime meters fuel. What stops a module from just running forever?",
                    "transcript": "Every basic block decrements a fuel counter and traps at zero, so there's no loop that can escape it — the check is compiled in, not polled from outside. A watchdog thread would be racy and wouldn't interrupt a tight loop deterministically. The cost is a few percent of throughput, which is worth it to run untrusted code at all.",
                    "grounded_in": "src/interp/fuel.rs",
                    "rationale": "Chose the deterministic mechanism and justified the overhead.",
                },
                {
                    "prompt": "Where does unsafe appear in wasm-runtime, and how do you keep it honest?",
                    "transcript": "Linear memory access, mostly — bounds are checked once and then a slice is created without re-checking. Each unsafe block has a comment stating the invariant that makes it sound, and the invariants are tested with Miri in CI. If someone changes the bounds check, Miri catches the aliasing violation rather than it becoming a silent out-of-bounds read.",
                    "grounded_in": "src/memory/linear.rs",
                    "rationale": "Documented invariants and mechanically verified them.",
                },
            ],
        },
    },
]


def already_seeded(db: Session) -> bool:
    return (
        db.execute(select(User).where(User.email == DEMO_MARKER_EMAIL)).scalar_one_or_none() is not None
    )


def seed_demo(db: Session) -> None:
    recruiter = helpers.register_recruiter(
        db,
        full_name="Deepak Verma",
        company="TechNova Solutions",
        email=DEMO_RECRUITER_EMAIL,
        password=DEMO_PASSWORD,
    )
    print(f"Recruiter: {DEMO_RECRUITER_EMAIL} / {DEMO_PASSWORD}  (Deepak Verma, TechNova Solutions)")

    skills = {
        name: helpers.get_or_create_skill(db, name, category)
        for name, category in SKILL_CATALOGUE.items()
    }

    profiles = []
    for spec in STUDENTS:
        profile = helpers.register_candidate(db, email=spec["email"], password=DEMO_PASSWORD)
        helpers.fill_basic(
            db,
            profile,
            full_name=spec["name"],
            headline=spec["headline"],
            college=spec["college"],
            grad_year=spec["grad_year"],
            location=spec["location"],
            degree=spec["degree"],
            branch=spec["branch"],
            target_roles=spec["target_roles"],
            about=spec["about"],
        )
        helpers.fill_technical(
            db,
            profile,
            github_username=spec["github"],
            coding_profiles=[(platform, handle) for platform, handle, _, _ in spec["coding"]],
        )
        helpers.set_github_status(
            db, profile, status=VerificationStatus.VERIFIED, score=spec["github_score"]
        )

        for platform, _handle, rating, contests in spec["coding"]:
            # Only Codeforces has a documented public API, so it is the only
            # platform whose check can reach VERIFIED on hard data
            # (`CodingPlatform`'s docstring). The rest cap at FLAGGED via
            # reachability — seeding them VERIFIED would put a badge on screen
            # the real verifier could never award.
            if rating is not None:
                helpers.set_coding_status(
                    db,
                    profile,
                    platform=platform,
                    status=VerificationStatus.VERIFIED,
                    score=min(100.0, round(rating / 25.0, 1)),
                    payload={"rating": rating, "contests": contests, "max_rating": rating + 60},
                )
            else:
                helpers.set_coding_status(
                    db, profile, platform=platform, status=VerificationStatus.FLAGGED, score=None
                )

        first_project = None
        for project_spec in spec["projects"]:
            project = helpers.add_project(
                db,
                profile,
                title=project_spec["title"],
                repo_url=project_spec["repo"],
                description=project_spec["description"],
                technologies=project_spec["tech"],
                status=project_spec["status"],
                contribution_share=project_spec["share"],
                score=project_spec["score"],
                commit_count=project_spec["commits"],
            )
            if first_project is None:
                first_project = project

        for skill_name, proficiency, weight in spec["skills"]:
            helpers.add_skill(db, profile, skills[skill_name], proficiency, weight)

        for title, issuer, status in spec["certificates"]:
            helpers.add_certificate(db, profile, title=title, issuer=issuer, status=status)

        for position, experience in enumerate(spec["experience"]):
            helpers.add_experience(
                db,
                profile,
                company_name=experience["company"],
                title=experience["title"],
                employment_type=experience["type"],
                start_date=experience["start"],
                end_date=experience["end"],
                technologies=experience["tech"],
                description=experience["description"],
                position=position,
            )

        db.flush()
        if first_project is not None:
            helpers.add_completed_interview(
                db,
                profile,
                first_project,
                total_score=spec["interview"]["score"],
                highlights=spec["interview"]["highlights"],
                dimension_scores=spec["interview"]["dimensions"],
            )
        profiles.append(profile)

    from src.domains.student import service as student_service

    for profile in profiles:
        student_service.recompute_and_persist_strength(db, profile.id)
    db.commit()
    print(f"Students: {', '.join(spec['email'] for spec in STUDENTS)} (all password {DEMO_PASSWORD})")

    job = helpers.publish_job(db, recruiter, DEMO_JOB)
    print(f"Published job: {job.title} ({job.id})")

    helpers.recompute_all_matching(db)
    _report_scores(db, job)


def _report_scores(db: Session, job) -> None:  # noqa: ANN001 — JobPosting
    """Prints the pool the matcher actually produced.

    Worth the twenty lines: the demo's premise is a specific spread across a
    specific ten people, and the only way to know the evidence above still
    produces it — after a weight change, a threshold change, or an edit to a
    persona — is to read the scores back out. A silent seed that publishes an
    empty pipeline looks identical to a working one until someone logs in.
    """
    from src.domains.matching.models import MatchResult
    from src.domains.auth.models import CandidateProfile, User

    rows = db.execute(
        select(User.full_name, MatchResult.match_score)
        .join(CandidateProfile, CandidateProfile.id == MatchResult.candidate_profile_id)
        .join(User, User.id == CandidateProfile.user_id)
        .where(MatchResult.job_posting_id == job.id)
        .order_by(MatchResult.match_score.desc())
    ).all()

    print(f"\n  Matched pool for '{job.title}': {len(rows)} of {len(STUDENTS)} students")
    for name, score in rows:
        print(f"    {float(score):5.1f}  {name}")

    matched_names = {name for name, _ in rows}
    missing = [spec["name"] for spec in STUDENTS if spec["name"] not in matched_names]
    if missing:
        print(f"    below MATCH_THRESHOLD (not on the board): {', '.join(missing)}")
