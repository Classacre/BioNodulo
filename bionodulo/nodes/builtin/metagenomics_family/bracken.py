"""Bracken 3.1 abundance re-estimation."""

from __future__ import annotations

import re
from typing import Any

from .adapter import MetagenomicsCommandNode, path_value, validate_int


_LEVEL_RE = re.compile(r"^[DPCOFGS](?:[1-9][0-9]*)?$")


class BrackenNode(MetagenomicsCommandNode):
    """Re-estimate abundance from one standard Kraken report."""

    NODE_ID = "bracken"
    DISPLAY_NAME = "Bracken"
    DESCRIPTION = "Estimate taxon abundance from a standard Kraken report and a Bracken-built database."
    SEARCH_ALIASES = ["BioNodulo builtin", "Bracken", "Kraken report", "abundance estimation"]
    RETURN_TYPES = ("TSV", "KRAKEN_REPORT")
    RETURN_NAMES = ("abundance", "report")
    REQUIRED_EXECUTABLES = ["bracken"]
    REQUIRED_CONDA_PACKAGES = ["bracken"]
    VERSION = "3.1"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "bracken=3.1"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/bracken/files?version=3.1"
    GIT_URL = "https://github.com/jenniferlu717/Bracken.git"
    GIT_COMMIT = "cfeac04b6445c44c3825866683a6fdd18746cb58"
    UPSTREAM_TAG = "v3.1"
    UPSTREAM_SOURCE = "bracken; src/est_abundance.py; README.md"
    UPSTREAM_REPORTED_VERSION = "3.0.1"
    DOCUMENTATION_URL = (
        "https://github.com/jenniferlu717/Bracken/blob/cfeac04b6445c44c3825866683a6fdd18746cb58/README.md"
    )
    CITATION_DOIS = ["10.7717/peerj-cs.104"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj-cs.104"]
    CITATION_TEXT = "Bracken: estimating species abundance in metagenomics data."
    OUTPUT_FILENAMES = ("abundance.tsv", "bracken.kreport")
    REQUIRED_PATH_INPUTS = ("report", "db")
    EXIT_SEMANTICS = (
        "The shell wrapper uses set -eu and the estimator exits nonzero for malformed reports; "
        "BioNodulo additionally fails when either native output is missing."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "report": (
                    "KRAKEN_REPORT",
                    {"description": "Standard six-column Kraken report; MPA-style reports are rejected upstream"},
                ),
                "db": (
                    "DIRECTORY",
                    {"description": "Kraken/Bracken database containing database{read_length}mers.kmer_distrib"},
                ),
            },
            "optional": {
                "read_length": ("INT", {"default": 100, "min": 1}),
                "level": (
                    "STRING",
                    {"default": "S", "description": "Taxonomic rank such as D, P, C, O, F, G, S, or S1"},
                ),
                "threshold": ("INT", {"default": 10, "min": 0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default, minimum in (("read_length", 100, 1), ("threshold", 10, 0)):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        level = str(inputs.get("level", "S"))
        if not _LEVEL_RE.fullmatch(level):
            return "Input 'level' must be D, P, C, O, F, G, S, or a numbered sub-rank such as S1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        return cls.checked_command(
            inputs,
            "bracken",
            "-d",
            path_value(inputs.get("db")),
            "-i",
            path_value(inputs.get("report")),
            "-o",
            str(output / cls.OUTPUT_FILENAMES[0]),
            "-w",
            str(output / cls.OUTPUT_FILENAMES[1]),
            "-r",
            str(inputs.get("read_length", 100)),
            "-l",
            str(inputs.get("level", "S")),
            "-t",
            str(inputs.get("threshold", 10)),
        )
