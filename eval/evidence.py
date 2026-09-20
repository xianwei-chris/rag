"""Chunking-independent evidence matching for the golden set.

Golden evidence is written as {"source": <file>, "quote": <verbatim text>}.
`required_evidence` is a list of groups: every group must be satisfied, and a
group is satisfied when any one of its quotes appears in a retrieved chunk
from the same source file.
"""

from __future__ import annotations

import re


def normalize(text: str) -> str:
    text = text.replace("**", "")
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_in(quote: str, text: str) -> bool:
    return normalize(quote) in normalize(text)


def group_hit(group: list[dict], retrieved: list) -> bool:
    """`retrieved` items need `.source` and `.text` (e.g. RetrievedChunk or Chunk)."""
    return any(
        ev["source"] == chunk.source and quote_in(ev["quote"], chunk.text)
        for ev in group
        for chunk in retrieved
    )
