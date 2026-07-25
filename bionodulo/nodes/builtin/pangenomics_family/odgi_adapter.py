"""Shared ODGI 0.9.2 metadata and command helpers."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


def path_value(value: Any) -> str | None:
    """Return one non-empty filesystem path."""
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return None
    return path if path.strip() else None


def validate_input_file(value: Any, label: str) -> str | None:
    """Return an error for a missing, empty, or unreadable input file."""
    path = path_value(value)
    if path is None:
        return f"{label} must be a non-empty path-like value"
    source = Path(path)
    if not source.is_file() or not os.access(source, os.R_OK):
        return f"{label} does not exist or is not readable: {path}"
    if source.stat().st_size == 0:
        return f"{label} is empty: {path}"
    return None


def validate_positive_int(value: Any, label: str) -> str | None:
    """Return an error unless a value is a positive integer."""
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{label} must be an integer"
    if value < 1:
        return f"{label} must be at least 1"
    return None


def safe_output_stem(value: Any, fallback: str) -> str:
    """Create a stable filename stem without interpreting path separators."""
    text = str(value or "").strip() or fallback
    stem = Path(text).name
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return stem or fallback


def stats_argv(graph: str | os.PathLike[str], threads: int) -> list[str]:
    """Render ODGI's documented tabular summary operation."""
    return ["odgi", "stats", "-i", os.fsdecode(os.fspath(graph)), "-S", "-t", str(threads)]


def stats_json_pipeline(
    graph: str | os.PathLike[str],
    output: str | os.PathLike[str],
    threads: int,
) -> str:
    """Adapt ODGI's exact two-line summary using Bash built-ins only."""
    output_q = shlex.quote(os.fsdecode(os.fspath(output)))
    summary_command = shlex.join(stats_argv(graph, threads))
    return "\n".join(
        [
            f": > {output_q}",
            f"summary=$({summary_command})",
            r'''header="${summary%%$'\n'*}"''',
            r"""if [[ "$summary" == "$header" ]]; then printf '[bionodulo::odgi] expected a two-line summary\n' >&2; exit 1; fi""",
            r'''row="${summary#*$'\n'}"''',
            r"""if [[ "$row" == *$'\n'* ]]; then printf '[bionodulo::odgi] unexpected extra summary rows\n' >&2; exit 1; fi""",
            r"""if [[ "$header" != $'#length\tnodes\tedges\tpaths\tsteps' ]]; then printf '[bionodulo::odgi] unexpected summary header\n' >&2; exit 1; fi""",
            r'''IFS=$'\t' read -r length nodes edges paths steps extra <<< "$row"''',
            r"""if [[ -n "$extra" ]]; then printf '[bionodulo::odgi] unexpected summary columns\n' >&2; exit 1; fi""",
            r"""for value in "$length" "$nodes" "$edges" "$paths" "$steps"; do if [[ ! "$value" =~ ^[0-9]+$ ]]; then printf '[bionodulo::odgi] summary values must be unsigned integers\n' >&2; exit 1; fi; done""",
            f"""printf '{{"edges":%s,"length":%s,"nodes":%s,"paths":%s,"steps":%s}}\\n' "$edges" "$length" "$nodes" "$paths" "$steps" > {output_q}""",
            f"[[ -s {output_q} ]]",
        ]
    )


def bash_pipeline(commands: list[str]) -> list[str]:
    """Execute a fixed compound command with pipeline failure propagation."""
    return ["bash", "-o", "pipefail", "-c", "set -euo pipefail\n" + "\n".join(commands)]


class ODGICommandNode(CommandNode):
    """Pinned metadata and non-empty output checks for ODGI operations."""

    CATEGORY = "pangenomics"
    REQUIRED_EXECUTABLES = ["odgi"]
    REQUIRED_CONDA_PACKAGES = ["odgi"]
    VERSION = "0.9.2"
    CONDA_PACKAGE_CONSTRAINTS = {"odgi": VERSION}
    PACKAGE_CONSTRAINTS = (f"odgi=={VERSION}",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    GIT_URL = "https://github.com/pangenome/odgi.git"
    GIT_COMMIT = "be6a0202501d7ea2ac57f9ad89d4d10ed5dbd7c6"
    DOCUMENTATION_URL = (
        "https://github.com/pangenome/odgi/tree/be6a0202501d7ea2ac57f9ad89d4d10ed5dbd7c6/docs/rst/commands"
    )
    SOURCE_REF = f"tag v0.9.2 at {GIT_COMMIT}"
    SOURCE_REVISION = GIT_COMMIT
    SOURCE_URL = f"https://github.com/pangenome/odgi/tree/{GIT_COMMIT}"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    CITATION_DOIS = ["10.1093/bioinformatics/btac308"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btac308"]
    CITATION_TEXT = "Guarracino et al. ODGI: understanding pangenome graphs. Bioinformatics (2022)."
    SHELL = False

    UPSTREAM_TAG: ClassVar[str] = "v0.9.2"
    BIOCONDA_RECIPE_COMMIT: ClassVar[str] = "aac8e6e4ee3d12bd497495dddfc32825393c35da"
    BIOCONDA_RECIPE_URL: ClassVar[str] = (
        "https://github.com/bioconda/bioconda-recipes/blob/"
        "aac8e6e4ee3d12bd497495dddfc32825393c35da/recipes/odgi/meta.yaml"
    )
    UPSTREAM_SOURCE: ClassVar[str] = ""
    EXIT_SEMANTICS: ClassVar[str] = (
        "Any non-zero ODGI or compound-shell status, missing planned artifact, or empty "
        "planned artifact fails the node."
    )

    async def run(self, **kwargs: Any) -> tuple[Any, ...] | dict[str, Any]:
        result = await super().run(**kwargs)
        if not isinstance(result, tuple):
            return result
        empty = [Path(str(path)) for path in result if Path(str(path)).stat().st_size == 0]
        if empty:
            names = ", ".join(str(path) for path in empty)
            raise RuntimeError(f"ODGI completed but produced empty output artifact(s): {names}")
        return result
