from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_s3_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    info = registry.object_info()

    assert info["s3_upload"]["display_name"] == "S3 Upload"
    assert info["s3_upload"]["category"] == "storage"
    assert info["s3_upload"]["output_name"] == ["s3_uri", "metadata"]
    assert info["s3_upload"]["required_executables"] == ["aws"]
    assert info["s3_upload"]["required_conda_packages"] == ["awscli"]
    assert info["s3_upload"]["requires_external_tools"] is True
    assert info["s3_download"]["display_name"] == "S3 Download"
    assert info["s3_download"]["category"] == "storage"
    assert info["s3_download"]["output_name"] == ["local_path", "metadata"]
    assert info["s3_download"]["output"] == ["FILE", "JSON"]
    assert info["s3_download"]["required_executables"] == ["aws"]
    assert info["s3_download"]["required_conda_packages"] == ["awscli"]
    assert info["s3_download"]["requires_external_tools"] is True


def test_s3_upload_renders_aws_cli_command_preview(tmp_path: Path) -> None:
    node_class = _node_class("s3_upload")
    local_file = tmp_path / "results.vcf.gz"
    local_file.write_text("vcf", encoding="utf-8")

    command = node_class.render_command(
        {
            "local_path": str(local_file),
            "bucket": "analysis-bucket",
            "key": "runs/sample 1/results.vcf.gz",
            "storage_class": "STANDARD_IA",
            "profile": "lab",
            "region": "ap-southeast-2",
            "extra_args": "--acl bucket-owner-full-control",
        }
    )

    assert command == [
        "aws",
        "s3",
        "cp",
        str(local_file),
        "s3://analysis-bucket/runs/sample 1/results.vcf.gz",
        "--storage-class",
        "STANDARD_IA",
        "--profile",
        "lab",
        "--region",
        "ap-southeast-2",
        "--acl",
        "bucket-owner-full-control",
    ]


def test_s3_download_renders_aws_cli_command_preview(tmp_path: Path) -> None:
    node_class = _node_class("s3_download")
    destination = tmp_path / "results.vcf.gz"

    command = node_class.render_command(
        {
            "bucket": "analysis-bucket",
            "key": "runs/sample-1/results.vcf.gz",
            "local_path": str(destination),
            "profile": "lab",
            "region": "us-west-2",
            "extra_args": "--only-show-errors",
        }
    )

    assert command == [
        "aws",
        "s3",
        "cp",
        "s3://analysis-bucket/runs/sample-1/results.vcf.gz",
        str(destination),
        "--profile",
        "lab",
        "--region",
        "us-west-2",
        "--only-show-errors",
    ]


@pytest.mark.asyncio
async def test_s3_upload_executes_aws_cli_and_writes_metadata(tmp_path: Path) -> None:
    node_class = _node_class("s3_upload")
    local_file = tmp_path / "summary.tsv"
    local_file.write_text("sample\treads\nS1\t10\n", encoding="utf-8")
    commands: list[dict[str, Any]] = []

    async def fake_run_command(cmd: list[str], cwd: str) -> dict[str, Any]:
        commands.append({"cmd": list(cmd), "cwd": cwd})
        return {"returncode": 0, "stdout": "upload complete\n", "stderr": ""}

    context = SimpleNamespace(node_dir=tmp_path, run_command=fake_run_command)

    result = await node_class().run(
        local_path=str(local_file),
        bucket="analysis-bucket",
        key="reports/summary.tsv",
        storage_class="STANDARD",
        profile="",
        region="",
        extra_args="",
        context=context,
    )

    metadata_path = Path(result["outputs"]["metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert result["outputs"]["s3_uri"] == "s3://analysis-bucket/reports/summary.tsv"
    assert metadata_path == tmp_path / "s3_upload" / "upload_metadata.json"
    assert metadata == {
        "operation": "upload",
        "aws_cli_version": "2.36.2",
        "bucket": "analysis-bucket",
        "key": "reports/summary.tsv",
        "s3_uri": "s3://analysis-bucket/reports/summary.tsv",
        "local_path": str(local_file),
        "command": [
            "aws",
            "s3",
            "cp",
            str(local_file),
            "s3://analysis-bucket/reports/summary.tsv",
            "--storage-class",
            "STANDARD",
        ],
        "returncode": 0,
        "stdout": "upload complete\n",
        "stderr": "",
    }
    assert commands == [
        {
            "cmd": [
                "aws",
                "s3",
                "cp",
                str(local_file),
                "s3://analysis-bucket/reports/summary.tsv",
                "--storage-class",
                "STANDARD",
            ],
            "cwd": str(tmp_path / "s3_upload"),
        }
    ]


@pytest.mark.asyncio
async def test_s3_download_executes_aws_cli_and_writes_metadata(tmp_path: Path) -> None:
    node_class = _node_class("s3_download")
    destination = tmp_path / "downloads" / "summary.tsv"
    commands: list[dict[str, Any]] = []

    async def fake_run_command(cmd: list[str], cwd: str) -> dict[str, Any]:
        commands.append({"cmd": list(cmd), "cwd": cwd})
        transfer_path = Path(cmd[4])
        transfer_path.parent.mkdir(parents=True, exist_ok=True)
        transfer_path.write_text("sample\treads\nS1\t10\n", encoding="utf-8")
        return {"returncode": 0, "stdout": "download complete\n", "stderr": ""}

    context = SimpleNamespace(node_dir=tmp_path, run_command=fake_run_command)

    result = await node_class().run(
        bucket="analysis-bucket",
        key="reports/summary.tsv",
        local_path=str(destination),
        profile="",
        region="",
        extra_args="",
        context=context,
    )

    metadata_path = Path(result["outputs"]["metadata"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert result["outputs"]["local_path"] == str(destination)
    assert destination.read_text(encoding="utf-8") == "sample\treads\nS1\t10\n"
    assert metadata_path == tmp_path / "s3_download" / "download_metadata.json"
    assert metadata == {
        "operation": "download",
        "aws_cli_version": "2.36.2",
        "transport": "aws-cli",
        "bucket": "analysis-bucket",
        "key": "reports/summary.tsv",
        "s3_uri": "s3://analysis-bucket/reports/summary.tsv",
        "local_path": str(destination),
        "size_bytes": 19,
        "command": [
            "aws",
            "s3",
            "cp",
            "s3://analysis-bucket/reports/summary.tsv",
            str(destination.with_name(".summary.tsv.bionodulo-part")),
        ],
        "returncode": 0,
        "stdout": "download complete\n",
        "stderr": "",
    }
    assert commands == [
        {
            "cmd": [
                "aws",
                "s3",
                "cp",
                "s3://analysis-bucket/reports/summary.tsv",
                str(destination.with_name(".summary.tsv.bionodulo-part")),
            ],
            "cwd": str(tmp_path / "s3_download"),
        }
    ]


def test_s3_upload_validates_required_inputs(tmp_path: Path) -> None:
    node_class = _node_class("s3_upload")

    assert node_class.VALIDATE_INPUTS({"local_path": "", "bucket": "bucket", "key": "key"}) == (
        "S3 Upload requires local_path"
    )
    assert node_class.VALIDATE_INPUTS({"local_path": str(tmp_path / "missing.txt"), "bucket": "bucket", "key": "key"}) == (
        "S3 Upload local_path does not exist"
    )
    assert node_class.VALIDATE_INPUTS({"local_path": str(tmp_path), "bucket": "bucket", "key": "key"}) == (
        "S3 Upload local_path must be a file"
    )
    assert node_class.VALIDATE_INPUTS({"local_path": __file__, "bucket": "", "key": "key"}) == (
        "S3 Upload requires bucket"
    )
    assert node_class.VALIDATE_INPUTS({"local_path": __file__, "bucket": "bucket", "key": ""}) == (
        "S3 Upload requires key"
    )


def test_s3_download_validates_required_inputs() -> None:
    node_class = _node_class("s3_download")

    assert node_class.VALIDATE_INPUTS({"bucket": "", "key": "key", "local_path": "out.txt"}) == (
        "S3 Download requires bucket"
    )
    assert node_class.VALIDATE_INPUTS({"bucket": "bucket", "key": "", "local_path": "out.txt"}) == (
        "S3 Download requires key"
    )
    assert node_class.VALIDATE_INPUTS({"bucket": "bucket", "key": "key", "local_path": ""}) == (
        "S3 Download requires local_path"
    )


@pytest.mark.parametrize("node_id", ["s3_upload", "s3_download"])
def test_s3_nodes_reject_non_transfer_extra_args(node_id: str, tmp_path: Path) -> None:
    node_class = _node_class(node_id)
    local_path = tmp_path / "input.txt"
    local_path.write_text("data", encoding="utf-8")
    inputs = {
        "bucket": "bucket",
        "key": "key",
        "local_path": str(local_path),
        "extra_args": "--dryrun",
    }

    assert "requires one real object transfer" in str(node_class.VALIDATE_INPUTS(inputs))


@pytest.mark.asyncio
async def test_s3_download_never_accepts_a_stale_destination(tmp_path: Path) -> None:
    node = _node_class("s3_download")()
    destination = tmp_path / "result.txt"
    destination.write_text("stale", encoding="utf-8")

    async def fake_run_command(_cmd: list[str], cwd: str) -> dict[str, Any]:
        assert cwd == str(tmp_path / "s3_download")
        return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="did not create"):
        await node.run(
            bucket="bucket",
            key="result.txt",
            local_path=str(destination),
            context=SimpleNamespace(node_dir=tmp_path, run_command=fake_run_command),
        )

    assert destination.read_text(encoding="utf-8") == "stale"


@pytest.mark.asyncio
async def test_s3_upload_fails_closed_without_a_runner_returncode(tmp_path: Path) -> None:
    local_path = tmp_path / "input.txt"
    local_path.write_text("data", encoding="utf-8")

    async def fake_run_command(_cmd: list[str], cwd: str) -> dict[str, Any]:
        assert cwd == str(tmp_path / "s3_upload")
        return {"stdout": "", "stderr": ""}

    with pytest.raises(RuntimeError, match="did not report an integer return code"):
        await _node_class("s3_upload")().run(
            local_path=str(local_path),
            bucket="bucket",
            key="input.txt",
            context=SimpleNamespace(node_dir=tmp_path, run_command=fake_run_command),
        )


@pytest.mark.asyncio
async def test_s3_download_resolves_relative_paths_against_the_node_directory(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    async def fake_run_command(cmd: list[str], cwd: str) -> dict[str, Any]:
        assert cwd == str(tmp_path / "s3_download")
        commands.append(list(cmd))
        Path(cmd[4]).write_text("fresh", encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await _node_class("s3_download")().run(
        bucket="bucket",
        key="result.txt",
        local_path="downloads/result.txt",
        context=SimpleNamespace(node_dir=tmp_path, run_command=fake_run_command),
    )

    expected = (tmp_path / "s3_download" / "downloads" / "result.txt").resolve()
    assert result["outputs"]["local_path"] == str(expected)
    assert expected.read_text(encoding="utf-8") == "fresh"
    assert commands[0][4] == str(expected.with_name(".result.txt.bionodulo-part"))


def test_s3_environment_metadata_is_declared() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["aws"] == "awscli"
    assert PACKAGE_MIN_VERSIONS["awscli"] == "2.36.2"
    assert workflow_to_packages({"nodes": [{"id": "upload", "type": "s3_upload"}]}, registry) == ["awscli"]
    assert workflow_to_packages({"nodes": [{"id": "download", "type": "s3_download"}]}, registry) == ["awscli"]


def test_s3_download_anonymous_adds_no_sign_request(tmp_path: Path) -> None:
    node_class = _node_class("s3_download")
    destination = tmp_path / "sgnex_run1.pod5"

    command = node_class.render_command(
        {
            "bucket": "sg-nex-data",
            "key": "data/sequencing_data_ont/fast5/example.pod5",
            "local_path": str(destination),
            "anonymous": True,
        }
    )

    assert command[:6] == [
        "aws",
        "s3",
        "cp",
        "s3://sg-nex-data/data/sequencing_data_ont/fast5/example.pod5",
        str(destination),
        "--no-sign-request",
    ]

    signed = node_class.render_command(
        {
            "bucket": "sg-nex-data",
            "key": "data/example.pod5",
            "local_path": str(destination),
            "anonymous": False,
        }
    )
    assert "--no-sign-request" not in signed


@pytest.mark.asyncio
async def test_s3_download_anonymous_https_fallback_without_aws_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hosts without the AWS CLI must still download public open-data objects.

    Field defect: OCI workers have no ``aws`` binary, so the node died with a
    bare FileNotFoundError and took the whole e4 direct-RNA leg with it.
    """
    import bionodulo.nodes.builtin.cloud_storage_family.s3_download as mod

    monkeypatch.setattr(mod.shutil, "which", lambda name: None)

    class FakeResponse:
        def __init__(self, chunks: list[bytes]) -> None:
            self._chunks = list(chunks)
            self.headers = {"Content-Length": str(sum(len(c) for c in chunks))}

        def read(self, size: int = -1) -> bytes:
            return self._chunks.pop(0) if self._chunks else b""

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    requested: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: int = 0) -> FakeResponse:
        requested["url"] = getattr(req, "full_url", req)
        return FakeResponse([b"POD5", b"data-bytes"])

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)

    node_class = _node_class("s3_download")
    destination = tmp_path / "out" / "sample.pod5"
    context = SimpleNamespace(node_dir=tmp_path, run_command=None)

    result = await node_class().run(
        bucket="sg-nex-data",
        key="data/sequencing_1/sample.pod5",
        local_path=str(destination),
        profile="",
        region="",
        extra_args="",
        context=context,
    )

    assert requested["url"] == "https://sg-nex-data.s3.amazonaws.com/data/sequencing_1/sample.pod5"
    assert destination.read_bytes() == b"POD5data-bytes"
    metadata = json.loads(Path(result["outputs"]["metadata"]).read_text(encoding="utf-8"))
    assert metadata["transport"] == "https-anonymous"
    assert metadata["size_bytes"] == len(b"POD5data-bytes")


@pytest.mark.asyncio
async def test_s3_download_anonymous_large_object_uses_parallel_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Large open-data objects must fetch as parallel ranged streams.

    A single TCP stream saturates near 15 MB/s on cross-continent paths
    (measured against the SG-NEx bucket from us-ashburn: 16 MB/s/stream
    while OCI-Melbourne reached 32 MB/s); the 467 GB campaign POD5 needs
    aws-cli-style parallelism to finish in minutes instead of hours.
    """
    import bionodulo.nodes.builtin.cloud_storage_family.s3_download as mod

    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    monkeypatch.setattr(mod, "PARALLEL_THRESHOLD_BYTES", 1024)

    blob = bytes(range(256)) * 8192  # 2 MiB fake object

    class FakeResponse:
        def __init__(self, data: bytes) -> None:
            self._data = data
            self.headers = {"Content-Length": str(len(blob))}

        def read(self, size: int = -1) -> bytes:
            data, self._data = self._data, b""
            return data

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

    ranges_requested: list[str | None] = []

    def fake_urlopen(req: Any, timeout: int = 0) -> FakeResponse:
        rng = getattr(req.headers, "get", lambda *_: None)("Range")
        ranges_requested.append(rng)
        if rng is None:
            return FakeResponse(blob)
        start_s, end_s = rng.replace("bytes=", "").split("-")
        return FakeResponse(blob[int(start_s) : int(end_s) + 1])

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)

    destination = tmp_path / "big.pod5"
    context = SimpleNamespace(node_dir=tmp_path, run_command=None)
    result = await _node_class("s3_download")().run(
        bucket="sg-nex-data",
        key="data/run1.pod5",
        local_path=str(destination),
        profile="",
        region="",
        extra_args="",
        context=context,
    )

    ranged = [r for r in ranges_requested if r]
    assert len(ranged) == mod.PARALLEL_STREAMS, "expected 8 ranged streams + 1 HEAD"
    assert destination.read_bytes() == blob, "parts must reassemble byte-exact"
    metadata = json.loads(Path(result["outputs"]["metadata"]).read_text(encoding="utf-8"))
    assert metadata["transport"] == "https-anonymous"


def test_s3_download_offloads_blocking_fetch_from_event_loop(monkeypatch, tmp_path):
    """The starvation fix: s3_download's run() is async, but the whole HTTP
    fetch (HEAD + ranged streams + reassembly) used to execute inline, parking
    the server's event loop for the entire transfer (hours on a 467 GB
    object). The fetch now runs via asyncio.to_thread; a heartbeat coroutine
    must keep ticking while a download is in flight."""
    import asyncio
    import time
    from types import SimpleNamespace

    import bionodulo.nodes.builtin.cloud_storage_family.s3_download as mod

    ticks: list[float] = []

    def slow_fetch(cls_self, url, transfer_path):
        time.sleep(0.6)  # stands in for the blocking transfer
        transfer_path.write_bytes(b"data")

    async def scenario():
        node = mod.S3DownloadNode()
        ctx = SimpleNamespace(node_dir=str(tmp_path))
        monkeypatch.setattr(mod.S3DownloadNode, "_fetch_https_anonymous", slow_fetch)
        monkeypatch.setattr(mod.shutil, "which", lambda _: None)  # force HTTPS path

        async def heartbeat():
            for _ in range(6):
                ticks.append(asyncio.get_running_loop().time())
                await asyncio.sleep(0.05)

        hb = asyncio.create_task(heartbeat())
        result = await node.run(
            context=ctx,
            bucket="example-bucket",
            key="some/object.pod5",
            local_path=str(tmp_path / "out.pod5"),
        )
        await hb
        return result

    out = asyncio.run(scenario())
    assert str(out["outputs"]["local_path"]).endswith("out.pod5")
    assert (tmp_path / "out.pod5").read_bytes() == b"data"
    # The heartbeat progressed DURING the blocking fetch rather than bunching
    # up after it completed.
    assert len(ticks) >= 4
    assert ticks[-1] - ticks[0] >= 0.15
