"""Join a pinned CWL source repository to a hash-verified bio.tools snapshot.

There are deliberately no tool-name aliases, wrapper templates or allowlists in
this module. An upstream SoftwareRequirement must supply the identity and exact
package versions. Unsupported records remain in the returned denominator.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse

import yaml

from bionodulo.nodes.import_cwl import _UniqueKeyLoader


@dataclass
class Candidate:
    descriptor: str
    source_uri: str
    source_sha256: str
    source_size_bytes: int
    status: str = "discovered"
    reason: str = ""
    accession: str | None = None
    biotools_uri: str | None = None
    registry_record_sha256: str | None = None
    primary_package: str | None = None
    primary_version: str | None = None
    requests: tuple[str, ...] = ()
    test_jobs: tuple[str, ...] = ()
    node_id: str | None = None
    environment_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative.lstrip("/")).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"source path escapes repository: {relative}")
    return path


def _load(path: Path) -> dict:
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("descriptor exceeds 4 MiB")
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    if not isinstance(value, dict):
        raise ValueError("descriptor must be a mapping")
    return value


def _identity(uri: str) -> str | None:
    parsed = urlparse(uri)
    try:
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
        or port is not None
    ):
        return None
    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if parsed.hostname == "identifiers.org" and len(parts) == 2 and parts[0] == "biotools":
        accession = parts[1]
    elif parsed.hostname in {"bio.tools", "www.bio.tools"} and len(parts) == 1:
        accession = parts[0]
    else:
        return None
    return accession if re.fullmatch(r"[A-Za-z0-9._-]+", accession) else None


def package_identity(document: dict) -> tuple[str, str, str, tuple[str, ...]]:
    """Return accession, owning package, exact version and all package pins."""
    packages: dict[str, Any] = {}
    for section in ("requirements", "hints"):
        requirements = document.get(section, {})
        if isinstance(requirements, list):
            entries = []
            for index, entry in enumerate(requirements):
                if not isinstance(entry, dict) or not isinstance(entry.get("class"), str):
                    raise ValueError(f"{section}[{index}] must be a requirement object with class")
                entries.append((entry["class"], entry))
        elif isinstance(requirements, dict):
            entries = list(requirements.items())
        else:
            raise ValueError("requirements/hints must be mappings or lists")
        for name, requirement in entries:
            if str(name).rsplit("#", 1)[-1] != "SoftwareRequirement":
                continue
            if not isinstance(requirement, dict):
                raise ValueError("SoftwareRequirement must be a mapping")
            declared_packages = requirement.get("packages")
            if isinstance(declared_packages, list):
                # CWL permits the array form as well as its package-keyed map
                # shorthand. Normalize identity metadata only; retain the
                # original descriptor for the reference engine unchanged.
                normalized = {}
                for entry in declared_packages:
                    if not isinstance(entry, dict) or not isinstance(entry.get("package"), str):
                        raise ValueError("SoftwareRequirement package list entries need a package name")
                    package = entry["package"]
                    if package in normalized:
                        raise ValueError("duplicate SoftwareRequirement package list entry")
                    normalized[package] = {key: value for key, value in entry.items() if key != "package"}
                declared_packages = normalized
            if not isinstance(declared_packages, dict):
                raise ValueError("SoftwareRequirement.packages must be a mapping or list")
            for package, value in declared_packages.items():
                if package in packages and packages[package] != value:
                    raise ValueError("conflicting software requirements")
                packages[package] = value
    if not packages:
        raise ValueError("no machine-readable SoftwareRequirement")
    identities: set[tuple[str, str, str]] = set()
    requests = []
    for name, package in sorted(packages.items()):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) or not isinstance(package, dict):
            raise ValueError("unsupported package name or definition")
        versions = package.get("version")
        if not isinstance(versions, list) or len(versions) != 1 or not isinstance(versions[0], str):
            raise ValueError(f"package {name} does not have exactly one version pin")
        version = versions[0]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+!-]*", version):
            raise ValueError(f"package {name} has a non-exact version")
        requests.append(f"{name}=={version}")
        specs = package.get("specs", [])
        if not isinstance(specs, list):
            raise ValueError("package specs must be a list")
        for uri in specs:
            accession = _identity(uri) if isinstance(uri, str) else None
            if accession:
                identities.add((accession.casefold(), name, version))
    if len(identities) != 1:
        raise ValueError(f"expected one explicit bio.tools package identity, found {len(identities)}")
    accession, name, version = next(iter(identities))
    return accession, name, version, tuple(requests)


def read_verified_snapshot(path: Path, manifest_path: Path) -> tuple[dict[str, dict], dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        type(manifest) is not dict
        or type(manifest.get("sha256")) is not str
        or re.fullmatch(r"[0-9a-f]{64}", manifest["sha256"]) is None
        or type(manifest.get("records")) is not int
        or manifest["records"] < 0
        or manifest.get("complete") is not True
    ):
        raise ValueError("registry snapshot manifest is malformed or incomplete")
    digest = hashlib.sha256()
    records: dict[str, dict] = {}
    with path.open("rb") as stream:
        for line in stream:
            digest.update(line)
            record = json.loads(line)
            if type(record) is not dict:
                raise ValueError("registry snapshot record must be an object")
            accession = record.get("biotoolsID")
            if not isinstance(accession, str) or not accession:
                raise ValueError("registry record has no bio.tools accession")
            key = accession.casefold()
            if key in records:
                raise ValueError(f"duplicate registry accession: {accession}")
            records[key] = record
    if digest.hexdigest() != manifest.get("sha256"):
        raise ValueError("registry snapshot SHA-256 does not match manifest")
    if len(records) != manifest.get("records"):
        raise ValueError("registry snapshot count/completeness does not match manifest")
    return records, manifest


def execution_profile_requests(source_requests: tuple[str, ...]) -> tuple[str, ...]:
    """Provide a pinned utility baseline for every shared native execution.

    Conda command wrappers can use POSIX file utilities without declaring the
    package themselves. Keep these utilities in the verified prefix instead of
    falling back to arbitrary host executables. This is a profile dependency,
    not a replacement or inferred alias for any upstream tool requirement.
    """
    # A baseCommand can itself be a shell launcher without declaring CWL's
    # ShellCommandRequirement. Apply the baseline uniformly to avoid per-tool
    # wrapper inspection or an incomplete shell-feature heuristic.
    requirement = "coreutils==9.5"
    conflicting = [item for item in source_requests if item.startswith("coreutils==") and item != requirement]
    if conflicting:
        raise ValueError("upstream coreutils pin conflicts with native execution profile coreutils==9.5")
    return () if requirement in source_requests else (requirement,)


def scan_repository(root: Path, *, revision: str, source_url: str,
                    registry: dict[str, dict]) -> tuple[list[Candidate], dict]:
    """Scan every tracked CWL descriptor; require a clean, pinned Git revision."""
    root = root.resolve()
    actual = _git(root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or actual != revision:
        raise ValueError("source revision must equal the complete checked-out Git commit")
    if _git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("tracked source files differ from the pinned Git revision")
    parsed = urlparse(source_url.rstrip("/").removesuffix(".git"))
    if parsed.scheme != "https" or parsed.netloc != "github.com" or len(parsed.path.strip("/").split("/")) != 2:
        raise ValueError("this acquisition provider requires a canonical HTTPS GitHub repository URL")
    raw_base = f"https://raw.githubusercontent.com/{parsed.path.strip('/')}/{revision}"
    tracked = [path for path in _git(root, "ls-files", "-z").split("\0") if path]
    jobs: dict[str, list[str]] = {}
    if ".dockstore.yml" in tracked:
        for tool in _load(root / ".dockstore.yml").get("tools", []):
            descriptor = str(tool.get("primaryDescriptorPath", "")).lstrip("/")
            for job in tool.get("testParameterFiles", []):
                relative_job = str(job).lstrip("/")
                _inside(root, relative_job)
                if relative_job not in tracked:
                    raise ValueError(f"Dockstore test parameter file is not tracked: {relative_job}")
                jobs.setdefault(descriptor, []).append(relative_job)
    candidates = []
    for relative in sorted(path for path in tracked if path.endswith(".cwl")):
        raw = _inside(root, relative).read_bytes()
        candidate = Candidate(relative, f"{raw_base}/{quote(relative, safe='/')}", "sha256:" + hashlib.sha256(raw).hexdigest(), len(raw),
                              test_jobs=tuple(sorted(set(jobs.get(relative, [])))))
        candidates.append(candidate)
        try:
            document = _load(_inside(root, relative))
            accession, package, version, requests = package_identity(document)
            candidate.accession, candidate.primary_package, candidate.primary_version = accession, package, version
            candidate.requests = requests
            record = registry.get(accession)
            if record is None:
                candidate.status = "identity_unmatched"
                candidate.reason = "explicit accession absent from verified registry snapshot"
                continue
            candidate.accession = record["biotoolsID"]
            candidate.biotools_uri = f"https://bio.tools/{record['biotoolsID']}"
            canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            candidate.registry_record_sha256 = "sha256:" + hashlib.sha256(canonical).hexdigest()
            candidate.details = {"registry_name": record.get("name"), "registry_license": record.get("license"),
                                 "descriptor_license": document.get("s:license") or document.get("license"),
                                 "document_class": document.get("class")}
            stem = re.sub(r"[^a-z0-9]+", "_", f"{accession}_{Path(relative).stem}".lower()).strip("_")
            candidate.node_id = f"auto_{stem[:105]}_{candidate.source_sha256[-8:]}"
            from bionodulo.nodes.contract.cwl_reference import inspect_reference_document
            inspect_reference_document(document)
            profile_requests = execution_profile_requests(requests)
            candidate.requests = tuple(sorted(set(requests + profile_requests)))
            candidate.details["source_package_requests"] = list(requests)
            candidate.details["execution_profile_package_requests"] = list(profile_requests)
            candidate.status = "eligible"
        except (ValueError, TypeError, KeyError, yaml.YAMLError) as error:
            candidate.status = "unsupported"
            candidate.reason = str(error)
    return candidates, {"repository": source_url, "revision": actual,
                        "tracked_cwl_descriptors": len(candidates), "tracked_files": len(tracked)}


def select_cohort(candidates: list[Candidate], limit: int) -> list[Candidate]:
    """Deterministic round-robin across exact accessions, without a tool allowlist."""
    if limit < 0:
        raise ValueError("cohort limit must be nonnegative")
    groups: dict[str, list[Candidate]] = {}
    for candidate in sorted(candidates, key=lambda item: item.descriptor):
        if candidate.status == "eligible":
            if candidate.accession is None:
                raise ValueError(f"eligible descriptor has no bio.tools accession: {candidate.descriptor}")
            groups.setdefault(candidate.accession.casefold(), []).append(candidate)
    ordered = []
    while any(groups.values()):
        for accession in sorted(groups):
            if groups[accession]:
                ordered.append(groups[accession].pop(0))
    return ordered[:limit] if limit else ordered
