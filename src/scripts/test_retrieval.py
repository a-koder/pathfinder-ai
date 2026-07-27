"""
Test Pinecone retrieval quality for PathFinder AI.

Usage (from project root, with .venv_win active):
    python src/scripts/test_retrieval.py

What this script does:
    Runs a fixed set of student-style interest queries through
    RetrievalService.search_all() and prints the top 5 matches for each,
    so retrieval quality can be eyeballed manually.

This script is read-only: it does not modify any production code or data,
and does not write to Pinecone.

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from infrastructure.openai_client import OpenAIClient
from infrastructure.pinecone_client import PineconeClient
from infrastructure.knowledge_loader import KnowledgeLoader
from services.embedding_service import EmbeddingService
from services.retrieval_service import RetrievalService


QUERIES = [
    "I like sports and statistics",
    "I like fashion and creativity",
    "I enjoy helping people and healthcare",
    "I like building things with my hands",
    "I enjoy travel, cultures and languages",
    "I like gaming and storytelling",
    "I enjoy leadership and business",
]

_TAG_FIELDS = [
    "interest_tags",
    "strength_tags",
    "related_majors",
    "adjacent_paths",
    "related_careers",
    "skills_built",
    "fit_tags",
    "career_directions",
]


def _extract_tags(metadata: dict) -> list[str]:
    tags: list[str] = []
    for field in _TAG_FIELDS:
        tags.extend(metadata.get(field, []))
    return tags


def _print_result(rank: int, result: dict) -> None:
    if "metadata" in result:
        # Pinecone shape: {id, score, metadata}
        metadata = result["metadata"]
        title = metadata.get("title", "<no title>")
        doc_type = metadata.get("doc_type", "<no doc_type>")
        score = result.get("score")
        tags = _extract_tags(metadata)
    else:
        # KnowledgeLoader tag-match fallback shape: raw record dict
        title = result.get("title") or result.get("name") or result.get("label") or "<no title>"
        doc_type = "<fallback: no doc_type>"
        score = None
        tags = (
            result.get("interest_tags", [])
            + result.get("strength_tags", [])
            + result.get("fit_tags", [])
        )

    score_str = f"{score:.4f}" if isinstance(score, (int, float)) else "N/A"
    print(f"  {rank}. {title}")
    print(f"     doc_type: {doc_type}")
    print(f"     score:    {score_str}")
    print(f"     tags:     {', '.join(tags) if tags else '(none)'}")


def run(retrieval_service: RetrievalService) -> None:
    for query in QUERIES:
        print(f"\nQuery: \"{query}\"")
        print("-" * (len(query) + 8))
        results = retrieval_service.search_all(query, top_k=5)
        if not results:
            print("  (no results)")
            continue
        for i, result in enumerate(results, start=1):
            _print_result(i, result)

    print("\n" + "=" * 70)
    print("Manual review checklist:")
    print("  - For each query above, check whether the top results' doc_type")
    print("    and title are topically relevant to the query.")
    print("  - Flag any result whose title/tags have no clear connection to")
    print("    the query as a noisy result (e.g. an unrelated doc_type or")
    print("    a low score far below the rest of the top 5).")
    print("  - Compare scores within each query: a sharp drop-off after the")
    print("    first few results suggests the rest may be noise.")
    print("=" * 70)


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    openai_client = OpenAIClient()
    pinecone_client = PineconeClient()
    loader = KnowledgeLoader()
    embedding_svc = EmbeddingService(openai_client)
    retrieval_svc = RetrievalService(embedding_svc, pinecone_client, loader)

    run(retrieval_svc)
