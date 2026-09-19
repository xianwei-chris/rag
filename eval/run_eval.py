"""Run the golden set through the RAG pipeline and score it.

    uv run python -m eval.run_eval                         # full run
    uv run python -m eval.run_eval --ids S02,S08,C10       # subset
    uv run python -m eval.run_eval --skip-ragas            # rule-based checks only (no judge calls)
    uv run python -m eval.run_eval --reuse-answers eval/results/<run>/answers.jsonl

Scores
  Rule-based (deterministic):
    status_correct     predicted support status == expected
    evidence_recall    share of required evidence groups present in the retrieved chunks
    abstained_exactly  answer is exactly the abstention string (expected "not supported" only)
    rule_pass          status correct, all required evidence retrieved, exact abstention where expected
  RAGAS (LLM judge; skipped for expected "not supported" questions, which have no claims to score):
    faithfulness, context_precision, context_recall, factual_correctness (F1)

Outputs go to eval/results/<timestamp>/: answers.jsonl, results.csv, summary.json.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd

from eval.evidence import evidence_recall
from rag.config import ABSTAIN_ANSWER, get_settings
from rag.pipeline import RagPipeline
from rag.store import RetrievedChunk

EVAL_DIR = Path(__file__).parent
GOLDEN_PATH = EVAL_DIR / "golden_set.json"
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


def build_table(golden: list[dict], answers: dict[str, dict], ragas: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for item in golden:
        answer = answers[item["id"]]
        rows.append(
            {
                "id": item["id"],
                "source": item["source"],
                "type": item["type"],
                "question": item["question"],
                "expected_status": item["expected_status"],
                "predicted_status": answer["support_status"],
                "answer": answer["answer"],
                "missing_information": answer["missing_information"],
                "missing_points_expected": "; ".join(item.get("missing_points", [])) or None,
                "citations": ", ".join(answer["citations"]),
                "retrieved": ", ".join(f"{c['chunk_id']} ({c['section']})" for c in answer["retrieved"]),
                **rule_scores(item, answer),
                **ragas.get(item["id"], dict.fromkeys(RAGAS_COLUMNS.values())),
                "latency_s": answer["latency_s"],
                "warnings": " | ".join(answer["warnings"]) or None,
            }
        )
    return pd.DataFrame(rows)


def summarize(table: pd.DataFrame) -> dict:
    metrics = ["status_correct", "evidence_recall", "rule_pass", *RAGAS_COLUMNS.values()]

    def means(frame: pd.DataFrame) -> dict:
        return {m: _clean(pd.to_numeric(frame[m], errors="coerce").mean()) for m in metrics} | {"n": len(frame)}

    return {
        "overall": means(table),
        "by_source": {k: means(g) for k, g in table.groupby("source")},
        "by_type": {k: means(g) for k, g in table.groupby("type")},
        "by_expected_status": {k: means(g) for k, g in table.groupby("expected_status")},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline on the golden set.")
    parser.add_argument("--ids", help="Comma-separated question IDs to run, e.g. S01,C05.")
    parser.add_argument("--skip-ragas", action="store_true", help="Only compute rule-based scores.")
    parser.add_argument("--reuse-answers", type=Path, help="Score an existing answers.jsonl instead of regenerating.")
    args = parser.parse_args()

    warnings.filterwarnings("ignore")
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")

    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if args.ids:
        wanted = set(args.ids.split(","))
        golden = [item for item in golden if item["id"] in wanted]

    run_dir = RESULTS_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.reuse_answers:
        records = [json.loads(line) for line in args.reuse_answers.read_text(encoding="utf-8").splitlines()]
    else:
        settings = get_settings()
        print(f"Generating answers with {settings.llm_model} (top_k={settings.top_k})...")
        records = generate_answers(golden)
    answers = {r["id"]: r for r in records}
    golden = [item for item in golden if item["id"] in answers]
    (run_dir / "answers.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )

    ragas = {}
    if not args.skip_ragas:
        print(f"Scoring with RAGAS (judge={JUDGE_MODEL})...")
        ragas = ragas_scores(golden, answers)

    table = build_table(golden, answers, ragas)
    table.to_csv(run_dir / "results.csv", index=False)
    summary = summarize(table)
    settings = get_settings()
    summary["config"] = {
        "llm_model": settings.llm_model,
        "embed_model": settings.embed_model,
        "judge_model": None if args.skip_ragas else JUDGE_MODEL,
        "top_k": settings.top_k,
        "max_chunk_words": settings.max_chunk_words,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    view = ["id", "type", "expected_status", "predicted_status", "evidence_recall", "rule_pass", *RAGAS_COLUMNS.values()]
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print("\n", table[view].to_string(index=False))
        print("\nOverall:", json.dumps(summary["overall"]))
    print(f"\nSaved to {run_dir}")


if __name__ == "__main__":
    main()
