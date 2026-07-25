"""Shared source-pinned CNVkit 0.9.12 contracts."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index
from bionodulo.nodes.command_node import CommandNode


CNVKIT_GIT_URL = "https://github.com/etal/cnvkit.git"
CNVKIT_GIT_COMMIT = "dd834b0b5b482f174d1dcb7c35b358087309c6b3"
CNVKIT_COMMIT = CNVKIT_GIT_COMMIT
CNVKIT_GIT_TAG = "v0.9.12"
CNVKIT_COMMANDS_SHA256 = "5d5820ad6a376f1184de626c240a72589bc06f9ad5c9f53092364c5374b4730b"
CNVKIT_SOURCE_SHA256 = {
    "cnvlib/commands.py": CNVKIT_COMMANDS_SHA256,
    "cnvlib/access.py": "a88028ca7ddb62ccd3de169526c1bfcc28a150c6f30fd2e246b4185b543baa0e",
    "cnvlib/antitarget.py": "cbffc36ae086de735fbc60b2f85915bbcf189cd3a31ffd807f5c669bc0a693db",
    "cnvlib/batch.py": "b7870bc1971026db8e3ed68ceed5d318e681478d3da06bfc7acff391838ee20c",
    "cnvlib/call.py": "c40347eaab591c41c54faeb39a145c8a45bd44fbc52da92e3cfd55c5b710dcc0",
    "cnvlib/coverage.py": "274c522be2077e380c1932d00ae7a0a876d98d817a5820d20ee5a9cc654c4b51",
    "cnvlib/heatmap.py": "9520c59d265fd2f3f2fc88b11a0c589259218ca199faeb1c69a7a9bfb41ca6a7",
    "cnvlib/scatter.py": "37d63cc6c3893caf5b5dfb6d37e92d4a623b6a5bde671bb3f40e4fc81fd478c8",
    "cnvlib/samutil.py": "a6c2caf338ea0f1a09556922204e6f3c9d91ab87dfe84c37582bcc91fa71558d",
    "cnvlib/target.py": "e4f5aa187e9407b3dfbd1263869490847455b7e7d5774e8ba90975d27c7d6b05",
    "doc/calling.rst": "71e38e89b58738aa23f413778d0fcf8729ee08f09a74994fab3c383d7ba55296",
    "doc/pipeline.rst": "d2e7a204e5d42c872f4161e0d7ed174cc376bf153af0214bf9e3a9e6c100fb60",
    "doc/plots.rst": "0e57bdebe1b3128275513883c095df16b5e3e3d6da296a8090cd4135a2dfcb68",
}
CNVKIT_CITATION_DOI = "10.1371/journal.pcbi.1004873"


def output_path(inputs: dict[str, Any], filename: str) -> str:
    output_dir = inputs.get("output", inputs.get("output_dir", "."))
    return str(Path(str(output_dir)) / filename)


def plan_output(node_id: str, output_dir: str | Path, filename: str) -> list[Path]:
    node_dir = Path(output_dir) / node_id
    node_dir.mkdir(parents=True, exist_ok=True)
    return [node_dir / filename]


def optional_positive_int(inputs: dict[str, Any], field: str) -> bool | str:
    value = inputs.get(field)
    if value is None or str(value).strip() == "":
        return True
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return f"{field} must be an integer"
    if parsed < 1:
        return f"{field} must be at least 1"
    return True


def path_list(value: Any) -> list[str] | None:
    if isinstance(value, (str, os.PathLike)):
        values = (value,)
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return None

    result: list[str] = []
    for item in values:
        try:
            path = os.fsdecode(os.fspath(item))
        except TypeError:
            return None
        if not path.strip():
            return None
        result.append(path)
    return result


def optional_path(value: Any) -> str | None:
    if value in (None, ""):
        return ""
    values = path_list(value)
    if values is None or len(values) != 1:
        return None
    return values[0]


def sample_id(path: str) -> str:
    name = Path(path).name
    for suffix in (".deduplicated.realign.bam", ".recal.bam"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name.rsplit(".", 1)[0] if "." in name else name


def validate_bam_index_list(
    bams: list[str],
    indexes_value: Any,
    *,
    bam_key: str,
    index_key: str,
) -> bool | str:
    indexes = path_list(indexes_value)
    if not indexes:
        return f"{index_key} must contain one index for each {bam_key} entry"
    if len(indexes) != len(bams):
        return f"{index_key} must contain exactly {len(bams)} path(s)"
    for bam, index in zip(bams, indexes, strict=True):
        validation = validate_colocated_bam_index(
            {bam_key: bam, index_key: index},
            bam_key=bam_key,
            index_key=index_key,
        )
        if validation is not True:
            return validation
    return True


def validate_optional_number(
    value: Any,
    *,
    key: str,
    minimum: float | None = None,
    maximum: float | None = None,
    exclusive_minimum: bool = False,
) -> bool | str:
    if value in (None, ""):
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"{key} must be a number"
    numeric = float(value)
    if not math.isfinite(numeric):
        return f"{key} must be finite"
    if minimum is not None:
        if exclusive_minimum and numeric <= minimum:
            return f"{key} must be greater than {minimum:g}"
        if not exclusive_minimum and numeric < minimum:
            return f"{key} must be at least {minimum:g}"
    if maximum is not None and numeric > maximum:
        return f"{key} must be at most {maximum:g}"
    return True


class CNVkitCommandNode(CommandNode):
    """Pinned authority and fixed-output helpers shared by six CNVkit nodes."""

    CATEGORY = "variant"
    REQUIRED_CONDA_PACKAGES = ["cnvkit"]
    REQUIRED_EXECUTABLES = ["cnvkit.py"]
    REQUIRES_EXTERNAL_TOOLS = True
    VERSION = "0.9.12"
    GIT_URL = CNVKIT_GIT_URL
    GIT_COMMIT = CNVKIT_GIT_COMMIT
    GIT_TAG = CNVKIT_GIT_TAG
    SOURCE_URL = f"https://github.com/etal/cnvkit/tree/{CNVKIT_GIT_COMMIT}"
    PINNED_SOURCE_URL = SOURCE_URL
    SOURCE_REF = CNVKIT_GIT_COMMIT
    SOURCE_PATHS = ("cnvlib/commands.py",)
    SOURCE_SHA256 = CNVKIT_COMMANDS_SHA256
    SOURCE_FILE_SHA256 = CNVKIT_SOURCE_SHA256
    PACKAGE_AUTHORITY = "Bioconda cnvkit 0.9.12"
    PACKAGE_CONSTRAINTS = ("cnvkit==0.9.12",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    EXIT_SEMANTICS = "Argument validation or a non-zero cnvkit.py command result fails the node."
    AUDIT_STATUS = "contract-checked-no-external-execution"
    CITATION_DOIS = [CNVKIT_CITATION_DOI]
    CITATION_URLS = [f"https://doi.org/{CNVKIT_CITATION_DOI}"]
    CITATION_TEXT = (
        "CNVkit: Genome-Wide Copy Number Detection and Visualization from Targeted DNA Sequencing."
    )
    SHELL = False
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))


__all__ = [
    "CNVKIT_COMMIT",
    "CNVKIT_GIT_COMMIT",
    "CNVKIT_GIT_TAG",
    "CNVKIT_SOURCE_SHA256",
    "CNVkitCommandNode",
    "optional_path",
    "optional_positive_int",
    "output_path",
    "path_list",
    "plan_output",
    "sample_id",
    "validate_bam_index_list",
    "validate_optional_number",
]
