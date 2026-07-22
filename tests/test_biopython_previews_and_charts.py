"""Tests for the Biopython-pipeline fixes: previews, the text_preview node,
seq-stats CSV output, and labelled PNG charts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from bionodulo.nodes.builtin import _bitmap_font as font
from bionodulo.nodes.builtin.biopython_nodes import SequenceStatsNode
from bionodulo.nodes.builtin.utils import TextPreviewNode
from bionodulo.nodes.builtin.visualization import BarChartNode


def _context(tmp_path: Path) -> SimpleNamespace:
    previews: list[dict] = []
    ctx = SimpleNamespace(node_dir=tmp_path, node_id="n", run_id="r", previews=previews)
    ctx.register_preview = lambda path, label="": previews.append({"path": str(path), "label": label})
    return ctx


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_text_preview_renders_fasta_head_as_html(tmp_path: Path) -> None:
    fasta = tmp_path / "seqs.fasta"
    fasta.write_text(">a\nACGT\n>b\nTTTT\n", encoding="utf-8")
    ctx = _context(tmp_path)

    _run(TextPreviewNode().run(file=str(fasta), max_lines=10, context=ctx))

    assert ctx.previews, "text_preview must register a preview"
    html = Path(ctx.previews[-1]["path"]).read_text(encoding="utf-8")
    assert "<pre>" in html and "ACGT" in html
    assert ctx.previews[-1]["path"].endswith(".html")


def test_text_preview_rejects_binary_extension() -> None:
    verdict = TextPreviewNode.VALIDATE_INPUTS({"file": "/tmp/x.png"})
    assert verdict is not True
    assert "binary" in str(verdict).lower()


def test_seq_stats_emits_csv_for_charting(tmp_path: Path) -> None:
    fasta = tmp_path / "in.fasta"
    fasta.write_text(">s1\nACGTACGTGG\n>s2\nTTTTACGTAC\n", encoding="utf-8")
    ctx = _context(tmp_path)

    out = _run(SequenceStatsNode().run(input_file=str(fasta), format="fasta", context=ctx))

    assert SequenceStatsNode.RETURN_NAMES == ("stats_json", "stats_tsv", "stats_csv")
    csv_path = Path(out[2])
    assert csv_path.name == "stats.csv"
    header = csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert header == "id,length,gc_content,molecular_weight,molecular_weight_error"


def test_bitmap_font_draws_ink_into_buffer() -> None:
    w, h = 60, 12
    pixels = bytearray([255, 255, 255]) * (w * h)
    font.draw_text(pixels, w, h, 1, 2, "AB1", (0, 0, 0), scale=1)
    # At least some pixels must have been painted black.
    assert any(pixels[i] == 0 for i in range(0, len(pixels), 3))
    assert font.text_width("AB", 1) == 2 * font.char_width(1)


def test_bar_chart_png_contains_label_ink(tmp_path: Path) -> None:
    table = tmp_path / "d.csv"
    table.write_text("id,length\nNR_1,1500\nNR_2,1421\n", encoding="utf-8")
    ctx = _context(tmp_path)

    titled = _run(BarChartNode().run(
        table=str(table), x_column="id", y_column="length",
        orientation="horizontal", title="Sequence Lengths", format="png", context=ctx,
    ))
    titled_bytes = Path(titled["outputs"]["chart_image"]).read_bytes()

    ctx2 = _context(tmp_path / "b")
    (tmp_path / "b").mkdir()
    untitled = _run(BarChartNode().run(
        table=str(table), x_column="id", y_column="length",
        orientation="horizontal", title="", format="png", context=ctx2,
    ))
    untitled_bytes = Path(untitled["outputs"]["chart_image"]).read_bytes()

    # Drawing a title must change the rendered pixels (text ink present).
    assert titled_bytes != untitled_bytes
