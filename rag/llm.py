"""Thin LiteLLM wrappers so the provider/model is swappable via config."""

from __future__ import annotations

import logging

import litellm

# Keep CLI output readable; LiteLLM warns on every Gemini 3 call that `temperature` is deprecated.
logging.getLogger("LiteLLM").setLevel(logging.ERROR)

EMBED_BATCH_SIZE = 50
# Gemini returns transient 503s under load. Without retries a single one kills a whole evaluation
# run partway through, losing every answer generated so far.
NUM_RETRIES = 4


def embed(texts: list[str], model: str) -> list[list[float]]:
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        response = litellm.embedding(
            model=model, input=texts[i : i + EMBED_BATCH_SIZE], num_retries=NUM_RETRIES
        )
        vectors.extend(item["embedding"] for item in response.data)
    return vectors


def complete_json(messages: list[dict], model: str, temperature: float) -> str:
    response = litellm.completion(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
        num_retries=NUM_RETRIES,
    )
    return response.choices[0].message.content or ""
