import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


class KnowledgeLoader:
    """Loads and parses JSON knowledge base files from data/."""

    def load_careers(self) -> list[dict]:
        return self._load("careers.json")

    def load_majors(self) -> list[dict]:
        return self._load("majors.json")

    def load_colleges(self) -> list[dict]:
        return self._load("colleges.json")

    def load_interests(self) -> list[dict]:
        return self._load("interests.json")

    def search_by_tags(self, tags: list[str], top_k: int = 5) -> list[dict]:
        """Tag-match fallback used when Pinecone is unavailable."""
        tag_set = {t.lower() for t in tags}
        scored: list[tuple[int, dict]] = []
        all_records = self.load_careers() + self.load_majors() + self.load_colleges()
        for record in all_records:
            record_tags = {
                t.lower()
                for t in record.get("interest_tags", [])
                + record.get("fit_tags", [])
                + record.get("strength_tags", [])
            }
            overlap = len(tag_set & record_tags)
            if overlap > 0:
                scored.append((overlap, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_k]]

    def _load(self, filename: str) -> list[dict]:
        path = _DATA_DIR / filename
        with open(path, encoding="utf-8") as f:
            return json.load(f)
