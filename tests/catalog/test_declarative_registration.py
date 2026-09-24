"""Catalog admission and discovery tests; package hashes here are test fixtures."""
from __future__ import annotations

import hashlib
import json

import pytest

from bionodulo.nodes.contract.cwl import import_cwl
from bionodulo.nodes.contract.environments import ExecutableProbe
from bionodulo.nodes.import_cwl import main
from bionodulo.nodes.registry import NodeRegistry

from .test_node_spec import SHA_A, pixi_environment


def environment():
    return pixi_environment(tool_id="coreutils", tool_version="9.5").model_copy(update={
        "executable_probes": (ExecutableProbe(
            probe_id="echo-version", locator="bin/echo", version_arguments=("--version",),
            version_line_prefix="echo (GNU coreutils) ", expected_version="9.5", fingerprint=SHA_A,
        ),),
    })


def descriptor():
    return {
        "cwlVersion": "v1.2", "class": "CommandLineTool", "baseCommand": "echo",
        "inputs": {"message": {"type": "string", "inputBinding": {"position": 1}}},
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "message.txt"}}},
        "stdout": "message.txt",
    }


def spec(node_id="descriptor_echo"):
    return import_cwl(descriptor(), node_id=node_id, environment=environment(),
                      tool_id="coreutils", tool_version="9.5", source_uri="https://example.org/fixture.cwl")


def bundle(path, specs):
    path.write_text(json.dumps({"schema_version": 1, "specs": [item.model_dump(mode="json") for item in specs]}))
    return path


def test_data_only_registration_requires_explicit_candidate_execution():
    registry = NodeRegistry.create_isolated()
    candidate = spec()
    with pytest.raises(ValueError, match="unverified"):
        registry.register_cwl_spec(candidate)
    assert registry.get(candidate.identity.machine_id) is None
    registry.register_cwl_spec(candidate, allow_unverified=True)
    metadata = registry.object_info()[candidate.identity.machine_id]
    assert metadata["declarative_runtime"]["verification"] == "unverified"
    assert metadata["declarative_runtime"]["contract_digest"] == candidate.contract_digest()
    assert "message" in metadata["input"]["required"]
    assert metadata["output_name"] == ["result"]
    assert metadata["experimental"] is True
    assert registry.get(candidate.identity.machine_id).__module__ == "bionodulo.nodes.declarative_cwl"


def test_bundle_admission_is_atomic_and_cannot_shadow_builtin(tmp_path):
    registry = NodeRegistry.create_isolated()
    # A valid first entry must not become live if a later one shadows a builtin.
    path = bundle(tmp_path / "catalog.json", [spec(), spec("normalize_data")])
    with pytest.raises(ValueError, match="collides"):
        registry.load_declarative_catalog(path, allow_unverified=True)
    assert registry.get("descriptor_echo") is None
    assert registry.get("normalize_data").__module__ != "bionodulo.nodes.declarative_cwl"


def test_bundle_rejects_duplicate_entries_and_unknown_schema(tmp_path):
    registry = NodeRegistry.create_isolated()
    path = bundle(tmp_path / "catalog.json", [spec(), spec()])
    with pytest.raises(ValueError, match="collides"):
        registry.load_declarative_catalog(path, allow_unverified=True)
    assert registry.get("descriptor_echo") is None
    path.write_text(json.dumps({"schema_version": True, "specs": []}))
    with pytest.raises(ValueError, match="schema_version"):
        registry.load_declarative_catalog(path, allow_unverified=True)


def test_singleton_startup_loads_configured_catalog_and_failed_load_can_retry(tmp_path, monkeypatch):
    path = bundle(tmp_path / "catalog.json", [spec()])
    monkeypatch.setattr(NodeRegistry, "_instance", None)
    monkeypatch.setenv("BIONODULO_DECLARATIVE_CATALOG", str(path))
    monkeypatch.delenv("BIONODULO_ALLOW_UNVERIFIED_CWL", raising=False)
    with pytest.raises(ValueError, match="unverified"):
        NodeRegistry()
    assert NodeRegistry._instance is None
    monkeypatch.setenv("BIONODULO_ALLOW_UNVERIFIED_CWL", "1")
    assert NodeRegistry().has("descriptor_echo")
    # An isolated validation registry must not recursively reload process config.
    assert NodeRegistry.create_isolated().get("descriptor_echo") is None


def test_cli_import_and_append_changes_only_catalog_data(tmp_path):
    source = tmp_path / "source.cwl"
    source.write_text(json.dumps(descriptor()))
    locked = tmp_path / "environment.json"
    locked.write_text(environment().model_dump_json())
    output = tmp_path / "catalog.json"
    args = [str(source), "--environment", str(locked), "--tool-id", "coreutils",
            "--tool-version", "9.5", "--output", str(output), "--node-id"]
    assert main([*args, "first_import"]) == 0
    invocation = json.loads(output.read_bytes())["specs"][0]["cwl_invocation"]
    assert invocation["source_content_sha256"] == "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
    assert invocation["source_size_bytes"] == len(source.read_bytes())
    assert main([*args, "second_import", "--append"]) == 0
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        main([*args, "second_import", "--append"])
    assert output.read_bytes() == original
    registry = NodeRegistry.create_isolated()
    assert registry.load_declarative_catalog(output, allow_unverified=True) == 2
    assert registry.has("first_import") and registry.has("second_import")
    assert not list(tmp_path.glob("*.py"))


def test_cli_rejects_ambiguous_yaml_without_writing_catalog(tmp_path, capsys):
    source = tmp_path / "ambiguous.cwl"
    source.write_text("cwlVersion: v1.2\nclass: CommandLineTool\nbaseCommand: echo\nbaseCommand: cat\n")
    locked = tmp_path / "environment.json"
    locked.write_text(environment().model_dump_json())
    output = tmp_path / "catalog.json"
    with pytest.raises(SystemExit) as error:
        main([str(source), "--environment", str(locked), "--node-id", "ambiguous",
              "--tool-id", "coreutils", "--tool-version", "9.5", "--output", str(output)])
    assert error.value.code == 2
    assert "duplicate mapping key" in capsys.readouterr().err
    assert not output.exists()
