# Golden set changelog

Golden sets are immutable once a run has used them. Any change to questions, expectations,
evidence or references becomes a new version (`vN+1.json`) with an entry here. Runs record the
version and a content hash in `run.json`, so each run is always scored and displayed against
the golden set it was evaluated with.

To re-score an existing run's answers on a newer version without regenerating them:

    uv run python -m eval.run_eval --name <new-run> --golden vN --reuse-answers eval/results/<run>

## v0 — initial set

- 10 supplied questions (verbatim) and 10 self-generated questions.
- Fields: `source`, `type`, `question`, `expected_behavior`, `expected_status`, `reference`,
  `missing_points` (partial cases), `required_evidence` as `{source, quote}` groups, `notes`.
- `expected_behavior` is display-only (the results table's column) and does not affect scoring.
- Reference-writing rules, applied while finalising v0:
  - **scoped to what the question asks**, not everything true about the topic: a reference listing
    extra rules scores a correct, focused answer as missing coverage;
  - **one fact per sentence, each sentence self-contained**, because the judge verifies claims in
    isolation ("The cell must be suppressed." is marked missing even when the answer states it with
    context, so it reads "A management dashboard cell containing 4 patients must be suppressed …");
  - **leading with the direct answer or verdict**, stating any premise correction as a claim, so the
    reference carries the expected behaviour for supported questions.
