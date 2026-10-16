"""Native horizontal bar labels fit without losing category/value identity."""

from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from bionodulo.nodes.builtin.visualization_family.adapter import (
    BarDatum,
    _bar_label_lines,
    _layout,
    _render_bar_svg,
)


SVG = {"s": "http://www.w3.org/2000/svg"}


@pytest.mark.parametrize("width", [320, 800, 1500])
def test_long_category_and_numeric_labels_remain_bounded_without_losing_rows(
    tmp_path: Path, width: int,
) -> None:
    categories = [
        "A long category name with several words and an independent stratified suffix",
        'A <category> & "quoted" label',
        "W" * 120,
        "Δ Unicode category " * 12,
    ]
    values = [9.87654e100, -8.76543e100, 0.0, 0.123456789]
    rows = [BarDatum(category, value, "Value") for category, value in zip(categories, values)]
    path = tmp_path / "horizontal.svg"
    _render_bar_svg(path, rows=rows, layout=_layout(width, 420), title="Long categories",
                    orientation="horizontal", color="steelblue", show_values=True)
    root = ET.parse(path).getroot()
    bars = root.findall('s:rect[@data-category]', SVG)
    assert [bar.attrib["data-category"] for bar in bars] == categories
    assert [float(bar.attrib["data-value"]) for bar in bars] == pytest.approx(values, rel=1e-5)
    assert all(float(bar.attrib["width"]) >= 0 for bar in bars)
    plot = root.findall("s:rect", SVG)[1]
    assert float(plot.attrib["width"]) >= width * 0.4
    assert float(plot.attrib["x"]) <= min(360, int(width * 0.34))
    labels = root.findall('s:g[@class="bar-category-label"]', SVG)
    assert [label.find("s:title", SVG).text for label in labels] == categories
    assert any("…" in "".join(label.itertext()) for label in labels)
    for label in labels:
        texts = label.findall("s:text", SVG)
        assert 1 <= len(texts) <= 2
        for text in texts:
            x = float(text.attrib["x"])
            length = float(text.attrib["textLength"])
            assert x - length >= 13
            assert x < float(plot.attrib["x"])
            assert 0 < float(text.attrib["y"]) < 420
            assert text.attrib["lengthAdjust"] == "spacingAndGlyphs"
    for text in root.findall('s:text[@class="bar-value-label"]', SVG):
        x = float(text.attrib["x"])
        length = float(text.attrib["textLength"])
        left, right = (x, x + length) if text.attrib["text-anchor"] == "start" else (x - length, x)
        assert 0 <= left < right <= width - 11


def test_wrapping_retains_short_labels_and_bounds_extremely_long_tokens() -> None:
    assert _bar_label_lines("short", 100, 12, 2) == ["short"]
    assert _bar_label_lines("first second third fourth", 80, 12, 2) == ["first second", "third fourth"]
    lines = _bar_label_lines("W" * 100_000, 100, 12, 2)
    assert len(lines) == 2 and lines[-1].endswith("…")
    assert sum(len(line) for line in lines) < 30


def test_horizontal_values_can_be_hidden_without_affecting_bars(tmp_path: Path) -> None:
    path = tmp_path / "no-values.svg"
    _render_bar_svg(path, rows=[BarDatum("A category " * 20, 4.0, "Value")],
                    layout=_layout(800, 420), title="No values", orientation="horizontal",
                    color="steelblue", show_values=False)
    root = ET.parse(path).getroot()
    assert len(root.findall('s:rect[@data-category]', SVG)) == 1
    assert root.findall('s:text[@class="bar-value-label"]', SVG) == []


def test_updated_bar_renderer_does_not_reuse_a_valid_legacy_cached_svg(tmp_path: Path) -> None:
    from bionodulo.execution.cache import CacheStore
    from bionodulo.nodes.builtin.visualization_family.bar_chart import BarChartNode

    old_svg = tmp_path / "legacy.svg"
    old_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    cache = CacheStore(tmp_path / "cache")
    try:
        arguments = {"node_id": "chart", "node_type": BarChartNode.NODE_ID,
                     "params": {"format": "svg", "orientation": "horizontal"},
                     "inputs": {"table": "same-table.tsv"}, "upstream_keys": {}}
        legacy_key = cache.cache_key_for_node(**arguments, tool_version="1.0.0")
        cache.write_marker(legacy_key, {"chart_image": str(old_svg)})
        assert cache.is_hit(legacy_key)
        current_key = cache.cache_key_for_node(**arguments, tool_version=BarChartNode.VERSION)
        assert current_key != legacy_key
        assert not cache.is_hit(current_key)
    finally:
        cache.close()
