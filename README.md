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
| Retrieve | `rag/store.py`, `rag/query.py` | Top-k dense retrieval. Optional sub-query expansion (`RAG_QUERY_EXPANSION=1`) for multi-part questions: the de-duplicated union of the original query's top-k and 3 chunks per sub-query. |
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
uv run python -m eval.run_eval --name tmp --skip-judge      # deterministic metrics only (no judge calls)
uv run python -m eval.run_eval --name 01-fc90 --regate \
    --reuse-answers eval/results/01-baseline             # re-apply gates to stored scores, no LLM calls
uv run python -m eval.run_eval --name <new-run> --golden v1 \
    --reuse-answers eval/results/<old-run>                # re-score old answers on a new golden set
RAG_QUERY_EXPANSION=1 uv run python -m eval.run_eval --name <new-run>   # with sub-query retrieval
```

Sub-query retrieval (`rag/query.py`, off by default) splits a multi-part question into at most 3
sub-queries, retrieves 3 chunks for each alongside the original query's full top-k, and passes the
de-duplicated union to generation. Retrieving the original to full depth means expansion can only add.
It took `retrieval_recall` to 1.000; see section 7.2 of the notebook.

Metrics and pass/fail gates are defined in `eval/scoring.py` and explained in section 4.2 of
`rag_assignment.ipynb`:

- deterministic (quote matching, no LLM): `status_correct` (gates), `retrieval_recall` and
  `retrieval_precision` (diagnostics; they explain *why* an answer was wrong but do not gate);
- judged (judge `RAG_JUDGE_MODEL`, default `gemini/gemini-2.5-flash`): `factual_correctness` (RAGAS,
  `recall` mode — gates), `missing_points_named` (partial questions — gates), and `faithfulness`
  (claims grounded in the retrieved passages — debug only, does not gate);
- `pass`: one gate shape for every question — the right call (`status_correct`) and the right content
  (per expected status: factual correctness / missing points named / the abstention text, which is
  emitted in code) — with `fail_reasons` stored per question.

`recall` mode excludes false positives, so an answer is not marked down for stating more than the
reference. Known weakness: RAGAS takes TP and FN from two different claim decompositions, so both can
fall to zero together and score 0.00 for an answer that states every reference claim. An exact 0.0 is
treated as suspect and checked against the claims. See section 6 of the notebook.

### Notebook

`eval/explore_results.ipynb` inspects a saved run: scores, breakdowns, per-question drill-down,
which required evidence was missed, and a live re-ask cell.

```bash
uv run python -m ipykernel install --user --name rag-assessment --display-name "Python (rag-assessment)"
uv run jupyter lab eval/explore_results.ipynb
```

The first command registers this project's `.venv` as a Jupyter kernel, so the notebook can also be
opened in VS Code or any other Jupyter client by selecting the **Python (rag-assessment)** kernel.
