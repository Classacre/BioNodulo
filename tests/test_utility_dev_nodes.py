from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _context(tmp_path: Path, name: str) -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir()
    return SimpleNamespace(node_dir=node_dir)


def test_utility_dev_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "debug": ("Debug", "utils/dev", ["STRING"], ["value"], True, False),
        "breakpoint": ("Breakpoint", "utils/dev", ["STRING"], ["value"], True, True),
        "datetime": ("Date / Time", "utils/format", ["STRING", "INT", "STRING"], ["formatted", "timestamp", "iso"], False, False),
        "type_cast": ("Type Cast", "utils/dev", ["STRING", "INT", "FLOAT", "BOOLEAN", "FILE"], ["as_string", "as_int", "as_float", "as_bool", "as_file"], False, False),
    }

    for node_id, (display_name, category, outputs, output_names, output_node, experimental) in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == display_name
        assert node_info["category"] == category
        assert node_info["output"] == outputs
        assert node_info["output_name"] == output_names
        assert node_info["output_node"] is output_node
        assert node_info["experimental"] is experimental
        assert node_info["search_aliases"]
        assert node_info["required_executables"] == []
        assert node_info["required_conda_packages"] == []


@pytest.mark.asyncio
async def test_debug_node_formats_and_passes_value_through(capsys: pytest.CaptureFixture[str]) -> None:
    result = await _node_class("debug")().run(
        value={"sample": "S1", "depth": 30},
        label="QC",
        log_level="info",
        show_type=True,
    )

    assert result == ('{\n  "sample": "S1",\n  "depth": 30\n}',)
    captured = capsys.readouterr()
    assert "[QC]" in captured.out
    assert "dict" in captured.out
    assert '"sample": "S1"' in captured.out


@pytest.mark.asyncio
async def test_breakpoint_node_passes_through_when_disabled_or_condition_misses() -> None:
    node = _node_class("breakpoint")()

    assert await node.run(value="aligned=100", enabled=False, timeout=0) == ("aligned=100",)
    assert await node.run(value="aligned=100", enabled=True, condition="failed", timeout=0) == ("aligned=100",)


@pytest.mark.asyncio
async def test_datetime_node_parses_and_formats_fixed_dates() -> None:
    formatted, timestamp, iso = await _node_class("datetime")().run(
        operation="parse",
        date_string="2026-06-03",
        format_string="%Y/%m/%d",
        timezone="UTC",
    )

    assert formatted == "2026/06/03"
    assert timestamp > 0
    assert iso.startswith("2026-06-03T00:00:00")


@pytest.mark.asyncio
async def test_datetime_format_uses_date_string_when_provided() -> None:
    formatted, timestamp, iso = await _node_class("datetime")().run(
        operation="format",
        date_string="2026-06-03T14:30:00Z",
        format_string="%Y%m%d-%H%M",
        timezone="UTC",
    )

    assert formatted == "20260603-1430"
    assert timestamp == 1_780_497_000
    assert iso == "2026-06-03T14:30:00+00:00"


@pytest.mark.asyncio
async def test_type_cast_node_converts_scalars_and_file_content(tmp_path: Path) -> None:
    node = _node_class("type_cast")()

    assert await node.run(target_type="INT", value="30.9") == ("30", 30, 30.0, True, "")
    assert await node.run(target_type="BOOLEAN", value="off") == ("false", 0, 0.0, False, "")

    source = tmp_path / "params.txt"
    source.write_text("alpha=1\n", encoding="utf-8")
    assert await node.run(target_type="FILE_CONTENT", value=str(source)) == ("alpha=1\n", 0, 0.0, True, str(source))

    result = await node.run(
        target_type="FILE_FROM_STRING",
        value="created",
        output_name="created.txt",
        context=_context(tmp_path, "cast-file"),
    )
    output_path = Path(result[4])
    assert output_path.name == "created.txt"
    assert output_path.read_text(encoding="utf-8") == "created"
