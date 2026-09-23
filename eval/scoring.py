"""Evaluation design: metrics and pass/fail gates.

Each question gets deterministic metrics (quote matching, no LLM) and, where they apply,
LLM-judged checks. One gate shape applies to every question -- the right call, and the right
content -- and only the content check is instantiated per expected support status:

  supported            status correct · factual correctness against the reference
  partially supported  status correct · factual correctness against the reference (which covers
                       only the supported portion) · every missing point named
  not supported        status correct (the abstention text is emitted by code, not the model)

Retrieval recall and precision, and faithfulness, are computed but do not gate: they are
diagnostics. Recall in particular explains *why* a wrong answer was wrong, but gating on it
would double-count, since an answer that needed a missing passage already fails on content.

Ops assumption behind the gates: completeness first. Omitting a required fact is the costly error
in a compliance setting; extra claims are tolerated, because an answer that says more than the
reference is not thereby wrong.

Factual correctness runs in RAGAS "recall" mode, which excludes false positives by construction, so
an answer is not marked down for stating more than the reference. Reading its source, that mode is
TP/(TP+FN) where

    TP = claims of the RESPONSE that the reference entails
    FN = claims of the REFERENCE that the response does not entail

The numerator counts response claims while the denominator adds reference claims, so the score is
not the share of the reference that was covered. An answer that covers the reference completely but
adds extra true material scores *lower*, since few of its claims are entailed by a short reference.
S09 is the extreme: its answer covers all four reference claims and adds several more, giving TP=0,
FN=0 and a reproducible 0.0. C09 confirms the formula exactly: TP=3, FN=2, score 0.60.

TP and FN come from two different claim decompositions, so both can fall to zero together and the
score becomes 0/(0+1e-8) for an answer that in fact states every reference claim. Seen on S09 and on
C02: decomposing their references by hand and checking each claim against the answer matched every
one. An exact 0.0 is therefore treated as suspect and checked against the claims before it is
believed, rather than read as a content failure.

Faithfulness is measured against all retrieved passages, so it checks grounding rather than
"supported by the cited passage". Citations themselves are validated in rag/generation.py,
which drops any citation outside the retrieved set and abstains on an uncited answer.
"""

from __future__ import annotations

import asyncio
import math

from eval.evidence import quote_in
from rag.config import ABSTAIN_ANSWER

# Thresholds for the judged gates. Judge scores vary between runs, so these are starting
# points to be calibrated against manual review, not exact requirements.
FACTUAL_CORRECTNESS_MIN = 0.9  # references are short (2-6 claims), so this means "every reference claim"
FACTUAL_CORRECTNESS_MODE = "recall"  # TP/(TP+FN): the gate metric

DETERMINISTIC = ["status_correct", "retrieval_recall", "retrieval_precision"]
JUDGED = ["faithfulness", "factual_correctness", "missing_points_named"]


# ---------------------------------------------------------------- deterministic (no LLM)


def _contains(chunk: dict, group: list[dict]) -> bool:
    return any(ev["source"] == chunk["source"] and quote_in(ev["quote"], chunk["text"]) for ev in group)


def _recall(groups: list[list[dict]], chunks: list[dict]) -> float | None:
    if not groups:
        return None
    return sum(any(_contains(c, g) for c in chunks) for g in groups) / len(groups)


def _precision(groups: list[list[dict]], chunks: list[dict]) -> float | None:
    """Share of chunks containing any required quote. A lower bound: the golden set labels
    required evidence only, so relevant-but-unlabelled passages count as misses."""
    if not groups or not chunks:
        return None
    return sum(any(_contains(c, g) for g in groups) for c in chunks) / len(chunks)


def deterministic_scores(item: dict, answer: dict) -> dict:
    groups = item["required_evidence"]
    retrieved = answer["retrieved"]
    return {
        "status_correct": answer["support_status"] == item["expected_status"],
        "abstained_exactly": answer["answer"].strip() == ABSTAIN_ANSWER,
        "retrieval_recall": _recall(groups, retrieved),
        "retrieval_precision": _precision(groups, retrieved),
    }


# ---------------------------------------------------------------- LLM-judged


def make_judge(model: str):
    import instructor
    import litellm
    from ragas.llms import llm_factory

    client = instructor.from_litellm(litellm.acompletion, mode=instructor.Mode.JSON)
    return llm_factory(model, provider="litellm", client=client, adapter="litellm", temperature=0)


def judged_scores(golden: list[dict], answers: dict[str, dict], judge) -> dict[str, dict]:
    """faithfulness: share of answer claims supported by the retrieved passages
         (answers that make claims, i.e. expected supported/partial).
    factual_correctness: RAGAS FactualCorrectness against the reference, `recall` mode (expected
         supported and partial). Gate metric.
    missing_points_named: share of `missing_points` the answer or its missing_information
         states as unsupported (expected partial only)."""
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.metrics import FactualCorrectness, Faithfulness

    scores = {item["id"]: dict.fromkeys(JUDGED) for item in golden}
    run_config = RunConfig(max_workers=4, timeout=300)

    def run(metric, name: str, rows: list[tuple[str, dict]]) -> None:
        """Score `rows`, then retry once for any that came back empty.

        RAGAS already retries each call (RunConfig.max_retries), and `raise_exceptions=False` turns
        whatever survives that into a silent NaN. A fresh `evaluate` recovers cases where the whole
        batch was affected (a rate limit clearing, say), and anything still missing is reported
        rather than left to look like a low score.
        """
        if not rows:
            return

        def score(batch: list[tuple[str, dict]]) -> None:
            frame = evaluate(
                EvaluationDataset.from_list([row for _, row in batch]),
                metrics=[metric],
                llm=judge,
                run_config=run_config,
                raise_exceptions=False,
                show_progress=False,
            ).to_pandas()
            column = frame.columns[-1]
            for i, (qid, _) in enumerate(batch):
                scores[qid][name] = _clean(frame.iloc[i][column])

        score(rows)
        retry = [row for row in rows if scores[row[0]][name] is None]
        if retry:
            print(f"  {name}: no score for {[qid for qid, _ in retry]}; retrying once.")
            score(retry)
        still_missing = [qid for qid, _ in rows if scores[qid][name] is None]
        if still_missing:
            print(f"  WARNING: {name} could not be scored for {still_missing} (judge error, not a low score).")

    claim_rows = [
        (item["id"], {"user_input": item["question"], "response": answers[item["id"]]["answer"],
                      "retrieved_contexts": [c["text"] for c in answers[item["id"]]["retrieved"]]})
        for item in golden
        if item["expected_status"] != "not supported"
    ]
    run(Faithfulness(), "faithfulness", claim_rows)

    # Partial questions are scored too: their reference covers only the supported portion, so recall
    # against it asks "did the answer state everything the documents do say?" without penalising the
    # answer for leaving out what the documents never covered.
    reference_rows = [
        (item["id"], {"user_input": item["question"], "response": answers[item["id"]]["answer"],
                      "reference": item["reference"]})
        for item in golden
        if item["expected_status"] in ("supported", "partially supported")
    ]
    run(FactualCorrectness(mode=FACTUAL_CORRECTNESS_MODE), "factual_correctness", reference_rows)

    checker = FactualCorrectness(llm=judge)  # used only for its claim/NLI primitives

    async def points_named(item: dict) -> float:
        """Share of missing_points the answer states as unsupported."""
        answer = answers[item["id"]]
        premise = f"{answer['answer']}\n\nNot covered by the documents: {answer['missing_information'] or ''}"
        hypotheses = [f"The documents do not specify the {point}." for point in item["missing_points"]]
        verdicts = await checker.verify_claims(premise=premise, hypothesis_list=hypotheses, callbacks=None)
        return round(float(sum(verdicts)) / len(hypotheses), 3) if len(verdicts) else 0.0

    partial = [item for item in golden if item["expected_status"] == "partially supported"]
    if partial:

        async def run_partial() -> list[float]:
            return await asyncio.gather(*(points_named(item) for item in partial))

        for item, value in zip(partial, asyncio.run(run_partial())):
            scores[item["id"]]["missing_points_named"] = value

    return scores


def _clean(value) -> float | None:
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else round(float(value), 3)


# ---------------------------------------------------------------- gates


def gate(item: dict, scores: dict) -> tuple[bool, list[str]]:
    """Pass/fail for one question and the reasons it failed (empty if it passed)."""
    reasons = []
    if not scores["status_correct"]:
        reasons.append("wrong support status")
    if item["expected_status"] == "not supported":
        # Nothing further to check: rag/generation.py emits ABSTAIN_ANSWER for this status, so the
        # text is guaranteed by code rather than by the model. `abstained_exactly` is recorded as a
        # regression check on that guarantee, but it cannot fail independently of the status.
        return not reasons, reasons

    fc = scores["factual_correctness"]
    if fc is None:
        # Distinguish a judge failure from a low score: a missing metric is an evaluation problem,
        # not evidence about the answer, and should not be read as a content failure.
        reasons.append("factual correctness not scored (judge error)")
    elif fc < FACTUAL_CORRECTNESS_MIN:
        reasons.append("answer does not match the reference")
    if item["expected_status"] == "partially supported":
        named = scores["missing_points_named"]
        if named is None or named < 1.0:
            reasons.append("missing points not all named")
    return not reasons, reasons
