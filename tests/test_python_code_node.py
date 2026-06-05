from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.execution.subprocess_runner import CommandExecutionError
from bionodulo.nodes.builtin import python_code
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _context(tmp_path: Path, name: str) -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir()
    return SimpleNamespace(node_dir=node_dir)


def _require_bwrap() -> None:
    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is required for Python Code node sandbox tests")


def test_python_code_reports_sandbox_prerequisite_status(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = {
        "bwrap": "/usr/bin/bwrap",
        "newuidmap": "/usr/bin/newuidmap",
        "newgidmap": None,
    }

    monkeypatch.setattr(python_code.shutil, "which", lambda executable: paths[executable])

    assert python_code.sandbox_prerequisite_status() == {
        "bwrap": {
            "available": True,
            "path": "/usr/bin/bwrap",
            "required": True,
            "auto_installable": False,
            "description": "Bubblewrap sandbox executable",
        },
        "newuidmap": {
            "available": True,
            "path": "/usr/bin/newuidmap",
            "required": True,
            "auto_installable": False,
            "description": "User namespace UID mapping helper for bubblewrap",
        },
        "newgidmap": {
            "available": False,
            "path": None,
            "required": True,
            "auto_installable": False,
            "description": "User namespace GID mapping helper for bubblewrap",
        },
    }


@pytest.mark.asyncio
async def test_python_code_appends_missing_uidmap_prerequisites_to_sandbox_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = {
        "bwrap": "/usr/bin/bwrap",
        "newuidmap": None,
        "newgidmap": None,
    }
    node = _node_class("python_code")()

    async def fail_sandbox(_context, _command, out_dir: Path, _timeout_seconds: int) -> dict[str, object]:
        stderr_path = out_dir / "stderr.log"
        stderr_path.write_text("bwrap: setup failed\n", encoding="utf-8")
        raise CommandExecutionError("bwrap", 1, out_dir / "stdout.log", stderr_path)

    monkeypatch.setattr(python_code.shutil, "which", lambda executable: paths[executable])
    monkeypatch.setattr(node, "_run_sandbox_command", fail_sandbox)

    with pytest.raises(RuntimeError) as exc_info:
        await node.run(
            code='output = {"ok": True}',
            inputs_json="{}",
            timeout_seconds=5,
            context=_context(tmp_path, "uidmap-missing"),
        )

    message = str(exc_info.value)
    assert "Python Code failed: bwrap: setup failed" in message
    assert "missing sandbox prerequisites on PATH: newuidmap, newgidmap" in message


@pytest.mark.asyncio
async def test_python_code_node_executes_json_inputs_in_bwrap(tmp_path: Path) -> None:
    _require_bwrap()
    node = _node_class("python_code")()

    result_json, result, stdout = await node.run(
        code="""
total = sum(sample["count"] for sample in inputs["samples"])
output = {"sample_count": len(inputs["samples"]), "total": total}
""".strip(),
        inputs_json=json.dumps({"samples": [{"count": 4}, {"count": 7}]}),
        timeout_seconds=5,
        context=_context(tmp_path, "code"),
    )

    assert Path(result_json).exists()
    assert json.loads(Path(result_json).read_text(encoding="utf-8")) == {
        "sample_count": 2,
        "total": 11,
    }
    assert result == {"sample_count": 2, "total": 11}
    assert stdout == ""


@pytest.mark.asyncio
async def test_python_code_node_allows_numpy_but_blocks_network_by_namespace(tmp_path: Path) -> None:
    _require_bwrap()
    node = _node_class("python_code")()

    _result_json, result, _stdout = await node.run(
        code="""
import numpy as np

try:
    import socket
except ImportError as exc:
    socket_error = type(exc).__name__
else:
    socket_error = "allowed"

output = {"mean": float(np.mean(inputs["values"])), "socket_import": socket_error}
""".strip(),
        inputs_json=json.dumps({"values": [2, 4, 6]}),
        timeout_seconds=5,
        context=_context(tmp_path, "numpy"),
    )

    assert result == {"mean": 4.0, "socket_import": "ImportError"}


@pytest.mark.asyncio
async def test_python_code_node_blocks_host_file_reads(tmp_path: Path) -> None:
    _require_bwrap()
    secret = tmp_path / "host-secret.txt"
    secret.write_text("top-secret", encoding="utf-8")
    node = _node_class("python_code")()

    result_json, result, _stdout = await node.run(
        code=f"""
try:
    output = {{"content": open({str(secret)!r}).read()}}
except Exception as exc:
    output = {{"blocked": type(exc).__name__, "message": str(exc)}}
""".strip(),
        inputs_json="{}",
        timeout_seconds=5,
        context=_context(tmp_path, "blocked"),
    )

    assert result["blocked"] in {"FileNotFoundError", "PermissionError"}
    assert "top-secret" not in Path(result_json).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_python_code_node_times_out_long_running_code(tmp_path: Path) -> None:
    _require_bwrap()
    node = _node_class("python_code")()

    with pytest.raises(TimeoutError, match="timed out after 1 second"):
        await node.run(
            code="while True:\n    pass",
            inputs_json="{}",
            timeout_seconds=1,
            context=_context(tmp_path, "timeout"),
        )
