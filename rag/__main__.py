"""CLI entry point.

    uv run python -m rag chunks              # inspect chunking (no API calls)
    uv run python -m rag index               # chunk, embed and (re)build the Chroma index
    uv run python -m rag ask "question" [-k 5] [--json] [--full]
    uv run python -m rag [chat] [--full]     # interactive loop (default); --full shows whole passages
"""

from __future__ import annotations

import argparse
import json
import select
import sys
import textwrap

from rag.chunking import load_chunks
from rag.config import GREETING, get_settings
from rag.pipeline import RagPipeline, RagResult


def print_result(result: RagResult, full: bool = False, snippet_chars: int = 300) -> None:
    print(f"\nAnswer:\n{textwrap.fill(result.display_answer(), 100)}\n")
    print(f"Support status: {result.support_status}")
    print("Citations:" + ("" if result.citations else " -"))
    for line in result.cited_sources():
        print(f"  {line}")
    if result.missing_information:
        print(f"Missing information: {result.missing_information}")
    for w in result.warnings:
        print(f"WARNING: {w}")
    print("\nRetrieved passages:")
    for c in result.retrieved:
        marker = "*" if c.chunk_id in result.citations else " "
        print(f" {marker} [{c.chunk_id}] {c.source} :: {c.section} (distance={c.distance:.3f})")
        if full:
            print(textwrap.indent(c.text, "      "))
            continue
        snippet = " ".join(c.text.split())
        if len(snippet) > snippet_chars:
            snippet = snippet[:snippet_chars] + " ..."
        print(textwrap.indent(textwrap.fill(snippet, 96), "      "))
    print()


def read_question(prompt: str = "\nQ> ") -> str:
    """Read one question, joining the extra lines a multi-line paste delivers in one go.

    A pasted question arrives as several lines at once, and `input()` takes only the first: the rest
    would then run as a second question, costing an API call and confusing the answer. Anything still
    waiting on stdin immediately after the first line came from the same paste, not from a person
    typing, so it belongs to the same question.
    """
    parts = [input(prompt).strip()]
    while select.select([sys.stdin], [], [], 0)[0]:
        line = sys.stdin.readline()
        if not line:
            break
        parts.append(line.strip())
    return " ".join(part for part in parts if part)


def chat_loop(pipeline: RagPipeline, model: str, k: int | None, full: bool) -> int:
    print(f"RAG chat ({model})\n")
    print(textwrap.fill(GREETING, 96).replace("\n ", "\n"))
    print("\nType 'exit', an empty line or Ctrl-C to quit.")
    while True:
        try:
            question = read_question()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"", "exit", "quit"}:
            break
        try:
            print_result(pipeline.ask(question, k=k), full=full)
        except KeyboardInterrupt:
            print("\n(cancelled)")
        except Exception as exc:  # keep the session alive on API/network errors
            print(f"ERROR: {exc}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag", description="Lightweight grounded RAG over the PDPC pack.")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("chunks", help="Print chunk IDs, sections and sizes.")
    sub.add_parser("index", help="Chunk, embed and rebuild the vector index.")
    ask = sub.add_parser("ask", help="Answer a single question.")
    ask.add_argument("question")
    ask.add_argument("-k", type=int, default=None, help="Number of passages to retrieve.")
    ask.add_argument("--json", action="store_true", help="Print the full result as JSON.")
    ask.add_argument("--full", action="store_true", help="Show whole retrieved passages.")
    chat = sub.add_parser("chat", help="Interactive question loop.")
    chat.add_argument("-k", type=int, default=None)
    chat.add_argument("--full", action="store_true", help="Show whole retrieved passages.")
    args = parser.parse_args(argv)
    if args.command is None:
        args.command, args.k, args.full = "chat", None, False

    settings = get_settings()

    if args.command == "chunks":
        for c in load_chunks(settings.docs_dir, settings.max_chunk_words):
            print(f"{c.chunk_id:<10} {len(c.text.split()):>4}w  {c.source} :: {c.section}")
        return 0

    pipeline = RagPipeline(settings)

    if args.command == "index":
        n = pipeline.build_index()
        print(f"Indexed {n} chunks into {settings.chroma_dir} (collection={settings.collection}, "
              f"embed_model={settings.embed_model}).")
        return 0

    if args.command == "ask":
        result = pipeline.ask(args.question, k=args.k)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            print_result(result, full=args.full)
        return 0

    return chat_loop(pipeline, settings.llm_model, args.k, args.full)


if __name__ == "__main__":
    sys.exit(main())
