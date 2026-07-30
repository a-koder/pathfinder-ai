"""
Ingest PathFinder AI knowledge base into Pinecone.

Usage (from project root, with .venv_win active):
    python src/scripts/ingest_knowledge_base.py

What this script does:
    1. Loads careers.json, majors.json, colleges.json, interests.json from data/
    2. Converts each record to a rich searchable text string
    3. Calls OpenAI text-embedding-3-small to generate a 1536-dim vector
    4. Upserts all vectors into the 'pathfinder-ai' Pinecone index
    5. Attaches doc_type, title, and tag metadata to each vector for filtered retrieval

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from infrastructure.openai_client import OpenAIClient
from infrastructure.pinecone_client import PineconeClient
from infrastructure.knowledge_loader import KnowledgeLoader
from services.embedding_service import EmbeddingService

_STATE_ABBREVIATIONS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC",
}


def _extract_state(location: str) -> str:
    """Derive a normalized 2-letter state code from a location string like 'Cambridge, MA'
    or 'Tempe, AZ (+ online)', for reliable Pinecone metadata filtering. Returns '' for
    nationwide/online-only entries with no single home state - callers should treat that
    as 'no state filter applies', not a data error."""
    if "D.C." in location:
        return "DC"
    match = re.search(r",\s*([A-Z]{2})\b", location)
    if match and match.group(1) in _STATE_ABBREVIATIONS:
        return match.group(1)
    return ""


# ---------------------------------------------------------------------------
# Text builders — convert each record type into embedding-friendly prose
# ---------------------------------------------------------------------------

def _career_to_text(c: dict) -> str:
    return "\n".join(filter(None, [
        f"Career: {c['title']}",
        f"Description: {c['description']}",
        f"Interest areas: {', '.join(c.get('interest_tags', []))}",
        f"Strengths needed: {', '.join(c.get('strength_tags', []))}",
        f"Related majors: {', '.join(c.get('related_majors', []))}",
        f"Skills: {', '.join(c.get('skills', []))}",
        f"Why exciting: {c.get('why_exciting', '')}",
        f"Opportunities: {'; '.join(c.get('opportunities', []))}",
        f"Real world impact: {c.get('real_world_impact', '')}",
        f"Adjacent careers: {', '.join(c.get('adjacent_paths', []))}",
    ]))


def _major_to_text(m: dict) -> str:
    return "\n".join(filter(None, [
        f"Major: {m['name']}",
        f"Description: {m['description']}",
        f"Related careers: {', '.join(m.get('related_careers', []))}",
        f"Skills built: {', '.join(m.get('skills_built', []))}",
        f"Recommended high school subjects: {', '.join(m.get('recommended_subjects', []))}",
        f"Degree types: {', '.join(m.get('typical_degree_types', []))}",
    ]))


def _college_to_text(c: dict) -> str:
    return "\n".join(filter(None, [
        f"College: {c['name']}",
        f"Location: {c['location']}",
        f"Type: {c['college_type']}",
        f"Sample programs: {', '.join(c.get('sample_programs', []))}",
        f"GPA band: {c['gpa_band']}",
        f"Pathway notes: {c.get('pathway_notes', '')}",
        f"Affordability: {c.get('affordability_notes', '')}",
        f"Fit tags: {', '.join(c.get('fit_tags', []))}",
    ]))


def _interest_to_text(i: dict) -> str:
    return "\n".join(filter(None, [
        f"Interest area: {i['label']}",
        f"Category: {i['category']}",
        f"Description: {i['description']}",
        f"Example activities: {', '.join(i.get('example_activities', []))}",
        f"Career directions: {', '.join(i.get('career_directions', []))}",
        f"Strength connections: {', '.join(i.get('strength_connections', []))}",
        f"Pathway note: {i.get('pathway_note', '')}",
    ]))


# ---------------------------------------------------------------------------
# Vector builders — attach Pinecone metadata to each embedded record
# ---------------------------------------------------------------------------

def _career_vector(c: dict, values: list[float]) -> dict:
    return {
        "id": c["id"],
        "values": values,
        "metadata": {
            "doc_type": "career",
            "title": c["title"],
            "interest_tags": c.get("interest_tags", []),
            "strength_tags": c.get("strength_tags", []),
            "related_majors": c.get("related_majors", []),
            "adjacent_paths": c.get("adjacent_paths", []),
            "source_file": "careers.json",
        },
    }


def _major_vector(m: dict, values: list[float]) -> dict:
    return {
        "id": m["id"],
        "values": values,
        "metadata": {
            "doc_type": "major",
            "title": m["name"],
            "related_careers": m.get("related_careers", []),
            "skills_built": m.get("skills_built", []),
            "source_file": "majors.json",
        },
    }


def _college_vector(c: dict, values: list[float]) -> dict:
    return {
        "id": c["id"],
        "values": values,
        "metadata": {
            "doc_type": "college",
            "title": c["name"],
            "gpa_band": c["gpa_band"],
            "college_type": c["college_type"],
            "location": c["location"],
            "state": _extract_state(c["location"]),
            "fit_tags": c.get("fit_tags", []),
            "source_file": "colleges.json",
        },
    }


def _interest_vector(i: dict, values: list[float]) -> dict:
    return {
        "id": i["id"],
        "values": values,
        "metadata": {
            "doc_type": "interest",
            "title": i["label"],
            "category": i["category"],
            "career_directions": i.get("career_directions", []),
            "source_file": "interests.json",
        },
    }


# ---------------------------------------------------------------------------
# Ingestion orchestration
# ---------------------------------------------------------------------------

def _display_name(record: dict) -> str:
    return record.get("title") or record.get("name") or record.get("label") or record["id"]


def ingest(
    embedding_svc: EmbeddingService,
    pinecone_client: PineconeClient,
    loader: KnowledgeLoader,
) -> None:
    pinecone_client.initialize_pinecone()
    print(f"Connected to Pinecone index '{config.PINECONE_INDEX_NAME}'.\n")

    batches = [
        (loader.load_careers(),   _career_to_text,   _career_vector,   "careers"),
        (loader.load_majors(),    _major_to_text,    _major_vector,    "majors"),
        (loader.load_colleges(),  _college_to_text,  _college_vector,  "colleges"),
        (loader.load_interests(), _interest_to_text, _interest_vector, "interests"),
    ]

    total = 0
    for records, to_text, to_vector, label in batches:
        print(f"[{label}] Embedding {len(records)} records...")
        vectors = []
        for record in records:
            text = to_text(record)
            embedding = embedding_svc.generate_embedding(text)
            vectors.append(to_vector(record, embedding))
            print(f"  + {_display_name(record)}")

        pinecone_client.upsert_vectors(vectors)
        print(f"  -> {len(vectors)} vectors upserted.\n")
        total += len(vectors)

    print(f"Ingestion complete: {total} vectors in index '{config.PINECONE_INDEX_NAME}' (namespace: default).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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

    ingest(embedding_svc, pinecone_client, loader)
