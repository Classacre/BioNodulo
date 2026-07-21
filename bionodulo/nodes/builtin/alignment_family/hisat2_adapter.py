"""Shared HISAT2 2.2.2 metadata and index layout."""

from __future__ import annotations

from typing import ClassVar

from bionodulo.nodes.command_node import CommandNode


HISAT2_SMALL_SUFFIXES = tuple(f".{number}.ht2" for number in range(1, 9))
HISAT2_LARGE_SUFFIXES = tuple(suffix.replace(".ht2", ".ht2l") for suffix in HISAT2_SMALL_SUFFIXES)
HISAT2_SUFFIX_FAMILIES = (HISAT2_SMALL_SUFFIXES, HISAT2_LARGE_SUFFIXES)
HISAT2_VERSION = "2.2.2"
HISAT2_GIT_URL = "https://github.com/DaehwanKimLab/hisat2.git"
HISAT2_GIT_COMMIT = "99583d7536b9ee017ac07de8834017a3bf99a2fe"
HISAT2_SOURCE_ROOT = f"https://github.com/DaehwanKimLab/hisat2/blob/{HISAT2_GIT_COMMIT}"
HISAT2_PACKAGE_CONSTRAINT = f"hisat2=={HISAT2_VERSION}"


def hisat2_source_urls(*paths: str) -> tuple[str, ...]:
    return tuple(f"{HISAT2_SOURCE_ROOT}/{path}" for path in paths)


class HISAT2CommandNode(CommandNode):
    """Pinned metadata shared by the documented HISAT2 operations."""

    CATEGORY = "alignment"
    REQUIRED_CONDA_PACKAGES = ["hisat2"]
    VERSION = HISAT2_VERSION
    GIT_URL = HISAT2_GIT_URL
    GIT_COMMIT = HISAT2_GIT_COMMIT
    DOCUMENTATION_URL = (
        "https://github.com/DaehwanKimLab/hisat2/blob/99583d7536b9ee017ac07de8834017a3bf99a2fe/docs/_pages/manual.md"
    )
    CITATION_DOIS = ["10.1038/nmeth.3317", "10.1038/s41587-019-0201-4"]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    CITATION_TEXT = "Hierarchical graph FM-index alignment for spliced sequencing reads."
    CONDA_PACKAGE_CONSTRAINTS = {"hisat2": HISAT2_VERSION}
    PACKAGE_CONSTRAINTS = (HISAT2_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    GIT_TAG = "v2.2.2"
    SOURCE_REF = f"tag v2.2.2 at {HISAT2_GIT_COMMIT}"
    SOURCE_REVISION = HISAT2_GIT_COMMIT
    SOURCE_URL = f"https://github.com/DaehwanKimLab/hisat2/tree/{HISAT2_GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "HISAT2 wrappers and binaries return non-zero for malformed arguments, "
        "missing inputs, incomplete index bundles, or alignment/build failures; "
        "BioNodulo validates every planned index and output artifact after exit 0."
    )
    SHELL = False

    UPSTREAM_TAG: ClassVar[str] = "v2.2.2"
    UPSTREAM_MANUAL: ClassVar[str] = "docs/_pages/manual.md"
    UPSTREAM_WRAPPER: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""
