"""Shared runtime contract for the csvtk 0.31.0 tabular operation nodes.

csvtk is a cross-platform CSV/TSV toolkit. Generated operations name an output
file explicitly. Hand-written stdout operations inherit ``CsvtkStdoutNode``;
their ``OUTPUT_FILENAMES`` names the captured stream.

The delimiter is deliberately exposed as an input rather than inferred from the
filename: ``delimiter="tab"`` renders ``-t`` (tab input) and ``-T`` (tab output),
``delimiter="comma"`` renders neither and therefore uses csvtk's default comma
in/out. This was verified against the pinned image, not assumed.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


CSVTK_VERSION = "0.31.0"
CSVTK_GIT_URL = "https://github.com/shenwei356/csvtk.git"
CSVTK_GIT_TAG = "v0.31.0"
CSVTK_GIT_COMMIT = "4818152b6fb38954203ec1a570836949dea84091"
CSVTK_DOCUMENTATION_URL = "https://bioinf.shenwei.me/csvtk/usage/"
CSVTK_PACKAGE_CONSTRAINT = f"csvtk=={CSVTK_VERSION}"
CSVTK_CITATION_URLS = ["https://github.com/shenwei356/csvtk"]
CSVTK_CITATION_TEXT = (
    "csvtk: a cross-platform, efficient and practical CSV/TSV toolkit (Wei Shen). "
    "The project publishes no peer-reviewed paper or DOI."
)

# ``delimiter`` input value -> global csvtk flags. ``-t`` selects tab input and,
# in the pinned release, tab output as well; ``-T`` is passed to make the output
# delimiter explicit rather than incidental.
DELIMITER_MODES = ("tab", "comma")
DELIMITER_FLAGS: dict[str, tuple[str, ...]] = {
    "tab": ("-t", "-T"),
    "comma": (),
}

# csvtk 0.31.0 ``summary`` operations, copied from the pinned binary's
# ``csvtk summary --help`` output.
SUMMARY_OPERATIONS = (
    "argmax",
    "argmin",
    "collapse",
    "count",
    "countn",
    "countuniq",
    "countunique",
    "entropy",
    "first",
    "last",
    "max",
    "mean",
    "median",
    "min",
    "prod",
    "q1",
    "q2",
    "q3",
    "rand",
    "stdev",
    "sum",
    "uniq",
    "unique",
    "variance",
)

# EDAM labels below were read from the pinned EDAM release
# (reports/biotools_registry/ontology-and-snapshot-pins.json,
# release 1.25-20260626T1230Z, EDAM.csv sha256 cac8ca5d...), never from memory.
CSVTK_TOPIC_DATA_ARCHITECTURE = {
    "uri": "http://edamontology.org/topic_3365",
    "label": "Data architecture, analysis and design",
}
CSVTK_OPERATION_STATISTICAL_CALCULATION = {
    "uri": "http://edamontology.org/operation_2238",
    "label": "Statistical calculation",
}
CSVTK_OPERATION_FEATURE_SELECTION = {
    "uri": "http://edamontology.org/operation_3936",
    "label": "Feature selection",
}

# csvtk has no bio.tools accession: a case-insensitive search of the pinned
# registry snapshot (reports/biotools_registry/current/registry.jsonl) returns
# nothing, and the live bio.tools API reports zero results for "csvtk". The
# schema makes ``tool_id`` optional, so it is omitted rather than invented.
CSVTK_KNOWLEDGE: dict[str, Any] = {
    "schema_version": 1,
    "topics": [CSVTK_TOPIC_DATA_ARCHITECTURE],
    "reviewed_at": "2026-09-25",
}


class CsvtkBase(CommandNode):
    """Pinned metadata and validation shared by the csvtk operation nodes."""

    # Group operations by tool, matching the samtools and emboss families,
    # so this suite remains easy to find as the catalog grows.
    CATEGORY = "csvtk"
    REQUIRED_EXECUTABLES = ["csvtk"]
    REQUIRED_CONDA_PACKAGES = ["csvtk"]
    CONDA_PACKAGE_CONSTRAINTS = {"csvtk": f"=={CSVTK_VERSION}"}
    PACKAGE_CONSTRAINTS = (CSVTK_PACKAGE_CONSTRAINT,)
    PACKAGE_CONSTRAINT = CSVTK_PACKAGE_CONSTRAINT
    VERSION = CSVTK_VERSION
    GIT_URL = CSVTK_GIT_URL
    GIT_TAG = CSVTK_GIT_TAG
    GIT_COMMIT = CSVTK_GIT_COMMIT
    RUNTIME_VERSION = CSVTK_VERSION
    RUNTIME_GIT_URL = CSVTK_GIT_URL
    RUNTIME_GIT_COMMIT = CSVTK_GIT_COMMIT
    DOCUMENTATION_URL = CSVTK_DOCUMENTATION_URL
    CITATION_DOIS: ClassVar[list[str]] = []
    CITATION_URLS = list(CSVTK_CITATION_URLS)
    CITATION_TEXT = CSVTK_CITATION_TEXT
    KNOWLEDGE = dict(CSVTK_KNOWLEDGE)
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ("table",)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in cls.REQUIRED_PATH_INPUTS:
            validation = cls.require_path(inputs, key)
            if validation is not True:
                return validation
        mode = inputs.get("delimiter", "tab")
        if mode in (None, ""):
            mode = "tab"
        return cls.validate_choice(mode, DELIMITER_MODES, "delimiter")

    @staticmethod
    def path_value(value: Any) -> str:
        try:
            result = os.fsdecode(os.fspath(value))
        except TypeError:
            return ""
        return result if result.strip() else ""

    @classmethod
    def require_path(cls, inputs: Mapping[str, Any], key: str) -> bool | str:
        path = cls.path_value(inputs.get(key))
        if not path:
            return f"Input '{key}' must be a non-empty path-like value"
        if path == "-":
            return f"Input '{key}' must be a file path; this node has no stdin port"
        return True

    @classmethod
    def delimiter_flags(cls, inputs: Mapping[str, Any]) -> list[str]:
        mode = inputs.get("delimiter", "tab") or "tab"
        if mode not in DELIMITER_FLAGS:
            raise ValueError(f"Unsupported delimiter: {mode}")
        return list(DELIMITER_FLAGS[mode])

    @staticmethod
    def validate_choice(value: Any, choices: Sequence[str], key: str) -> bool | str:
        allowed = tuple(choices)
        if str(value) not in allowed:
            return f"Input '{key}' must be one of: {', '.join(allowed)}"
        return True

    @staticmethod
    def validate_int(
        value: Any,
        key: str,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> bool | str:
        if isinstance(value, bool) or not isinstance(value, int):
            return f"Input '{key}' must be an integer"
        if minimum is not None and value < minimum:
            return f"Input '{key}' must be at least {minimum}"
        if maximum is not None and value > maximum:
            return f"Input '{key}' must be at most {maximum}"
        return True

    @staticmethod
    def split_fields(value: Any) -> list[str]:
        if value is None:
            return []
        items = [str(item) for item in value] if isinstance(value, (list, tuple)) else [str(value)]
        return [part.strip() for item in items for part in item.split(",") if part.strip()]


class CsvtkStdoutNode(CsvtkBase):
    """csvtk operation whose declared primary artifact is written to stdout."""

    STDOUT_OUTPUT_INDEX = 0
