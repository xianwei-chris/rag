"""Sub-query expansion: turn a multi-part question into several retrieval queries.

Why this exists (measured in section 7.1 of the notebook): a question with two parts needs passages
from two regions of the embedding space, and one query is one vector. C04 ("must we notify, *and
what determines that*") ranked the passage holding the notifiability criteria 8th; asked on its own
that passage ranks 1st. Rewriting into a single better query does not help, because it only moves
the same point.

Two design rules, both learned from failures:

* **Always retrieve for the original question as well**, and never let the sub-queries displace its
  best hits. Naive rank fusion over sub-queries alone dropped both chunks holding S02's required
  evidence, because the generated sub-queries were uniformly anonymisation-flavoured and out-voted
  the question. `RESERVED` top hits of the original are kept unconditionally, so expansion can only
  add.
* **Skip the call when the question is simple.** A single-clause question has nothing to decompose,
  and the extra call buys nothing.
"""

from __future__ import annotations

import json
import re

from rag import llm

RESERVED = 3  # top hits of the original query that sub-queries may never displace
MAX_SUBQUERIES = 3
RRF_K = 60  # reciprocal-rank fusion constant; damps the tail of each ranking

EXPAND_PROMPT = """Rewrite the user's question as search queries for a document retrieval system.
Return JSON: {"queries": [string, ...]}.
Rules:
- 1 to 3 queries, each self-contained and keyword-rich.
- If the question has several parts, give each part its own query.
- If the question rests on a claim about what a document says, give that claim its own query, so the
  claim can be checked against the source.
- Do not answer the question."""

# A question worth decomposing has more than one clause, or rests on a premise.
_MULTI_PART = re.compile(r"\b(and|or|because|unless|whether)\b|[,;]", re.IGNORECASE)


def looks_multi_part(question: str) -> bool:
    return bool(_MULTI_PART.search(question)) or question.count("?") > 1


def sub_queries(question: str, model: str, temperature: float) -> list[str]:
    """Sub-queries for `question`, or [] if it is simple or the model returns nothing usable."""
    if not looks_multi_part(question):
        return []
    raw = llm.complete_json(
        [{"role": "system", "content": EXPAND_PROMPT}, {"role": "user", "content": question}],
        model,
        temperature,
    )
    try:
        queries = json.loads(raw).get("queries", [])
    except (json.JSONDecodeError, TypeError, AttributeError):
        return []
    seen = {question.strip().lower()}
    out = []
    for q in queries:
        if isinstance(q, str) and q.strip() and q.strip().lower() not in seen:
            seen.add(q.strip().lower())
            out.append(q.strip())
    return out[:MAX_SUBQUERIES]


def fuse(original: list, extra: list[list], k: int) -> list:
    """Keep the original ranking's top `RESERVED` hits, then fill from rank-fused sub-query results.

    `original` and each list in `extra` are rankings of retrieved chunks, best first. Returns at most
    `k` chunks. Because the reserved hits are taken first and the rest only fills the remainder, the
    result can never be worse than `original[:k]` on evidence the original already found.
    """
    kept = list(original[:RESERVED])
    chosen = {c.chunk_id for c in kept}
    if len(kept) >= k:
        return kept[:k]

    scores: dict[str, float] = {}
    pool: dict[str, object] = {}
    for ranking in [original, *extra]:
        for rank, chunk in enumerate(ranking, 1):
            if chunk.chunk_id in chosen:
                continue
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1 / (RRF_K + rank)
            pool.setdefault(chunk.chunk_id, chunk)

    for cid in sorted(scores, key=scores.get, reverse=True)[: k - len(kept)]:
        kept.append(pool[cid])
    return kept
