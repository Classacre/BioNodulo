"""Shared validation and execution helpers for focused variant callers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index
from bionodulo.nodes.builtin._reference_sidecars import (
    validate_colocated_reference_index,
)
from bionodulo.nodes.command_node import CommandNode


def option_value(inputs: dict[str, Any], key: str, default: Any) -> Any:
    """Use an upstream default when an optional UI value is absent or null."""
    value = inputs.get(key)
    return default if value is None else value


def validate_integer(
    inputs: dict[str, Any],
    key: str,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> bool | str:
    value = option_value(inputs, key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        return f"{key} must be an integer"
    if minimum is not None and value < minimum:
        return f"{key} must be at least {minimum}"
    if maximum is not None and value > maximum:
        return f"{key} must be at most {maximum}"
    return True


def validate_choice(
    inputs: dict[str, Any],
    key: str,
    default: str,
    choices: tuple[str, ...],
) -> bool | str:
    value = str(option_value(inputs, key, default))
    if value not in choices:
        return f"{key} must be one of: {', '.join(choices)}"
    return True


async def run_direct_argv(
    command: list[str],
    *,
    context: Any,
    cwd: Path,
    env: dict[str, str] | None,
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    """Execute one argv without a shell through the workflow context or fallback."""
    if context is not None and hasattr(context, "run_command"):
        return await context.run_command(command, env=env, cwd=str(cwd))

    from bionodulo.execution.subprocess_runner import run_subprocess

    return await run_subprocess(
        command,
        cwd=cwd,
        env=env,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def require_success(result: dict[str, Any], *, label: str) -> None:
    returncode = result.get("returncode", 0)
    if returncode != 0:
        stderr = str(result.get("stderr", ""))
        raise RuntimeError(f"{label} failed (exit {returncode}): {stderr[:500]}")


class VariantCommandNode(CommandNode):
    """Small adapter for fixed outputs and fail-closed command rendering."""

    CATEGORY = "variant"
    SHELL = False
    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()

    @classmethod
    def PLAN_OUTPUTS(
        cls,
        inputs: dict[str, Any],
        output_dir: str | Path,
    ) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def require_valid_inputs(cls, inputs: dict[str, Any]) -> None:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))


class IndexedBamReferenceNode(VariantCommandNode):
    """Require the exact BAM BAI and FASTA FAI paths consumed implicitly."""

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_colocated_bam_index(inputs)
        if validation is not True:
            return validation
        return validate_colocated_reference_index(inputs)
