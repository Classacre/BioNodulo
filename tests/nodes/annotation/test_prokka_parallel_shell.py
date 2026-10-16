"""The normal Prokka command gets its shell selection in both execution paths."""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.annotation_family import ProkkaNode, SnpEffNode


@pytest.mark.asyncio
@pytest.mark.parametrize("execution_path", ["context", "direct"])
@pytest.mark.parametrize("parent_shell", [None, "/parent/custom-shell"])
async def test_prokka_parallel_shell_reaches_command_without_mutating_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    execution_path: str,
    parent_shell: str | None,
) -> None:
    if parent_shell is None:
        monkeypatch.delenv("SHELL", raising=False)
    else:
        monkeypatch.setenv("SHELL", parent_shell)
    monkeypatch.setenv("PARALLEL_SHELL", "/parent/missing-parallel-shell")
    assembly = tmp_path / "contigs.fa"
    assembly.write_text(">test\nACGT\n", encoding="ascii")
    run_root = tmp_path / "run"
    captured: list[tuple[list[str], dict]] = []

    async def record_command(command: list[str], **kwargs: object) -> dict:
        captured.append((command, kwargs))
        # Simulate the command's artifact contract; no scientific executable
        # runs, and failures in the wrapper still fail the normal run method.
        for output in ProkkaNode.PLAN_OUTPUTS({"prefix": "audit"}, run_root):
            output.write_text("test artifact\n", encoding="ascii")
        return {"returncode": 0, "stdout": "", "stderr": ""}

    arguments: dict = {
        "assembly": str(assembly), "prefix": "audit", "threads": 4,
        "kingdom": "Bacteria", "output_dir": run_root,
    }
    if execution_path == "context":
        arguments["context"] = SimpleNamespace(node_dir=run_root, run_command=record_command)
    else:
        monkeypatch.setattr("bionodulo.execution.subprocess_runner.run_subprocess", record_command)

    outputs = await ProkkaNode().run(**arguments)

    assert len(captured) == 1
    command, options = captured[0]
    assert command == ProkkaNode.render_command({
        "assembly": str(assembly), "prefix": "audit", "threads": 4,
        "kingdom": "Bacteria", "output": str(run_root / "prokka"),
    })
    assert options["env"] == {"PARALLEL_SHELL": "/bin/sh"}
    assert os.environ.get("SHELL") == parent_shell
    assert os.environ["PARALLEL_SHELL"] == "/parent/missing-parallel-shell"
    assert SnpEffNode.ENV_VARS == {}
    assert len(outputs) == len(ProkkaNode.RETURN_NAMES) == 12
    assert all(Path(output).is_file() for output in outputs)
