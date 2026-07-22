"""KronaTools 2.8.1 taxonomy visualization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import MetagenomicsCommandNode, path_value, validate_int


class KronaTaxonomyNode(MetagenomicsCommandNode):
    """Render a Kraken-style classification with an explicit Krona taxonomy database."""

    NODE_ID = "krona"
    DISPLAY_NAME = "Krona Taxonomy Chart"
    DESCRIPTION = "Create a standalone interactive Krona taxonomy chart from per-read classifications."
    SEARCH_ALIASES = ["BioNodulo builtin", "Krona", "taxonomy", "sunburst", "Kraken2"]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("krona_html",)
    OUTPUT_NODE = True
    REQUIRED_EXECUTABLES = ["ktImportTaxonomy"]
    REQUIRED_CONDA_PACKAGES = ["krona"]
    VERSION = "2.8.1"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "krona=2.8.1"
    BIOCONDA_PACKAGE_URL = "https://anaconda.org/bioconda/krona/files?version=2.8.1"
    GIT_URL = "https://github.com/marbl/Krona.git"
    GIT_COMMIT = "106dedb36b6c80445c6bacbd53d745a2388de273"
    UPSTREAM_TAG = "v2.8.1"
    UPSTREAM_SOURCE = "KronaTools/scripts/ImportTaxonomy.pl; KronaTools/lib/KronaTools.pm"
    SOURCE_PATHS = ("KronaTools/scripts/ImportTaxonomy.pl", "KronaTools/lib/KronaTools.pm")
    SOURCE_REVISION = GIT_COMMIT
    SOURCE_URL = f"{GIT_URL}/blob/{GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    TAXONOMY_FILES = ("taxonomy.tab",)
    SIDECAR_POLICY = (
        "The materialized taxonomy directory must contain KronaTools' exact taxonomy.tab sibling; "
        "ktImportTaxonomy discovers this file beneath the directory passed with -tax."
    )
    DOCUMENTATION_URL = (
        "https://github.com/marbl/Krona/blob/"
        "106dedb36b6c80445c6bacbd53d745a2388de273/KronaTools/scripts/ImportTaxonomy.pl"
    )
    CITATION_DOIS = ["10.1186/1471-2105-12-385"]
    CITATION_URLS = ["https://doi.org/10.1186/1471-2105-12-385"]
    CITATION_TEXT = "Interactive metagenomic visualization in a Web browser."
    OUTPUT_FILENAMES = ("krona.html",)
    REQUIRED_PATH_INPUTS = ("classification", "taxonomy")
    EXIT_SEMANTICS = (
        "KronaTools terminates on unreadable input or taxonomy data; its no-argument usage path exits zero, "
        "so BioNodulo also requires the planned HTML output."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "classification": (
                    "KRAKEN_OUTPUT",
                    {"description": "Per-read Kraken2 classification: query IDs in column 2 and taxids in column 3"},
                ),
                "taxonomy": (
                    "DIRECTORY",
                    {"description": "Krona taxonomy directory containing taxonomy.tab"},
                ),
            },
            "optional": {
                "query_column": ("INT", {"default": 2, "min": 1}),
                "taxid_column": ("INT", {"default": 3, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default in (("query_column", 2), ("taxid_column", 3)):
            validation = validate_int(inputs.get(key, default), key, minimum=1)
            if validation is not True:
                return validation
        if inputs.get("query_column", 2) == inputs.get("taxid_column", 3):
            return "query_column and taxid_column must identify different columns"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Validate Krona's sibling-discovered taxonomy database after staging."""

        taxonomy = Path(path_value(inputs.get("taxonomy")))
        if not taxonomy.exists():
            return
        if not taxonomy.is_dir():
            raise ValueError(f"Krona taxonomy database must be a directory: {taxonomy}")
        missing = [
            name
            for name in cls.TAXONOMY_FILES
            if not (taxonomy / name).is_file() or (taxonomy / name).stat().st_size == 0
        ]
        if missing:
            raise ValueError(
                "Krona taxonomy database is missing required non-empty sidecar(s): "
                + ", ".join(missing)
            )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        return cls.checked_command(
            inputs,
            "ktImportTaxonomy",
            "-q",
            str(inputs.get("query_column", 2)),
            "-t",
            str(inputs.get("taxid_column", 3)),
            "-tax",
            path_value(inputs.get("taxonomy")),
            "-o",
            str(output / cls.OUTPUT_FILENAMES[0]),
            path_value(inputs.get("classification")),
        )
