"""Load the Markdown corpus and split it into heading-scoped chunks.

Strategy: every `#`/`##`/`###` section becomes one chunk, carrying its full
heading path (e.g. "Small Cell Suppression") so citations are human-readable.
Sections longer than `max_words` are split on paragraph boundaries with a
one-paragraph overlap. Heading-only sections (no body) are skipped.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

# Short, stable prefixes make chunk IDs readable in citations, e.g. "policy-07".
DOC_PREFIXES = {
    "pdpc_key_concepts_extract.md": "kc",
    "pdpc_healthcare_sector_extract.md": "hc",
    "pdpc_basic_anonymisation_extract.md": "anon",
    "synthetic_internal_policy_addendum.md": "policy",
}
# The internal addendum overrides public guidance where it is more specific.
INTERNAL_POLICY_DOCS = {"synthetic_internal_policy_addendum.md"}
EXCLUDED_FILES = {"README.md"}

HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")


@dataclass
class Chunk:
    chunk_id: str
    source: str
    doc_title: str
    section: str
    text: str
    authority: str
    metadata: dict = field(default_factory=dict)

    def embedding_text(self) -> str:
        # Prefixing title and section gives short sections enough context to embed well.
        return f"{self.doc_title} | {self.section}\n\n{self.text}"

    def to_metadata(self) -> dict:
        return {
            "source": self.source,
            "doc_title": self.doc_title,
            "section": self.section,
            "authority": self.authority,
        }


def list_documents(docs_dir: Path) -> list[Path]:
    return sorted(p for p in docs_dir.glob("*.md") if p.name not in EXCLUDED_FILES)


def corpus_fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _split_sections(markdown: str) -> tuple[str, list[tuple[list[str], str]]]:
    """Return (doc_title, [(heading_path, body), ...])."""
    doc_title = ""
    path: list[str] = []
    sections: list[tuple[list[str], str]] = []
    body: list[str] = []

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            sections.append((list(path), text))
        body.clear()

    for line in markdown.splitlines():
        m = HEADING_RE.match(line)
        if not m:
            body.append(line)
            continue
        flush()
        level, title = len(m.group(1)), m.group(2).strip()
        if level == 1 and not doc_title:
            doc_title = title
            path = []
            continue
        # Level 2 headings are the top of the section path under the doc title.
        depth = max(level - 2, 0)
        path = path[:depth] + [title]
    flush()
    return doc_title, sections


def _split_long(text: str, max_words: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []
    current: list[str] = []
    for para in paragraphs:
        if current and len(" ".join(current + [para]).split()) > max_words:
            pieces.append("\n\n".join(current))
            current = [current[-1]]  # one-paragraph overlap keeps context across the cut
        current.append(para)
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def chunk_document(path: Path, max_words: int = 300) -> list[Chunk]:
    doc_title, sections = _split_sections(path.read_text(encoding="utf-8"))
    prefix = DOC_PREFIXES.get(path.name, path.stem)
    authority = "internal_policy" if path.name in INTERNAL_POLICY_DOCS else "public_guidance"

    chunks: list[Chunk] = []
    for heading_path, body in sections:
        section = " > ".join(heading_path) or doc_title
        for piece in _split_long(body, max_words):
            chunks.append(
                Chunk(
                    chunk_id=f"{prefix}-{len(chunks) + 1:02d}",
                    source=path.name,
                    doc_title=doc_title,
                    section=section,
                    text=piece,
                    authority=authority,
                )
            )
    return chunks


def load_chunks(docs_dir: Path, max_words: int = 300) -> list[Chunk]:
    return [c for p in list_documents(docs_dir) for c in chunk_document(p, max_words)]
