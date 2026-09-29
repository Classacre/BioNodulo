#!/usr/bin/env python
"""Run a samtools operation chain in a pinned container and check output honesty.

Each step uses the node's **own** ``render_command`` output, executed in one
immutable digest-pinned image with a shared mounted workspace so the chain can
pass artifacts forward exactly as a workflow would.

For every step this records, and then checks:

* the rendered argv (both as rendered on this host and POSIX-normalised);
* the node's ``PLAN_OUTPUTS`` claims;
* which files the command **actually** created;
* whether every planned output exists afterwards.

That last comparison is the point. A node whose plan promises a file its command
never writes is not output-honest, and on the real executor a missing planned
output fails the run. This harness surfaces the mismatch as data instead of
letting a successful exit code imply success.

Usage:
    python scripts/run_samtools_chain.py \
        --image quay.io/biocontainers/samtools:1.23.1--ha83d96e_0 \
        --digest sha256:23cda3... \
        --fixture tests/nodes/samtools/fixtures/mini_unsorted.sam \
        --receipt-dir reports/run-receipts/samtools-chain
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

WORKDIR = "/work"
OUT = f"{WORKDIR}/out"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)).replace("\\", "/"): sha256_file(p)
            for p in root.rglob("*") if p.is_file()}


def to_posix(argument: str) -> tuple[str, bool]:
    if "\\" in argument and "work" in argument:
        return argument.replace("\\", "/"), True
    return argument, False


def _to_host(value: object, work: Path) -> object:
    """Map a container path under /work back to its host path."""
    if not isinstance(value, str) or not value.startswith(WORKDIR):
        return value
    return str(work / value[len(WORKDIR):].lstrip("/"))


def _to_container(value: object, work: Path) -> object:
    """Map a host path under the work dir to its container path."""
    if not isinstance(value, str):
        return value
    root = str(work.resolve()).replace("\\", "/")
    normalized = value.replace("\\", "/")
    if normalized.startswith(root):
        return WORKDIR + normalized[len(root):]
    return value


def run_step(registry, node_id: str, inputs: dict, work: Path, image: str, digest: str,
             out_label: str | None = None) -> dict:
    node_class = registry.get(node_id)
    if node_class is None:
        raise SystemExit(f"unknown node: {node_id}")

    # A distinct label per step keeps repeated node types (two sorts) from
    # overwriting each other.
    label = out_label or node_id
    run_root = work / "out"
    (run_root / label).mkdir(parents=True, exist_ok=True)

    # Chain inputs arrive as container paths for convenience, but the node hooks do
    # HOST filesystem work (PLAN_OUTPUTS creates directories, PREPARE_EXECUTION
    # stages or hard-links files) while render_command must emit CONTAINER paths.
    # Translate across that boundary rather than pretending the two coincide.
    inputs_host = {key: _to_host(value, work) for key, value in inputs.items()}
    inputs_host["output"] = str(run_root / label)

    # PLAN_OUTPUTS declares filenames under the node id; remap them into this
    # step's labelled directory.
    planned = [run_root / label / Path(p).name
               for p in node_class.PLAN_OUTPUTS(inputs_host, run_root)]

    before = snapshot(work)

    # PREPARE_EXECUTION runs BEFORE render_command and may materialise a planned
    # output. samtools_index hard-links the source BAM to its first planned output
    # here, so skipping this hook would make an honest node look like it never
    # produced the file.
    node_class.PREPARE_EXECUTION(inputs_host, planned)

    inputs_render = {key: _to_container(value, work) for key, value in inputs_host.items()}
    argv_raw = list(node_class.render_command(inputs_render))
    argv: list[str] = []
    rewrites = []
    for argument in argv_raw:
        converted, changed = to_posix(argument)
        if changed:
            rewrites.append({"rendered_on_host": argument, "used_in_container": converted})
        argv.append(converted)

    started = now()
    result = subprocess.run([
        "docker", "run", "--rm", "--network", "none", "--cpus", "1", "--memory", "2048m",
        "-v", f"{str(work.resolve()).replace(chr(92), '/')}:/work", "-w", WORKDIR,
        "--entrypoint", "sh", f"{image}@{digest}", "-c", 'exec "$@"', "sh", *argv,
    ], capture_output=True, text=True, timeout=900, check=False)
    completed = now()

    # Mirror the executor's stdout capture: a node declaring STDOUT_OUTPUT_INDEX
    # writes its report to that planned output instead of to a file itself, so the
    # command legitimately creates nothing on disk.
    stdout_index = getattr(node_class, "STDOUT_OUTPUT_INDEX", None)
    stdout_captured_to = None
    if isinstance(stdout_index, int) and 0 <= stdout_index < len(planned):
        target = planned[stdout_index]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.stdout, encoding="utf-8")
        stdout_captured_to = str(target.relative_to(work)).replace("\\", "/")

    after = snapshot(work)
    created = sorted(set(after) - set(before))
    # Compare by filename inside the step's own output directory. PLAN_OUTPUTS
    # names paths after the node id while a labelled step writes elsewhere, so a
    # raw path comparison would report false mismatches.
    step_prefix = f"out/{label}/"
    created_in_step = {Path(name).name for name in created if name.startswith(step_prefix)}
    planned_names = [Path(path).name for path in planned]
    missing = [name for name in planned_names if name not in created_in_step]

    return {
        "node_id": node_id,
        "step_label": label,
        "inputs": inputs,
        "rendered_command": argv,
        "rendered_command_as_rendered_on_host": argv_raw,
        "platform_path_rewrites": rewrites,
        "planned_output_filenames": planned_names,
        "stdout_captured_to": stdout_captured_to,
        "created_files_relative": created,
        "planned_outputs_missing_after_run": missing,
        "output_honest": not missing,
        "status": "completed" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "started_at_utc": started,
        "completed_at_utc": completed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--image", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    args = parser.parse_args()

    work = (args.receipt_dir / "work").resolve()
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    (work / "out").mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.fixture, work / args.fixture.name)

    registry = NodeRegistry()
    sam = f"{WORKDIR}/{args.fixture.name}"
    # Each step writes into its own output directory, matching the executor contract.
    sorted_bam = f"{OUT}/01_sort/sorted_bam.bam"
    collated = f"{OUT}/05_collate/name_collated_bam.bam"
    fixmate = f"{OUT}/06_fixmate/fixmate_bam.bam"
    sorted_after_fixmate = f"{OUT}/07_sort_after_fixmate/sorted_bam.bam"

    # Composition note: samtools markdup requires COORDINATE-SORTED input, so
    # fixmate cannot feed it directly. A second sort is required between them.
    # This was established by experiment, not assumption.
    steps = [
        ("samtools_sort", {"alignment": sam, "threads": 1, "memory_per_thread": "32M"}, "01_sort"),
        ("samtools_index", {"bam": sorted_bam, "threads": 1}, "02_index"),
        ("samtools_flagstat", {"bam": sorted_bam, "threads": 1}, "03_flagstat"),
        ("samtools_view", {"alignment": sorted_bam, "threads": 1}, "04_view"),
        ("samtools_collate", {"bam": sam, "threads": 1}, "05_collate"),
        ("samtools_fixmate", {"bam": collated, "threads": 1}, "06_fixmate"),
        ("samtools_sort", {"alignment": fixmate, "threads": 1, "memory_per_thread": "32M"},
         "07_sort_after_fixmate"),
        ("samtools_markdup", {"bam": sorted_after_fixmate, "threads": 1}, "08_markdup"),
    ]

    results = []
    for node_id, inputs, label in steps:
        step = run_step(registry, node_id, inputs, work, args.image, args.digest, label)
        results.append(step)
        flag = "ok " if step["status"] == "completed" else "FAIL"
        honest = "honest" if step["output_honest"] else f"MISSING {step['planned_outputs_missing_after_run']}"
        print(f"[{flag}] {label:22s} {node_id:20s} exit={step['exit_code']} "
              f"outputs={len(step['created_files_relative'])} {honest}", flush=True)

    version = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--entrypoint", "sh",
         f"{args.image}@{args.digest}", "-c", "samtools --version | head -2"],
        capture_output=True, text=True, timeout=180, check=False)

    artifacts = [{"path": name, "sha256": digest} for name, digest in sorted(snapshot(work).items())]
    receipt = {
        "schema_version": 1,
        "kind": "digest_pinned_container_chain",
        "image": args.image,
        "image_digest": args.digest,
        "tool_version": version.stdout.strip(),
        "network": "none",
        "fixture": {"name": args.fixture.name, "sha256": sha256_file(args.fixture)},
        "generated_at_utc": now(),
        "steps": results,
        "summary": {
            "steps": len(results),
            "completed": sum(1 for r in results if r["status"] == "completed"),
            "failed": sum(1 for r in results if r["status"] != "completed"),
            "output_honest": sum(1 for r in results if r["output_honest"]),
            "output_dishonest": [r["node_id"] for r in results if not r["output_honest"]],
        },
        "artifacts": artifacts,
        "scope": (
            "Each node's own render_command argv executed in one immutable image with a shared "
            "workspace. Proves the declared commands run and whether planned outputs materialise. "
            "Does not prove scientific correctness of any analysis."
        ),
    }
    args.receipt_dir.mkdir(parents=True, exist_ok=True)
    (args.receipt_dir / "receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], indent=2))


if __name__ == "__main__":
    main()
