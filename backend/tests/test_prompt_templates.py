from pathlib import Path
import yaml

TEMPLATE_DIR = Path(__file__).parents[1] / "firebase" / "ai_logic_templates"


def load_template(name: str):
    text = (TEMPLATE_DIR / name).read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{name}: missing YAML frontmatter"
    _, frontmatter, body = text.split("---", 2)
    config = yaml.safe_load(frontmatter)
    return config, body


def test_contract_analysis_template_matches_backend_contract():
    config, body = load_template("contract-analysis.prompt")
    assert config["model"] == "gemini-3.8-flash"
    assert config["input"]["schema"]["prompt"].startswith("string")
    assert config["output"]["format"] == "json"
    schema = config["output"]["schema"]
    required = {
        "executiveSummary", "executiveSummaryCitations(array)", "findings(array)",
        "obligations(array)", "terminationOverview", "terminationCitations(array)",
        "lawyerReport", "lawyerReportCitations(array)", "hrSections(array)",
    }
    assert required.issubset(schema)
    assert '{{role "user"}}' in body and "{{prompt}}" in body


def test_follow_up_template_matches_backend_contract():
    config, body = load_template("follow-up.prompt")
    assert config["model"] == "gemini-3.8-flash"
    assert config["input"]["schema"]["prompt"].startswith("string")
    assert config["output"]["format"] == "json"
    assert {"answer", "citations(array)"}.issubset(config["output"]["schema"])
    assert '{{role "user"}}' in body and "{{prompt}}" in body
