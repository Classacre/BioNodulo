"""Focused BayeScan 2.1 node contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin._wrapped_tool_utils import (
    BIONODULO_BUILTIN_ALIAS,
    DOI_URL,
    _out,
)
from bionodulo.nodes.command_node import CommandNode

from .evidence import pin_contract


class BayeScanNode(CommandNode):
    """Detect loci under selection from population genotype data with BayeScan."""

    NODE_ID = "bayescan"
    DISPLAY_NAME = "BayeScan"
    REQUIRED_CONDA_PACKAGES = ["bayescan"]
    CATEGORY = "population_genetics"
    DESCRIPTION = "Identify candidate loci under natural selection from population allele-frequency differences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BayeScan",
        "bayescan2",
        "natural selection",
        "population genetics",
        "FST",
        "genome scan",
        "dominant markers",
        "codominant markers",
    ]
    RETURN_TYPES = ("TXT", "TXT", "TXT", "TXT", "TXT", "TXT", "TXT")
    RETURN_NAMES = (
        "log",
        "selection",
        "mcmc_trace",
        "verification",
        "acceptance_rate",
        "pilot_runs",
        "allele_frequencies",
    )
    REQUIRED_EXECUTABLES = ["bayescan2"]
    DOCUMENTATION_URL = "http://cmpg.unibe.ch/software/BayeScan/"
    CITATION_DOIS = ["10.1534/genetics.108.092221"]
    CITATION_URLS = [f"{DOI_URL}10.1534/genetics.108.092221"]
    CITATION_TEXT = "A genome-scan method to identify selected loci appropriate for both dominant and codominant markers."
    VERSION = "2.1"
    SHELL = True
    QUARANTINE_STATUS = "contract-checked-no-binary-execution"

    OUTPUT_NAME_BY_BASENAME = {
        "bayescan.log": "log",
        "bayescan_fst.txt": "selection",
        "bayescan.sel": "mcmc_trace",
        "bayescan_Verif.txt": "verification",
        "bayescan_AccRte.txt": "acceptance_rate",
        "bayescan_prop.txt": "pilot_runs",
        "bayescan_freq.txt": "allele_frequencies",
    }

    @staticmethod
    def _integer(value: Any, *, name: str, minimum: int) -> int | str:
        if isinstance(value, bool):
            return f"{name} must be an integer"
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return f"{name} must be an integer"
        if parsed < minimum:
            return f"{name} must be >= {minimum}"
        return parsed

    @staticmethod
    def _number(value: Any, *, name: str) -> float | str:
        if isinstance(value, bool):
            return f"{name} must be a number"
        try:
            return float(value)
        except (TypeError, ValueError):
            return f"{name} must be a number"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out = _out(inputs)
        discovered_dir = f"{out}/output_dir"
        cmd = [
            "mkdir",
            "-p",
            discovered_dir,
            "&&",
            "bayescan2",
            str(inputs.get("input", "")),
            "-od",
            discovered_dir,
        ]
        if inputs.get("discard_loci_file"):
            cmd.extend(["-d", str(inputs.get("discard_loci_file"))])
        if inputs.get("snp_genotypes_matrix"):
            cmd.append("-snp")
        if inputs.get("fstats"):
            cmd.append("-fstat")
        if inputs.get("pilot_runs"):
            cmd.append("-out_pilot")
        if inputs.get("allele_frequency"):
            cmd.append("-out_freq")
        cmd.extend(
            [
                "-o",
                "bayescan",
                "-threads",
                str(inputs.get("threads", 4)),
                "-n",
                str(inputs.get("sample_size", 5000)),
                "-thin",
                str(inputs.get("thinning_interval", 10)),
                "-nbp",
                str(inputs.get("num_pilot_runs", 20)),
                "-pilot",
                str(inputs.get("length_pilot_run", 5000)),
                "-burn",
                str(inputs.get("burn", 50000)),
                "-pr_odds",
                str(inputs.get("prior_odds", 10)),
                "-lb_fis",
                str(inputs.get("lower_prior", 0.0)),
                "-hb_fis",
                str(inputs.get("higher_prior", 1.0)),
                "-aflp_pc",
                str(inputs.get("threshold", 0.1)),
                ">",
                f"{out}/bayescan.log",
            ]
        )
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        discovered_dir = out / "output_dir"
        discovered_dir.mkdir(parents=True, exist_ok=True)
        outputs = [out / "bayescan.log"]
        if not inputs.get("fstats"):
            outputs.append(discovered_dir / "bayescan_fst.txt")
        outputs.extend(
            [
                discovered_dir / "bayescan.sel",
                discovered_dir / "bayescan_Verif.txt",
                discovered_dir / "bayescan_AccRte.txt",
            ]
        )
        if inputs.get("pilot_runs"):
            outputs.append(discovered_dir / "bayescan_prop.txt")
        if inputs.get("allele_frequency"):
            outputs.append(discovered_dir / "bayescan_freq.txt")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path] | tuple[Any, ...]) -> dict[str, str]:
        mapped: dict[str, str] = {}
        for value in planned_paths:
            path = Path(value)
            try:
                output_name = cls.OUTPUT_NAME_BY_BASENAME[path.name]
            except KeyError as exc:
                raise ValueError(f"BayeScan planned an unknown artifact: {path.name}") from exc
            mapped[output_name] = str(path)
        return mapped

    async def run(self, **kwargs: Any) -> dict[str, dict[str, str]]:
        planned = await super().run(**kwargs)
        if not isinstance(planned, tuple):
            raise TypeError("BayeScan command execution must return planned paths")
        return {"outputs": self.__class__.MAP_PLANNED_OUTPUTS(planned)}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TXT", {"description": "BayeScan genotype data file in tab- or space-delimited text format"}),
            },
            "optional": {
                "discard_loci_file": ("TSV", {"default": "", "description": "Optional list of loci to discard before analysis"}),
                "snp_genotypes_matrix": (
                    "BOOLEAN",
                    {"default": False, "description": "Use SNP genotypes matrix input mode (-snp)"},
                ),
                "fstats": ("BOOLEAN", {"default": False, "description": "Only estimate F-statistics without selection testing"}),
                "threads": (
                    "INT",
                    {"default": 4, "min": 1, "max": 128, "display": "slider"},
                ),
                "sample_size": ("INT", {"default": 5000, "min": 1, "description": "Number of output iterations"}),
                "thinning_interval": ("INT", {"default": 10, "min": 1, "description": "MCMC thinning interval"}),
                "num_pilot_runs": ("INT", {"default": 20, "min": 0, "description": "Number of pilot runs"}),
                "length_pilot_run": ("INT", {"default": 5000, "min": 1, "description": "Length of each pilot run"}),
                "burn": ("INT", {"default": 50000, "min": 0, "description": "Additional burn-in length"}),
                "prior_odds": ("FLOAT", {"default": 10.0, "min": 0.0, "description": "Prior odds for the neutral model"}),
                "lower_prior": (
                    "FLOAT",
                    {"default": 0.0, "min": 0, "max": 1, "description": "Lower bound for the dominant-data Fis prior"},
                ),
                "higher_prior": (
                    "FLOAT",
                    {"default": 1.0, "min": 0, "max": 1, "description": "Upper bound for the dominant-data Fis prior"},
                ),
                "threshold": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "AFLP recessive-genotype threshold fraction"},
                ),
                "pilot_runs": ("BOOLEAN", {"default": False, "description": "Write optional pilot-run diagnostics"}),
                "allele_frequency": ("BOOLEAN", {"default": False, "description": "Write optional allele-frequency output"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "") or "").strip():
            return "input genotype data file is required"
        for name, default, minimum in (
            ("threads", 4, 1),
            ("sample_size", 5000, 1),
            ("thinning_interval", 10, 1),
            ("num_pilot_runs", 20, 0),
            ("length_pilot_run", 5000, 1),
            ("burn", 50000, 0),
        ):
            validation = cls._integer(inputs.get(name, default), name=name, minimum=minimum)
            if isinstance(validation, str):
                return validation

        prior_odds = cls._number(inputs.get("prior_odds", 10.0), name="prior_odds")
        if isinstance(prior_odds, str):
            return prior_odds
        if prior_odds <= 0:
            return "prior_odds must be > 0"

        lower = cls._number(inputs.get("lower_prior", 0.0), name="lower_prior")
        if isinstance(lower, str):
            return lower
        higher = cls._number(inputs.get("higher_prior", 1.0), name="higher_prior")
        if isinstance(higher, str):
            return higher
        if not 0 <= lower < higher <= 1:
            return "lower_prior and higher_prior must satisfy 0 <= lower_prior < higher_prior <= 1"

        threshold = cls._number(inputs.get("threshold", 0.1), name="threshold")
        if isinstance(threshold, str):
            return threshold
        if not 0 <= threshold <= 1:
            return "threshold must be between 0 and 1"
        return True


class BayeScanGalaxyNode(BayeScanNode):
    """Galaxy wrapper ID for BayeScan."""

    NODE_ID = "BayeScan"
    DISPLAY_NAME = "BayeScan (Galaxy)"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BayeScan",
        "bayescan2",
        "natural selection",
        "population genetics",
        "FST",
        "genome scan",
        "dominant markers",
        "codominant markers",
    ]

pin_contract(BayeScanNode)
pin_contract(BayeScanGalaxyNode)

__all__ = ["BayeScanNode", "BayeScanGalaxyNode"]
