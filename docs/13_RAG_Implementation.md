# PathFinder AI — RAG Implementation

## Overview

PathFinder AI uses Retrieval-Augmented Generation (RAG) to ground career, major, and college recommendations in a curated, locally-controlled knowledge base. This document describes the knowledge base schema, how embeddings are generated, how Pinecone is structured, and how retrieval is performed at query time.

---

## Knowledge Base Field Schemas

Four datasets under `data/`, each loaded by `KnowledgeLoader` and embedded/indexed by `src/scripts/ingest_knowledge_base.py`.

### Careers — `data/careers.json` (73 entries)

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g. `career_ux_researcher`) |
| `title` | string | Career name |
| `description` | string | 2–3 sentence plain-language description |
| `interest_tags` | list[string] | Interests that make this career a good fit |
| `strength_tags` | list[string] | Academic or personal strengths that align |
| `related_majors` | list[string] | Majors that lead to this career |
| `skills` | list[string] | Core skills used in this role |
| `why_exciting` | string | What draws people to this work |
| `opportunities` | list[string] | Growth paths, industries, adjacent roles |
| `real_world_impact` | string | How this work affects people, companies, or communities |
| `adjacent_paths` | list[string] | Related careers a student can explore instead |

### Majors — `data/majors.json` (47 entries)

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g. `major_cognitive_science`) |
| `name` | string | Major name |
| `description` | string | What students study in this major |
| `related_careers` | list[string] | Careers this major leads to |
| `recommended_subjects` | list[string] | High school subjects that prepare students for this major |
| `skills_built` | list[string] | Skills developed through this program |
| `typical_degree_types` | list[string] | e.g. `["Bachelor's", "Master's"]` |

### Colleges — `data/colleges.json` (45 entries)

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g. `college_uc_san_diego`) |
| `name` | string | College name |
| `location` | string | City, State |
| `college_type` | string | e.g. "Public Research University", "Liberal Arts College" |
| `sample_programs` | list[string] | Notable programs relevant to common student profiles |
| `gpa_band` | string | Typical admitted GPA range or tier |
| `pathway_notes` | string | What type of student fits well |
| `affordability_notes` | string | General note on in-state tuition, financial aid reputation |
| `fit_tags` | list[string] | Student profile tags this college matches |

Not a JSON field, but derived from `location` at ingestion time and stored as Pinecone metadata: `state`, a normalized 2-letter code used for `search_colleges(state=...)` filtering (decision D033) — see Metadata Strategy below.

### Interests — `data/interests.json` (58 entries)

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier |
| `label` | string | Interest area name (e.g. "Sports & Fitness") |
| `category` | string | Broad grouping |
| `description` | string | What this interest area covers |
| `example_activities` | list[string] | Concrete activities a student might relate to |
| `career_directions` | list[string] | Careers this interest area points toward |
| `strength_connections` | list[string] | Strengths commonly associated with this interest |
| `pathway_note` | string | Brief framing note |

This dataset exists to bridge vague student language ("I don't know, I just like being creative") to concrete career/major directions before the student has named a specific interest the other three datasets would match directly.

**Quality note:** depth and coverage can be expanded over time — quality of data matters more than quantity for a curated prototype knowledge base.

---

## Embedding Flow

```
Record (dict from JSON)
  -> Text builder function (career_to_text / major_to_text / etc.)
  -> Rich prose string (multi-field, embedding-friendly)
  -> EmbeddingService.generate_embedding(text)
  -> OpenAIClient.embed(text, model)
  -> openai.embeddings.create(input=text, model="text-embedding-3-small")
  -> 1536-dimensional float vector
```

### Text Construction Strategy

Each JSON record is converted to a multi-field prose string before embedding. This ensures the vector captures the full semantic meaning of the record — not just its title.

**Career example:**
```
Career: Sports Analyst
Description: Collect, analyze, and interpret performance data...
Interest areas: sports_team, math, data_analytics, technology
Strengths needed: statistical thinking, sports knowledge, programming
Related majors: Sports Analytics, Statistics, Data Science
Skills: Python or R, SQL, sports metrics (WAR, PER, xG)...
Why exciting: You give coaches and GMs superpowers...
Opportunities: all major professional sports leagues...
Real world impact: Sports analysts at multiple NBA teams...
Adjacent careers: Data Scientist, Sports Broadcaster, General Manager
```

This approach means a query like *"I love sports and math — what careers exist?"* will match semantically even if none of those exact words appear in the title field.

### Embedding Model

| Property | Value |
|---|---|
| Model | `text-embedding-3-small` |
| Dimensions | 1536 |
| Similarity metric | Cosine |
| Cost | $0.02 / 1M tokens |

`text-embedding-3-small` was chosen over `text-embedding-ada-002` for better quality per token, and over `text-embedding-3-large` to control cost for a high-school guidance use case with modest query volumes.

---

## Pinecone Flow

### Ingestion (one-time, via `ingest_knowledge_base.py`)

```
PineconeClient.initialize_pinecone()
  -> create_index_if_needed()  (serverless, cosine, 1536 dim)
  -> connect to index

For each record batch (careers, majors, colleges, interests):
  -> build vector: {id, values, metadata}
  -> PineconeClient.upsert_vectors(vectors)
     -> batched in groups of 100
     -> upserted to namespace "default"
```

### Query (per student turn, via `RetrievalService`)

```
RetrievalService.search_careers(query)
  -> EmbeddingService.generate_embedding(query)
  -> PineconeClient.query_vectors(vector, top_k=5, filter={"doc_type": "career"})
  -> Pinecone returns [{id, score, metadata}]
  -> RetrievalAgent uses results to build recommendation context
```

### Index Configuration

| Property | Value |
|---|---|
| Index name | `pathfinder-ai` |
| Namespace | `default` |
| Dimension | 1536 |
| Metric | cosine |
| Cloud | AWS us-east-1 (serverless) |
| Total vectors | 223 (73 careers + 47 majors + 45 colleges + 58 interests) |

---

## Metadata Strategy

Every vector carries a `metadata` dict stored alongside its embedding in Pinecone. Metadata enables filtered retrieval — narrowing results to a specific `doc_type` or `gpa_band` without embedding separate namespaces for each.

### Metadata Schema by Document Type

**Career:**
```json
{
  "doc_type": "career",
  "title": "Sports Analyst",
  "interest_tags": ["sports_team", "math", "data_analytics"],
  "strength_tags": ["statistical thinking", "programming"],
  "related_majors": ["Data Science", "Statistics"],
  "adjacent_paths": ["Data Scientist", "General Manager"],
  "source_file": "careers.json"
}
```

**Major:**
```json
{
  "doc_type": "major",
  "title": "Data Science",
  "related_careers": ["Data Scientist", "Sports Analyst"],
  "skills_built": ["Python", "statistics", "machine learning"],
  "source_file": "majors.json"
}
```

**College:**
```json
{
  "doc_type": "college",
  "title": "Georgia Institute of Technology",
  "gpa_band": "target",
  "college_type": "Public Research University",
  "location": "Atlanta, GA",
  "state": "GA",
  "fit_tags": ["engineering powerhouse", "co-op programs", "great value"],
  "source_file": "colleges.json"
}
```

`state` is a normalized 2-letter code derived from `location` at ingestion time (`_extract_state()` in `ingest_knowledge_base.py`) — `location` itself is a free-text string ("Atlanta, GA", "Tempe, AZ (+ online)") not reliable for an exact-match Pinecone filter, so `state` exists specifically to make `search_colleges(state=...)` filtering work (decision D033 in `docs/12_DECISION_LOG.md`). Nationwide/online-only colleges (WGU, Lincoln Tech, the community college pathway entry) get `state: ""` — no single home state applies.

**Interest:**
```json
{
  "doc_type": "interest",
  "title": "Sports & Fitness",
  "category": "Sports & Fitness",
  "career_directions": ["Athletic Trainer", "Sports Coach", "Physical Therapist"],
  "source_file": "interests.json"
}
```

---

## Retrieval Strategy

### Per-Query Retrieval Flow

When the Retrieval Agent runs (`RetrievalAgent.retrieve_relevant_context()`):

1. Discovery Agent has already extracted the student's profile (interests, GPA, grade level, `location_preference`, `budget_preference`)
2. The raw student message (not a profile-blended query string) is embedded and searched twice: once against everything except colleges, once against colleges only
3. The college search is narrowed by a `state` filter derived from `location_preference` (see Filter Examples below) when one can be confidently inferred, with a fallback to an unfiltered college search if the state match returns too few candidates — the catalog is only 45 colleges, so an exact-match filter can reasonably come up short
4. A `budget_preference` signaling affordability doesn't filter — there's no real per-college cost data, only editorial notes — it instead soft-boosts public colleges above private ones of similar relevance in `RetrievalAgent._rank_colleges()`

### Filter Examples

```python
# Retrieve only career documents
filter = {"doc_type": {"$eq": "career"}}

# Retrieve only college documents for a student who wants to stay in Georgia
filter = {"doc_type": {"$eq": "college"}, "state": {"$eq": "GA"}}

# Retrieve everything except colleges (the live non-college search path)
filter = {"doc_type": {"$ne": "college"}}

# Retrieve all document types (used by the manual test_retrieval.py script only)
filter = None
```

### Retrieval Methods

| Method | Filter | Use Case |
|---|---|---|
| `search_careers(query)` | `doc_type = career` | Career exploration from interest/strength query |
| `search_majors(query)` | `doc_type = major` | Major guidance from career or interest query |
| `search_non_colleges(query)` | `doc_type != college` | Live path: careers/majors/interests in one blended call |
| `search_colleges(query, gpa_band, state)` | `doc_type = college` + optional `gpa_band`/`state` | Live path: college pathway guidance, location-aware, with fallback backfill |
| `search_all(query)` | None | Broad discovery — used only by the manual `test_retrieval.py` quality-check script, not the live agent path |

### Fallback Behavior

If Pinecone is unavailable (network error, quota exceeded, key missing), `RetrievalService._search()` falls back to `KnowledgeLoader.search_by_tags()` — a local in-memory tag intersection search across the JSON files. This ensures the system remains functional without Pinecone, at the cost of reduced semantic matching quality.

---

## Why One Namespace

The decision to use a single `"default"` namespace instead of separate namespaces per doc type was deliberate:

**Rationale:**
- Pinecone namespaces cannot be cross-queried in a single call. Using `career`, `major`, `college` as separate namespaces would require a separate API call per doc type for any broad query.
- A single namespace with `doc_type` metadata filtering is equivalent in isolation behavior but more flexible — a filtered search still costs exactly one call, whether the filter is `doc_type = career` or the more granular `doc_type = college AND state = GA` used by the live retrieval path today.
- Namespace proliferation becomes a maintenance burden if doc types expand (e.g., adding `interest` or future `activity` or `scholarship` types).
- Metadata filters apply efficiently on serverless Pinecone indexes with low vector counts.

**The metadata filter `{"doc_type": {"$eq": "career"}}` achieves the same isolation as a separate namespace — without the cross-query penalty.**

---

## Why Metadata Filtering Is Preferred Over Multiple Indexes

A separate Pinecone index per doc type (careers-index, majors-index, colleges-index) would also achieve isolation but introduces:

- **Higher cost:** Pinecone charges per index on many plans; multiple indexes consume more resources
- **Operational complexity:** Each index needs separate initialization, connection, and lifecycle management
- **No cross-type queries:** Searching across careers AND majors in one call is impossible with separate indexes
- **Fragile ingestion:** Adding a new knowledge base source (e.g., `interests.json`) requires creating and managing a new index

**Metadata filtering on one index with one namespace is simpler, cheaper, and more extensible.**

---

## Clean Architecture Compliance

The RAG layer follows the same layering rules as the rest of PathFinder AI:

| Layer | File | Rule |
|---|---|---|
| Infrastructure | `openai_client.py` | Only file that imports `openai` |
| Infrastructure | `pinecone_client.py` | Only file that imports `pinecone` |
| Infrastructure | `knowledge_loader.py` | Only file that reads JSON from disk |
| Service | `embedding_service.py` | Wraps OpenAIClient; never imports `openai` |
| Service | `retrieval_service.py` | Wraps EmbeddingService + PineconeClient; never imports either SDK |
| Application | `retrieval_agent.py` | Calls `RetrievalService` only; never calls Pinecone or OpenAI directly |

All dependencies are injected via constructor. The `ingest_knowledge_base.py` script wires infrastructure and services manually — the same pattern the Orchestrator uses at runtime.

---

## Running Ingestion

### Prerequisites

1. `.env` file at project root with:
   ```
   OPENAI_API_KEY=sk-...
   PINECONE_API_KEY=...
   PINECONE_INDEX_NAME=pathfinder-ai
   ```
2. Dependencies installed: `pip install openai pinecone python-dotenv`
3. Virtual environment active (`.venv_win` on Windows)

### Command

```bash
# From project root
python src/scripts/ingest_knowledge_base.py
```

### Expected Output

```
Connected to Pinecone index 'pathfinder-ai'.

[careers] Embedding 73 records...
  + Software Engineer
  + Data Scientist
  ...
  -> 73 vectors upserted.

[majors] Embedding 47 records...
  ...
  -> 47 vectors upserted.

[colleges] Embedding 45 records...
  ...
  -> 45 vectors upserted.

[interests] Embedding 58 records...
  ...
  -> 58 vectors upserted.

Ingestion complete: 223 vectors in index 'pathfinder-ai' (namespace: default).
```

### Re-ingestion

The script uses the record `id` field as the Pinecone vector ID. Re-running the script will upsert (overwrite) existing vectors — safe to run after updating JSON data files.

---

## Estimated Ingestion Cost

| Item | Tokens (approx) | Cost |
|---|---|---|
| 73 career texts (~300 tokens each) | ~21,900 | ~$0.0004 |
| 47 major texts (~150 tokens each) | ~7,050 | ~$0.0001 |
| 45 college texts (~250 tokens each) | ~11,250 | ~$0.0002 |
| 58 interest texts (~200 tokens each) | ~11,600 | ~$0.0002 |
| **Total** | **~51,800** | **~$0.0009** |

Full ingestion costs under $0.01 at current OpenAI embedding pricing. Re-ingestion after data updates is cheap enough to run freely.
