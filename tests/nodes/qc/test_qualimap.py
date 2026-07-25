from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin import qc
from bionodulo.nodes.builtin.qc_family.qualimap import QualiMapAliasNode, QualiMapNode


def _write_report_bundle(report_dir: Path, *, outside: bool = False) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "qualimapReport.html").write_text(
        '<link rel="stylesheet" href="css/report.css"><img src="images_qualimapReport/coverage.png">',
        encoding="utf-8",
    )
    base_assets = {
        "css": ("report.css", b"body {}"),
        "images_qualimapReport": ("coverage.png", b"PNG"),
        "raw_data_qualimapReport": ("coverage.txt", b"position\tcoverage\n"),
    }
    for directory, (filename, content) in base_assets.items():
        asset_dir = report_dir / directory
        asset_dir.mkdir()
        (asset_dir / filename).write_bytes(content)

    if outside:
        (report_dir / "qualimapReportOutsideRegions.html").write_text(
            '<img src="images_qualimapReportOutsideRegions/coverage.png">',
            encoding="utf-8",
        )
        outside_assets = {
            "images_qualimapReportOutsideRegions": ("coverage.png", b"PNG"),
            "raw_data_qualimapReportOutsideRegions": ("coverage.txt", b"position\tcoverage\n"),
        }
        for directory, (filename, content) in outside_assets.items():
            asset_dir = report_dir / directory
            asset_dir.mkdir()
            (asset_dir / filename).write_bytes(content)


def test_qualimap_facade_reexports_compatible_classes() -> None:
    assert qc.QualiMapNode is QualiMapNode
    assert qc.QualiMapAliasNode is QualiMapAliasNode
    assert issubclass(QualiMapAliasNode, QualiMapNode)


def test_qualimap_pinned_authority_runtime_and_bam_access_contract() -> None:
    assert QualiMapNode.VERSION == "2.3"
    assert QualiMapNode.GIT_COMMIT == "ad90b904c90a97ffaec9a953588efd19c5132f23"
    assert QualiMapNode.SOURCE_ARCHIVE_SHA256 == ("2a04dd864b712da30923cce3bc8dfc6ea59612118e8b0ff1a246fe43b8d34c40")
    assert QualiMapNode.BIOCONDA_RECIPE_COMMIT == ("db84c8bb8e9f5a12977172c0fcc0eb7dff388a7b")
    assert QualiMapNode.PACKAGE_CONSTRAINTS == ("qualimap==2.3",)
    assert QualiMapNode.REQUIRED_EXECUTABLES == ["qualimap", "java"]
    assert QualiMapNode.REQUIRED_CONDA_PACKAGES == ["qualimap", "openjdk"]
    assert QualiMapNode.REQUIRED_R_PACKAGES == []
    assert QualiMapNode.R_RUNTIME_REQUIRED is False
    assert QualiMapNode.BAM_INDEX_REQUIRED is False
    assert "SAMFileReader.iterator()" in QualiMapNode.BAM_ACCESS_SEMANTICS
    assert QualiMapNode.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert "zero exit" in QualiMapNode.EXIT_SEMANTICS


def test_qualimap_inputs_match_upstream_defaults_without_bai_port() -> None:
    inputs = QualiMapNode.INPUT_TYPES()
    all_port_names = set().union(*(section.keys() for section in inputs.values()))
    assert "bam_index" not in all_port_names
    assert inputs["required"]["threads"][1]["default"] == 0
    assert "dynamic" in inputs["required"]["threads"][1]["description"]
    assert inputs["optional"]["number_of_windows"][1]["default"] == 400
    assert inputs["optional"]["chunk_size"][1]["default"] == 1000
    assert inputs["optional"]["minimum_homopolymer_size"][1]["default"] == 3
    assert inputs["optional"]["coverage_histogram_limit"][1]["default"] == 50
    assert inputs["optional"]["duplication_rate_limit"][1]["default"] == 50
    assert inputs["optional"]["sequencing_protocol"][1]["default"] == "non-strand-specific"
    assert inputs["optional"]["skip_duplicate_mode"][1]["default"] == 0


def test_qualimap_in_place_report_contract_is_exact(tmp_path: Path) -> None:
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


def test_qualimap_minimal_argv_preserves_dynamic_thread_default(tmp_path: Path) -> None:
    command = QualiMapNode.render_command(
        {
            "bam": "coordinate-sorted.bam",
            "threads": 0,
            "output": str(tmp_path / "qualimap_bamqc"),
        }
    )
    assert command == [
        "qualimap",
        "bamqc",
        "-bam",
        "coordinate-sorted.bam",
        "-outdir",
        str(tmp_path / "qualimap_bamqc" / "report"),
        "-outformat",
        "HTML",
    ]
    assert "-nt" not in command


def test_qualimap_full_argv_uses_documented_flags_and_order(tmp_path: Path) -> None:
    report_dir = tmp_path / "qualimap_bamqc" / "report"
    assert QualiMapNode.render_command(
        {
            "bam": "coordinate-sorted.bam",
            "feature_file": "features.bed",
            "number_of_windows": 800,
            "threads": 4,
            "chunk_size": 2000,
            "minimum_homopolymer_size": 4,
            "save_genome_coverage": True,
            "paint_chromosome_limits": True,
            "skip_duplicates": True,
            "skip_duplicate_mode": 2,
            "collect_overlap_pairs": True,
            "outside_stats": True,
            "genome_gc_distribution": "hg38",
            "coverage_histogram_limit": 75,
            "duplication_rate_limit": 80,
            "sequencing_protocol": "strand-specific-reverse",
            "java_memory_size": "4G",
            "output": str(tmp_path / "qualimap_bamqc"),
        }
    ) == [
        "qualimap",
        "bamqc",
        "--java-mem-size=4G",
        "-bam",
        "coordinate-sorted.bam",
        "-outdir",
        str(report_dir),
        "-outformat",
        "HTML",
        "-gff",
        "features.bed",
        "-nw",
        "800",
        "-nt",
        "4",
        "-nr",
        "2000",
        "-hm",
        "4",
        "--output-genome-coverage",
        str(report_dir / "genome_coverage.txt"),
        "--paint-chromosome-limits",
        "--skip-duplicated",
        "--skip-dup-mode",
        "2",
        "--collect-overlap-pairs",
        "--outside-stats",
        "--genome-gc-distr",
        "hg38",
        "--cov-hist-lim",
        "75",
        "--dup-rate-lim",
        "80",
        "--sequencing-protocol",
        "strand-specific-reverse",
    ]


@pytest.mark.parametrize(("alias", "build"), [("HUMAN", "hg19"), ("MOUSE", "mm9")])
def test_qualimap_normalizes_documented_genome_gc_aliases(
    tmp_path: Path,
    alias: str,
    build: str,
) -> None:
    command = QualiMapNode.render_command(
        {
            "bam": "coordinate-sorted.bam",
            "genome_gc_distribution": alias,
            "output": str(tmp_path / "qualimap_bamqc"),
        }
    )
    assert command[-2:] == ["--genome-gc-distr", build]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"bam": ""}, "non-empty path"),
        ({"threads": -1}, "at least 0"),
        ({"threads": True}, "must be an integer"),
        ({"number_of_windows": 0}, "at least 1"),
        ({"coverage_histogram_limit": 49}, "at least 50"),
        ({"duplication_rate_limit": 49}, "at least 50"),
        ({"skip_duplicate_mode": 3}, "between 0 and 2"),
        ({"paint_chromosome_limits": "yes"}, "must be a boolean"),
        ({"genome_gc_distribution": "human"}, "must be one of"),
        ({"java_memory_size": "four gigs"}, "must look like"),
        ({"feature_file": "genes.gff.gz"}, "must be uncompressed"),
    ],
)
def test_qualimap_invalid_values_fail_closed(updates: dict[str, Any], message: str) -> None:
    inputs: dict[str, Any] = {"bam": "coordinate-sorted.bam", "threads": 0}
    inputs.update(updates)
    validation = QualiMapNode.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"outside_stats": True}, "requires feature_file"),
        (
            {"sequencing_protocol": "strand-specific-forward"},
            "requires feature_file",
        ),
        ({"skip_duplicate_mode": 1}, "requires skip_duplicates"),
    ],
)
def test_qualimap_dependent_options_fail_closed(updates: dict[str, Any], message: str) -> None:
    inputs: dict[str, Any] = {"bam": "coordinate-sorted.bam", "threads": 0}
    inputs.update(updates)
    validation = QualiMapNode.VALIDATE_INPUTS(inputs)
    assert validation is not True
    assert message in str(validation)


def test_qualimap_rejects_unmaterialized_bam_and_feature_file(tmp_path: Path) -> None:
    missing_bam = tmp_path / "missing.bam"
    assert "not a materialized file" in str(QualiMapNode.VALIDATE_INPUTS({"bam": str(missing_bam), "threads": 0}))

    bam = tmp_path / "coordinate-sorted.bam"
    bam.write_bytes(b"BAM")
    missing_features = tmp_path / "missing.gff"
    assert "not a materialized file" in str(
        QualiMapNode.VALIDATE_INPUTS(
            {
                "bam": str(bam),
                "threads": 0,
                "feature_file": str(missing_features),
            }
        )
    )


@pytest.mark.asyncio
async def test_qualimap_fake_execution_keeps_complete_html_bundle(tmp_path: Path) -> None:
    bam = tmp_path / "coordinate-sorted.bam"
    bam.write_bytes(b"BAM")

    class FakeContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            report_dir = Path(command[command.index("-outdir") + 1])
            _write_report_bundle(report_dir)
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await QualiMapNode().run(
        bam=str(bam),
        threads=0,
        context=FakeContext(),
        output_dir=tmp_path,
    )
    report_dir = tmp_path / "qualimap_bamqc" / "report"
    report = report_dir / "qualimapReport.html"
    assert result == (str(report), str(report_dir))
    assert (report_dir / "css" / "report.css").exists()
    assert (report_dir / "images_qualimapReport" / "coverage.png").exists()
    assert (report_dir / "raw_data_qualimapReport" / "coverage.txt").exists()


@pytest.mark.asyncio
async def test_qualimap_fake_execution_validates_conditional_outputs(tmp_path: Path) -> None:
    bam = tmp_path / "coordinate-sorted.bam"
    bam.write_bytes(b"BAM")
    features = tmp_path / "features.bed"
    features.write_text("chr1\t0\t1\n", encoding="utf-8")

    class FakeContext:
        node_dir = tmp_path

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            report_dir = Path(command[command.index("-outdir") + 1])
            _write_report_bundle(report_dir, outside=True)
            coverage = Path(command[command.index("--output-genome-coverage") + 1])
            coverage.touch()
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await QualiMapNode().run(
        bam=str(bam),
        threads=2,
        feature_file=str(features),
        outside_stats=True,
        save_genome_coverage=True,
        context=FakeContext(),
        output_dir=tmp_path,
    )
    report_dir = Path(result[1])
    assert (report_dir / QualiMapNode.OUTSIDE_REPORT_FILENAME).exists()
    assert (report_dir / QualiMapNode.COVERAGE_FILENAME).exists()


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
            threads=0,
            context=FakeContext(),
            output_dir=tmp_path,
        )

    assert "qualimapReport.html" in str(exc_info.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_directory", QualiMapNode.REPORT_ASSET_DIRECTORIES)
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
            _write_report_bundle(report_dir)
            target = report_dir / missing_directory
            for item in target.iterdir():
                item.unlink()
            target.rmdir()
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="asset directory is missing or empty"):
        await QualiMapNode().run(
            bam=str(bam),
            threads=0,
            context=FakeContext(),
            output_dir=tmp_path,
        )
