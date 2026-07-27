from pydantic import BaseModel, Field
from typing import Optional


class StudentProfile(BaseModel):
    student_id: Optional[int] = None
    name: str = ""
    grade_level: str = ""
    gpa: str = ""
    interests: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    favorite_careers: list[str] = Field(default_factory=list)
    preferred_majors: list[str] = Field(default_factory=list)
    college_preferences: list[str] = Field(default_factory=list)
    prior_recommendations: list[str] = Field(default_factory=list)
    conversation_summary: str = ""
    # Optional preference fields. Never required - guardrails treat absence as "unknown",
    # not an error, and fall back to broad, hedged guidance instead of guessing.
    location_preference: str = ""
    budget_preference: str = ""
    college_type_preference: str = ""
    pathway_preference: str = ""


class RetrievedDocument(BaseModel):
    doc_id: str = ""
    doc_type: str = ""  # "career", "major", or "college"
    title: str = ""
    content: str = ""
    score: float = 0.0
    metadata: dict = Field(default_factory=dict)


class DiscoveryOutput(BaseModel):
    student_name: str = ""
    student_profile_updates: dict = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    next_question: str = ""
    confidence: float = 0.0


class RetrievalOutput(BaseModel):
    query_used: str = ""
    retrieved_documents: list[RetrievedDocument] = Field(default_factory=list)
    retrieval_method: str = "pinecone"  # "pinecone", "local_fallback", "tag_fallback"
    retrieval_confidence: float = 0.0


class RecommendationItem(BaseModel):
    title: str = ""
    doc_type: str = ""  # "career", "major", "college"
    why_it_fits: str = ""
    next_steps: list[str] = Field(default_factory=list)
    tier: str = ""  # for colleges: "reach", "target", "likely"


class RecommendationOutput(BaseModel):
    summary: str = ""
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    follow_up_question: str = ""


class PathPlanningOutput(BaseModel):
    short_term_steps: list[str] = Field(default_factory=list)
    medium_term_steps: list[str] = Field(default_factory=list)
    long_term_steps: list[str] = Field(default_factory=list)
    target_majors: list[str] = Field(default_factory=list)
    target_careers: list[str] = Field(default_factory=list)


class GuardrailResult(BaseModel):
    passed: bool = True
    flags: list[str] = Field(default_factory=list)
    risk_level: str = "low"  # "low", "medium", "high"
    required_revisions: list[str] = Field(default_factory=list)


class EvaluationScores(BaseModel):
    relevance: int = 0
    groundedness: int = 0
    personalization: int = 0
    actionability: int = 0
    safety: int = 0
    clarity: int = 0


class EvaluationResult(BaseModel):
    scores: EvaluationScores = Field(default_factory=EvaluationScores)
    total_score: int = 0
    max_score: int = 30
    passed: bool = False
    quality_badge: str = "not_evaluated"  # "green", "amber", "red", "not_evaluated"
    notes: str = ""


class ObservabilityLog(BaseModel):
    student_name: str = ""
    session_number: int = 0
    user_message_length: int = 0
    response_length: int = 0
    model: str = ""
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0
    retrieved_doc_count: int = 0
    retrieval_method: str = ""
    guardrail_flags: list[str] = Field(default_factory=list)
    evaluation_score: int = 0
    quality_badge: str = "not_evaluated"
    errors: list[str] = Field(default_factory=list)
    fallbacks_used: list[str] = Field(default_factory=list)
    timestamp: str = ""


class OrchestratorTurnResult(BaseModel):
    student_name: str = ""
    response: str = ""
    quality_badge: str = "not_evaluated"
    guardrail_flags: list[str] = Field(default_factory=list)
    evaluation_score: int = 0
    retrieved_document_count: int = 0
