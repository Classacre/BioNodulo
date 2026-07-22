"""Tests for automatic truncated HEAD previews of node outputs.

Covers the standalone ``head_preview`` helper (text head, binary info card,
truncation, escaping) and the executor wiring that registers a head preview
for nodes lacking a visual preview without overriding existing ones.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution import head_preview as hp
from bionodulo.execution.executor import ExecutionContext, WorkflowExecutor
from bionodulo.nodes.builtin.qc import QualiMapNode


# ---------------------------------------------------------------------------
# Standalone helper
# ---------------------------------------------------------------------------


def test_text_fasta_head_preview_is_truncated_and_escaped(tmp_path: Path) -> None:
    fasta = tmp_path / "seqs.fasta"
    # 200 lines, well past the default 60-line cap, with HTML-special chars.
    lines = [f">seq{i} <tag>&amp" for i in range(100)]
    fasta.write_text("\n".join(lines) + "\n", encoding="utf-8")

    out = hp.write_head_preview(fasta, tmp_path / "out", max_lines=60)

    assert out is not None
    assert out.suffix == ".html"
    html = out.read_text(encoding="utf-8")
    assert "<pre>" in html
    # Escaped, not raw.
    assert "&lt;tag&gt;" in html
    assert "<tag>" not in html.split("<pre>", 1)[1]
    # Truncation note present and only the head is rendered (content escaped).
    assert "showing first 60" in html
    assert "&gt;seq0 " in html
    assert "&gt;seq99 " not in html


def test_text_head_caps_bytes(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_text("A" * (200 * 1024), encoding="utf-8")  # 200 KB, one line

    out = hp.write_head_preview(big, tmp_path / "out", max_bytes=64 * 1024)

    assert out is not None
    html = out.read_text(encoding="utf-8")
    assert "truncated at" in html
    # Only the capped slice (64 KB of 'A') made it into the body, not 200 KB.
    assert html.count("A") <= 64 * 1024 + 16


def test_binary_file_yields_info_card_not_dump(tmp_path: Path) -> None:
    bam = tmp_path / "alignment.bam"
    payload = bytes(range(256)) * 64  # non-UTF-8 binary bytes
    bam.write_bytes(payload)

    out = hp.write_head_preview(bam, tmp_path / "out")

    assert out is not None
    html = out.read_text(encoding="utf-8")
    assert "Binary file" in html
    assert "alignment.bam" in html
    assert "<pre>" not in html  # never a raw dump
    # The raw binary payload must not be embedded.
    assert payload.decode("latin-1") not in html


def test_non_utf8_unknown_extension_falls_back_to_info_card(tmp_path: Path) -> None:
    weird = tmp_path / "data.xyz"  # unknown ext, binary content
    weird.write_bytes(b"\xff\xfe\x00\x01\x02not-text\x80\x81")

    out = hp.write_head_preview(weird, tmp_path / "out")

    assert out is not None
    html = out.read_text(encoding="utf-8")
    assert "Binary file" in html
    assert "<pre>" not in html


def test_native_extension_is_skipped(tmp_path: Path) -> None:
    for name in ("plot.png", "report.html", "table.csv"):
        f = tmp_path / name
        f.write_text("x", encoding="utf-8")
        assert hp.write_head_preview(f, tmp_path / "out") is None


def test_missing_file_returns_none(tmp_path: Path) -> None:
    assert hp.write_head_preview(tmp_path / "nope.txt", tmp_path / "out") is None


def test_qualimap_bundle_opts_out_of_automatic_single_file_previews(tmp_path: Path) -> None:
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    report = report_dir / QualiMapNode.REPORT_FILENAME
    report.write_text('<link rel="stylesheet" href="css/qualimap.css">', encoding="utf-8")
    manual = tmp_path / "bundle-aware-preview.html"
    manual.write_text("<html>served deliberately</html>", encoding="utf-8")

    ctx = ExecutionContext(
        run_id="qualimap-preview-run",
        node_id="qualimap_001",
        node_type=QualiMapNode.NODE_ID,
        node_dir=tmp_path,
        workspace_dir=tmp_path,
        params={},
        api_secrets={},
        emit=lambda *_: None,
        cancel_event=asyncio.Event(),
    )
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache")
    result = {"outputs": {"report": str(report), "report_dir": str(report_dir)}}

    assert QualiMapNode.AUTO_PREVIEW is False
    assert executor._collect_previews(ctx, result, QualiMapNode) == []
    assert not (report_dir / "_head_preview").exists()

    ctx.register_preview(manual, label="Bundle-aware preview")
    assert executor._collect_previews(ctx, result, QualiMapNode) == [
        {
            "path": str(manual),
            "label": "Bundle-aware preview",
            "node_id": "qualimap_001",
        }
    ]


# ---------------------------------------------------------------------------
# Executor wiring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executor_registers_head_preview_for_text_output(tmp_path: Path) -> None:
    class FastaWriterNode:
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            out = context.node_dir / "seqs.fasta"
            out.write_text(">a\nACGT\n>b\nTTTT\n", encoding="utf-8")
            return {"outputs": {"out": str(out)}}

    class Registry:
        def get(self, _node_type: str) -> type[FastaWriterNode]:
            return FastaWriterNode

    workflow = {
        "nodes": [{"id": "writer", "type": "fasta_writer", "outputs": {"out": {}}}],
        "edges": [],
    }
    executor = WorkflowExecutor(
        workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry()
    )

    result = await executor.execute("head-text-run", workflow, force=True)

    head = [
        p
        for p in result["previews"]
        if p["node_id"] == "writer" and p["path"].endswith("head_preview.html")
    ]
    assert head, f"expected a head preview, got {result['previews']}"
    html = Path(head[0]["path"]).read_text(encoding="utf-8")
    assert "<pre>" in html and "ACGT" in html


@pytest.mark.asyncio
async def test_executor_does_not_override_existing_visual_preview(tmp_path: Path) -> None:
    class ChartNode:
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            # Node produces a plain-text output AND registers its own HTML chart.
            txt = context.node_dir / "data.fasta"
            txt.write_text(">a\nACGT\n", encoding="utf-8")
            chart = context.node_dir / "chart.html"
            chart.write_text("<html><body>my chart</body></html>", encoding="utf-8")
            context.register_preview(chart, label="Chart")
            return {"outputs": {"out": str(txt)}}

    class Registry:
        def get(self, _node_type: str) -> type[ChartNode]:
            return ChartNode

    workflow = {
        "nodes": [{"id": "charty", "type": "chart", "outputs": {"out": {}}}],
        "edges": [],
    }
    executor = WorkflowExecutor(
        workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry()
    )

    result = await executor.execute("head-chart-run", workflow, force=True)

    charty = [p for p in result["previews"] if p["node_id"] == "charty"]
    # The node's own chart preview survives...
    assert any(p["path"].endswith("chart.html") for p in charty)
    # ...and no auto head preview was generated to override it.
    assert not any(p["path"].endswith("head_preview.html") for p in charty)


@pytest.mark.asyncio
async def test_executor_head_preview_for_binary_output_is_info_card(tmp_path: Path) -> None:
    class BamWriterNode:
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("out",)

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            out = context.node_dir / "reads.bam"
            out.write_bytes(bytes(range(256)) * 32)
            return {"outputs": {"out": str(out)}}

    class Registry:
        def get(self, _node_type: str) -> type[BamWriterNode]:
            return BamWriterNode

    workflow = {
        "nodes": [{"id": "bamw", "type": "bam_writer", "outputs": {"out": {}}}],
        "edges": [],
    }
    executor = WorkflowExecutor(
        workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry()
    )

    result = await executor.execute("head-bam-run", workflow, force=True)

    head = [
        p
        for p in result["previews"]
        if p["node_id"] == "bamw" and p["path"].endswith("head_preview.html")
    ]
    assert head, f"expected a head preview, got {result['previews']}"
    html = Path(head[0]["path"]).read_text(encoding="utf-8")
    assert "Binary file" in html and "<pre>" not in html
