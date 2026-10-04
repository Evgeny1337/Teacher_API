import httpx
from django.conf import settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = httpx.post(
        f"{settings.TEI_URL.rstrip('/')}/embed",
        json={"inputs": texts},
        timeout=60.0,
    )
    response.raise_for_status()
    data = response.json()

    if data and isinstance(data[0], (int, float)):
        return [data]
    return data
