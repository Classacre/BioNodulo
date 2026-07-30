"""Build the Bowtie2 index MetaPhlAn requires from a database bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.metagenomics_family.adapter import (
    MetagenomicsCommandNode,
    path_value,
)


class MetaPhlAnBuildIndexNode(MetagenomicsCommandNode):
    """Materialise a MetaPhlAn database's six Bowtie2 ``bt2l`` index members.

    MetaPhlAn's published database bundles ship the marker FASTA and the ``.pkl``
    but NOT the Bowtie2 index; it is normally built on first use by an implicit
    download-and-build step. BioNodulo runs offline by design, and the profiler
    node fails closed when the index is absent, so the build has to be an
    explicit workflow step.
    """

    NODE_ID = "metaphlan_build_index"
    DISPLAY_NAME = "MetaPhlAn Build Index"
    DESCRIPTION = "Build the six Bowtie2 bt2l index members MetaPhlAn needs from its marker FASTA."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "MetaPhlAn",
        "bowtie2",
        "build index",
        "bt2l",
        "metagenomics",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("database",)
    #: Mirrors MetaPhlAnNode.DATABASE_INDEX_SUFFIXES; a divergence here would let
    #: this node "succeed" while the profiler still rejects the database.
    INDEX_SUFFIXES = (".1.bt2l", ".2.bt2l", ".3.bt2l", ".4.bt2l", ".rev.1.bt2l", ".rev.2.bt2l")
    OUTPUT_FILENAMES = ()
    # bzip2 is declared explicitly: the marker FASTA ships bzip2-compressed and
    # the worker image is minimal, so relying on a host bunzip2 works on a dev
    # box and fails in the cloud -- which is exactly how this first surfaced.
    REQUIRED_EXECUTABLES = ["bowtie2-build", "bunzip2"]
    REQUIRED_CONDA_PACKAGES = ["bowtie2", "bzip2"]
    CONDA_PACKAGE_CONSTRAINTS = {"bowtie2": "2.5.*"}
    VERSION = "2.5"
    GIT_URL = "https://github.com/BenLangmead/bowtie2.git"
    DOCUMENTATION_URL = "https://github.com/biobakery/MetaPhlAn/wiki/MetaPhlAn-4#customizing-the-database"
    UPSTREAM_SOURCE = "bowtie2-build; metaphlan/utils/database_controller.py"
    REQUIRED_PATH_INPUTS = ("database",)
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    SHELL = True
    EXIT_SEMANTICS = (
        "bowtie2-build exits non-zero on an unreadable or empty FASTA; the six bt2l members "
        "are written beside the marker FASTA under the database directory."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "database": (
                    "DIRECTORY",
                    {"description": "MetaPhlAn database directory containing <index>_SGB.fna(.bz2) and <index>.pkl"},
                ),
                "index": ("STRING", {"description": "Database index name, e.g. mpa_vJan21_TOY_CHOCOPhlAnSGB_202103"}),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        # The index must sit BESIDE the database's own files, because MetaPhlAn
        # discovers it by name under the directory it is handed. Returning that
        # same directory keeps the profiler's `database` input satisfied.
        node_dir = Path(output_dir) / cls.NODE_ID / "database"
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir]

    # NOTE: the runner passes the node directory as `output`, so render_command
    # derives <output>/database -- the same location PLAN_OUTPUTS returns when
    # given the run root. Keeping both in one helper avoids them drifting.

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        target = cls.output_dir(inputs) / "database"
        source = Path(path_value(inputs["database"]))
        index = str(inputs["index"]).strip()
        threads = int(inputs.get("threads", 4))
        # bunzip2 -k: the bundle ships the marker FASTA bzip2-compressed and
        # bowtie2-build needs it expanded, but MetaPhlAn still wants the original
        # alongside. --large-index forces the bt2l members the profiler requires
        # regardless of how small the toy database is.
        return (
            f'set -e; mkdir -p "{target}"; cp -f "{source}"/* "{target}"/; '
            f'cd "{target}"; '
            f'if [ -f "{index}_SGB.fna.bz2" ] && [ ! -f "{index}_SGB.fna" ]; then '
            f'bunzip2 -k "{index}_SGB.fna.bz2"; fi; '
            f'bowtie2-build --large-index --threads {threads} "{index}_SGB.fna" "{index}"'
        )

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Require all six members, so a partial index cannot pass downstream."""
        if not outputs:
            return
        index = str(inputs.get("index", "")).strip()
        missing = [
            f"{index}{suffix}"
            for suffix in cls.INDEX_SUFFIXES
            if not (outputs[0] / f"{index}{suffix}").is_file()
        ]
        if missing:
            raise ValueError(
                "MetaPhlAn index build did not produce: " + ", ".join(missing)
            )
