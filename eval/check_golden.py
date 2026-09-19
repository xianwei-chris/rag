"""Validate the golden set against the corpus and the current chunking.

    uv run python -m eval.check_golden            # latest version in eval/golden/
    uv run python -m eval.check_golden v1         # a specific version

Checks that every evidence quote appears verbatim in its source document and
lands inside a single chunk (a quote split across chunks can never be matched).
Also shows which chunk currently holds each quote, for debugging retrieval.
"""

from __future__ import annotations

import sys

from eval.evidence import normalize, quote_in
from eval.versioning import latest_golden_version, load_golden
from rag.chunking import load_chunks
from rag.config import get_settings


def main() -> int:
    version = sys.argv[1] if len(sys.argv) > 1 else latest_golden_version()
    settings = get_settings()
    chunks = load_chunks(settings.docs_dir, settings.max_chunk_words)
    golden = load_golden(version)
    print(f"Checking golden set {version}\n")
    errors = 0

    for item in golden:
        print(f"{item['id']} [{item['source']}/{item['type']}] expected={item['expected_status']}")
        for i, group in enumerate(item["required_evidence"], 1):
            for ev in group:
                doc = settings.docs_dir / ev["source"]
                if not doc.exists():
                    print(f"  ERROR group {i}: unknown source {ev['source']}")
                    errors += 1
                    continue
                count = normalize(doc.read_text(encoding="utf-8")).count(normalize(ev["quote"]))
                holders = [c.chunk_id for c in chunks if c.source == ev["source"] and quote_in(ev["quote"], c.text)]
                status = "ok"
                if count == 0:
                    status, errors = "ERROR not found in document", errors + 1
                elif not holders:
                    status, errors = "ERROR split across chunks", errors + 1
                elif count > 1:
                    status = f"warn: appears {count}x in document"
                print(f"  g{i} {status:<10} {','.join(holders) or '-':<18} {ev['quote'][:70]}")

    print(f"\n{len(golden)} questions, {errors} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
