"""CAMERA 1.66.0 isotope and adduct annotation for XCMS features."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import (
    MetabolomicsCommandNode,
    path_value,
    r_string,
    safe_output_stem,
    validate_choice,
    validate_number,
)


class CAMERAAnnotationNode(MetabolomicsCommandNode):
    """Convert an XCMS experiment and run CAMERA's documented annotation order."""

    NODE_ID = "camera_annotation"
    DISPLAY_NAME = "CAMERA Annotation"
    DESCRIPTION = "Annotate XCMS LC-MS peaks with CAMERA 1.66.0 isotopes and adducts."
    SEARCH_ALIASES = ["BioNodulo builtin", "CAMERA", "camera", "LC-MS", "isotopes", "adducts"]
    RETURN_TYPES = ("TSV", "FILE", "JSON")
    RETURN_NAMES = ("annotated_peaklist", "camera_object", "summary")
    OUTPUT_SUFFIXES = (".camera_peaklist.tsv", ".camera.rds", ".camera.summary.json")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = [
        "r-base",
        "bioconductor-camera",
        "bioconductor-xcms",
        "r-jsonlite",
        "r-readr",
    ]
    REQUIRED_R_PACKAGES = ["CAMERA", "xcms", "jsonlite", "readr"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "r-base": "4.5.*",
        "bioconductor-camera": "1.66.0",
        "bioconductor-xcms": "4.8.0",
        "r-jsonlite": "2.0.0",
        "r-readr": "2.2.0",
    }
    VERSION = "1.66.0"
    GIT_URL = "https://git.bioconductor.org/packages/CAMERA"
    GIT_COMMIT = "fcd3b860012e0c1b93b57390363c56c6e1b8230f"
    DOCUMENTATION_URL = "https://bioconductor.org/packages/release/bioc/html/CAMERA.html"
    SOURCE_URL = "https://git.bioconductor.org/packages/CAMERA"
    UPSTREAM_SOURCE = (
        "DESCRIPTION; man/groupFWHM-methods.Rd; man/findIsotopes-methods.Rd; "
        "man/groupCorr-methods.Rd; man/findAdducts-methods.Rd; man/getPeaklist-methods.Rd"
    )
    CITATION_DOIS = ["10.1021/ac202450g"]
    CITATION_URLS = ["https://doi.org/10.1021/ac202450g"]
    EXIT_SEMANTICS = (
        "CAMERA stops when the RDS cannot be converted to an MS1 xcmsSet or an annotation step fails; "
        "BioNodulo propagates that exit and requires all three artifacts."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"xcms_object": ("FILE", {"description": "Aligned XcmsExperiment RDS"})},
            "optional": {
                "polarity": ("STRING", {"default": "positive", "options": ["positive", "negative"]}),
                "perfwhm": ("FLOAT", {"default": 0.6, "min": 0.0}),
                "sigma": ("FLOAT", {"default": 6.0, "min": 0.0}),
                "maxcharge": ("INT", {"default": 3, "min": 1}),
                "maxiso": ("INT", {"default": 4, "min": 1}),
                "isotope_ppm": ("FLOAT", {"default": 5.0, "min": 0.0}),
                "isotope_mzabs": ("FLOAT", {"default": 0.01, "min": 0.0}),
                "cor_eic_th": ("FLOAT", {"default": 0.75, "min": 0.0, "max": 1.0}),
                "pval": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "run_group_corr": ("BOOLEAN", {"default": True}),
                "run_adducts": ("BOOLEAN", {"default": True}),
                "adduct_ppm": ("FLOAT", {"default": 5.0, "min": 0.0}),
                "adduct_mzabs": ("FLOAT", {"default": 0.015, "min": 0.0}),
                "intval": ("STRING", {"default": "maxo", "options": ["maxo", "into", "intb"]}),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("xcms_object")):
            return "Input 'xcms_object' must be a non-empty path-like value"
        for key, default, choices in (
            ("polarity", "positive", ("positive", "negative")),
            ("intval", "maxo", ("maxo", "into", "intb")),
        ):
            validation = validate_choice(inputs.get(key, default), key, choices)
            if validation is not True:
                return validation
        for key, default, minimum, maximum, integer in (
            ("perfwhm", 0.6, 0.0, None, False),
            ("sigma", 6.0, 0.0, None, False),
            ("maxcharge", 3, 1, None, True),
            ("maxiso", 4, 1, None, True),
            ("isotope_ppm", 5.0, 0.0, None, False),
            ("isotope_mzabs", 0.01, 0.0, None, False),
            ("cor_eic_th", 0.75, 0.0, 1.0, False),
            ("pval", 0.05, 0.0, 1.0, False),
            ("adduct_ppm", 5.0, 0.0, None, False),
            ("adduct_mzabs", 0.015, 0.0, None, False),
        ):
            validation = validate_number(
                inputs.get(key, default),
                key,
                minimum=minimum,
                maximum=maximum,
                integer=integer,
            )
            if validation is not True:
                return validation
        return True

    @classmethod
    def output_stem(cls, inputs: dict[str, Any], fallback: str) -> str:
        source_stem = safe_output_stem(inputs.get("xcms_object"), "camera")
        return safe_output_stem(inputs.get("output_name"), source_stem)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        out_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / "camera_annotation.R"
        stem = cls.output_stem(inputs, "camera")
        annotated_peaklist = out_dir / f"{stem}.camera_peaklist.tsv"
        camera_object = out_dir / f"{stem}.camera.rds"
        summary_json = out_dir / f"{stem}.camera.summary.json"
        xcms_object = path_value(inputs["xcms_object"])
        polarity = str(inputs.get("polarity", "positive"))
        intval = str(inputs.get("intval", "maxo"))
        group_corr_step = ""
        if inputs.get("run_group_corr", True):
            group_corr_step = (
                "xsa <- groupCorr("
                f"xsa, cor_eic_th = {inputs.get('cor_eic_th', 0.75)}, "
                f"pval = {inputs.get('pval', 0.05)}, calcIso = TRUE, intval = {r_string(intval)})"
            )
        adduct_step = ""
        if inputs.get("run_adducts", True):
            adduct_step = (
                "xsa <- findAdducts("
                f"xsa, ppm = {inputs.get('adduct_ppm', 5.0)}, "
                f"mzabs = {inputs.get('adduct_mzabs', 0.015)}, "
                f"polarity = {r_string(polarity)}, intval = {r_string(intval)})"
            )

        script = textwrap.dedent(
            f"""\
            suppressPackageStartupMessages({{
                library("CAMERA")
                library("xcms")
                library("jsonlite")
                library("readr")
            }})

            xdata <- readRDS({r_string(xcms_object)})
            if (is(xdata, "xcmsSet")) {{
                xset <- xdata
            }} else if (is(xdata, "XcmsExperiment") || is(xdata, "XCMSnExp")) {{
                xset <- as(xdata, "xcmsSet")
            }} else {{
                stop("CAMERA Annotation requires an xcmsSet, XcmsExperiment, or XCMSnExp RDS object.")
            }}
            xsa <- xsAnnotate(xset, polarity = {r_string(polarity)})
            xsa <- groupFWHM(
                xsa,
                sigma = {inputs.get('sigma', 6.0)},
                perfwhm = {inputs.get('perfwhm', 0.6)},
                intval = {r_string(intval)}
            )
            xsa <- findIsotopes(
                xsa,
                maxcharge = {inputs.get('maxcharge', 3)},
                maxiso = {inputs.get('maxiso', 4)},
                ppm = {inputs.get('isotope_ppm', 5.0)},
                mzabs = {inputs.get('isotope_mzabs', 0.01)},
                intval = {r_string(intval)}
            )
            {group_corr_step}
            {adduct_step}
            peaklist <- as.data.frame(getPeaklist(xsa, intval = {r_string(intval)}))
            write_tsv(peaklist, {r_string(annotated_peaklist.as_posix())})
            saveRDS(xsa, {r_string(camera_object.as_posix())})
            summary <- list(
                input_xcms_object = {r_string(xcms_object)},
                annotated_peaklist = {r_string(annotated_peaklist.as_posix())},
                camera_object = {r_string(camera_object.as_posix())},
                peak_count = nrow(peaklist),
                polarity = {r_string(polarity)},
                intval = {r_string(intval)},
                run_group_corr = {str(bool(inputs.get('run_group_corr', True))).upper()},
                run_adducts = {str(bool(inputs.get('run_adducts', True))).upper()}
            )
            write_json(summary, {r_string(summary_json.as_posix())}, pretty = TRUE, auto_unbox = TRUE)
            """
        )
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]
