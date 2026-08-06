# DEMO — GroundTruth in under 10 minutes

A click path that proves the three things GroundTruth actually claims: **verification**
(a skill backed by real evidence, not a self-report), the **code-grounded AI interview**
(questions generated from *this candidate's own* repository analysis), and **two-way matching**
(the same computed score drives both the recruiter's candidate list and the candidate's job feed).

## 0. Bring it up (~3 min, mostly image builds the first time)

```bash
# Infra + app, all tiers (api, three worker tiers, web)
docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.prod.yml up -d

# Seed demo data — idempotent, safe to re-run
make seed
```

| Service | URL |
|---|---|
| Web app | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| MailHog (every outbound email) | http://localhost:8025 |
| MinIO console | http://localhost:9001 (`groundtruth` / `groundtruth-dev-secret`) |

> **Note on AI features.** Job-requirement extraction and the AI interview call Google Gemini, and
> resume import falls back to it for documents its deterministic parser can't read. Set
> `GOOGLE_API_KEY` in `apps/backend/.env` ([get one here](https://aistudio.google.com/apikey)) —
> it is the only LLM key the project uses.
>
> Without it those steps fail *gracefully and visibly* (the job reverts to `draft` with an
> `extraction_error`, the dead-letter surface offers a retry) rather than hanging or corrupting
> state — which is itself worth showing. Matching needs no key at all: it embeds in-process. The
> seeded data below includes a **pre-computed interview and pre-computed match results**, so the
> demo path works fully either way.

## Seeded credentials

Password for every seeded account: **`SeedPass1!`**

| Role | Email | What they show |
|---|---|---|
| Candidate | `ada.lovelace@seed.groundtruth.dev` | Fully verified — 2 verified repos with high contribution share, a completed code interview (88/100), a verified certificate. Application at **Interview Scheduled**. |
| Candidate | `margaret.hamilton@seed.groundtruth.dev` | Fully verified, completed interview (92/100). Application at **Hired**. |
| Candidate | `grace.kim@seed.groundtruth.dev` | Partially verified — verified GitHub, one repo still `PENDING`. Application at **Shortlisted**. |
| Candidate | `alan.turing@seed.groundtruth.dev` | A **failed** verification — his listed repo was checked and `REJECTED` (near-empty fork). Application at **Rejected**. |
| Candidate | `marie.curie@seed.groundtruth.dev` | Freshly registered, not yet discoverable — shows the "incomplete profile" state. |
| Recruiter | `grace.hopper@seed.groundtruth.dev` | Acme Corp — owns the Backend + Frontend jobs and the populated pipeline. |
| Recruiter | `peter.gibbons@seed.groundtruth.dev` | Initech — a *second* company, for proving cross-tenant isolation. |

## 1. Verification is real, not a checkbox (~2 min)

Log in as **`ada.lovelace@seed.groundtruth.dev`**.

- The **dashboard home** shows profile strength with a per-section breakdown, and every claim
  carries its *own* verification badge — "Saved" and "Verified" are deliberately two different
  badges, because a filled-in field is not a proven one.
- Each **repository card** shows the contribution share computed from the real GitHub API
  (`92%`, `88%`) plus the interview score for that repo.
- Now log in as **`alan.turing@seed.groundtruth.dev`** and look at his repository: same UI, but
  the badge reads **"Could not verify"** and the contribution share is `2%`. *Nothing about the
  claim was deleted or hidden* — it's shown, with the verification result attached. That contrast
  is the product.

## 2. The code-grounded interview (~2 min)

Still as Ada: open the verified **Distributed Cache** repository card → the interview score.

- Every question is grounded in a specific file from *her* stored repository analysis — not a
  generic "tell me about caching" question.
- Each answer is scored on five fixed dimensions with explicit weights
  (`technical_accuracy 30% · code_understanding 25% · problem_solving 20% ·
  repository_knowledge 15% · communication 10%`), and every dimension carries a written rationale.
  The weights are configurable (`INTERVIEW_WEIGHT_*`) and must sum to 1.0 or the API refuses to
  start; changing them never rescores a past interview, because each row stores the
  `rubric_version` it was sat under.
- The same report is what a recruiter sees on the evidence card in step 4 — one builder, two
  audiences, no divergence.

> **Two interview types.** The above is a **repository interview**, started by the candidate on one
> verified repo. There is also a **profile interview**, generated *automatically* once verification
> settles and grounded in everything verified about the candidate. That one is what makes a
> candidate with no verifiable repository still able to become discoverable — check MailHog after
> registering a new candidate to see the invitation email.

## 3. Two-way matching (~1 min)

Still as Ada → **Job matches**.

- She's matched to *Backend Engineer Intern* and *Data Engineer Intern*, each with a score.

> ⚠️ **The scores here are no longer the `66.7` / `60.1` this file used to quote.** The rank-fusion
> formula gained an interview term and a coding-competency term, and the threshold moved from 50 to
> 60 — so every match score in the system changed, and pairs that scored just above 50 may now be
> absent entirely. `make seed` computes these live rather than hardcoding them; read the real
> numbers off the running app and update this line. The numbers have not been re-observed since the
> formula changed.
- Each match shows *why*: which must-have skills she has, with a checkmark per skill traced back
  to the verified repository that evidences it.
- Nothing here is computed in the browser — every number is read straight off `match_results`,
  written by the same rank-fusion pass that produces the recruiter's list.

## 4. The recruiter's view of the same computation (~2 min)

Log out, log in as **`grace.hopper@seed.groundtruth.dev`** → **Job postings** →
*Backend Engineer Intern* → **View pipeline**.

- The **Kanban board** has real occupants in Applied / Shortlisted / Interview Scheduled /
  Hired / Rejected — plus a **Matched** column of candidates who cleared the threshold but haven't
  applied (matching is a computation, not an action).
- Click a candidate → the **evidence card**: contribution analysis, the *full interview transcript
  with per-criterion scores*, coding-platform stats, certificates. Every number is traceable; none
  of it is LLM-narrated after the fact.
- **Private team notes** are visibly marked *not visible to the candidate* — and they genuinely
  aren't: there is no candidate-reachable route for notes at all (asserted by a test).
- Try an **illegal transition** (e.g. Applied → Hired directly, via the API at `/docs`): you get a
  **409** with an explicit message. The frontend surfaces that error rather than swallowing it.
- **Analytics** → funnel counts, per-stage conversion, and time-to-first-response, computed from
  the `audit_log` trail that every stage transition writes.

## 5. Prove the tenant boundary (~30 sec)

Log in as **`peter.gibbons@seed.groundtruth.dev`** (Initech, the second company).

- He sees only Initech's *Data Engineer Intern* job. Acme's pipeline, notes, and candidates are
  invisible — and not merely hidden in the UI: requesting Acme's pipeline URL directly returns
  **403**, enforced at the query layer (asserted by `tests/integration/test_cross_tenant_authz.py`).

## 6. Email is real (~30 sec)

Register a brand-new candidate at http://localhost:5173. Signup has no verification step — the
account is created, signed in and dropped on the dashboard in one request, and **no email is sent
at that point**. Open http://localhost:8025 to confirm the outbox is empty.

Then exercise the two mails that do exist:

- Hit **Forgot password** and open MailHog: the reset link is really there, really delivered over
  SMTP. Click it and set a new password — the token is single-use and revokes existing sessions.
- As a recruiter, move any application a stage: the candidate gets a **stage-change email** in
  MailHog *and* an in-app notification on the bell.

---

**Total: ~10 minutes.** What was proven: a claim can reach `VERIFIED` **or** `REJECTED` from real
third-party evidence; an interview is grounded in the candidate's own code and scored against a
fixed rubric; one match computation serves both sides; the pipeline enforces its own state machine;
tenants are isolated at the query layer; and email actually sends.
