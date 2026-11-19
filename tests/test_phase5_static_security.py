from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_google_genai_or_direct_vertex_ai_python_client():
    requirements = (ROOT / 'requirements.txt').read_text().lower()
    source = '\n'.join(path.read_text(errors='ignore') for path in (ROOT / 'app').rglob('*.py'))
    assert 'google-genai' not in requirements
    assert 'from google import genai' not in source
    assert 'from vertexai' not in source


def test_no_unrestricted_cors_or_debug_docs_in_production():
    source = (ROOT / 'app' / 'main.py').read_text()
    assert 'allow_origins=settings.cors_origins' in source
    assert 'allow_origins=["*"]' not in source
    assert 'docs_url="/api/docs" if settings.environment != "production" else None' in source


def test_backend_security_headers_are_present():
    source = (ROOT / 'app' / 'main.py').read_text()
    for header in ['Cache-Control', 'X-Content-Type-Options', 'Referrer-Policy']:
        assert f'response.headers["{header}"]' in source


def test_application_contains_no_typescript_or_node_build_toolchain():
    assert not (ROOT / 'frontend').exists()
    assert not (ROOT / 'package.json').exists()
    assert not list(ROOT.rglob('package.json'))
    assert not list(ROOT.rglob('*.ts'))
    assert not list(ROOT.rglob('*.tsx'))
    assert not (ROOT / 'scripts' / 'build.py').exists()
    assert not (ROOT / 'public').exists()
    assert (ROOT / 'app' / 'static' / 'js' / 'main.js').is_file()
    assert (ROOT / 'app' / 'templates' / 'index.html').is_file()


def test_native_browser_javascript_uses_only_pinned_browser_imports():
    html = (ROOT / 'app' / 'templates' / 'index.html').read_text()
    assert 'type="importmap"' in html
    assert 'firebase/ai' in html
    assert 'pdfjs-dist@5.4.394' in html
    assert 'mammoth@1.10.0' in html
    assert 'type="module" src="/js/main.js"' in html


def test_native_javascript_bare_imports_have_matching_browser_import_map_entries():
    import json
    import re

    html = (ROOT / "app" / "templates" / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<script type="importmap">\s*(\{.*?\})\s*</script>', html, re.S)
    assert match is not None
    imports = json.loads(match.group(1))["imports"]

    required = set()
    for path in (ROOT / "app" / "static" / "js").rglob("*.js"):
        source = path.read_text(encoding="utf-8")
        required.update(spec for spec in re.findall(r"from\s*['\"]([^'\"]+)['\"]", source) if not spec.startswith("."))
    assert required <= set(imports)
    assert "mammoth.browser.js" in html
    assert "pdf.worker.mjs" in (ROOT / "app" / "static" / "js" / "lib" / "documents.js").read_text(encoding="utf-8")
