import httpx
from django.conf import settings
from pgvector.django import CosineDistance

from api.models import LessonChunk

TEI_MAX_BATCH = 32
MIN_CHUNK_CHARS = 80
CANDIDATE_LIMIT = 8


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


def find_style_chunks(query: str, *, k: int = 20) -> list[str]:
    query = (query or "").strip()
    if not query:
        return []

    vectors = embed_texts([query])
    if not vectors:
        return []

    chunks = (
        LessonChunk.objects.filter(is_active=True)
        .order_by(CosineDistance("embedding", vectors[0]))[:k]
    )
    filtered = [c for c in chunks if len(c.content or "") > MIN_CHUNK_CHARS]
    filtered_chunks = []
    chunks_content = set()
    for chunk in filtered:
        chunk_content = (chunk.content or "").strip()
        if chunk_content not in chunks_content:
            chunks_content.add(chunk_content)
            filtered_chunks.append(chunk)
    return [c.content for c in filtered_chunks[:CANDIDATE_LIMIT] if c.content]
