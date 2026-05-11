"""CommandNode class - wraps external bioinformatics tools.

Provides template-based command rendering, output planning, and execution
via the workflow context.
"""
from __future__ import annotations

import abc
import logging
import re
import shlex
from pathlib import Path
from typing import Any, ClassVar, Optional, Union

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.types import file_extension_for

logger = logging.getLogger(__name__)


class CommandNode(BaseNode):
    """Base class for nodes that execute external bioinformatics commands.

    Subclasses define a COMMAND template that gets rendered with input values
    and executed via the workflow context.
    """

    # Template command as list of strings with {params.name} placeholders
    COMMAND: ClassVar[list[str]] = []
    """Command template, e.g. ["fastqc", "--threads", "{params.threads}", "{inputs.reads}"]."""

    # Shell execution settings
    SHELL: ClassVar[bool] = False
    """If True, execute command through a shell interpreter."""

    # Working directory override
    WORKING_DIR: ClassVar[Optional[str]] = None
    """Optional working directory for command execution."""

    # Environment variable overrides
    ENV_VARS: ClassVar[dict[str, str]] = {}
    """Additional environment variables for the command."""

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        """Render the COMMAND template with actual input values.

        Args:
            inputs: Dictionary of input parameter values.

        Returns:
            List of command tokens ready for subprocess execution.
        """
        if not cls.COMMAND:
            return []

        rendered: list[str] = []
        for token in cls.COMMAND:
            rendered_token = cls._render_token(token, inputs)
            if rendered_token is not None:
                rendered.append(str(rendered_token))
        return rendered

    @classmethod
    def _render_token(cls, token: str, inputs: dict[str, Any]) -> Any:
        """Render a single command token, replacing placeholders.

        Supports placeholders:
            {inputs.NAME}   - value from inputs dict
            {params.NAME}   - alias for inputs.NAME
            {output}        - resolved output directory
            {output_dir}    - alias for output
            {threads}       - common alias for inputs.threads

        Args:
            token: Template token string.
            inputs: Input values dictionary.

        Returns:
            Rendered value or None to skip this token.
        """
        # Match {namespace.name} or {name} patterns
        pattern = re.compile(r"\{([^}]+)\}")

        def _replace(match: re.Match) -> str:
            key = match.group(1).strip()

            # Namespace-qualified lookups
            if key.startswith("inputs."):
                name = key[7:]
                val = inputs.get(name)
                return cls._format_value(val)

            if key.startswith("params."):
                name = key[7:]
                val = inputs.get(name)
                return cls._format_value(val)

            # Direct lookups
            if key in ("output", "output_dir"):
                return str(inputs.get("output", inputs.get("output_dir", ".")))

            if key == "threads":
                return str(inputs.get("threads", inputs.get("params.threads", 1)))

            # Fallback: try direct input lookup
            if key in inputs:
                return cls._format_value(inputs[key])

            # Unknown placeholder - return as-is for shell variable substitution
            return match.group(0)

        rendered = pattern.sub(_replace, token)
        return rendered

    @classmethod
    def _format_value(cls, value: Any) -> str:
        """Format a Python value for command-line use.

        Args:
            value: The value to format.

        Returns:
            String representation suitable for command-line.
        """
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return " ".join(shlex.quote(str(v)) for v in value)
        if isinstance(value, Path):
            return shlex.quote(str(value))
        return shlex.quote(str(value))

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        """Plan output paths and create output directories.

        Args:
            inputs: Input values.
            output_dir: Base output directory.

        Returns:
            List of planned output paths.
        """
        output_dir = Path(output_dir)
        node_out = output_dir / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)

        paths: list[Path] = []
        for i, ret_type in enumerate(cls.RETURN_TYPES):
            name = cls.RETURN_NAMES[i] if i < len(cls.RETURN_NAMES) else f"output_{i}"
            ext = file_extension_for(ret_type)
            paths.append(node_out / f"{name}{ext}")
        return paths

    async def run(self, **kwargs: Any) -> Union[tuple[Any, ...], dict[str, Any]]:
        """Execute the command via the workflow context.

        Args:
            **kwargs: Input values from connected upstream nodes.

        Returns:
            Tuple or dict of output values matching RETURN_TYPES.
        """
        # Resolve context from kwargs
        context = kwargs.pop("_context", None)
        output_dir = kwargs.pop("_output_dir", ".")

        # Validate inputs
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")

        # Render command
        cmd = self.__class__.render_command(kwargs)
        if not cmd:
            raise RuntimeError(f"No command rendered for {self.__class__.NODE_ID}")

        logger.info("[%s] Executing: %s", self.__class__.NODE_ID, " ".join(cmd))

        # Plan outputs
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)

        # Execute via context if available
        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(
                cmd,
                env=self.__class__.ENV_VARS or None,
                cwd=self.__class__.WORKING_DIR,
                shell=self.__class__.SHELL,
                node_id=self.__class__.NODE_ID,
            )
        else:
            # Fallback: direct subprocess execution
            import asyncio
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            result = {
                "returncode": proc.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
            }

        if result.get("returncode", 0) != 0:
            stderr = result.get("stderr", "")
            raise RuntimeError(
                f"Command failed (exit {result.get('returncode')}): {stderr[:500]}"
            )

        # Return output paths as tuple
        if len(outputs) == 1:
            return (str(outputs[0]),)
        return tuple(str(p) for p in outputs)
