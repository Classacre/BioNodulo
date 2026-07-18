"""Shared Bowtie2 2.5.5 metadata and index layout."""

from __future__ import annotations

from typing import ClassVar

from bionodulo.nodes.command_node import CommandNode


BOWTIE2_SMALL_SUFFIXES = (
    ".1.bt2",
    ".2.bt2",
    ".3.bt2",
    ".4.bt2",
    ".rev.1.bt2",
    ".rev.2.bt2",
)
BOWTIE2_LARGE_SUFFIXES = tuple(suffix.replace(".bt2", ".bt2l") for suffix in BOWTIE2_SMALL_SUFFIXES)
BOWTIE2_SUFFIX_FAMILIES = (BOWTIE2_SMALL_SUFFIXES, BOWTIE2_LARGE_SUFFIXES)


class Bowtie2CommandNode(CommandNode):
    """Pinned metadata shared by the documented Bowtie2 operations."""

    CATEGORY = "alignment"
    REQUIRED_CONDA_PACKAGES = ["bowtie2"]
    VERSION = "2.5.5"
    GIT_URL = "https://github.com/BenLangmead/bowtie2.git"
    GIT_COMMIT = "0c6a1c75e047ad8bf70c178fa3cb1528fba6adc2"
    DOCUMENTATION_URL = (
        "https://github.com/BenLangmead/bowtie2/blob/0c6a1c75e047ad8bf70c178fa3cb1528fba6adc2/MANUAL.markdown"
    )
    CITATION_DOIS = ["10.1038/nmeth.1923", "10.1093/bioinformatics/bty648"]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = "Fast gapped-read alignment with Bowtie 2; scaling read aligners to hundreds of threads."
    SHELL = False

    UPSTREAM_TAG: ClassVar[str] = "v2.5.5"
    UPSTREAM_MANUAL: ClassVar[str] = "MANUAL.markdown"
    UPSTREAM_WRAPPER: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""
