"""Industrial Operations Copilot (owner: copilot). Read-only, tool-based, grounded, cited."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import ApiModel, Provenance


class CopilotMode(StrEnum):
    deterministic = "deterministic"  # no-API: intent router + templates grounded in DB
    llm = "llm"  # provider adapter (optional, LLM_PROVIDER)


class ChatRequest(ApiModel):
    message: str = Field(min_length=1, max_length=2000)
    copilot_session_id: str | None = Field(None, description="Continue a conversation (uuid)")
    lang: str = Field("th", pattern="^(th|en)$")


class ToolCall(ApiModel):
    tool: str
    arguments: dict
    allowed: bool
    status: str = Field(description="ok | denied | error | no_data")
    duration_ms: float | None = None
    result_summary: str | None = None


class Citation(ApiModel):
    kind: str = Field(description="document | data")
    ref: str = Field(description="kb chunk id ('kb:<doc>#<chunk>') or data ref ('tool:get_oer_trend')")
    title: str
    snippet: str | None = None
    url: str | None = Field(None, description="API path to open the source, e.g. /api/v1/copilot/sources/{ref}")
    # ---- additive (copilot) ----
    doc_id: str | None = Field(None, description="Sample document slug (document citations)")
    heading: str | None = Field(None, description="Section heading of the cited chunk")


class EvidenceFact(ApiModel):
    key: str
    label: str
    value: float
    unit: str = ""


class EvidenceItem(ApiModel):
    """One tool result the answer is grounded in (every number in the answer must match one of `facts`)."""

    tool: str
    arguments: dict
    status: str
    result_digest: str = Field(description="sha256 prefix of the tool's data payload")
    provenance: Provenance | None = None
    as_of: datetime | None = None
    facts: list[EvidenceFact] = []
    assumptions: list[str] = []
    limits: list[str] = []


class ChatResponse(ApiModel):
    copilot_session_id: str
    answer: str
    lang: str
    mode: CopilotMode
    intent: str | None
    tool_calls: list[ToolCall]
    citations: list[Citation]
    assumptions: list[str] = []
    uncertainty: str | None = Field(None, description="Explicit statement when data is missing or weak")
    refused: bool = False
    refusal_reason: str | None = None
    provenance: Provenance
    # ---- additive (copilot) ----
    evidence: list[EvidenceItem] = []
    suggested_followups: list[str] = []
    llm_answer_rejected: bool = False
    llm_rejection_reason: str | None = Field(None, description="grounding_failed | instruction_like_output | provider_error:* | tool_loop_limit | empty_reply")
    verification: dict | None = Field(None, description="Grounding verifier result: numbers checked/supported, unsupported numbers, causal flags")
    safety_flags: list[str] = Field(default_factory=list, description="injection | escalation | sql | control | untrusted_data_neutralised")
    limits: list[str] = []
    route: dict | None = Field(None, description="Router decision: method (rule|tfidf|followup|explicit_tool|none), confidence, slots")
    persisted: bool = Field(False, description="False when no X-Demo-Session was sent (conversation is not stored, ADR-006)")


class ToolSpec(ApiModel):
    name: str
    description: str
    parameters_schema: dict
    permission: str
    allowed_for_role: bool
    read_only: bool = True


class ToolListResponse(ApiModel):
    role: str
    mode: CopilotMode
    tools: list[ToolSpec]


class CopilotMessageOut(ApiModel):
    id: int
    sender: str
    content: str
    intent: str | None = None
    tool_calls: list[ToolCall] = []
    citations: list[Citation] = []
    created_at: datetime


class CopilotSessionOut(ApiModel):
    id: str
    title: str | None
    role: str
    mode: CopilotMode
    created_at: datetime
    message_count: int = 0


class CopilotSessionListResponse(ApiModel):
    items: list[CopilotSessionOut]


class CopilotSessionDetail(CopilotSessionOut):
    messages: list[CopilotMessageOut]


class SourceDocumentResponse(ApiModel):
    ref: str
    document_slug: str
    document_title: str
    heading: str | None
    text: str
    data_kind: str = "sample_document"
    notice: str = "Newly authored sample document for this demo - not a real company document."
