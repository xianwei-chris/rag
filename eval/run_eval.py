"""Run the golden set through the RAG pipeline and score it.

    uv run python -m eval.run_eval --name 03-modal-prompt            # full run, latest golden set
    uv run python -m eval.run_eval --name tmp --ids S02,S08,C10      # subset
    uv run python -m eval.run_eval --name tmp --skip-ragas           # rule-based checks only (no judge calls)
    uv run python -m eval.run_eval --name <new-run> --golden v1 \
        --reuse-answers eval/results/<old-run>                   # re-score old answers on a new golden set

Scores
  Rule-based (deterministic):
    status_correct     predicted support status == expected
    evidence_recall    share of required evidence groups present in the retrieved chunks
    abstained_exactly  answer is exactly the abstention string (expected "not supported" only)
    rule_pass          status correct, all required evidence retrieved, exact abstention where expected
  RAGAS (LLM judge; skipped for expected "not supported" questions, which have no claims to score):
    faithfulness, context_precision, context_recall, factual_correctness (F1)

Outputs go to eval/results/<name>/:
    answers.jsonl  one record per question: answer, status, citations, retrieved passages,
                   raw model output, latency, and its "scores" (rule-based + RAGAS)
    run.json       provenance: golden version + hash, git commit, models, top_k, prompt hash
Tables and averages are computed from these by eval/report.py, never stored.
Runs are never overwritten: an existing --name is refused.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import time
import warnings
from pathlib import Path

from eval.evidence import evidence_recall
from eval.report import RAGAS_SCORES, overall
from eval.versioning import git_state, golden_hash, latest_golden_version, load_golden, sha256_short
from rag.config import ABSTAIN_ANSWER, get_settings
from rag.generation import SYSTEM_PROMPT
from rag.pipeline import RagPipeline
from rag.store import RetrievedChunk

EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
JUDGE_MODEL = os.getenv("RAG_JUDGE_MODEL", "gemini/gemini-3.5-flash")

RAGAS_COLUMNS = {
    "faithfulness": "faithfulness",
    "llm_context_precision_with_reference": "context_precision",
    "context_recall": "context_recall",
    "factual_correctness(mode=f1)": "factual_correctness",
}


def generate_answers(golden: list[dict]) -> list[dict]:
    pipeline = RagPipeline()
    records = []
    for item in golden:
        start = time.perf_counter()
        result = pipeline.ask(item["question"])
        records.append(
            {
                "id": item["id"],
                "latency_s": round(time.perf_counter() - start, 2),
                **result.to_dict(),
            }
        )
        print(f"  {item['id']}: {result.support_status}")
    return records


def rule_scores(item: dict, answer: dict) -> dict:
    retrieved = [RetrievedChunk(**c) for c in answer["retrieved"]]
    hit, total = evidence_recall(item["required_evidence"], retrieved)
    expected_abstain = item["expected_status"] == "not supported"
    status_correct = answer["support_status"] == item["expected_status"]
    abstained_exactly = answer["answer"].strip() == ABSTAIN_ANSWER
    return {
        "status_correct": status_correct,
        "evidence_recall": hit / total if total else None,
        "abstained_exactly": abstained_exactly if expected_abstain else None,
        "rule_pass": status_correct
        and hit == total
        and (abstained_exactly if expected_abstain else not abstained_exactly),
    }


def ragas_scores(golden: list[dict], answers: dict[str, dict]) -> dict[str, dict]:
    import instructor
    import litellm
    from ragas import EvaluationDataset, RunConfig, evaluate
    from ragas.llms import llm_factory
    from ragas.metrics import (
        FactualCorrectness,
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
    )

    scored = [item for item in golden if item["expected_status"] != "not supported"]
    if not scored:
        return {}
    dataset = EvaluationDataset.from_list(
        [
            {
                "user_input": item["question"],
                "retrieved_contexts": [c["text"] for c in answers[item["id"]]["retrieved"]],
                "response": answers[item["id"]]["answer"],
                "reference": item["reference"],
            }
            for item in scored
        ]
    )
    client = instructor.from_litellm(litellm.acompletion, mode=instructor.Mode.JSON)
    judge = llm_factory(JUDGE_MODEL, provider="litellm", client=client, adapter="litellm", temperature=0)
    result = evaluate(
        dataset,
        metrics=[
            Faithfulness(),
            LLMContextPrecisionWithReference(),
            LLMContextRecall(),
            FactualCorrectness(mode="f1"),
        ],
        llm=judge,
        run_config=RunConfig(max_workers=4, timeout=300),
        raise_exceptions=False,
    )
    frame = result.to_pandas().rename(columns=RAGAS_COLUMNS)
    return {
        item["id"]: {name: _clean(frame.iloc[i][name]) for name in RAGAS_COLUMNS.values()}
        for i, item in enumerate(scored)
    }


def _clean(value) -> float | None:
    return None if value is None or (isinstance(value, float) and math.isnan(value)) else round(float(value), 3)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline on a golden set.")
    parser.add_argument("--name", required=True, help="Run folder name, e.g. 03-modal-prompt.")
    parser.add_argument("--golden", default=None, help="Golden set version (default: latest in eval/golden/).")
    parser.add_argument("--ids", help="Comma-separated question IDs to run, e.g. S01,C05.")
    parser.add_argument("--skip-ragas", action="store_true", help="Only compute rule-based scores.")
    parser.add_argument("--reuse-answers", type=Path, help="Existing run folder to re-score instead of regenerating.")
    args = parser.parse_args()

    warnings.filterwarnings("ignore")
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")

    run_dir = RESULTS_DIR / args.name
    if run_dir.exists():
        raise SystemExit(f"{run_dir} already exists; runs are immutable, choose a new --name.")

    golden_version = args.golden or latest_golden_version()
    golden = load_golden(golden_version)
    if args.ids:
        wanted = set(args.ids.split(","))
        golden = [item for item in golden if item["id"] in wanted]

    settings = get_settings()
    source = args.reuse_answers
    if source:
        records = [json.loads(line) for line in (source / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
        generation = json.loads((source / "run.json").read_text(encoding="utf-8"))["generation"]
        generation = generation | {"answers_from": source.name}
    else:
        print(f"Generating answers with {settings.llm_model} (top_k={settings.top_k})...")
        records = generate_answers(golden)
        generation = {
            "llm_model": settings.llm_model,
            "embed_model": settings.embed_model,
            "top_k": settings.top_k,
            "max_chunk_words": settings.max_chunk_words,
            "prompt_hash": sha256_short(SYSTEM_PROMPT),
            **git_state(),
        }
    answers = {r["id"]: r for r in records}
    golden = [item for item in golden if item["id"] in answers]

    ragas = {}
    if not args.skip_ragas:
        print(f"Scoring with RAGAS (judge={JUDGE_MODEL})...")
        ragas = ragas_scores(golden, answers)

    records = []
    for item in golden:
        record = {k: v for k, v in answers[item["id"]].items() if k != "scores"}
        record["scores"] = rule_scores(item, record) | ragas.get(item["id"], dict.fromkeys(RAGAS_COLUMNS.values()))
        records.append(record)
    run_info = {
        "golden_version": golden_version,
        "golden_hash": golden_hash(golden_version),
        "question_ids": [item["id"] for item in golden],
        "judge_model": None if args.skip_ragas else JUDGE_MODEL,
        "generation": generation,
    }

    run_dir.mkdir(parents=True)
    (run_dir / "answers.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")

    for r in records:
        sc = r["scores"]
        judged = " ".join(f"{m}={sc[m]}" for m in RAGAS_SCORES if sc[m] is not None)
        print(f"  {r['id']}: {r['support_status']:<20} rule_pass={sc['rule_pass']} {judged}")
    means = overall([rec["scores"] for rec in records])
    print("\nOverall:", json.dumps(means))
    print(f"\nSaved to {run_dir} (golden {golden_version})")


if __name__ == "__main__":
    main()
