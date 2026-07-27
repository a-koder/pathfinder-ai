"""
Test structured student profile extraction and persistence.

Usage (from project root, with .venv_win active):
    python src/scripts/test_profile_extraction.py

What this script does:
    Sends a sequence of messages, in order, from one test student through
    DiscoveryAgent.extract_profile_updates() and MemoryAgent.update_profile(),
    printing the merged profile after each message so accumulation across
    turns can be verified.

This script writes to the local SQLite database (data/memory.db) under a
dedicated test student name, but does not touch Pinecone or production code.

Prerequisites:
    OPENAI_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from infrastructure.sqlite_client import SQLiteClient
from infrastructure.openai_client import OpenAIClient
from repositories.student_repository import StudentRepository
from repositories.profile_repository import ProfileRepository
from repositories.message_repository import MessageRepository
from repositories.conversation_summary_repository import ConversationSummaryRepository
from services.llm_service import LLMService
from agents.discovery_agent import DiscoveryAgent
from agents.memory_agent import MemoryAgent


TEST_STUDENT = "TestProfileStudent"

MESSAGES = [
    "I like math and video games.",
    "I am in 11th grade and my GPA is 3.4.",
    "I like fashion, business, and being creative.",
    "My parents want me to do engineering but I am not sure.",
    "I enjoy helping people and healthcare.",
]


def run(discovery_agent: DiscoveryAgent, memory_agent: MemoryAgent) -> None:
    for i, message in enumerate(MESSAGES, start=1):
        print(f"\nMessage {i}: \"{message}\"")
        print("-" * (len(message) + 12))

        memory = memory_agent.load_memory(TEST_STUDENT)
        discovery = discovery_agent.extract_profile_updates(
            student_name=TEST_STUDENT,
            user_message=message,
            existing_profile=memory["profile"],
        )
        print(f"Confidence: {discovery['confidence']:.2f}")
        print(f"Missing information: {discovery['missing_information']}")
        print(f"Next question: {discovery['next_question']}")

        profile = memory_agent.update_profile(
            student_name=TEST_STUDENT,
            profile_updates=discovery["student_profile_updates"],
        )
        print(f"\nProfile after this message: {profile}")

    print("\n" + "=" * 70)
    final_profile = memory_agent.load_memory(TEST_STUDENT)["profile"]
    print(f"Final accumulated profile for '{TEST_STUDENT}':")
    print(final_profile)
    print("=" * 70)


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    sqlite_client = SQLiteClient()
    sqlite_client.create_tables()

    student_repo = StudentRepository(sqlite_client)
    profile_repo = ProfileRepository(sqlite_client)
    message_repo = MessageRepository(sqlite_client)
    summary_repo = ConversationSummaryRepository(sqlite_client)

    openai_client = OpenAIClient()
    llm_service = LLMService(openai_client)

    discovery_agent = DiscoveryAgent(llm_service)
    memory_agent = MemoryAgent(student_repo, profile_repo, message_repo, summary_repo)

    run(discovery_agent, memory_agent)
