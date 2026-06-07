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
        "read_file": ("Read File", "utils", ["STRING", "STRING", "INT"], ["content", "lines", "line_count"]),
        "write_file": ("Write File", "utils", ["STRING", "INT"], ["file_path", "bytes_written"]),
        "json_operations": ("JSON Operations", "utils/format", ["STRING", "STRING", "BOOLEAN"], ["result_json", "value", "valid"]),
        "yaml_operations": ("YAML Operations", "utils/format", ["STRING", "STRING", "BOOLEAN"], ["result_yaml", "value", "valid"]),
        "csv_to_json": ("CSV to JSON", "utils/format", ["JSON", "STRING", "INT"], ["json_file", "preview_json", "record_count"]),
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

    csv_to_json_inputs = info["csv_to_json"]["input"]
    assert set(csv_to_json_inputs["required"]) == {"csv_file"}
    assert set(csv_to_json_inputs["optional"]) == {
        "delimiter",
        "key_column",
        "nest_separator",
        "output_name",
        "pretty",
    }


def test_json_and_yaml_operation_metadata_exposes_planned_aliases() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    json_operations = set(info["json_operations"]["input"]["required"]["operation"][1]["options"])
    yaml_operations = set(info["yaml_operations"]["input"]["required"]["operation"][1]["options"])

    assert {"stringify", "pretty_print"}.issubset(json_operations)
    assert {"stringify", "pretty_print"}.issubset(yaml_operations)


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
async def test_path_operations_support_documented_relative_type_and_rewrite_modes(tmp_path: Path) -> None:
    sample = tmp_path / "reads" / "sample.fastq.gz"
    sample.parent.mkdir()
    sample.write_text("ACGT\n", encoding="utf-8")
    node = _node_class("path_operations")()

    assert await node.run(operation="relative", path=str(sample), path_b=str(tmp_path)) == ("reads/sample.fastq.gz", True)
    assert await node.run(operation="is_file", path=str(sample)) == (str(sample), True)
    assert await node.run(operation="is_dir", path=str(sample.parent)) == (str(sample.parent), True)
    assert await node.run(operation="with_suffix", path=str(sample), suffix=".bam") == (
        str(sample.with_suffix(".bam")),
        False,
    )
    assert await node.run(operation="with_name", path=str(sample), name="trimmed.fastq.gz") == (
        str(sample.with_name("trimmed.fastq.gz")),
        False,
    )


@pytest.mark.asyncio
async def test_read_file_returns_content_lines_and_line_count(tmp_path: Path) -> None:
    sample = tmp_path / "notes.txt"
    sample.write_text("alpha\nbeta\n\n", encoding="utf-8")

    content, lines, line_count = await _node_class("read_file")().run(file_path=str(sample), encoding="utf-8")

    assert content == "alpha\nbeta\n\n"
    assert lines == "alpha\nbeta\n"
    assert line_count == 3


@pytest.mark.asyncio
async def test_write_file_writes_text_and_formatted_json(tmp_path: Path) -> None:
    node = _node_class("write_file")()
    text_path = tmp_path / "out" / "notes.txt"

    written_path, bytes_written = await node.run(
        content="alpha\nbeta\n",
        file_path=str(text_path),
        format="text",
        encoding="utf-8",
    )

    assert written_path == str(text_path)
    assert text_path.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert bytes_written == len("alpha\nbeta\n".encode("utf-8"))

    json_path = tmp_path / "payload.json"
    written_path, bytes_written = await node.run(
        content='{"enabled":true,"sample":"S1"}',
        file_path=str(json_path),
        format="json",
        encoding="utf-8",
    )

    assert written_path == str(json_path)
    assert json_path.read_text(encoding="utf-8") == '{\n  "enabled": true,\n  "sample": "S1"\n}\n'
    assert bytes_written == len(json_path.read_bytes())


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


@pytest.mark.asyncio
async def test_yaml_operations_set_preserves_structured_values() -> None:
    node = _node_class("yaml_operations")()

    result_yaml, value, valid = await node.run(
        operation="set",
        yaml_input="sample: S1\n",
        key="metrics",
        value='{"depth": 24, "flags": ["pass", "review"]}',
    )

    result_json, _, _ = await node.run(operation="to_json", yaml_input=result_yaml)
    result = json.loads(result_json)
    assert result["metrics"] == {"depth": 24, "flags": ["pass", "review"]}
    assert value == '{"depth": 24, "flags": ["pass", "review"]}'
    assert valid is True


@pytest.mark.asyncio
async def test_csv_to_json_writes_array_output_and_preview(tmp_path: Path) -> None:
    table = tmp_path / "samples.csv"
    table.write_text("sample,depth,status\nS1,12,pass\nS2,8,warn\n", encoding="utf-8")

    json_path, preview_json, record_count = await _node_class("csv_to_json")().run(
        csv_file=str(table),
        delimiter="auto",
        pretty=True,
        context=type("Context", (), {"node_dir": tmp_path})(),
    )

    output = Path(json_path)
    assert output.name == "samples.json"
    assert record_count == 2
    assert json.loads(output.read_text(encoding="utf-8")) == [
        {"sample": "S1", "depth": "12", "status": "pass"},
        {"sample": "S2", "depth": "8", "status": "warn"},
    ]
    assert json.loads(preview_json) == [{"sample": "S1", "depth": "12", "status": "pass"}]


@pytest.mark.asyncio
async def test_csv_to_json_supports_keyed_object_and_nested_keys(tmp_path: Path) -> None:
    table = tmp_path / "samples.tsv"
    table.write_text(
        "sample\tmetrics.depth\tmetrics.status\n"
        "S1\t12\tpass\n"
        "S2\t8\twarn\n",
        encoding="utf-8",
    )

    json_path, preview_json, record_count = await _node_class("csv_to_json")().run(
        csv_file=str(table),
        delimiter="auto",
        key_column="sample",
        nest_separator=".",
        output_name="keyed_samples",
        context=type("Context", (), {"node_dir": tmp_path})(),
    )

    output = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert record_count == 2
    assert output == {
        "S1": {"sample": "S1", "metrics": {"depth": "12", "status": "pass"}},
        "S2": {"sample": "S2", "metrics": {"depth": "8", "status": "warn"}},
    }
    assert json.loads(preview_json) == {"S1": {"sample": "S1", "metrics": {"depth": "12", "status": "pass"}}}


@pytest.mark.asyncio
async def test_csv_to_json_rejects_duplicate_key_values(tmp_path: Path) -> None:
    table = tmp_path / "samples.csv"
    table.write_text("sample,depth\nS1,12\nS1,8\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate key_column value"):
        await _node_class("csv_to_json")().run(csv_file=str(table), key_column="sample")
