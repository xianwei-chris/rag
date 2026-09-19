# Golden set changelog

Golden sets are immutable once a run has used them. Any change to questions, expectations,
evidence or references becomes a new version (`vN+1.json`) with an entry here. Runs record the
version and a content hash in `run.json`, so each run is always scored and displayed against
the golden set it was evaluated with.

To re-score an existing run's answers on a newer version without regenerating them:

    uv run python -m eval.run_eval --name <new-run> --golden vN --reuse-answers eval/results/<run>

## v0 — initial set (AI-drafted, used by run 01)

- 10 supplied questions (verbatim) and 10 self-generated questions.
- Fields: `source`, `type`, `question`, `expected_behavior`, `expected_status`, `reference`,
  `missing_points` (partial cases), `required_evidence` as `{source, quote}` groups, `notes`.
- `expected_behavior` was added after run 01; it is display-only and does not affect scoring.
