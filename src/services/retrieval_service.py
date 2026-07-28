from infrastructure.pinecone_client import PineconeClient
from infrastructure.knowledge_loader import KnowledgeLoader
from services.embedding_service import EmbeddingService
from services.usage_tracker import UsageTracker


class RetrievalService:
    """Semantic search via Pinecone with local JSON tag-match fallback."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        pinecone_client: PineconeClient,
        knowledge_loader: KnowledgeLoader,
    ):
        self._embeddings = embedding_service
        self._pinecone = pinecone_client
        self._loader = knowledge_loader

    def search_careers(self, query: str, top_k: int = 5, usage: UsageTracker | None = None) -> list[dict]:
        """Return top-k career documents semantically similar to query."""
        return self._search(query, top_k, filter={"doc_type": {"$eq": "career"}}, usage=usage)

    def search_majors(self, query: str, top_k: int = 5, usage: UsageTracker | None = None) -> list[dict]:
        """Return top-k major documents semantically similar to query."""
        return self._search(query, top_k, filter={"doc_type": {"$eq": "major"}}, usage=usage)

    def search_colleges(
        self,
        query: str,
        top_k: int = 5,
        gpa_band: str | None = None,
        usage: UsageTracker | None = None,
    ) -> list[dict]:
        """Return top-k college documents, optionally pre-filtered by gpa_band."""
        f: dict = {"doc_type": {"$eq": "college"}}
        if gpa_band in ("likely", "target", "reach"):
            f["gpa_band"] = {"$eq": gpa_band}
        return self._search(query, top_k, filter=f, usage=usage)

    def search_all(self, query: str, top_k: int = 10, usage: UsageTracker | None = None) -> list[dict]:
        """Return top-k documents across all doc types (no filter)."""
        return self._search(query, top_k, filter=None, usage=usage)

    def _search(self, query: str, top_k: int, filter: dict | None, usage: UsageTracker | None = None) -> list[dict]:
        try:
            vector = self._embeddings.generate_embedding(query, usage=usage)
            return self._pinecone.query_vectors(vector, top_k=top_k, filter=filter)
        except Exception:
            return self._loader.search_by_tags(query.split(), top_k)
