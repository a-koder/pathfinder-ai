from services.retrieval_service import RetrievalService


def _normalize_document(result: dict) -> dict:
    """Normalize a Pinecone match or a tag-fallback record into a common shape."""
    if "metadata" in result:
        metadata = result.get("metadata", {})
        return {
            "doc_id": result.get("id", ""),
            "doc_type": metadata.get("doc_type", ""),
            "title": metadata.get("title", ""),
            "score": result.get("score", 0.0),
            "metadata": metadata,
        }
    # KnowledgeLoader.search_by_tags fallback shape: raw knowledge base record
    title = result.get("title") or result.get("name") or result.get("label") or ""
    return {
        "doc_id": result.get("id", ""),
        "doc_type": result.get("doc_type", ""),
        "title": title,
        "score": 0.0,
        "metadata": result,
    }


class RetrievalAgent:
    """
    Retrieves the top-k most relevant career, major, and college documents
    from Pinecone for the student's current message and profile.

    Service dependencies: RetrievalService
    """

    def __init__(self, retrieval_service: RetrievalService):
        self._retrieval_service = retrieval_service

    def retrieve_relevant_context(
        self,
        user_message: str,
        profile: dict,
        top_k: int = 5,
    ) -> dict:
        """Runs RetrievalService.search_all() and returns a RetrievalOutput-shaped dict."""
        results = self._retrieval_service.search_all(user_message, top_k=top_k)
        retrieved_documents = [_normalize_document(r) for r in results]

        scores = [d["score"] for d in retrieved_documents]
        retrieval_confidence = sum(scores) / len(scores) if scores else 0.0

        return {
            "query": user_message,
            "retrieved_documents": retrieved_documents,
            "retrieval_confidence": retrieval_confidence,
        }
