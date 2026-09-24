"""Exact child environments must not inherit unexpected host variables."""

from __future__ import annotations

import asyncio
import sys

from bionodulo.execution.subprocess_runner import run_subprocess


def test_replace_env_excludes_host_secret_sentinel(monkeypatch) -> None:
    monkeypatch.setenv("UNUSUAL_WORKSPACE_SECRET_SENTINEL", "must-not-reach-child")
    result = asyncio.run(run_subprocess(
        [sys.executable, "-c", "import os; print(os.getenv('UNUSUAL_WORKSPACE_SECRET_SENTINEL', 'absent'))"],
        env={"PYTHONIOENCODING": "utf-8"}, replace_env=True,
    ))
    assert result["stdout"].strip() == "absent"
