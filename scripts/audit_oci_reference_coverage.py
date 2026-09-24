"""Account for source-only OCI candidates without calling them executable.

The complete pinned CWL coverage ledger is the denominator. Optional image
resolution reads public registry metadata only; it never pulls image layers or
uses a Docker daemon. No bio.tools identity is synthesized for source-only
descriptors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from bionodulo.nodes.contract.cwl_oci import (
    CwlOciContract, CwlOciImportError, declared_docker_pull, import_cwl_oci, import_cwl_oci_spec,
)
from bionodulo.nodes.contract.cwl_reference import CwlReferenceImportError, _UniqueKeyLoader, inspect_reference_document
from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.generation.oci import OciResolutionError, resolve_oci_pull

import yaml  # type: ignore[import-untyped]


def audit_oci_coverage(
    coverage: dict[str, Any],
    repository: Path,
    *,
    resolve_descriptors: frozenset[str] = frozenset(),
    resolve_all: bool = False,
    platform: ExecutionPlatform = ExecutionPlatform.LINUX_AMD64,
    verify_revision: bool = False,
) -> dict[str, Any]:
    entries = coverage.get("candidates")
    if not isinstance(entries, list):
        raise ValueError("source coverage must contain a complete candidate list")
    descriptors = [item.get("descriptor") for item in entries if isinstance(item, dict)]
    if len(descriptors) != len(entries) or len(set(descriptors)) != len(entries):
        raise ValueError("source coverage has missing or duplicate descriptors")
    unknown = resolve_descriptors - set(descriptors)
    if unknown:
        raise ValueError(f"requested OCI resolution is outside source denominator: {sorted(unknown)}")
    if resolve_all and resolve_descriptors:
        raise ValueError("--resolve-all and --resolve-descriptor are mutually exclusive")
    root = repository.resolve(strict=True)
    if coverage.get("source", {}).get("tracked_cwl_descriptors") not in (None, len(entries)):
        raise ValueError("source coverage denominator differs from candidate list")
    if verify_revision:
        revision = coverage.get("source", {}).get("revision")
        actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if actual != revision:
            raise ValueError("upstream checkout differs from pinned CWL revision")
    records: list[dict[str, Any]] = []
    resolution_cache: dict[tuple[str, ExecutionPlatform], Any] = {}
    for item in entries:
        descriptor = item["descriptor"]
        if not isinstance(descriptor, str) or not descriptor.endswith(".cwl"):
            raise ValueError("source coverage descriptor is invalid")
        candidate_path = root / descriptor
        if candidate_path.is_symlink():
            raise ValueError(f"source descriptor is a symlink: {descriptor}")
        path = candidate_path.resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"source descriptor escapes repository: {descriptor}")
        # The pinned ledger hashes Git blobs. A Windows checkout can transparently
        # convert their line endings while still reporting a clean worktree.
        raw = (subprocess.check_output(["git", "-C", str(root), "show", f"HEAD:{descriptor}"])
               if verify_revision else path.read_bytes())
        source_sha = "sha256:" + hashlib.sha256(raw).hexdigest()
        if source_sha != item.get("source_sha256"):
            raise ValueError(f"source descriptor differs from pinned coverage: {descriptor}")
        record: dict[str, Any] = {
            "descriptor": descriptor,
            "source_sha256": source_sha,
            "prior_status": item.get("status"),
            "prior_reason": item.get("reason"),
        }
        if item.get("reason") != "no machine-readable SoftwareRequirement":
            record["oci_status"] = "outside_missing_software_cohort"
            records.append(record)
            continue
        try:
            document = yaml.load(raw.decode("utf-8"), Loader=_UniqueKeyLoader)
            if type(document) is not dict:
                raise CwlOciImportError("CWL document is not an object")
            pull = declared_docker_pull(document)
            record["source_docker_pull"] = pull
            inspect_reference_document(document, allow_container_requirement=True)
        except (UnicodeError, yaml.YAMLError, CwlOciImportError, CwlReferenceImportError) as error:
            record["oci_status"] = "oci_profile_unsupported"
            record["oci_reason"] = str(error).split("\n", 1)[0]
            records.append(record)
            continue
        if not resolve_all and descriptor not in resolve_descriptors:
            record["oci_status"] = "oci_image_unresolved"
            records.append(record)
            continue
        cache_key = (pull, platform)
        record["resolution_reused"] = cache_key in resolution_cache
        if cache_key not in resolution_cache:
            try:
                resolution_cache[cache_key] = resolve_oci_pull(pull, platform=platform)
            except (OciResolutionError, HTTPError, URLError, TimeoutError, OSError) as error:
                # Network exception text may contain token URLs; retain only its type.
                if isinstance(error, OciResolutionError):
                    reason = str(error).split("\n", 1)[0][:500]
                elif isinstance(error, HTTPError):
                    reason = f"registry HTTP {error.code}"
                else:
                    reason = f"registry network error: {type(error).__name__}"
                resolution_cache[cache_key] = reason
        try:
            resolution = resolution_cache[cache_key]
            if isinstance(resolution, str):
                raise OciResolutionError(resolution)
            contract = import_cwl_oci(
                raw,
                source_uri=item["source_uri"],
                image_index=resolution.image_index,
                image_platform=resolution.image_platform,
                platform=platform,
            )
        except (OciResolutionError, CwlOciImportError, ValueError) as error:
            record["oci_status"] = "oci_resolution_failed"
            record["oci_reason"] = str(error).split("\n", 1)[0]
        else:
            record["oci_status"] = "oci_source_only_unverified"
            record["resolution"] = resolution.model_dump(mode="json")
            record["contract"] = contract.model_dump(mode="json")
        records.append(record)
    return {
        "schema_version": 1,
        "source_revision": coverage.get("source", {}).get("revision"),
        "source_denominator": len(entries),
        "counts": dict(Counter(item["oci_status"] for item in records)),
        "registry_resolution": {
            "mode": "all_structurally_eligible" if resolve_all else "selected_descriptors",
            "platform": platform.value,
            "unique_source_pulls_attempted": len(resolution_cache),
            "descriptor_attempts": sum("resolution_reused" in item for item in records),
        },
        "records": records,
        "boundary": "OCI source contracts are not registered executable nodes; a digest and proven local container runtime are required.",
    }


def project_oci_catalog(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project every resolved source contract through the app guard, offline."""

    records = report.get("records")
    if (report.get("schema_version") != 1 or not isinstance(records, list)
            or len(records) != report.get("source_denominator")
            or report.get("registry_resolution", {}).get("mode") != "all_structurally_eligible"):
        raise ValueError("projection requires a complete --resolve-all coverage report")
    if len({item.get("descriptor") for item in records}) != len(records):
        raise ValueError("projection report has duplicate descriptors")
    if dict(Counter(item.get("oci_status") for item in records)) != report.get("counts"):
        raise ValueError("projection report status counts differ from records")
    specs: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for record in records:
        if record["oci_status"] != "oci_source_only_unverified":
            continue
        descriptor = record["descriptor"]
        if not isinstance(descriptor, str) or not descriptor.endswith(".cwl"):
            raise ValueError("resolved descriptor is invalid")
        source_sha = record["source_sha256"]
        if not isinstance(source_sha, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", source_sha):
            raise ValueError("resolved source digest is invalid")
        stem = re.sub(r"[^a-z0-9]+", "_", descriptor[:-4].lower()).strip("_")[:80].rstrip("_")
        suffix = hashlib.sha256(f"{descriptor}\0{source_sha}".encode()).hexdigest()[:12]
        node_id = f"generated_oci_{stem}_{suffix}"
        outcome: dict[str, Any] = {
            "descriptor": descriptor, "source_sha256": source_sha, "node_id": node_id,
        }
        contract = CwlOciContract.model_validate_json(json.dumps(record["contract"]))
        if contract.source_sha256 != source_sha:
            raise ValueError(f"projection contract source differs from coverage: {descriptor}")
        resolution = record["resolution"]
        if (contract.image_index != resolution["image_index"]
                or contract.image_platform != resolution["image_platform"]):
            raise ValueError(f"projection contract image differs from resolution: {descriptor}")
        try:
            spec = import_cwl_oci_spec(contract, node_id=node_id)
        except (CwlOciImportError, ValueError) as error:
            outcome["projection_status"] = "denied"
            outcome["reason"] = str(error)[:2000]
        else:
            outcome["projection_status"] = "source_only_unverified"
            specs.append(spec.model_dump(mode="json"))
        outcomes.append(outcome)
    counts = dict(Counter(item["projection_status"] for item in outcomes))
    catalog = {"schema_version": 1, "specs": specs}
    ledger = {
        "schema_version": 1,
        "source_revision": report.get("source_revision"),
        "source_denominator": report["source_denominator"],
        "resolved_source_contracts": len(outcomes),
        "counts": counts,
        "records": outcomes,
        "boundary": "Generated catalog data is source-only and unverified; local runtime readiness and execution proof are separate gates.",
    }
    return catalog, ledger


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes((json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path)
    parser.add_argument("--repository", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--resolution-report", type=Path, help="project an existing full-cohort report offline")
    parser.add_argument("--catalog-output", type=Path, help="write data-only app catalog for accepted projections")
    parser.add_argument("--projection-output", type=Path, help="write every app projection acceptance or denial")
    parser.add_argument("--resolve-descriptor", action="append", default=[])
    parser.add_argument("--resolve-all", action="store_true", help="attempt every structurally eligible descriptor")
    args = parser.parse_args(argv)
    if bool(args.catalog_output) != bool(args.projection_output):
        parser.error("--catalog-output and --projection-output must be supplied together")
    if args.resolution_report:
        if args.coverage or args.repository or args.output or args.resolve_all or args.resolve_descriptor:
            parser.error("--resolution-report cannot be combined with source audit options")
        if not args.catalog_output:
            parser.error("--resolution-report requires --catalog-output and --projection-output")
        result = json.loads(args.resolution_report.read_text(encoding="utf-8"))
    else:
        if not args.coverage or not args.repository or not args.output:
            parser.error("source audit requires --coverage, --repository, and --output")
        coverage = json.loads(args.coverage.read_text(encoding="utf-8"))
        result = audit_oci_coverage(
            coverage, args.repository, resolve_descriptors=frozenset(args.resolve_descriptor),
            resolve_all=args.resolve_all, verify_revision=True,
        )
        _write_json(args.output, result)
    summary: dict[str, Any] = {"counts": result["counts"]}
    if args.output:
        summary["output"] = str(args.output)
    if args.catalog_output:
        catalog, ledger = project_oci_catalog(result)
        _write_json(args.catalog_output, catalog)
        _write_json(args.projection_output, ledger)
        summary["projection_counts"] = ledger["counts"]
        summary["catalog_output"] = str(args.catalog_output)
        summary["projection_output"] = str(args.projection_output)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
