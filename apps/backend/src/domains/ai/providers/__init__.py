"""Concrete adapters behind the protocols in `domains/ai/llm.py`.

Nothing outside this package may import a vendor SDK, and nothing outside
`domains/ai/` may import from this package — callers go through the factory
functions in `llm.py`, which is what keeps "which model answered" a decision
made in one file.

| Module                  | Implements                                        |
|-------------------------|---------------------------------------------------|
| `gemini_client.py`      | shared client, schema dialect, error translation  |
| `gemini_extractor.py`   | `ResumeExtractor`                                 |
| `gemini_interview.py`   | `InterviewQuestionGenerator` + `InterviewAnswerEvaluator` |
| `gemini_job_extractor.py` | `JobRequirementExtractor`                       |
| `local_embedder.py`     | `Embedder` — in-process, no API call              |

The modules are deliberately not re-exported here. `llm.py` imports each one
lazily inside the factory that needs it, so a process that never runs an
interview never pays to import the interview adapter — and, more importantly,
`sentence_transformers` (a torch dependency measured in hundreds of megabytes)
is only loaded by a process that actually embeds.
"""
