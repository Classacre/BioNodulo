"""Small direct-argv adapters for pinned long-read command-line tools."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.command_node import CommandNode


def option_value(inputs: Mapping[str, Any], key: str, default: Any) -> Any:
    """Return the upstream default when an optional UI value is absent."""
    value = inputs.get(key)
    return default if value is None else value


def path_value(value: Any) -> str:
    """Normalize one path-like value without requiring it to exist locally."""
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return path if path.strip() else ""


def path_list(value: Any) -> list[str]:
    """Normalize one or more path-like values while preserving their order."""
    if value is None:
        return []
    if isinstance(value, (str, bytes, os.PathLike)):
        values: Iterable[Any] = (value,)
    elif isinstance(value, Iterable):
        values = value
    else:
        return []
    paths = [path_value(item) for item in values]
    return paths if paths and all(paths) else []


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


def validate_number(
    value: Any,
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"Input '{key}' must be a number"
    number = float(value)
    if minimum is not None and number < minimum:
        return f"Input '{key}' must be at least {minimum:g}"
    if maximum is not None and number > maximum:
        return f"Input '{key}' must be at most {maximum:g}"
    return True


def valid_dorado_device(device: str) -> bool:
    """Mirror the official Dorado 0.9.6 Linux CUDA build device syntax."""
    if device in {"auto", "cpu", "cuda:all", "cuda:auto"}:
        return True
    if not device.startswith("cuda:"):
        return False
    tokens = device[5:].split(",")
    if not tokens or any(not token.isdecimal() for token in tokens):
        return False
    if any(str(int(token)) != token for token in tokens):
        return False
    return len(tokens) == len(set(tokens))


class LongReadCommandNode(CommandNode):
    """Fixed-output command adapter with fail-closed path validation."""

    CATEGORY = "long_read"
    SHELL = False
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    REQUIRED_PATH_INPUTS: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(
        cls,
        inputs: dict[str, Any],
        output_dir: str | Path,
    ) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in cls.REQUIRED_PATH_INPUTS:
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        return True

    @classmethod
    def checked_command(cls, inputs: dict[str, Any], *prefix: str) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return list(prefix)


async def run_direct_argv(
    command: list[str],
    *,
    context: Any,
    cwd: Path,
    env: dict[str, str] | None,
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    """Run one argv while keeping tool-generated binary artifacts off stdout."""
    if context is not None and hasattr(context, "run_command"):
        return await context.run_command(
            command,
            cwd=str(cwd),
            env=env,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

    from bionodulo.execution.subprocess_runner import run_subprocess

    return await run_subprocess(
        command,
        cwd=cwd,
        env=env,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def require_success(result: Mapping[str, Any], *, label: str) -> None:
    """Convert a returned non-zero status into the normal node runtime error."""
    returncode = result.get("returncode", 0)
    if returncode != 0:
        stderr = str(result.get("stderr", ""))
        raise RuntimeError(f"{label} failed (exit {returncode}): {stderr[:500]}")


class DoradoCommandNode(LongReadCommandNode):
    """Dorado 0.9.6 metadata shared by basecalling and demultiplexing."""

    VERSION = "0.9.6"
    GIT_URL = "https://github.com/nanoporetech/dorado.git"
    GIT_COMMIT = "0949eb8de80dce9a198c08c0e37e31ed1eb627fc"
    SOURCE_TAG = "v0.9.6"
    DOCUMENTATION_URL = "https://github.com/nanoporetech/dorado/tree/v0.9.6"
    LINUX_X64_BINARY_URL = "https://cdn.oxfordnanoportal.com/software/analysis/dorado-0.9.6-linux-x64.tar.gz"
    PACKAGE_CONSTRAINT = (
        "official Dorado 0.9.6 binary; no package exists in the configured conda-forge/bioconda channels"
    )
    REQUIRED_EXECUTABLES = ["dorado"]
    REQUIRED_CONDA_PACKAGES: ClassVar[list[str]] = []
    ENVIRONMENT = {
        "provisioning": "external_worker_binary",
        "version": "0.9.6",
        "source": LINUX_X64_BINARY_URL,
        "platform": "linux-64",
    }
    SEARCH_ALIASES = ["BioNodulo builtin", "Dorado", "Oxford Nanopore", "ONT"]
    EXPERIMENTAL = True
    EXIT_SEMANTICS = (
        "Dorado returns EXIT_FAILURE for CLI, input, model, device, and pipeline "
        "errors; an empty demux input directory is a successful no-op."
    )
