"""Evaluation design: metrics and pass/fail gates.

Each question gets deterministic metrics (quote matching, no LLM) and, where they apply,
LLM-judged checks. `pass` is decided by gates that depend on the expected support status,
mirroring the brief's pass conditions:

  supported            status correct · all required evidence retrieved ·
                       answer faithful to the retrieved passages · reference claims covered
  partially supported  status correct · all required evidence retrieved ·
                       answer faithful to the retrieved passages · every missing point named
  not supported        status correct · exact abstention string

Ops assumption behind the gates: completeness first. Omitting a required fact fails; extra
claims are tolerated only if the retrieved passages support them. So coverage is measured in
one direction only - the share of the reference's claims that the answer states - and extra
claims are policed by faithfulness instead.

RAGAS FactualCorrectness is deliberately not used: all three of its modes mix directions
(`recall` divides answer claims entailed by the reference by that count plus missing reference
claims), so a single stray verdict can zero a complete answer. `reference_coverage` below uses
the same claim decomposition and NLI primitives in one direction, which is the quantity the
completeness-first assumption cares about.

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
FAITHFULNESS_MIN = 0.8
REFERENCE_COVERAGE_MIN = 0.8

DETERMINISTIC = ["status_correct", "retrieval_recall", "retrieval_precision"]
JUDGED = ["faithfulness", "reference_coverage", "missing_points_named"]


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
    reference_coverage: share of the reference's claims that the answer states
         (expected supported only).
    missing_points_named: share of `missing_points` the answer or its missing_information
         states as unsupported (expected partial only)."""
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.metrics import FactualCorrectness, Faithfulness

    scores = {item["id"]: dict.fromkeys(JUDGED) for item in golden}
    run_config = RunConfig(max_workers=4, timeout=300)

    def run(metric, name: str, rows: list[tuple[str, dict]]) -> None:
        if not rows:
            return
        frame = evaluate(
            EvaluationDataset.from_list([row for _, row in rows]),
            metrics=[metric],
            llm=judge,
            run_config=run_config,
            raise_exceptions=False,
            show_progress=False,
        ).to_pandas()
        column = frame.columns[-1]
        for i, (qid, _) in enumerate(rows):
            scores[qid][name] = _clean(frame.iloc[i][column])

    claim_rows = [
        (item["id"], {"user_input": item["question"], "response": answers[item["id"]]["answer"],
                      "retrieved_contexts": [c["text"] for c in answers[item["id"]]["retrieved"]]})
        for item in golden
        if item["expected_status"] != "not supported"
    ]
    run(Faithfulness(), "faithfulness", claim_rows)

    checker = FactualCorrectness(llm=judge)  # used only for its claim decomposition and NLI

    async def coverage(item: dict) -> float:
        """Share of the reference's claims entailed by the answer."""
        claims = await checker.decompose_claims(item["reference"], callbacks=None)
        if not claims:
            return 0.0
        verdicts = await checker.verify_claims(
            premise=answers[item["id"]]["answer"], hypothesis_list=claims, callbacks=None
        )
        return round(float(sum(verdicts)) / len(claims), 3) if len(verdicts) else 0.0

    async def points_named(item: dict) -> float:
        """Share of missing_points the answer states as unsupported."""
        answer = answers[item["id"]]
        premise = f"{answer['answer']}\n\nNot covered by the documents: {answer['missing_information'] or ''}"
        hypotheses = [f"The documents do not specify the {point}." for point in item["missing_points"]]
        verdicts = await checker.verify_claims(premise=premise, hypothesis_list=hypotheses, callbacks=None)
        return round(float(sum(verdicts)) / len(hypotheses), 3) if len(verdicts) else 0.0

    supported = [item for item in golden if item["expected_status"] == "supported"]
    partial = [item for item in golden if item["expected_status"] == "partially supported"]

    async def run_checks() -> tuple[list[float], list[float]]:
        return (
            await asyncio.gather(*(coverage(item) for item in supported)),
            await asyncio.gather(*(points_named(item) for item in partial)),
        )

    coverages, named = asyncio.run(run_checks())
    for item, value in zip(supported, coverages):
        scores[item["id"]]["reference_coverage"] = value
    for item, value in zip(partial, named):
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
        if not scores["abstained_exactly"]:
            reasons.append("not the exact abstention string")
        return not reasons, reasons

    if scores["retrieval_recall"] is not None and scores["retrieval_recall"] < 1.0:
        reasons.append("required evidence not retrieved")
    faithfulness = scores["faithfulness"]
    if faithfulness is None or faithfulness < FAITHFULNESS_MIN:
        reasons.append("claims not grounded in retrieved passages")
    if item["expected_status"] == "supported":
        covered = scores["reference_coverage"]
        if covered is None or covered < REFERENCE_COVERAGE_MIN:
            reasons.append("reference claims not covered")
    else:
        named = scores["missing_points_named"]
        if named is None or named < 1.0:
            reasons.append("missing points not all named")
    return not reasons, reasons
