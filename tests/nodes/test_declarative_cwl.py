from __future__ import annotations

import asyncio
import hashlib
import json
import platform
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import ExecutionContext
from bionodulo.nodes.contract.cwl import import_cwl
from bionodulo.nodes.contract.environments import (
    CondaLockedArtifact,
    ExecutableProbe,
    ExecutionPlatform,
    PixiEnvironment,
    PlatformLock,
    ResolverIdentity,
)
from bionodulo.nodes.contract.outputs import MissingOutputError
from bionodulo.nodes.declarative_cwl import _render_argv, bind_cwl_node


SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
LINUX_ONLY = pytest.mark.skipif(
    platform.system().lower() != "linux",
    reason="the native descriptor runtime intentionally supports locked Linux environments only",
)


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _python_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[PixiEnvironment, Path]:
    version = platform.python_version()
    prefix = tmp_path / "python-prefix"
    executable = prefix / "bin" / "python"
    executable.parent.mkdir(parents=True)
    shutil.copy2(sys.executable, executable)
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    environment = PixiEnvironment(
        environment_id="python-cwl-runtime",
        platforms=(ExecutionPlatform.LINUX_AMD64,),
        packages=(f"python=={version}",),
        locks=(
            PlatformLock(
                platform=ExecutionPlatform.LINUX_AMD64,
                environment_name="python-cwl-runtime",
                resolver_platform="linux-64",
                resolver=ResolverIdentity(name="pixi", version="0.68.1", config_digest=SHA_A),
                native_lock_sha256=SHA_C,
                artifacts=(
                    CondaLockedArtifact(
                        name="python",
                        version=version,
                        build="test_0",
                        filename=f"python-{version}-test_0.conda",
                        url=f"https://packages.example.org/linux-64/python-{version}-test_0.conda",
                        sha256=SHA_B,
                        size_bytes=executable.stat().st_size,
                    ),
                ),
            ),
        ),
        executable_probes=(
            ExecutableProbe(
                probe_id="python",
                locator="bin/python",
                version_arguments=("--version",),
                version_line_prefix="Python ",
                expected_version=version,
                fingerprint=_file_sha256(executable),
            ),
        ),
    )
    monkeypatch.setenv(
        "BIONODULO_CWL_ENVIRONMENTS",
        json.dumps({environment.environment_id: str(prefix.absolute())}),
    )
    return environment, executable


def _spec(document: dict[str, Any], environment: PixiEnvironment, *, node_id: str = "generated_tool") -> Any:
    source_bytes = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return import_cwl(
        document,
        node_id=node_id,
        environment=environment,
        tool_id="python",
        tool_version=platform.python_version(),
        source_uri="file:///held-out/generated-tool.cwl",
        source_content_sha256="sha256:" + hashlib.sha256(source_bytes).hexdigest(),
        source_size_bytes=len(source_bytes),
    )


def _context(node_dir: Path, node_type: str) -> ExecutionContext:
    return ExecutionContext(
        run_id="runtime-test",
        node_id="node-1",
        node_type=node_type,
        node_dir=node_dir,
        workspace_dir=node_dir.parent,
        params={},
        api_secrets={},
        emit=lambda _event, _payload: None,
        cancel_event=asyncio.Event(),
    )


def test_bound_node_projects_descriptor_ports_and_cache_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, executable = _python_environment(tmp_path, monkeypatch)
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "python",
        "inputs": {
            "source": {"type": "File", "inputBinding": {"position": 2}},
            "count": {"type": "int", "inputBinding": {"position": 3, "prefix": "--count"}},
            "enabled": {
                "type": ["null", "boolean"],
                "default": False,
                "inputBinding": {"position": 4, "prefix": "--enabled"},
            },
        },
        "arguments": [
            {"position": 0, "valueFrom": "-c"},
            {"position": 1, "valueFrom": "from pathlib import Path; Path('result.txt').write_text('ok')"},
        ],
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.txt"}}},
    }
    node = bind_cwl_node(_spec(document, environment))

    inputs = node.INPUT_TYPES()
    assert inputs["required"]["source"][0] == "FILE"
    assert inputs["required"]["count"][0] == "INT"
    assert inputs["optional"]["enabled"][1]["default"] is False
    assert node.RETURN_TYPES == ("FILE",)
    assert node.RETURN_NAMES == ("result",)
    assert node.EXECUTOR_CACHE_POLICY == "always_run"
    assert node.DESCRIPTOR_DIGEST == node.CONTRACT_SPEC.cwl_invocation.descriptor_sha256
    first = node.IS_CHANGED({"source": "input.txt", "count": 2})
    executable.write_bytes(executable.read_bytes() + b"runtime-drift")
    second = node.IS_CHANGED({"source": "input.txt", "count": 2})
    assert first != second


def test_boolean_without_prefix_adds_no_argv_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, _executable = _python_environment(tmp_path, monkeypatch)
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "python",
        "inputs": {"enabled": {"type": "boolean", "inputBinding": {"position": 2}}},
        "arguments": [
            {"position": 0, "valueFrom": "-c"},
            {"position": 1, "valueFrom": "from pathlib import Path; Path('result.txt').touch()"},
        ],
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.txt"}}},
    }
    spec = _spec(document, environment, node_id="boolean_without_prefix")

    assert _render_argv(spec, {"enabled": True}) == list(spec.cwl_invocation.base_command) + [
        "-c",
        "from pathlib import Path; Path('result.txt').touch()",
    ]
    assert _render_argv(spec, {"enabled": False}) == _render_argv(spec, {"enabled": True})


@LINUX_ONLY
@pytest.mark.asyncio
async def test_real_native_execution_stages_file_and_renders_arguments_without_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, _executable = _python_environment(tmp_path, monkeypatch)
    source = tmp_path / "original.txt"
    source.write_text("original", encoding="utf-8")
    script = (
        "import json,sys; from pathlib import Path; "
        "p=Path(sys.argv[1]); p.chmod(0o600); p.write_text('mutated'); "
        "Path('result.txt').write_text(json.dumps(sys.argv[1:]))"
    )
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "python",
        "inputs": {
            "source": {"type": "File", "inputBinding": {"position": 2}},
            "count": {"type": "int", "inputBinding": {"position": 3, "prefix": "--count"}},
            "enabled": {"type": "boolean", "inputBinding": {"position": 4, "prefix": "--enabled"}},
        },
        "arguments": [{"position": 0, "valueFrom": "-c"}, {"position": 1, "valueFrom": script}],
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.txt"}}},
    }
    node = bind_cwl_node(_spec(document, environment))
    node_dir = tmp_path / "run" / "node-1"
    context = _context(node_dir, node.NODE_ID)

    (result_path,) = await node().run(context=context, source=str(source), count=7, enabled=True)

    assert source.read_text(encoding="utf-8") == "original"
    argv = json.loads(Path(result_path).read_text(encoding="utf-8"))
    assert argv[0] != str(source)
    assert Path(argv[0]).name == "original.txt"
    assert argv[1:] == ["--count", "7", "--enabled"]
    provenance = context.run_metadata["declarative_cwl"]["node-1"]
    assert provenance["descriptor_digest"] == node.DESCRIPTOR_DIGEST
    assert provenance["source_content_sha256"] == node.CONTRACT_SPEC.cwl_invocation.source_content_sha256
    assert provenance["source_size_bytes"] == node.CONTRACT_SPEC.cwl_invocation.source_size_bytes
    assert provenance["source_content_sha256"] in provenance["source_digests"]
    assert provenance["binary_fingerprint_verified"] is True
    assert provenance["input_staging"][0]["source_sha256"] == _file_sha256(source)
    log_dirs = tuple(node_dir.parent.glob(".node-1.cwl-logs-*"))
    assert len(log_dirs) == 1
    assert (log_dirs[0] / "command.stderr.log").is_file()


@LINUX_ONLY
@pytest.mark.asyncio
async def test_stdout_artifact_preserves_non_utf8_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, _executable = _python_environment(tmp_path, monkeypatch)
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "python",
        "arguments": [
            {"position": 0, "valueFrom": "-c"},
            {"position": 1, "valueFrom": "import sys; sys.stdout.buffer.write(bytes([255,0,10,128]))"},
        ],
        "inputs": {},
        "stdout": "result.bin",
        "outputs": {"result": "stdout"},
    }
    node = bind_cwl_node(_spec(document, environment, node_id="binary_stdout"))
    node_dir = tmp_path / "run" / "binary"

    (result_path,) = await node().run(context=_context(node_dir, node.NODE_ID))

    assert Path(result_path).read_bytes() == bytes([255, 0, 10, 128])


@LINUX_ONLY
@pytest.mark.asyncio
async def test_exit_zero_without_declared_output_fails_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, _executable = _python_environment(tmp_path, monkeypatch)
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "python",
        "arguments": [
            {"position": 0, "valueFrom": "-c"},
            {"position": 1, "valueFrom": "pass"},
        ],
        "inputs": {},
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "missing.txt"}}},
    }
    node = bind_cwl_node(_spec(document, environment, node_id="missing_output"))
    node_dir = tmp_path / "run" / "missing"
    node_dir.mkdir(parents=True)
    stale = node_dir / "missing.txt"
    stale.write_text("STALE MUST NOT BE ACCEPTED", encoding="utf-8")

    with pytest.raises(MissingOutputError, match="result|missing.txt"):
        await node().run(context=_context(node_dir, node.NODE_ID))
    assert stale.read_text(encoding="utf-8") == "STALE MUST NOT BE ACCEPTED"
    assert not tuple(node_dir.glob(".cwl-attempt-*"))


@LINUX_ONLY
@pytest.mark.asyncio
async def test_failed_attempt_outputs_are_removed_before_a_fresh_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment, _executable = _python_environment(tmp_path, monkeypatch)
    marker = tmp_path / "first-attempt.marker"
    script = (
        f"import sys; from pathlib import Path; marker=Path({str(marker)!r}); "
        "first=not marker.exists(); marker.touch(); "
        "Path('result.txt').write_text('failed-attempt' if first else 'fresh-attempt'); "
        "sys.exit(17 if first else 0)"
    )
    document = {
        "cwlVersion": "v1.2",
        "class": "CommandLineTool",
        "baseCommand": "python",
        "arguments": [{"position": 0, "valueFrom": "-c"}, {"position": 1, "valueFrom": script}],
        "inputs": {},
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.txt"}}},
    }
    node = bind_cwl_node(_spec(document, environment, node_id="retry_isolation"))
    node_dir = tmp_path / "run" / "retry"
    context = _context(node_dir, node.NODE_ID)

    with pytest.raises(Exception, match="17|exit"):
        await node().run(context=context)
    assert not tuple(node_dir.glob(".cwl-attempt-*"))

    (result_path,) = await node().run(context=context)

    assert Path(result_path).read_text(encoding="utf-8") == "fresh-attempt"
    assert len(tuple(node_dir.glob(".cwl-attempt-*"))) == 1
