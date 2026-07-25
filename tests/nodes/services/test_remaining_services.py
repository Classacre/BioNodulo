"""Focused ownership and contract checks for the final service nodes."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.hpc.base import HPCJob
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


EXPECTED_OWNERS = {
    "cnvkit_access": "bionodulo.nodes.builtin.cnvkit_family.access",
    "cnvkit_antitarget": "bionodulo.nodes.builtin.cnvkit_family.antitarget",
    "cnvkit_target": "bionodulo.nodes.builtin.cnvkit_family.target",
    "s3_download": "bionodulo.nodes.builtin.cloud_storage_family.s3_download",
    "s3_upload": "bionodulo.nodes.builtin.cloud_storage_family.s3_upload",
    "hpc_check_status": "bionodulo.nodes.builtin.hpc_family.check_status",
    "hpc_submit_job": "bionodulo.nodes.builtin.hpc_family.submit_job",
    "http_request": "bionodulo.nodes.builtin.http_request_family.http_request",
    "python_code": "bionodulo.nodes.builtin.python_code_family.python_code",
    "ucsc_genome_browser": "bionodulo.nodes.builtin.ucsc_family.genome_browser",
}

SOURCE_COMMITS = {
    "cnvkit_access": "dd834b0b5b482f174d1dcb7c35b358087309c6b3",
    "cnvkit_antitarget": "dd834b0b5b482f174d1dcb7c35b358087309c6b3",
    "cnvkit_target": "dd834b0b5b482f174d1dcb7c35b358087309c6b3",
    "s3_download": "f656cacd23b2ceb815189546245da99857c5c3a3",
    "s3_upload": "f656cacd23b2ceb815189546245da99857c5c3a3",
    "hpc_check_status": "09c1316eabc70cdf1804fece6966a1847002b896",
    "hpc_submit_job": "09c1316eabc70cdf1804fece6966a1847002b896",
    "http_request": "26d48e0634e6ee9cdc0533996db289ce4b430177",
    "python_code": "1b80120ef26a28e065e67f89bfef873f13bdd317",
    "ucsc_genome_browser": "f665d4cc3b02924a8507b2f910eaf85eab54d433",
}


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None
    return node_class


def test_service_nodes_have_focused_source_pinned_owners() -> None:
    index = build_index()
    for node_id, owner_name in EXPECTED_OWNERS.items():
        assert index[node_id] == owner_name
        node_class = _node_class(node_id)
        assert node_class.__module__ == owner_name
        assert node_class.GIT_COMMIT == SOURCE_COMMITS[node_id]


def test_compatibility_facades_export_the_focused_classes() -> None:
    facades = {
        "cnvkit": ("CNVkitAccessNode", "cnvkit_access"),
        "cloud_storage": ("S3DownloadNode", "s3_download"),
        "hpc": ("HPCCheckStatusNode", "hpc_check_status"),
        "http_request": ("HTTPRequestNode", "http_request"),
        "python_code": ("PythonCodeNode", "python_code"),
        "ucsc": ("UCSCGenomeBrowserNode", "ucsc_genome_browser"),
    }
    for module_name, (class_name, node_id) in facades.items():
        facade = importlib.import_module(f"bionodulo.nodes.builtin.{module_name}")
        assert getattr(facade, class_name) is _node_class(node_id)


def test_cnvkit_commands_follow_upstream_optional_flag_semantics() -> None:
    antitarget = _node_class("cnvkit_antitarget")
    target = _node_class("cnvkit_target")

    antitarget_command = antitarget.render_command(
        {"targets_file": "capture.bed", "output": "/work/anti"}
    )
    assert "--min-size" not in antitarget_command
    assert antitarget_command[:3] == ["cnvkit.py", "antitarget", "capture.bed"]

    target_command = target.render_command(
        {"input_file": "capture with spaces.bed", "output": "/work/target"}
    )
    assert target_command[:3] == ["cnvkit.py", "target", "capture with spaces.bed"]
    assert "--avg-size" not in target_command
    assert "./capture.bed" not in target_command


@pytest.mark.asyncio
async def test_s3_download_fails_if_aws_exits_zero_without_an_artifact(tmp_path: Path) -> None:
    node = _node_class("s3_download")()

    async def fake_run_command(_command: list[str], cwd: str) -> dict[str, Any]:
        assert cwd == str(tmp_path / "s3_download")
        return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="did not create"):
        await node.run(
            bucket="analysis-bucket",
            key="runs/result.vcf.gz",
            local_path=str(tmp_path / "result.vcf.gz"),
            context=SimpleNamespace(node_dir=tmp_path, run_command=fake_run_command),
        )


def test_s3_metadata_command_redacts_customer_keys() -> None:
    from bionodulo.nodes.builtin.cloud_storage_family.adapter import redacted_command

    assert redacted_command(
        ["aws", "s3", "cp", "a", "b", "--sse-c-key", "secret", "--only-show-errors"]
    ) == ["aws", "s3", "cp", "a", "b", "--sse-c-key", "[REDACTED]", "--only-show-errors"]


@pytest.mark.asyncio
async def test_hpc_nodes_validate_and_fail_closed_without_an_adapter() -> None:
    submit = _node_class("hpc_submit_job")()
    status = _node_class("hpc_check_status")()

    assert submit.VALIDATE_INPUTS({"workflow_json": "{}", "scheduler": "lsf"}) == (
        "scheduler must be one of: slurm, pbs, sge"
    )
    assert status.VALIDATE_INPUTS({"job_id": "--all", "scheduler": "slurm"}) == (
        "job_id contains unsupported scheduler characters"
    )
    with pytest.raises(RuntimeError, match="configured context.hpc_adapter"):
        await status.run(job_id="1234", scheduler="slurm")


@pytest.mark.asyncio
async def test_hpc_nodes_return_typed_adapter_results() -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class Adapter:
        async def submit(self, **kwargs: Any) -> str:
            calls.append(("submit", kwargs))
            return "1234"

        async def status(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(("status", kwargs))
            return {"state": "running", "queue": "compute"}

    context = SimpleNamespace(hpc_adapter=Adapter())
    submit_result = await _node_class("hpc_submit_job")().run(
        workflow_json=json.dumps({"nodes": [], "edges": []}),
        scheduler="slurm",
        context=context,
    )
    status_result = await _node_class("hpc_check_status")().run(
        job_id="1234",
        scheduler="slurm",
        context=context,
    )

    assert submit_result == ("1234",)
    assert status_result == ("RUNNING", {"state": "RUNNING", "queue": "compute"})
    assert [name for name, _kwargs in calls] == ["submit", "status"]


@pytest.mark.asyncio
async def test_standard_executor_bridges_existing_hpc_backends(tmp_path: Path) -> None:
    calls: list[tuple[str, Any]] = []

    class Backend:
        scheduler = "slurm"

        def generate_job_script(self, **kwargs: Any) -> str:
            calls.append(("generate", kwargs))
            return f"#!/bin/bash\n{kwargs['commands'][0]}\n"

        async def submit_job(self, script_path: Path, **kwargs: Any) -> HPCJob:
            calls.append(("submit_job", {"script_path": script_path, **kwargs}))
            assert script_path.is_file()
            assert "bionodulo.execution.hpc_job_runner" in script_path.read_text(encoding="utf-8")
            return HPCJob(job_id="4321", status="PENDING")

        async def check_status(self, job: HPCJob) -> HPCJob:
            calls.append(("check_status", job))
            job.status = "RUNNING"
            job.metadata = {"queue": "compute"}
            return job

    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=registry,
        hpc_backend=Backend(),
    )
    submit_workflow = {
        "nodes": [
            {
                "id": "submit",
                "type": "hpc_submit_job",
                "params": {
                    "workflow_json": json.dumps({"nodes": [], "edges": []}),
                    "scheduler": "slurm",
                    "partition": "compute",
                    "nodes": 2,
                    "account": "research-project",
                },
                "outputs": {"job_id": {}},
            }
        ],
        "edges": [],
    }
    submit_result = await executor.execute("hpc-submit", submit_workflow, force=True)

    assert submit_result["status"] == "completed"
    assert submit_result["outputs"]["submit"] == {"job_id": "4321"}
    generated = calls[0][1]
    assert generated["scheduler"] == "slurm"
    assert generated["nodes"] == 2
    assert generated["account"] == "research-project"
    status_workflow = {
        "nodes": [
            {
                "id": "status",
                "type": "hpc_check_status",
                "params": {"job_id": "4321", "scheduler": "slurm"},
                "outputs": {"status": {}, "details": {}},
            }
        ],
        "edges": [],
    }
    status_result = await executor.execute("hpc-status", status_workflow, force=True)

    assert status_result["status"] == "completed"
    assert status_result["outputs"]["status"]["status"] == "RUNNING"
    assert status_result["outputs"]["status"]["details"]["metadata"] == {"queue": "compute"}
    assert [name for name, _value in calls] == ["generate", "submit_job", "check_status"]


@pytest.mark.asyncio
async def test_hpc_backend_adapter_rejects_scheduler_mismatches(tmp_path: Path) -> None:
    class PBSBackend:
        scheduler = "pbs"

        def generate_job_script(self, **_kwargs: Any) -> str:
            raise AssertionError("mismatched backend must not generate a script")

        async def submit_job(self, _script_path: Path) -> HPCJob:
            raise AssertionError("mismatched backend must not submit a job")

    context = SimpleNamespace(
        hpc_backend=PBSBackend(),
        node_dir=tmp_path,
        run_id="run",
        node_id="submit",
    )
    with pytest.raises(RuntimeError, match="node requested 'slurm'.*backend is 'pbs'"):
        await _node_class("hpc_submit_job")().run(
            workflow_json=json.dumps({"nodes": [], "edges": []}),
            scheduler="slurm",
            context=context,
        )


def test_hpc_scheduler_scripts_encode_supported_resources(tmp_path: Path) -> None:
    from bionodulo.hpc.pbs import PBSBackend
    from bionodulo.hpc.sge import SGEBackend
    from bionodulo.hpc.slurm import SLURMBackend

    slurm = SLURMBackend().generate_job_script(
        ["echo ok"],
        output_dir=tmp_path,
        scheduler="slurm",
        nodes=2,
        cpus=8,
        memory_mb=32768,
        account="project-a",
    )
    assert "#SBATCH --nodes=2" in slurm
    assert "#SBATCH --account=project-a" in slurm

    pbs = PBSBackend().generate_job_script(
        ["echo ok"],
        output_dir=tmp_path,
        scheduler="pbs",
        nodes=2,
        cpus=8,
        memory_mb=32768,
        account="project-a",
    )
    assert "#PBS -l select=2:ncpus=8:mem=32768mb" in pbs
    assert "#PBS -A project-a" in pbs

    sge = SGEBackend().generate_job_script(
        ["echo ok"],
        output_dir=tmp_path,
        scheduler="sge",
        nodes=1,
        account="project-a",
    )
    assert "#$ -A project-a" in sge
    with pytest.raises(ValueError, match="does not support multi-node"):
        SGEBackend().generate_job_script(
            ["echo ok"], output_dir=tmp_path, scheduler="sge", nodes=2
        )


@pytest.mark.asyncio
async def test_http_request_preserves_binary_bytes_and_redacts_response_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("http_request")
    module = importlib.import_module(node_class.__module__)

    class Response:
        status_code = 200
        headers = {"content-type": "application/octet-stream", "set-cookie": "session=secret"}
        content = b"\x00\xffartifact"
        text = "unused"
        url = "https://example.test/file"

    async def fake_request(**_kwargs: Any) -> Response:
        return Response()

    monkeypatch.setattr(module, "_request", fake_request)
    result = await node_class().run(
        url="https://example.test/file",
        method="GET",
        context=SimpleNamespace(node_dir=tmp_path),
    )

    body_path = Path(result["outputs"]["response_body"])
    assert body_path.suffix == ".bin"
    assert body_path.read_bytes() == b"\x00\xffartifact"
    assert result["outputs"]["metadata"]["headers"]["set-cookie"] == "[REDACTED]"
    assert node_class.VALIDATE_INPUTS({"url": "https://example.test", "timeout": 301}) == (
        "timeout must be between 1 and 300"
    )


def test_python_code_declares_the_exact_sandbox_package() -> None:
    node_class = _node_class("python_code")
    assert node_class.REQUIRED_EXECUTABLES == ["python", "bwrap"]
    assert node_class.REQUIRED_CONDA_PACKAGES == ["python", "bubblewrap", "numpy", "pandas"]
    assert node_class.SANDBOX_VERSION == "bubblewrap 0.11.2"


@pytest.mark.asyncio
async def test_http_request_fails_closed_when_selected_auth_is_missing() -> None:
    node = _node_class("http_request")()
    with pytest.raises(ValueError, match="requires a bearer token"):
        await node.run(
            url="https://example.test/resource",
            method="GET",
            auth_mode="bearer",
            bearer_token="",
        )


@pytest.mark.asyncio
async def test_ucsc_rejects_provider_error_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module(_node_class("ucsc_genome_browser").__module__)

    class Response:
        def json(self) -> dict[str, str]:
            return {"error": "unknown genome"}

    async def fake_request(*_args: Any, **_kwargs: Any) -> Response:
        return Response()

    monkeypatch.setattr(module, "_request", fake_request)
    with pytest.raises(RuntimeError, match="unknown genome"):
        await module._request_json("getData/sequence", {"genome": "missing"})
