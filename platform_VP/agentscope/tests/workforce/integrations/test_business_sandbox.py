"""Sandbox preparation must never inherit production credentials or endpoints."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "workforce" / "business_sandbox.py"
sandbox = None
pytestmark = pytest.mark.skipif(len(SCRIPT.resolve().parents) < 5, reason="Requires the complete Platform + Domain source tree")
if len(SCRIPT.resolve().parents) >= 5:
    spec = importlib.util.spec_from_file_location("business_sandbox", SCRIPT)
    sandbox = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sandbox)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(sandbox, "source_snapshot", lambda: {
        "commit": "fixture", "branch": "fixture", "worktree_sha256": "a" * 64, "dirty": True,
    })
    monkeypatch.setenv("OPENAI_API_KEY", "must-never-copy-production-model-secret")
    monkeypatch.setenv("VINHOMES_API_DATABASE_URL", "postgresql://production.example/production")
    folder = tmp_path / "run"
    manifest = sandbox.prepare(folder, "test-run", 17)
    return folder, manifest


def test_sandbox_has_separate_data_no_egress_or_inherited_credentials(prepared):
    folder, manifest = prepared
    contents = (folder / "compose.json").read_text(encoding="utf-8")
    compose = json.loads(contents)
    assert compose["networks"]["default"]["internal"] is True
    assert "production.example" not in contents
    assert "must-never-copy" not in contents
    assert compose["services"]["platform"]["environment"]["OPENAI_API_KEY"] == ""
    assert compose["services"]["domain-api"]["environment"]["VINHOMES_API_PLATFORM_URL"] == ""
    assert manifest["connection_status"] == "not_onboarded"
    assert manifest["runtime_status"] == "prepared_only"
    assert manifest["model"]["mode"] == "unconfigured"
    assert manifest["runtime_images"] == {}
    assert all(port.startswith("127.0.0.1:") for service in compose["services"].values()
               for port in service.get("ports", []))
    assert all(not service.get("extra_hosts") and not service.get("container_name")
               for service in compose["services"].values())
    assert manifest["seed"] == 17
    assert len(manifest["declaration_sha256"]) == len(manifest["schema_sha256"]) == 64


def test_new_run_reset_preserves_previous_directory_and_uses_fresh_database(prepared, tmp_path):
    folder, first = prepared
    before = (folder / "compose.json").read_bytes()
    with pytest.raises(ValueError, match="never overwritten"):
        sandbox.prepare(folder, "test-run")
    second = sandbox.prepare(tmp_path / "second", "another-run", 17)
    assert first["database"] != second["database"]
    assert first["project"] != second["project"]
    assert (folder / "compose.json").read_bytes() == before


def test_rejects_repo_output_and_invalid_namespace_before_writing():
    with pytest.raises(ValueError, match="outside the repository"):
        sandbox.prepare(sandbox.REPOSITORY / "unwanted-sandbox", "test")
    with pytest.raises(ValueError, match="run_id"):
        sandbox.prepare(Path("unused"), "../production")


def test_runtime_capture_rejects_changed_topology_before_docker(prepared, monkeypatch):
    folder, _ = prepared
    compose = json.loads((folder / "compose.json").read_text(encoding="utf-8"))
    compose["networks"]["default"]["internal"] = False
    sandbox._write_json(folder / "compose.json", compose)
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: pytest.fail("Docker must not be called"))
    with pytest.raises(ValueError, match="internal"):
        sandbox.record_runtime(folder)


def test_runtime_capture_requires_source_fingerprint(prepared, monkeypatch):
    folder, _ = prepared
    monkeypatch.setattr(sandbox, "source_snapshot", lambda: {"commit": "changed"})
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: pytest.fail("Docker must not be called"))
    with pytest.raises(ValueError, match="Source changed"):
        sandbox.record_runtime(folder)
