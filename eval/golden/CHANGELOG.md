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
  - (added after reviewing run 01) **quote the documents' wording where the reference states
    something they state**, rather than paraphrasing it. Factual correctness runs in recall mode, so
    a paraphrase that drops a qualifier cannot be rescued by an answer that is *more* precise: the
    extra precision earns no credit and the lost qualifier scores as a miss. See C09.

## v1 - applied after reviewing run 01

Each change is justified against the source documents, not against any answer. Scored as runs
`02-golden-v1` (13/20 -> 16/20) and `archive-coverage-metric` (17/20).

- **C09** reference: restore "clinical" - `policy-07` reads "a formal clinical governance process".
- **C05** reference: scoped to the question; dropped the notification-contents sentence.
- **C03** reference: dropped the final compound, which decomposed into two claims each stronger than
  `hc-25`, a rule requiring both conditions together.
- **C02** reference: "may be waived only where A, B and C" replaced by the conditions stated
  separately, because the quantifier form decomposed into one unmatchable claim.
- **S02** evidence: added `anon-21` ("The guide refers to k values of 3, 5, or more."); reference
  rewritten to concede what the guide says, then defeat the premise on precedence. `retrieval_recall`
  correctly drops to 0.5, exposing a miss v0 had hidden.
- **S01** type: `multi-passage` -> `answerable`. `anon-03` alone contains every reference claim, so
  the second evidence group originally planned would have been invented.
- **S10, C06, C07** references now track `ABSTAIN_ANSWER`.

New rule, from C09: **quote the documents' wording where the reference states something they state**.
Guards in `eval/check_golden.py` enforce the structural part.

## Backlog beyond v1

Found while reviewing run 01 against v0. Not applied: v0 is frozen because run 01 is scored
against it, and its hash is recorded in `run.json`. These are batched into v1 as one iteration.

Evidence labelling — the recurring theme. Evidence was labelled only for the path the `reference`
takes, so a retrieval miss on any other path is invisible and `retrieval_recall` reads 1.0:

- **S01** — the question has two parts ("what is the difference" and "why is removing names
  insufficient") but only the first is labelled. Add a second group for the re-identification-risk
  fact. Also resolves a contradiction: S01 is typed `multi-passage` yet has one evidence group,
  the only such case in the set.
- **S02** — the question's premise is about k-anonymity = 3, but the chunk stating what the guide
  says about k values (`anon-21`) is neither labelled nor retrieved. The answer inferred the guide
  is silent on k=3 from five chunks that never mention k-anonymity. Add it as a required group so
  the retrieval gap is measured instead of hidden.

Reference wording:

- **C05** — the reference's last sentence lists what a breach notification should contain
  (circumstances, data affected, steps taken). The question asks only what to do on suspicion and
  within how many days, so the answer is penalised for omitting a claim answering the question does
  not need. Same defect as the S02/S03/C08 rewrites already applied in v0; C05 was missed. Scope the
  reference to the question.
- **C09** — the reference says "unless separately approved under a formal governance process", but
  `policy-07` reads "a formal **clinical** governance process". The answer quotes the source
  correctly and is marked down against a reference that paraphrased a word away. Restore "clinical".
- **C02** — the reference reads "may be waived **only** where ...". The answer covers every
  condition but not the exclusivity, scoring 0.8. Reword so each claim is a fact the answer can
  state, not a quantifier it must mirror.
- **S10, C06, C07** — `reference` still holds the pre-change abstention text. Unused (factual
  correctness is not scored for `not supported`), so cosmetic, but inconsistent with
  `ABSTAIN_ANSWER`.

Not a golden-set change:

- **S09** — factual correctness 0.0 with all three reference claims present verbatim: the RAGAS
  TP/FN double-decomposition artefact (same family as S03). Re-judging may clear it; the reference
  needs no change. Record it as a reviewed override plus a documented metric limitation.
- **C03** — cause not yet established. The answer is arguably more complete than the reference
  (all four withdrawal duties, no-immediate-deletion, plus the retention caveat), so 0.8 may be
  claim-granularity rather than a reference defect. Diagnose which claim went unmatched before
  changing anything: a reference must only be edited where it is wrong, out of scope, or malformed,
  never merely because an answer phrased things differently. Tuning references until a run passes
  overfits the golden set to one model.
- `eval/check_golden.py` — add deterministic guards: `multi-passage` implies at least two evidence
  groups (would have caught S01 for free), and flag reference sentences that *nearly* but not
  exactly match a source sentence, which is the C09 paraphrase-drift signature.
