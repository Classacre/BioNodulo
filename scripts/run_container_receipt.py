#!/usr/bin/env python
"""Execute a builtin node's real rendered command inside a digest-pinned container.

Why this exists: the project declares ``linux-64``/``linux-aarch64`` targets, and
its bioinformatics nodes shell out to Linux binaries that do not exist on a
Windows host. Rather than fabricate a receipt or claim a run that never happened,
this harness takes the node's **own** ``render_command`` output — the real
contract-derived argv — and executes it in an immutable, digest-pinned Linux
image, then retains everything needed to audit the claim:

* the exact argv the node rendered
* the image reference **and** its resolved ``sha256`` digest, re-verified after
  the run so the receipt cannot silently drift to a different image
* the tool version reported from inside that image
* fixture and output SHA-256 hashes
* exit status, stdout, stderr, UTC start/end and wall time

What this proves: the node's declared command works, in a pinned environment, on
a real fixture, and produced these exact bytes. What it does **not** prove: that
the output is scientifically correct (that needs an independent oracle), or that
the cloud queue provisions an identical environment.

Usage:
    python scripts/run_container_receipt.py \
        --node samtools_sort \
        --image quay.io/biocontainers/samtools:1.23.1--ha83d96e_0 \
        --digest sha256:23cda33a3a42125872766df9aaf1d2db67cdb8c85314b793465188435af31ba6 \
        --input-key alignment --fixture fixtures/mini.sam \
        --inputs-json '{"threads": 1, "memory_per_thread": "32M"}' \
        --receipt-dir reports/run-receipts/samtools-sort
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bionodulo.nodes.registry import NodeRegistry  # noqa: E402

CONTAINER_WORKDIR = "/work"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def docker(args: list[str], *, timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True,
                          timeout=timeout, check=False)


def resolve_digest(image: str) -> str | None:
    result = docker(["inspect", "--format", "{{index .RepoDigests 0}}", image], timeout=60)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def run(node_id: str, image: str, digest: str, fixture: Path, input_key: str,
        inputs_json: str, receipt_dir: Path, extra_argv: list[str] | None = None,
        assets: list[Path] | None = None) -> dict:
    registry = NodeRegistry()
    node_class = registry.get(node_id)
    if node_class is None:
        raise SystemExit(f"unknown node id: {node_id}")

    work = receipt_dir / "work"
    out_dir = work / "out"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    staged = work / fixture.name
    shutil.copy2(fixture, staged)
    staged_assets = []
    for asset in assets or []:
        target = work / asset.name
        if asset.is_dir():
            shutil.copytree(asset, target)
            files = sorted(target.rglob("*"))
        else:
            shutil.copy2(asset, target)
            files = [target]
        staged_assets.extend({"path": str(p.relative_to(work)).replace("\\", "/"),
                              "sha256": sha256_file(p)} for p in files if p.is_file())

    inputs: dict[str, object] = json.loads(inputs_json) if inputs_json else {}
    inputs[input_key] = f"{CONTAINER_WORKDIR}/{fixture.name}"
    # Mirror CommandNode.run: PLAN_OUTPUTS receives the base output directory,
    # while render_command receives its node-specific child.
    inputs["output"] = f"{CONTAINER_WORKDIR}/out/{node_id}"

    planned = node_class.PLAN_OUTPUTS(inputs, out_dir)
    # The node renders its own argv. On this host `pathlib.Path` is a WindowsPath,
    # so path arguments come out with backslashes ("\work\out\tmp"). A Linux worker
    # would render the same arguments with forward slashes. Both forms are retained
    # so the difference is visible rather than silently normalised away.
    rendered_raw = list(node_class.render_command(inputs))
    rendered: list[str] = []
    path_rewrites: list[dict[str, str]] = []
    for argument in rendered_raw:
        if "\\" in argument and CONTAINER_WORKDIR.lstrip("/") in argument:
            rewritten = argument.replace("\\", "/")
            path_rewrites.append({"rendered_on_host": argument, "used_in_container": rewritten})
            rendered.append(rewritten)
        else:
            rendered.append(argument)
    if extra_argv:
        rendered = [*rendered, *extra_argv]

    started = now()
    docker_args = [
        "run", "--rm", "--network", "none",
        "--cpus", "1", "--memory", "2048m",
        "-v", f"{str(work.resolve()).replace(chr(92), '/')}:/work", "-w", CONTAINER_WORKDIR,
        "--entrypoint", "sh", f"{image}@{digest}",
        "-c", 'exec "$@"', "sh", *rendered,
    ]
    result = subprocess.run(["docker", *docker_args], capture_output=True,
                            timeout=900, check=False)
    stdout_path = work / "stdout.bin"
    if result.stdout:
        stdout_path.write_bytes(result.stdout)
        if node_class.STDOUT_OUTPUT_INDEX is not None:
            planned[node_class.STDOUT_OUTPUT_INDEX].write_bytes(result.stdout)
    completed = now()

    missing_outputs = [str(path) for path in planned if not path.exists()]
    output_verification_error = None
    if result.returncode == 0 and not missing_outputs:
        try:
            node_class.VERIFY_OUTPUTS(inputs, planned)
        except Exception as exc:  # noqa: BLE001
            output_verification_error = f"{type(exc).__name__}: {exc}"

    digest_after = resolve_digest(image)
    version_arg = "version" if rendered[0] in {"unikmer", "taxonkit"} else "--version"
    version = docker(["run", "--rm", "--network", "none", "--entrypoint", "sh",
                      f"{image}@{digest}", "-c",
                      f"{rendered[0]} {version_arg} 2>&1 | head -5"], timeout=180)

    artifacts = []
    for path in sorted(work.rglob("*")):
        if path.is_file():
            artifacts.append({
                "path": str(path.relative_to(receipt_dir)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })

    receipt = {
        "schema_version": 1,
        "node_id": node_id,
        "node_class": f"{node_class.__module__}.{node_class.__name__}",
        "execution": {
            "kind": "digest_pinned_container",
            "image": image,
            "image_digest_expected": digest,
            "image_digest_observed_after_run": digest_after,
            "digest_stable": digest_after == f"{image.split(':')[0]}@{digest}" or digest_after == digest,
            "container_workdir": CONTAINER_WORKDIR,
            "network": "none",
            "cpus": 1,
            "memory": "2048m",
            "host_platform": sys.platform,
        },
        "rendered_command": rendered,
        "rendered_command_as_rendered_on_this_host": rendered_raw,
        "platform_path_rewrites": path_rewrites,
        "platform_path_rewrite_note": (
            "render_command() builds output paths with pathlib.Path, so on Windows the argv "
            "contains backslash paths. A linux-64 worker renders the same arguments with forward "
            "slashes. The rewritten form was executed; the raw form is retained for comparison."
        ),
        "rendered_command_argv0_in_container": rendered[0],
        "inputs": inputs,
        "planned_outputs": [str(p) for p in planned],
        "tool_version_stdout": version.stdout.strip(),
        "status": ("completed" if result.returncode == 0 and not missing_outputs
                   and not output_verification_error else "failed"),
        "exit_code": result.returncode,
        "missing_planned_outputs": missing_outputs,
        "output_verification_error": output_verification_error,
        "stdout": result.stdout.decode("utf-8", errors="replace") if not result.stdout.startswith(b"\x1f\x8b") else "[gzip bytes retained in work/stdout.bin]",
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "stdout_bytes": len(result.stdout),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
        "started_at_utc": started,
        "completed_at_utc": completed,
        "fixture": {
            "name": fixture.name,
            "sha256": sha256_file(fixture),
            "bytes": fixture.stat().st_size,
            "source": str(fixture).replace("\\", "/"),
        },
        "additional_staged_assets": staged_assets,
        "artifacts": artifacts,
        "artifact_count": len(artifacts),
        "scope": (
            "The node's own render_command argv executed in an immutable digest-pinned image. "
            "Proves the declared command runs in a pinned Linux environment and produced these "
            "bytes. Does not prove scientific correctness; that requires the independent oracle."
        ),
    }
    receipt_dir.mkdir(parents=True, exist_ok=True)
    (receipt_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--node", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--input-key", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--inputs-json", default="{}")
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--extra-argv", nargs="*", default=None)
    parser.add_argument("--asset", type=Path, action="append", default=[])
    args = parser.parse_args()
    receipt = run(args.node, args.image, args.digest, args.fixture, args.input_key,
                  args.inputs_json, args.receipt_dir, args.extra_argv, args.asset)
    print(json.dumps({
        "node_id": receipt["node_id"], "status": receipt["status"],
        "exit_code": receipt["exit_code"],
        "rendered_command": receipt["rendered_command"],
        "tool_version": receipt["tool_version_stdout"].splitlines()[:1],
        "digest_stable": receipt["execution"]["digest_stable"],
        "artifacts": receipt["artifact_count"],
        "stderr": receipt["stderr"][:300],
    }, indent=2))


if __name__ == "__main__":
    main()
