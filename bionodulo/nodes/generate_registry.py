"""Generate executable nodes from explicit bio.tools-linked upstream CWL.

The default operation only scans. --realize resolves a deterministic cohort's
exact software requirements on native Linux, retaining failures and actual
locks. Generated nodes remain scientifically unverified until independently
tested; a successful installation is not execution evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import TypeAdapter

from bionodulo.nodes.contract.environments import PixiEnvironment
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.generation.acquisition import read_verified_snapshot, scan_repository, select_cohort
from bionodulo.nodes.generation.environments import (
    DEFAULT_CHANNELS,
    INCOMPLETE_MARKER,
    RECEIPT_NAME,
    CondaPrefixReceipt,
    recover_conda_environment,
    verify_conda_prefix,
)


_EXACT_REQUEST_RE = re.compile(r"^(?P<name>[a-z0-9][a-z0-9._-]{0,127})==(?P<version>[^=,\s]+)$")


class EnvironmentUnavailableError(RuntimeError):
    """A no-install generation pass has no complete verified environment."""


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".generation-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _json_object(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError(f"generation receipt is missing, unsafe, or too large: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"generation receipt must be a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".generation-evidence-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def retain_prior_generation_evidence(source: Path, output: Path) -> dict[str, object]:
    """Copy bounded prior-run evidence so receipt-only output remains self-contained."""

    source_root = source.expanduser().absolute()
    if not source_root.is_dir() or source_root.is_symlink():
        raise ValueError("--receipts-from must be a nonsymlink generation directory")
    source_root = source_root.resolve(strict=True)
    required = (source_root / "coverage.json",)
    if any(not path.is_file() or path.is_symlink() for path in required):
        raise ValueError("--receipts-from has no safe prior coverage receipt")
    selected: list[Path] = list(required)
    engine = source_root / "engine.json"
    if engine.is_file() and not engine.is_symlink():
        selected.append(engine)
    for directory in ("runs", "environments"):
        root = source_root / directory
        if root.exists() and (not root.is_dir() or root.is_symlink()):
            raise ValueError(f"--receipts-from has an unsafe {directory} evidence directory")
        if root.is_dir():
            selected.extend(sorted(root.glob("*.json")))
    if not any(path.parent.name == "runs" for path in selected):
        raise ValueError("--receipts-from has no prior generation run receipt")
    if len(selected) > 10_000:
        raise ValueError("prior generation evidence exceeds the 10000-file limit")

    evidence_root = output / "acquisition-evidence"
    entries: list[dict[str, object]] = []
    total = 0
    for path in selected:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"prior generation evidence is missing or unsafe: {path}")
        resolved = path.resolve(strict=True)
        if os.path.commonpath((str(source_root), str(resolved))) != str(source_root):
            raise ValueError(f"prior generation evidence escapes its source directory: {path}")
        relative = resolved.relative_to(source_root)
        content = resolved.read_bytes()
        total += len(content)
        if total > 256 * 1024 * 1024:
            raise ValueError("prior generation evidence exceeds the 256 MiB limit")
        value = json.loads(content)
        if type(value) is not dict:
            raise ValueError(f"prior generation evidence must be a JSON object: {relative}")
        destination = evidence_root / relative
        _atomic_bytes(destination, content)
        entries.append(
            {
                "path": relative.as_posix(),
                "sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
        )
    manifest = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_generation_directory": str(source_root),
        "files": entries,
    }
    manifest_path = evidence_root / "manifest.json"
    atomic_json(manifest_path, manifest)
    return {
        "manifest": "acquisition-evidence/manifest.json",
        "manifest_sha256": _sha256_file(manifest_path),
        "files": len(entries),
        "bytes": total,
    }


def preflight_exact_versions(
    requests: tuple[str, ...],
    *,
    channels: tuple[str, ...] = DEFAULT_CHANNELS,
    cache: dict[tuple[str, str], frozenset[str] | None] | None = None,
    receipts: list[dict[str, object]] | None = None,
) -> None:
    """Reject conclusively absent exact pins; API uncertainty falls back to solving."""

    selected_cache = {} if cache is None else cache
    for exact_request in requests:
        match = _EXACT_REQUEST_RE.fullmatch(exact_request)
        if match is None:
            raise ValueError(f"availability preflight requires an exact package pin: {exact_request!r}")
        package, version = match.group("name"), match.group("version")
        conclusive = 0
        available = False
        for channel_url in channels:
            owner = channel_url.rstrip("/").rsplit("/", 1)[-1]
            cache_key = (owner, package)
            if cache_key not in selected_cache:
                api_url = f"https://api.anaconda.org/package/{quote(owner, safe='')}/{quote(package, safe='')}"
                request = Request(
                    api_url,
                    headers={"Accept": "application/json", "User-Agent": "BioNodulo-CWL-generation/1"},
                )
                checked_at = datetime.now(timezone.utc).isoformat()
                payload: bytes | None = None
                try:
                    with urlopen(request, timeout=20) as response:
                        payload = response.read(16 * 1024 * 1024 + 1)
                    if len(payload) > 16 * 1024 * 1024:
                        raise ValueError("Anaconda package metadata exceeds 16 MiB")
                    document = json.loads(payload)
                    versions = document.get("versions") if type(document) is dict else None
                    if not isinstance(versions, list) or any(type(item) is not str for item in versions):
                        raise ValueError("Anaconda package metadata has no exact version list")
                    selected_cache[cache_key] = frozenset(versions)
                    if receipts is not None:
                        receipts.append(
                            {
                                "api_url": api_url,
                                "channel": owner,
                                "package": package,
                                "checked_at": checked_at,
                                "status": "200",
                                "response_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                                "observed_versions": sorted(set(versions)),
                            }
                        )
                except HTTPError as error:
                    selected_cache[cache_key] = frozenset() if error.code == 404 else None
                    if receipts is not None:
                        receipts.append(
                            {
                                "api_url": api_url,
                                "channel": owner,
                                "package": package,
                                "checked_at": checked_at,
                                "status": "404" if error.code == 404 else "uncertain",
                                "http_status": error.code,
                                "response_sha256": None,
                                "observed_versions": [],
                            }
                        )
                except (OSError, URLError, UnicodeError, json.JSONDecodeError, ValueError) as error:
                    selected_cache[cache_key] = None
                    if receipts is not None:
                        receipts.append(
                            {
                                "api_url": api_url,
                                "channel": owner,
                                "package": package,
                                "checked_at": checked_at,
                                "status": "uncertain",
                                "error_type": type(error).__name__,
                                "response_sha256": (
                                    "sha256:" + hashlib.sha256(payload).hexdigest()
                                    if payload is not None
                                    else None
                                ),
                                "observed_versions": [],
                            }
                        )
            versions = selected_cache[cache_key]
            if versions is None:
                continue
            conclusive += 1
            if version in versions:
                available = True
                break
        if not available and conclusive == len(channels):
            owners = ", ".join(channel.rstrip("/").rsplit("/", 1)[-1] for channel in channels)
            raise ValueError(f"exact package pin {exact_request!r} is absent from configured channels: {owners}")


def resume_verified_environment(
    requests: tuple[str, ...],
    *,
    prefix: Path,
    environment_path: Path,
    receipt_path: Path,
) -> tuple[PixiEnvironment, CondaPrefixReceipt] | None:
    """Reuse only a complete environment whose three receipts still agree."""

    expected_paths = (prefix, environment_path, receipt_path, prefix / RECEIPT_NAME)
    present = tuple(path.exists() or path.is_symlink() for path in expected_paths)
    if not any(present):
        return None
    if not all(present):
        raise ValueError("partial prior environment realization cannot be resumed")
    environment = TypeAdapter(PixiEnvironment).validate_json(environment_path.read_bytes())
    if tuple(item.as_string() for item in environment.packages) != tuple(sorted(requests)):
        raise ValueError("prior environment requests do not match this generation group")
    output_receipt = CondaPrefixReceipt(**_json_object(receipt_path))
    prefix_receipt = CondaPrefixReceipt(**_json_object(prefix / RECEIPT_NAME))
    verified = verify_conda_prefix(environment, prefix, require_receipt=True)
    if output_receipt.to_dict() != prefix_receipt.to_dict():
        raise ValueError("stored output and prefix environment receipts do not match")
    reproducible_fields = (
        "environment_id",
        "environment_digest",
        "platform",
        "prefix",
        "lock_digest",
        "conda_metadata_sha256",
        "installed_inventory_sha256",
        "verified_file_hashes",
        "unhashed_paths",
    )
    if any(getattr(output_receipt, field) != getattr(verified, field) for field in reproducible_fields):
        raise ValueError("prior environment receipt identity or inventory differs from fresh prefix verification")
    if Path(verified.prefix).resolve() != prefix.resolve():
        raise ValueError("prior environment receipt refers to a different prefix")
    for suffix, expected_digest in (
        ("stdout", output_receipt.solver_stdout_sha256),
        ("stderr", output_receipt.solver_stderr_sha256),
    ):
        if expected_digest is None:
            continue
        log_path = prefix.parent / f".{prefix.name}.micromamba-create.{suffix}.log"
        if not log_path.is_file() or log_path.is_symlink() or _sha256_file(log_path) != expected_digest:
            raise ValueError(f"stored solver {suffix} log does not match its environment receipt")
    return environment, output_receipt


def prior_environment_prefix(receipt_path: Path, *, fallback: Path) -> Path:
    """Reuse a recorded nonrelocatable prefix; place only new solves in fallback.

    This selects a path, not a trusted realization. The caller must still
    verify the lock, both receipts, every installed path and solver log hashes.
    """
    if not receipt_path.exists() and not receipt_path.is_symlink():
        return fallback
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("prior environment receipt must be a regular nonsymlink file")
    value = _json_object(receipt_path).get("prefix")
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError("prior environment receipt must name an absolute prefix")
    return Path(value)


def prior_environment_paths(
    source: Path,
    group_key: str,
) -> tuple[Path, Path]:
    """Select direct receipts, falling back only when the direct pair is absent."""

    direct = (
        source / "environments" / f"{group_key}.json",
        source / "environments" / f"{group_key}.receipt.json",
    )
    if any(os.path.lexists(path) for path in direct):
        return direct
    retained = (
        source / "acquisition-evidence" / "environments" / f"{group_key}.json",
        source / "acquisition-evidence" / "environments" / f"{group_key}.receipt.json",
    )
    if any(os.path.lexists(path) for path in retained):
        return retained
    return direct


def resume_or_recover_environment(
    requests: tuple[str, ...],
    *,
    prefix: Path,
    environment_path: Path,
    receipt_path: Path,
    recover_incomplete: bool,
    micromamba: Path | None,
) -> tuple[tuple[PixiEnvironment, CondaPrefixReceipt] | None, bool]:
    """Resume complete receipts or strictly recover an exclusive partial install."""

    try:
        return (
            resume_verified_environment(
                requests,
                prefix=prefix,
                environment_path=environment_path,
                receipt_path=receipt_path,
            ),
            False,
        )
    except (OSError, ValueError):
        marker = prefix.parent / f".{prefix.name}{INCOMPLETE_MARKER}"
        incomplete_only = (
            prefix.is_dir()
            and not prefix.is_symlink()
            and os.path.lexists(marker)
            and not any(
                os.path.lexists(path)
                for path in (environment_path, receipt_path, prefix / RECEIPT_NAME)
            )
        )
        if not recover_incomplete or not incomplete_only or micromamba is None:
            raise
        return (
            recover_conda_environment(
                requests,
                prefix=prefix,
                micromamba=micromamba,
            ),
            True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--revision", required=True, help="Full immutable Git commit")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--realize", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="0 scans/generates all; positive values cap deterministic cohort")
    parser.add_argument("--prefix-root", type=Path)
    parser.add_argument("--micromamba", type=Path)
    parser.add_argument("--cwltool", type=Path)
    parser.add_argument("--receipts-from", type=Path, help="Reuse verified environment receipts from another run")
    parser.add_argument("--no-install", action="store_true", help="Never solve/install missing environments")
    parser.add_argument("--recover-incomplete", action="store_true",
                        help="Reverify reserved incomplete prefixes and publish receipts only if every check passes")
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    if args.realize and not all((args.prefix_root, args.cwltool)):
        parser.error("--realize requires --prefix-root and --cwltool")
    if args.realize and not args.no_install and args.micromamba is None:
        parser.error("installing during --realize requires --micromamba")
    if args.no_install and (not args.realize or args.receipts_from is None):
        parser.error("--no-install requires --realize and --receipts-from")
    if args.receipts_from is not None and not args.realize:
        parser.error("--receipts-from requires --realize")
    if args.recover_incomplete and (not args.realize or args.micromamba is None):
        parser.error("--recover-incomplete requires --realize and --micromamba for lock inspection")
    records, manifest = read_verified_snapshot(args.snapshot, args.manifest)
    candidates, source = scan_repository(args.repository, revision=args.revision, source_url=args.source_url, registry=records)
    cohort = select_cohort(candidates, args.limit)
    chosen = {item.descriptor for item in cohort}
    for item in candidates:
        if item.status == "eligible" and item.descriptor not in chosen:
            item.status = "not_attempted_budget"
    specs: list[NodeSpec] = []
    prefixes: dict[str, str] = {}
    environments: dict[tuple[str, ...], tuple[PixiEnvironment, CondaPrefixReceipt] | Exception] = {}
    args.output.mkdir(parents=True, exist_ok=True)
    prior_generation_evidence = (
        retain_prior_generation_evidence(args.receipts_from, args.output)
        if args.receipts_from is not None
        else None
    )
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:12]
    run_started_at = datetime.now(timezone.utc).isoformat()
    run_status = "in_progress"
    run_completed_at: str | None = None
    engine_receipt = None
    availability_cache: dict[tuple[str, str], frozenset[str] | None] = {}
    availability_receipts: list[dict[str, object]] = []

    def publish() -> None:
        coverage = {
            "schema_version": 1, "source": source,
            "registry": {key: manifest.get(key) for key in ("source", "completed_at", "records", "sha256", "license")},
            "selection": {"rule": "round-robin across sorted exact accessions, sorted descriptor paths within each accession",
                          "limit": args.limit, "selected": [item.descriptor for item in cohort]},
            "counts": dict(Counter(item.status for item in candidates)),
            "registry_identity_coverage": len({item.accession for item in candidates if item.registry_record_sha256}),
            "generated_accessions": sorted({item.accession for item in candidates
                                            if item.status == "generated_unverified" and item.accession is not None}),
            "candidates": [item.to_dict() for item in candidates],
        }
        atomic_json(args.output / "coverage.json", coverage)
        atomic_json(args.output / "catalog.json", {"schema_version": 1, "specs": [item.model_dump(mode="json") for item in specs]})
        atomic_json(args.output / "prefixes.json", prefixes)
        atomic_json(
            args.output / "runs" / f"{run_id}.json",
            {
                "schema_version": 1,
                "run_id": run_id,
                "started_at": run_started_at,
                "status": run_status,
                "completed_at": run_completed_at,
                "realize": args.realize,
                "recover_incomplete": args.recover_incomplete,
                "limit": args.limit,
                "source": source,
                "registry": coverage["registry"],
                "counts": coverage["counts"],
                "candidates": coverage["candidates"],
                "engine": engine_receipt,
                "availability": availability_receipts,
                "prior_generation_evidence": prior_generation_evidence,
            },
        )

    publish()
    if not args.realize:
        run_status = "completed"
        run_completed_at = datetime.now(timezone.utc).isoformat()
        publish()
        print(json.dumps({"output": str(args.output), "counts": dict(Counter(item.status for item in candidates))}))
        return 0
    from bionodulo.nodes.contract.cwl_reference import import_cwl_reference
    from bionodulo.nodes.generation.environments import solve_conda_environment
    engine_path = args.cwltool.expanduser().absolute()
    if not engine_path.is_file() or engine_path.is_symlink():
        parser.error("--cwltool must be an existing nonsymlink regular file")
    engine_result = subprocess.run([str(engine_path), "--version"], capture_output=True, text=True, check=True, timeout=30)
    # cwltool prefixes its version with the executable path; retain the exact
    # distribution version independently of where the environment was mounted.
    engine_version = engine_result.stdout.strip().split()[-1]
    engine_receipt = {
        "executable": str(engine_path.resolve()),
        "version": engine_version,
        "version_output": engine_result.stdout.strip(),
        "sha256": _sha256_file(engine_path),
        "size_bytes": engine_path.stat().st_size,
        "dependency_lock_status": "external_environment_not_byte_locked",
    }
    atomic_json(args.output / "engine.json", engine_receipt)
    for candidate in cohort:
        group_key = hashlib.sha256(json.dumps(candidate.requests).encode()).hexdigest()[:16]
        print(json.dumps({"descriptor": candidate.descriptor, "stage": "realizing", "requests": candidate.requests}), flush=True)
        try:
            if candidate.requests not in environments:
                try:
                    environment_path = args.output / "environments" / f"{group_key}.json"
                    receipt_path = args.output / "environments" / f"{group_key}.receipt.json"
                    source_environment_path, source_receipt_path = (
                        prior_environment_paths(args.receipts_from, group_key)
                        if args.receipts_from is not None
                        else (environment_path, receipt_path)
                    )
                    prefix = args.prefix_root / group_key
                    if args.receipts_from is not None:
                        prefix = prior_environment_prefix(source_receipt_path, fallback=prefix)
                    try:
                        resumed, recovered = resume_or_recover_environment(
                            candidate.requests,
                            prefix=prefix,
                            environment_path=source_environment_path,
                            receipt_path=source_receipt_path,
                            recover_incomplete=args.recover_incomplete,
                            micromamba=args.micromamba,
                        )
                    except (OSError, ValueError) as error:
                        if args.no_install:
                            raise EnvironmentUnavailableError(
                                f"environment receipts for group {group_key} are not reusable: {error}"
                            ) from error
                        raise
                    if recovered:
                        candidate.details["recovered_incomplete_prefix"] = str(prefix)
                    if resumed is None and args.no_install:
                        raise EnvironmentUnavailableError(
                            f"no complete verified environment receipts for group {group_key}"
                        )
                    if resumed is None:
                        preflight_exact_versions(
                            candidate.requests,
                            cache=availability_cache,
                            receipts=availability_receipts,
                        )
                    environment, receipt = (
                        resumed
                        if resumed is not None
                        else solve_conda_environment(candidate.requests, prefix=prefix, micromamba=args.micromamba)
                    )
                    environments[candidate.requests] = (environment, receipt)
                    atomic_json(environment_path, environment.model_dump(mode="json"))
                    atomic_json(receipt_path, receipt.to_dict())
                except Exception as error:
                    environments[candidate.requests] = error
                    raise
            value = environments[candidate.requests]
            if isinstance(value, Exception):
                if isinstance(value, EnvironmentUnavailableError):
                    raise value
                raise RuntimeError(f"same package group failed earlier: {value}")
            environment, receipt = value
            candidate.environment_id = environment.environment_id
            raw = (args.repository / candidate.descriptor).read_bytes()
            if "sha256:" + hashlib.sha256(raw).hexdigest() != candidate.source_sha256:
                raise ValueError("descriptor changed after acquisition")
            if any(value is None for value in (candidate.node_id, candidate.accession,
                                               candidate.biotools_uri, candidate.primary_package,
                                               candidate.primary_version)):
                raise ValueError(f"eligible descriptor has incomplete tool identity: {candidate.descriptor}")
            assert candidate.node_id is not None and candidate.accession is not None
            assert candidate.biotools_uri is not None and candidate.primary_package is not None
            assert candidate.primary_version is not None
            spec = import_cwl_reference(raw, node_id=candidate.node_id, source_uri=candidate.source_uri,
                biotools_accession=candidate.accession, biotools_uri=candidate.biotools_uri,
                environment=environment, primary_package=candidate.primary_package,
                primary_package_version=candidate.primary_version, engine_version=engine_version)
            specs.append(spec)
            prefixes[environment.environment_id] = receipt.prefix
            candidate.status = "generated_unverified"
            candidate.details["contract_digest"] = spec.contract_digest()
        except Exception as error:
            if isinstance(error, EnvironmentUnavailableError):
                candidate.status = "environment_unavailable"
            else:
                candidate.status = "realization_failed" if candidate.environment_id is None else "generation_failed"
            candidate.reason = f"{type(error).__name__}: {error}"
        publish()
        print(json.dumps({"descriptor": candidate.descriptor, "status": candidate.status, "reason": candidate.reason}), flush=True)
    run_status = "completed"
    run_completed_at = datetime.now(timezone.utc).isoformat()
    publish()
    return 0 if specs else 1


if __name__ == "__main__":
    raise SystemExit(main())
