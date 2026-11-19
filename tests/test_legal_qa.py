from app.schemas import LegalQADraft, LegalQARequest, LegalQACitationDraft
from app.services.legal_sources import LawPassage, LAW_SOURCES
from app.services.legal_qa import build_legal_qa_prompt, verify_legal_qa


def make_passage() -> LawPassage:
    source = LAW_SOURCES["ON"]
    return LawPassage(
        source_id="law-on-1",
        jurisdiction_code="ON",
        jurisdiction=source.jurisdiction,
        act_title=source.act_title,
        official_url=source.official_url,
        section_label="Section 22",
        page_number=None,
        text="An employer must pay overtime wages when an employee works more than the statutory threshold of hours in a work week.",
    )


def test_prompt_contains_the_question_selected_jurisdiction_and_retrieved_excerpt():
    request = LegalQARequest(question="How does overtime work?", jurisdictionCode="ON", language="en")
    passage = make_passage()
    prompt = build_legal_qa_prompt(request, LAW_SOURCES["ON"], [passage])
    assert "How does overtime work?" in prompt
    assert "Ontario" in prompt
    assert "LAW_EXCERPTS_JSON" in prompt
    assert passage.text in prompt
    assert "Do not invent section numbers" in prompt


def test_verified_official_excerpt_is_returned_as_citation():
    request = LegalQARequest(question="How does overtime work?", jurisdictionCode="ON", language="en")
    passage = make_passage()
    draft = LegalQADraft(
        answer="The Act requires overtime wages after the applicable statutory threshold.",
        citations=[LegalQACitationDraft(sourceId=passage.source_id, excerpt=passage.text)],
    )
    result = verify_legal_qa(request, LAW_SOURCES["ON"], [passage], draft)
    assert result.evidenceFound is True
    assert len(result.citations) == 1
    assert result.citations[0].verified is True
    assert result.citations[0].officialUrl == passage.official_url


def test_fabricated_or_wrong_source_citation_is_suppressed_and_answer_withheld():
    request = LegalQARequest(question="How does overtime work?", jurisdictionCode="ON", language="en")
    passage = make_passage()
    draft = LegalQADraft(
        answer="The law requires overtime after 40 hours, with a special exception.",
        citations=[LegalQACitationDraft(sourceId="made-up-source", excerpt="The law requires overtime after 40 hours.")],
    )
    result = verify_legal_qa(request, LAW_SOURCES["ON"], [passage], draft)
    assert result.evidenceFound is False
    assert result.citations == []
    assert "do not provide enough support" in result.answer


def test_french_answer_includes_french_general_information_disclaimer():
    request = LegalQARequest(question="Comment les heures supplémentaires sont-elles calculées?", jurisdictionCode="QC", language="fr")
    source = LAW_SOURCES["QC"]
    passage = make_passage()
    draft = LegalQADraft(answer="Réponse", citations=[])
    result = verify_legal_qa(request, source, [passage], draft)
    assert "ne constituent pas un avis juridique" in result.disclaimer




def test_municipal_scope_requires_a_parent_province_or_territory_and_municipality():
    request = LegalQARequest(
        question="Does a local bylaw affect this employment question?",
        jurisdictionCode="ON",
        jurisdictionLevel="municipal",
        municipalityName="  City   of Toronto  ",
        language="en",
    )
    assert request.jurisdictionLevel == "municipal"
    assert request.municipalityName == "City of Toronto"

    for payload in (
        {"question": "Does a local bylaw affect this employment question?", "jurisdictionCode": "ON", "jurisdictionLevel": "municipal", "language": "en"},
        {"question": "Does a local bylaw affect this employment question?", "jurisdictionCode": "CA", "jurisdictionLevel": "municipal", "municipalityName": "Toronto", "language": "en"},
        {"question": "Does a local bylaw affect this employment question?", "jurisdictionCode": "ON", "jurisdictionLevel": "federal", "language": "en"},
    ):
        try:
            LegalQARequest(**payload)
        except Exception:
            continue
        raise AssertionError("Invalid jurisdiction hierarchy must be rejected")


def test_municipal_query_prompt_and_result_identify_the_actual_parent_source_level():
    request = LegalQARequest(
        question="Does a Toronto bylaw change employment standards?",
        jurisdictionCode="ON",
        jurisdictionLevel="municipal",
        municipalityName="Toronto",
        language="en",
    )
    passage = make_passage()
    prompt = build_legal_qa_prompt(request, LAW_SOURCES["ON"], [passage])
    assert "Requested municipality: Toronto" in prompt
    assert "Source jurisdiction level: provincial" in prompt
    assert "no matching official municipal source was retrieved" in prompt
    assert "Do not describe it as a municipal bylaw" in prompt

    result = verify_legal_qa(
        request,
        LAW_SOURCES["ON"],
        [passage],
        LegalQADraft(answer="The provincial statute is the source supplied.", citations=[]),
    )
    assert result.jurisdictionLevel == "municipal"
    assert result.municipalityName == "Toronto"
    assert result.sourceLevel == "provincial"


def test_legal_qa_request_only_accepts_employment_law_for_now():
    request = LegalQARequest(question="How does overtime work?", jurisdictionCode="ON", language="en", lawType="employment")
    assert request.lawType == "employment"
    try:
        LegalQARequest(question="How does overtime work?", jurisdictionCode="ON", language="en", lawType="privacy")
    except Exception:
        pass
    else:
        raise AssertionError("Unsupported law categories must be rejected")


def test_legal_qa_prompt_declares_employment_law_category():
    request = LegalQARequest(question="How does overtime work?", jurisdictionCode="ON", language="en")
    prompt = build_legal_qa_prompt(request, LAW_SOURCES["ON"], [make_passage()])
    assert "Type of law: Employment law" in prompt
