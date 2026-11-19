import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vercel_config_targets_fastapi_entrypoint_and_montreal_region():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["regions"] == ["yul1"]
    assert "app/main.py" in config["functions"]
    assert (ROOT / "app" / "main.py").is_file()


def test_vercel_build_runs_frontend_build_without_creating_a_node_server():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    command = config["buildCommand"]
    assert "npm install --prefix frontend" in command
    assert "python scripts/build.py" in command
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert "scripts" not in package
    assert not any(ROOT.glob("*.mjs"))
    assert not (ROOT / "backend").exists()


def test_vercel_function_includes_templates_and_excludes_dev_only_files():
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    function = config["functions"]["app/main.py"]
    assert "firebase/ai_logic_templates/**" in function["includeFiles"]
    assert "tests/**" in function["excludeFiles"]
    assert "scripts/**" in function["excludeFiles"]


def test_python_requirements_are_at_repository_root():
    assert (ROOT / "requirements.txt").is_file()
    assert (ROOT / "requirements-dev.txt").is_file()


def test_firestore_emulator_does_not_collide_with_fastapi_local_port():
    firebase = json.loads((ROOT / "firebase.json").read_text(encoding="utf-8"))
    firestore_port = firebase["emulators"]["firestore"]["port"]
    assert firestore_port == 8081
    assert firestore_port != 8080
