from collections import defaultdict
from typing import Any

import httpx
from django.conf import settings
from pgvector.django import CosineDistance

from api.models import LessonChunk

TEI_MAX_BATCH = 32
MIN_CHUNK_CHARS = 80
CANDIDATE_LIMIT = 8
RETRIEVE_K = 40
MAX_PER_SOURCE = 2
MAX_CHUNK_CHARS = 1200


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    url = f"{settings.TEI_URL.rstrip('/')}/embed"
    vectors: list[list[float]] = []

    for start in range(0, len(texts), TEI_MAX_BATCH):
        batch = texts[start : start + TEI_MAX_BATCH]
        response = httpx.post(
            url,
            json={"inputs": batch},
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()

        if data and isinstance(data[0], (int, float)):
            vectors.append(data)
        else:
            vectors.extend(data)

    return vectors


def _source_key(chunk: Any) -> str:
    reference_id = getattr(chunk, "reference_id", None)
    generated_id = getattr(chunk, "generated_id", None)
    if reference_id is not None:
        return f"reference:{reference_id}"
    if generated_id is not None:
        return f"generated:{generated_id}"
    return f"chunk:{getattr(chunk, 'id', id(chunk))}"


def diversify_style_chunks(
    chunks: list[Any],
    *,
    limit: int = CANDIDATE_LIMIT,
    max_per_source: int = MAX_PER_SOURCE,
    max_chars: int = MAX_CHUNK_CHARS,
) -> list[str]:
    seen_text: set[str] = set()
    per_source: dict[str, int] = defaultdict(int)
    selected: list[str] = []

    for chunk in chunks:
        content = (getattr(chunk, "content", None) or "").strip()
        if len(content) <= MIN_CHUNK_CHARS:
            continue
        if content in seen_text:
            continue
        source = _source_key(chunk)
        if per_source[source] >= max_per_source:
            continue
        seen_text.add(content)
        per_source[source] += 1
        if len(content) > max_chars:
            content = content[:max_chars].rstrip()
        selected.append(content)
        if len(selected) >= limit:
            break

    return selected


def find_style_chunks(query: str, *, k: int = RETRIEVE_K) -> list[str]:
    query = (query or "").strip()
    if not query:
        return []

    vectors = embed_texts([query])
    if not vectors:
        return []

    chunks = list(
        LessonChunk.objects.filter(is_active=True)
        .order_by(CosineDistance("embedding", vectors[0]))[:k]
    )
    return diversify_style_chunks(chunks)
