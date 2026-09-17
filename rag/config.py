"""Runtime settings, read from environment variables (optionally via a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ABSTAIN_ANSWER = "Not enough information in the provided documents."

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


def get_settings() -> Settings:
    return Settings()
