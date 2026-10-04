import httpx
from django.conf import settings
from pgvector.django import CosineDistance

from api.models import LessonChunk

TEI_MAX_BATCH = 32


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


def find_style_chunks(query: str, *, k: int = 5) -> list[str]:
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
    return [chunk.content for chunk in chunks if chunk.content]
