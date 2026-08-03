# GroundTruth AI — Data Model

Design-only reference for the entire platform's entity-relationship model, including
domains that are not implemented yet. Only the tables listed in §0.2 ("Implemented in
this phase") exist as SQLAlchemy models / migrations today — everything else here is a
forward design so later phases build on a single agreed schema instead of improvising
one feature at a time.

## 0. Conventions

### 0.1 Base patterns (apply to every table unless noted)

- **Primary key**: `id UUID`, application-generated (`uuid.uuid4`), via `UUIDPrimaryKeyMixin`
  (`src/shared/db_mixins.py`). No DB-side `gen_random_uuid()` — kept consistent with the
  existing `users` table so ids are available before `INSERT`.
- **Timestamps**: `created_at`, `updated_at`, both `timestamptz`, application-side defaults
  (`TimestampMixin`, same file). No DB triggers.
- **Soft delete**: `deleted_at timestamptz NULL`, via a new `SoftDeleteMixin` (added in Part B
  alongside the other mixins). Applied only to tables listed in §0.3 — most tables are hard
  parent/child data with no independent "trash" state and don't need it.
- **Enums**: Postgres native enum (`SAEnum(PyEnum, name="...", native_enum=True)`), matching
  `UserRole`/`user_role` in the existing `auth` domain.
- **Naming**: tables `snake_case` plural; FK columns `<singular_table>_id`; every FK is
  indexed (Postgres does not auto-index FK columns).

### 0.2 Implemented in this phase (Part B)

`companies`, `skills`, `candidate_skills`, `async_jobs`, `audit_log`, plus an ALTER on the
existing `recruiter_profiles` (adds `company_id`). Everything else in this document is design
only — no model, no migration — until its own phase starts.

### 0.2.1 Implemented by the student profile builder (Part C)

Migration `c3f1a9d47b02`, models in `src/domains/student/models.py`:

- **ALTER `candidate_profiles`** — section 1 fields (`headline`, `college`, `degree`, `branch`,
  `graduation_year`, `location`, `target_role`) plus the derived `profile_strength` and
  `is_discoverable`. All section-1 fields are nullable: the builder is a multi-sitting flow, so
  a partially filled profile is a valid persisted state. `degree`/`branch`/`target_role` are
  native enums (`degree_type`, `branch`, `target_role`) rather than free text, because
  recruiters filter on them.
- **`github_accounts`**, **`coding_platform_accounts`**, **`certificates`** — as designed in §3,
  with one deviation: `github_accounts.github_user_id` is **nullable**. The builder only
  receives a username/URL; resolving GitHub's stable numeric id needs an API call owned by the
  verification worker. It stays `UNIQUE` — Postgres allows many NULLs under a unique index, so
  the constraint binds once a worker fills it in.
- **`projects`** *(new — not in §3)* — section 3 accepts "a repo URL **or** a described
  project". §3's `repositories` cannot hold the latter: it is GitHub-shaped
  (`github_repo_id BIGINT NOT NULL`, `is_fork`, `primary_language`) and only populatable from
  the GitHub API. `projects` carries a `kind` discriminator (`repository|described`) with a
  nullable `repo_url`. **`repositories` remains unbuilt**, reserved for the GitHub-sync phase.
- **`experiences`** — as designed in §3, plus `employment_type` (`internship|freelance|
  part_time`) and a `technologies text[]`, neither of which §3 included.

A shared `verification_status` enum (`unverified|pending|verified|rejected`) is used by
`github_accounts`, `coding_platform_accounts`, `projects` and `certificates`.

**`evidence_records` is deliberately still unbuilt.** It is a derived *scoring* hub: it carries
`weight NUMERIC NOT NULL` and a `source_type` naming finished artifacts (`repository_analysis`,
`coding_platform_snapshot`), and it has no `status` column. At claim time no analysis or
snapshot exists and no weight is computable, so speculative rows there would break the §0.5
guarantee that every evidence record traces back to concrete analyzed evidence. Pending
verification is instead tracked by each claim row's own `verification_status` plus an
`async_jobs` row (`status=pending`) — see `src/domains/student/evidence.py`. Phase II workers
write `evidence_records` once a real analysis or snapshot exists.

### 0.3 Soft-delete strategy

A row is soft-deleted (not the same as `is_active`/`revoked_at`, which are domain states) when
a **user-initiated removal** must not cascade-destroy data other rows still reference for
historical/audit reasons. Applied to: `github_accounts`, `repositories`,
`coding_platform_accounts`, `certificates`, `experiences`, `evidence_records`, `applications`,
`jobs`. Queries against these tables filter `deleted_at IS NULL` by default (a repository
pattern / query helper, not a DB-level `WHERE`, so audits and admin tooling can still see
everything).

**Not** soft-deleted: pure join/associative tables (`candidate_skills`, `job_requirements`),
append-only event logs (`audit_log`, `application_events`), and anything whose parent already
soft-deletes for it (e.g. `repository_analyses` disappears from view when its `repository`
does — no independent `deleted_at` needed).

### 0.4 created_at / updated_at conventions

Both are set application-side at the ORM layer (`_utcnow()` default / `onupdate` in
`TimestampMixin`), not DB defaults — chosen in Phase 2 so behavior is identical whether a row
is inserted via the ORM in tests (SQLite-free, real Postgres in a rolled-back transaction) or
in production. `created_at` is immutable after insert (no code path re-sets it).
Append-only tables (`audit_log`, `application_events`, `interview_answers`) have `created_at`
only — no `updated_at`, since a row that can change isn't a valid event record.

### 0.5 Evidence traceability

Every number a recruiter sees (a skill proficiency, an evidence-vector dimension, an interview
score) must be traceable back to the raw evidence that produced it. `evidence_records` is the
hub:

```
evidence_records
├── source_type: repository_analysis | coding_platform_snapshot | certificate
│                | experience | interview_score
├── source_id: UUID  (polymorphic — the PK of whichever *one* of the five source
│              tables `source_type` names; enforced at the application layer, not
│              a DB constraint, since Postgres has no native polymorphic FK)
├── candidate_profile_id: UUID  (always present — the candidate this evidence is about)
├── skill_id: UUID NULL  (set when the evidence contributes to a specific skill)
└── weight: numeric  (this evidence's contribution to whatever it feeds)
```

`candidate_skills.evidence_weight` is a **denormalized rollup** of the `evidence_records` rows
that reference that `(candidate, skill)` pair — recomputed, not hand-edited, whenever new
evidence lands. `embeddings` (the vector fed to search/matching) is derived from
`evidence_records` + `candidate_skills` in aggregate, so an embedding is explainable by walking
back through `evidence_records` to the concrete repository analysis, test score, or interview
answer that moved it.

### 0.6 Relationship cardinality summary

| Kind | Example |
|---|---|
| One-to-one | `users` ↔ `candidate_profiles`, `users` ↔ `recruiter_profiles` |
| One-to-many | `companies` → `recruiter_profiles`, `candidate_profiles` → `github_accounts`, `github_accounts` → `repositories`, `jobs` → `applications` |
| Many-to-many (via associative entity) | `candidate_profiles` ↔ `skills` through `candidate_skills` (carries `proficiency`/`evidence_weight`), `jobs` ↔ `skills` through `job_requirements` (carries `min_proficiency`/`weight`) |
| Polymorphic | `evidence_records.source_*` → one of five source tables; `embeddings.entity_*` → any embeddable entity |

---

## 1. Identity

### `users` *(existing — `src/domains/auth/models.py`, unchanged)*

The single authentication identity for every role. Documented here only for cross-reference —
see §Authentication Module in `README.md` for the full column list. Key columns relevant to
this document: `id`, `email` (unique), `role` (`candidate|recruiter|admin`), `full_name`,
`is_email_verified`, `is_active`.

### `candidate_profiles` *(existing, unchanged in this phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | NO | FK → `users.id`, `ondelete=CASCADE`, **unique** (1:1) |
| `phone_number` | String(20) | NO | |
| `created_at`/`updated_at` | timestamptz | NO | |

**Relationships**: `user` (back-populates `User.candidate_profile`). **Future** (not this
phase): `github_accounts`, `coding_platform_accounts`, `certificates`, `experiences`,
`candidate_skills`, `applications` all FK to `candidate_profiles.id`.

### `recruiter_profiles` *(existing — extended in Part B)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | NO | FK → `users.id`, `ondelete=CASCADE`, **unique** (1:1) |
| `company_name` | String(200) | NO | kept as free-text fallback (recruiter self-reports before their company row is matched/created) |
| `company_id` | UUID | **YES** | **new** — FK → `companies.id`, `ondelete=SET NULL`. Nullable: a recruiter can exist before their company is deduplicated into `companies` |
| `created_at`/`updated_at` | timestamptz | NO | |

**Relationships**: `user`, `company` (new, many-to-one).
**Cascade**: deleting a `company` sets `company_id` NULL on its recruiters rather than
deleting recruiter accounts.

### `companies` *(new — Part B)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `name` | String(200) | NO | |
| `domain` | String(255) | YES | primary email/website domain, e.g. `acme.com` — used to auto-match recruiters by email domain in a later phase |
| `industry` | String(100) | YES | |
| `size` | Enum(`company_size`: `1-10`,`11-50`,`51-200`,`201-1000`,`1000+`) | YES | |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `name` (case-insensitive, enforced at the application layer via
normalized-lowercase comparison — Postgres `UNIQUE` stays case-sensitive on `String`).
**Indexes**: `domain` (lookup by email domain).
**Relationships**: `recruiter_profiles` (one-to-many), future `jobs` (one-to-many).
**Cascade**: none inbound (nothing hard-depends on a company row existing).

---

## 2. Skills

### `skills` *(new — Part B)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `name` | String(100) | NO | e.g. `"React"`, `"PostgreSQL"` |
| `category` | Enum(`skill_category`: `language`,`framework`,`database`,`devops`,`cloud`,`tool`,`soft_skill`,`other`) | NO | |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `name` (normalized-lowercase at the application layer, same reasoning
as `companies.name`, to avoid `"React"` / `"react"` duplicates).
**Relationships**: `candidate_skills` (one-to-many → many-to-many with candidates),
future `job_requirements` (one-to-many → many-to-many with jobs).

### `candidate_skills` *(new — Part B, associative entity)*

Deliberately modeled as a full entity (not a bare join table) because the relationship itself
carries data — this is *where* a candidate's proficiency and its evidence backing live.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `candidate_profile_id` | UUID | NO | FK → `candidate_profiles.id`, `ondelete=CASCADE` |
| `skill_id` | UUID | NO | FK → `skills.id`, `ondelete=CASCADE` |
| `proficiency` | Enum(`proficiency_level`: `novice`,`intermediate`,`advanced`,`expert`) | NO | derived, not self-reported |
| `evidence_weight` | Numeric(5,4) | NO, default `0` | 0–1 rollup of contributing `evidence_records.weight` — recomputed by the scoring pipeline, never hand-edited |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `(candidate_profile_id, skill_id)` — one row per candidate/skill pair.
**Indexes**: `candidate_profile_id`, `skill_id` (both FK lookups).
**Cascade**: deleting a candidate or a skill deletes the join row (nothing else references it).

---

## 3. Evidence

### `github_accounts` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `candidate_profile_id` | UUID | NO | FK → `candidate_profiles.id`, `ondelete=CASCADE` |
| `github_user_id` | BigInteger | NO | GitHub's numeric user id (stable across username changes) |
| `github_username` | String(100) | NO | |
| `access_token_encrypted` | Text | YES | app-level-encrypted OAuth token; NULL once scope is revoked |
| `scopes` | String(500) | NO, default `""` | space-separated OAuth scopes granted |
| `connected_at` | timestamptz | NO | |
| `deleted_at` | timestamptz | YES | soft-delete: candidate revokes access |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `github_user_id`; `(candidate_profile_id)` is *not* unique — a
candidate could theoretically reconnect a different GitHub account after disconnecting one
(old row stays soft-deleted).
**Relationships**: `repositories` (one-to-many).

### `repositories` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `github_account_id` | UUID | NO | FK → `github_accounts.id`, `ondelete=CASCADE` |
| `github_repo_id` | BigInteger | NO | GitHub's numeric repo id |
| `full_name` | String(255) | NO | `owner/repo` |
| `is_private` | Boolean | NO | |
| `is_fork` | Boolean | NO | |
| `visibility_consented` | Boolean | NO, default `false` | candidate must explicitly opt a private repo in before analysis reads it |
| `primary_language` | String(50) | YES | |
| `deleted_at` | timestamptz | YES | soft-delete: candidate un-links the repo |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `github_repo_id`.
**Indexes**: `github_account_id`.
**Relationships**: `repository_analyses` (one-to-many). **Cascade**: deleting the owning
GitHub account cascades to repositories, which cascades to their analyses — none of that data
is meaningful without the link that authorized reading it.

### `repository_analyses` *(new — future phase)*

One row per analysis run (static analysis + contribution detection) against a repository —
append-heavy, re-run over time as the repo changes.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `repository_id` | UUID | NO | FK → `repositories.id`, `ondelete=CASCADE` |
| `status` | Enum(`analysis_status`: `queued`,`running`,`completed`,`failed`) | NO | |
| `commit_sha` | String(40) | YES | HEAD at analysis time |
| `contribution_summary` | JSONB | YES | lines/commits/PRs attributable to the candidate |
| `static_analysis_summary` | JSONB | YES | tree-sitter/AST-derived findings |
| `error` | Text | YES | set when `status=failed` |
| `started_at` / `completed_at` | timestamptz | YES | |
| `created_at`/`updated_at` | timestamptz | NO | |

**Indexes**: `repository_id`, `status` (worker polling).
**Relationships**: referenced by `evidence_records.source_id` when
`source_type=repository_analysis`.

### `coding_platform_accounts` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `candidate_profile_id` | UUID | NO | FK → `candidate_profiles.id`, `ondelete=CASCADE` |
| `platform` | Enum(`coding_platform`: `leetcode`,`codeforces`,`hackerrank`) | NO | |
| `handle` | String(100) | NO | username on that platform |
| `verified_at` | timestamptz | YES | NULL until the verification ping succeeds |
| `deleted_at` | timestamptz | YES | soft-delete |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `(candidate_profile_id, platform)` — one handle per platform per
candidate. **Relationships**: `coding_platform_snapshots` (one-to-many).

### `coding_platform_snapshots` *(new — future phase)*

Periodic point-in-time pulls of a candidate's stats on a linked platform (append-only —
history matters, e.g. rating trend over time).

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `coding_platform_account_id` | UUID | NO | FK → `coding_platform_accounts.id`, `ondelete=CASCADE` |
| `snapshot_data` | JSONB | NO | raw platform-specific payload (rating, problems solved, contest history, ...) |
| `captured_at` | timestamptz | NO | |

No `updated_at` — a snapshot is immutable once captured.
**Indexes**: `(coding_platform_account_id, captured_at)`.
**Relationships**: referenced by `evidence_records.source_id` when
`source_type=coding_platform_snapshot`.

### `certificates` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `candidate_profile_id` | UUID | NO | FK → `candidate_profiles.id`, `ondelete=CASCADE` |
| `title` | String(200) | NO | |
| `issuer` | String(200) | NO | |
| `issued_at` | Date | YES | |
| `credential_url` | String(500) | YES | |
| `file_url` | String(500) | YES | uploaded artifact, if any |
| `verification_status` | Enum(`verification_status`: `unverified`,`pending`,`verified`,`rejected`) | NO, default `unverified` | |
| `deleted_at` | timestamptz | YES | soft-delete |
| `created_at`/`updated_at` | timestamptz | NO | |

**Indexes**: `candidate_profile_id`.
**Relationships**: referenced by `evidence_records.source_id` when `source_type=certificate`.

### `experiences` *(new — future phase)*

Self-reported work history, optionally evidence-backed (e.g. a GitHub org membership
corroborating an employer claim).

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `candidate_profile_id` | UUID | NO | FK → `candidate_profiles.id`, `ondelete=CASCADE` |
| `company_name` | String(200) | NO | free text — not FK'd to `companies` (a candidate's past employer isn't necessarily a GroundTruth customer) |
| `title` | String(200) | NO | |
| `start_date` | Date | NO | |
| `end_date` | Date | YES | NULL = current role |
| `description` | Text | YES | |
| `deleted_at` | timestamptz | YES | soft-delete |
| `created_at`/`updated_at` | timestamptz | NO | |

**Indexes**: `candidate_profile_id`.
**Relationships**: referenced by `evidence_records.source_id` when `source_type=experience`.

### `evidence_records` *(new — future phase)*

The traceability hub — see §0.5.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `candidate_profile_id` | UUID | NO | FK → `candidate_profiles.id`, `ondelete=CASCADE` |
| `skill_id` | UUID | YES | FK → `skills.id`, `ondelete=SET NULL` — set when this evidence contributes to a specific skill |
| `source_type` | Enum(`evidence_source_type`: `repository_analysis`,`coding_platform_snapshot`,`certificate`,`experience`,`interview_score`) | NO | discriminator for the polymorphic `source_id` |
| `source_id` | UUID | NO | PK of whichever table `source_type` names (application-enforced, no DB FK — Postgres has no native polymorphic constraint) |
| `weight` | Numeric(5,4) | NO | this record's contribution, 0–1 |
| `deleted_at` | timestamptz | YES | soft-delete: evidence invalidated (e.g. repo access revoked) |
| `created_at`/`updated_at` | timestamptz | NO | |

**Indexes**: `candidate_profile_id`, `skill_id`, `(source_type, source_id)`.
**Relationships**: feeds `candidate_skills.evidence_weight` (recomputed) and, in aggregate,
`embeddings` for that candidate.

---

## 4. Interview

### `interviews` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `candidate_profile_id` | UUID | NO | FK → `candidate_profiles.id`, `ondelete=CASCADE` |
| `application_id` | UUID | YES | FK → `applications.id`, `ondelete=SET NULL` — an interview can be job-specific or a standalone evidence-building session |
| `status` | Enum(`interview_status`: `scheduled`,`in_progress`,`completed`,`abandoned`) | NO | |
| `started_at` / `completed_at` | timestamptz | YES | |
| `created_at`/`updated_at` | timestamptz | NO | |

**Indexes**: `candidate_profile_id`, `application_id`.
**Relationships**: `interview_questions` (one-to-many).

### `interview_questions` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `interview_id` | UUID | NO | FK → `interviews.id`, `ondelete=CASCADE` |
| `skill_id` | UUID | YES | FK → `skills.id`, `ondelete=SET NULL` — the skill this question probes |
| `sequence` | Integer | NO | order within the interview |
| `prompt` | Text | NO | |
| `generated_from` | JSONB | YES | trace to the candidate-specific code diff/context the question was grounded in (per README's "ground every question in candidate-specific code diffs") |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `(interview_id, sequence)`.
**Relationships**: `interview_answers` (one-to-one per question, in practice).

### `interview_answers` *(new — future phase, append-only)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `interview_question_id` | UUID | NO | FK → `interview_questions.id`, `ondelete=CASCADE`, **unique** (one answer per question) |
| `transcript` | Text | NO | |
| `answered_at` | timestamptz | NO | |
| `created_at` | timestamptz | NO | no `updated_at` — an answer is immutable once submitted |

**Relationships**: `interview_scores` (one-to-many — a question can be scored on several
rubric dimensions).

### `interview_scores` *(new — future phase, append-only)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `interview_answer_id` | UUID | NO | FK → `interview_answers.id`, `ondelete=CASCADE` |
| `dimension` | String(50) | NO | e.g. `correctness`, `depth`, `communication` |
| `score` | Numeric(4,2) | NO | |
| `rationale` | Text | YES | model-generated explanation, for the "recruiter-reviewable" transparency goal |
| `created_at` | timestamptz | NO | no `updated_at` — immutable |

**Indexes**: `interview_answer_id`.
**Relationships**: referenced by `evidence_records.source_id` when
`source_type=interview_score`.

---

## 5. Recruiting

### `jobs` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `company_id` | UUID | NO | FK → `companies.id`, `ondelete=CASCADE` |
| `created_by_user_id` | UUID | YES | FK → `users.id`, `ondelete=SET NULL` — job posting outlives the recruiter's account |
| `title` | String(200) | NO | |
| `description` | Text | NO | |
| `status` | Enum(`job_status`: `draft`,`open`,`paused`,`closed`) | NO, default `draft` | |
| `deleted_at` | timestamptz | YES | soft-delete |
| `created_at`/`updated_at` | timestamptz | NO | |

**Indexes**: `company_id`, `status`.
**Relationships**: `job_requirements` (one-to-many), `applications` (one-to-many).

### `job_requirements` *(new — future phase, associative entity)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `job_id` | UUID | NO | FK → `jobs.id`, `ondelete=CASCADE` |
| `skill_id` | UUID | NO | FK → `skills.id`, `ondelete=CASCADE` |
| `min_proficiency` | Enum(`proficiency_level`, shared with `candidate_skills`) | NO | |
| `weight` | Numeric(5,4) | NO, default `1` | this requirement's importance in ranking, recruiter-adjustable per README's "recruiter-reviewable weighting" goal |
| `is_required` | Boolean | NO, default `true` | `false` = nice-to-have |

**Unique constraints**: `(job_id, skill_id)`.
**Indexes**: `job_id`, `skill_id`.

### `applications` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `job_id` | UUID | NO | FK → `jobs.id`, `ondelete=CASCADE` |
| `candidate_profile_id` | UUID | NO | FK → `candidate_profiles.id`, `ondelete=CASCADE` |
| `status` | Enum(`application_status`: `applied`,`screening`,`interviewing`,`offered`,`rejected`,`withdrawn`) | NO, default `applied` | current status — history lives in `application_events` |
| `deleted_at` | timestamptz | YES | soft-delete: withdrawal, distinct from `status=withdrawn` which is a visible state change |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `(job_id, candidate_profile_id)` — one active application per
candidate per job.
**Relationships**: `application_events` (one-to-many), `interview_slots` (one-to-many).

### `application_events` *(new — future phase, append-only audit trail)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `application_id` | UUID | NO | FK → `applications.id`, `ondelete=CASCADE` |
| `actor_user_id` | UUID | YES | FK → `users.id`, `ondelete=SET NULL` — NULL for system-generated events |
| `from_status` | Enum(`application_status`) | YES | NULL on the initial `applied` event |
| `to_status` | Enum(`application_status`) | NO | |
| `note` | Text | YES | |
| `created_at` | timestamptz | NO | no `updated_at` — event log |

**Indexes**: `application_id`.

### `interview_slots` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `application_id` | UUID | NO | FK → `applications.id`, `ondelete=CASCADE` |
| `interview_id` | UUID | YES | FK → `interviews.id`, `ondelete=SET NULL` — set once the scheduled slot is actually taken |
| `scheduled_at` | timestamptz | NO | |
| `duration_minutes` | Integer | NO | |
| `status` | Enum(`slot_status`: `proposed`,`confirmed`,`completed`,`cancelled`) | NO, default `proposed` | |
| `created_at`/`updated_at` | timestamptz | NO | |

**Indexes**: `application_id`, `scheduled_at`.

---

## 6. Matching

### `embeddings` *(new — future phase)*

Generic vector store, backed by `pgvector` (already an installed dependency). Polymorphic by
design — the same table serves candidate evidence vectors, job requirement vectors, and any
future embeddable entity, instead of one vector column bolted onto each entity's own table.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `entity_type` | Enum(`embeddable_entity_type`: `candidate_profile`,`job`,`repository`) | NO | |
| `entity_id` | UUID | NO | PK of whichever table `entity_type` names — application-enforced, no DB FK (same polymorphism reasoning as `evidence_records.source_id`) |
| `vector` | `pgvector.Vector` | NO | dimension fixed by `model_version`'s embedding model |
| `model_version` | String(50) | NO | e.g. `"text-embedding-3-large"` — re-embedding on a model upgrade inserts new rows rather than overwriting, so search can be A/B'd across model versions |
| `created_at`/`updated_at` | timestamptz | NO | |

**Unique constraints**: `(entity_type, entity_id, model_version)` — one current vector per
entity per model version.
**Indexes**: `(entity_type, entity_id)`; an `ivfflat`/`hnsw` vector index on `vector` scoped
per `model_version` partition, added when the matching phase actually ships (premature to
tune now, before real data volume exists).

---

## 7. Platform

### `async_jobs` *(new — Part B)*

Background-job bookkeeping (Celery is already a `pyproject.toml` dependency; this table is the
durable status record a Celery task ID alone doesn't give you — retries, error text, and
result surfaced to the UI).

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `job_type` | String(100) | NO | e.g. `repository_analysis`, `email_send` |
| `status` | Enum(`async_job_status`: `pending`,`running`,`succeeded`,`failed`) | NO, default `pending` | |
| `payload` | JSONB | YES | input args |
| `result` | JSONB | YES | set on success |
| `error` | Text | YES | set on failure |
| `attempts` | Integer | NO, default `0` | |
| `created_at`/`updated_at` | timestamptz | NO | |

**Indexes**: `status`, `job_type` (worker/dashboard polling).
**Cascade**: none — a job record's referenced entities (e.g. which repository) live inside
`payload`, not as FKs, since a job type's shape varies too much for a fixed schema.

### `notifications` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `user_id` | UUID | NO | FK → `users.id`, `ondelete=CASCADE` |
| `type` | String(100) | NO | e.g. `interview_invitation`, `application_status_changed` |
| `payload` | JSONB | NO | |
| `read_at` | timestamptz | YES | NULL = unread |
| `created_at` | timestamptz | NO | no `updated_at` — a notification's content doesn't change, only `read_at` |

**Indexes**: `(user_id, read_at)`.

### `conversations` *(new — future phase)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `application_id` | UUID | YES | FK → `applications.id`, `ondelete=CASCADE` — messaging is always in the context of an application in the initial design |
| `created_at`/`updated_at` | timestamptz | NO | |

**Relationships**: `messages` (one-to-many). A `conversation_participants` join table
(`conversation_id`, `user_id`) is implied but deferred — not needed until messaging actually
ships with real multi-party requirements.

### `messages` *(new — future phase, append-only)*

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `conversation_id` | UUID | NO | FK → `conversations.id`, `ondelete=CASCADE` |
| `sender_user_id` | UUID | YES | FK → `users.id`, `ondelete=SET NULL` |
| `body` | Text | NO | |
| `created_at` | timestamptz | NO | no `updated_at` — messages are immutable once sent |

**Indexes**: `(conversation_id, created_at)`.

### `audit_log` *(new — Part B, append-only, immutable)*

Platform-wide audit trail — distinct from `application_events` (which is a domain-specific
status-change log). Every state-changing action that matters for compliance/security review
writes one row here.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | PK | |
| `actor_user_id` | UUID | YES | FK → `users.id`, `ondelete=SET NULL` — log survives account deletion; NULL for system actions |
| `action` | String(100) | NO | e.g. `job.created`, `candidate_profile.updated`, `application.status_changed` |
| `entity_type` | String(100) | NO | |
| `entity_id` | UUID | NO | polymorphic, application-enforced, no FK (same reasoning as `evidence_records.source_id`) |
| `before` | JSONB | YES | entity state pre-change |
| `after` | JSONB | YES | entity state post-change |
| `ip_address` | String(64) | YES | |
| `created_at` | timestamptz | NO | **no `updated_at`, no `deleted_at`** — a true audit log must be immutable and un-deletable by application code |

**Indexes**: `actor_user_id`, `(entity_type, entity_id)`, `created_at`.
**Cascade**: `SET NULL` only on `actor_user_id` — the row itself is never deleted by any FK
cascade from elsewhere (nothing else owns it).
