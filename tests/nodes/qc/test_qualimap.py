from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.builtin import qc
from bionodulo.nodes.builtin.qc_family.qualimap import QualiMapAliasNode, QualiMapNode


def test_qualimap_ids_are_owned_only_by_the_focused_module() -> None:
    assert QualiMapNode.__module__.endswith("qc_family.qualimap")
    assert QualiMapAliasNode.__module__.endswith("qc_family.qualimap")
    assert qc.QualiMapNode is QualiMapNode
    assert qc.QualiMapAliasNode is QualiMapAliasNode
    legacy_ids = {
        obj.NODE_ID
        for _name, obj in inspect.getmembers(qc, inspect.isclass)
        if issubclass(obj, BaseNode)
        and obj is not BaseNode
        and obj.__module__ == qc.__name__
        and obj.NODE_ID
    }
    assert {"qualimap", "qualimap_bamqc"}.isdisjoint(legacy_ids)


def test_qualimap_source_and_in_place_report_contract_are_exact(tmp_path: Path) -> None:
    assert QualiMapNode.VERSION == "2.3"
    assert QualiMapNode.GIT_COMMIT == "ad90b904c90a97ffaec9a953588efd19c5132f23"
    assert QualiMapNode.SOURCE_ARCHIVE_SHA256 == (
        "2a04dd864b712da30923cce3bc8dfc6ea59612118e8b0ff1a246fe43b8d34c40"
    )
    assert QualiMapNode.RETURN_TYPES == ("HTML_REPORT", "QC_REPORT_DIR")
    assert QualiMapNode.RETURN_NAMES == ("report", "report_dir")
    assert QualiMapNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "qualimap_bamqc" / "report" / "qualimapReport.html",
        tmp_path / "qualimap_bamqc" / "report",
    ]
    assert QualiMapAliasNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "qualimap" / "report" / "qualimapReport.html",
        tmp_path / "qualimap" / "report",
    ]


def test_qualimap_argv_includes_documented_optional_flags(tmp_path: Path) -> None:
    assert QualiMapNode.render_command(
        {
            "bam": "coordinate-sorted.bam",
            "threads": 4,
            "feature_file": "features.bed",
            "paint_chromosome_limits": True,
            "collect_overlap_pairs": True,
            "output": str(tmp_path / "qualimap_bamqc"),
        }
    ) == [
        "qualimap",
        "bamqc",
        "-bam",
        "coordinate-sorted.bam",
        "-outdir",
        str(tmp_path / "qualimap_bamqc" / "report"),
        "-nt",
        "4",
        "-gff",
        "features.bed",
        "--paint-chromosome-limits",
        "--collect-overlap-pairs",
    ]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"bam": ""}, "non-empty path"),
        ({"threads": 0}, "between 1 and 64"),
        ({"threads": True}, "must be an integer"),
        ({"feature_file": "genes.gff.gz"}, "must be uncompressed"),
    ],
)
def test_qualimap_invalid_inputs_fail_closed(updates: dict[str, Any], message: str) -> None:
    inputs: dict[str, Any] = {"bam": "coordinate-sorted.bam", "threads": 2}
    inputs.update(updates)
    validation = QualiMapNode.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)


def test_qualimap_rejects_unmaterialized_bam_and_feature_file(tmp_path: Path) -> None:
    missing_bam = tmp_path / "missing.bam"
    assert "not a materialized file" in str(
        QualiMapNode.VALIDATE_INPUTS({"bam": str(missing_bam), "threads": 2})
    )

    bam = tmp_path / "coordinate-sorted.bam"
    bam.write_bytes(b"BAM")
    missing_features = tmp_path / "missing.gff"
    assert "not a materialized file" in str(
        QualiMapNode.VALIDATE_INPUTS(
            {
                "bam": str(bam),
                "threads": 2,
                "feature_file": str(missing_features),
            }
        )
    )


@pytest.mark.asyncio
async def test_qualimap_fake_execution_keeps_html_with_sibling_assets(tmp_path: Path) -> None:
    bam = tmp_path / "coordinate-sorted.bam"
    bam.write_bytes(b"BAM")

    class FakeContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            report_dir = Path(command[command.index("-outdir") + 1])
            (report_dir / "css").mkdir(parents=True)
            (report_dir / "images_qualimapReport").mkdir()
            (report_dir / "raw_data_qualimapReport").mkdir()
            (report_dir / "css" / "report.css").write_text("body {}", encoding="utf-8")
            (report_dir / "images_qualimapReport" / "coverage.png").write_bytes(b"PNG")
            (report_dir / "qualimapReport.html").write_text(
                '<link rel="stylesheet" href="css/report.css"><img src="images_qualimapReport/coverage.png">',
                encoding="utf-8",
            )
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await QualiMapNode().run(
        bam=str(bam),
        threads=2,
        context=FakeContext(),
        output_dir=tmp_path,
    )
    report_dir = tmp_path / "qualimap_bamqc" / "report"
    report = report_dir / "qualimapReport.html"
    assert result == (str(report), str(report_dir))
    assert 'href="css/report.css"' in report.read_text(encoding="utf-8")
    assert (report_dir / "css" / "report.css").exists()
    assert (report_dir / "images_qualimapReport" / "coverage.png").exists()
    assert not (tmp_path / "qualimap_bamqc" / "report.html").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("report_state", ["missing", "empty"])
async def test_qualimap_rejects_missing_or_empty_html_after_zero_exit(
    tmp_path: Path,
    report_state: str,
) -> None:
    bam = tmp_path / "coordinate-sorted.bam"
    bam.write_bytes(b"BAM")

    class FakeContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            report_dir = Path(command[command.index("-outdir") + 1])
            report_dir.mkdir(parents=True, exist_ok=True)
            if report_state == "empty":
                (report_dir / "qualimapReport.html").touch()
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError) as exc_info:
        await QualiMapNode().run(
            bam=str(bam),
            threads=1,
            context=FakeContext(),
            output_dir=tmp_path,
        )

    assert "qualimapReport.html" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_directory", ["css", "images_qualimapReport"])
async def test_qualimap_rejects_incomplete_report_asset_bundle(
    tmp_path: Path,
    missing_directory: str,
) -> None:
    bam = tmp_path / "coordinate-sorted.bam"
    bam.write_bytes(b"BAM")

    class FakeContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            report_dir = Path(command[command.index("-outdir") + 1])
            report_dir.mkdir(parents=True)
            (report_dir / "qualimapReport.html").write_text("<html></html>", encoding="utf-8")
            for directory in QualiMapNode.REPORT_ASSET_DIRECTORIES:
                if directory == missing_directory:
                    continue
                asset_dir = report_dir / directory
                asset_dir.mkdir()
                (asset_dir / "asset.bin").write_bytes(b"asset")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="asset directory is missing or empty"):
        await QualiMapNode().run(
            bam=str(bam),
            threads=1,
            context=FakeContext(),
            output_dir=tmp_path,
        )
