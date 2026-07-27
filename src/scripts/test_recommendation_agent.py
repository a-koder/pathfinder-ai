"""
Test the Recommendation Agent's GPT-4o-mini output for a set of student queries.

Usage (from project root, with .venv_win active):
    python src/scripts/test_recommendation_agent.py

What this script does:
    For each test query, runs RetrievalAgent.retrieve_relevant_context() followed
    by RecommendationAgent.generate_recommendations(), then prints the recommendation
    titles, summary, and follow-up question so output quality can be eyeballed.

This script is read-only: it does not modify production code, Pinecone data, or
the SQLite database.

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
from services.llm_service import LLMService
from services.prompt_service import PromptService
from agents.retrieval_agent import RetrievalAgent
from agents.recommendation_agent import RecommendationAgent


QUERIES = [
    "I like math and video games. What careers might fit me?",
    "I like fashion, creativity, and business.",
    "I enjoy helping people and healthcare.",
    "I like building things with my hands.",
    "I enjoy travel, cultures, and languages.",
]

_EMPTY_PROFILE = {
    "name": "Student",
    "grade_level": "",
    "gpa": "",
    "interests": [],
    "strengths": [],
    "dislikes": [],
}


def run(retrieval_agent: RetrievalAgent, recommendation_agent: RecommendationAgent) -> None:
    for query in QUERIES:
        print(f"\nQuery: \"{query}\"")
        print("=" * (len(query) + 8))

        retrieval = retrieval_agent.retrieve_relevant_context(
            user_message=query,
            profile=_EMPTY_PROFILE,
            top_k=5,
        )
        print(f"Retrieved {len(retrieval['retrieved_documents'])} documents "
              f"(confidence {retrieval['retrieval_confidence']:.4f})")

        recommendations = recommendation_agent.generate_recommendations(
            user_message=query,
            profile=_EMPTY_PROFILE,
            retrieved_context=retrieval,
        )

        items = recommendations.get("recommendations", [])
        print(f"\nRecommendation titles ({len(items)}):")
        if items:
            for i, item in enumerate(items, start=1):
                print(f"  {i}. {item.get('title', '')}  [{item.get('type', '')}]  "
                      f"confidence={item.get('confidence', 0.0):.2f}")
        else:
            print("  (none — fallback path was used)")

        print(f"\nSummary: {recommendations.get('summary', '')}")
        print(f"Follow-up question: {recommendations.get('follow_up_question', '')}")


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    openai_client = OpenAIClient()
    pinecone_client = PineconeClient()
    knowledge_loader = KnowledgeLoader()
    embedding_service = EmbeddingService(openai_client)
    retrieval_service = RetrievalService(embedding_service, pinecone_client, knowledge_loader)
    llm_service = LLMService(openai_client)
    prompt_service = PromptService()

    retrieval_agent = RetrievalAgent(retrieval_service)
    recommendation_agent = RecommendationAgent(llm_service, prompt_service)

    run(retrieval_agent, recommendation_agent)
