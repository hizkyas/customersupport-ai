from typing import Protocol, List

class EmbeddingProvider(Protocol):
    """Abstract interface for embedding providers — decoupled from any specific vendor."""
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of text strings.
        Returns a list of float vectors, one per input text.
        """
        ...


class OpenAIEmbeddingProvider:
    """OpenAI implementation of EmbeddingProvider."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def embed(self, texts: List[str]) -> List[List[float]]:
        import httpx
        if not texts:
            return []

        if self.api_key == "mock-key":
            # Return deterministic mock embeddings (1536-dim) for testing
            return [[0.1] * 1536 for _ in texts]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": texts}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/embeddings",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        # Sort by index to preserve input order
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]


def get_embedding_provider() -> EmbeddingProvider:
    """Factory to return the configured embedding provider."""
    from app.core.config import settings
    if settings.EMBEDDING_PROVIDER == "openai":
        return OpenAIEmbeddingProvider(
            api_key=settings.EMBEDDING_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
    raise ValueError(f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER}")
