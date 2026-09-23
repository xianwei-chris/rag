"""Runtime settings, read from environment variables (optionally via a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The one fixed abstention message. It is a constant, not something the model writes: a model-worded
# refusal can smuggle in an invented fact ("...though notification is generally required within 72
# hours"), and code that emits a fixed string cannot. Kept exact so the evaluation, and any caller,
# can detect abstention without an LLM. The second sentence points at what the pack does cover.
ABSTAIN_ANSWER = (
    "Sorry, we could not find an answer to that in the provided documents. "
    "We can help with PDPA key concepts, healthcare-sector guidance, anonymisation, "
    "and the internal data-sharing policy - try asking about one of those."
)

load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_model: str = os.getenv("RAG_LLM_MODEL", "gemini/gemini-3.5-flash")
    embed_model: str = os.getenv("RAG_EMBED_MODEL", "gemini/gemini-embedding-001")
    docs_dir: Path = PROJECT_ROOT / os.getenv("RAG_DOCS_DIR", "documents")
    chroma_dir: Path = PROJECT_ROOT / os.getenv("RAG_CHROMA_DIR", ".chroma")
    collection: str = os.getenv("RAG_COLLECTION", "pdpc_policy")
    top_k: int = int(os.getenv("RAG_TOP_K", "5"))
    max_chunk_words: int = int(os.getenv("RAG_MAX_CHUNK_WORDS", "300"))
    temperature: float = float(os.getenv("RAG_TEMPERATURE", "0"))
    # Expand a multi-part question into sub-queries before retrieving (rag/query.py). Off by
    # default so the baseline is reproducible; RAG_QUERY_EXPANSION=1 turns it on.
    query_expansion: bool = os.getenv("RAG_QUERY_EXPANSION", "0") == "1"


def get_settings() -> Settings:
    return Settings()
