from __future__ import annotations

import json
from pathlib import Path

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_file_format_utility_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "file_info": ("File Info", "utils", ["STRING", "INT", "FLOAT", "BOOLEAN"], ["info_json", "size_bytes", "size_mb", "exists"]),
        "path_operations": ("Path Operations", "utils", ["STRING", "BOOLEAN"], ["result", "exists"]),
        "json_operations": ("JSON Operations", "utils/format", ["STRING", "STRING", "BOOLEAN"], ["result_json", "value", "valid"]),
        "yaml_operations": ("YAML Operations", "utils/format", ["STRING", "STRING", "BOOLEAN"], ["result_yaml", "value", "valid"]),
    }

    for node_id, (display_name, category, outputs, output_names) in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == display_name
        assert node_info["category"] == category
        assert node_info["output"] == outputs
        assert node_info["output_name"] == output_names
        assert node_info["search_aliases"]
        assert node_info["required_executables"] == []
        assert node_info["required_conda_packages"] == []


@pytest.mark.asyncio
async def test_file_info_reports_metadata_for_existing_and_missing_paths(tmp_path: Path) -> None:
    sample = tmp_path / "sample.fastq"
    sample.write_text("@r1\nACGT\n+\n!!!!\n", encoding="utf-8")

    info_json, size_bytes, size_mb, exists = await _node_class("file_info")().run(file=str(sample))
    info = json.loads(info_json)

    assert exists is True
    assert size_bytes == sample.stat().st_size
    assert size_mb == pytest.approx(size_bytes / (1024 * 1024))
    assert info["path"] == str(sample.resolve())
    assert info["name"] == "sample.fastq"
    assert info["extension"] == ".fastq"
    assert info["exists"] is True
    assert info["is_file"] is True
    assert info["is_dir"] is False
    assert info["size_bytes"] == size_bytes
    assert info["size_mb"] == pytest.approx(size_mb)

    missing_json, missing_size, missing_mb, missing_exists = await _node_class("file_info")().run(file=str(tmp_path / "missing.txt"))
    missing_info = json.loads(missing_json)

    assert missing_exists is False
    assert missing_size == 0
    assert missing_mb == 0.0
    assert missing_info["exists"] is False
    assert missing_info["is_file"] is False
    assert missing_info["is_dir"] is False


@pytest.mark.asyncio
async def test_path_operations_manipulate_paths_and_report_existence(tmp_path: Path) -> None:
    sample = tmp_path / "reads" / "sample.fastq.gz"
    sample.parent.mkdir()
    sample.write_text("ACGT\n", encoding="utf-8")
    node = _node_class("path_operations")()

    assert await node.run(operation="basename", path=str(sample)) == ("sample.fastq.gz", True)
    assert await node.run(operation="dirname", path=str(sample)) == (str(sample.parent), True)
    assert await node.run(operation="extension", path=str(sample)) == (".gz", True)
    assert await node.run(operation="stem", path=str(sample)) == ("sample.fastq", True)
    assert await node.run(operation="join", path=str(tmp_path), path_b="out/result.txt") == (str(tmp_path / "out/result.txt"), False)
    assert await node.run(operation="exists", path=str(sample)) == (str(sample), True)
    assert await node.run(operation="absolute", path=str(sample)) == (str(sample.resolve()), True)

    with pytest.raises(ValueError, match="Unsupported path operation"):
        await node.run(operation="unknown", path=str(sample))


@pytest.mark.asyncio
async def test_json_operations_support_string_and_file_inputs(tmp_path: Path) -> None:
    node = _node_class("json_operations")()
    payload = {"samples": [{"id": "S1", "reads": 12}], "enabled": True}
    json_text = json.dumps(payload)
    json_file = tmp_path / "payload.json"
    json_file.write_text(json_text, encoding="utf-8")

    result_json, value, valid = await node.run(operation="get", json_input=str(json_file), key="samples.0.id")
    assert json.loads(result_json) == payload
    assert value == "S1"
    assert valid is True

    result_json, value, valid = await node.run(operation="set", json_input=json_text, key="samples.0.reads", value="24")
    assert json.loads(result_json)["samples"][0]["reads"] == 24
    assert value == "24"
    assert valid is True

    result_json, value, valid = await node.run(operation="delete", json_input=result_json, key="enabled")
    assert "enabled" not in json.loads(result_json)
    assert value == ""
    assert valid is True

    keys_json, keys_value, keys_valid = await node.run(operation="keys", json_input=json_text)
    assert json.loads(keys_json) == payload
    assert keys_value == "samples\nenabled"
    assert keys_valid is True

    invalid_json, invalid_value, invalid_valid = await node.run(operation="validate", json_input="{bad json")
    assert invalid_json == ""
    assert "Invalid JSON" in invalid_value
    assert invalid_valid is False

    with pytest.raises(ValueError, match="key is required"):
        await node.run(operation="get", json_input=json_text)


@pytest.mark.asyncio
async def test_yaml_operations_support_flat_yaml_and_json_conversion(tmp_path: Path) -> None:
    node = _node_class("yaml_operations")()
    yaml_text = "sample: S1\nreads: 12\nenabled: true\n"
    yaml_file = tmp_path / "payload.yaml"
    yaml_file.write_text(yaml_text, encoding="utf-8")

    result_yaml, value, valid = await node.run(operation="get", yaml_input=str(yaml_file), key="sample")
    assert "sample:" in result_yaml
    assert value == "S1"
    assert valid is True

    result_yaml, value, valid = await node.run(operation="set", yaml_input=yaml_text, key="reads", value="24")
    assert "reads: 24" in result_yaml
    assert value == "24"
    assert valid is True

    result_json, value, valid = await node.run(operation="to_json", yaml_input=result_yaml)
    assert json.loads(result_json)["reads"] == 24
    assert value == ""
    assert valid is True

    keys_yaml, keys_value, keys_valid = await node.run(operation="keys", yaml_input=yaml_text)
    assert "sample:" in keys_yaml
    assert keys_value == "sample\nreads\nenabled"
    assert keys_valid is True
    assert await node.run(operation="validate", yaml_input="sample: S1\n") == ("sample: S1\n", "", True)

    with pytest.raises(ValueError, match="key is required"):
        await node.run(operation="get", yaml_input=yaml_text)
