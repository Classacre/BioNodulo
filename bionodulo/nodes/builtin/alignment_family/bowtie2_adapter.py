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
BOWTIE2_VERSION = "2.5.5"
BOWTIE2_GIT_URL = "https://github.com/BenLangmead/bowtie2.git"
BOWTIE2_GIT_COMMIT = "0c6a1c75e047ad8bf70c178fa3cb1528fba6adc2"
BOWTIE2_SOURCE_ROOT = f"https://github.com/BenLangmead/bowtie2/blob/{BOWTIE2_GIT_COMMIT}"
BOWTIE2_PACKAGE_CONSTRAINT = f"bowtie2=={BOWTIE2_VERSION}"


def bowtie2_source_urls(*paths: str) -> tuple[str, ...]:
    return tuple(f"{BOWTIE2_SOURCE_ROOT}/{path}" for path in paths)


class Bowtie2CommandNode(CommandNode):
    """Pinned metadata shared by the documented Bowtie2 operations."""

    CATEGORY = "alignment"
    REQUIRED_CONDA_PACKAGES = ["bowtie2"]
    VERSION = BOWTIE2_VERSION
    GIT_URL = BOWTIE2_GIT_URL
    GIT_COMMIT = BOWTIE2_GIT_COMMIT
    DOCUMENTATION_URL = (
        "https://github.com/BenLangmead/bowtie2/blob/0c6a1c75e047ad8bf70c178fa3cb1528fba6adc2/MANUAL.markdown"
    )
    CITATION_DOIS = ["10.1038/nmeth.1923", "10.1093/bioinformatics/bty648"]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = "Fast gapped-read alignment with Bowtie 2; scaling read aligners to hundreds of threads."
    CONDA_PACKAGE_CONSTRAINTS = {"bowtie2": BOWTIE2_VERSION}
    PACKAGE_CONSTRAINTS = (BOWTIE2_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    GIT_TAG = "v2.5.5"
    SOURCE_REF = f"tag v2.5.5 at {BOWTIE2_GIT_COMMIT}"
    SOURCE_REVISION = BOWTIE2_GIT_COMMIT
    SOURCE_URL = f"https://github.com/BenLangmead/bowtie2/tree/{BOWTIE2_GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "Bowtie 2 wrappers and binaries return non-zero for malformed arguments, "
        "missing inputs, incomplete index bundles, or alignment/build failures; "
        "BioNodulo validates every planned index and output artifact after exit 0."
    )
    SHELL = False

    UPSTREAM_TAG: ClassVar[str] = "v2.5.5"
    UPSTREAM_MANUAL: ClassVar[str] = "MANUAL.markdown"
    UPSTREAM_WRAPPER: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""
