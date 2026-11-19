from pathlib import Path

from fastapi.testclient import TestClient

from app import main


def test_fastapi_serves_frontend_html_from_dist(monkeypatch, tmp_path):
    index = tmp_path / "index.html"
    index.write_text("<!doctype html><html><title>Mataba</title></html>", encoding="utf-8")
    (tmp_path / "app.js").write_text("console.log('mataba');", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)

    with TestClient(main.app) as client:
        root = client.get("/")
        asset = client.get("/app.js")

    assert root.status_code == 200
    assert "Mataba" in root.text
    assert root.headers["content-type"].startswith("text/html")
    assert asset.status_code == 200
    assert "console.log" in asset.text


def test_fastapi_rejects_static_path_traversal(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)
    with TestClient(main.app) as client:
        response = client.get("/%2e%2e/.env")
    assert response.status_code in {404, 422}


def test_fastapi_keeps_unknown_api_routes_out_of_frontend_fallback(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html>Mataba</html>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)
    with TestClient(main.app) as client:
        response = client.get("/api/not-a-real-route")
    assert response.status_code == 404
    assert "Mataba" not in response.text


def test_frontend_backend_api_uses_same_origin_by_default():
    root = Path(__file__).resolve().parents[1]
    config = (root / "frontend" / "public" / "config.js").read_text()
    client = (root / "frontend" / "src" / "lib" / "backend.ts").read_text()
    assert 'backendApiBaseUrl: ""' in config
    assert "fetch(`${backendApiBaseUrl}${path}`" in client
    assert "if (!backendApiBaseUrl)" not in client


def test_settings_read_env_file_from_project_root():
    from app.config import ROOT_ENV_FILE
    expected = Path(__file__).resolve().parents[1] / ".env"
    assert ROOT_ENV_FILE == expected



def test_qa_route_serves_mataba_frontend_without_contract_id(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html><title>Mataba</title></html>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)
    with TestClient(main.app) as client:
        response = client.get("/qa")
    assert response.status_code == 200
    assert "Mataba" in response.text


def test_unknown_browser_route_returns_real_custom_404_page(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html>Mataba</html>", encoding="utf-8")
    (tmp_path / "404.html").write_text("<html><h1>Page not found</h1><a href='/qa'>Legal Q&A</a></html>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)
    with TestClient(main.app) as client:
        response = client.get("/this-page-does-not-exist")
    assert response.status_code == 404
    assert "Page not found" in response.text
    assert "Legal Q&A" in response.text


def test_missing_javascript_asset_does_not_return_custom_html_404(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html>Mataba</html>", encoding="utf-8")
    (tmp_path / "404.html").write_text("<html>Page not found</html>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)
    with TestClient(main.app) as client:
        response = client.get("/assets/missing-worker.js")
    assert response.status_code == 404
    assert "Page not found" not in response.text


def test_contract_review_supports_upload_and_pasted_text_modes():
    root = Path(__file__).resolve().parents[1]
    source = (root / "frontend" / "src" / "main.ts").read_text(encoding="utf-8")
    assert 'data-action="contract-input-mode"' in source
    assert 'data-field="pasted-contract-text"' in source
    assert 'data-action="prepare-pasted-contract"' in source
    assert "Pasted contract text" in source
    assert "generateContractAnalysis" in source


def test_legal_qa_has_employment_only_law_type_and_three_level_jurisdiction_selector():
    root = Path(__file__).resolve().parents[1]
    source = (root / "frontend" / "src" / "main.ts").read_text(encoding="utf-8")
    assert 'id="legal-law-type"' in source
    assert 'value="employment"' in source
    assert "Employment law" in source
    assert 'name="jurisdictionLevel"' in source
    assert 'value="municipal"' in source
    assert 'name="municipalityName"' in source
    assert "legalQaSourceLevel" in source
