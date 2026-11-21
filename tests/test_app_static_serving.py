from pathlib import Path

from fastapi.testclient import TestClient

from app import main


def set_test_assets(monkeypatch, tmp_path):
    static = tmp_path / "static"
    templates = tmp_path / "templates"
    static.mkdir()
    templates.mkdir()
    monkeypatch.setattr(main, "STATIC_DIR", static)
    monkeypatch.setattr(main, "TEMPLATES_DIR", templates)
    return static, templates


def test_fastapi_serves_html_and_native_javascript_directly(monkeypatch, tmp_path):
    static, templates = set_test_assets(monkeypatch, tmp_path)
    (templates / "landing.html").write_text("<!doctype html><html><title>Mataba</title></html>", encoding="utf-8")
    (templates / "index.html").write_text("<!doctype html><html><title>Mataba app</title></html>", encoding="utf-8")
    (static / "main.js").write_text("console.log('mataba');", encoding="utf-8")

    with TestClient(main.app) as client:
        root = client.get("/")
        application = client.get("/app")
        signin = client.get("/signin", follow_redirects=False)
        asset = client.get("/main.js")

    assert root.status_code == 200
    assert "Mataba" in root.text
    assert root.headers["content-type"].startswith("text/html")
    assert application.status_code == 200
    assert signin.status_code == 307
    assert signin.headers["location"] == "/app"
    assert asset.status_code == 200
    assert "console.log" in asset.text
    assert "javascript" in asset.headers["content-type"]


def test_fastapi_rejects_static_path_traversal(monkeypatch, tmp_path):
    static, templates = set_test_assets(monkeypatch, tmp_path)
    (templates / "index.html").write_text("<html></html>", encoding="utf-8")
    with TestClient(main.app) as client:
        response = client.get("/%2e%2e/.env")
    assert response.status_code in {404, 422}


def test_fastapi_keeps_unknown_api_routes_out_of_application_fallback(monkeypatch, tmp_path):
    _, templates = set_test_assets(monkeypatch, tmp_path)
    (templates / "index.html").write_text("<html>Mataba</html>", encoding="utf-8")
    with TestClient(main.app) as client:
        response = client.get("/api/not-a-real-route")
    assert response.status_code == 404
    assert "Mataba" not in response.text


def test_browser_api_client_uses_fastapi_same_origin_by_default():
    root = Path(__file__).resolve().parents[1]
    config = (root / "app" / "static" / "config.js").read_text()
    client = (root / "app" / "static" / "js" / "lib" / "backend.js").read_text()
    assert 'backendApiBaseUrl: ""' in config
    assert "fetch(`${backendApiBaseUrl}${path}`" in client
    assert "if (!backendApiBaseUrl)" not in client


def test_settings_read_env_file_from_project_root():
    from app.config import ROOT_ENV_FILE
    expected = Path(__file__).resolve().parents[1] / ".env"
    assert ROOT_ENV_FILE == expected


def test_qa_route_serves_application_template_without_contract_id(monkeypatch, tmp_path):
    _, templates = set_test_assets(monkeypatch, tmp_path)
    (templates / "index.html").write_text("<html><title>Mataba</title></html>", encoding="utf-8")
    with TestClient(main.app) as client:
        response = client.get("/qa")
    assert response.status_code == 200
    assert "Mataba" in response.text


def test_unknown_browser_route_returns_real_custom_404_page(monkeypatch, tmp_path):
    _, templates = set_test_assets(monkeypatch, tmp_path)
    (templates / "index.html").write_text("<html>Mataba</html>", encoding="utf-8")
    (templates / "404.html").write_text("<html><h1>Page not found</h1><a href='/qa'>Legal Q&A</a></html>", encoding="utf-8")
    with TestClient(main.app) as client:
        response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert "Page not found" in response.text
    assert "Legal Q&A" in response.text


def test_missing_javascript_asset_does_not_return_custom_html_404(monkeypatch, tmp_path):
    _, templates = set_test_assets(monkeypatch, tmp_path)
    (templates / "404.html").write_text("<html>Page not found</html>", encoding="utf-8")
    with TestClient(main.app) as client:
        response = client.get("/js/missing.js")
    assert response.status_code == 404
    assert "Page not found" not in response.text


def test_contract_review_supports_upload_and_pasted_text_modes():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "static" / "js" / "main.js").read_text(encoding="utf-8")
    assert 'data-action="contract-input-mode"' in source
    assert 'data-field="pasted-contract-text"' in source
    assert 'data-action="prepare-pasted-contract"' in source
    assert "Pasted contract text" in source
    assert "generateContractAnalysis" in source


def test_legal_qa_has_employment_only_law_type_and_municipal_jurisdiction_selector():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "static" / "js" / "main.js").read_text(encoding="utf-8")
    assert 'id="legal-law-type"' in source
    assert 'value="employment"' in source
    assert "Employment law" in source
    assert 'name="jurisdictionLevel"' in source
    assert 'value="municipal"' in source
    assert 'name="municipalityName"' in source
    assert "legalQaSourceLevel" in source


def test_fastapi_serves_html_css_javascript_and_runtime_config_from_app_package():
    root = Path(__file__).resolve().parents[1]
    with TestClient(main.app) as client:
        page = client.get("/app")
        landing = client.get("/")
        stylesheet = client.get("/css/styles.css")
        script = client.get("/js/main.js")
        config = client.get("/config.js")

    assert page.status_code == 200
    assert 'type="module" src="/js/main.js"' in page.text
    assert landing.status_code == 200
    assert 'href="/app"' in landing.text
    assert "How it works" not in landing.text
    assert "Legal coverage</a>" not in landing.text
    assert "<footer" not in landing.text
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert "import {" in script.text
    assert config.status_code == 200
    assert "MATABA_CONFIG" in config.text
    assert (root / "app" / "static" / "js" / "main.js").is_file()


def test_public_landing_and_direct_application_entry_have_no_signin_screen():
    root = Path(__file__).resolve().parents[1]
    with TestClient(main.app) as client:
        landing = client.get("/")
        signin = client.get("/signin", follow_redirects=False)
        application = client.get("/app")
    assert "Understand your employment contract before you sign." in landing.text
    assert 'href="/app"' in landing.text
    assert "How it works" not in landing.text
    assert "Legal coverage</a>" not in landing.text
    assert "Review the terms that matter." in landing.text
    assert "Canadian legal coverage" in landing.text
    assert 'class="landing-cards"' in landing.text
    assert 'class="landing-card"' in landing.text
    assert "<footer" not in landing.text
    assert signin.status_code == 307
    assert signin.headers["location"] == "/app"
    assert 'type="module" src="/js/main.js"' not in landing.text
    assert 'type="module" src="/js/main.js"' in application.text
    script = (root / "app" / "static" / "js" / "main.js").read_text(encoding="utf-8")
    assert 'data-action="preview"' not in script
    assert 'Local-only preview' not in script
    assert 'localPreviewText' not in script
    assert 'class="eyebrow"' not in script
    assert 'class="eyebrow"' not in (root / "app" / "templates" / "landing.html").read_text(encoding="utf-8")
    assert "authView()" not in script
    assert "signInAnonymously(auth)" in script
    assert "localGuestIdentity()" in script


def test_guest_local_fallback_never_writes_to_firestore_without_matching_firebase_user():
    root = Path(__file__).resolve().parents[1]
    repository = (root / "app" / "static" / "js" / "lib" / "repository.js").read_text(encoding="utf-8")
    assert "auth.currentUser.uid === userId" in repository
    assert "!userId.startsWith('local-')" in repository

def test_landing_information_cards_are_equal_height_and_responsive():
    root = Path(__file__).resolve().parents[1]
    stylesheet = (root / "app" / "static" / "css" / "styles.css").read_text(encoding="utf-8")
    assert ".landing-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));" in stylesheet
    assert ".landing-card { box-sizing: border-box; display: flex; flex-direction: column; min-height: 205px; height: 100%;" in stylesheet
    assert ".landing-cards { grid-template-columns: 1fr;" in stylesheet


def test_new_review_requires_jurisdiction_and_contains_conditional_location_fields():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "static" / "js" / "main.js").read_text(encoding="utf-8")
    translations = (root / "app" / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
    assert 'data-form="new-review"' in source
    assert "type=\"submit\" ${d.busy ? 'disabled' : ''}" in source
    assert 'data-field="draftJurisdictionLevel" required' in source
    assert 'data-field="draftJurisdictionCode" required' in source
    assert 'data-field="draftMunicipalityName"' in source
    assert "function validateNewReview()" in source
    assert "reviewChooseJurisdictionLevel" in source
    assert "reviewChooseProvinceTerritory" in source
    assert "reviewEnterMunicipality" in source
    assert "jurisdictionLevel: analysisJurisdictionLevel" in source
    assert "reviewJurisdictionLevel: 'Jurisdiction level'" in translations
    assert "reviewJurisdictionLevel: 'Palier de compétence'" in translations


def test_legal_qa_municipal_context_paragraph_is_removed_in_both_languages():
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "static" / "js" / "main.js").read_text(encoding="utf-8")
    translations = (root / "app" / "static" / "js" / "i18n.js").read_text(encoding="utf-8")
    assert "For this Employment law release, the municipality adds local context." not in source + translations
    assert "Dans cette version du droit du travail, la municipalité précise le contexte local." not in source + translations
    assert "legalQaMunicipalNote" not in source + translations
