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
        """Retrieve `k` chunks, or, for a multi-part question, the union over its sub-queries."""
        if not self.settings.query_expansion:
            return retrieve(question, self.settings, self._embed, k), []
        subs = query.sub_queries(question, self.settings.llm_model, self.settings.temperature)
        if not subs:
            return retrieve(question, self.settings, self._embed, k), []
        # The original is retrieved to full depth `k`, the sub-queries to PER_QUERY each. Retrieving
        # only PER_QUERY for the original too can leave fewer than `k` passages after de-duplication
        # when the sub-queries overlap, which starved C05 of the passage naming the notification duty.
        rankings = [retrieve(question, self.settings, self._embed, k)]
        rankings += [retrieve(q, self.settings, self._embed, query.PER_QUERY) for q in subs]
        return query.merge(rankings), subs

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
