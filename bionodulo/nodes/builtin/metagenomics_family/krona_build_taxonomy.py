"""Build a Krona taxonomy database from the NCBI taxdump."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import MetagenomicsCommandNode, path_value


class KronaBuildTaxonomyNode(MetagenomicsCommandNode):
    """Extract KronaTools' taxonomy.tab from an NCBI taxdump archive.

    Krona needs a `taxonomy.tab` that nobody publishes as a downloadable
    artifact: upstream ships `updateTaxonomy.sh`, which fetches NCBI's taxdump
    and runs `extractTaxonomy.pl` over it. Without a node for that step, every
    Krona workflow depends on a file the user has to build by hand.

    The extractor ships inside the same `krona` conda package as
    `ktImportTaxonomy`, so this adds no new dependency.
    """

    NODE_ID = "krona_build_taxonomy"
    DISPLAY_NAME = "Krona Build Taxonomy"
    DESCRIPTION = "Build KronaTools' taxonomy.tab database from an NCBI taxdump archive."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "Krona",
        "taxonomy",
        "taxdump",
        "build database",
        "extractTaxonomy",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("taxonomy",)
    OUTPUT_FILENAMES = ("taxonomy.tab",)
    REQUIRED_EXECUTABLES = ["perl"]
    REQUIRED_CONDA_PACKAGES = ["krona"]
    VERSION = "2.8.1"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "krona=2.8.1"
    GIT_URL = "https://github.com/marbl/Krona.git"
    GIT_COMMIT = "106dedb36b6c80445c6bacbd53d745a2388de273"
    UPSTREAM_TAG = "v2.8.1"
    UPSTREAM_SOURCE = "KronaTools/scripts/extractTaxonomy.pl; KronaTools/scripts/taxonomy.make"
    DOCUMENTATION_URL = (
        "https://github.com/marbl/Krona/blob/"
        "106dedb36b6c80445c6bacbd53d745a2388de273/KronaTools/updateTaxonomy.sh"
    )
    SOURCE_URL = (
        "https://github.com/marbl/Krona/blob/"
        "106dedb36b6c80445c6bacbd53d745a2388de273/KronaTools/scripts/extractTaxonomy.pl"
    )
    CITATION_DOIS = ["10.1186/1471-2105-12-385"]
    CITATION_URLS = ["https://doi.org/10.1186/1471-2105-12-385"]
    CITATION_TEXT = "Interactive metagenomic visualization in a Web browser."
    REQUIRED_PATH_INPUTS = ("taxdump",)
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    SHELL = True
    EXIT_SEMANTICS = (
        "extractTaxonomy.pl exits non-zero when names.dmp/nodes.dmp are absent or malformed; "
        "taxonomy.tab is written into the directory it is pointed at."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "taxdump": (
                    ("DIRECTORY", "FILE"),
                    {
                        "description": (
                            "NCBI taxdump: either the extracted directory containing "
                            "names.dmp/nodes.dmp, or the taxdump.tar.gz archive"
                        )
                    },
                )
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID / "taxonomy"
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / cls.OUTPUT_FILENAMES[0]]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        # PLAN_OUTPUTS places taxonomy.tab under <node dir>/taxonomy, and the
        # runner passes that node directory as `output`.
        taxonomy_dir = cls.output_dir(inputs) / "taxonomy"
        source = Path(path_value(inputs["taxdump"]))
        # The extractor reads names.dmp/nodes.dmp from the directory it is given,
        # so an archive input is unpacked next to where taxonomy.tab will land.
        # `tar -m` matches upstream's taxonomy.make and avoids clock-skew warnings.
        return (
            f'set -e; mkdir -p "{taxonomy_dir}"; '
            f'if [ -d "{source}" ]; then cp -f "{source}"/*.dmp "{taxonomy_dir}"/; '
            f'else tar -xmf "{source}" -C "{taxonomy_dir}"; fi; '
            f'perl "$(dirname "$(command -v ktImportTaxonomy)")"/../opt/krona/scripts/extractTaxonomy.pl '
            f'"{taxonomy_dir}"'
        )

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """A truncated taxonomy silently produces an empty chart, so check size."""
        if outputs and outputs[0].exists() and outputs[0].stat().st_size == 0:
            raise ValueError("Krona taxonomy.tab was written empty; the taxdump is incomplete")
