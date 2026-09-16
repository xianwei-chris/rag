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
python -m rag chat       # interactive loop
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
