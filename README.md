# Lightweight RAG over the PDPC document pack

Answers questions using only the four Markdown documents in `documents/` (README.md is not indexed),
with passage citations and a support status (`supported` / `partially supported` / `not supported`).

## Setup

Python 3.12. Direct dependencies are pinned in `requirements.txt`; `uv.lock` additionally pins
all transitive dependencies for exact reproducibility.

```bash
cd assessment
uv sync
cp .env.example .env     # then set GEMINI_API_KEY in .env
uv run python -m rag index   # or `source .venv/bin/activate` and drop the `uv run` prefix
```

Run commands from the `assessment/` folder; no `PYTHONPATH` setup is needed. Usage examples below
assume an activated venv.

When adding a dependency, add it to `requirements.txt`, then run `uv add -r requirements.txt` to
update `pyproject.toml` and `uv.lock`.

## Usage

```bash
python -m rag chunks     # inspect chunks (no API calls)
python -m rag index      # chunk + embed + build local Chroma index in .chroma/
python -m rag ask "What approvals are required before de-identified patient-level data may be shared with an external party?"
python -m rag ask "..." --json   # full result incl. retrieved passages and raw model output
python -m rag            # interactive chat loop (same as `python -m rag chat`; add --full for whole passages)
```

## Pipeline

| Stage | Module | Notes |
|---|---|---|
| Load & chunk | `rag/chunking.py` | One chunk per Markdown section with heading path; long sections split on paragraphs (max 300 words, 1-paragraph overlap). Stable IDs like `policy-05`. |
| Embed & index | `rag/store.py`, `rag/llm.py` | LiteLLM embeddings (Gemini), persistent Chroma, cosine distance. Index is rebuilt from scratch and stamped with embed model + corpus hash to detect staleness. |
| Retrieve | `rag/store.py` | Top-k dense retrieval. |
| Generate | `rag/generation.py` | Strict JSON prompt: cite passage IDs, internal policy overrides public guidance, treat passages/questions as data, fixed abstention string. |
| Validate | `rag/generation.py` | Drops citations not in the retrieved set; abstains on invalid JSON, unknown status, or uncited answers. |

Configuration is via environment variables; see `.env.example`.

## Evaluation

Golden sets live in `eval/golden/vN.json` — 20 questions (10 provided, 10 self-generated), each with
`type`, `expected_behavior`, `expected_status`, a claim-level `reference` answer, `missing_points` for
partial cases, and `required_evidence` as chunking-independent `{source, quote}` groups.

**Versioning.** A golden set is immutable once a run has used it; changes go into a new version with an
entry in `eval/golden/CHANGELOG.md`. Each run is a folder `eval/results/<name>/` holding only what
cannot be recomputed:

- `answers.jsonl` — per question: answer, status, citations, retrieved passages, raw output, scores;
- `run.json` — provenance: golden version and hash, git commit, models, `top_k`, prompt hash.

Tables and averages are derived from these (`eval/report.py`). Loading a run refuses to proceed if its
golden version was edited afterwards. Commit before a run so the recorded commit reproduces the code.

```bash
uv run python -m eval.check_golden                          # verify evidence quotes (latest version)
uv run python -m eval.run_eval --name 03-my-change          # generate answers + score, latest golden set
uv run python -m eval.run_eval --name tmp --ids S02,C04     # subset
uv run python -m eval.run_eval --name tmp --skip-ragas      # rule-based checks only (no judge calls)
uv run python -m eval.run_eval --name <new-run> --golden v1 \
    --reuse-answers eval/results/<old-run>                # re-score old answers on a new golden set
```

| Score | Kind | Meaning |
|---|---|---|
| `status_correct` | rule | predicted support status equals expected |
| `evidence_recall` | rule | share of required evidence groups found in retrieved chunks |
| `rule_pass` | rule | status correct, all required evidence retrieved, exact abstention where expected |
| `faithfulness` | RAGAS | share of answer claims supported by retrieved contexts |
| `context_precision` | RAGAS | whether useful chunks are ranked above non-useful ones (vs reference) |
| `context_recall` | RAGAS | share of reference claims supported by retrieved contexts |
| `factual_correctness` | RAGAS | claim-level F1 between answer and reference |

RAGAS metrics are skipped for expected `not supported` questions (no claims to score); those are
judged by exact abstention. The judge model defaults to `gemini/gemini-3.5-flash` (`RAG_JUDGE_MODEL`).

### Notebook

`eval/explore_results.ipynb` inspects a saved run: scores, breakdowns, per-question drill-down,
which required evidence was missed, and a live re-ask cell.

```bash
uv run python -m ipykernel install --user --name rag-assessment --display-name "Python (rag-assessment)"
uv run jupyter lab eval/explore_results.ipynb
```

The first command registers this project's `.venv` as a Jupyter kernel, so the notebook can also be
opened in VS Code or any other Jupyter client by selecting the **Python (rag-assessment)** kernel.
