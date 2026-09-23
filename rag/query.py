"""Sub-query expansion: turn a multi-part question into several retrieval queries.

Why this exists (measured in section 6.1 of the notebook): a question with two parts needs passages
from two regions of the embedding space, and one query is one vector. C04 ("must we notify, *and
what determines that*") ranked the passage holding the notifiability criteria 8th; asked on its own
that passage ranks 1st. Rewriting into a single better query does not help, because it only moves
the same point.

Design, kept deliberately simple: split the question into at most `MAX_SUBQUERIES` sub-queries,
retrieve `PER_QUERY` chunks for each, and pass the union to generation. No rank fusion and no
weighting -- each sub-query simply brings its own best passages.

Two rules:

* **The original question is always one of the queries, retrieved to full depth `top_k`.** Sub-queries
  can miss what the question as a whole is about: an early attempt using only the generated
  sub-queries dropped both chunks holding S02's required evidence, because all three came back
  anonymisation-flavoured while the question was really about a suppression rule. Retrieving the
  original to `top_k` also guarantees at least `top_k` passages: when sub-queries overlap heavily the
  de-duplicated union can otherwise be *smaller* than an ordinary retrieval, which starved C05.
* **Skip the call when the question is simple.** A single-clause question has nothing to decompose,
  and the extra call buys nothing.

The cost is a larger context on multi-part questions (up to `(1 + MAX_SUBQUERIES) * PER_QUERY`
passages before de-duplication, against `top_k` for a simple one), traded for covering each part of
the question.
"""

from __future__ import annotations

import json
import re

from rag import llm

MAX_SUBQUERIES = 3
PER_QUERY = 3  # chunks retrieved per query, including the original

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


def merge(rankings: list[list]) -> list:
    """De-duplicated union of several rankings, taking one chunk at a time from each in turn.

    Interleaving rather than concatenating means every query contributes its best hit before any
    query contributes its second, so no single sub-query can crowd out the others.
    """
    merged, seen = [], set()
    for rank in range(max((len(r) for r in rankings), default=0)):
        for ranking in rankings:
            if rank < len(ranking) and ranking[rank].chunk_id not in seen:
                seen.add(ranking[rank].chunk_id)
                merged.append(ranking[rank])
    return merged
