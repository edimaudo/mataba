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


def test_application_has_no_custom_node_application_servers_or_mjs_scripts():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    custom_mjs = [path for path in root.rglob('*.mjs') if 'node_modules' not in path.parts and 'dist' not in path.parts]
    assert custom_mjs == []
    assert not (root / 'dev.mjs').exists()
    assert not (root / 'serve.mjs').exists()
    assert not (root / 'build.mjs').exists()


def test_frontend_package_manifest_has_no_node_application_scripts():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'frontend' / 'package.json').read_text())
    assert 'scripts' not in manifest
    assert 'firebase' in manifest['dependencies']
    assert 'pdfjs-dist' in manifest['dependencies']
