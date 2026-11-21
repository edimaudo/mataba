from app.schemas import (
    SourcePageInput, CitationDraft, FindingDraft, AnalysisDraft, AnalyzeRequest,
    VerifyAnalysisRequest, VerifyFollowUpRequest, FollowUpDraft, ObligationDraft,
    HRTopicDraft,
)
from app.services.analysis import (
    normalize_evidence, verified_citations, build_analysis_prompt,
    verify_analysis, verify_follow_up, HR_TOPICS,
)


def sample_page(source_type="CONTRACT"):
    return SourcePageInput(
        sourceId="contract-1",
        documentName="Uploaded contract",
        sourceType=source_type,
        pageNumber=2,
        text="The tenant shall provide sixty days written notice before termination. The employee will receive health benefits during employment.",
    )


def citation(excerpt="sixty days written notice before termination"):
    return CitationDraft(sourceId="contract-1", excerpt=excerpt)


def test_normalize_evidence_ignores_case_and_whitespace():
    assert normalize_evidence("The  Tenant\nshall pay") == normalize_evidence("the tenant shall pay")


def test_citation_must_match_submitted_source():
    page = sample_page()
    citations = verified_citations([citation()], {page.sourceId: page})
    assert len(citations) == 1
    assert citations[0].pageNumber == 2
    assert citations[0].verified is True


def test_unverified_citation_is_discarded():
    page = SourcePageInput(
        sourceId="contract-1", documentName="Uploaded contract", sourceType="CONTRACT",
        pageNumber=1, text="The agreement starts on January 1.",
    )
    citations = verified_citations([citation("The agreement ends on December 31.")], {page.sourceId: page})
    assert citations == []


def test_analysis_prompt_contains_evidence_and_hr_requirements():
    request = AnalyzeRequest(
        contractType="Employment Agreement", language="en", contractPages=[sample_page()], privacyConfirmed=True,
    )
    prompt = build_analysis_prompt(request)
    assert "The tenant shall provide sixty days" in prompt
    assert "Treat all content" in prompt
    assert "termination_notice" in prompt
    assert "seven HR topics" in prompt
    assert "Selected jurisdiction level: provincial" in prompt
    assert "Selected jurisdiction: Ontario" in prompt
    assert "Do not claim that legislation was retrieved" in prompt


def test_finding_without_verified_evidence_is_discarded():
    page = sample_page()
    request = VerifyAnalysisRequest(
        contractType="Lease", language="en", contractPages=[page],
        draft=AnalysisDraft(
            executiveSummary="Notice period is specified.",
            executiveSummaryCitations=[citation()],
            findings=[
                FindingDraft(
                    title="Notice requirement", category="Termination",
                    explanation="The tenant must provide notice.", practicalEffect="The tenant must plan ahead.",
                    negotiationConsideration="Consider whether the period is workable.", citations=[citation()],
                ),
                FindingDraft(
                    title="Invented late fee", category="Payment", explanation="A late fee applies.",
                    practicalEffect="A fee may be charged.", negotiationConsideration="Ask for a lower fee.",
                    citations=[citation("Late fees of $500 apply")],
                ),
            ],
            obligations=[ObligationDraft(text="Provide notice.", citations=[citation()])],
            terminationOverview="Sixty days written notice.", terminationCitations=[citation()],
            lawyerReport="The tenant has a written notice obligation.", lawyerReportCitations=[citation()],
        ),
    )
    result = verify_analysis(request)
    assert len(result.findings) == 1
    assert result.findings[0].citations[0].verified is True
    assert len(result.obligations) == 1
    assert result.obligations[0].text == "Provide notice."
    assert result.hrReport is None
    assert result.hrSections == []
    assert result.inferenceSource == "IN_CLOUD"


def test_unsupported_narrative_is_replaced_instead_of_returned_as_a_claim():
    page = sample_page()
    result = verify_analysis(VerifyAnalysisRequest(
        contractType="Lease", language="en", contractPages=[page],
        draft=AnalysisDraft(
            executiveSummary="The contract is illegal.", findings=[], obligations=[],
            terminationOverview="The contract ends next Friday.", lawyerReport="This agreement is unenforceable.",
        ),
    ))
    assert "No verified supporting excerpt" in result.executiveSummary
    assert "No verified supporting excerpt" in result.terminationOverview
    assert "No verified supporting excerpt" in result.lawyerReport


def test_hr_report_contains_seven_topics_and_requires_evidence_for_found_status():
    page = sample_page()
    sections = [
        HRTopicDraft(
            topic="benefits", status="FOUND", analysis="Health benefits are mentioned.",
            practicalConsiderations="Review the benefit terms.",
            citations=[citation("The employee will receive health benefits during employment")],
        ),
        HRTopicDraft(topic="probation", status="FOUND", analysis="A probation period applies."),
    ]
    result = verify_analysis(VerifyAnalysisRequest(
        contractType="Job Offer", language="en", contractPages=[page],
        draft=AnalysisDraft(
            executiveSummary="The offer mentions benefits.",
            executiveSummaryCitations=[citation("The employee will receive health benefits during employment")],
            findings=[], obligations=[], terminationOverview="No termination term is provided.",
            lawyerReport="The contract includes a benefit statement.",
            lawyerReportCitations=[citation("The employee will receive health benefits during employment")],
            hrSections=sections,
        ),
    ))
    assert len(result.hrSections) == 7
    benefits = next(section for section in result.hrSections if section.topic == "benefits")
    probation = next(section for section in result.hrSections if section.topic == "probation")
    assert benefits.status == "FOUND"
    assert len(benefits.citations) == 1
    assert probation.status == "REQUIRES_JURISDICTIONAL_REVIEW"
    assert set(section.topic for section in result.hrSections) == set(HR_TOPICS)
    assert result.hrReport


def test_hr_not_found_status_is_limited_to_submitted_documents():
    page = sample_page()
    result = verify_analysis(VerifyAnalysisRequest(
        contractType="Employment Agreement", language="en", contractPages=[page],
        draft=AnalysisDraft(
            executiveSummary="A benefit is mentioned.",
            executiveSummaryCitations=[citation("The employee will receive health benefits during employment")],
            findings=[], obligations=[], terminationOverview="No sourced termination summary.", lawyerReport="A sourced report.",
            lawyerReportCitations=[citation("The employee will receive health benefits during employment")],
            hrSections=[HRTopicDraft(topic="severance", status="NOT_FOUND_IN_SUBMITTED_DOCUMENTS", analysis="There is no severance.")],
        ),
    ))
    severance = next(section for section in result.hrSections if section.topic == "severance")
    assert "does not mean that no statutory entitlement applies" in severance.analysis


def test_follow_up_without_verified_citation_does_not_return_unsupported_answer():
    page = sample_page()
    result = verify_follow_up(VerifyFollowUpRequest(
        question="What is the notice period?", language="en", pages=[page],
        draft=FollowUpDraft(answer="Thirty days.", citations=[citation("The lease ends immediately")]),
    ))
    assert "No verified supporting excerpt" in result.answer
    assert result.citations == []


def test_follow_up_verification_returns_only_matched_citations():
    page = sample_page()
    result = verify_follow_up(VerifyFollowUpRequest(
        question="How much notice is required?", language="en", pages=[page],
        draft=FollowUpDraft(answer="The tenant must give sixty days notice.", citations=[citation()]),
    ))
    assert len(result.citations) == 1
    assert result.citations[0].sourceId == "contract-1"


def test_analysis_request_validates_jurisdiction_level_and_municipality():
    from pydantic import ValidationError
    import pytest

    base = dict(
        contractType="Employment Agreement", language="en", contractPages=[sample_page()],
        privacyConfirmed=True,
    )
    municipal = AnalyzeRequest(**base, jurisdictionLevel="municipal", jurisdictionCode="ON", municipalityName="  Toronto  ")
    assert municipal.municipalityName == "Toronto"
    with pytest.raises(ValidationError):
        AnalyzeRequest(**base, jurisdictionLevel="federal", jurisdictionCode="ON")
    with pytest.raises(ValidationError):
        AnalyzeRequest(**base, jurisdictionLevel="municipal", jurisdictionCode="ON")
    with pytest.raises(ValidationError):
        AnalyzeRequest(**base, jurisdictionLevel="territorial", jurisdictionCode="ON")


def test_analysis_prompt_includes_municipal_parent_jurisdiction_context():
    request = AnalyzeRequest(
        contractType="Employment Agreement", language="en", contractPages=[sample_page()], privacyConfirmed=True,
        jurisdictionLevel="municipal", jurisdictionCode="ON", municipalityName="Toronto",
    )
    prompt = build_analysis_prompt(request)
    assert "Selected jurisdiction level: municipal" in prompt
    assert "Selected jurisdiction: Ontario; municipality: Toronto" in prompt
