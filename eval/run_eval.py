"""Run a golden set through the RAG pipeline and score it (metrics and gates: eval/scoring.py).

    uv run python -m eval.run_eval --name 02-my-change                # full run, latest golden set
    uv run python -m eval.run_eval --name tmp --ids S02,S08,C10       # subset
    uv run python -m eval.run_eval --name tmp --skip-judge            # deterministic metrics only
    uv run python -m eval.run_eval --name 01-fc90 --regate \
        --reuse-answers eval/results/01-baseline-k5                    # re-apply gates, no LLM calls
    uv run python -m eval.run_eval --name <new-run> --golden v1 \
        --reuse-answers eval/results/<old-run>                        # re-score old answers

Outputs go to eval/results/<name>/:
    answers.jsonl  one record per question: answer, status, citations, retrieved passages,
                   raw model output, latency, and its "scores" (metrics, pass, fail_reasons)
    run.json       provenance: golden version + hash, git commit, models, top_k, prompt hash,
                   judge model and gate thresholds
Tables and averages are computed from these by eval/report.py, never stored.
Runs are never overwritten: an existing --name is refused.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import warnings
from pathlib import Path

from eval import scoring
from eval.report import overall
from eval.versioning import git_state, golden_hash, latest_golden_version, load_golden, sha256_short
from rag.config import get_settings
from rag.generation import SYSTEM_PROMPT
from rag.pipeline import RagPipeline

EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
# A different (and much cheaper) model from the generator, so the judge is not scoring its own
# output: $0.30/$2.50 per M tokens vs $1.50/$9.00 for gemini-3.5-flash.
JUDGE_MODEL = os.getenv("RAG_JUDGE_MODEL", "gemini/gemini-2.5-flash")


def generate_answers(golden: list[dict]) -> list[dict]:
    pipeline = RagPipeline()
    records = []
    for item in golden:
        start = time.perf_counter()
        result = pipeline.ask(item["question"])
        records.append({"id": item["id"], "latency_s": round(time.perf_counter() - start, 2), **result.to_dict()})
        print(f"  {item['id']}: {result.support_status}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline on a golden set.")
    parser.add_argument("--name", required=True, help="Run folder name, e.g. 02-my-change.")
    parser.add_argument("--golden", default=None, help="Golden set version (default: latest in eval/golden/).")
    parser.add_argument("--ids", help="Comma-separated question IDs to run, e.g. S01,C05.")
    parser.add_argument("--skip-judge", action="store_true", help="Deterministic metrics only; no pass/fail.")
    parser.add_argument("--regate", action="store_true",
                        help="Reuse the source run's judged scores and only re-apply the gates (no LLM calls). "
                             "Use to compare gate thresholds; requires --reuse-answers.")
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

    if args.regate and not args.reuse_answers:
        raise SystemExit("--regate requires --reuse-answers.")

    settings = get_settings()
    source = args.reuse_answers
    if source:
        answers = [json.loads(line) for line in (source / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
        generation = json.loads((source / "run.json").read_text(encoding="utf-8"))["generation"]
        generation = generation | {"answers_from": generation.get("answers_from") or source.name}
    else:
        print(f"Generating answers with {settings.llm_model} (top_k={settings.top_k})...")
        answers = generate_answers(golden)
        generation = {
            "llm_model": settings.llm_model,
            "embed_model": settings.embed_model,
            "top_k": settings.top_k,
            "max_chunk_words": settings.max_chunk_words,
            "prompt_hash": sha256_short(SYSTEM_PROMPT),
            **git_state(),
        }
    stored = {a["id"]: (a.get("scores") or {}) for a in answers} if args.regate else {}
    answers = {a["id"]: {k: v for k, v in a.items() if k != "scores"} for a in answers}
    golden = [item for item in golden if item["id"] in answers]

    judged = {}
    if args.regate:
        judged = {qid: {m: sc.get(m) for m in scoring.JUDGED} for qid, sc in stored.items()}
        # A gate change can need a metric the source run never scored (e.g. factual correctness on
        # partial questions). Judge only those, so re-gating stays as cheap as it can be.
        needed = [
            item
            for item in golden
            if item["expected_status"] != "not supported"
            and judged.get(item["id"], {}).get("factual_correctness") is None
        ]
        if needed:
            print(f"Judging {len(needed)} question(s) missing a gate metric: {[i['id'] for i in needed]}")
            fresh = scoring.judged_scores(needed, answers, scoring.make_judge(JUDGE_MODEL))
            for qid, values in fresh.items():
                judged[qid] = {k: (judged.get(qid, {}).get(k) if v is None else v) for k, v in values.items()}
        print("Re-applying gates to the stored judged scores.")
    elif not args.skip_judge:
        print(f"Scoring with judge {JUDGE_MODEL}...")
        judged = scoring.judged_scores(golden, answers, scoring.make_judge(JUDGE_MODEL))

    records = []
    for item in golden:
        record = answers[item["id"]]
        scores = scoring.deterministic_scores(item, record) | judged.get(item["id"], dict.fromkeys(scoring.JUDGED))
        if args.skip_judge and not args.regate:
            scores |= {"pass": None, "fail_reasons": ["not judged"]}
        else:
            passed, reasons = scoring.gate(item, scores)
            scores |= {"pass": passed, "fail_reasons": reasons}
        records.append(record | {"scores": scores})

    run_info = {
        "golden_version": golden_version,
        "golden_hash": golden_hash(golden_version),
        "question_ids": [item["id"] for item in golden],
        "judge_model": json.loads((source / "run.json").read_text(encoding="utf-8"))["judge_model"]
        if args.regate
        else (None if args.skip_judge else JUDGE_MODEL),
        "gates": {
            "factual_correctness_min": scoring.FACTUAL_CORRECTNESS_MIN,
            "factual_correctness_mode": scoring.FACTUAL_CORRECTNESS_MODE,
        },
        "generation": generation,
    }

    run_dir.mkdir(parents=True)
    (run_dir / "answers.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8"
    )
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")

    for r in records:
        sc = r["scores"]
        detail = "; ".join(sc["fail_reasons"]) or "ok"
        print(f"  {r['id']}: {r['support_status']:<20} pass={sc['pass']}  {detail}")
    print("\nOverall:", json.dumps(overall([r["scores"] for r in records])))
    print(f"\nSaved to {run_dir} (golden {golden_version})")


if __name__ == "__main__":
    main()
