from __future__ import annotations

import asyncio
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.builtin.reporting import HTMLReportNode as FacadeHTMLReportNode
from bionodulo.nodes.builtin.reporting_family.html_report import HTMLReportNode
from bionodulo.nodes.builtin.reporting_family.pdf_report import PDFReportNode
from bionodulo.nodes.builtin.reporting_family.qc_dashboard import QCDashboardNode
from bionodulo.nodes.builtin.utility_preview_family.collect_files import CollectFilesNode
from bionodulo.nodes.builtin.utility_preview_family.generic_command import GenericCommandNode
from bionodulo.nodes.builtin.utility_preview_family.html_preview import HtmlPreviewNode
from bionodulo.nodes.builtin.utility_preview_family.image_preview import ImagePreviewNode
from bionodulo.nodes.builtin.utility_preview_family.merge_vcf import MergeVCFNode
from bionodulo.nodes.builtin.utility_preview_family.note import NoteNode
from bionodulo.nodes.builtin.utility_preview_family.reroute import RerouteNode
from bionodulo.nodes.builtin.utility_preview_family.table_preview import TablePreviewNode
from bionodulo.nodes.builtin.utility_preview_family.text_preview import TextPreviewNode
from bionodulo.nodes.builtin.utility_preview_family.view_text_file import ViewTextFileNode
from bionodulo.nodes.builtin.utils import TextPreviewNode as FacadeTextPreviewNode
from bionodulo.nodes.registry import NodeRegistry
from scripts.compile_catalog import EXPECTED_NODE_COUNT  # live catalog size: sealed ledger + declared post-baseline nodes


NODE_MODULES = {
    "collect_files": "bionodulo.nodes.builtin.utility_preview_family.collect_files",
    "generic_command": "bionodulo.nodes.builtin.utility_preview_family.generic_command",
    "html_preview": "bionodulo.nodes.builtin.utility_preview_family.html_preview",
    "image_preview": "bionodulo.nodes.builtin.utility_preview_family.image_preview",
    "merge_vcf": "bionodulo.nodes.builtin.utility_preview_family.merge_vcf",
    "note": "bionodulo.nodes.builtin.utility_preview_family.note",
    "reroute": "bionodulo.nodes.builtin.utility_preview_family.reroute",
    "table_preview": "bionodulo.nodes.builtin.utility_preview_family.table_preview",
    "text_preview": "bionodulo.nodes.builtin.utility_preview_family.text_preview",
    "view_text_file": "bionodulo.nodes.builtin.utility_preview_family.view_text_file",
    "html_report": "bionodulo.nodes.builtin.reporting_family.html_report",
    "pdf_report": "bionodulo.nodes.builtin.reporting_family.pdf_report",
    "qc_dashboard": "bionodulo.nodes.builtin.reporting_family.qc_dashboard",
}


def _context(tmp_path: Path) -> SimpleNamespace:
    previews: list[tuple[str, str]] = []
    return SimpleNamespace(
        node_dir=tmp_path,
        previews=previews,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )


def test_family_has_focused_ownership_and_keeps_943_ids() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert len(registry.object_info()) == EXPECTED_NODE_COUNT
    assert {node_id: registry.get(node_id).__module__ for node_id in NODE_MODULES} == NODE_MODULES
    assert FacadeTextPreviewNode is TextPreviewNode
    assert FacadeHTMLReportNode is HTMLReportNode


def test_family_records_exact_source_authorities() -> None:
    assert TextPreviewNode.SOURCE_AUTHORITIES["CPython"] == (
        "3.12.13",
        "3bb231a6a5dc02b95658877318bf61501a7209e9",
    )
    assert HTMLReportNode.SOURCE_AUTHORITIES["BioNodulo reporting baseline"] == (
        "7523e9aaae5e1c6c3badb23b6b43a1d7798b9429",
        "8df764297b6cb3e452adc6ad556223074795d96b",
    )
    assert MergeVCFNode.VERSION == "1.24"
    assert MergeVCFNode.GIT_COMMIT == "fb9f0f783e0f67d734f6fa7fe4df9d230522f196"
    assert MergeVCFNode.CONDA_PACKAGE_CONSTRAINTS == {"bcftools": "1.24"}
    assert PDFReportNode.PDF_SPEC_VERSION == "1.4"


@pytest.mark.asyncio
async def test_generic_command_captures_stdout_and_honors_cwd_and_timeout(tmp_path: Path) -> None:
    working_dir = tmp_path / "working"
    working_dir.mkdir()

    class RecordingContext:
        node_dir = tmp_path
        command: str | None = None
        kwargs: dict[str, Any] = {}

        async def run_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
            self.command = command
            self.kwargs = kwargs
            Path(kwargs["stdout_path"]).write_text("captured\n", encoding="utf-8")
            Path(kwargs["stderr_path"]).write_text("", encoding="utf-8")
            return {"returncode": 0, "stdout": "captured\n", "stderr": ""}

    context = RecordingContext()
    result = await GenericCommandNode().run(
        command="printf '%s\\n' 'a b' | sed 's/a/A/'",
        working_dir=str(working_dir),
        timeout=17,
        context=context,
    )

    assert context.command == "printf '%s\\n' 'a b' | sed 's/a/A/'"
    assert context.kwargs["cwd"] == working_dir
    assert context.kwargs["timeout"] == 17
    assert Path(result[0]).name == "output.txt"
    assert Path(result[0]).read_text(encoding="utf-8") == "captured\n"


@pytest.mark.asyncio
async def test_generic_command_propagates_timeout(tmp_path: Path) -> None:
    class TimeoutContext:
        node_dir = tmp_path

        async def run_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
            raise asyncio.TimeoutError

    with pytest.raises(asyncio.TimeoutError):
        await GenericCommandNode().run(command="sleep forever", timeout=1, context=TimeoutContext())


def test_merge_vcf_uses_documented_no_index_argv_and_native_filename() -> None:
    inputs = {
        "vcfs": ["tumor.vcf.gz", "normal.vcf.gz"],
        "force_samples": True,
        "merge": "both",
        "output": "/work/merge_vcf",
    }

    assert MergeVCFNode.render_command(inputs) == [
        "bcftools",
        "merge",
        "--no-index",
        "--force-samples",
        "--merge",
        "both",
        "-Oz",
        "-o",
        "/work/merge_vcf/merged.vcf.gz",
        "tumor.vcf.gz",
        "normal.vcf.gz",
    ]
    assert "at least 2" in str(MergeVCFNode.VALIDATE_INPUTS({"vcfs": ["one.vcf.gz"]}))


@pytest.mark.asyncio
async def test_collect_files_recreates_output_and_rejects_collisions(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    first.write_text("first", encoding="utf-8")
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "nested.txt").write_text("nested", encoding="utf-8")
    stale = tmp_path / "bundle"
    stale.mkdir()
    (stale / "stale.txt").write_text("stale", encoding="utf-8")

    result = await CollectFilesNode().run(
        files=[str(source_dir), str(first)],
        output_name="bundle",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    output = Path(result[0])
    assert sorted(path.name for path in output.iterdir()) == ["first.txt", "source"]
    assert not (output / "stale.txt").exists()
    duplicate_dir = tmp_path / "other"
    duplicate_dir.mkdir()
    duplicate = duplicate_dir / "first.txt"
    duplicate.write_text("duplicate", encoding="utf-8")
    assert "basename collision" in str(CollectFilesNode.VALIDATE_INPUTS({"files": [str(first), str(duplicate)]}))


@pytest.mark.asyncio
async def test_view_text_file_is_bounded_and_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("one\ntwo\nthree\n", encoding="utf-8")

    assert await ViewTextFileNode().run(file=str(source), max_lines=2) == ("one\ntwo\n... (2 lines shown)",)
    with pytest.raises(ValueError, match="not found"):
        await ViewTextFileNode().run(file=str(tmp_path / "missing.txt"), max_lines=2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node_class", "filename", "label"),
    [(ImagePreviewNode, "plot.png", "Image Preview"), (HtmlPreviewNode, "report.html", "HTML Preview")],
)
async def test_visual_sinks_require_regular_files_and_register_preview(
    tmp_path: Path,
    node_class: type,
    filename: str,
    label: str,
) -> None:
    source = tmp_path / filename
    source.write_text("payload", encoding="utf-8")
    context = _context(tmp_path)

    assert await node_class().run(file=str(source), context=context) == ()
    assert context.previews == [(str(source), label)]
    directory = tmp_path / f"directory{source.suffix}"
    directory.mkdir()
    assert "not a regular file" in str(node_class.VALIDATE_INPUTS({"file": str(directory)}))


@pytest.mark.asyncio
async def test_table_preview_parses_quoted_delimiters_and_escapes_html(tmp_path: Path) -> None:
    source = tmp_path / "<stats>.csv"
    source.write_text(
        'sample,comment\nS1,"a,b & <tag>"\nS2,not-shown\n',
        encoding="utf-8",
    )
    context = _context(tmp_path)

    await TablePreviewNode().run(file=str(source), rows=1, delimiter="auto", context=context)
    rendered = Path(context.previews[0][0]).read_text(encoding="utf-8")

    assert "&lt;stats&gt;.csv" in rendered
    assert "a,b &amp; &lt;tag&gt;" in rendered
    assert "not-shown" not in rendered
    assert "additional rows not shown" in rendered


@pytest.mark.asyncio
async def test_table_preview_accepts_headered_bed_as_tabular_text(tmp_path: Path) -> None:
    source = tmp_path / "modkit.bed"
    source.write_text("chrom\tstart\tend\nchr1\t0\t10\n", encoding="utf-8")
    context = _context(tmp_path)

    assert TablePreviewNode.VALIDATE_INPUTS({"file": str(source)}) is True
    await TablePreviewNode().run(file=str(source), context=context)
    rendered = Path(context.previews[0][0]).read_text(encoding="utf-8")

    assert "<th>chrom</th><th>start</th><th>end</th>" in rendered
    assert "<td>chr1</td><td>0</td><td>10</td>" in rendered


@pytest.mark.parametrize(
    "filename",
    [
        "genome.gff",
        "sample_peaks.narrowPeak",
        "quant.sf",
        "bracken.kreport",
        "sample_CpG.bedGraph",
    ],
)
def test_table_preview_accepts_documented_official_template_outputs(
    tmp_path: Path,
    filename: str,
) -> None:
    source = tmp_path / filename
    source.write_text("placeholder\n", encoding="utf-8")

    assert TablePreviewNode.VALIDATE_INPUTS({"file": str(source)}) is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "payload", "expected_header", "expected_row", "excluded"),
    [
        (
            "genome.gff",
            "##gff-version 3\n"
            "##sequence-region contig1 1 100\n"
            "contig1\tProkka\tCDS\t1\t10\t.\t+\t0\tID=cds1\n"
            "##FASTA\n>contig1\nACGT\n",
            "<th>seqid</th><th>source</th><th>type</th>",
            "<td>contig1</td><td>Prokka</td><td>CDS</td>",
            "gff-version",
        ),
        (
            "sample_peaks.narrowPeak",
            "chr1\t10\t30\tpeak_1\t1000\t.\t42.5\t12\t8\t7\n",
            "<th>chrom</th><th>start</th><th>end</th><th>name</th>",
            "<td>chr1</td><td>10</td><td>30</td><td>peak_1</td>",
            "<th>chr1</th>",
        ),
        (
            "quant.sf",
            "Name\tLength\tEffectiveLength\tTPM\tNumReads\n"
            "tx1\t1000\t800.5\t12.5\t42\n",
            "<th>Name</th><th>Length</th><th>EffectiveLength</th>",
            "<td>tx1</td><td>1000</td><td>800.5</td>",
            "<td>Name</td>",
        ),
        (
            "bracken.kreport",
            "75.00\t150\t120\tS\t562\t  Escherichia coli\n",
            "<th>percentage</th><th>clade_reads</th><th>taxon_reads</th>",
            "<td>75.00</td><td>150</td><td>120</td>",
            "<th>75.00</th>",
        ),
        (
            "sample_CpG.bedGraph",
            'track type=bedGraph name="CpG"\nchr1\t20\t21\t87.5\n',
            "<th>chrom</th><th>start</th><th>end</th><th>value</th>",
            "<td>chr1</td><td>20</td><td>21</td><td>87.5</td>",
            "track type",
        ),
    ],
)
async def test_table_preview_uses_format_aware_headers_and_comments(
    tmp_path: Path,
    filename: str,
    payload: str,
    expected_header: str,
    expected_row: str,
    excluded: str,
) -> None:
    source = tmp_path / filename
    source.write_text(payload, encoding="utf-8")
    context = _context(tmp_path)

    await TablePreviewNode().run(file=str(source), rows=5, context=context)
    rendered = Path(context.previews[0][0]).read_text(encoding="utf-8")

    assert expected_header in rendered
    assert expected_row in rendered
    assert excluded not in rendered


@pytest.mark.asyncio
async def test_text_preview_caps_bytes_escapes_content_and_rejects_nul(tmp_path: Path) -> None:
    source = tmp_path / "sequence.fa"
    source.write_bytes((b"<tag>\n" + b"A" * 1400))
    context = _context(tmp_path)

    await TextPreviewNode().run(file=str(source), max_lines=20, max_bytes=1024, context=context)
    rendered = Path(context.previews[0][0]).read_text(encoding="utf-8")
    assert "&lt;tag&gt;" in rendered
    assert "truncated at 1,024 bytes" in rendered

    binary = tmp_path / "payload.txt"
    binary.write_bytes(b"text\x00binary")
    with pytest.raises(ValueError, match="NUL-containing"):
        await TextPreviewNode().run(file=str(binary), max_lines=20, max_bytes=1024)


@pytest.mark.asyncio
async def test_note_and_reroute_preserve_native_semantics() -> None:
    marker = object()
    assert await RerouteNode().run(input=marker) == (marker,)
    assert await NoteNode().run(text="annotation") == ()


@pytest.mark.asyncio
async def test_html_report_streams_quoted_tables_and_blocks_style_breakout(tmp_path: Path) -> None:
    table = tmp_path / "stats.csv"
    table.write_text('sample,note\nS1,"a,b <unsafe>"\nS2,hidden\n', encoding="utf-8")
    context = _context(tmp_path)

    result = await HTMLReportNode().run(
        title="<Report>",
        tables=str(table),
        max_table_rows=1,
        context=context,
    )
    rendered = Path(result["outputs"]["html_report"]).read_text(encoding="utf-8")
    assert "&lt;Report&gt;" in rendered
    assert "a,b &lt;unsafe&gt;" in rendered
    assert "hidden" not in rendered
    with pytest.raises(ValueError, match="custom_css"):
        await HTMLReportNode().run(title="Report", custom_css="</style><script>alert(1)</script>")


@pytest.mark.asyncio
async def test_pdf_report_writes_all_content_across_multiple_pages(tmp_path: Path) -> None:
    context = _context(tmp_path)
    text = "\n".join(f"line {index:03d} retained" for index in range(180))

    result = await PDFReportNode().run(title="Long Report", text=text, context=context)
    payload = Path(result["outputs"]["pdf_report"]).read_bytes()
    match = re.search(rb"/Count (\d+)", payload)

    assert payload.startswith(b"%PDF-1.4")
    assert match is not None and int(match.group(1)) >= 3
    assert b"line 000 retained" in payload
    assert b"line 179 retained" in payload


@pytest.mark.asyncio
async def test_qc_dashboard_escapes_metrics_and_rejects_bad_coverage(tmp_path: Path) -> None:
    coverage = tmp_path / "coverage.csv"
    coverage.write_text("depth,count\n10,5\n", encoding="utf-8")
    context = _context(tmp_path)
    result = await QCDashboardNode().run(
        run_name="<sample>",
        custom_metrics='{"<Metric>": "<value>"}',
        coverage_stats=str(coverage),
        context=context,
    )
    rendered = Path(result["outputs"]["qc_dashboard"]).read_text(encoding="utf-8")
    assert "&lt;sample&gt;" in rendered
    assert "&lt;Metric&gt;" in rendered
    assert "&lt;value&gt;" in rendered

    coverage.write_text("depth,count\n10,nan\n", encoding="utf-8")
    with pytest.raises(ValueError, match="finite and nonnegative"):
        await QCDashboardNode().run(run_name="sample", coverage_stats=str(coverage))
    with pytest.raises(ValueError, match="JSON object"):
        await QCDashboardNode().run(run_name="sample", custom_metrics="[]")
