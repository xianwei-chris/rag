"""Build and query the persistent Chroma index."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import chromadb

from rag.chunking import corpus_fingerprint, list_documents, load_chunks
from rag.config import Settings

EmbedFn = Callable[[list[str]], list[list[float]]]


@dataclass
class RetrievedChunk:
    chunk_id: str
    source: str
    section: str
    authority: str
    text: str
    distance: float  # cosine distance, lower is closer


def _client(settings: Settings) -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(settings.chroma_dir))


def build_index(settings: Settings, embed_fn: EmbedFn) -> int:
    """Rebuild the collection from scratch so the index always matches the corpus."""
    chunks = load_chunks(settings.docs_dir, settings.max_chunk_words)
    vectors = embed_fn([c.embedding_text() for c in chunks])

    client = _client(settings)
    if settings.collection in [c.name for c in client.list_collections()]:
        client.delete_collection(settings.collection)
    collection = client.create_collection(
        settings.collection,
        metadata={
            "hnsw:space": "cosine",
            "embed_model": settings.embed_model,
            "corpus_fingerprint": corpus_fingerprint(list_documents(settings.docs_dir)),
            "max_chunk_words": settings.max_chunk_words,
        },
    )
    collection.add(
        ids=[c.chunk_id for c in chunks],
        embeddings=vectors,
        documents=[c.text for c in chunks],
        metadatas=[c.to_metadata() for c in chunks],
    )
    return len(chunks)


def index_warnings(settings: Settings) -> list[str]:
    """Detect a stale index (docs or embedding model changed since it was built)."""
    try:
        meta = _client(settings).get_collection(settings.collection).metadata or {}
    except Exception:
        raise RuntimeError("Index not found. Run `uv run python -m rag index` first.")
    warnings = []
    if meta.get("embed_model") != settings.embed_model:
        warnings.append(
            f"Index built with {meta.get('embed_model')}, but config uses {settings.embed_model}."
        )
    if meta.get("corpus_fingerprint") != corpus_fingerprint(list_documents(settings.docs_dir)):
        warnings.append("Documents changed since the index was built; re-run `index`.")
    return warnings


def retrieve(question: str, settings: Settings, embed_fn: EmbedFn, k: int) -> list[RetrievedChunk]:
    collection = _client(settings).get_collection(settings.collection)
    result = collection.query(query_embeddings=embed_fn([question]), n_results=k)
    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            source=meta["source"],
            section=meta["section"],
            authority=meta["authority"],
            text=text,
            distance=distance,
        )
        for chunk_id, text, meta, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]
