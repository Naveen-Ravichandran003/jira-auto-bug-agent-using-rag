"""
Pydantic models for input/output validation.
Implements the schemas defined in gemini.md (Project Constitution).
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


# ─── Enums ───────────────────────────────────────────────────

class EvidenceType(str, Enum):
    SCREENSHOT = "screenshot"
    PDF = "pdf"
    JIRA_TICKET = "jira_ticket"
    DOCUMENT = "document"
    TEXT_DESCRIPTION = "text_description"


class GenerationStatus(str, Enum):
    SUCCESS = "success"
    INSUFFICIENT_DATA = "insufficient_data"
    LOW_CONFIDENCE = "low_confidence"
    FAILED = "failed"


class PriorityLevel(str, Enum):
    HIGHEST = "Highest"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LOWEST = "Lowest"


INSUFFICIENT_EVIDENCE_MSG = "Insufficient evidence provided to generate this section."


# ─── Input Schemas ───────────────────────────────────────────

class JiraCredentials(BaseModel):
    """User's Jira connection credentials."""
    base_url: str = Field(..., description="Jira Cloud instance URL")
    email: str = Field(..., description="Atlassian account email")
    api_token: str = Field(..., description="Atlassian API token")
    project_key: str = Field(..., description="Jira project key (e.g., PROJ)")
    board_name: Optional[str] = Field(None, description="Target board name")
    groq_api_key: Optional[str] = Field(None, description="Required Groq API key")


class Evidence(BaseModel):
    """Evidence provided by the user for bug generation."""
    type: EvidenceType = Field(..., description="Type of evidence")
    file_path: Optional[str] = Field(None, description="Path to uploaded file")
    jira_ticket_key: Optional[str] = Field(None, description="Existing Jira ticket key")
    text_description: Optional[str] = Field(None, description="Free-text description")


class BugGenerationRules(BaseModel):
    """Rules controlling the bug generation behavior."""
    strict_mode: bool = Field(default=True, description="Enforce anti-hallucination")
    anti_hallucination: bool = Field(default=True, description="Evidence-only generation")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    allow_manual_edit: bool = Field(default=True)
    use_rag: bool = Field(default=False, description="Use RAG (embedding/retrieval) vs Direct LLM")
    use_ai: bool = Field(default=True, description="Whether to use OpenAI at all")
    llm_model: str = Field(default="llama-3.3-70b-versatile")
    custom_prompt: Optional[str] = Field(None, description="Additional custom system instructions")


class BugGenerationRequest(BaseModel):
    """Complete request payload for bug generation."""
    user_id: str = Field(..., description="Unique user identifier")
    jira_credentials: JiraCredentials
    evidence: Evidence
    bug_generation_rules: BugGenerationRules = Field(
        default_factory=BugGenerationRules
    )


# ─── Output Schemas ──────────────────────────────────────────

class JiraTicketPayload(BaseModel):
    """The generated bug ticket payload matching Jira schema."""
    summary: str = Field(..., description="Bug title/summary")
    description: str = Field(..., description="Detailed bug description")
    steps_to_reproduce: str = Field(
        default=INSUFFICIENT_EVIDENCE_MSG,
        description="Steps to reproduce the bug",
    )
    actual_result: str = Field(
        default=INSUFFICIENT_EVIDENCE_MSG,
        description="What actually happened",
    )
    expected_result: str = Field(
        default=INSUFFICIENT_EVIDENCE_MSG,
        description="What was expected",
    )
    priority: str = Field(
        default=INSUFFICIENT_EVIDENCE_MSG,
        description="Bug priority level",
    )
    labels: List[str] = Field(
        default_factory=lambda: ["auto-generated", "ai-agent"]
    )
    attachments: List[str] = Field(default_factory=list)


class FieldConfidence(BaseModel):
    """Per-field confidence scores."""
    summary: float = 0.0
    description: float = 0.0
    steps_to_reproduce: float = 0.0
    actual_result: float = 0.0
    expected_result: float = 0.0
    priority: float = 0.0


class BugGenerationResponse(BaseModel):
    """Complete response payload from bug generation."""
    jira_ticket_payload: JiraTicketPayload
    evidence_trace: List[str] = Field(
        default_factory=list, description="chunk_ids used"
    )
    confidence_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Overall confidence"
    )
    generation_status: GenerationStatus = Field(
        default=GenerationStatus.FAILED
    )
    field_confidence: FieldConfidence = Field(default_factory=FieldConfidence)
    warnings: List[str] = Field(default_factory=list)
    evidence_file_path: Optional[str] = Field(None, description="Path to the evidence file for attachment")
    jira_issue_key: Optional[str] = Field(
        None, description="Created Jira issue key"
    )
    jira_issue_url: Optional[str] = Field(
        None, description="URL to the created Jira issue"
    )


# ─── Internal Models ─────────────────────────────────────────

class ChunkMetadata(BaseModel):
    """Metadata for a document chunk in the RAG pipeline."""
    chunk_id: str
    source_file: str
    source_type: str
    user_id: str
    timestamp: str
    chunk_index: int
    page_number: Optional[int] = None


class RetrievedChunk(BaseModel):
    """A chunk retrieved from the vector store with similarity score."""
    content: str
    metadata: ChunkMetadata
    similarity_score: float


class ConnectionTestResult(BaseModel):
    """Result of a Jira connection test."""
    success: bool
    message: str
    user_display_name: Optional[str] = None
    projects: Optional[List[dict]] = None
