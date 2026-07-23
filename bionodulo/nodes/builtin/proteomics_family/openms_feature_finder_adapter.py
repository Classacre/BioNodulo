"""OpenMS 3.5.0 FeatureFinderCentroided contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import ProteomicsCommandNode, path_value, validate_int, validate_number


class OpenMSFeatureFinderNode(ProteomicsCommandNode):
    """Detect two-dimensional features in centroided LC-MS data."""

    LEGACY_NODE_ID = "openms_feature_finder"
    DISPLAY_NAME = "OpenMS FeatureFinder"
    DESCRIPTION = "Detect two-dimensional peptide features with OpenMS 3.5.0 FeatureFinderCentroided."
    SEARCH_ALIASES = ["BioNodulo builtin", "OpenMS", "FeatureFinderCentroided", "LC-MS features"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("feature_xml",)
    REQUIRED_EXECUTABLES = ["FeatureFinderCentroided"]
    REQUIRED_CONDA_PACKAGES = ["openms"]
    REQUIRED_PATH_INPUTS = ("mzml_file",)
    OUTPUT_FILENAMES = ("feature_xml.featureXML",)
    VERSION = "3.5.0"
    GIT_URL = "https://github.com/OpenMS/OpenMS.git"
    GIT_COMMIT = "c49149d47d6fcc76d1271d87d3a7fad15d2219de"
    DOCUMENTATION_URL = (
        "https://openms.de/doxygen/release/3.5.0/html/"
        "TOPP_FeatureFinderCentroided.html"
    )
    UPSTREAM_SOURCE = (
        "src/topp/FeatureFinderCentroided.cpp and "
        "src/openms/source/FEATUREFINDER/FeatureFinderAlgorithmPicked.cpp"
    )
    PACKAGE_AUTHORITY = (
        "Bioconda openms 3.5.0 recipe at "
        "0f45cb6931cc383705d156ad4e7e8c7e5015b505"
    )
    CITATION_DOIS = ["10.1021/pr300992u"]
    CITATION_URLS = ["https://doi.org/10.1021/pr300992u"]
    CITATION_TEXT = "An automated pipeline for high-throughput label-free quantitative proteomics."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mzml_file": ("FILE", {"description": "Centroided MS1 mzML input"}),
            },
            "optional": {
                "ini_file": ("FILE", {"default": "", "description": "OpenMS INI file"}),
                "seeds_file": ("FILE", {"default": "", "description": "Optional featureXML seed list"}),
                "mass_trace_mz_tolerance": (
                    "FLOAT",
                    {"default": None, "min": 0.0, "description": "Mass-trace m/z tolerance"},
                ),
                "isotope_mz_tolerance": (
                    "FLOAT",
                    {"default": None, "min": 0.0, "description": "Isotope-pattern m/z tolerance"},
                ),
                "min_spectra": (
                    "INT",
                    {"default": None, "min": 1, "description": "Minimum spectra in a mass trace"},
                ),
                "force_profile_input": (
                    "BOOLEAN",
                    {"default": False, "description": "Allow profile data despite centroided expectation"},
                ),
                "faims_merge_features": (
                    "BOOLEAN",
                    {"default": True, "description": "Merge matching features across FAIMS CV values"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("mass_trace_mz_tolerance", "isotope_mz_tolerance"):
            if inputs.get(key) is not None:
                validation = validate_number(inputs[key], key, minimum=0.0)
                if validation is not True:
                    return validation
        if inputs.get("min_spectra") is not None:
            validation = validate_int(inputs["min_spectra"], "min_spectra", minimum=1)
            if validation is not True:
                return validation
        return validate_int(inputs.get("threads", 1), "threads", minimum=1, maximum=128)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", "."))) / cls.OUTPUT_FILENAMES[0]
        command = [
            "FeatureFinderCentroided",
            "-in",
            path_value(inputs["mzml_file"]),
            "-out",
            str(output),
        ]
        if path_value(inputs.get("ini_file")):
            command.extend(["-ini", path_value(inputs["ini_file"])])
        if path_value(inputs.get("seeds_file")):
            command.extend(["-seeds", path_value(inputs["seeds_file"])])
        if inputs.get("mass_trace_mz_tolerance") is not None:
            command.extend(
                [
                    "-algorithm:mass_trace:mz_tolerance",
                    str(inputs["mass_trace_mz_tolerance"]),
                ]
            )
        if inputs.get("isotope_mz_tolerance") is not None:
            command.extend(
                [
                    "-algorithm:isotopic_pattern:mz_tolerance",
                    str(inputs["isotope_mz_tolerance"]),
                ]
            )
        if inputs.get("min_spectra") is not None:
            command.extend(["-algorithm:mass_trace:min_spectra", str(inputs["min_spectra"])])
        if inputs.get("force_profile_input", False):
            command.append("-force")
        command.extend(
            [
                "-faims_merge_features",
                "true" if inputs.get("faims_merge_features", True) else "false",
                "-threads",
                str(inputs.get("threads", 1)),
            ]
        )
        return command


class OpenMSFeatureNode(OpenMSFeatureFinderNode):
    """Compatibility alias for the original OpenMS feature node ID."""

    LEGACY_NODE_ID = "openms_feature"
    DISPLAY_NAME = "OpenMS Feature"
    DESCRIPTION = "Detect peptide features with OpenMS FeatureFinderCentroided."
    SEARCH_ALIASES = ["BioNodulo builtin", "OpenMS feature", "FeatureFinderCentroided", "LC-MS"]
