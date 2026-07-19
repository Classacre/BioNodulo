"""Qualimap 2.3 BAM quality-control nodes."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class QualiMapNode(CommandNode):
    """Generate a complete Qualimap BAM QC report bundle."""

    NODE_ID = "qualimap_bamqc"
    DISPLAY_NAME = "QualiMap BAM QC"
    CATEGORY = "qc"
    DESCRIPTION = "Analyze a coordinate-sorted BAM and generate a complete Qualimap report"
    SEARCH_ALIASES = ["qualimap", "bamqc", "bam qc", "alignment qc"]
    RETURN_TYPES = ("HTML_REPORT", "QC_REPORT_DIR")
    RETURN_NAMES = ("report", "report_dir")
    REQUIRED_EXECUTABLES = ["qualimap"]
    REQUIRED_CONDA_PACKAGES = ["qualimap"]
    VERSION = "2.3"
    GIT_URL = "https://bitbucket.org/kokonech/qualimap.git"
    GIT_COMMIT = "ad90b904c90a97ffaec9a953588efd19c5132f23"
    SOURCE_ARCHIVE_URL = "https://bitbucket.org/kokonech/qualimap/downloads/qualimap_v2.3.zip"
    SOURCE_ARCHIVE_SHA256 = "2a04dd864b712da30923cce3bc8dfc6ea59612118e8b0ff1a246fe43b8d34c40"
    UPSTREAM_CLI_SOURCE = "src/main/java/org/bioinfo/ngs/qc/qualimap/main/BamQcTool.java"
    DOCUMENTATION_URL = "http://qualimap.conesalab.org/doc_html/analysis.html#bam-qc"
    REPORT_DIRECTORY = "report"
    REPORT_FILENAME = "qualimapReport.html"
    REPORT_ASSET_DIRECTORIES = ("css", "images_qualimapReport")
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {"description": "Coordinate-sorted BAM alignment file; no BAI is required"},
                ),
                "threads": (
                    "INT",
                    {"default": 2, "min": 1, "max": 64, "display": "slider"},
                ),
            },
            "optional": {
                "feature_file": (
                    ("GFF_GTF", "BED"),
                    {
                        "description": "Uncompressed GFF, GTF, or BED feature file",
                        "advanced": True,
                    },
                ),
                "paint_chromosome_limits": (
                    "BOOLEAN",
                    {"default": False, "advanced": True},
                ),
                "collect_overlap_pairs": (
                    "BOOLEAN",
                    {"default": False, "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        report_dir = node_out / cls.REPORT_DIRECTORY
        return [report_dir / cls.REPORT_FILENAME, report_dir]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        bam = inputs.get("bam")
        if not isinstance(bam, (str, os.PathLike)) or not os.fsdecode(os.fspath(bam)).strip():
            return "bam must be a non-empty path"
        threads = inputs.get("threads", 2)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "threads must be an integer"
        if not 1 <= threads <= 64:
            return "threads must be between 1 and 64"
        feature_file = inputs.get("feature_file")
        if feature_file not in (None, ""):
            if not isinstance(feature_file, (str, os.PathLike)):
                return "feature_file must be path-like"
            path = os.fsdecode(os.fspath(feature_file))
            if not path.strip():
                return "feature_file must be a non-empty path"
            if path.lower().endswith(".gz"):
                return "feature_file must be uncompressed GFF, GTF, or BED"
        bam_path = Path(os.fsdecode(os.fspath(bam)))
        if not bam_path.is_file():
            return f"bam is not a materialized file: {bam_path}"
        if bam_path.stat().st_size == 0:
            return f"bam file is empty: {bam_path}"
        if feature_file not in (None, ""):
            feature_path = Path(os.fsdecode(os.fspath(feature_file)))
            if not feature_path.is_file():
                return f"feature_file is not a materialized file: {feature_path}"
            if feature_path.stat().st_size == 0:
                return f"feature_file is empty: {feature_path}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "qualimap",
            "bamqc",
            "-bam",
            str(inputs.get("bam", "")),
            "-outdir",
            str(output / cls.REPORT_DIRECTORY),
            "-nt",
            str(inputs.get("threads", 2)),
        ]
        if inputs.get("feature_file"):
            command.extend(["-gff", str(inputs["feature_file"])])
        if inputs.get("paint_chromosome_limits"):
            command.append("--paint-chromosome-limits")
        if inputs.get("collect_overlap_pairs"):
            command.append("--collect-overlap-pairs")
        return command

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        report = Path(result[0])
        if not report.is_file() or report.stat().st_size == 0:
            raise RuntimeError(f"Qualimap HTML report is missing or empty: {report}")
        for directory_name in self.REPORT_ASSET_DIRECTORIES:
            asset_dir = report.parent / directory_name
            try:
                has_nonempty_asset = asset_dir.is_dir() and any(
                    path.is_file() and path.stat().st_size > 0
                    for path in asset_dir.rglob("*")
                )
            except OSError as exc:
                raise RuntimeError(
                    f"Cannot inspect Qualimap report assets in {asset_dir}: {exc}"
                ) from exc
            if not has_nonempty_asset:
                raise RuntimeError(
                    f"Qualimap report asset directory is missing or empty: {asset_dir}"
                )
        return result


class QualiMapAliasNode(QualiMapNode):
    """Planner compatibility ID for the same documented BAM QC operation."""

    NODE_ID = "qualimap"
    DISPLAY_NAME = "QualiMap"
    DESCRIPTION = "Run QualiMap BAM quality control for alignment reports."
    SEARCH_ALIASES = [
        "qualimap",
        "bamqc",
        "bam qc",
        "alignment qc",
        "quality report",
    ]
