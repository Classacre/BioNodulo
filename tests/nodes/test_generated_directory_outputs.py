"""Generated directory outputs must agree with CommandNode's injected path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.seqfu_family.seqfu_shred import SeqfuShredNode
from bionodulo.nodes.builtin.unikmer_family.unikmer_grep import UnikmerGrepNode
from bionodulo.nodes.builtin.unikmer_family.unikmer_split import UnikmerSplitNode
from bionodulo.nodes.builtin.unikmer_family.unikmer_tsplit import UnikmerTsplitNode


CASES = (
    (SeqfuShredNode, "--out-prefix"),
    (UnikmerGrepNode, "--out-dir"),
    (UnikmerSplitNode, "--out-dir"),
    (UnikmerTsplitNode, "--out-dir"),
)


class FakeContext:
    def __init__(self, node_dir: Path, *, write_file: bool) -> None:
        self.node_dir = node_dir
        self.write_file = write_file
        self.command: list[str] = []

    async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
        self.command = command
        if self.write_file:
            flag = "--out-prefix" if "--out-prefix" in command else "--out-dir"
            target = Path(command[command.index(flag) + 1])
            if flag == "--out-prefix":
                target.parent.mkdir(parents=True, exist_ok=True)
                (target.parent / f"{target.name}_1.fq").write_text("@read\nA\n+\nI\n")
            else:
                target.mkdir(parents=True, exist_ok=True)
                (target / "part.unik").write_bytes(b"artifact")
        return {"returncode": 0, "stdout": "", "stderr": ""}


@pytest.mark.asyncio
@pytest.mark.parametrize("node,flag", CASES, ids=lambda value: getattr(value, "NODE_ID", str(value)))
async def test_run_returns_exact_directory_where_command_writes(
    tmp_path: Path, node: type, flag: str
) -> None:
    input_path = tmp_path / "input.fa"
    input_path.write_text(">read\nACGT\n")
    context = FakeContext(tmp_path / "run", write_file=True)

    inputs = {"input": str(input_path)}
    if node is UnikmerGrepNode:
        inputs["query"] = "ACG"
    result = await node().run(context=context, **inputs)

    planned_dir = context.node_dir / node.NODE_ID
    assert node.PLAN_OUTPUTS({}, context.node_dir) == [planned_dir]
    assert result == (str(planned_dir),)
    target = Path(context.command[context.command.index(flag) + 1])
    assert target == (planned_dir / "output" if flag == "--out-prefix" else planned_dir)
    assert any(path.is_file() for path in planned_dir.rglob("*"))


@pytest.mark.asyncio
@pytest.mark.parametrize("node,flag", CASES, ids=lambda value: getattr(value, "NODE_ID", str(value)))
async def test_zero_exit_without_directory_content_fails(
    tmp_path: Path, node: type, flag: str
) -> None:
    input_path = tmp_path / "input.fa"
    input_path.write_text(">read\nACGT\n")
    context = FakeContext(tmp_path / "run", write_file=False)

    inputs = {"input": str(input_path)}
    if node is UnikmerGrepNode:
        inputs["query"] = "ACG"
    with pytest.raises(RuntimeError, match="produced no files"):
        await node().run(context=context, **inputs)

    assert flag in context.command
