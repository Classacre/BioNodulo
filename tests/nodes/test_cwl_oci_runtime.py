"""The OCI command remains unavailable until binaries, daemon, and image match."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes import cwl_oci_runtime as runtime
from bionodulo.nodes.contract.cwl_oci import import_cwl_oci, import_cwl_oci_spec
from bionodulo.nodes.contract.environments import ExecutionPlatform


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _contract():
    source = json.dumps({
        "cwlVersion": "v1.2", "class": "CommandLineTool", "baseCommand": "seqtool",
        "hints": [{"class": "DockerRequirement", "dockerPull": "example.org/lab/sequence:v1"}],
        "inputs": {}, "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.fa"}}},
    })
    return import_cwl_oci(
        source, source_uri="https://example.org/sequence.cwl",
        image_index="example.org/lab/sequence@sha256:" + "a" * 64,
        image_platform="example.org/lab/sequence@sha256:" + "a" * 64,
        platform=ExecutionPlatform.LINUX_AMD64,
    )


def _config(tmp_path: Path):
    engine = tmp_path / "cwltool"
    docker = tmp_path / "docker"
    node = tmp_path / "node"
    engine.write_bytes(b"pinned cwltool")
    docker.write_bytes(b"pinned docker")
    node.write_bytes(b"pinned node")
    docker.chmod(0o755)
    node.chmod(0o755)
    return runtime.CwlOciRuntimeConfig(
        cwltool=engine, cwltool_sha256=_digest(engine.read_bytes()),
        cwltool_version="3.2.20260720092025",
        docker=docker, docker_sha256=_digest(docker.read_bytes()),
        nodejs=node, nodejs_sha256=_digest(node.read_bytes()), nodejs_version="v18.19.1",
    )


def test_oci_preparation_fails_closed_without_proven_runtime(tmp_path: Path) -> None:
    config = _config(tmp_path)
    config.docker.unlink()
    with pytest.raises(runtime.OciRuntimeUnavailable, match="Docker must be"):
        runtime.prove_oci_runtime(_contract(), config)


def test_oci_preparation_requires_cached_exact_digest(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    monkeypatch.setattr(runtime.shutil, "which", lambda cmd, *, path: next(
        str(candidate) for directory in path.split(os.pathsep)
        if (candidate := Path(directory) / cmd).exists()
    ))
    contract = _contract()
    job = tmp_path / "job.json"
    job.write_text("{}")

    def run(args, **_kwargs):
        if args[1] == "--version":
            return SimpleNamespace(stdout="v18.19.1\n" if Path(args[0]).name == "node" else "cwltool 3.2.20260720092025\n")
        if args[1] == "info":
            return SimpleNamespace(stdout=json.dumps({"ServerVersion": "28.0", "OSType": "linux", "Architecture": "x86_64"}))
        return SimpleNamespace(stdout=json.dumps(["example.org/lab/sequence@sha256:" + "c" * 64]))

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(runtime.OciRuntimeUnavailable, match="exact OCI platform image digest is absent"):
        runtime.prepare_oci_invocation(contract, config, workspace=tmp_path, job_path=job)
    assert not (tmp_path / "tool.oci.cwl").exists()

    def matched(args, **kwargs):
        result = run(args, **kwargs)
        if args[1] == "image":
            return SimpleNamespace(stdout=json.dumps([contract.image_platform]))
        return result

    monkeypatch.setattr(runtime.subprocess, "run", matched)
    command, receipt, environment = runtime.prepare_oci_invocation(contract, config, workspace=tmp_path, job_path=job)
    assert "--disable-pull" in command and "--no-container" not in command
    assert command[command.index("--custom-net") + 1] == "none"
    assert "--strict-memory-limit" in command and "--strict-cpu-limit" in command
    assert "--rm-container" in command
    assert receipt["image_platform"] == contract.image_platform
    assert receipt["effective_source_sha256"] == _digest((tmp_path / "tool.oci.cwl").read_bytes())
    assert runtime.shutil.which("docker", path=environment["PATH"]) == str(tmp_path / "docker-cli" / "docker")
    assert receipt["docker_wrapper_sha256"] == _digest((tmp_path / "docker-cli" / "docker").read_bytes())


def test_oci_runtime_rejects_wrong_daemon_architecture(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    monkeypatch.setattr(runtime.shutil, "which", lambda cmd, **_kwargs: str(config.nodejs if cmd == "node" else config.docker))

    def run(args, **_kwargs):
        if args[1] == "--version":
            return SimpleNamespace(stdout="v18.19.1\n" if Path(args[0]).name == "node" else "cwltool 3.2.20260720092025\n")
        return SimpleNamespace(stdout=json.dumps({
            "ServerVersion": "28.0", "OSType": "linux", "Architecture": "aarch64",
        }))

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(runtime.OciRuntimeUnavailable, match="linux/amd64 platform"):
        runtime.prove_oci_runtime(_contract(), config)


def test_oci_preparation_rejects_different_path_docker(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    job = tmp_path / "job.json"
    job.write_text("{}")

    def run(args, **_kwargs):
        if args[1] == "--version":
            return SimpleNamespace(stdout="v18.19.1\n" if Path(args[0]).name == "node" else "cwltool 3.2.20260720092025\n")
        if args[1] == "info":
            return SimpleNamespace(stdout=json.dumps({
                "ServerVersion": "28.0", "OSType": "linux", "Architecture": "x86_64",
            }))
        return SimpleNamespace(stdout=json.dumps([_contract().image_platform]))

    monkeypatch.setattr(runtime.subprocess, "run", run)
    monkeypatch.setattr(runtime.shutil, "which", lambda *_args, **_kwargs: str(tmp_path / "other" / "docker"))
    with pytest.raises(runtime.OciRuntimeUnavailable, match="does not resolve the pinned Docker executable"):
        runtime.prepare_oci_invocation(_contract(), config, workspace=tmp_path, job_path=job)
    assert not (tmp_path / "tool.oci.cwl").exists()


def test_oci_rejects_unbounded_or_dynamic_resource_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    for value in (4096, "$(inputs.ram)"):
        source = json.dumps({
            "cwlVersion": "v1.2", "class": "CommandLineTool", "baseCommand": "seqtool",
            "hints": [
                {"class": "DockerRequirement", "dockerPull": "example.org/lab/sequence:v1"},
                {"class": "ResourceRequirement", "ramMax": value},
            ],
            "inputs": {}, "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.fa"}}},
        })
        contract = import_cwl_oci(
            source, source_uri="https://example.org/sequence.cwl",
            image_index="example.org/lab/sequence@sha256:" + "a" * 64,
            image_platform="example.org/lab/sequence@sha256:" + "a" * 64,
            platform=ExecutionPlatform.LINUX_AMD64,
        )
        with pytest.raises(runtime.OciRuntimeUnavailable, match="resource request exceeds|static positive"):
            runtime._validated_resource_budget(contract, config)


def test_oci_cancellation_removes_container_and_preserves_bounded_failure(monkeypatch, tmp_path: Path) -> None:
    from bionodulo.execution.subprocess_runner import CommandCancelledError

    contract = _contract()
    node = runtime.bind_cwl_oci_node(import_cwl_oci_spec(contract, node_id="sequence"))()
    config = _config(tmp_path)
    monkeypatch.setattr(runtime, "configured_oci_runtime", lambda: config)
    cid = "e" * 64
    seen: list[list[str]] = []

    def prepare(_contract, _config, *, workspace, job_path):
        assert job_path.is_file()
        (workspace / "container-ids").mkdir()
        (workspace / "container-ids" / "one.cid").write_text(cid)
        return ["cwltool", "tool.cwl", str(job_path)], {
            "image_platform": contract.image_platform, "attempt_label": "a" * 32,
        }, {"PATH": "/usr/bin"}

    async def cancelled(_command, **kwargs):
        assert kwargs["replace_env"] is True
        (kwargs["cwd"] / "cwltool.stderr.log").write_text("bounded cancellation detail")
        raise CommandCancelledError("cwltool")

    def docker(args, **_kwargs):
        seen.append(list(args))
        if args[1:3] == ["container", "ls"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args[1:3] == ["container", "inspect"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps(cid) + "|" + json.dumps({
                "org.bionodulo.oci.attempt": "a" * 32,
            }) + "\n", stderr="")
        return SimpleNamespace(returncode=0, stdout=cid + "\n", stderr="")

    monkeypatch.setattr(runtime, "prepare_oci_invocation", prepare)
    monkeypatch.setattr(runtime, "_run_process", cancelled)
    monkeypatch.setattr(runtime.subprocess, "run", docker)
    context = SimpleNamespace(node_dir=tmp_path / "run", node_id="sequence", run_metadata={})
    with pytest.raises(CommandCancelledError):
        asyncio.run(node.run(context=context))
    assert any(args[1:3] == ["rm", "-f"] and args[3] == cid for args in seen)
    receipt = next((tmp_path / "run").glob("*.failure.json"))
    saved = json.loads(receipt.read_text())
    assert saved["error_type"] == "CommandCancelledError"
    assert "bounded cancellation detail" in saved["stderr_tail"]
    assert context.run_metadata["cwl_oci_failures"]["sequence"]["receipt"] == receipt.name

    def cleanup_failure(*_args):
        raise runtime.OciRuntimeUnavailable("foreign label blocks removal")

    monkeypatch.setattr(runtime, "_cleanup_oci_containers", cleanup_failure)
    second = SimpleNamespace(node_dir=tmp_path / "run_failure", node_id="sequence", run_metadata={})
    with pytest.raises(runtime.OciRuntimeUnavailable, match="cleanup failed") as failure:
        asyncio.run(node.run(context=second))
    assert isinstance(failure.value.__cause__, CommandCancelledError)
    second_receipt = next((tmp_path / "run_failure").glob("*.failure.json"))
    blocked = json.loads(second_receipt.read_text())
    assert blocked["cleanup_error"] == "foreign label blocks removal"
    assert blocked["error_type"] == "CommandCancelledError"


def test_oci_cleanup_rejects_foreign_cidfile_label(monkeypatch, tmp_path: Path) -> None:
    directory = tmp_path / "container-ids"
    directory.mkdir()
    cid = "d" * 64
    (directory / "one.cid").write_text(cid)
    seen: list[list[str]] = []

    def docker(args, **_kwargs):
        seen.append(list(args))
        if args[1:3] == ["container", "ls"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps(cid) + "|" + json.dumps({
            "org.bionodulo.oci.attempt": "b" * 32,
        }), stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", docker)
    with pytest.raises(runtime.OciRuntimeUnavailable, match="not owned by this OCI attempt"):
        runtime._cleanup_oci_containers(tmp_path, _config(tmp_path), {"PATH": "/usr/bin"}, "a" * 32)
    assert not any(args[1:3] == ["rm", "-f"] for args in seen)


def test_escaped_inline_javascript_still_requires_pinned_nodejs(tmp_path: Path) -> None:
    source = json.dumps({
        "cwlVersion": "v1.2", "class": "CommandLineTool", "baseCommand": "seqtool",
        "requirements": [{"class": "InlineJavascriptRequirement"}],
        "hints": [{"class": "DockerRequirement", "dockerPull": "example.org/lab/sequence:v1"}],
        "inputs": {}, "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.fa"}}},
    }).replace("InlineJavascriptRequirement", "InlineJavascriptRequire\\u006dent")
    assert "InlineJavascriptRequirement" not in source
    contract = import_cwl_oci(
        source, source_uri="https://example.org/sequence.cwl",
        image_index="example.org/lab/sequence@sha256:" + "a" * 64,
        image_platform="example.org/lab/sequence@sha256:" + "a" * 64,
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    config = _config(tmp_path).model_copy(update={"nodejs": None, "nodejs_sha256": None, "nodejs_version": None})
    with pytest.raises(runtime.OciRuntimeUnavailable, match="requires a pinned Node.js runtime"):
        runtime.prove_oci_runtime(contract, config)


def test_expression_without_javascript_requirement_still_requires_pinned_nodejs(tmp_path: Path) -> None:
    source = json.dumps({
        "cwlVersion": "v1.2", "class": "CommandLineTool", "baseCommand": "seqtool",
        "hints": [{"class": "DockerRequirement", "dockerPull": "example.org/lab/sequence:v1"}],
        "inputs": {"x": {"type": "string", "inputBinding": {"valueFrom": "$(self)"}}},
        "outputs": {"result": {"type": "File", "outputBinding": {"glob": "result.fa"}}},
    })
    assert "InlineJavascriptRequirement" not in source
    contract = import_cwl_oci(
        source, source_uri="https://example.org/sequence.cwl",
        image_index="example.org/lab/sequence@sha256:" + "a" * 64,
        image_platform="example.org/lab/sequence@sha256:" + "a" * 64,
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    config = _config(tmp_path).model_copy(update={"nodejs": None, "nodejs_sha256": None, "nodejs_version": None})
    with pytest.raises(runtime.OciRuntimeUnavailable, match="requires a pinned Node.js runtime"):
        runtime.prove_oci_runtime(contract, config)
