"""Load saved evaluation runs and render the assignment's results table.

Used by the notebook so it stays narrative rather than plumbing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

EVAL_DIR = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"
GOLDEN_PATH = EVAL_DIR / "golden_set.json"
REVIEW_PATH = EVAL_DIR / "manual_review.json"

RULE_SCORES = ["status_correct", "evidence_recall", "rule_pass"]
RAGAS_SCORES = ["faithfulness", "context_precision", "context_recall", "factual_correctness"]

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


@dataclass
class Run:
    path: Path
    results: pd.DataFrame
    answers: dict[str, dict]
    summary: dict

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def config(self) -> dict:
        return self.summary["config"]


def load_golden(path: Path = GOLDEN_PATH) -> dict[str, dict]:
    return {item["id"]: item for item in json.loads(path.read_text(encoding="utf-8"))}


def list_runs(results_dir: Path = RESULTS_DIR) -> list[Path]:
    return sorted(p for p in results_dir.iterdir() if (p / "results.csv").exists())


def load_run(path: Path | str) -> Run:
    path = Path(path)
    answers = {
        json.loads(line)["id"]: json.loads(line)
        for line in (path / "answers.jsonl").read_text(encoding="utf-8").splitlines()
    }
    return Run(
        path=path,
        results=pd.read_csv(path / "results.csv"),
        answers=answers,
        summary=json.loads((path / "summary.json").read_text(encoding="utf-8")),
    )


def load_review(path: Path = REVIEW_PATH) -> dict[str, dict]:
    """Manual pass/fail verdicts; the automated rule check cannot judge expected behaviour."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_summary(answer: dict, max_chars: int = 220) -> str:
    """Compact 'chunk_id (section): snippet' list of the cited (else retrieved) passages."""
    cited = [c for c in answer["retrieved"] if c["chunk_id"] in answer["citations"]]
    shown = cited or answer["retrieved"][:2]
    return "\n".join(
        f"[{c['chunk_id']}] {c['source']} :: {c['section']} — "
        f"{' '.join(c['text'].split())[:max_chars]}..."
        for c in shown
    )


def assignment_table(run: Run, golden: dict[str, dict] | None = None, review: dict | None = None) -> pd.DataFrame:
    """The table required by the brief, with its column names."""
    golden = golden or load_golden()
    review = load_review() if review is None else review
    rows = []
    for row in run.results.itertuples():
        item, answer = golden[row.id], run.answers[row.id]
        verdict = review.get(row.id, {})
        passed = verdict.get("pass", bool(row.rule_pass))
        notes = verdict.get("note") or (row.warnings if isinstance(row.warnings, str) else "")
        rows.append(
            {
                "Question": f"{row.id}. {item['question']}",
                "Expected Behavior": item["expected_behavior"],
                "Retrieved Evidence": evidence_summary(answer),
                "Answer": answer["answer"]
                + (f"\n\nMissing: {answer['missing_information']}" if answer["missing_information"] else ""),
                "Support Status": answer["support_status"],
                "Pass/Fail": "Pass" if passed else "Fail",
                "Notes": notes,
            }
        )
    return pd.DataFrame(rows, columns=TABLE_COLUMNS)


def scores_table(run: Run) -> pd.DataFrame:
    columns = ["id", "source", "type", "expected_status", "predicted_status", *RULE_SCORES, *RAGAS_SCORES]
    return run.results[columns]


def compare_runs(runs: list[Run], metrics: list[str] | None = None) -> pd.DataFrame:
    metrics = metrics or [*RULE_SCORES, *RAGAS_SCORES]
    return pd.DataFrame(
        {
            run.name: {m: run.summary["overall"].get(m) for m in metrics}
            | {"top_k": run.config.get("top_k"), "n": run.summary["overall"]["n"]}
            for run in runs
        }
    )


def show_case(run: Run, qid: str, golden: dict[str, dict] | None = None, chars: int = 350) -> None:
    """Print one question end to end: expectation, answer, scores, retrieved passages."""
    golden = golden or load_golden()
    item, answer = golden[qid], run.answers[qid]
    row = run.results[run.results["id"] == qid].iloc[0]
    print(f"{qid} [{item['source']} / {item['type']}]\n\nQ: {item['question']}\n")
    print(f"Expected behaviour: {item['expected_behavior']}")
    print(f"Expected status: {item['expected_status']}   predicted: {answer['support_status']}")
    print("Scores:", {m: row[m] for m in RULE_SCORES + RAGAS_SCORES})
    if answer["missing_information"]:
        print("Reported missing:", answer["missing_information"])
    print(f"\nAnswer:\n{answer['answer']}\n\nRetrieved ('*' = cited):")
    for c in answer["retrieved"]:
        mark = "*" if c["chunk_id"] in answer["citations"] else " "
        print(f" {mark} [{c['chunk_id']}] {c['section']} (distance={c['distance']:.3f})")
        print("     ", " ".join(c["text"].split())[:chars], "...")
