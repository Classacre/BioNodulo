"""IQ-TREE 2.3.4 maximum-likelihood tree inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import PhylogenyCommandNode, path_value, validate_int


class IQTREENode(PhylogenyCommandNode):
    """Infer a maximum-likelihood tree from a multiple-sequence alignment."""

    NODE_ID = "iqtree"
    DISPLAY_NAME = "IQ-TREE"
    DESCRIPTION = "Maximum-likelihood tree inference with IQ-TREE 2.3.4."
    SEARCH_ALIASES = ["BioNodulo builtin", "IQ-TREE", "maximum likelihood", "phylogeny"]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("tree",)
    REQUIRED_EXECUTABLES = ["iqtree2"]
    REQUIRED_CONDA_PACKAGES = ["iqtree"]
    CONDA_PACKAGE_CONSTRAINTS = {"iqtree": "2.3.4"}
    PACKAGE_CONSTRAINTS = ("iqtree=2.3.4",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    REQUIRED_PATH_INPUTS = ("alignment",)
    OUTPUT_FILENAMES = ("tree.treefile",)
    VERSION = "2.3.4"
    GIT_URL = "https://github.com/iqtree/iqtree2.git"
    GIT_COMMIT = "33b2ab64cfa3a42364a175752ede881bfe5daf05"
    GIT_TAG = "v2.3.4"
    DOCUMENTATION_URL = "https://iqtree.github.io/doc/Command-Reference"
    UPSTREAM_SOURCE = "README.md; utils/tools.cpp:parseArg; tree/iqtree.cpp:treefile writers"
    SOURCE_AUTHORITIES = {
        "release": (GIT_TAG, GIT_COMMIT),
        "argv_and_bounds": "utils/tools.cpp:parseArg",
        "tree_output": "tree/iqtree.cpp:.treefile writers",
    }
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    EXIT_SEMANTICS = (
        "IQ-TREE argument, input, and inference failures exit non-zero. Exit zero is accepted only "
        "when the native .treefile exists, is non-empty, and terminates as Newick with a semicolon."
    )
    CITATION_DOIS = ["10.1093/molbev/msu300", "10.1093/molbev/msaa015"]
    CITATION_URLS = [
        "https://doi.org/10.1093/molbev/msu300",
        "https://doi.org/10.1093/molbev/msaa015",
    ]
    CITATION_TEXT = "IQ-TREE 2: New models and efficient methods for phylogenetic inference."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("ALIGNMENT", {"description": "FASTA, PHYLIP, NEXUS, Clustal, or MSF alignment"}),
            },
            "optional": {
                "threads": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "description": "Maximum threads used with IQ-TREE's automatic thread selection",
                    },
                ),
                "model": ("STRING", {"default": "MFP", "description": "IQ-TREE model string"}),
                "ufboot_replicates": (
                    "INT",
                    {"default": None, "min": 1000, "description": "Ultrafast bootstrap replicates; null disables"},
                ),
                "alrt_replicates": (
                    "INT",
                    {"default": None, "min": 0, "description": "SH-aLRT replicates; null disables and 0 selects parametric aLRT"},
                ),
                "seed": ("INT", {"default": None, "description": "Optional reproducibility seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("threads", 1), "threads", minimum=1)
        if validation is not True:
            return validation
        if not str(inputs.get("model", "MFP")).strip():
            return "Input 'model' must be non-empty"
        ufboot = inputs.get("ufboot_replicates")
        if ufboot is not None:
            validation = validate_int(ufboot, "ufboot_replicates", minimum=1000)
            if validation is not True:
                return validation
        alrt = inputs.get("alrt_replicates")
        if alrt is not None:
            validation = validate_int(alrt, "alrt_replicates", minimum=0)
            if validation is not True:
                return validation
            if 0 < alrt < 1000:
                return "Input 'alrt_replicates' must be 0 or at least 1000"
        if inputs.get("seed") is not None:
            validation = validate_int(inputs["seed"], "seed")
            if validation is not True:
                return validation
        alignment = Path(path_value(inputs.get("alignment")))
        if not alignment.is_file():
            return f"Input 'alignment' is not a materialized file: {alignment}"
        try:
            if alignment.stat().st_size == 0:
                return f"Input 'alignment' file is empty: {alignment}"
        except OSError as exc:
            return f"Cannot inspect input 'alignment' file {alignment}: {exc}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "iqtree2",
            "-s",
            path_value(inputs["alignment"]),
            "--prefix",
            str(output / "tree"),
            "-m",
            str(inputs.get("model", "MFP")),
            "-T",
            "AUTO",
            "--threads-max",
            str(inputs.get("threads", 1)),
        ]
        if inputs.get("ufboot_replicates") is not None:
            command.extend(["--ufboot", str(inputs["ufboot_replicates"])])
        if inputs.get("alrt_replicates") is not None:
            command.extend(["--alrt", str(inputs["alrt_replicates"])])
        if inputs.get("seed") is not None:
            command.extend(["--seed", str(inputs["seed"])])
        return command

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        result = await super().run(**kwargs)
        tree = Path(result[0])
        size = tree.stat().st_size
        if size == 0:
            raise RuntimeError("IQ-TREE produced an empty .treefile")
        with tree.open("rb") as handle:
            handle.seek(-min(size, 4096), 2)
            tail = handle.read()
        if not tail.rstrip().endswith(b";"):
            raise RuntimeError("IQ-TREE .treefile is not terminated Newick")
        return result
