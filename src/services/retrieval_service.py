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
        state: str | None = None,
        usage: UsageTracker | None = None,
    ) -> list[dict]:
        """Return top-k college documents, optionally pre-filtered by gpa_band and/or a
        normalized state code (e.g. "CA", set at ingestion time from each college's
        location). Falls back to backfilling with an unfiltered college search if the
        state filter returns fewer than top_k results - the curated catalog is only 45
        colleges, so an exact state match can reasonably come up short even when the
        student's stated preference is perfectly valid."""
        f: dict = {"doc_type": {"$eq": "college"}}
        if gpa_band in ("likely", "target", "reach"):
            f["gpa_band"] = {"$eq": gpa_band}
        if state:
            f["state"] = {"$eq": state}
        results = self._search(query, top_k, filter=f, usage=usage)

        if state and len(results) < top_k:
            fallback_filter: dict = {"doc_type": {"$eq": "college"}}
            if gpa_band in ("likely", "target", "reach"):
                fallback_filter["gpa_band"] = {"$eq": gpa_band}
            seen_ids = {r.get("id") for r in results}
            for candidate in self._search(query, top_k, filter=fallback_filter, usage=usage):
                if len(results) >= top_k:
                    break
                if candidate.get("id") not in seen_ids:
                    results.append(candidate)
                    seen_ids.add(candidate.get("id"))

        return results

    def search_non_colleges(self, query: str, top_k: int = 5, usage: UsageTracker | None = None) -> list[dict]:
        """Return top-k career/major/interest documents (everything except colleges)."""
        return self._search(query, top_k, filter={"doc_type": {"$ne": "college"}}, usage=usage)

    def search_all(self, query: str, top_k: int = 10, usage: UsageTracker | None = None) -> list[dict]:
        """Return top-k documents across all doc types (no filter). Used by the manual
        retrieval-quality test script (src/scripts/test_retrieval.py) - the live agent
        pipeline uses search_non_colleges()/search_colleges() instead so college results
        can be state/gpa_band-aware."""
        return self._search(query, top_k, filter=None, usage=usage)

    def _search(self, query: str, top_k: int, filter: dict | None, usage: UsageTracker | None = None) -> list[dict]:
        try:
            vector = self._embeddings.generate_embedding(query, usage=usage)
            return self._pinecone.query_vectors(vector, top_k=top_k, filter=filter)
        except Exception:
            return self._loader.search_by_tags(query.split(), top_k)
