from openai import OpenAI

from app.core.settings import (
    EMBEDDING_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
)


client = OpenAI(
    api_key=EMBEDDING_API_KEY,
    base_url=EMBEDDING_BASE_URL,
)

def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    batch_size = 10
    all_embeddings = []

    for start in range(0, len(texts), batch_size):
        batch = texts[
            start:start + batch_size
        ]

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
            dimensions=EMBEDDING_DIMENSIONS,
            encoding_format="float",
        )

        batch_embeddings = [
            item.embedding
            for item in response.data
        ]

        all_embeddings.extend(
            batch_embeddings
        )

    return all_embeddings