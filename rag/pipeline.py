"""End-to-end question answering: retrieve -> generate -> validate."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from rag import llm, query
from rag.config import Settings, get_settings
from rag.generation import build_messages, parse_and_validate, strip_citations
from rag.store import RetrievedChunk, build_index, index_warnings, retrieve


@dataclass
class RagResult:
    question: str
    answer: str
    support_status: str
    citations: list[str]
    missing_information: str | None
    retrieved: list[RetrievedChunk]
    sub_queries: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_output: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def display_answer(self) -> str:
        """The answer as a user should see it: no internal chunk ids in the prose."""
        return strip_citations(self.answer)

    def cited_sources(self) -> list[str]:
        """Each citation resolved to '[ID] file :: section', in citation order."""
        by_id = {c.chunk_id: c for c in self.retrieved}
        return [f"[{cid}] {by_id[cid].source} :: {by_id[cid].section}" for cid in self.citations]


class RagPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return llm.embed(texts, self.settings.embed_model)

    def build_index(self) -> int:
        return build_index(self.settings, self._embed)

    def _retrieve(self, question: str, k: int) -> tuple[list[RetrievedChunk], list[str]]:
        """Retrieve `k` chunks, optionally widening the question into sub-queries first."""
        chunks = retrieve(question, self.settings, self._embed, k)
        if not self.settings.query_expansion:
            return chunks, []
        subs = query.sub_queries(question, self.settings.llm_model, self.settings.temperature)
        if not subs:
            return chunks, []
        # Retrieve deeper per sub-query so fusion has a ranking to work with, not just k hits.
        extra = [retrieve(q, self.settings, self._embed, k * 3) for q in subs]
        return query.fuse(chunks, extra, k), subs

    def ask(self, question: str, k: int | None = None) -> RagResult:
        warnings = index_warnings(self.settings)
        chunks, subs = self._retrieve(question, k or self.settings.top_k)
        raw = llm.complete_json(
            build_messages(question, chunks), self.settings.llm_model, self.settings.temperature
        )
        result, validation_warnings = parse_and_validate(raw, chunks)
        return RagResult(
            question=question,
            retrieved=chunks,
            sub_queries=subs,
            warnings=warnings + validation_warnings,
            raw_output=raw,
            **result,
        )
