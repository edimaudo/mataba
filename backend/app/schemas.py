from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

ContractType = Literal[
    "Employment Agreement",
    "Job Offer",
    "Severance Agreement",
    "Service/Vendor Contract",
    "Lease",
    "General",
]
Language = Literal["en", "fr"]
SourceType = Literal["CONTRACT", "REFERENCE"]
HRTopic = Literal[
    "probation",
    "termination_notice",
    "severance",
    "non_compete",
    "non_solicit",
    "ip_assignment",
    "benefits",
]
HRTopicStatus = Literal[
    "FOUND",
    "NOT_FOUND_IN_SUBMITTED_DOCUMENTS",
    "REQUIRES_JURISDICTIONAL_REVIEW",
]


class SourcePageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceId: str = Field(min_length=1, max_length=180)
    documentName: str = Field(min_length=1, max_length=180)
    sourceType: SourceType
    pageNumber: int | None = Field(default=None, ge=1, le=100_000)
    sectionLabel: str | None = Field(default=None, max_length=180)
    text: str = Field(min_length=1, max_length=80_000)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contractType: ContractType
    language: Language
    contractPages: list[SourcePageInput] = Field(min_length=1, max_length=250)
    referencePages: list[SourcePageInput] = Field(default_factory=list, max_length=250)
    privacyConfirmed: bool

    @field_validator("privacyConfirmed")
    @classmethod
    def require_privacy_confirmation(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("The sanitized text must be reviewed before analysis.")
        return value


class FollowUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=2_000)
    language: Language
    pages: list[SourcePageInput] = Field(min_length=1, max_length=40)


class CitationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sourceId: str = Field(min_length=1, max_length=180)
    excerpt: str = Field(min_length=1, max_length=8_000)


class FindingDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(max_length=500)
    category: str = Field(max_length=120)
    explanation: str = Field(max_length=12_000)
    practicalEffect: str = Field(max_length=8_000)
    negotiationConsideration: str = Field(max_length=8_000)
    suggestedWording: str = Field(default="", max_length=8_000)
    citations: list[CitationDraft] = Field(default_factory=list, max_length=20)


class ObligationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=8_000)
    citations: list[CitationDraft] = Field(default_factory=list, max_length=20)


class HRTopicDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: HRTopic
    status: HRTopicStatus
    analysis: str = Field(default="", max_length=8_000)
    practicalConsiderations: str = Field(default="", max_length=8_000)
    citations: list[CitationDraft] = Field(default_factory=list, max_length=20)


class AnalysisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executiveSummary: str = Field(max_length=16_000)
    executiveSummaryCitations: list[CitationDraft] = Field(default_factory=list, max_length=30)
    findings: list[FindingDraft] = Field(default_factory=list, max_length=100)
    obligations: list[ObligationDraft] = Field(default_factory=list, max_length=100)
    terminationOverview: str = Field(max_length=16_000)
    terminationCitations: list[CitationDraft] = Field(default_factory=list, max_length=30)
    lawyerReport: str = Field(max_length=30_000)
    lawyerReportCitations: list[CitationDraft] = Field(default_factory=list, max_length=50)
    hrSections: list[HRTopicDraft] = Field(default_factory=list, max_length=7)


class FollowUpDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(max_length=16_000)
    citations: list[CitationDraft] = Field(default_factory=list, max_length=20)


class VerifyAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contractType: ContractType
    language: Language
    contractPages: list[SourcePageInput] = Field(min_length=1, max_length=250)
    referencePages: list[SourcePageInput] = Field(default_factory=list, max_length=250)
    draft: AnalysisDraft


class VerifyFollowUpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=2_000)
    language: Language
    pages: list[SourcePageInput] = Field(min_length=1, max_length=40)
    draft: FollowUpDraft


class CitationOutput(BaseModel):
    sourceId: str
    sourceType: SourceType
    documentName: str
    pageNumber: int | None
    sectionLabel: str | None = None
    verbatimExcerpt: str
    verified: Literal[True] = True


class FindingOutput(BaseModel):
    id: str
    title: str
    category: str
    explanation: str
    practicalEffect: str
    negotiationConsideration: str
    suggestedWording: str = ""
    citations: list[CitationOutput]


class ObligationOutput(BaseModel):
    text: str
    citations: list[CitationOutput]


class HRTopicOutput(BaseModel):
    topic: HRTopic
    status: HRTopicStatus
    analysis: str
    practicalConsiderations: str
    citations: list[CitationOutput]


class AnalysisOutput(BaseModel):
    executiveSummary: str
    executiveSummaryCitations: list[CitationOutput]
    findings: list[FindingOutput]
    obligations: list[ObligationOutput]
    terminationOverview: str
    terminationCitations: list[CitationOutput]
    lawyerReport: str
    lawyerReportCitations: list[CitationOutput]
    hrReport: str | None = None
    hrSections: list[HRTopicOutput] = Field(default_factory=list)
    generatedLanguage: Language
    inferenceSource: Literal["IN_CLOUD"] = "IN_CLOUD"


class FollowUpOutput(BaseModel):
    answer: str
    citations: list[CitationOutput]
    inferenceSource: Literal["IN_CLOUD"] = "IN_CLOUD"
