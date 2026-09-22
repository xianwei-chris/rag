"""Load saved evaluation runs and derive every table and average from them.

A run folder stores only what cannot be recomputed:
    answers.jsonl  per question: the system's output and its scores
    run.json       provenance: golden version + hash, git commit, models, top_k, prompt hash
Everything else (results table, averages, the assignment's table) is derived here, so stored
numbers can never disagree with each other. A run is always displayed against the golden-set
version it was scored with, so later iterations never change what an earlier run shows.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from eval.scoring import DETERMINISTIC, JUDGED
from eval.versioning import golden_hash, load_golden

EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"

METRICS = ["pass", *DETERMINISTIC, *JUDGED]

# Column names required by the assignment brief.
TABLE_COLUMNS = [
    "Question",
    "Expected Behavior",
    "Retrieved Evidence",
    "Answer",
    "Support Status",
    "Pass/Fail",
    "Notes",
]


def _mean(values) -> float | None:
    numbers = [float(v) for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    return round(sum(numbers) / len(numbers), 3) if numbers else None


def overall(scores: list[dict]) -> dict:
    """Mean of each metric over a list of per-question score dicts (None values skipped)."""
    return {m: _mean(s.get(m) for s in scores) for m in METRICS} | {"n": len(scores)}


@dataclass
class Run:
    path: Path
    info: dict  # run.json
    answers: dict[str, dict]  # answers.jsonl keyed by question id
    golden: dict[str, dict]  # the golden version this run was scored against

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def config(self) -> dict:
        """Flat view of what produced the run, for display and comparison."""
        gen = self.info["generation"]
        return {
            "golden_version": self.info["golden_version"],
            "top_k": gen["top_k"],
            "llm_model": gen["llm_model"],
            "embed_model": gen["embed_model"],
            "judge_model": self.info["judge_model"],
            "prompt_hash": gen["prompt_hash"],
            "git_commit": gen["git_commit"],
            "answers_from": gen.get("answers_from"),
        }

    @property
    def results(self) -> pd.DataFrame:
        """One row per question: identity, expectation, prediction and all scores."""
        rows = []
        for qid, answer in self.answers.items():
            item = self.golden[qid]
            rows.append(
                {
                    "id": qid,
                    "source": item["source"],
                    "type": item["type"],
                    "expected_status": item["expected_status"],
                    "predicted_status": answer["support_status"],
                    **{m: answer["scores"].get(m) for m in METRICS},
                    "fail_reasons": "; ".join(answer["scores"].get("fail_reasons") or []) or None,
                    "latency_s": answer["latency_s"],
                    "warnings": " | ".join(answer["warnings"]) or None,
                }
            )
        return pd.DataFrame(rows)

    def summary(self) -> dict:
        """Averages overall and by source, type and expected status."""
        frame = self.results

        def means(group: pd.DataFrame) -> dict:
            return overall(group[METRICS].to_dict("records"))

        return {
            "overall": means(frame),
            "by_source": {k: means(g) for k, g in frame.groupby("source")},
            "by_type": {k: means(g) for k, g in frame.groupby("type")},
            "by_expected_status": {k: means(g) for k, g in frame.groupby("expected_status")},
        }


def list_runs(results_dir: Path = RESULTS_DIR) -> list[Path]:
    return sorted(p for p in results_dir.iterdir() if (p / "run.json").exists())


def load_run(name_or_path: Path | str) -> Run:
    path = Path(name_or_path)
    if not path.exists():
        path = RESULTS_DIR / str(name_or_path)
    info = json.loads((path / "run.json").read_text(encoding="utf-8"))
    version = info["golden_version"]
    if golden_hash(version) != info["golden_hash"]:
        raise ValueError(
            f"Golden set {version} changed after run {path.name} used it; golden sets must be immutable "
            "(create a new version instead of editing)."
        )
    answers = {
        record["id"]: record
        for record in map(json.loads, (path / "answers.jsonl").read_text(encoding="utf-8").splitlines())
    }
    return Run(path=path, info=info, answers=answers, golden={g["id"]: g for g in load_golden(version)})


def evidence_summary(answer: dict, max_chars: int = 220) -> str:
    """Compact 'chunk_id (section): snippet' list of the cited (else retrieved) passages."""
    cited = [c for c in answer["retrieved"] if c["chunk_id"] in answer["citations"]]
    shown = cited or answer["retrieved"][:2]
    return "\n".join(
        f"[{c['chunk_id']}] {c['source']} :: {c['section']} — "
        f"{' '.join(c['text'].split())[:max_chars]}..."
        for c in shown
    )


def assignment_table(run: Run, review: dict[str, dict] | None = None) -> pd.DataFrame:
    """The table required by the brief, with its column names.

    `review` holds manual verdicts {id: {"pass": bool, "note": str}}; questions without one fall
    back to the automated gates.
    """
    review = review or {}
    rows = []
    for qid, answer in run.answers.items():
        item, verdict = run.golden[qid], review.get(qid, {})
        passed = verdict.get("pass", bool(answer["scores"]["pass"]))
        rows.append(
            {
                "Question": f"{qid}. {item['question']}",
                "Expected Behavior": item["expected_behavior"],
                "Retrieved Evidence": evidence_summary(answer),
                "Answer": answer["answer"]
                + (f"\n\nMissing: {answer['missing_information']}" if answer["missing_information"] else ""),
                "Support Status": answer["support_status"],
                "Pass/Fail": "Pass" if passed else "Fail",
                "Notes": verdict.get("note")
                or "; ".join(answer["scores"].get("fail_reasons") or [])
                or " | ".join(answer["warnings"]),
            }
        )
    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


def passages(answer: dict, chars: int = 400, cited_only: bool = False) -> str:
    """Every retrieved passage as '* [id] file :: section — text' ('*' marks a cited one)."""
    chunks = answer["retrieved"]
    if cited_only:
        chunks = [c for c in chunks if c["chunk_id"] in answer["citations"]]
    return "\n\n".join(
        f"{'*' if c['chunk_id'] in answer['citations'] else ' '} [{c['chunk_id']}] "
        f"{c['source']} :: {c['section']} (d={c['distance']:.3f})\n"
        f"{' '.join(c['text'].split())[:chars]}{'...' if len(c['text']) > chars else ''}"
        for c in chunks
    )


def review_table(run: Run, review: dict[str, dict] | None = None, chars: int = 400) -> pd.DataFrame:
    """Everything about each question in one row, for reading the run and recording a verdict.

    Columns cover what was asked, what was expected, what the system did, and how it scored, so a
    case can be judged without opening any other file. `my_pass`/`my_note` carry the verdicts already
    in `review` and are empty elsewhere, ready to be filled in.
    """
    review = review or {}
    rows = []
    for qid, answer in run.answers.items():
        item, verdict, scores = run.golden[qid], review.get(qid, {}), answer["scores"]
        by_id = {c["chunk_id"]: c for c in answer["retrieved"]}
        rows.append(
            {
                "id": qid,
                "source": item["source"],
                "type": item["type"],
                "question": item["question"],
                "expected_behavior": item["expected_behavior"],
                "expected_status": item["expected_status"],
                "predicted_status": answer["support_status"],
                "reference": item.get("reference"),
                "missing_points": "; ".join(item.get("missing_points") or []) or None,
                "answer": answer["answer"],
                "missing_information": answer["missing_information"],
                "citations": "\n".join(
                    f"[{c}] {by_id[c]['source']} :: {by_id[c]['section']}" for c in answer["citations"]
                )
                or None,
                "retrieved": passages(answer, chars=chars),
                **{m: scores.get(m) for m in METRICS},
                "fail_reasons": "; ".join(scores.get("fail_reasons") or []) or None,
                "warnings": " | ".join(answer["warnings"]) or None,
                "latency_s": answer["latency_s"],
                "notes": item.get("notes"),
                "my_pass": verdict.get("pass"),
                "my_note": verdict.get("note"),
            }
        )
    return pd.DataFrame(rows).set_index("id")


def review_style(frame: pd.DataFrame):
    """`review_table` rendered so long text wraps and rows stay aligned."""
    return frame.style.set_properties(
        **{"white-space": "pre-wrap", "text-align": "left", "vertical-align": "top"}
    ).set_table_styles([{"selector": "th", "props": [("text-align", "left"), ("vertical-align", "top")]}])


def review_case(run: Run, qid: str, chars: int = 400) -> None:
    """One question printed as a block, for reading rather than scanning a wide table."""
    row = review_table(run, chars=chars).loc[qid]
    for field, value in row.items():
        if value is None or value == "" or (isinstance(value, float) and math.isnan(value)):
            continue
        text = str(value)
        print(f"{field}:")
        print("\n".join("    " + line for line in text.splitlines()) if "\n" in text else f"    {text}")
    print()


def scores_table(run: Run) -> pd.DataFrame:
    return run.results[["id", "source", "type", "expected_status", "predicted_status", *METRICS]]


def compare_runs(runs: list[Run], metrics: list[str] | None = None) -> pd.DataFrame:
    metrics = metrics or METRICS
    return pd.DataFrame(
        {
            run.name: {m: run.summary()["overall"].get(m) for m in metrics}
            | {
                "top_k": run.config["top_k"],
                "golden": run.config["golden_version"],
                "prompt": run.config["prompt_hash"],
                "n": len(run.answers),
            }
            for run in runs
        }
    )


def show_case(run: Run, qid: str, chars: int = 350) -> None:
    """Print one question end to end: expectation, answer, scores, retrieved passages."""
    item, answer = run.golden[qid], run.answers[qid]
    print(f"{qid} [{item['source']} / {item['type']}]\n\nQ: {item['question']}\n")
    print(f"Expected behaviour: {item['expected_behavior']}")
    print(f"Expected status: {item['expected_status']}   predicted: {answer['support_status']}")
    print("Scores:", {m: answer["scores"].get(m) for m in METRICS})
    if answer["scores"].get("fail_reasons"):
        print("Failed because:", "; ".join(answer["scores"]["fail_reasons"]))
    if answer["missing_information"]:
        print("Reported missing:", answer["missing_information"])
    by_id = {c["chunk_id"]: c for c in answer["retrieved"]}
    print(f"\nAnswer:\n{answer['answer']}\n\nCitations:")
    for cid in answer["citations"]:
        print(f"  [{cid}] {by_id[cid]['source']} :: {by_id[cid]['section']}")
    print("\nRetrieved ('*' = cited):")
    for c in answer["retrieved"]:
        mark = "*" if c["chunk_id"] in answer["citations"] else " "
        print(f" {mark} [{c['chunk_id']}] {c['section']} (distance={c['distance']:.3f})")
        print("     ", " ".join(c["text"].split())[:chars], "...")
