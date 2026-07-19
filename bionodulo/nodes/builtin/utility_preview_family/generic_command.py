"""Product-native arbitrary Bash command execution contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.execution.subprocess_runner import run_subprocess
from bionodulo.nodes.command_node import CommandNode

from .adapter import (
    INTERNAL_BASELINE_BLOB,
    INTERNAL_BASELINE_COMMIT,
    INTERNAL_GIT_URL,
    PYTHON_GIT_COMMIT,
    PYTHON_VERSION,
    path_value,
    validate_int,
)


class GenericCommandNode(CommandNode):
    """Execute one caller-provided Bash program and capture its stdout."""

    NODE_ID = "generic_command"
    DISPLAY_NAME = "Shell Command"
    CATEGORY = "utils"
    DESCRIPTION = "Run a custom Bash command and capture stdout as a workflow artifact"
    SEARCH_ALIASES = ["shell", "command", "bash", "custom", "script"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRES_EXTERNAL_TOOLS = False
    SHELL = True
    VERSION = "1.0.0"
    GIT_URL = INTERNAL_GIT_URL
    GIT_COMMIT = INTERNAL_BASELINE_COMMIT
    DOCUMENTATION_URL = "https://www.gnu.org/software/bash/manual/"
    UPSTREAM_SOURCE = (
        f"bionodulo/nodes/builtin/utils.py blob {INTERNAL_BASELINE_BLOB}; "
        "bionodulo/execution/subprocess_runner.py"
    )
    SOURCE_AUTHORITIES = {
        "BioNodulo utility baseline": (INTERNAL_BASELINE_COMMIT, INTERNAL_BASELINE_BLOB),
        "CPython asyncio": (PYTHON_VERSION, PYTHON_GIT_COMMIT),
    }
    SHELL_EXECUTABLE = "/bin/bash"
    EXIT_SEMANTICS = (
        "The Bash process must exit zero before timeout; stdout is captured to output.txt, "
        "and timeout or non-zero exit fails the node."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "command": ("STRING", {"description": "Bash command to execute", "multiline": True}),
            },
            "optional": {
                "working_dir": ("DIRECTORY", {"description": "Working directory"}),
                "timeout": ("INT", {"default": 3600, "min": 1, "description": "Timeout in seconds"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        path = Path(output_dir) / cls.NODE_ID / "output.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        return [path]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("command", "")).strip():
            return "Input 'command' must contain a non-empty Bash program"
        validation = validate_int(inputs.get("timeout", 3600), "timeout", minimum=1)
        if validation is not True:
            return validation
        working_dir = inputs.get("working_dir")
        if working_dir not in (None, ""):
            raw_path = path_value(working_dir)
            if not raw_path:
                return "Input 'working_dir' must be a non-empty path-like value"
            path = Path(raw_path)
            if not path.exists():
                return f"Working directory not found: {path}"
            if not path.is_dir():
                return f"Working directory is not a directory: {path}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return str(inputs["command"])

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        explicit_output_dir = kwargs.pop("output_dir", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        base_dir = Path(
            explicit_output_dir
            if explicit_output_dir is not None
            else getattr(context, "node_dir", ".") if context is not None else "."
        )
        output_path = self.PLAN_OUTPUTS(kwargs, base_dir)[0]
        stderr_path = output_path.parent / "stderr.log"
        working_dir = Path(path_value(kwargs.get("working_dir")) or base_dir)
        timeout = int(kwargs.get("timeout", 3600))
        command = self.render_command(kwargs)

        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(
                command,
                cwd=working_dir,
                timeout=timeout,
                stdout_path=output_path,
                stderr_path=stderr_path,
            )
        else:
            result = await run_subprocess(
                command,
                cwd=working_dir,
                timeout=timeout,
                stdout_path=output_path,
                stderr_path=stderr_path,
                node_id=self.NODE_ID,
            )
        if result.get("returncode", 0) != 0:
            raise RuntimeError(
                f"Command failed (exit {result.get('returncode')}): {str(result.get('stderr', ''))[:500]}"
            )
        if not output_path.is_file():
            raise RuntimeError(f"Command completed but stdout artifact is missing: {output_path}")
        return (str(output_path),)
