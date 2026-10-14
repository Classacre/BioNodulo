from __future__ import annotations

import json
from pathlib import Path

import pytest

from bionodulo.provenance.workflow_embed import extract_workflow


TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
MEASUREMENTS = json.loads(
    (Path(__file__).parent / "fixtures" / "template_node_measurements.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "template", sorted(path for path in TEMPLATES.glob("*.json") if path.stem != "robust_designer"),
    ids=lambda path: path.stem,
)
def test_template_thumbnail_restores_the_current_workflow(template: Path) -> None:
    """Dragging a gallery PNG must restore the same graph as opening its JSON."""
    embedded = extract_workflow(template.with_suffix(".png"))
    assert embedded is not None, f"{template.stem} thumbnail has no workflow provenance"
    assert embedded["workflow"] == json.loads(template.read_text(encoding="utf-8"))


@pytest.mark.parametrize("filename", sorted(MEASUREMENTS))
def test_template_positions_separate_browser_measured_node_rectangles(filename: str) -> None:
    """Dimensions were measured in Chromium with the real editor and registry."""
    workflow = json.loads((TEMPLATES / filename).read_text(encoding="utf-8"))
    dimensions = MEASUREMENTS[filename]
    assert {node["id"] for node in workflow["nodes"]} == set(dimensions)
    boxes = {}
    for node in workflow["nodes"]:
        position = node["position"]
        x, y = (position["x"], position["y"]) if isinstance(position, dict) else position
        measured = dimensions[node["id"]]
        boxes[node["id"]] = (x, y, x + measured["width"], y + measured["height"])
    entries = list(boxes.items())
    for index, (left_id, left) in enumerate(entries):
        for right_id, right in entries[index + 1:]:
            assert not (left[0] < right[2] and right[0] < left[2] and left[1] < right[3] and right[1] < left[3]), (
                f"{filename}: {left_id} overlaps {right_id} using actual editor dimensions"
            )
    for edge in workflow["edges"]:
        assert boxes[edge["from"]["node"]][2] < boxes[edge["to"]["node"]][0], (
            f"{filename}: edge {edge['id']} does not flow left to right"
        )


def test_template_renderer_keeps_every_title_within_its_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Check real font bounds for all layouts, including dictionary positions."""
    pytest.importorskip("PIL")
    from PIL import ImageDraw
    from scripts.relayout_templates import render_thumbnail

    original_rectangle = ImageDraw.ImageDraw.rounded_rectangle
    original_text = ImageDraw.ImageDraw.text
    current_header = None
    rendered_titles = 0

    def rectangle(draw, coordinates, *args, **kwargs):
        nonlocal current_header
        current_header = coordinates
        return original_rectangle(draw, coordinates, *args, **kwargs)

    def text(draw, coordinates, value, *args, **kwargs):
        nonlocal rendered_titles
        bounds = draw.textbbox(coordinates, value, font=kwargs.get("font"))
        assert current_header is not None
        assert bounds[0] >= current_header[0]
        assert bounds[1] >= current_header[1]
        assert bounds[2] <= current_header[2]
        assert bounds[3] <= current_header[3]
        rendered_titles += 1
        return original_text(draw, coordinates, value, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "rounded_rectangle", rectangle)
    monkeypatch.setattr(ImageDraw.ImageDraw, "text", text)
    for template in sorted(TEMPLATES.glob("*.json")):
        if template.stem != "robust_designer":
            render_thumbnail(json.loads(template.read_text(encoding="utf-8")), measurements=MEASUREMENTS[template.name])
    assert rendered_titles > 0
