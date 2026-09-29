"""Shared runtime contract for the vcflib operation nodes.

vcflib is unusual among the families here: it is not one binary with subcommands
but ~121 separate executables in a single package, each with its own interface
(``vcfcheck``, ``vcf2tsv``, ``vcffilter``, ``vcfwave``, ...). The nodes are
generated from each executable's own ``--help`` output by
``scripts/generate_vcflib_nodes.py``, which reuses the node emitter in
``generate_subcommand_nodes.py``.

The upstream help output comes in several dialects, and each one is a declaration
of a different quality:

- ``options:`` tables (26 tools) give short name, long name and metavar.
- ``INFO: required: t,target -- ...`` blocks (14 tools) additionally mark which
  flags are required, so no empirical probe is needed.
- ``Params:`` blocks with ``<TYPE>`` metavars (2 tools).
- 46 tools declare no flags at all. They are positional-only or use a ``Params:``
  block that does not survive being printed by ``--help``. Those nodes declare the
  data ports and write to stdout, and nothing more, which is the honest limit of
  what their own documentation supports.

Almost every vcflib tool writes VCF to stdout rather than to a named file, so the
nodes use ``STDOUT_OUTPUT_INDEX`` and let the executor capture stdout into the
planned output.

Citation verified against Crossref on 2026-09-28: the vcflib software paper in
PLOS Computational Biology (2022).

Known runtime defect in the pinned build, measured 2026-09-28: ``vcfinfosummarize``
segfaults (exit 139) on every valid invocation, including ``-f DP -i SUMM file.vcf``
and with ``-a``/``-m``. ``vcfinfosummarize --help`` exits 0, so the crash is in the
tool, not in how the node calls it. The node is kept because its contract matches the
documented interface, but a run of it will fail. 26 of the 27 vcflib tools smoke-run
in this family exit 0; this is the exception.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode

VCFLIB_VERSION = "1.0.15"
VCFLIB_DOCUMENTATION_URL = "https://github.com/vcflib/vcflib"
VCFLIB_CITATION_DOIS = ["10.1371/journal.pcbi.1009123"]
VCFLIB_CITATION_URLS = [f"https://doi.org/{doi}" for doi in VCFLIB_CITATION_DOIS]
VCFLIB_CITATION_TEXT = (
    "A spectrum of free software tools for processing the VCF variant call format: "
    "vcflib, bio-vcf, cyvcf2, hts-nim and slivar."
)
VCFLIB_KNOWLEDGE = {
    "schema_version": 1,
    "tool_id": "https://bio.tools/vcflib",
    "topics": [
        {"uri": "http://edamontology.org/topic_0199", "label": "Genetic variation"},
        {"uri": "http://edamontology.org/topic_2533", "label": "DNA mutation"},
    ],
    "citation_evidence": [
        {
            "identifier": VCFLIB_CITATION_DOIS[0],
            "source_url": "https://api.crossref.org/works/10.1371/journal.pcbi.1009123",
            "checked_at": "2026-09-28",
            "note": (
                "Crossref returns 'A spectrum of free software tools for processing "
                "the VCF variant call format: vcflib, bio-vcf, cyvcf2, hts-nim and "
                "slivar', PLOS Computational Biology 2022. This is the software paper "
                "covering vcflib, not a version-specific DOI for the pinned 1.0.15 "
                "runtime."
            ),
        }
    ],
    "reviewed_at": "2026-09-28",
}


class VcflibBase(CommandNode):
    """Pinned metadata shared by the vcflib operation nodes."""

    CATEGORY = "vcflib"
    # There is no binary called `vcflib`; the package installs ~121 executables and
    # each generated node declares its own (vcfcheck, vcf2tsv, ...). Left empty here
    # rather than filled with a name that does not resolve.
    REQUIRED_EXECUTABLES: ClassVar[list[str]] = []
    REQUIRED_CONDA_PACKAGES = ["vcflib"]
    CONDA_PACKAGE_CONSTRAINTS = {"vcflib": f"=={VCFLIB_VERSION}"}
    VERSION = VCFLIB_VERSION
    DOCUMENTATION_URL = VCFLIB_DOCUMENTATION_URL
    CITATION_DOIS = VCFLIB_CITATION_DOIS
    CITATION_URLS = VCFLIB_CITATION_URLS
    CITATION_TEXT = VCFLIB_CITATION_TEXT
    KNOWLEDGE = dict(VCFLIB_KNOWLEDGE)
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        if not cls.OUTPUT_FILENAMES:
            return [node_out]
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]
