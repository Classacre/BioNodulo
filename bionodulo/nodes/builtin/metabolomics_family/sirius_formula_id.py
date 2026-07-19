"""SIRIUS 5.8.6 molecular-formula and optional structure identification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    MetabolomicsCommandNode,
    path_value,
    safe_output_stem,
    validate_choice,
    validate_number,
)


class SiriusFormulaIDNode(MetabolomicsCommandNode):
    """Run a documented SIRIUS 5.8.6 compound-tool chain."""

    NODE_ID = "sirius_formula_id"
    DISPLAY_NAME = "SIRIUS Formula ID"
    DESCRIPTION = "Identify molecular formulas and optional structures with SIRIUS 5.8.6."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "SIRIUS",
        "ZODIAC",
        "CSI:FingerID",
        "CANOPUS",
        "molecular formula",
        "metabolomics",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("project_space",)
    OUTPUT_SUFFIXES = ("",)
    REQUIRED_EXECUTABLES: list[str] = []
    EXTERNAL_REQUIRED_EXECUTABLES = ("sirius",)
    REQUIRED_CONDA_PACKAGES: list[str] = []
    CONDA_PACKAGE_CONSTRAINTS: dict[str, str] = {}
    VERSION = "5.8.6"
    GIT_URL = "https://github.com/sirius-ms/sirius.git"
    GIT_COMMIT = "03af898a944ada6527bbbabd8f85e2e00c6c4d5b"
    DOCUMENTATION_URL = "https://v5.docs.sirius-ms.io/cli/"
    SOURCE_URL = GIT_URL
    UPSTREAM_SOURCE = (
        "sirius_cli/.../CLIRootOptions.java; InputFilesOptions.java; "
        "sirius/SiriusOptions.java; fingerblast/FingerblastOptions.java"
    )
    EXTERNAL_INSTALLATION = (
        "SIRIUS 5.8.6 is not provided by Bioconda; stage an official SIRIUS installation on PATH."
    )
    NETWORK_SEMANTICS = (
        "formula and ZODIAC can run locally; structure search and CANOPUS use the SIRIUS web service "
        "and require a logged-in SIRIUS workspace/subscription."
    )
    EXIT_SEMANTICS = (
        "SIRIUS non-zero exit status is fatal; BioNodulo requires the native project-space path to exist."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "spectra_file": (
                    "FILE",
                    {"description": "SIRIUS input in .ms, .mgf, .mzML/.mzXML, or project-space format"},
                ),
            },
            "optional": {
                "cores": ("INT", {"default": 1, "min": 1, "max": 64}),
                "profile": (
                    "STRING",
                    {"default": "", "options": ["", "default", "qtof", "orbitrap", "fticr"]},
                ),
                "ppm_max": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "formula_database": (
                    "STRING",
                    {"default": "", "description": "Comma-separated formula-search databases"},
                ),
                "ions_considered": (
                    "STRING",
                    {"default": "", "description": "Comma-separated adducts for --ions-considered"},
                ),
                "ions_enforced": (
                    "STRING",
                    {"default": "", "description": "Comma-separated adducts for --ions-enforced"},
                ),
                "run_zodiac": ("BOOLEAN", {"default": True}),
                "run_structure": ("BOOLEAN", {"default": False}),
                "structure_database": (
                    "STRING",
                    {"default": "", "description": "Comma-separated CSI:FingerID structure databases"},
                ),
                "run_canopus": ("BOOLEAN", {"default": False}),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("spectra_file")):
            return "Input 'spectra_file' must be a non-empty path-like value"
        validation = validate_number(inputs.get("cores", 1), "cores", minimum=1, maximum=64, integer=True)
        if validation is not True:
            return validation
        validation = validate_number(inputs.get("ppm_max", 0.0), "ppm_max", minimum=0)
        if validation is not True:
            return validation
        validation = validate_choice(
            inputs.get("profile", ""),
            "profile",
            ("", "default", "qtof", "orbitrap", "fticr"),
        )
        if validation is not True:
            return validation
        if str(inputs.get("ions_considered", "")).strip() and str(inputs.get("ions_enforced", "")).strip():
            return "Use either 'ions_considered' or 'ions_enforced', not both"
        return True

    @classmethod
    def output_stem(cls, inputs: dict[str, Any], fallback: str) -> str:
        source = safe_output_stem(inputs.get("spectra_file"), "sirius")
        return safe_output_stem(inputs.get("output_name"), source)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        project_space = output / cls.output_stem(inputs, "sirius")
        command = [
            "sirius",
            "--input",
            path_value(inputs.get("spectra_file")),
            "--output",
            str(project_space),
            "--cores",
            str(inputs.get("cores", 1)),
            "formula",
        ]
        profile = str(inputs.get("profile", "") or "").strip()
        if profile:
            command.extend(["--profile", profile])
        ppm_max = float(inputs.get("ppm_max", 0.0) or 0.0)
        if ppm_max > 0:
            command.extend(["--ppm-max", str(inputs.get("ppm_max"))])
        formula_database = str(inputs.get("formula_database", "") or "").strip()
        if formula_database:
            command.extend(["--database", formula_database])
        ions_considered = str(inputs.get("ions_considered", "") or "").strip()
        ions_enforced = str(inputs.get("ions_enforced", "") or "").strip()
        if ions_considered:
            command.extend(["--ions-considered", ions_considered])
        if ions_enforced:
            command.extend(["--ions-enforced", ions_enforced])
        if inputs.get("run_zodiac", True):
            command.append("zodiac")
        if inputs.get("run_structure", False):
            command.append("structure")
            structure_database = str(inputs.get("structure_database", "") or "").strip()
            if structure_database:
                command.extend(["--database", structure_database])
        if inputs.get("run_canopus", False):
            command.append("canopus")
        return command
