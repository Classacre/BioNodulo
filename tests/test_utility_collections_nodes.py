from __future__ import annotations

import json

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_utility_collection_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "string_operations": ("String Operations", "utils", ["STRING", "INT", "BOOLEAN"], ["result", "length", "matched"]),
        "regex_extract": ("Regex Extract", "utils", ["STRING", "INT"], ["matches_json", "count"]),
        "text_template": ("Text Template", "utils", ["STRING"], ["output"]),
        "list_operations": ("List Operations", "utils", ["STRING", "INT", "BOOLEAN"], ["result", "length", "contains"]),
        "select_from_list": ("Select From List", "utils", ["STRING", "INT"], ["item", "index"]),
        "flatten_nested": ("Flatten Nested", "utils", ["STRING", "INT"], ["flattened_json", "count"]),
        "dictionary": ("Dictionary", "utils", ["STRING", "STRING", "INT"], ["result_json", "value", "count"]),
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
async def test_string_operations_support_required_string_modes() -> None:
    node = _node_class("string_operations")()

    assert await node.run(operation="concat", string="sample", string_b="R1", delimiter="_") == ("sample_R1", 9, False)
    assert await node.run(operation="upper", string="atcg") == ("ATCG", 4, False)
    assert await node.run(operation="lower", string="ATCG") == ("atcg", 4, False)
    assert await node.run(operation="regex_replace", string="sample-001", pattern=r"\d+", replacement="002") == (
        "sample-002",
        10,
        True,
    )
    assert await node.run(operation="split", string="S1,S2,S3", delimiter=",", index=1) == ("S2", 3, True)
    assert await node.run(operation="length", string="BioNodulo") == ("BioNodulo", 9, False)
    assert await node.run(operation="contains", string="sample_R1.fastq", substring="R1") == ("", 0, True)


@pytest.mark.asyncio
async def test_string_operations_reject_bad_inputs_clearly() -> None:
    node = _node_class("string_operations")()

    with pytest.raises(ValueError, match="Unsupported string operation"):
        await node.run(operation="reverse_words", string="abc")

    with pytest.raises(ValueError, match="regex_replace requires a non-empty pattern"):
        await node.run(operation="regex_replace", string="abc", pattern="")

    with pytest.raises(ValueError, match="split index 5 is out of range"):
        await node.run(operation="split", string="a,b", delimiter=",", index=5)


@pytest.mark.asyncio
async def test_regex_extract_returns_capture_group_matches_as_json() -> None:
    node = _node_class("regex_extract")()

    matches_json, count = await node.run(
        text="sample=S1 depth=12\nsample=S2 depth=25",
        pattern=r"sample=(S\d+)\s+depth=(\d+)",
        group=1,
    )

    assert json.loads(matches_json) == ["S1", "S2"]
    assert count == 2


@pytest.mark.asyncio
async def test_regex_extract_supports_full_match_and_rejects_bad_inputs() -> None:
    node = _node_class("regex_extract")()

    matches_json, count = await node.run(text="chr1:10-20 chr2:30-40", pattern=r"chr\d+:\d+-\d+", group=0)
    assert json.loads(matches_json) == ["chr1:10-20", "chr2:30-40"]
    assert count == 2

    with pytest.raises(ValueError, match="pattern is required"):
        await node.run(text="abc", pattern="", group=0)

    with pytest.raises(ValueError, match="group 3 is out of range"):
        await node.run(text="abc-123", pattern=r"([a-z]+)-(\d+)", group=3)

    with pytest.raises(ValueError, match="Invalid regex pattern"):
        await node.run(text="abc", pattern="[", group=0)


@pytest.mark.asyncio
async def test_text_template_renders_json_variables() -> None:
    node = _node_class("text_template")()

    (output,) = await node.run(
        template="sample=${sample}\ncondition=${condition}\nreads=${reads}",
        variables='{"sample": "S1", "condition": "tumor", "reads": 42}',
    )

    assert output == "sample=S1\ncondition=tumor\nreads=42"


@pytest.mark.asyncio
async def test_text_template_rejects_invalid_variables_and_missing_keys() -> None:
    node = _node_class("text_template")()

    with pytest.raises(ValueError, match="variables must be a JSON object"):
        await node.run(template="${sample}", variables='["S1"]')

    with pytest.raises(ValueError, match="Missing template variable: sample"):
        await node.run(template="${sample}", variables="{}")

    with pytest.raises(ValueError, match="Invalid template"):
        await node.run(template="${sample", variables='{"sample": "S1"}')


@pytest.mark.asyncio
async def test_list_operations_parse_json_and_text_inputs() -> None:
    node = _node_class("list_operations")()

    assert await node.run(operation="join", items='["S1", "S2", "S3"]', delimiter="|") == ("S1|S2|S3", 3, False)
    assert await node.run(operation="append", items="S1\nS2", item="S3") == ('["S1", "S2", "S3"]', 3, False)
    assert await node.run(operation="prepend", items="S2,S3", item="S1") == ('["S1", "S2", "S3"]', 3, False)
    assert await node.run(operation="unique", items="S1\nS2\nS1") == ('["S1", "S2"]', 2, False)
    assert await node.run(operation="sort", items='["10", "2", "1"]') == ('["1", "2", "10"]', 3, False)
    assert await node.run(operation="length", items="S1,S2") == ("", 2, False)
    assert await node.run(operation="contains", items="S1\nS2", item="S2") == ("", 2, True)


@pytest.mark.asyncio
async def test_list_operations_reject_bad_inputs_clearly() -> None:
    node = _node_class("list_operations")()

    with pytest.raises(ValueError, match="Unsupported list operation"):
        await node.run(operation="shuffle", items="S1,S2")

    with pytest.raises(ValueError, match="items JSON must be a list"):
        await node.run(operation="length", items='{"S1": true}')


@pytest.mark.asyncio
async def test_select_from_list_selects_by_index_and_modes() -> None:
    node = _node_class("select_from_list")()

    assert await node.run(mode="index", items='["S1", "S2", "S3"]', index=1) == ("S2", 1)
    assert await node.run(mode="first", items="S1,S2,S3") == ("S1", 0)
    assert await node.run(mode="last", items="S1\nS2\nS3") == ("S3", 2)
    item, index = await node.run(mode="random", items="S1\nS2\nS3", seed=7)
    assert item in {"S1", "S2", "S3"}
    assert index in {0, 1, 2}


@pytest.mark.asyncio
async def test_select_from_list_rejects_bad_inputs_clearly() -> None:
    node = _node_class("select_from_list")()

    with pytest.raises(ValueError, match="Cannot select from an empty list"):
        await node.run(mode="first", items="")

    with pytest.raises(ValueError, match="index 4 is out of range"):
        await node.run(mode="index", items="S1,S2", index=4)


@pytest.mark.asyncio
async def test_flatten_nested_flattens_json_lists_and_object_values() -> None:
    node = _node_class("flatten_nested")()

    flattened_json, count = await node.run(data='["S1", ["S2", ["S3"]], {"sample": "S4", "lanes": ["L1", "L2"]}]')

    assert json.loads(flattened_json) == ["S1", "S2", "S3", "S4", "L1", "L2"]
    assert count == 6


@pytest.mark.asyncio
async def test_flatten_nested_respects_max_depth() -> None:
    node = _node_class("flatten_nested")()

    flattened_json, count = await node.run(data='["S1", ["S2", ["S3"]]]', max_depth=1)

    assert json.loads(flattened_json) == ["S1", "S2", ["S3"]]
    assert count == 3

    shallow_json, shallow_count = await node.run(data='["S1", ["S2", ["S3"]]]', max_depth=0)
    assert json.loads(shallow_json) == ["S1", ["S2", ["S3"]]]
    assert shallow_count == 2


@pytest.mark.asyncio
async def test_flatten_nested_handles_scalars_and_rejects_invalid_json() -> None:
    node = _node_class("flatten_nested")()

    assert await node.run(data='"S1"') == ('["S1"]', 1)

    with pytest.raises(ValueError, match="data must be valid JSON"):
        await node.run(data="[")


@pytest.mark.asyncio
async def test_dictionary_operations_support_json_objects() -> None:
    node = _node_class("dictionary")()

    source = '{"sample": "S1", "condition": "tumor"}'
    assert await node.run(operation="get", dictionary=source, key="condition") == (source, "tumor", 2)

    set_json, set_value, set_count = await node.run(operation="set", dictionary=source, key="batch", value="A")
    assert json.loads(set_json) == {"sample": "S1", "condition": "tumor", "batch": "A"}
    assert set_value == "A"
    assert set_count == 3

    keys_json, keys_value, keys_count = await node.run(operation="keys", dictionary=source)
    assert json.loads(keys_json) == {"sample": "S1", "condition": "tumor"}
    assert keys_value == '["sample", "condition"]'
    assert keys_count == 2

    values_json, values_value, values_count = await node.run(operation="values", dictionary=source)
    assert json.loads(values_json) == {"sample": "S1", "condition": "tumor"}
    assert values_value == '["S1", "tumor"]'
    assert values_count == 2

    merged_json, merged_value, merged_count = await node.run(
        operation="merge",
        dictionary=source,
        dictionary_b='{"condition": "normal", "replicate": "1"}',
    )
    assert json.loads(merged_json) == {"sample": "S1", "condition": "normal", "replicate": "1"}
    assert merged_value == ""
    assert merged_count == 3

    assert await node.run(operation="has_key", dictionary=source, key="sample") == (source, "true", 2)


@pytest.mark.asyncio
async def test_dictionary_operations_reject_bad_inputs_clearly() -> None:
    node = _node_class("dictionary")()

    with pytest.raises(ValueError, match="dictionary must be a JSON object"):
        await node.run(operation="get", dictionary='["S1"]', key="sample")

    with pytest.raises(ValueError, match="Unsupported dictionary operation"):
        await node.run(operation="delete", dictionary="{}", key="sample")
