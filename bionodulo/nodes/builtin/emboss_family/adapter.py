"""Shared runtime contract for the EMBOSS sequence-tool nodes.

EMBOSS (the European Molecular Biology Open Software Suite) ships a large set
of single-purpose command-line programs.  Each program is a separate executable
(``transeq``, ``revseq``, ``pepstats``, ...) and, in bio.tools, a separate
record, so unlike a single-binary suite the base class carries only the suite
identity: the conda package, the source repository, the suite citation, and the
EMBOSS-wide EDAM topic.  Every operation node supplies its own executable,
documentation page, and ``tool_id``/EDAM annotations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


EMBOSS_VERSION = "6.6.0"
EMBOSS_PACKAGE_CONSTRAINT = f"emboss=={EMBOSS_VERSION}"
EMBOSS_GIT_URL = "https://github.com/kimrutherford/EMBOSS"
EMBOSS_CITATION_DOIS = ["10.1016/S0168-9525(00)02024-2"]
EMBOSS_CITATION_URLS = [f"https://doi.org/{doi}" for doi in EMBOSS_CITATION_DOIS]
EMBOSS_CITATION_TEXT = "EMBOSS: The European Molecular Biology Open Software Suite."
EMBOSS_EDAM_TOPIC_SEQUENCE_ANALYSIS = {
    "uri": "http://edamontology.org/topic_0080",
    "label": "Sequence analysis",
}


class EmbossBase(CommandNode):
    """Common source and environment identity for focused EMBOSS operations."""

    CATEGORY = "emboss"
    # The suite-wide marker binary.  Each operation node overrides this with the
    # program it actually invokes; ``embossversion`` is guaranteed present in any
    # EMBOSS installation and identifies the suite.
    REQUIRED_EXECUTABLES = ["embossversion"]
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    CONDA_PACKAGE_CONSTRAINTS = {"emboss": EMBOSS_VERSION}
    PACKAGE_CONSTRAINTS = (EMBOSS_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = EMBOSS_PACKAGE_CONSTRAINT
    VERSION = EMBOSS_VERSION
    GIT_URL = EMBOSS_GIT_URL
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/"
    CITATION_DOIS = EMBOSS_CITATION_DOIS
    CITATION_URLS = EMBOSS_CITATION_URLS
    CITATION_TEXT = EMBOSS_CITATION_TEXT
    KNOWLEDGE: ClassVar[dict[str, Any]] = {
        "schema_version": 1,
        "tool_id": "https://bio.tools/emboss",
        "topics": [EMBOSS_EDAM_TOPIC_SEQUENCE_ANALYSIS],
        "citation_evidence": [
            {
                "identifier": EMBOSS_CITATION_DOIS[0],
                "source_url": "https://bio.tools/emboss",
                "checked_at": "2026-09-25",
                "note": (
                    "The bio.tools 'emboss' record lists this Trends in Genetics 2000 "
                    "paper as the suite citation. It is the software paper for EMBOSS as "
                    "a whole, not a version-specific DOI for the pinned 6.6.0 release."
                ),
            }
        ],
        "reviewed_at": "2026-09-25",
    }
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    # EMBOSS qualifiers are single-dash; the primary data input is always
    # ``-sequence`` and the primary file output is ``-outseq`` (or stdout).
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ("sequence",)
    UPSTREAM_MANPAGE: ClassVar[str] = ""
    UPSTREAM_SOURCE: ClassVar[str] = ""

    @classmethod
    def output_dir(cls, inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output", inputs.get("output_dir", "."))))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_types = cls.INPUT_TYPES()
        normalized_inputs = dict(inputs)
        for name in input_types.get("optional", {}):
            if normalized_inputs.get(name) == "":
                normalized_inputs.pop(name)
        base_validation = super().VALIDATE_INPUTS(normalized_inputs)
        if base_validation is not True:
            return base_validation

        # Fail closed on missing or empty required path inputs.  EMBOSS writes
        # its report to stdout when ``-outseq`` is omitted, so a blank sequence
        # path would otherwise be interpreted as an empty argument and produce a
        # confusing "cannot open ''" error deep inside the tool.
        for name in cls.REQUIRED_PATH_INPUTS:
            value = inputs.get(name)
            if value is None:
                return f"Required input '{name}' is missing"
            try:
                path_value = os.fsdecode(os.fspath(value))
            except TypeError:
                return f"Input '{name}' must be a non-empty path-like value"
            if not path_value.strip():
                return f"Input '{name}' must be a non-empty path-like value"

        for category in ("required", "optional"):
            for name, spec in input_types.get(category, {}).items():
                declared_type = spec[0] if isinstance(spec, (list, tuple)) else spec
                metadata = spec[1] if isinstance(spec, tuple) and len(spec) > 1 else {}
                value = inputs.get(name)
                if value in (None, ""):
                    continue
                if declared_type == "INT":
                    if isinstance(value, bool) or not isinstance(value, int):
                        return f"{name} must be an integer"
                    minimum = metadata.get("min")
                    maximum = metadata.get("max")
                    if minimum is not None and value < minimum:
                        return f"{name} must be at least {minimum}"
                    if maximum is not None and value > maximum:
                        return f"{name} must be at most {maximum}"
                options = metadata.get("options")
                if options and declared_type == "STRING" and value not in options:
                    return f"{name} must be one of: {', '.join(map(str, options))}"
        return True

    @classmethod
    def outseq_path(cls, inputs: dict[str, Any]) -> Path:
        """Resolve the ``-outseq`` target from the node's planned output name."""
        if not cls.OUTPUT_FILENAMES:
            raise ValueError(f"{cls.NODE_ID} declares no OUTPUT_FILENAMES for -outseq")
        return cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]
