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


def test_html_report_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["html_report"]["display_name"] == "HTML Report"
    assert info["html_report"]["category"] == "reporting"
    assert info["html_report"]["output_name"] == ["html_report"]
    assert info["html_report"]["output"] == ["HTML_REPORT"]
    assert info["html_report"]["output_node"] is True


def test_pdf_report_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["pdf_report"]["display_name"] == "PDF Report"
    assert info["pdf_report"]["category"] == "reporting"
    assert info["pdf_report"]["output_name"] == ["pdf_report"]
    assert info["pdf_report"]["output"] == ["PDF_REPORT"]
    assert info["pdf_report"]["output_node"] is True


def test_qc_dashboard_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["qc_dashboard"]["display_name"] == "QC Dashboard"
    assert info["qc_dashboard"]["category"] == "reporting"
    assert info["qc_dashboard"]["output_name"] == ["qc_dashboard"]
    assert info["qc_dashboard"]["output"] == ["HTML_REPORT"]
    assert info["qc_dashboard"]["output_node"] is True


@pytest.mark.asyncio
async def test_html_report_writes_multisection_report_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("html_report")
    image = tmp_path / "plot.svg"
    image.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80">'
        '<rect width="120" height="80" fill="#2563EB"/></svg>',
        encoding="utf-8",
    )
    table = tmp_path / "stats.tsv"
    table.write_text("sample\treads\nS1\t120\nS2\t240\n", encoding="utf-8")
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        title="RNA-seq Analysis Report",
        images=str(image),
        tables=str(table),
        text_sections="# Summary\nDifferential expression completed.\n---\n## Methods\nSTAR + DESeq2",
        section_names="Volcano Plot,Read Stats",
        theme="dark",
        include_toc=True,
        max_table_rows=1,
        context=context,
    )

    report_path = Path(result["outputs"]["html_report"])
    report = report_path.read_text(encoding="utf-8")

    assert report_path.name == "report.html"
    assert "<!DOCTYPE html>" in report
    assert "RNA-seq Analysis Report" in report
    assert 'class="report-toc"' in report
    assert 'class="report-section"' in report
    assert 'data-section="Volcano Plot"' in report
    assert "data:image/svg+xml;base64," in report
    assert "<th>sample</th>" in report
    assert "<td>S1</td>" in report
    assert "<td>S2</td>" not in report
    assert "Differential expression completed." in report
    assert "STAR + DESeq2" in report
    assert previews == [(str(report_path), "HTML Report")]


@pytest.mark.asyncio
async def test_pdf_report_writes_report_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("pdf_report")
    table = tmp_path / "stats.tsv"
    table.write_text("sample\treads\nS1\t120\nS2\t240\n", encoding="utf-8")
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        title="BioNodulo PDF Report",
        text="Summary section\n---\nMethods section",
        tables=str(table),
        section_names="Read Stats",
        page_size="Letter",
        orientation="landscape",
        author="BioNodulo Test",
        header_text="Workflow QC",
        context=context,
    )

    pdf_path = Path(result["outputs"]["pdf_report"])
    pdf_bytes = pdf_path.read_bytes()

    assert pdf_path.name == "report.pdf"
    assert pdf_bytes.startswith(b"%PDF-")
    assert b"BioNodulo PDF Report" in pdf_bytes
    assert b"Summary section" in pdf_bytes
    assert b"Read Stats" in pdf_bytes
    assert b"S1" in pdf_bytes
    assert previews == [(str(pdf_path), "PDF Report")]


@pytest.mark.asyncio
async def test_qc_dashboard_writes_dashboard_from_metrics_and_registers_preview(tmp_path: Path) -> None:
    node_class = _node_class("qc_dashboard")
    flagstat = tmp_path / "sample.flagstat"
    flagstat.write_text(
        "1000 + 0 in total (QC-passed reads + QC-failed reads)\n"
        "900 + 0 mapped (90.00% : N/A)\n"
        "800 + 0 properly paired (80.00% : N/A)\n",
        encoding="utf-8",
    )
    variant_stats = tmp_path / "variants.json"
    variant_stats.write_text('{"total_variants": 42, "titv_ratio": 2.1}', encoding="utf-8")
    coverage = tmp_path / "coverage.csv"
    coverage.write_text("depth,count\n10,5\n20,12\n30,3\n", encoding="utf-8")
    previews: list[tuple[str, str]] = []
    context = SimpleNamespace(
        node_dir=tmp_path,
        register_preview=lambda path, label=None: previews.append((str(path), str(label))),
    )

    result = await node_class().run(
        run_name="Sample_001",
        alignment_stats=str(flagstat),
        variant_stats=str(variant_stats),
        coverage_stats=str(coverage),
        custom_metrics='{"Duplication Rate": "12.3%", "Mean Coverage": "45x"}',
        title="Sample 001 QC Dashboard",
        theme="dark",
        context=context,
    )

    dashboard_path = Path(result["outputs"]["qc_dashboard"])
    dashboard = dashboard_path.read_text(encoding="utf-8")

    assert dashboard_path.name == "qc_dashboard.html"
    assert "<!DOCTYPE html>" in dashboard
    assert "Sample 001 QC Dashboard" in dashboard
    assert "Sample_001" in dashboard
    assert "Total Reads" in dashboard
    assert "1000" in dashboard
    assert "Mapped %" in dashboard
    assert "90.00%" in dashboard
    assert "Total Variants" in dashboard
    assert "42" in dashboard
    assert "Duplication Rate" in dashboard
    assert "12.3%" in dashboard
    assert "Coverage Depth Distribution" in dashboard
    assert "data-depth=\"20\"" in dashboard
    assert "data-count=\"12\"" in dashboard
    assert "Generated by BioNodulo" in dashboard
    assert previews == [(str(dashboard_path), "QC Dashboard")]


@pytest.mark.asyncio
async def test_html_report_rejects_bad_theme() -> None:
    node_class = _node_class("html_report")

    with pytest.raises(ValueError, match="Unsupported HTML report theme"):
        await node_class().run(title="Report", theme="sepia")


@pytest.mark.asyncio
async def test_html_report_rejects_missing_file(tmp_path: Path) -> None:
    node_class = _node_class("html_report")

    with pytest.raises(FileNotFoundError, match="Report input file not found"):
        await node_class().run(title="Report", images=str(tmp_path / "missing.svg"))


@pytest.mark.asyncio
async def test_pdf_report_rejects_bad_page_size() -> None:
    node_class = _node_class("pdf_report")

    with pytest.raises(ValueError, match="Unsupported PDF page size"):
        await node_class().run(title="Report", page_size="Legal")


@pytest.mark.asyncio
async def test_pdf_report_rejects_missing_file(tmp_path: Path) -> None:
    node_class = _node_class("pdf_report")

    with pytest.raises(FileNotFoundError, match="Report input file not found"):
        await node_class().run(title="Report", tables=str(tmp_path / "missing.tsv"))


@pytest.mark.asyncio
async def test_qc_dashboard_rejects_bad_theme() -> None:
    node_class = _node_class("qc_dashboard")

    with pytest.raises(ValueError, match="Unsupported QC dashboard theme"):
        await node_class().run(run_name="Sample", theme="sepia")


@pytest.mark.asyncio
async def test_qc_dashboard_rejects_missing_file(tmp_path: Path) -> None:
    node_class = _node_class("qc_dashboard")

    with pytest.raises(FileNotFoundError, match="QC dashboard input file not found"):
        await node_class().run(run_name="Sample", alignment_stats=str(tmp_path / "missing.flagstat"))
