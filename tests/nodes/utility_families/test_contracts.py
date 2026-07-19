from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import utility_collections, utility_dev, utility_file_format
from bionodulo.nodes.builtin.utility_collections_family import (
    DictionaryNode,
    FlattenNestedNode,
    ListOperationsNode,
    RegexExtractNode,
    SelectFromListNode,
    StringOperationsNode,
    TextTemplateNode,
)
from bionodulo.nodes.builtin.utility_collections_family import adapter as collections_adapter
from bionodulo.nodes.builtin.utility_dev_family import BreakpointNode, DateTimeNode, DebugNode, TypeCastNode
from bionodulo.nodes.builtin.utility_dev_family import adapter as dev_adapter
from bionodulo.nodes.builtin.utility_file_format_family import (
    CSVToJSONNode,
    FileInfoNode,
    JSONOperationsNode,
    PathOperationsNode,
    ReadFileNode,
    WriteFileNode,
    YMLOperationsNode,
)
from bionodulo.nodes.builtin.utility_file_format_family import adapter as file_adapter


FAMILIES = (
    (
        "utility_collections_family",
        utility_collections,
        collections_adapter,
        {
            "dictionary": ("dictionary", DictionaryNode),
            "flatten_nested": ("flatten_nested", FlattenNestedNode),
            "list_operations": ("list_operations", ListOperationsNode),
            "regex_extract": ("regex_extract", RegexExtractNode),
            "select_from_list": ("select_from_list", SelectFromListNode),
            "string_operations": ("string_operations", StringOperationsNode),
            "text_template": ("text_template", TextTemplateNode),
        },
    ),
    (
        "utility_file_format_family",
        utility_file_format,
        file_adapter,
        {
            "csv_to_json": ("csv_to_json", CSVToJSONNode),
            "file_info": ("file_info", FileInfoNode),
            "json_operations": ("json_operations", JSONOperationsNode),
            "path_operations": ("path_operations", PathOperationsNode),
            "read_file": ("read_file", ReadFileNode),
            "write_file": ("write_file", WriteFileNode),
            "yaml_operations": ("yaml_operations", YMLOperationsNode),
        },
    ),
    (
        "utility_dev_family",
        utility_dev,
        dev_adapter,
        {
            "breakpoint": ("breakpoint", BreakpointNode),
            "datetime": ("datetime", DateTimeNode),
            "debug": ("debug", DebugNode),
            "type_cast": ("type_cast", TypeCastNode),
        },
    ),
)


def _owned_node_classes(module: Any) -> list[type[BaseNode]]:
    return [
        candidate
        for _name, candidate in inspect.getmembers(module, inspect.isclass)
        if issubclass(candidate, BaseNode)
        and candidate is not BaseNode
        and candidate.__module__ == module.__name__
        and candidate.NODE_ID
    ]


def test_each_stable_id_has_one_focused_owner() -> None:
    for package_name, facade, adapter, owners in FAMILIES:
        assert _owned_node_classes(adapter) == []
        for node_id, (module_name, expected_class) in owners.items():
            module = importlib.import_module(f"bionodulo.nodes.builtin.{package_name}.{module_name}")
            assert _owned_node_classes(module) == [expected_class]
            assert expected_class.NODE_ID == node_id
            assert getattr(facade, expected_class.__name__) is expected_class


def test_python_and_pyyaml_authorities_are_pinned() -> None:
    for _package_name, _facade, _adapter, owners in FAMILIES:
        for _module_name, node_class in owners.values():
            assert node_class.GIT_COMMIT == "a32a426c03ce4c925bf7dcdbd2cf08fbdedd55e9"
            assert node_class.RUNTIME_VERSION == "3.12.3"
            assert node_class.RUNTIME_GIT_COMMIT == "f6650f9ad73359051f3e558c2431a109bc016664"
            assert node_class.GIT_COMMIT in node_class.SOURCE_URL
            assert all(node_class.RUNTIME_GIT_COMMIT in url for url in node_class.RUNTIME_SOURCE_URLS)
            assert node_class.REQUIRED_EXECUTABLES == []
            assert node_class.REQUIRED_CONDA_PACKAGES == []

    assert YMLOperationsNode.YAML_RUNTIME_VERSION == "6.0.3"
    assert YMLOperationsNode.YAML_RUNTIME_GIT_COMMIT == "49790e73684bebad1df05ef8d828fa12f685bffb"
    assert YMLOperationsNode.YAML_RUNTIME_GIT_COMMIT in YMLOperationsNode.YAML_RUNTIME_SOURCE_URL
    assert YMLOperationsNode.YAML_PACKAGE_CONSTRAINT == "pyyaml==6.0.3"


def test_declared_choices_and_bounds_validate_before_execution() -> None:
    assert StringOperationsNode.VALIDATE_INPUTS({"operation": "unknown", "string": "x"}) is not True
    assert RegexExtractNode.VALIDATE_INPUTS({"text": "x", "pattern": "x", "group": -1}) is not True
    assert JSONOperationsNode.VALIDATE_INPUTS(
        {"operation": "pretty", "json_input": "{}", "indent": 9}
    ) is not True
    assert BreakpointNode.VALIDATE_INPUTS({"value": "x", "timeout": -1}) is not True
    assert DateTimeNode.VALIDATE_INPUTS({"operation": "now", "timezone": "Mars"}) is not True


@pytest.mark.asyncio
async def test_representative_aliases_keep_legacy_behavior() -> None:
    assert await StringOperationsNode().run(operation="uppercase", string="atcg") == ("ATCG", 4, False)
    assert await JSONOperationsNode().run(operation="pretty_print", json_input='{"sample":"S1"}', indent=2) == (
        '{\n  "sample": "S1"\n}',
        "",
        True,
    )
    assert await TypeCastNode().run(target_type="INT", value="30.9") == ("30", 30, 30.0, True, "")


@pytest.mark.asyncio
async def test_invalid_modes_regexes_and_paths_fail_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported string operation: unknown"):
        await StringOperationsNode().run(operation="unknown", string="x")
    with pytest.raises(ValueError, match="Invalid regex pattern"):
        await RegexExtractNode().run(text="x", pattern="[")
    with pytest.raises(ValueError, match="JSON key not found: missing"):
        await JSONOperationsNode().run(operation="get", json_input="{}", key="missing")
    with pytest.raises(ValueError, match="YAML key not found: missing"):
        await YMLOperationsNode().run(operation="get", yaml_input="sample: S1\n", key="missing")
    with pytest.raises(ValueError, match="Unsupported timezone: mars"):
        await DateTimeNode().run(operation="now", timezone="Mars")


@pytest.mark.asyncio
async def test_text_encodings_are_validated_before_file_io(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("sample", encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown text encoding: not-a-codec"):
        await ReadFileNode().run(file_path=str(source), encoding="not-a-codec")
    with pytest.raises(ValueError, match="Unknown text encoding: not-a-codec"):
        await WriteFileNode().run(
            content="sample",
            file_path=str(tmp_path / "out.txt"),
            encoding="not-a-codec",
        )
    with pytest.raises(ValueError, match="Unknown text encoding: not-a-codec"):
        await TypeCastNode().run(
            target_type="FILE_FROM_STRING",
            value="sample",
            encoding="not-a-codec",
            context=SimpleNamespace(node_dir=tmp_path),
        )


def test_yaml_requires_the_pinned_safe_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "yaml", None)
    with pytest.raises(RuntimeError, match="YAML operations require PyYAML 6.0.3"):
        file_adapter._load_yaml("sample: S1\n")


@pytest.mark.asyncio
async def test_seed_zero_uses_system_randomness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collections_adapter.random, "randrange", lambda _length: 1)
    assert await SelectFromListNode().run(mode="random", items="S1,S2,S3", seed=0) == ("S2", 1)


@pytest.mark.asyncio
async def test_breakpoint_wait_is_awaitable_and_mockable(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(dev_adapter.asyncio, "sleep", fake_sleep)
    assert await BreakpointNode().run(value={"sample": "S1"}, timeout=2, label="audit") == (
        "{'sample': 'S1'}",
    )
    assert sleeps == [2]


def test_debug_and_breakpoint_accept_arbitrary_values() -> None:
    assert DebugNode.INPUT_TYPES()["required"]["value"][0] == "ANY"
    assert BreakpointNode.INPUT_TYPES()["required"]["value"][0] == "ANY"


def test_generated_output_names_cannot_escape_node_directories(tmp_path: Path) -> None:
    csv_output = CSVToJSONNode.PLAN_OUTPUTS(
        {"csv_file": "/input/samples.csv", "output_name": "../../escape"},
        tmp_path,
    )[0]
    cast_output = TypeCastNode.PLAN_OUTPUTS(
        {"target_type": "FILE_FROM_STRING", "output_name": "../../escape.txt"},
        tmp_path,
    )[0]

    assert csv_output == tmp_path / "csv_to_json" / "escape.json"
    assert cast_output == tmp_path / "type_cast" / "escape.txt"
    assert csv_output.is_relative_to(tmp_path)
    assert cast_output.is_relative_to(tmp_path)


def test_write_file_keeps_its_explicit_destination_contract(tmp_path: Path) -> None:
    destination = tmp_path / "chosen" / "result.txt"
    assert WriteFileNode.PLAN_OUTPUTS({"file_path": str(destination)}, tmp_path / "ignored") == [destination]


@pytest.mark.asyncio
async def test_runtime_generated_paths_match_planned_safe_names(tmp_path: Path) -> None:
    table = tmp_path / "samples.csv"
    table.write_text("sample,depth\nS1,12\n", encoding="utf-8")
    context = SimpleNamespace(node_dir=tmp_path)

    csv_path, preview, count = await CSVToJSONNode().run(
        csv_file=str(table),
        output_name="../../escape",
        context=context,
    )
    cast_result = await TypeCastNode().run(
        target_type="FILE_FROM_STRING",
        value="created",
        output_name="../../escape.txt",
        context=context,
    )

    assert Path(csv_path) == tmp_path / "csv_to_json" / "escape.json"
    assert json.loads(preview) == [{"sample": "S1", "depth": "12"}]
    assert count == 1
    assert Path(cast_result[4]) == tmp_path / "type_cast" / "escape.txt"
