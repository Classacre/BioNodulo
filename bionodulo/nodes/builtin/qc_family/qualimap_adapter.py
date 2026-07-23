"""Pinned Qualimap 2.3 BAM quality-control nodes."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

_QUALIMAP_GIT_COMMIT = "ad90b904c90a97ffaec9a953588efd19c5132f23"


class QualiMapNode(CommandNode):
    """Generate a complete Qualimap BAM QC HTML report bundle."""

    LEGACY_NODE_ID = "qualimap_bamqc"
    DISPLAY_NAME = "QualiMap BAM QC"
    CATEGORY = "qc"
    DESCRIPTION = "Analyze a coordinate-sorted BAM and generate a complete Qualimap report"
    SEARCH_ALIASES = ["qualimap", "bamqc", "bam qc", "alignment qc"]
    RETURN_TYPES = ("HTML_REPORT", "QC_REPORT_DIR")
    RETURN_NAMES = ("report", "report_dir")
    REQUIRED_EXECUTABLES = ["qualimap", "java"]
    REQUIRED_CONDA_PACKAGES = ["qualimap", "openjdk"]
    CONDA_PACKAGE_CONSTRAINTS = {"qualimap": "2.3"}
    PACKAGE_CONSTRAINTS = ("qualimap==2.3",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "2.3"

    GIT_URL = "https://bitbucket.org/kokonech/qualimap.git"
    GIT_COMMIT = _QUALIMAP_GIT_COMMIT
    SOURCE_ARCHIVE_URL = "https://bitbucket.org/kokonech/qualimap/downloads/qualimap_v2.3.zip"
    SOURCE_ARCHIVE_SHA256 = "2a04dd864b712da30923cce3bc8dfc6ea59612118e8b0ff1a246fe43b8d34c40"
    BIOCONDA_RECIPE_COMMIT = "db84c8bb8e9f5a12977172c0fcc0eb7dff388a7b"
    BIOCONDA_RECIPE_URL = (
        f"https://github.com/bioconda/bioconda-recipes/blob/{BIOCONDA_RECIPE_COMMIT}/recipes/qualimap/meta.yaml"
    )
    DOCUMENTATION_URL = "http://qualimap.conesalab.org/doc_html/command_line.html#bam-qc"
    UPSTREAM_CLI_SOURCE = "src/main/java/org/bioinfo/ngs/qc/qualimap/main/BamQcTool.java"
    UPSTREAM_RUNNER_SOURCE = "src/main/java/org/bioinfo/ngs/qc/qualimap/main/NgsSmartTool.java"
    UPSTREAM_BAM_SOURCE = "src/main/java/org/bioinfo/ngs/qc/qualimap/process/BamStatsAnalysis.java"
    UPSTREAM_HTML_SOURCE = "src/main/java/org/bioinfo/ngs/qc/qualimap/gui/threads/ExportHtmlThread.java"
    UPSTREAM_DOCUMENTATION_SOURCE = "doc/command_line.rst"
    UPSTREAM_SOURCE_PATHS = (
        UPSTREAM_CLI_SOURCE,
        UPSTREAM_RUNNER_SOURCE,
        UPSTREAM_BAM_SOURCE,
        UPSTREAM_HTML_SOURCE,
        UPSTREAM_DOCUMENTATION_SOURCE,
        "cli/qualimap",
    )
    UPSTREAM_SOURCE_URLS = tuple(
        f"https://bitbucket.org/kokonech/qualimap/src/{_QUALIMAP_GIT_COMMIT}/{path}" for path in UPSTREAM_SOURCE_PATHS
    )
    UPSTREAM_CLI_SHA256 = "bceba1e2ab0a387e94d69c2fd8ad6368ef944d754020596590ba5ab498a02831"
    UPSTREAM_DOCUMENTATION_SHA256 = "ccd43748c86e25b57d527e2541fe73f86ad10ecf913f300226d824c2f01e5395"
    CITATION_DOIS = ["10.1093/bioinformatics/btv566"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btv566"]

    BAM_INDEX_REQUIRED = False
    BAM_ACCESS_SEMANTICS = (
        "BamStatsAnalysis opens the BAM directly and consumes SAMFileReader.iterator(); "
        "it never opens or queries a BAI, so no index input or sibling staging is required."
    )
    R_RUNTIME_REQUIRED = False
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "NgsSmartMain exits non-zero for parse, memory, and uncaught execution errors. "
        "The HTML exporter can report an export failure without changing the process exit code, "
        "so BioNodulo also validates the expected HTML asset bundle after a zero exit."
    )

    REPORT_DIRECTORY = "report"
    REPORT_FILENAME = "qualimapReport.html"
    # The HTML uses sibling CSS, image, and raw-data directories. Serving only
    # this file through the generic preview endpoint breaks those assets.
    AUTO_PREVIEW = False
    REPORT_ASSET_DIRECTORIES = (
        "css",
        "images_qualimapReport",
        "raw_data_qualimapReport",
    )
    OUTSIDE_REPORT_FILENAME = "qualimapReportOutsideRegions.html"
    OUTSIDE_REPORT_ASSET_DIRECTORIES = (
        "images_qualimapReportOutsideRegions",
        "raw_data_qualimapReportOutsideRegions",
    )
    COVERAGE_FILENAME = "genome_coverage.txt"
    SEQUENCING_PROTOCOLS = (
        "non-strand-specific",
        "strand-specific-forward",
        "strand-specific-reverse",
    )
    GENOME_GC_DISTRIBUTIONS = ("", "hg19", "hg38", "mm9", "mm10", "HUMAN", "MOUSE")
    GENOME_GC_ALIASES = {"human": "hg19", "mouse": "mm9"}
    SHELL = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {
                        "description": (
                            "Coordinate-sorted BAM alignment file. Qualimap streams the BAM and does not use a BAI."
                        )
                    },
                ),
                "threads": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "description": (
                            "Worker threads; zero omits -nt and preserves Qualimap's dynamic "
                            "available-processors default"
                        ),
                    },
                ),
            },
            "optional": {
                "feature_file": (
                    ("GFF_GTF", "BED"),
                    {
                        "description": "Uncompressed GFF, GTF, or BED regions of interest",
                        "advanced": True,
                    },
                ),
                "number_of_windows": (
                    "INT",
                    {"default": 400, "min": 1, "advanced": True},
                ),
                "chunk_size": (
                    "INT",
                    {"default": 1000, "min": 1, "advanced": True},
                ),
                "minimum_homopolymer_size": (
                    "INT",
                    {"default": 3, "min": 1, "advanced": True},
                ),
                "coverage_histogram_limit": (
                    "INT",
                    {"default": 50, "min": 50, "advanced": True},
                ),
                "duplication_rate_limit": (
                    "INT",
                    {"default": 50, "min": 50, "advanced": True},
                ),
                "sequencing_protocol": (
                    "STRING",
                    {
                        "default": "non-strand-specific",
                        "options": list(cls.SEQUENCING_PROTOCOLS),
                        "advanced": True,
                    },
                ),
                "genome_gc_distribution": (
                    "STRING",
                    {
                        "default": "",
                        "options": list(cls.GENOME_GC_DISTRIBUTIONS),
                        "description": (
                            "Optional built-in hg19, hg38, mm9, or mm10 GC distribution; "
                            "Qualimap's HUMAN and MOUSE aliases select hg19 and mm9"
                        ),
                        "advanced": True,
                    },
                ),
                "save_genome_coverage": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": (
                            "Write per-base non-zero coverage inside the report directory; this can be very large"
                        ),
                        "advanced": True,
                    },
                ),
                "paint_chromosome_limits": (
                    "BOOLEAN",
                    {"default": False, "advanced": True},
                ),
                "skip_duplicates": (
                    "BOOLEAN",
                    {"default": False, "advanced": True},
                ),
                "skip_duplicate_mode": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 2,
                        "description": "0=flagged, 1=estimated by Qualimap, 2=both",
                        "advanced": True,
                    },
                ),
                "collect_overlap_pairs": (
                    "BOOLEAN",
                    {"default": False, "advanced": True},
                ),
                "outside_stats": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Also report regions outside feature_file",
                        "advanced": True,
                    },
                ),
                "java_memory_size": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Optional launcher heap size such as 1200M or 4G; empty preserves the "
                            "release launcher's 1200M default"
                        ),
                        "advanced": True,
                    },
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
    def _validate_integer(
        cls,
        inputs: dict[str, Any],
        key: str,
        default: int,
        minimum: int,
        maximum: int | None = None,
    ) -> bool | str:
        value = inputs.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int):
            return f"{key} must be an integer"
        if value < minimum or (maximum is not None and value > maximum):
            if maximum is None:
                return f"{key} must be at least {minimum}"
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        bam = inputs.get("bam")
        if not isinstance(bam, (str, os.PathLike)) or not os.fsdecode(os.fspath(bam)).strip():
            return "bam must be a non-empty path"

        for key, default, minimum, maximum in (
            ("threads", 0, 0, None),
            ("number_of_windows", 400, 1, None),
            ("chunk_size", 1000, 1, None),
            ("minimum_homopolymer_size", 3, 1, None),
            ("coverage_histogram_limit", 50, 50, None),
            ("duplication_rate_limit", 50, 50, None),
            ("skip_duplicate_mode", 0, 0, 2),
        ):
            validation = cls._validate_integer(inputs, key, default, minimum, maximum)
            if validation is not True:
                return validation

        for key in (
            "save_genome_coverage",
            "paint_chromosome_limits",
            "skip_duplicates",
            "collect_overlap_pairs",
            "outside_stats",
        ):
            if not isinstance(inputs.get(key, False), bool):
                return f"{key} must be a boolean"

        protocol = inputs.get("sequencing_protocol", "non-strand-specific")
        if protocol not in cls.SEQUENCING_PROTOCOLS:
            return "sequencing_protocol is not supported by Qualimap 2.3"
        genome = inputs.get("genome_gc_distribution", "")
        if genome not in cls.GENOME_GC_DISTRIBUTIONS:
            return "genome_gc_distribution must be one of hg19, hg38, mm9, mm10, HUMAN, or MOUSE"

        feature_file = inputs.get("feature_file")
        if feature_file not in (None, ""):
            if not isinstance(feature_file, (str, os.PathLike)):
                return "feature_file must be path-like"
            feature_path_text = os.fsdecode(os.fspath(feature_file))
            if not feature_path_text.strip():
                return "feature_file must be a non-empty path"
            if feature_path_text.lower().endswith(".gz"):
                return "feature_file must be uncompressed GFF, GTF, or BED"
        elif inputs.get("outside_stats"):
            return "outside_stats requires feature_file"
        elif protocol != "non-strand-specific":
            return "a strand-specific sequencing_protocol requires feature_file"

        skip_mode = inputs.get("skip_duplicate_mode", 0)
        if skip_mode != 0 and not inputs.get("skip_duplicates", False):
            return "skip_duplicate_mode 1 or 2 requires skip_duplicates"

        memory_size = inputs.get("java_memory_size", "")
        if not isinstance(memory_size, str):
            return "java_memory_size must be a string"
        if memory_size and re.fullmatch(r"[1-9][0-9]*[kKmMgG]?", memory_size) is None:
            return "java_memory_size must look like 1200M or 4G"

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
        report_dir = output / cls.REPORT_DIRECTORY
        command = ["qualimap", "bamqc"]
        memory_size = inputs.get("java_memory_size", "")
        if memory_size:
            command.append(f"--java-mem-size={memory_size}")
        command.extend(
            [
                "-bam",
                str(inputs.get("bam", "")),
                "-outdir",
                str(report_dir),
                "-outformat",
                "HTML",
            ]
        )

        feature_file = inputs.get("feature_file")
        if feature_file:
            command.extend(["-gff", str(feature_file)])

        for key, default, flag in (
            ("number_of_windows", 400, "-nw"),
            ("threads", 0, "-nt"),
            ("chunk_size", 1000, "-nr"),
            ("minimum_homopolymer_size", 3, "-hm"),
        ):
            value = inputs.get(key, default)
            if value != default:
                command.extend([flag, str(value)])

        if inputs.get("save_genome_coverage"):
            command.extend(["--output-genome-coverage", str(report_dir / cls.COVERAGE_FILENAME)])
        if inputs.get("paint_chromosome_limits"):
            command.append("--paint-chromosome-limits")
        if inputs.get("skip_duplicates"):
            command.append("--skip-duplicated")
            skip_mode = inputs.get("skip_duplicate_mode", 0)
            if skip_mode != 0:
                command.extend(["--skip-dup-mode", str(skip_mode)])
        if inputs.get("collect_overlap_pairs"):
            command.append("--collect-overlap-pairs")
        if inputs.get("outside_stats"):
            command.append("--outside-stats")

        genome = inputs.get("genome_gc_distribution", "")
        if genome:
            genome = cls.GENOME_GC_ALIASES.get(str(genome).lower(), str(genome))
            command.extend(["--genome-gc-distr", str(genome)])
        coverage_limit = inputs.get("coverage_histogram_limit", 50)
        if coverage_limit != 50:
            command.extend(["--cov-hist-lim", str(coverage_limit)])
        duplication_limit = inputs.get("duplication_rate_limit", 50)
        if duplication_limit != 50:
            command.extend(["--dup-rate-lim", str(duplication_limit)])
        protocol = inputs.get("sequencing_protocol", "non-strand-specific")
        if protocol != "non-strand-specific":
            command.extend(["--sequencing-protocol", str(protocol)])
        return command

    @staticmethod
    def _require_nonempty_file(path: Path, label: str) -> None:
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"Qualimap {label} is missing or empty: {path}")

    @staticmethod
    def _require_nonempty_directory(path: Path) -> None:
        try:
            has_nonempty_file = path.is_dir() and any(
                item.is_file() and item.stat().st_size > 0 for item in path.rglob("*")
            )
        except OSError as exc:
            raise RuntimeError(f"Cannot inspect Qualimap report assets in {path}: {exc}") from exc
        if not has_nonempty_file:
            raise RuntimeError(f"Qualimap report asset directory is missing or empty: {path}")

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        report = Path(result[0])
        report_dir = Path(result[1])
        self._require_nonempty_file(report, "HTML report")
        for directory_name in self.REPORT_ASSET_DIRECTORIES:
            self._require_nonempty_directory(report_dir / directory_name)

        if kwargs.get("outside_stats"):
            outside_report = report_dir / self.OUTSIDE_REPORT_FILENAME
            self._require_nonempty_file(outside_report, "outside-regions HTML report")
            for directory_name in self.OUTSIDE_REPORT_ASSET_DIRECTORIES:
                self._require_nonempty_directory(report_dir / directory_name)

        if kwargs.get("save_genome_coverage"):
            coverage = report_dir / self.COVERAGE_FILENAME
            if not coverage.is_file():
                raise RuntimeError(f"Qualimap genome coverage output is missing: {coverage}")
        return result


class QualiMapAliasNode(QualiMapNode):
    """Planner compatibility ID for the same documented BAM QC operation."""

    LEGACY_NODE_ID = "qualimap"
    DISPLAY_NAME = "QualiMap"
    DESCRIPTION = "Run QualiMap BAM quality control for alignment reports."
    SEARCH_ALIASES = [
        "qualimap",
        "bamqc",
        "bam qc",
        "alignment qc",
        "quality report",
    ]
