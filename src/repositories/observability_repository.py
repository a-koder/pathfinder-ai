import json

from infrastructure.sqlite_client import SQLiteClient


class ObservabilityRepository:
    """All SQL for the observability_logs table."""

    def __init__(self, client: SQLiteClient):
        self._db = client

    def save_log(self, event: dict) -> int:
        """Insert one observability log row. Returns the new row's log_id."""
        return self._db.insert(
            """
            INSERT INTO observability_logs (
                student_id, timestamp, agent, model, evaluation_model, embedding_model,
                prompt_tokens, completion_tokens, estimated_cost_usd, latency_ms,
                retrieved_doc_count, guardrail_flags, eval_score, error,
                student_name, user_message, guardrail_risk_level, quality_badge,
                evaluation_scores, prompt_versions, input_guardrail_flags, revision_attempted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("student_id"),
                event.get("timestamp", ""),
                event.get("agent", "Orchestrator"),
                event.get("model", ""),
                event.get("evaluation_model", ""),
                event.get("embedding_model", ""),
                event.get("prompt_tokens", 0),
                event.get("completion_tokens", 0),
                event.get("estimated_cost", 0.0),
                event.get("latency_ms", 0),
                event.get("retrieved_document_count", 0),
                json.dumps(event.get("guardrail_flags", []) or []),
                event.get("evaluation_score", 0),
                event.get("error", ""),
                event.get("student_name", ""),
                event.get("user_message", ""),
                event.get("guardrail_risk_level", ""),
                event.get("quality_badge", ""),
                json.dumps(event.get("evaluation_scores", {}) or {}),
                json.dumps(event.get("prompt_versions", {}) or {}),
                json.dumps(event.get("input_guardrail_flags", []) or []),
                1 if event.get("revision_attempted") else 0,
            ),
        )

    def get_recent_logs(self, limit: int = 20) -> list[dict]:
        """Return the most recent log rows across all students, newest first."""
        rows = self._db.execute(
            "SELECT * FROM observability_logs ORDER BY log_id DESC LIMIT ?",
            (limit,),
        )
        return [self._parse_row(row) for row in rows]

    def get_logs_for_student(self, student_id: int, limit: int = 20) -> list[dict]:
        """Return the most recent log rows for one student, newest first."""
        rows = self._db.execute(
            "SELECT * FROM observability_logs WHERE student_id = ? ORDER BY log_id DESC LIMIT ?",
            (student_id, limit),
        )
        return [self._parse_row(row) for row in rows]

    def save_feedback(self, log_id: int, helpful: bool, feedback_text: str | None = None) -> None:
        """
        Record human-in-the-loop feedback (helpful / not helpful, plus optional free text)
        against one observability log row. Overwrites any prior feedback on that row.
        """
        self._db.execute(
            "UPDATE observability_logs SET helpful = ?, feedback_text = ? WHERE log_id = ?",
            (1 if helpful else 0, feedback_text, log_id),
        )

    def get_feedback_summary(self) -> dict:
        """Aggregate helpful / not-helpful counts across every log row that has received feedback."""
        rows = self._db.execute(
            "SELECT helpful, COUNT(*) AS count FROM observability_logs "
            "WHERE helpful IS NOT NULL GROUP BY helpful"
        )
        helpful_count = 0
        not_helpful_count = 0
        for row in rows:
            if row["helpful"] == 1:
                helpful_count = row["count"]
            elif row["helpful"] == 0:
                not_helpful_count = row["count"]

        total = helpful_count + not_helpful_count
        return {
            "total_feedback": total,
            "helpful_count": helpful_count,
            "not_helpful_count": not_helpful_count,
            "helpful_rate": (helpful_count / total) if total else None,
        }

    def _parse_row(self, row: dict) -> dict:
        parsed = dict(row)
        try:
            parsed["guardrail_flags"] = json.loads(parsed.get("guardrail_flags") or "[]")
        except (TypeError, ValueError):
            parsed["guardrail_flags"] = []
        try:
            parsed["evaluation_scores"] = json.loads(parsed.get("evaluation_scores") or "{}")
        except (TypeError, ValueError):
            parsed["evaluation_scores"] = {}
        try:
            parsed["prompt_versions"] = json.loads(parsed.get("prompt_versions") or "{}")
        except (TypeError, ValueError):
            parsed["prompt_versions"] = {}
        try:
            parsed["input_guardrail_flags"] = json.loads(parsed.get("input_guardrail_flags") or "[]")
        except (TypeError, ValueError):
            parsed["input_guardrail_flags"] = []

        helpful = parsed.get("helpful")
        parsed["helpful"] = bool(helpful) if helpful is not None else None
        parsed["revision_attempted"] = bool(parsed.get("revision_attempted"))
        return parsed
