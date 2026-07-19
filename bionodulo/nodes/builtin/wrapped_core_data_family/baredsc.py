"""Focused baredsc node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class Baredsc1DNode(CommandNode):
    """Estimate a one-dimensional baredSC expression distribution."""

    NODE_ID = "baredsc_1d"
    DISPLAY_NAME = "baredSC 1d"
    REQUIRED_CONDA_PACKAGES = ["baredsc", "gzip"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Compute a one-dimensional baredSC expression distribution for a single gene."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "baredSC",
        "baredsc_1d",
        "baredSC 1d",
        "single gene",
        "single-cell expression distribution",
        "Bayesian Approach",
        "probability density function",
        "MCMC",
    ]
    RETURN_TYPES = ("NPZ", "TXT", "DIRECTORY", "TSV", "IMAGE", "DIRECTORY", "TXT")
    RETURN_NAMES = ("output", "neff", "qc_plots", "pdf", "plot", "other_outputs", "logevidence")
    REQUIRED_EXECUTABLES = ["baredSC_1d", "mkdir", "mv", "gunzip"]
    DOCUMENTATION_URL = BAREDSC_DOCUMENTATION_URL
    CITATION_DOIS = [BAREDSC_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BAREDSC_CITATION_DOI}"]
    CITATION_TEXT = BAREDSC_CITATION_TEXT
    VERSION = "1.1.3+galaxy0"
    SHELL = True

    FILETYPES = ["tabular", "anndata"]
    FILTER_COUNTS = ["0", "1", "2", "3"]
    SCALE_OPTIONS = ["Seurat", "log"]
    RESTART_OPTIONS = ["yes", "no"]
    IMAGE_FORMATS = ["png", "svg", "pdf"]

    @classmethod
    def _image_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("image_file_format", "png") or "png")

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [
            out / "output.npz",
            out / "output" / "baredSC_neff.txt",
            out / "QC",
            out / "output" / "baredSC_pdf.txt",
            out / f"baredSC.{cls._image_format(inputs)}",
            out / "other_outputs",
            out / "logevidence.txt",
        ]

    @classmethod
    def _append_required_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        filetype = str(inputs.get("filetype", "tabular") or "tabular")
        if filetype == "anndata":
            cmd.extend(["--inputAnnData", str(inputs.get("inputAnnData", "") or "")])
        else:
            cmd.extend(["--input", str(inputs.get("input", "") or "")])
        cmd.extend(["--geneColName", str(inputs.get("geneColName", "") or "")])

    @classmethod
    def _append_filters(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        count = int(str(inputs.get("filter_nb", "0") or "0"))
        for idx in range(1, count + 1):
            cmd.extend(
                [
                    f"--metadata{idx}ColName",
                    str(inputs.get(f"metadata{idx}ColName", "") or ""),
                    f"--metadata{idx}Values",
                    str(inputs.get(f"metadata{idx}Values", "") or ""),
                ]
            )

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        cmd.extend(
            [
                "--xmin",
                str(inputs.get("xmin", 0)),
                "--xmax",
                str(inputs.get("xmax", 2.5)),
                "--xscale",
                scale,
            ]
        )
        if scale == "Seurat":
            cmd.extend(["--targetSum", str(inputs.get("targetSum", 10000))])
        cmd.extend(
            [
                "--nx",
                str(inputs.get("nx", 100)),
                "--minScale",
                str(inputs.get("minScalex", 0.1)),
                "--seed",
                str(inputs.get("seed", 1)),
                "--nnorm",
                str(inputs.get("nnorm", 2)),
                "--nsampMCMC",
                str(inputs.get("nsampMCMC", 100000)),
            ]
        )
        if str(inputs.get("automatic_restart", "yes") or "yes") == "yes":
            cmd.extend(["--minNeff", str(inputs.get("minNeff", 200))])

    @classmethod
    def _append_plots(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        title = str(inputs.get("title", "") or "")
        if title:
            cmd.extend(["--title", title])
        remove_first = int(inputs.get("removeFirstSamples", -1))
        if remove_first != -1:
            cmd.extend(["--removeFirstSamples", str(remove_first)])
        cmd.extend(["--nsampInPlot", str(inputs.get("nsampInPlot", 100000))])
        pretty_bins = int(inputs.get("prettyBins", -1))
        if pretty_bins != -1:
            cmd.extend(["--prettyBins", str(pretty_bins)])

    @classmethod
    def _append_advanced(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--osampx",
                str(inputs.get("osampx", 10)),
                "--osampxpdf",
                str(inputs.get("osampxpdf", 5)),
                "--coviscale",
                str(inputs.get("coviscale", 1)),
                "--nis",
                str(inputs.get("nis", 1000)),
            ]
        )
        if str(inputs.get("burn_custom", "no") or "no") == "yes":
            nsamp_burn = int(inputs.get("nsampBurnMCMC", -1))
            if nsamp_burn != -1:
                cmd.extend(["--nsampBurnMCMC", str(nsamp_burn)])
            cmd.extend(["--T0BurnMCMC", str(inputs.get("T0BurnMCMC", 100))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        image_format = cls._image_format(inputs)
        cmd = ["baredSC_1d"]
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(["--output", "output", "--figure", f"baredSC.{image_format}", "--logevidence", "logevidence.txt"])
        commands = [
            _shell_join(cmd),
            "mkdir QC output",
            "mv baredSC_convergence.* QC",
            f"mv baredSC_p.{shlex.quote(image_format)} QC",
            "mv baredSC_corner.* QC",
            "mv baredSC_neff.txt output",
            "mv baredSC_pdf.txt output",
            f"mv baredSC.{shlex.quote(image_format)} baredSC",
            "gunzip baredSC_means.txt.gz",
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "output").mkdir(parents=True, exist_ok=True)
        (out / "QC").mkdir(parents=True, exist_ok=True)
        (out / "other_outputs").mkdir(parents=True, exist_ok=True)
        return cls._output_paths(inputs, output_dir)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("geneColName", "")).strip():
            return "geneColName is required"
        filetype = str(inputs.get("filetype", "tabular") or "tabular")
        if filetype == "tabular" and not str(inputs.get("input", "")).strip():
            return "input is required when filetype is tabular"
        if filetype not in cls.FILETYPES:
            return f"filetype must be one of: {', '.join(cls.FILETYPES)}"
        if filetype == "anndata" and not str(inputs.get("inputAnnData", "")).strip():
            return "inputAnnData is required when filetype is anndata"
        filter_nb = str(inputs.get("filter_nb", "0") or "0")
        if filter_nb not in cls.FILTER_COUNTS:
            return f"filter_nb must be one of: {', '.join(cls.FILTER_COUNTS)}"
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        if scale not in cls.SCALE_OPTIONS:
            return f"xscale must be one of: {', '.join(cls.SCALE_OPTIONS)}"
        restart = str(inputs.get("automatic_restart", "yes") or "yes")
        if restart not in cls.RESTART_OPTIONS:
            return f"automatic_restart must be one of: {', '.join(cls.RESTART_OPTIONS)}"
        image_format = cls._image_format(inputs)
        if image_format not in cls.IMAGE_FORMATS:
            return f"image_file_format must be one of: {', '.join(cls.IMAGE_FORMATS)}"
        numeric_mins = {
            "nx": (1, int, 100),
            "nnorm": (1, int, 2),
            "nsampMCMC": (1, int, 100000),
            "nsampInPlot": (1, int, 100000),
            "osampx": (1, int, 10),
            "osampxpdf": (1, int, 5),
        }
        for name, (minimum, caster, default) in numeric_mins.items():
            try:
                value = caster(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be numeric"
            if value < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "geneColName": ("STRING", {"description": "Name of the column with gene counts"}),
            },
            "optional": {
                "filetype": ("STRING", {"default": "tabular", "options": cls.FILETYPES}),
                "input": ("TSV", {"description": "Input count table with one row per cell"}),
                "inputAnnData": ("H5AD", {"description": "AnnData file containing raw counts"}),
                "filter_nb": ("STRING", {"default": "0", "options": cls.FILTER_COUNTS}),
                "metadata1ColName": ("STRING", {"default": ""}),
                "metadata1Values": ("STRING", {"default": ""}),
                "metadata2ColName": ("STRING", {"default": ""}),
                "metadata2Values": ("STRING", {"default": ""}),
                "metadata3ColName": ("STRING", {"default": ""}),
                "metadata3Values": ("STRING", {"default": ""}),
                "xmin": ("FLOAT", {"default": 0}),
                "xmax": ("FLOAT", {"default": 2.5}),
                "xscale": ("STRING", {"default": "Seurat", "options": cls.SCALE_OPTIONS}),
                "targetSum": ("FLOAT", {"default": 10000}),
                "nx": ("INT", {"default": 100, "min": 1}),
                "minScalex": ("FLOAT", {"default": 0.1}),
                "seed": ("INT", {"default": 1}),
                "nnorm": ("INT", {"default": 2, "min": 1}),
                "nsampMCMC": ("INT", {"default": 100000, "min": 1}),
                "automatic_restart": ("STRING", {"default": "yes", "options": cls.RESTART_OPTIONS}),
                "minNeff": ("FLOAT", {"default": 200}),
                "image_file_format": ("STRING", {"default": "png", "options": cls.IMAGE_FORMATS}),
                "title": ("STRING", {"default": ""}),
                "removeFirstSamples": ("INT", {"default": -1}),
                "nsampInPlot": ("INT", {"default": 100000, "min": 1}),
                "prettyBins": ("INT", {"default": -1, "min": -1}),
                "osampx": ("INT", {"default": 10, "min": 1, "advanced": True}),
                "osampxpdf": ("INT", {"default": 5, "min": 1, "advanced": True}),
                "coviscale": ("FLOAT", {"default": 1, "advanced": True}),
                "nis": ("INT", {"default": 1000, "advanced": True}),
                "burn_custom": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "nsampBurnMCMC": ("INT", {"default": -1, "advanced": True}),
                "T0BurnMCMC": ("FLOAT", {"default": 100, "min": 1, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Baredsc2DNode(Baredsc1DNode):
    """Estimate a two-dimensional baredSC expression distribution."""

    NODE_ID = "baredsc_2d"
    DISPLAY_NAME = "baredSC 2d"
    DESCRIPTION = "Compute a two-dimensional baredSC expression distribution for a pair of genes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "baredSC",
        "baredsc_2d",
        "baredSC 2d",
        "pair of genes",
        "two-gene expression distribution",
        "single-cell expression distribution",
        "Bayesian Approach",
        "correlation",
        "splity",
        "MCMC",
    ]
    RETURN_TYPES = ("NPZ", "TXT", "DIRECTORY", "TSV", "TSV", "IMAGE", "DIRECTORY", "TXT")
    RETURN_NAMES = ("output", "neff", "qc_plots", "pdf2d", "pdf2d_flat", "plot", "other_outputs", "logevidence")
    REQUIRED_EXECUTABLES = ["baredSC_2d", "mkdir", "mv"]

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [
            out / "output.npz",
            out / "output" / "baredSC_neff.txt",
            out / "QC",
            out / "output" / "baredSC_pdf2d.txt",
            out / "output" / "baredSC_pdf2d_flat.txt",
            out / f"baredSC.{cls._image_format(inputs)}",
            out / "other_outputs",
            out / "logevidence.txt",
        ]

    @classmethod
    def _append_required_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        filetype = str(inputs.get("filetype", "tabular") or "tabular")
        if filetype == "anndata":
            cmd.extend(["--inputAnnData", str(inputs.get("inputAnnData", "") or "")])
        else:
            cmd.extend(["--input", str(inputs.get("input", "") or "")])
        cmd.extend(
            [
                "--geneXColName",
                str(inputs.get("geneXColName", "") or ""),
                "--geneYColName",
                str(inputs.get("geneYColName", "") or ""),
            ]
        )

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        cmd.extend(
            [
                "--xmin",
                str(inputs.get("xmin", 0)),
                "--xmax",
                str(inputs.get("xmax", 2.5)),
                "--nx",
                str(inputs.get("nx", 100)),
                "--minScalex",
                str(inputs.get("minScalex", 0.1)),
                "--ymin",
                str(inputs.get("ymin", 0)),
                "--ymax",
                str(inputs.get("ymax", 2.5)),
                "--ny",
                str(inputs.get("ny", 100)),
                "--minScaley",
                str(inputs.get("minScaley", 0.1)),
                "--scale",
                scale,
            ]
        )
        if scale == "Seurat":
            cmd.extend(["--targetSum", str(inputs.get("targetSum", 10000))])
        cmd.extend(
            [
                "--seed",
                str(inputs.get("seed", 1)),
                "--nnorm",
                str(inputs.get("nnorm", 2)),
                "--nsampMCMC",
                str(inputs.get("nsampMCMC", 100000)),
            ]
        )
        if str(inputs.get("automatic_restart", "yes") or "yes") == "yes":
            cmd.extend(["--minNeff", str(inputs.get("minNeff", 200))])

    @classmethod
    def _append_plots(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        super()._append_plots(cmd, inputs)
        pretty_bins_x = int(inputs.get("prettyBinsx", -1))
        if pretty_bins_x != -1:
            cmd.extend(["--prettyBinsx", str(pretty_bins_x)])
        pretty_bins_y = int(inputs.get("prettyBinsy", -1))
        if pretty_bins_y != -1:
            cmd.extend(["--prettyBinsy", str(pretty_bins_y)])
        splity = str(inputs.get("splity", "") or "")
        if splity:
            cmd.extend(["--splity", splity])
        if inputs.get("log1pColorScale", False):
            cmd.append("--log1pColorScale")

    @classmethod
    def _append_advanced(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--osampx",
                str(inputs.get("osampx", 10)),
                "--osampxpdf",
                str(inputs.get("osampxpdf", 4)),
                "--osampy",
                str(inputs.get("osampy", 10)),
                "--osampypdf",
                str(inputs.get("osampypdf", 4)),
                "--coviscale",
                str(inputs.get("coviscale", 1)),
                "--nis",
                str(inputs.get("nis", 1000)),
                "--scalePrior",
                str(inputs.get("scalePrior", 0.3)),
            ]
        )
        if str(inputs.get("burn_custom", "no") or "no") == "yes":
            nsamp_burn = int(inputs.get("nsampBurnMCMC", -1))
            if nsamp_burn != -1:
                cmd.extend(["--nsampBurnMCMC", str(nsamp_burn)])
            cmd.extend(["--T0BurnMCMC", str(inputs.get("T0BurnMCMC", 100))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        image_format = cls._image_format(inputs)
        cmd = ["baredSC_2d"]
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(["--output", "output", "--figure", f"baredSC.{image_format}", "--logevidence", "logevidence.txt"])
        commands = [
            _shell_join(cmd),
            "mkdir QC",
            "mv baredSC_convergence.* QC",
            f"mv baredSC_p.{shlex.quote(image_format)} QC",
            "mv baredSC_corner.* QC",
            "mkdir output",
            "mv baredSC_neff.txt output",
            "mv baredSC_pdf2d.txt output",
            "mv baredSC_pdf2d_flat.txt output",
            f"mv baredSC.{shlex.quote(image_format)} baredSC",
        ]
        splity = str(inputs.get("splity", "") or "")
        commands.extend(
            _shell_join(["mv", f"baredSC_split{value}.txt", f"baredSC_split{value}_pdf.txt"])
            for value in splity.split()
        )
        return " && ".join(commands)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("geneXColName", "")).strip():
            return "geneXColName is required"
        if not str(inputs.get("geneYColName", "")).strip():
            return "geneYColName is required"
        filetype = str(inputs.get("filetype", "tabular") or "tabular")
        if filetype == "tabular" and not str(inputs.get("input", "")).strip():
            return "input is required when filetype is tabular"
        if filetype not in cls.FILETYPES:
            return f"filetype must be one of: {', '.join(cls.FILETYPES)}"
        if filetype == "anndata" and not str(inputs.get("inputAnnData", "")).strip():
            return "inputAnnData is required when filetype is anndata"
        filter_nb = str(inputs.get("filter_nb", "0") or "0")
        if filter_nb not in cls.FILTER_COUNTS:
            return f"filter_nb must be one of: {', '.join(cls.FILTER_COUNTS)}"
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        if scale not in cls.SCALE_OPTIONS:
            return f"xscale must be one of: {', '.join(cls.SCALE_OPTIONS)}"
        restart = str(inputs.get("automatic_restart", "yes") or "yes")
        if restart not in cls.RESTART_OPTIONS:
            return f"automatic_restart must be one of: {', '.join(cls.RESTART_OPTIONS)}"
        image_format = cls._image_format(inputs)
        if image_format not in cls.IMAGE_FORMATS:
            return f"image_file_format must be one of: {', '.join(cls.IMAGE_FORMATS)}"
        splity = str(inputs.get("splity", "") or "")
        if splity:
            try:
                [float(value) for value in splity.split()]
            except ValueError:
                return "splity must be space-separated numeric thresholds"
        numeric_mins = {
            "nx": (1, int, 100),
            "ny": (1, int, 100),
            "nnorm": (1, int, 2),
            "nsampMCMC": (1, int, 100000),
            "nsampInPlot": (1, int, 100000),
            "osampx": (1, int, 10),
            "osampxpdf": (1, int, 4),
            "osampy": (1, int, 10),
            "osampypdf": (1, int, 4),
        }
        for name, (minimum, caster, default) in numeric_mins.items():
            try:
                value = caster(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be numeric"
            if value < minimum:
                return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "geneXColName": ("STRING", {"description": "Name of the x-axis gene count column"}),
                "geneYColName": ("STRING", {"description": "Name of the y-axis gene count column"}),
            },
            "optional": {
                "filetype": ("STRING", {"default": "tabular", "options": cls.FILETYPES}),
                "input": ("TSV", {"description": "Input count table with one row per cell"}),
                "inputAnnData": ("H5AD", {"description": "AnnData file containing raw counts"}),
                "filter_nb": ("STRING", {"default": "0", "options": cls.FILTER_COUNTS}),
                "metadata1ColName": ("STRING", {"default": ""}),
                "metadata1Values": ("STRING", {"default": ""}),
                "metadata2ColName": ("STRING", {"default": ""}),
                "metadata2Values": ("STRING", {"default": ""}),
                "metadata3ColName": ("STRING", {"default": ""}),
                "metadata3Values": ("STRING", {"default": ""}),
                "xmin": ("FLOAT", {"default": 0}),
                "xmax": ("FLOAT", {"default": 2.5}),
                "nx": ("INT", {"default": 100, "min": 1}),
                "minScalex": ("FLOAT", {"default": 0.1}),
                "ymin": ("FLOAT", {"default": 0}),
                "ymax": ("FLOAT", {"default": 2.5}),
                "ny": ("INT", {"default": 100, "min": 1}),
                "minScaley": ("FLOAT", {"default": 0.1}),
                "xscale": ("STRING", {"default": "Seurat", "options": cls.SCALE_OPTIONS}),
                "targetSum": ("FLOAT", {"default": 10000}),
                "seed": ("INT", {"default": 1}),
                "nnorm": ("INT", {"default": 2, "min": 1}),
                "nsampMCMC": ("INT", {"default": 100000, "min": 1}),
                "automatic_restart": ("STRING", {"default": "yes", "options": cls.RESTART_OPTIONS}),
                "minNeff": ("FLOAT", {"default": 200}),
                "image_file_format": ("STRING", {"default": "png", "options": cls.IMAGE_FORMATS}),
                "title": ("STRING", {"default": ""}),
                "removeFirstSamples": ("INT", {"default": -1}),
                "nsampInPlot": ("INT", {"default": 100000, "min": 1}),
                "prettyBinsx": ("INT", {"default": -1, "min": -1}),
                "prettyBinsy": ("INT", {"default": -1, "min": -1}),
                "log1pColorScale": ("BOOLEAN", {"default": False}),
                "splity": ("STRING", {"default": ""}),
                "osampx": ("INT", {"default": 10, "min": 1, "advanced": True}),
                "osampxpdf": ("INT", {"default": 4, "min": 1, "advanced": True}),
                "osampy": ("INT", {"default": 10, "min": 1, "advanced": True}),
                "osampypdf": ("INT", {"default": 4, "min": 1, "advanced": True}),
                "coviscale": ("FLOAT", {"default": 1, "advanced": True}),
                "nis": ("INT", {"default": 1000, "advanced": True}),
                "scalePrior": ("FLOAT", {"default": 0.3, "advanced": True}),
                "burn_custom": ("STRING", {"default": "no", "options": ["no", "yes"], "advanced": True}),
                "nsampBurnMCMC": ("INT", {"default": -1, "advanced": True}),
                "T0BurnMCMC": ("FLOAT", {"default": 100, "min": 1, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class BaredscCombine1DNode(Baredsc1DNode):
    """Combine multiple one-dimensional baredSC model archives."""

    NODE_ID = "baredsc_combine_1d"
    DISPLAY_NAME = "Combine multiple 1D Models"
    DESCRIPTION = "Combine multiple one-dimensional baredSC model archives for a single gene."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "baredSC",
        "baredsc_combine_1d",
        "Combine multiple 1D Models",
        "combine 1D",
        "model averaging",
        "single gene",
        "Bayesian Approach",
        "MCMC",
    ]
    RETURN_TYPES = ("TSV", "IMAGE", "DIRECTORY")
    RETURN_NAMES = ("pdf", "plot", "other_outputs")
    REQUIRED_EXECUTABLES = ["combineMultipleModels_1d", "ln", "mkdir", "mv", "gunzip"]

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        cmd.extend(
            [
                "--xmin",
                str(inputs.get("xmin", 0)),
                "--xmax",
                str(inputs.get("xmax", 2.5)),
                "--xscale",
                scale,
            ]
        )
        if scale == "Seurat":
            cmd.extend(["--targetSum", str(inputs.get("targetSum", 10000))])
        cmd.extend(
            [
                "--nx",
                str(inputs.get("nx", 100)),
                "--minScale",
                str(inputs.get("minScalex", 0.1)),
                "--seed",
                str(inputs.get("seed", 1)),
            ]
        )

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [
            out / "output" / "baredSC_pdf.txt",
            out / f"baredSC.{cls._image_format(inputs)}",
            out / "other_outputs",
        ]

    @classmethod
    def _append_model_outputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        outputs = _as_list(inputs.get("outputs"))
        cmd.append("--outputs")
        cmd.extend(str(idx) for idx, _ in enumerate(outputs))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        outputs = _as_list(inputs.get("outputs"))
        commands = [_shell_join(["ln", "-s", output, f"{idx}.npz"]) for idx, output in enumerate(outputs)]
        image_format = cls._image_format(inputs)
        cmd = ["combineMultipleModels_1d"]
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_model_outputs(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(["--figure", f"baredSC.{image_format}"])
        commands.extend(
            [
                _shell_join(cmd),
                "mkdir output",
                "mv baredSC_pdf.txt output",
                f"mv baredSC.{shlex.quote(image_format)} baredSC",
                "gunzip baredSC_means.txt.gz",
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "output").mkdir(parents=True, exist_ok=True)
        (out / "other_outputs").mkdir(parents=True, exist_ok=True)
        return cls._output_paths(inputs, output_dir)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("outputs")):
            return "outputs is required"
        result = super().VALIDATE_INPUTS(inputs)
        if result is not True:
            return result
        try:
            pretty_bins = int(inputs.get("prettyBins", -1))
        except (TypeError, ValueError):
            return "prettyBins must be numeric"
        if pretty_bins < -1:
            return "prettyBins must be greater than or equal to -1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        base = super().INPUT_TYPES()
        required = {"outputs": ("FILE", {"is_list": True, "description": "baredSC 1D model archives to combine"})}
        required.update(base["required"])
        base["required"] = required
        return base

class BaredscCombine2DNode(Baredsc2DNode):
    """Combine multiple two-dimensional baredSC model archives."""

    NODE_ID = "baredsc_combine_2d"
    DISPLAY_NAME = "Combine multiple 2D Models"
    DESCRIPTION = "Combine multiple two-dimensional baredSC model archives for a pair of genes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "baredSC",
        "baredsc_combine_2d",
        "Combine multiple 2D Models",
        "combine 2D",
        "model averaging",
        "pair of genes",
        "Bayesian Approach",
        "correlation",
        "MCMC",
    ]
    RETURN_TYPES = ("TSV", "TSV", "IMAGE", "DIRECTORY")
    RETURN_NAMES = ("pdf2d", "pdf2d_flat", "plot", "other_outputs")
    REQUIRED_EXECUTABLES = ["combineMultipleModels_2d", "ln", "mkdir", "mv"]

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [
            out / "output" / "baredSC_pdf2d.txt",
            out / "output" / "baredSC_pdf2d_flat.txt",
            out / f"baredSC.{cls._image_format(inputs)}",
            out / "other_outputs",
        ]

    @classmethod
    def _append_model_outputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        outputs = _as_list(inputs.get("outputs"))
        cmd.append("--outputs")
        cmd.extend(str(idx) for idx, _ in enumerate(outputs))

    @classmethod
    def _append_mcmc(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        scale = str(inputs.get("xscale", "Seurat") or "Seurat")
        cmd.extend(
            [
                "--xmin",
                str(inputs.get("xmin", 0)),
                "--xmax",
                str(inputs.get("xmax", 2.5)),
                "--nx",
                str(inputs.get("nx", 100)),
                "--minScalex",
                str(inputs.get("minScalex", 0.1)),
                "--ymin",
                str(inputs.get("ymin", 0)),
                "--ymax",
                str(inputs.get("ymax", 2.5)),
                "--ny",
                str(inputs.get("ny", 100)),
                "--minScaley",
                str(inputs.get("minScaley", 0.1)),
                "--scale",
                scale,
            ]
        )
        if scale == "Seurat":
            cmd.extend(["--targetSum", str(inputs.get("targetSum", 10000))])
        cmd.extend(["--seed", str(inputs.get("seed", 1))])

    @classmethod
    def _append_advanced(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--osampx",
                str(inputs.get("osampx", 10)),
                "--osampxpdf",
                str(inputs.get("osampxpdf", 4)),
                "--osampy",
                str(inputs.get("osampy", 10)),
                "--osampypdf",
                str(inputs.get("osampypdf", 4)),
                "--coviscale",
                str(inputs.get("coviscale", 1)),
                "--nis",
                str(inputs.get("nis", 1000)),
                "--scalePrior",
                str(inputs.get("scalePrior", 0.3)),
            ]
        )
        if inputs.get("getPVal", False):
            cmd.append("--getPVal")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        outputs = _as_list(inputs.get("outputs"))
        commands = [_shell_join(["ln", "-s", output, f"{idx}.npz"]) for idx, output in enumerate(outputs)]
        image_format = cls._image_format(inputs)
        cmd = ["combineMultipleModels_2d"]
        cls._append_required_inputs(cmd, inputs)
        cls._append_filters(cmd, inputs)
        cls._append_model_outputs(cmd, inputs)
        cls._append_mcmc(cmd, inputs)
        cls._append_plots(cmd, inputs)
        cls._append_advanced(cmd, inputs)
        cmd.extend(["--figure", f"baredSC.{image_format}"])
        commands.extend(
            [
                _shell_join(cmd),
                "mkdir output",
                "mv baredSC_pdf2d.txt output",
                "mv baredSC_pdf2d_flat.txt output",
                f"mv baredSC.{shlex.quote(image_format)} baredSC",
            ]
        )
        splity = str(inputs.get("splity", "") or "")
        commands.extend(
            _shell_join(["mv", f"baredSC_split{value}.txt", f"baredSC_split{value}_pdf.txt"])
            for value in splity.split()
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "output").mkdir(parents=True, exist_ok=True)
        (out / "other_outputs").mkdir(parents=True, exist_ok=True)
        return cls._output_paths(inputs, output_dir)

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("outputs")):
            return "outputs is required"
        result = super().VALIDATE_INPUTS(inputs)
        if result is not True:
            return result
        for name in ("prettyBinsx", "prettyBinsy"):
            try:
                value = int(inputs.get(name, -1))
            except (TypeError, ValueError):
                return f"{name} must be numeric"
            if value < -1:
                return f"{name} must be greater than or equal to -1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        base = super().INPUT_TYPES()
        required = {"outputs": ("FILE", {"is_list": True, "description": "baredSC 2D model archives to combine"})}
        required.update(base["required"])
        base["required"] = required
        optional = dict(base["optional"])
        optional["getPVal"] = (
            "BOOLEAN",
            {"default": False, "advanced": True, "description": "Use fewer samples to estimate the p-value"},
        )
        base["optional"] = optional
        return base

pin_contract(Baredsc1DNode)
pin_contract(Baredsc2DNode)
pin_contract(BaredscCombine1DNode)
pin_contract(BaredscCombine2DNode)

__all__ = ['Baredsc1DNode', 'Baredsc2DNode', 'BaredscCombine1DNode', 'BaredscCombine2DNode']
