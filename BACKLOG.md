# Backlog — system changes to try

Ideas raised while reviewing run 01, with whatever evidence exists for each. Golden-set changes
live separately in `eval/golden/CHANGELOG.md`.

Priority, from the review of run 01. Reference fixes come first because until the golden set is
right, every other change is measured against a moving target:

1. golden-set reference and evidence fixes -> `eval/golden/CHANGELOG.md` (v1)
2. retrieval: sub-queries retrieved in parallel and fused (item 1 below) — C04, S02
3. answer style: citation markers and preamble leaking into user-facing text (item 6)
4. metric limitations to document rather than fix (item 7)

Rejected: raising `top_k` (item 3), and lowering it (item 8).

## Done (runs 02-05)

| Change | Where | Result |
|---|---|---|
| Golden v1: reference + evidence fixes | `eval/golden/v1.json` | 13/20 -> 16/20; recall 0.971 -> 0.941 (honest) |
| `reference_coverage` replaces RAGAS FC as the gate | `eval/scoring.py` | 16/20 -> 17/20; S09 artefact resolved |
| Sub-query retrieval, original top-3 reserved | `rag/query.py` | C04 recall 0.5 -> 1.0 and now passes; no regressions |
| Strip citation markers for display; no-preamble rule | `rag/generation.py` | preamble answers 2 -> 0 |
| Retries on LLM/embedding calls | `rag/llm.py` | a single 503 no longer destroys a whole run |
| `check_golden` structural + paraphrase-drift guards | `eval/check_golden.py` | would have caught S01 and C09 |

## Still open

- **S02** — the only remaining true system failure. Expansion did not fix it: the fused result
  returned the same five chunks, because the window is oversubscribed. See item 2.
- **C09** — the reference's "unless" clause decomposes into an unconditional claim the answer does
  not make. Same defect class as C02/C03, but fixing it means a v2, and the overfitting risk is
  real: it is now the only failure whose fix is purely a reference edit.
- **Modal drift (S08)** — no metric detects it reliably; the faithfulness 0.0 first read as detection
  turned out to be judge noise (notebook 7.3). Needs a deterministic modal-verb check or a reviewed
  verdict.
- **Judge variance** — the same stored answer scored faithfulness 0.0, 0.833 and 1.00 across runs
  01/02/03. At n=20 this flips one or two verdicts per run, so judged pass rates cannot resolve a
  one-question improvement. Either enlarge the golden set, average several judge passes, or lean on
  the deterministic metrics for iteration decisions.

## 1. Query generation before embedding (measured, partial win)

**Problem.** Two failures are two-part questions where the second part is drowned out of the query
embedding, so the chunk answering it falls outside the `top_k = 5` window:

| Question | Chunk needed | Rank, full question | Rank, sub-query |
|---|---|---|---|
| C04 "...and what determines that?" | `kc-25` (notifiability criteria) | 8 | **1** |
| S02 "...because the guide says k=3..." | `anon-21` (what the guide says about k) | 11 | **2** |

Both chunks were always retrievable. The query was the problem, not the index, the chunking or `k`.

**Change.** One LLM call rewrites the question into 1-3 keyword-rich sub-queries; retrieve for the
original *and* each sub-query, then fuse. `k` stays at 5.

**Result (S02, C04, with S01 and S03 as controls).** Fusion strategy matters more than the idea:

- naive reciprocal-rank fusion over original + 3 sub-queries **breaks S02**: it pulls in `anon-21`
  but drops `policy-05` *and* `policy-10`, the two chunks holding S02's required evidence, taking
  recall 1.0 -> 0.0. The sub-queries were all anonymisation-flavoured and out-voted the original.
- **reserving the original query's top 3 and filling the last 2 from the fused sub-queries** fixes
  C04 (recall 0.5 -> 1.0, both groups in window) and leaves S01/S03 unchanged. This is the variant
  to implement: it is strictly additive, since the original's best hits can never be displaced.

**Still open: S02 is not fixed by this at k=5.** It needs three distinct facts (the suppression
rule, the k-anonymity passage, the precedence between them) and the window holds five chunks, two
of which go to `anon-11`/`anon-12` — near-duplicates both about internal sharing. See item 2.

**Tested and rejected: rewriting into a single better query.** One LLM call producing one improved
query, embedded in place of the original, fixes neither case: `anon-21` stays outside S02's window
and `kc-25` stays outside C04's (which also loses `hc-27`). One query is one embedding vector, and a
two-part question needs passages from two regions of the space, so a rewrite only relocates the same
point. S02's rewrite is the instructive near-miss: it retrieves `anon-22`, which *defines*
k-anonymity, but not `anon-21`, which says the guide refers to k values of 3 and 5. The multiple
retrievals are the mechanism, not an implementation detail.

**Risks.** Decomposition is itself a failure surface: a bad split can lose the original intent,
which is exactly what the naive variant did. Always retrieve for the original question too. Cost is
one extra LLM call and one extra embedding per question; gate it on a cheap heuristic (more than one
clause) so single-clause questions skip it.

**Note on measuring it.** S02's `retrieval_recall` already reads 1.0 on v0 because `anon-21` is not
labelled required evidence, so on v0 the only visible win is C04. Sequence the v1 evidence fixes
(`eval/golden/CHANGELOG.md`) *before* this iteration, or the numbers will understate it.

## 2. Free the wasted slots (untested)

`retrieval_precision` is 0.31, and the window repeatedly spends slots on near-duplicates: S02 gets
both `anon-11` and `anon-12`, which say much the same thing about internal sharing. Diversity-aware
selection (MMR) or de-duplication by section would free a slot without raising `k` — the missing
piece for S02.

## 3. Rejected: raise `top_k` 5 -> 8

Would fix C04 (`kc-25` is at rank 8) but not S02 (`anon-21` at rank 11), and it dilutes an already
low precision while adding input tokens to every call. Fixing the query beats widening the window.

## 4. Not yet measured

- Whether better retrieval actually produces a better *answer*: today's checks measure retrieval
  only. S02's answer also has a reasoning gap (it never states that a more specific internal policy
  overrides general guidance), which more context may or may not fix.
- Reranking (retrieve ~20, cross-encode to 5): best precision, but adds a model dependency and
  latency. More a production note than a quick iteration.

## 5. Sub-answer synthesis (heavier variant of item 1)

Decompose, retrieve *and answer* each sub-question, then synthesise one answer. Buys accuracy on
genuinely multi-part questions, and the synthesis step is where a precedence judgement (S02's
"internal policy overrides general guidance") would naturally live.

Costs: n times the calls and latency, and real contract complexity — rules for combining
`support_status` across sub-answers (one supported + one not = partially supported), merging
citations, and resolving sub-answers that contradict each other. A bad decomposition now corrupts
the answer, not just the retrieval.

Prefer item 1 first: it fixes C04 for one extra call and leaves the output contract untouched.

**Why this belongs up front, not as a reflection loop.** Self-RAG/CRAG-style "answer, notice the
gap, re-retrieve" cannot catch these two: C04 and S02 both returned `support_status: supported`
with `missing_information: None`. Neither noticed anything was missing — from the inside, absent
context is indistinguishable from context that does not exist. Reflection helps where the model
already hedges (non-empty `missing_information` makes a good re-retrieval query, bounded to one
extra loop); it cannot help where the model is confidently incomplete. Question structure, by
contrast, is inspectable before any retrieval happens.

## 6. Answer style (user-facing text)

Two independent defects in what a user actually reads:

- **Citation markers leak into the answer string**: "identity mapping tables must be encrypted
  [anon-28]". `anon-28` is an internal chunk id and means nothing to a reader. The ids are already
  carried structurally in `citations`, and the CLI resolves them to file and section via
  `RagResult.cited_sources()`. Strip the markers from the user-facing string and render sources
  separately. Contract change, not a prompt change — keep the ids in the JSON, since evaluation and
  guardrails depend on them.
- **Preamble**: "Based on the provided documents, the differences and limitations are as follows:".
  Prompt fix.

## 7. Metric limitations to document (not defects to fix)

- **Faithfulness structurally penalises premise-rejection.** Correctly rejecting a false premise
  requires asserting an absence ("the policy does not state that ..."), which cannot be verified
  from the retrieved passages, so it scores unsupported. S02 0.5 and C09 0.667 are both this. It
  makes faithfulness systematically unfair to the `misleading` questions, which is a further reason
  it does not gate.
- **RAGAS factual correctness can return 0.0 for a complete answer** (S09, and S03 under a weaker
  judge): TP and FN come from two separate claim decompositions, so an inconsistent judge yields
  TP=0 with FN=0. Treat an exact 0.0 as suspect.
- **`retrieval_precision` is close to uninterpretable here.** 17 of 20 questions label only 1-2
  evidence groups against k=5, so the metric is dominated by how much evidence the golden set
  happens to label: mean structural value 0.22 against observed 0.306. S01 scores 0.2 while being a
  perfect result. Diagnostic only, at any threshold.
- **`abstained_exactly` is tautological.** `rag/generation.py` emits `ABSTAIN_ANSWER` for the
  `not supported` status, so the check cannot fail independently of `status_correct`. Kept as a
  regression check on that guarantee, not as evidence about the model.
- **Run 01 mixes two judge passes** — 17 questions judged originally, S08/S09/C05 when factual
  correctness was extended to partials. Judge variance is real (faithfulness moved 0.787 -> 0.746
  from re-judging three questions), so the 20 numbers are not one homogeneous measurement.

## 8. Rejected: lower `top_k` 5 -> 3

Tested against v0's labelled evidence: k=3 loses C03's evidence (rank 4); k=4 loses nothing. But
the motivating premise — that fewer chunks would reduce hallucination — is not supported by this
run. No failure was caused by surplus context: the faithfulness dips are decomposition and
absence-claim artefacts (item 7), and S02's weak inference came from a chunk being *missing*.
Shrinking the window would make that failure mode worse. The margin is also thinner than it looks,
since it is measured against evidence known to be under-labelled (S01, S02).

## 9. Answer defects the gates cannot see

- **S08 modal drift.** The documents say encryption "should" be applied (a recommended control);
  the answer says "must", in three claims. It passes every automated check — status correct,
  factual correctness 1.0, every missing point named — and is still wrong. The clearest argument
  for why section 6 records human verdicts rather than raw gate output. Candidate prompt rule:
  preserve the modal strength of the source.
