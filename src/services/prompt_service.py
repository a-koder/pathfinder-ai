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


class PromptService:
    """Builds context text from student profile, retrieved documents, and history."""

    def build(
        self,
        profile: dict,
        retrieved_docs: list[dict],
        history: list[dict],
    ) -> str:
        """Assemble a context block for grounding an LLM prompt."""
        sections = []

        profile_block = self._format_profile(profile)
        sections.append(f"Student profile:\n{profile_block if profile_block else '(no profile information yet)'}")

        docs_block = self._format_documents(retrieved_docs)
        sections.append(f"Retrieved knowledge base context:\n{docs_block if docs_block else '(no documents retrieved)'}")

        history_block = self._format_history(history)
        if history_block:
            sections.append(f"Recent conversation:\n{history_block}")

        return "\n\n".join(sections)

    def _format_profile(self, profile: dict) -> str:
        if not profile:
            return ""
        lines = []
        if profile.get("name"):
            lines.append(f"- Name: {profile['name']}")
        if profile.get("grade_level"):
            lines.append(f"- Grade level: {profile['grade_level']}")
        if profile.get("gpa"):
            lines.append(f"- GPA: {profile['gpa']}")
        if profile.get("interests"):
            lines.append(f"- Interests: {', '.join(profile['interests'])}")
        if profile.get("strengths"):
            lines.append(f"- Strengths: {', '.join(profile['strengths'])}")
        if profile.get("dislikes"):
            lines.append(f"- Dislikes: {', '.join(profile['dislikes'])}")
        return "\n".join(lines)

    def _format_documents(self, retrieved_docs: list[dict]) -> str:
        if not retrieved_docs:
            return ""
        lines = []
        for doc in retrieved_docs:
            title = doc.get("title", "Untitled")
            doc_type = doc.get("doc_type", "unknown")
            score = doc.get("score", 0.0)
            metadata = doc.get("metadata", {}) or {}

            tag_bits = []
            for key in _TAG_FIELDS:
                values = metadata.get(key)
                if values:
                    tag_bits.append(f"{key}: {', '.join(values[:5])}")
            tag_str = f" ({'; '.join(tag_bits)})" if tag_bits else ""

            lines.append(f"- [{doc_type}] {title} (relevance {score:.2f}){tag_str}")
        return "\n".join(lines)

    def _format_history(self, history: list[dict]) -> str:
        if not history:
            return ""
        lines = [f"- {msg.get('role', 'user')}: {msg.get('content', '')}" for msg in history[-6:]]
        return "\n".join(lines)
