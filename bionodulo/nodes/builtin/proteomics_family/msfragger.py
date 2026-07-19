"""MSFragger 4.2 licensed command contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    ProteomicsCommandNode,
    path_value,
    replace_assignments,
    require_file,
    stage_file,
    validate_choice,
    validate_int,
    validate_number,
)


def _spectrum_stem(value: Any) -> str:
    return Path(path_value(value)).stem


class MSFraggerNode(ProteomicsCommandNode):
    """Search one spectral file with a complete MSFragger 4.2 parameter template."""

    NODE_ID = "msfragger"
    DISPLAY_NAME = "MSFragger"
    DESCRIPTION = "Search one mass-spectrometry file with licensed MSFragger 4.2."
    SEARCH_ALIASES = ["BioNodulo builtin", "MSFragger", "FragPipe", "peptide identification"]
    RETURN_TYPES = ("FILE", "FILE", "FILE")
    RETURN_NAMES = ("pepxml", "pin_file", "params")
    REQUIRED_EXECUTABLES = ["msfragger"]
    REQUIRED_CONDA_PACKAGES = ["msfragger"]
    REQUIRED_PATH_INPUTS = ("spectra_file", "fasta_db", "params_template")
    VERSION = "4.2"
    GIT_URL = "https://github.com/Nesvilab/MSFragger.git"
    GIT_COMMIT = "8a143152285d36e2958e6e3013017fa4ca62fdcc"
    DOCUMENTATION_URL = (
        "https://github.com/Nesvilab/MSFragger/tree/"
        "8a143152285d36e2958e6e3013017fa4ca62fdcc/parameter_files"
    )
    UPSTREAM_SOURCE = "README.md and parameter_files/closed_fragger.params"
    PACKAGE_AUTHORITY = (
        "Bioconda msfragger 4.2 recipe and license-key wrapper at "
        "0f45cb6931cc383705d156ad4e7e8c7e5015b505"
    )
    INSTALLATION_REQUIRED = "Academic or commercial MSFragger 4.2 license key"
    CITATION_DOIS = ["10.1038/nmeth.4256"]
    CITATION_URLS = ["https://doi.org/10.1038/nmeth.4256"]
    CITATION_TEXT = "MSFragger: ultrafast and comprehensive peptide identification."
    CALIBRATION_MODES = (0, 1, 2, 4)
    RUN_IN_NODE_OUTPUT_DIR = True
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "spectra_file": ("FILE", {"description": "One mzML, mzXML, RAW, MGF, or Bruker input"}),
                "fasta_db": ("FASTA", {"description": "Target-decoy protein FASTA"}),
                "params_template": (
                    "FILE",
                    {"description": "Complete MSFragger-4.2 parameter file"},
                ),
                "license_key": (
                    "STRING",
                    {"description": "MSFragger license key obtained from Nesvilab"},
                ),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
                "precursor_mass_lower": ("FLOAT", {"default": -20.0}),
                "precursor_mass_upper": ("FLOAT", {"default": 20.0}),
                "precursor_mass_units": ("STRING", {"default": "ppm", "options": ["Da", "ppm"]}),
                "fragment_mass_tolerance": ("FLOAT", {"default": 20.0, "min": 0.0}),
                "fragment_mass_units": ("STRING", {"default": "ppm", "options": ["Da", "ppm"]}),
                "calibrate_mass": (
                    "INT",
                    {"default": 2, "options": list(cls.CALIBRATION_MODES)},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("license_key", "")).strip():
            return "Input 'license_key' must be non-empty"
        validation = validate_int(inputs.get("threads", 4), "threads", minimum=1, maximum=128)
        if validation is not True:
            return validation
        for key in ("precursor_mass_lower", "precursor_mass_upper"):
            validation = validate_number(inputs.get(key, -20.0 if key.endswith("lower") else 20.0), key)
            if validation is not True:
                return validation
        if float(inputs.get("precursor_mass_lower", -20.0)) > float(inputs.get("precursor_mass_upper", 20.0)):
            return "Input 'precursor_mass_lower' must not exceed 'precursor_mass_upper'"
        validation = validate_number(
            inputs.get("fragment_mass_tolerance", 20.0),
            "fragment_mass_tolerance",
            minimum=0.0,
        )
        if validation is not True:
            return validation
        for key in ("precursor_mass_units", "fragment_mass_units"):
            validation = validate_choice(inputs.get(key, "ppm"), key, ("Da", "ppm"))
            if validation is not True:
                return validation
        calibration = inputs.get("calibrate_mass", 2)
        if isinstance(calibration, bool) or calibration not in cls.CALIBRATION_MODES:
            return "Input 'calibrate_mass' must be one of: 0, 1, 2, 4"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        stem = _spectrum_stem(inputs.get("spectra_file")) or "spectrum"
        return [node_dir / f"{stem}.pepXML", node_dir / f"{stem}.pin", node_dir / "fragger.params"]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        cls.require_valid_inputs(inputs)
        node_dir = outputs[0].parent
        staged_spectrum = stage_file(inputs["spectra_file"], "spectra_file", node_dir)
        template = require_file(inputs["params_template"], "params_template")
        text = template.read_text(encoding="utf-8")
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line != "# MSFragger-4.2":
            raise ValueError("MSFragger parameter template must start with '# MSFragger-4.2'")
        unit_code = {"Da": 0, "ppm": 1}
        rendered = replace_assignments(
            text,
            {
                "database_name": str(Path(path_value(inputs["fasta_db"])).resolve()),
                "num_threads": inputs.get("threads", 4),
                "precursor_mass_lower": inputs.get("precursor_mass_lower", -20.0),
                "precursor_mass_upper": inputs.get("precursor_mass_upper", 20.0),
                "precursor_mass_units": unit_code[str(inputs.get("precursor_mass_units", "ppm"))],
                "fragment_mass_tolerance": inputs.get("fragment_mass_tolerance", 20.0),
                "fragment_mass_units": unit_code[str(inputs.get("fragment_mass_units", "ppm"))],
                "calibrate_mass": inputs.get("calibrate_mass", 2),
                "output_format": "pepxml_pin",
            },
        )
        outputs[2].write_text(rendered, encoding="utf-8")
        inputs["_msfragger_params"] = str(outputs[2])
        inputs["_msfragger_spectrum"] = str(staged_spectrum)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", ".")))
        params = str(inputs.get("_msfragger_params", output / "fragger.params"))
        spectrum = str(
            inputs.get(
                "_msfragger_spectrum",
                output / Path(path_value(inputs.get("spectra_file"))).name,
            )
        )
        return ["msfragger", "--key", str(inputs["license_key"]), params, spectrum]
