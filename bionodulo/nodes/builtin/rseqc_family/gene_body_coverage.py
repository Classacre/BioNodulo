"""RSeQC 5.0.3 ``geneBody_coverage.py`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import RSeQCCommandNode


class RSeQCGeneBodyCoverageNode(RSeQCCommandNode):
    """Measure coverage uniformity over one or more indexed BAM gene bodies."""

    NODE_ID = "rseqc_gene_body_coverage"
    DISPLAY_NAME = "RSeQC Gene Body Coverage"
    DESCRIPTION = "Calculate RNA-seq coverage across scaled gene bodies."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "RSeQC",
        "geneBody_coverage",
        "gene body coverage",
        "coverage uniformity",
    ]
    RETURN_TYPES = ("TSV", "TEXT", "FILE_LIST")
    RETURN_NAMES = ("coverage_table", "r_script", "coverage_plots")
    REQUIRED_EXECUTABLES = ["geneBody_coverage.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["rseqc", "r-base"]
    UPSTREAM_SCRIPT = "scripts/geneBody_coverage.py"
    UPSTREAM_SOURCE = UPSTREAM_SCRIPT
    UPSTREAM_OUTPUT_SOURCE = "scripts/geneBody_coverage.py:Rcode_write"
    DOCUMENTATION_URL = "https://rseqc.sourceforge.net/#genebody-coverage-py"
    RUN_IN_NODE_OUTPUT_DIR = True

    FORMATS = ("pdf", "png", "jpeg")
    REQUIRED_PATH_INPUTS = ("refgene",)
    REQUIRED_PATH_LIST_INPUTS = ("input", "bam_indexes")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "BAM_LIST",
                    {"multiple": True, "description": "One or more sorted indexed BAM files"},
                ),
                "bam_indexes": (
                    "FILE_LIST",
                    {"multiple": True, "description": "Exact sibling index for each BAM (<bam>.bai)"},
                ),
                "refgene": ("BED", {"description": "Reference gene model in BED12 format"}),
            },
            "optional": {
                "minimum_length": ("INT", {"default": 100, "min": 100}),
                "format": ("STRING", {"default": "pdf", "options": list(cls.FORMATS)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        graph_format = str(inputs.get("format", "pdf")).lower()
        outputs = [
            node_dir / "output.geneBodyCoverage.txt",
            node_dir / "output.geneBodyCoverage.r",
        ]
        if len(cls._bam_files(inputs)) >= 3:
            outputs.append(node_dir / f"output.geneBodyCoverage.heatMap.{graph_format}")
        outputs.append(node_dir / f"output.geneBodyCoverage.curves.{graph_format}")
        return outputs

    @classmethod
    def REQUIRED_OUTPUT_PATHS(
        cls,
        inputs: dict[str, Any],
        outputs: list[Path],
    ) -> list[Path]:
        """Require the curve, table, and R script but not a conditional heatmap.

        RSeQC's pinned ``Rcode_write`` source only writes ``heatMap`` when at
        least three BAMs successfully produce coverage.  The input list can
        contain more files than that runtime dataset because the source skips
        files with no coverage signal.
        """
        return [path for path in outputs if not path.name.startswith("output.geneBodyCoverage.heatMap.")]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Remove a prior conditional heatmap before a fresh source run."""
        for path in outputs:
            if path.name.startswith("output.geneBodyCoverage.heatMap."):
                path.unlink(missing_ok=True)

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        """Bind the table/script and group one or two native plot files."""
        tables = [path for path in planned_paths if path.name == "output.geneBodyCoverage.txt"]
        scripts = [path for path in planned_paths if path.name == "output.geneBodyCoverage.r"]
        plots = [
            path
            for path in planned_paths
            if path.name.startswith(("output.geneBodyCoverage.heatMap.", "output.geneBodyCoverage.curves."))
        ]
        if len(tables) != 1 or len(scripts) != 1 or len(plots) not in (1, 2):
            raise ValueError("geneBody_coverage planned an invalid native artifact set")
        if len(tables) + len(scripts) + len(plots) != len(planned_paths):
            raise ValueError("geneBody_coverage planned an unknown output artifact")
        return {
            "coverage_table": tables[0],
            "r_script": scripts[0],
            "coverage_plots": plots,
        }

    @classmethod
    def _bam_files(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.path_list(inputs.get("input"))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if "rscript_output" in inputs:
            return "Legacy input 'rscript_output' is unsupported; the source always creates its R script"
        validation = cls.validate_bam_indexes(inputs, bams_key="input", indexes_key="bam_indexes")
        if validation is not True:
            return validation
        for bam in cls._bam_files(inputs):
            if "," in bam:
                return "BAM paths containing commas cannot be represented by RSeQC's comma-separated -i input"
        validation = cls.validate_int(inputs.get("minimum_length", 100), "minimum_length", minimum=100)
        if validation is not True:
            return validation
        return cls.validate_choice(inputs.get("format", "pdf"), cls.FORMATS, "format")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        bams = cls._bam_files(inputs)
        return cls.checked_command(
            inputs,
            "geneBody_coverage.py",
            "-i",
            ",".join(bams),
            "-r",
            str(inputs["refgene"]),
            "-l",
            str(inputs.get("minimum_length", 100)),
            "-f",
            str(inputs.get("format", "pdf")),
            "-o",
            str(cls.output_prefix(inputs, "output")),
        )

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        result = await super().run(**kwargs)
        # The heatmap is planned when three inputs are supplied, but may be
        # absent when upstream skips one or more BAMs with no usable signal.
        # Only expose artifacts that actually exist at runtime.
        planned = [Path(path) for path in result if Path(path).exists()]
        mapped = self.__class__.MAP_PLANNED_OUTPUTS(planned)
        return {
            "outputs": {
                name: [str(path) for path in value] if isinstance(value, list) else str(value)
                for name, value in mapped.items()
            }
        }
