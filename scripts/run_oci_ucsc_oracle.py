"""Run one pinned UCSC CWL image against a tiny independent FASTA oracle.

This is an opt-in isolated audit command, not an app integration or a general
container scheduler. The image must already be cached at its exact digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bionodulo.nodes.contract.cwl_oci import import_cwl_oci
from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.cwl_oci_runtime import (
    CwlOciRuntimeConfig, OciRuntimeUnavailable, _cleanup_oci_containers,
    prepare_oci_invocation,
)
from scripts.oci_twobit_oracle import decode_twobit


EXPECTED_SEQUENCES = {"chrA": "ACGTACGTNNNNACGT", "chrB": "TTGCAANNCC"}
EXPECTED_DESCRIPTOR = "ucscuserapps/ucsc-fa-to-twobit.cwl"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resolution-report", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--cwltool", type=Path, required=True)
    parser.add_argument("--docker", type=Path, required=True)
    parser.add_argument("--nodejs", type=Path, required=True)
    parser.add_argument("--nodejs-version", required=True)
    args = parser.parse_args(argv)
    report = json.loads(args.resolution_report.read_text(encoding="utf-8"))
    record = next(item for item in report["records"] if item["descriptor"] == EXPECTED_DESCRIPTOR)
    if record["oci_status"] != "oci_source_only_unverified":
        parser.error("UCSC descriptor has no immutable OCI resolution receipt")
    if args.evidence_root.exists():
        parser.error("evidence root must be new to preserve every attempt")
    source = args.source.read_bytes()
    if "sha256:" + hashlib.sha256(source).hexdigest() != record["source_sha256"]:
        parser.error("source descriptor differs from pinned cohort")
    resolution = record["resolution"]
    contract = import_cwl_oci(
        source, source_uri=record["contract"]["source_uri"],
        image_index=resolution["image_index"], image_platform=resolution["image_platform"],
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    fixture = args.fixture.read_bytes()
    if fixture != b">chrA\nACGTACGTNNNNACGT\n>chrB\nTTGCAANNCC\n":
        parser.error("fixture bytes differ from the independently authored oracle")
    root = args.evidence_root.resolve()
    root.mkdir(parents=True, mode=0o700)
    input_path = root / "tiny.fa"
    input_path.write_bytes(fixture)
    job = root / "job.json"
    job.write_text(json.dumps({"fasta_file": {"class": "File", "path": str(input_path)}}), encoding="utf-8")
    config = CwlOciRuntimeConfig(
        cwltool=args.cwltool, cwltool_sha256=_sha256(args.cwltool),
        cwltool_version="3.2.20260720092025",
        docker=args.docker, docker_sha256=_sha256(args.docker),
        nodejs=args.nodejs, nodejs_sha256=_sha256(args.nodejs), nodejs_version=args.nodejs_version,
    )
    command, runtime_receipt, environment = prepare_oci_invocation(contract, config, workspace=root, job_path=job)
    if "external_schema_not_loaded" in contract.inspection.unfulfilled_hints:
        command.insert(1, "--skip-schemas")
    try:
        completed = subprocess.run(command, cwd=root, env=environment, capture_output=True, timeout=180)
        (root / "cwltool.stdout.json").write_bytes(completed.stdout)
        (root / "cwltool.stderr.log").write_bytes(completed.stderr)
    except subprocess.TimeoutExpired as error:
        (root / "cwltool.stdout.json").write_bytes((error.stdout or b"")[:16 * 1024 * 1024])
        (root / "cwltool.stderr.log").write_bytes((error.stderr or b"")[-64 * 1024:])
        (root / "failure.json").write_text(json.dumps({
            "error_type": "TimeoutExpired", "timeout_seconds": 180,
            "source_sha256": contract.source_sha256,
            "image_platform": contract.image_platform,
            "runtime": runtime_receipt,
        }, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError("direct OCI oracle exceeded its 180-second timeout") from error
    finally:
        try:
            runtime_receipt["container_cleanup_count"] = str(len(_cleanup_oci_containers(
                root, config, environment, runtime_receipt["attempt_label"],
            )))
        except (OSError, ValueError, subprocess.SubprocessError, OciRuntimeUnavailable) as cleanup_error:
            (root / "cleanup-failure.json").write_text(json.dumps({
                "error_type": type(cleanup_error).__name__,
                "error": str(cleanup_error)[:4096],
                "attempt_label": runtime_receipt["attempt_label"],
            }, indent=2) + "\n", encoding="utf-8")
            raise
    if completed.returncode != 0:
        raise RuntimeError(f"cwltool container execution failed with exit {completed.returncode}")
    result = json.loads(completed.stdout)
    output = result["twobit_file"]
    location = output.get("path", output.get("location"))
    if not isinstance(location, str):
        raise RuntimeError("cwltool did not return a local 2bit output path")
    parsed = urlsplit(location)
    output_path = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(location)
    if output_path.is_symlink() or not output_path.is_file() or not output_path.resolve().is_relative_to((root / "engine-output").resolve()):
        raise RuntimeError("2bit output is absent or escapes the isolated output directory")
    decoded = decode_twobit(output_path.read_bytes())
    if decoded != EXPECTED_SEQUENCES:
        raise AssertionError(f"2bit biological oracle mismatch: {decoded!r}")
    receipt = {
        "verification": "independent_fixture_passed",
        "source_descriptor": EXPECTED_DESCRIPTOR,
        "source_sha256": contract.source_sha256,
        "source_docker_pull": contract.source_docker_pull,
        "runtime": runtime_receipt,
        "input_sha256": _sha256(input_path),
        "output_sha256": _sha256(output_path),
        "decoded_sequences": decoded,
        "command": command,
        "cwltool_exit_code": completed.returncode,
        "scope": "One tiny authored FASTA through pinned cwltool and a digest-cached local container; no app queue proof",
    }
    (root / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verification": receipt["verification"], "output_sha256": receipt["output_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
