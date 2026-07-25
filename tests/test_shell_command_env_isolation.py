"""A shell command must run entirely inside its Pixi environment.

`env_prefix` is an argv prefix ending in `--` (e.g. `pixi run ... --`). A
SHELL=True node returns its command as a *string* containing shell operators.
Concatenating that string after the prefix lets the OUTER shell split on those
operators, so only the first segment runs inside the environment and everything
after `&&` / `|` / `;` runs outside it — where the tools do not exist.

Observed in production: featureCounts emitted
    export FC_PATH=$(command -v featureCounts | ...) && featureCounts ...
which became
    pixi run ... -- export FC_PATH=... && featureCounts ...
`pixi run -- export` exits 127 (no such binary), and the featureCounts call then
ran outside the environment. The same shape silently mis-executes any node whose
command starts with a real binary instead of a shell builtin.
"""
from __future__ import annotations

import shlex

from bionodulo.execution.executor import ExecutionContext


def _wrap(cmd, env_prefix):
    """Reproduce the wrapping ExecutionContext applies before spawning."""
    return ExecutionContext._wrap_with_env_prefix(cmd, env_prefix)


PREFIX = ["pixi", "run", "--locked", "--manifest-path", "/tmp/envs/abc/pixi.toml", "--"]


def test_shell_operators_stay_inside_the_environment() -> None:
    cmd = "export FC_PATH=$(command -v featureCounts) && featureCounts -a ann.gff -o out"
    wrapped = _wrap(cmd, PREFIX)

    assert isinstance(wrapped, str)
    tokens = shlex.split(wrapped)
    # Everything the node asked for must be a SINGLE argument handed to a shell
    # that itself runs inside the prefix.
    assert tokens[: len(PREFIX)] == PREFIX
    assert cmd in tokens, (
        "the node's shell command must be passed as one quoted argument, not "
        f"split across the prefix boundary: {wrapped}"
    )
    # No shell operator may appear as a bare token after the prefix.
    assert "&&" not in tokens


def test_pipes_and_redirects_also_stay_inside() -> None:
    cmd = "samtools view -h in.bam | grep -v '^@' > out.sam"
    tokens = shlex.split(_wrap(cmd, PREFIX))
    assert cmd in tokens
    assert "|" not in tokens and ">" not in tokens


def test_argv_commands_are_unchanged() -> None:
    """A list command needs no shell and must keep its exact argv."""
    cmd = ["samtools", "faidx", "ref.fa"]
    assert _wrap(cmd, PREFIX) == PREFIX + cmd


def test_no_prefix_leaves_the_command_alone() -> None:
    assert _wrap("echo hi && echo there", []) == "echo hi && echo there"
    assert _wrap(["echo", "hi"], []) == ["echo", "hi"]
