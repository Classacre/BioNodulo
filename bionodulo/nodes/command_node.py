"""CommandNode class - wraps external bioinformatics tools.

Provides template-based command rendering, output planning, and execution
via the workflow context.
"""
from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import tempfile
from pathlib import Path
from typing import Any, ClassVar, Optional, Union

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.types import file_extension_for

logger = logging.getLogger(__name__)

# Shell metacharacters that must NOT be quoted when building a shell command string.
_SHELL_METACHARS = {">", ">>", "|", "||", "&&", ";", "<", "<<", "$(", "${", "`", "&"}
_FD_REDIRECT_RE = re.compile(r"^\d*(?:<>|>>|>|<|>&|<&|&>)[^\s]*$")
# Process substitution ( <(...) / >(...) ) is emitted by node templates with any
# embedded user value already shlex-quoted inside, so the whole construct must
# stay bare for bash to interpret it.
_PROCESS_SUB_RE = re.compile(r"^[<>]\(.*\)$")


def _shell_join(cmd: list[str]) -> str:
    """Join a command list into a shell-safe string.

    Every token is quoted with ``shlex.quote()`` EXCEPT the exact operator
    tokens the node's own template emits: a token that is precisely a known shell
    metacharacter, matches the strict FD-redirect pattern (e.g. ``2>``, ``>>``),
    or is a full process-substitution construct (``<(...)`` / ``>(...)``).
    Previously any token merely *starting* with a metacharacter was left bare
    (audit LOW), which would pass e.g. ``>foo;bar`` through unquoted. Anchoring to
    exact/whole-construct matches keeps the intended operators working while
    ensuring nothing else escapes quoting.
    """
    parts: list[str] = []
    for token in cmd:
        if (
            token in _SHELL_METACHARS
            or _FD_REDIRECT_RE.match(token)
            or _PROCESS_SUB_RE.match(token)
        ):
            parts.append(token)
        else:
            parts.append(shlex.quote(token))
    return " ".join(parts)


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

    STDOUT_OUTPUT_INDEX: ClassVar[int | None] = None
    """Optional planned-output index that receives the command's stdout."""

    STDERR_OUTPUT_INDEX: ClassVar[int | None] = None
    """Optional planned-output index that receives the command's stderr."""

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str | list[str]:
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
            rendered_tokens = cls._render_token(token, inputs)
            if rendered_tokens is not None:
                if isinstance(rendered_tokens, list):
                    rendered.extend(rendered_tokens)
                else:
                    rendered.append(str(rendered_tokens))
        return rendered

    @classmethod
    def _render_token(cls, token: str, inputs: dict[str, Any]) -> list[str] | str | None:
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
            Rendered string, list of strings (for multi-value inputs), or None.
        """
        # Match {namespace.name} or {name} patterns
        pattern = re.compile(r"\{([^}]+)\}")

        # Track whether any placeholder expanded to a list
        list_expansion: list[str] | None = None

        def _replace(match: re.Match) -> str:
            nonlocal list_expansion
            key = match.group(1).strip()

            # Helper to resolve a name with optional bracket index
            def _resolve(name: str) -> Any:
                # Handle bracket indexing: reads[0] → inputs["reads"][0]
                bracket_match = re.match(r"^(\w+)\[(\d+)\]$", name)
                if bracket_match:
                    base_name = bracket_match.group(1)
                    idx = int(bracket_match.group(2))
                    base_val = inputs.get(base_name)
                    if isinstance(base_val, (list, tuple)) and idx < len(base_val):
                        return base_val[idx]
                    return None
                return inputs.get(name)

            # Namespace-qualified lookups
            if key.startswith("inputs."):
                name = key[7:]
                val = _resolve(name)
                formatted = cls._format_value(val)
                if isinstance(formatted, list):
                    list_expansion = formatted
                    return match.group(0)  # placeholder replaced later
                return formatted

            if key.startswith("params."):
                name = key[7:]
                val = _resolve(name)
                formatted = cls._format_value(val)
                if isinstance(formatted, list):
                    list_expansion = formatted
                    return match.group(0)
                return formatted

            # Direct lookups
            if key in ("output", "output_dir"):
                return str(inputs.get("output", inputs.get("output_dir", ".")))

            if key == "threads":
                return str(inputs.get("threads", inputs.get("params.threads", 1)))

            # Fallback: try direct input lookup (including bracket indexing)
            val = _resolve(key)
            if val is not None:
                formatted = cls._format_value(val)
                if isinstance(formatted, list):
                    list_expansion = formatted
                    return match.group(0)
                return formatted

            # Unknown placeholder - return as-is for shell variable substitution
            return match.group(0)

        rendered = pattern.sub(_replace, token)

        # If a list value was expanded, the token must be a plain placeholder
        # like "{inputs.reads}" — return the list directly so each element
        # becomes its own subprocess argument.
        if list_expansion is not None and rendered == token:
            return list_expansion

        if rendered == "":
            return None
        return rendered

    @classmethod
    def _format_value(cls, value: Any) -> list[str] | str:
        """Format a Python value for command-line use.

        Args:
            value: The value to format.

        Returns:
            String representation suitable for command-line, or a list of
            strings for multi-value inputs (e.g. FASTQ file pairs).

        Note:
            We do NOT use shlex.quote() here because the rendered tokens are
            passed directly to asyncio.create_subprocess_exec(), where each
            list element is already a separate argument. Quoting would insert
            literal quote characters into the argument strings.
        """
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        if isinstance(value, Path):
            return str(value)
        return str(value)

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

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Prepare deterministic artifacts or inputs before command rendering."""
        return None

    async def run(self, **kwargs: Any) -> Union[tuple[Any, ...], dict[str, Any]]:
        """Execute the command via the workflow context.

        Args:
            **kwargs: Input values from connected upstream nodes.

        Returns:
            Tuple or dict of output values matching RETURN_TYPES.
        """
        # Resolve context from kwargs
        context = kwargs.pop("context", None)
        output_dir = kwargs.pop("output_dir", None)
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")

        real_output_dir = output_dir
        symlink: Path | None = None
        temp_workspace: tempfile.TemporaryDirectory[str] | None = None
        # Some bioinformatics tools crash when paths contain spaces.
        # Create a temporary symlink to a space-free path for command execution,
        # while keeping the real output_dir for planning returns.
        if output_dir is not None and " " in str(output_dir):
            real_output_path = Path(output_dir)
            real_output_path.mkdir(parents=True, exist_ok=True)
            temp_workspace = tempfile.TemporaryDirectory(prefix=f"{self.__class__.NODE_ID}_")
            symlink = Path(temp_workspace.name) / "out"
            try:
                os.symlink(str(real_output_path), symlink, target_is_directory=True)
                output_dir = symlink
            except OSError:
                temp_workspace.cleanup()
                temp_workspace = None
                symlink = None

        # Compute the node's output directory (where PLAN_OUTPUTS places files).
        # Use this for command rendering so that commands which write to
        # {output}/filename end up in the same directory as the planned outputs.
        node_out = Path(output_dir) / self.__class__.NODE_ID if output_dir else Path(".")
        node_out.mkdir(parents=True, exist_ok=True)

        # Inject back so render_command sees {output} and {output_dir}
        kwargs["output"] = str(node_out)
        kwargs["output_dir"] = str(node_out)

        # --- Shared reference-data cache (perf §15 #3) ---------------------------
        # Index-building nodes (STAR/kraken/cellranger) override reference_cache_id
        # to opt in. On a cache HIT we populate node_out from the shared store and
        # SKIP the (30+ min) build; on a miss we build normally then publish the
        # result for every later run (any user). No-op unless the cache is
        # configured (REFERENCE_CACHE_BUCKET) and the node opts in.
        ref_id: str | None = None
        staged_from_cache = False
        try:
            ref_id = self.__class__.reference_cache_id(kwargs)
        except Exception:  # noqa: BLE001 — never let a cache-id error break a run
            ref_id = None
        if ref_id:
            try:
                from bionodulo.execution import reference_cache as _refcache

                if _refcache.cache_enabled():
                    staged = _refcache.stage(ref_id)
                    if staged is not None:
                        # Populate node_out with the staged reference contents.
                        node_out.mkdir(parents=True, exist_ok=True)
                        for item in Path(staged).iterdir():
                            dst = node_out / item.name
                            if not dst.exists():
                                if item.is_dir():
                                    shutil.copytree(item, dst)
                                else:
                                    shutil.copy2(item, dst)
                        staged_from_cache = True
                        logger.info(
                            "[%s] reference cache HIT %s — skipping build",
                            self.__class__.NODE_ID, ref_id,
                        )
            except Exception as exc:  # noqa: BLE001 — miss/error → build normally
                logger.info("[%s] reference cache stage skipped: %s",
                            self.__class__.NODE_ID, exc)

        try:
            # Validate inputs
            validation = self.__class__.VALIDATE_INPUTS(kwargs)
            if validation is not True:
                raise ValueError(f"Input validation failed: {validation}")

            # Plan outputs using the REAL output dir so returned paths are stable.
            # Preparation may use those paths and update inputs consumed by rendering.
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, real_output_dir)
            stdout_output_index = self.__class__.STDOUT_OUTPUT_INDEX
            stderr_output_index = self.__class__.STDERR_OUTPUT_INDEX
            stdout_path: Path | None = None
            stderr_path: Path | None = None
            if stdout_output_index is not None:
                if (
                    isinstance(stdout_output_index, bool)
                    or not isinstance(stdout_output_index, int)
                    or not 0 <= stdout_output_index < len(outputs)
                ):
                    raise ValueError(
                        f"{self.__class__.NODE_ID}.STDOUT_OUTPUT_INDEX "
                        f"{stdout_output_index!r} is invalid for {len(outputs)} planned output(s)"
                    )
                stdout_path = outputs[stdout_output_index]
            if stderr_output_index is not None:
                if (
                    isinstance(stderr_output_index, bool)
                    or not isinstance(stderr_output_index, int)
                    or not 0 <= stderr_output_index < len(outputs)
                ):
                    raise ValueError(
                        f"{self.__class__.NODE_ID}.STDERR_OUTPUT_INDEX "
                        f"{stderr_output_index!r} is invalid for {len(outputs)} planned output(s)"
                    )
                stderr_path = outputs[stderr_output_index]
            if stdout_path is not None and stderr_path == stdout_path:
                raise ValueError(
                    f"{self.__class__.NODE_ID} cannot capture stdout and stderr "
                    "to the same planned output"
                )

            prepare_outputs = outputs
            if symlink is not None:
                real_output_path = Path(real_output_dir)
                execution_output_path = Path(output_dir)
                prepare_outputs = []
                for path in outputs:
                    try:
                        relative_path = path.relative_to(real_output_path)
                    except ValueError:
                        prepare_outputs.append(path)
                    else:
                        prepare_outputs.append(execution_output_path / relative_path)

            self.__class__.PREPARE_EXECUTION(kwargs, prepare_outputs)

            # Render command from the prepared inputs.
            cmd: str | list[str] = self.__class__.render_command(kwargs)
            if not cmd:
                raise RuntimeError(f"No command rendered for {self.__class__.NODE_ID}")

            # When SHELL=True, join command list so shell operators (>, |) work.
            # Arguments with whitespace or special chars are safely quoted;
            # shell metacharacters themselves are left bare.
            if getattr(self.__class__, "SHELL", False) and isinstance(cmd, list):
                cmd = _shell_join(cmd)

            if staged_from_cache:
                # Reference restored from the shared cache — skip the build.
                logger.info("[%s] using cached reference; skipping command",
                            self.__class__.NODE_ID)
                result = {"returncode": 0, "stdout": "", "stderr": ""}
            else:
                logger.info("[%s] Executing: %s", self.__class__.NODE_ID, cmd if isinstance(cmd, str) else " ".join(cmd))

                # Execute via context if available
                if context is not None and hasattr(context, "run_command"):
                    command_kwargs: dict[str, Any] = {
                        "env": self.__class__.ENV_VARS or None,
                        "cwd": self.__class__.WORKING_DIR or output_dir,
                    }
                    if stdout_path is not None:
                        command_kwargs["stdout_path"] = stdout_path
                    if stderr_path is not None:
                        command_kwargs["stderr_path"] = stderr_path
                    result = await context.run_command(cmd, **command_kwargs)
                else:
                    # Fallback: direct subprocess execution via run_subprocess
                    # for consistency and proper shell handling.
                    from bionodulo.execution.subprocess_runner import run_subprocess
                    result = await run_subprocess(
                        cmd,
                        cwd=output_dir,
                        stdout_path=(
                            stdout_path
                            if stdout_path is not None
                            else Path(output_dir) / "stdout.log" if output_dir else None
                        ),
                        stderr_path=(
                            stderr_path
                            if stderr_path is not None
                            else Path(output_dir) / "stderr.log" if output_dir else None
                        ),
                    )

            if result.get("returncode", 0) != 0:
                stderr = result.get("stderr", "")
                raise RuntimeError(
                    f"Command failed (exit {result.get('returncode')}): {stderr[:500]}"
                )

            # Publish a freshly-built reference to the shared cache so every later
            # run (any user) stages it instead of rebuilding. Best-effort.
            if ref_id and not staged_from_cache:
                try:
                    from bionodulo.execution import reference_cache as _refcache

                    if _refcache.cache_enabled():
                        _refcache.publish(ref_id, node_out)
                except Exception as exc:  # noqa: BLE001 — publish is best-effort
                    logger.info("[%s] reference cache publish skipped: %s",
                                self.__class__.NODE_ID, exc)

            missing_outputs = [path for path in outputs if not path.exists()]
            if missing_outputs:
                missing = ", ".join(str(path) for path in missing_outputs)
                raise RuntimeError(f"Command completed but did not create expected output(s): {missing}")

            # Return output paths as tuple
            if len(outputs) == 1:
                return (str(outputs[0]),)
            return tuple(str(p) for p in outputs)
        finally:
            if symlink is not None:
                try:
                    symlink.unlink()
                except OSError:
                    pass
            if temp_workspace is not None:
                temp_workspace.cleanup()
