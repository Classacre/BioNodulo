from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import ExecutionContext
from bionodulo.nodes.command_node import CommandNode


class _RecordingContext:
    def __init__(self, node_dir: Path, produced_output: Path | None = None) -> None:
        self.node_dir = node_dir
        self.produced_output = produced_output
        self.command: str | list[str] | None = None
        self.stdout_path: Path | None = None

    async def run_command(
        self,
        cmd: str | list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.command = cmd
        raw_stdout_path = kwargs.get("stdout_path")
        self.stdout_path = (
            Path(raw_stdout_path) if raw_stdout_path is not None else self.node_dir / "stdout.log"
        )
        self.stdout_path.parent.mkdir(parents=True, exist_ok=True)
        self.stdout_path.write_text("command output\n", encoding="utf-8")
        if self.produced_output is not None and self.produced_output != self.stdout_path:
            self.produced_output.write_text("created artifact\n", encoding="utf-8")
        return {"returncode": 0, "stdout": "command output\n", "stderr": ""}


def test_command_node_default_prepare_execution_is_noop() -> None:
    assert CommandNode.PREPARE_EXECUTION({}, []) is None


@pytest.mark.asyncio
async def test_command_node_prepares_planned_outputs_before_rendering(tmp_path: Path) -> None:
    events: list[tuple[str, Path]] = []

    class PreparedCommandNode(CommandNode):
        NODE_ID = "prepared_command"
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("artifact",)

        @classmethod
        def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
            events.append(("prepare", outputs[0]))
            inputs["prepared_output"] = str(outputs[0])

        @classmethod
        def render_command(cls, inputs: dict[str, Any]) -> list[str]:
            prepared_output = Path(inputs["prepared_output"])
            events.append(("render", prepared_output))
            return ["fake-tool", str(prepared_output)]

    expected_output = tmp_path / "prepared_command" / "artifact.out"
    context = _RecordingContext(tmp_path, produced_output=expected_output)

    result = await PreparedCommandNode().run(context=context, output_dir=tmp_path)

    assert events == [("prepare", expected_output), ("render", expected_output)]
    assert context.command == ["fake-tool", str(expected_output)]
    assert result == (str(expected_output),)


@pytest.mark.asyncio
async def test_command_node_prepares_space_free_output_alias_for_rendering(tmp_path: Path) -> None:
    prepared_outputs: list[Path] = []
    outside_output = tmp_path / "outside-artifact.out"
    plan_calls = 0

    class SpacedOutputCommandNode(CommandNode):
        NODE_ID = "spaced_output_command"
        RETURN_TYPES = ("FILE", "FILE")
        RETURN_NAMES = ("artifact", "outside_artifact")
        STDOUT_OUTPUT_INDEX = 0

        @classmethod
        def PLAN_OUTPUTS(cls, _inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
            nonlocal plan_calls
            plan_calls += 1
            return [Path(output_dir) / cls.NODE_ID / "artifact.out", outside_output]

        @classmethod
        def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
            prepared_outputs.extend(outputs)
            inputs["prepared_output"] = str(outputs[0])

        @classmethod
        def render_command(cls, inputs: dict[str, Any]) -> list[str]:
            return ["fake-tool", str(inputs["prepared_output"])]

    class ArgvWritingContext:
        def __init__(self, node_dir: Path) -> None:
            self.node_dir = node_dir
            self.command: list[str] | None = None
            self.resolved_output: Path | None = None
            self.stdout_path: Path | None = None

        async def run_command(self, cmd: str | list[str], **kwargs: Any) -> dict[str, Any]:
            assert isinstance(cmd, list)
            self.command = cmd
            self.stdout_path = Path(kwargs["stdout_path"])
            argv_output = Path(cmd[-1])
            self.resolved_output = argv_output.resolve()
            argv_output.write_text("created through alias\n", encoding="utf-8")
            outside_output.write_text("created outside output base\n", encoding="utf-8")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    output_dir = tmp_path / "output directory with spaces"
    expected_output = output_dir / "spaced_output_command" / "artifact.out"
    context = ArgvWritingContext(output_dir)

    result = await SpacedOutputCommandNode().run(context=context, output_dir=output_dir)

    assert context.command is not None
    argv_output = Path(context.command[-1])
    assert plan_calls == 1
    assert prepared_outputs == [argv_output, outside_output]
    assert " " not in str(argv_output)
    assert context.resolved_output == expected_output
    assert context.stdout_path == expected_output
    assert expected_output.read_text(encoding="utf-8") == "created through alias\n"
    assert outside_output.read_text(encoding="utf-8") == "created outside output base\n"
    assert result == (str(expected_output), str(outside_output))


@pytest.mark.asyncio
async def test_command_node_redirects_stdout_to_declared_output(tmp_path: Path) -> None:
    class StdoutCommandNode(CommandNode):
        NODE_ID = "stdout_command"
        COMMAND = ["fake-tool"]
        RETURN_TYPES = ("STATS_FILE",)
        RETURN_NAMES = ("report",)
        STDOUT_OUTPUT_INDEX = 0

    expected_output = tmp_path / "stdout_command" / "report.stats.txt"
    context = _RecordingContext(tmp_path)

    result = await StdoutCommandNode().run(context=context, output_dir=tmp_path)

    assert context.stdout_path == expected_output
    assert expected_output.read_text(encoding="utf-8") == "command output\n"
    assert not (tmp_path / "stdout.log").exists()
    assert result == (str(expected_output),)


@pytest.mark.asyncio
async def test_command_node_direct_fallback_redirects_stdout_to_declared_output(
    tmp_path: Path,
) -> None:
    class DirectStdoutCommandNode(CommandNode):
        NODE_ID = "direct_stdout_command"
        COMMAND = [sys.executable, "-c", "print('direct output')"]
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("artifact",)
        STDOUT_OUTPUT_INDEX = 0

    expected_output = tmp_path / "direct_stdout_command" / "artifact.out"

    result = await DirectStdoutCommandNode().run(output_dir=tmp_path)

    assert expected_output.read_text(encoding="utf-8").strip() == "direct output"
    assert not (tmp_path / "stdout.log").exists()
    assert result == (str(expected_output),)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_index", [-1, 1])
async def test_command_node_rejects_invalid_stdout_output_index_before_execution(
    tmp_path: Path,
    invalid_index: int,
) -> None:
    class InvalidStdoutCommandNode(CommandNode):
        NODE_ID = "invalid_stdout_command"
        COMMAND = ["must-not-run"]
        RETURN_TYPES = ("FILE",)
        RETURN_NAMES = ("artifact",)
        STDOUT_OUTPUT_INDEX = invalid_index

    class NeverRunContext:
        node_dir = tmp_path
        executed = False

        async def run_command(self, _cmd: str | list[str], **_kwargs: Any) -> dict[str, Any]:
            self.executed = True
            raise AssertionError("command execution should not be reached")

    context = NeverRunContext()

    with pytest.raises(ValueError, match=r"STDOUT_OUTPUT_INDEX.*planned output"):
        await InvalidStdoutCommandNode().run(context=context, output_dir=tmp_path)

    assert context.executed is False


def _execution_context(node_dir: Path) -> ExecutionContext:
    node_dir.mkdir(parents=True, exist_ok=True)
    return ExecutionContext(
        run_id="run-1",
        node_id="node-1",
        node_type="test",
        node_dir=node_dir,
        workspace_dir=node_dir.parent,
        params={},
        api_secrets={},
        emit=lambda _event, _data: None,
        cancel_event=asyncio.Event(),
    )


@pytest.mark.asyncio
async def test_execution_context_run_command_keeps_default_log_paths(tmp_path: Path) -> None:
    node_dir = tmp_path / "node"
    context = _execution_context(node_dir)

    await context.run_command(
        [
            sys.executable,
            "-c",
            "import sys; print('default-out'); print('default-err', file=sys.stderr)",
        ]
    )

    assert (node_dir / "stdout.log").read_text(encoding="utf-8").strip() == "default-out"
    assert (node_dir / "stderr.log").read_text(encoding="utf-8").strip() == "default-err"


@pytest.mark.asyncio
async def test_execution_context_run_command_accepts_stream_path_overrides(tmp_path: Path) -> None:
    node_dir = tmp_path / "node"
    context = _execution_context(node_dir)
    stdout_path = tmp_path / "artifacts" / "report.txt"
    stderr_path = tmp_path / "diagnostics" / "tool.err"

    await context.run_command(
        [
            sys.executable,
            "-c",
            "import sys; print('artifact-out'); print('artifact-err', file=sys.stderr)",
        ],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )

    assert stdout_path.read_text(encoding="utf-8").strip() == "artifact-out"
    assert stderr_path.read_text(encoding="utf-8").strip() == "artifact-err"
    assert not (node_dir / "stdout.log").exists()
    assert not (node_dir / "stderr.log").exists()
