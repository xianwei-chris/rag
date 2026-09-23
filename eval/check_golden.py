"""Validate the golden set against the corpus and the current chunking.

    uv run python -m eval.check_golden            # latest version in eval/golden/
    uv run python -m eval.check_golden v1         # a specific version

Checks that every evidence quote appears verbatim in its source document and
lands inside a single chunk (a quote split across chunks can never be matched).
Also shows which chunk currently holds each quote, for debugging retrieval.

Two structural guards, added after the run-01 review found defects these would have caught:
  * a `multi-passage` question must have at least two evidence groups (S01 was typed
    multi-passage while answerable from one chunk);
  * a reference sentence that *nearly* but not exactly matches a source sentence is flagged as
    paraphrase drift (C09's reference dropped "clinical" from "a formal clinical governance
    process", then scored the answer down for keeping it).
"""

from __future__ import annotations

import sys

import difflib
import re

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

    errors += structural_checks(golden)
    errors += paraphrase_drift(golden, settings)

    print(f"\n{len(golden)} questions, {errors} error(s)")
    return 1 if errors else 0


def structural_checks(golden: list[dict]) -> int:
    """Type must match the evidence: multi-passage means more than one group is required."""
    errors = 0
    print("\nStructure:")
    for item in golden:
        groups = len(item["required_evidence"])
        if item["type"] == "multi-passage" and groups < 2:
            print(f"  ERROR {item['id']}: typed multi-passage but has {groups} evidence group(s)")
            errors += 1
        if item["expected_status"] == "partially supported" and not item.get("missing_points"):
            print(f"  ERROR {item['id']}: partially supported but no missing_points")
            errors += 1
    print("  ok" if not errors else "")
    return errors


def paraphrase_drift(golden: list[dict], settings, threshold: float = 0.82) -> int:
    """Flag reference sentences that nearly match a source sentence but are not identical.

    A near-match means the reference paraphrased the documents. Because factual correctness runs in
    recall mode, a paraphrase that drops a qualifier cannot be rescued by a more precise answer: the
    extra precision earns no credit and the lost qualifier scores as a miss.
    """
    corpus = []
    for doc in sorted(settings.docs_dir.glob("*.md")):
        if doc.name == "README.md":
            continue
        for sentence in re.split(r"(?<=[.;])\s+", " ".join(doc.read_text(encoding="utf-8").split())):
            if len(sentence) > 40:
                corpus.append((doc.name, sentence.strip()))

    print("\nReference paraphrase drift (warnings only):")
    found = 0
    for item in golden:
        for sentence in re.split(r"(?<=\.)\s+", item.get("reference") or ""):
            sentence = sentence.strip()
            if len(sentence) <= 40:
                continue
            best, score = None, 0.0
            for name, candidate in corpus:
                ratio = difflib.SequenceMatcher(None, normalize(sentence), normalize(candidate)).ratio()
                if ratio > score:
                    best, score = (name, candidate), ratio
            if threshold <= score < 1.0:
                found += 1
                print(f"  {item['id']} ({score:.2f}) reference: {sentence[:100]}")
                print(f"       {best[0]}: {best[1][:100]}")
    if not found:
        print("  none")
    return 0  # warnings, not errors


if __name__ == "__main__":
    sys.exit(main())
