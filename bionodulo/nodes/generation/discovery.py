"""Registry-wide executable-source discovery without name-based attribution.

This module inventories evidence already present in a hash-verified bio.tools
snapshot.  It never turns a name match into an executable node and never treats
metadata discovery as execution admission.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Iterator, Mapping
from urllib.parse import parse_qs, unquote, urlsplit

import yaml


_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_MAX_RECORD_BYTES = 16 * 1024 * 1024
_MAX_IUC_BLOB_BYTES = 8 * 1024 * 1024


class DiscoveryError(ValueError):
    """Discovery input is malformed, unverified, or ambiguous."""


class _UniqueSafeLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[object, object]:
        self.flatten_mapping(node)
        value: dict[object, object] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in value:
                raise DiscoveryError(f"duplicate YAML key in IUC metadata: {key!r}")
            value[key] = self.construct_object(value_node, deep=deep)
        return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _git_blob_object_id(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()  # noqa: S324 - Git SHA-1 object identity


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".registry-discovery-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_discovery_summary(output: Path, summary: Mapping[str, object]) -> None:
    """Atomically publish the current combined discovery summary."""

    content = json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n"
    _atomic_bytes(output / "summary.json", content)


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 8192:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
    ):
        return None
    return value


def _typed_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    return ()


def _record_urls(record: Mapping[str, Any]) -> Iterator[tuple[str, str | None, str]]:
    homepage = _safe_url(record.get("homepage"))
    if homepage:
        yield "homepage", None, homepage
    for field in ("download", "link", "documentation"):
        values = record.get(field)
        if not isinstance(values, list):
            continue
        for index, item in enumerate(values):
            if not isinstance(item, Mapping):
                continue
            url = _safe_url(item.get("url"))
            if not url:
                continue
            types = _typed_values(item.get("type"))
            if not types:
                yield f"{field}[{index}]", None, url
            for item_type in types:
                yield f"{field}[{index}]", item_type, url


def _package_identity(url: str) -> dict[str, str] | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    parts = [unquote(item) for item in parsed.path.split("/") if item]
    if host in {"pypi.org", "www.pypi.org"} and len(parts) >= 2 and parts[0] == "project":
        return {"ecosystem": "pypi", "package_id": parts[1]}
    if host == "anaconda.org" and len(parts) >= 2:
        return {"ecosystem": "conda", "namespace": parts[0], "package_id": parts[1]}
    if host in {"cran.r-project.org", "cloud.r-project.org"}:
        query = parse_qs(parsed.query)
        if len(parts) >= 3 and parts[:2] == ["web", "packages"]:
            return {"ecosystem": "cran", "package_id": parts[2]}
        if query.get("package"):
            return {"ecosystem": "cran", "package_id": query["package"][0]}
    if host == "bioconductor.org" and "html" in parts:
        selected = parts[-1].removesuffix(".html")
        if selected:
            return {"ecosystem": "bioconductor", "package_id": selected}
    if host in {"npmjs.com", "www.npmjs.com"} and len(parts) >= 2 and parts[0] == "package":
        return {"ecosystem": "npm", "package_id": "/".join(parts[1:])}
    return None


def _repository_identity(url: str) -> dict[str, str] | None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    parts = [unquote(item) for item in parsed.path.split("/") if item]
    if host == "github.com" and len(parts) >= 2:
        return {"provider": "github", "repository": f"{parts[0]}/{parts[1].removesuffix('.git')}"}
    if host == "gitlab.com" and len(parts) >= 2:
        return {"provider": "gitlab", "repository": f"{parts[0]}/{parts[1].removesuffix('.git')}"}
    return None


@dataclass(frozen=True)
class IucDescriptor:
    path: str
    git_object_id: str
    git_mode: str
    size_bytes: int | None
    sha256: str | None
    content_status: str


@dataclass(frozen=True)
class IucRepository:
    path: str
    shed_name: str | None
    metadata_git_object_id: str
    metadata_sha256: str | None
    metadata_content_status: str
    descriptors: tuple[IucDescriptor, ...]


@dataclass(frozen=True)
class IucInventory:
    source_url: str
    revision: str
    repositories: tuple[IucRepository, ...]
    unassigned_xml: tuple[IucDescriptor, ...]

    def by_name(self) -> dict[str, tuple[IucRepository, ...]]:
        selected: dict[str, list[IucRepository]] = defaultdict(list)
        for repository in self.repositories:
            if repository.shed_name is not None:
                selected[repository.shed_name.casefold()].append(repository)
        return {key: tuple(values) for key, values in selected.items()}


def inventory_iuc_repository(root: Path, *, revision: str, source_url: str) -> IucInventory:
    """Inventory pinned IUC Git blobs without interpreting Galaxy XML semantics."""

    if _COMMIT_RE.fullmatch(revision) is None:
        raise DiscoveryError("IUC revision must be one full lowercase Git commit")
    repository = root.expanduser().absolute()
    actual = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", f"{revision}^{{commit}}"], text=True
    ).strip()
    if actual != revision:
        raise DiscoveryError("IUC revision does not resolve to the requested commit")
    parsed_source = urlsplit(source_url.rstrip("/").removesuffix(".git"))
    if (
        parsed_source.scheme != "https"
        or parsed_source.hostname != "github.com"
        or parsed_source.path.rstrip("/").casefold() != "/galaxyproject/tools-iuc"
        or parsed_source.query
        or parsed_source.fragment
        or parsed_source.username is not None
        or parsed_source.password is not None
    ):
        raise DiscoveryError("IUC source URL must be canonical https://github.com/galaxyproject/tools-iuc")

    tree = subprocess.check_output(
        ["git", "-C", str(repository), "ls-tree", "-r", "-z", revision]
    )
    blobs: list[tuple[str, str, str]] = []
    for raw_entry in tree.split(b"\0"):
        if not raw_entry:
            continue
        metadata_bytes, separator, path_bytes = raw_entry.partition(b"\t")
        fields = metadata_bytes.split()
        if not separator or len(fields) != 3 or fields[1] != b"blob":
            raise DiscoveryError("unexpected entry in pinned IUC Git tree")
        try:
            path = path_bytes.decode("utf-8")
            mode = fields[0].decode("ascii")
            object_id = fields[2].decode("ascii")
        except UnicodeError as error:
            raise DiscoveryError("invalid path in pinned IUC Git tree") from error
        if path.endswith("/.shed.yml") or path.endswith(".xml"):
            if mode not in {"100644", "100755", "120000"}:
                raise DiscoveryError(f"unsupported pinned IUC Git mode {mode}: {path}")
            blobs.append((path, object_id, mode))

    process_environment = dict(os.environ)
    process_environment["GIT_NO_LAZY_FETCH"] = "1"
    local_objects_result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "cat-file",
            "--batch-all-objects",
            "--batch-check=%(objectname) %(objecttype)",
            "--unordered",
        ],
        capture_output=True,
        env=process_environment,
    )
    if local_objects_result.returncode != 0:
        raise DiscoveryError(
            "cannot inventory locally available objects in the pinned IUC partial clone: "
            + local_objects_result.stderr.decode("utf-8", errors="replace").strip()
        )
    locally_available_blobs = {
        fields[0].decode("ascii", errors="strict")
        for line in local_objects_result.stdout.splitlines()
        if len(fields := line.split()) == 2 and fields[1] == b"blob"
    }
    process = subprocess.Popen(
        ["git", "-C", str(repository), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=process_environment,
    )
    assert process.stdin is not None and process.stdout is not None
    metadata: dict[str, tuple[str | None, str | None, str, str]] = {}
    xml: list[IucDescriptor] = []
    try:
        for path, object_id, mode in blobs:
            if object_id not in locally_available_blobs:
                content = None
                size = None
            else:
                process.stdin.write(object_id.encode("ascii") + b"\n")
                process.stdin.flush()
                header = process.stdout.readline().decode("ascii", errors="strict").strip().split()
                if len(header) == 3 and header[0] == object_id and header[1] == "blob":
                    size = int(header[2])
                    if size < 1 or size > _MAX_IUC_BLOB_BYTES:
                        raise DiscoveryError(f"IUC blob has unsupported size: {path}")
                    content = process.stdout.read(size)
                    if len(content) != size or process.stdout.read(1) != b"\n":
                        raise DiscoveryError(f"truncated IUC blob: {path}")
                    if _git_blob_object_id(content) != object_id:
                        raise DiscoveryError(f"pinned IUC blob has the wrong Git object identity: {path}")
                else:
                    raise DiscoveryError(f"cannot read pinned IUC blob: {path}")
            if path.endswith("/.shed.yml"):
                name = None
                metadata_status = (
                    "git_object_missing_from_local_partial_clone"
                    if content is None
                    else "content_verified"
                )
                if content is not None:
                    try:
                        document = yaml.load(content.decode("utf-8"), Loader=_UniqueSafeLoader)
                    except (DiscoveryError, UnicodeError, yaml.YAMLError):
                        metadata_status = "content_invalid_metadata"
                    else:
                        name = document.get("name") if isinstance(document, Mapping) else None
                        if not isinstance(name, str) or not name.strip():
                            name = None
                            metadata_status = "content_invalid_metadata"
                metadata[str(PurePosixPath(path).parent)] = (
                    name,
                    None if content is None else _sha256(content),
                    object_id,
                    metadata_status,
                )
            else:
                xml.append(
                    IucDescriptor(
                        path=path,
                        git_object_id=object_id,
                        git_mode=mode,
                        size_bytes=size,
                        sha256=None if content is None else _sha256(content),
                        content_status=(
                            "git_object_missing_from_local_partial_clone"
                            if content is None
                            else "content_verified"
                        ),
                    )
                )
    finally:
        process.stdin.close()
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    if process.wait() != 0:
        raise DiscoveryError(f"git cat-file failed for IUC revision: {stderr.strip()}")

    descriptors_by_repository: dict[str, list[IucDescriptor]] = defaultdict(list)
    unassigned: list[IucDescriptor] = []
    for descriptor in xml:
        parent = PurePosixPath(descriptor.path).parent
        while str(parent) not in metadata and str(parent) not in {"", "."}:
            parent = parent.parent
        selected_path = str(parent)
        if selected_path in metadata:
            descriptors_by_repository[selected_path].append(descriptor)
        else:
            unassigned.append(descriptor)
    repositories: list[IucRepository] = []
    for path, (name, digest, object_id, content_status) in sorted(metadata.items()):
        descriptors = tuple(descriptors_by_repository.get(path, ()))
        repositories.append(
            IucRepository(path, name, object_id, digest, content_status, descriptors)
        )
    return IucInventory(
        source_url=source_url.rstrip("/").removesuffix(".git"),
        revision=revision,
        repositories=tuple(repositories),
        unassigned_xml=tuple(unassigned),
    )


def _iuc_match(url: str, inventory: IucInventory) -> tuple[IucRepository, ...]:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    path = unquote(parsed.path)
    selected: list[IucRepository] = []
    if host == "github.com":
        parts = [item for item in path.split("/") if item]
        if len(parts) >= 5 and [item.casefold() for item in parts[:2]] == ["galaxyproject", "tools-iuc"] and parts[2] in {"blob", "tree"}:
            relative = "/".join(parts[4:]).rstrip("/")
            for repository in inventory.repositories:
                if relative == repository.path or relative.startswith(repository.path.rstrip("/") + "/"):
                    selected.append(repository)
    if host in {"toolshed.g2.bx.psu.edu", "toolshed.galaxyproject.org"}:
        decoded = unquote(url)
        names = re.findall(r"/(?:view|repos)/iuc/([^/?&#]+)", decoded, flags=re.IGNORECASE)
        by_name = inventory.by_name()
        for name in names:
            selected.extend(by_name.get(name.casefold(), ()))
    return tuple(sorted(set(selected), key=lambda item: item.path))


def discover_record(record: Mapping[str, Any], *, iuc: IucInventory | None = None) -> dict[str, object]:
    accession = record.get("biotoolsID")
    if not isinstance(accession, str) or not accession:
        raise DiscoveryError("bio.tools record has no accession")
    candidates: list[dict[str, object]] = []
    iuc_matches: dict[str, IucRepository] = {}
    for evidence_path, evidence_type, url in _record_urls(record):
        low = url.casefold()
        path_low = urlsplit(url).path.casefold()
        candidate: dict[str, object] | None = None
        if evidence_type == "Tool wrapper (CWL)" or path_low.endswith(".cwl"):
            candidate = {"kind": "descriptor", "format": "cwl"}
        elif re.search(r"/(?:openapi|swagger)(?:[-._][^/]*)?\.(?:json|ya?ml)$", path_low):
            candidate = {"kind": "api_specification", "format": "openapi"}
        elif evidence_type == "Tool wrapper (Galaxy)":
            candidate = {"kind": "descriptor", "format": "galaxy"}
        elif evidence_type == "API specification":
            candidate = {
                "kind": "api_specification",
                "format": "openapi_candidate" if "openapi" in low or "swagger" in low else "unspecified",
            }
        elif evidence_type == "Command-line specification":
            candidate = {
                "kind": "descriptor",
                "format": "boutiques" if "boutiques" in low else "command_line_specification",
            }
        elif evidence_type == "Tool wrapper (Other)":
            candidate = {"kind": "descriptor", "format": "other_wrapper"}
        elif evidence_type == "Galaxy service":
            candidate = {"kind": "galaxy_service", "format": "galaxy_tool_id"}
        elif (urlsplit(url).hostname or "").casefold() in {
            "toolshed.g2.bx.psu.edu",
            "toolshed.galaxyproject.org",
        }:
            candidate = {"kind": "galaxy_reference", "format": "galaxy_tool_or_repository"}
        elif evidence_type in {"Repository", "Source code"}:
            candidate = {"kind": "repository", **(_repository_identity(url) or {})}
        elif evidence_type == "Software package":
            candidate = {"kind": "package", **(_package_identity(url) or {"ecosystem": "unspecified"})}
        if candidate is not None:
            candidate.update({"url": url, "evidence_path": evidence_path, "evidence_type": evidence_type})
            candidates.append(candidate)
        if iuc is not None:
            for repository in _iuc_match(url, iuc):
                iuc_matches[repository.path] = repository
    if iuc is not None:
        for repository in sorted(iuc_matches.values(), key=lambda item: item.path):
            candidates.append(
                {
                    "kind": "pinned_repository_descriptors",
                    "format": "galaxy_xml",
                    "url": f"{iuc.source_url}/tree/{iuc.revision}/{repository.path}",
                    "repository_path": repository.path,
                    "repository_name": repository.shed_name,
                    "revision": iuc.revision,
                    "metadata_git_object_id": repository.metadata_git_object_id,
                    "metadata_sha256": repository.metadata_sha256,
                    "metadata_content_status": repository.metadata_content_status,
                    "descriptor_count": len(repository.descriptors),
                    "descriptors": [item.__dict__ for item in repository.descriptors],
                    "identity_basis": "record URL explicitly names tools-iuc path or ToolShed owner iuc",
                    "semantics_status": "not_parsed_requires_official_galaxy_parser",
                }
            )
    unique = {_canonical_bytes(item): item for item in candidates}
    candidates = [unique[key] for key in sorted(unique)]
    kinds = {str(item["kind"]) for item in candidates}
    formats = {str(item.get("format", "")) for item in candidates}
    gaps: set[str] = {"not_execution_admitted"}
    if not candidates:
        gaps.add("no_structured_source_metadata")
    if "repository" in kinds:
        gaps.add("repository_requires_descriptor_discovery")
    if "package" in kinds:
        gaps.add("package_identity_requires_interface_contract")
    if "cwl" in formats or "boutiques" in formats or "command_line_specification" in formats:
        gaps.add("descriptor_requires_fetch_validation_and_environment")
    if formats & {"galaxy", "galaxy_tool_id", "galaxy_tool_or_repository"}:
        gaps.add("galaxy_source_not_pinned_or_parsed")
    if "galaxy_xml" in formats:
        gaps.add("galaxy_xml_requires_official_parser_and_runtime_adapter")
    if "openapi_candidate" in formats or "api_specification" in kinds:
        gaps.add("api_spec_requires_operation_contract_and_auth_review")
    tool_types = tuple(sorted(item for item in (record.get("toolType") or []) if isinstance(item, str)))
    if "Command-line tool" not in tool_types:
        gaps.add("record_not_declared_command_line_tool")
    if any(item["kind"] in {"descriptor", "pinned_repository_descriptors", "api_specification"} for item in candidates):
        status = "structured_interface_source_discovered"
    elif candidates:
        status = "metadata_source_candidates_only"
    else:
        status = "no_structured_source"
    return {
        "schema_version": 1,
        "biotools_accession": accession,
        "biotools_uri": f"https://bio.tools/{accession}",
        "record_sha256": _sha256(_canonical_bytes(record)),
        "tool_types": list(tool_types),
        "status": status,
        "source_candidates": candidates,
        "gap_states": sorted(gaps),
    }


def _verified_records(snapshot: Path, manifest: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    expected_digest = manifest.get("sha256")
    expected_records = manifest.get("records")
    if (
        not isinstance(expected_digest, str)
        or _SHA256_RE.fullmatch(expected_digest) is None
        or type(expected_records) is not int
        or expected_records < 1
        or manifest.get("complete") is not True
    ):
        raise DiscoveryError("registry manifest is malformed or incomplete")
    digest = hashlib.sha256()
    seen: set[str] = set()
    count = 0
    with snapshot.open("rb") as stream:
        for line in stream:
            digest.update(line)
            if len(line) > _MAX_RECORD_BYTES:
                raise DiscoveryError("registry record exceeds the 16 MiB limit")
            value = json.loads(line)
            if type(value) is not dict:
                raise DiscoveryError("registry snapshot record must be an object")
            accession = value.get("biotoolsID")
            if not isinstance(accession, str) or not accession:
                raise DiscoveryError("registry snapshot record has no accession")
            key = accession.casefold()
            if key in seen:
                raise DiscoveryError(f"duplicate registry accession: {accession}")
            seen.add(key)
            count += 1
            yield value
    if digest.hexdigest() != expected_digest or count != expected_records:
        raise DiscoveryError("registry snapshot digest or record count does not match its manifest")


def verified_registry_accessions(snapshot: Path, manifest_path: Path) -> set[str]:
    """Verify the snapshot while retaining only case-folded accession identity."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if type(manifest) is not dict:
        raise DiscoveryError("registry manifest must be an object")
    return {str(record["biotoolsID"]).casefold() for record in _verified_records(snapshot, manifest)}


def write_iuc_inventory(inventory: IucInventory, output: Path) -> dict[str, object]:
    lines: list[bytes] = []
    for repository in inventory.repositories:
        value = {
            "schema_version": 1,
            "repository_path": repository.path,
            "repository_name": repository.shed_name,
            "metadata_git_object_id": repository.metadata_git_object_id,
            "metadata_sha256": repository.metadata_sha256,
            "metadata_content_status": repository.metadata_content_status,
            "descriptors": [item.__dict__ for item in repository.descriptors],
            "semantics_status": "not_parsed_requires_official_galaxy_parser",
        }
        lines.append(_canonical_bytes(value) + b"\n")
    if inventory.unassigned_xml:
        lines.append(
            _canonical_bytes(
                {
                    "schema_version": 1,
                    "repository_path": None,
                    "repository_name": None,
                    "metadata_git_object_id": None,
                    "metadata_sha256": None,
                    "metadata_content_status": "no_nearest_shed_metadata",
                    "descriptors": [item.__dict__ for item in inventory.unassigned_xml],
                    "semantics_status": "not_parsed_requires_official_galaxy_parser",
                }
            )
            + b"\n"
        )
    content = b"".join(lines)
    _atomic_bytes(output, content)
    all_descriptors = [
        item
        for repository in inventory.repositories
        for item in repository.descriptors
    ] + list(inventory.unassigned_xml)
    return {
        "repository": inventory.source_url,
        "revision": inventory.revision,
        "repositories": len(inventory.repositories),
        "ledger_records": len(lines),
        "assigned_xml_blobs": sum(len(item.descriptors) for item in inventory.repositories),
        "unassigned_xml_blobs": len(inventory.unassigned_xml),
        "content_verified_xml_blobs": sum(item.sha256 is not None for item in all_descriptors),
        "content_unavailable_xml_blobs": sum(item.sha256 is None for item in all_descriptors),
        "sha256": _sha256(content),
        "semantics_status": "not_parsed_requires_official_galaxy_parser",
    }


def _bounded_json_value(value: object, *, label: str) -> object:
    content = json.dumps(value, ensure_ascii=False, allow_nan=False, default=str).encode("utf-8")
    if len(content) > 4 * 1024 * 1024:
        raise DiscoveryError(f"official Galaxy parser {label} exceeds the 4 MiB record limit")
    return json.loads(content)


def discover_iuc_with_official_parser(
    inventory: IucInventory,
    repository: Path,
    staging_root: Path,
    output: Path,
    *,
    registry_accessions: set[str],
) -> dict[str, object]:
    """Parse locally available pinned XML with galaxy-tool-util, never custom XML semantics."""

    try:
        from importlib.metadata import version as distribution_version
        from galaxy.tool_util.model_factory import parse_tool
        from galaxy.tool_util.parser import get_tool_source
    except ImportError as error:
        raise DiscoveryError("official galaxy-tool-util is required for --parse-iuc-official") from error

    parser_version = distribution_version("galaxy-tool-util")
    staging_parent = staging_root.expanduser().absolute()
    staging_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="iuc-parser-", dir=staging_parent)).resolve()
    output.mkdir(parents=True, exist_ok=True)
    descriptor_by_path = {
        descriptor.path: descriptor
        for item in inventory.repositories
        for descriptor in item.descriptors
        if descriptor.sha256 is not None
    }
    descriptor_by_path.update(
        {item.path: item for item in inventory.unassigned_xml if item.sha256 is not None}
    )
    staged: dict[str, dict[str, object]] = {}
    try:
        process_environment = dict(os.environ)
        process_environment["GIT_NO_LAZY_FETCH"] = "1"
        blob_process = subprocess.Popen(
            ["git", "-C", str(repository), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_environment,
        )
        assert blob_process.stdin is not None and blob_process.stdout is not None
        pending_symlinks: list[tuple[Path, str, str]] = []
        try:
            for relative, descriptor in sorted(descriptor_by_path.items()):
                pure = PurePosixPath(relative)
                if pure.is_absolute() or ".." in pure.parts:
                    raise DiscoveryError(f"unsafe pinned IUC path: {relative}")
                blob_process.stdin.write(descriptor.git_object_id.encode("ascii") + b"\n")
                blob_process.stdin.flush()
                header = blob_process.stdout.readline().decode("ascii", errors="strict").strip().split()
                if (
                    len(header) != 3
                    or header[0] != descriptor.git_object_id
                    or header[1] != "blob"
                ):
                    raise DiscoveryError(f"locally available IUC blob changed or disappeared: {relative}")
                size = int(header[2])
                content = blob_process.stdout.read(size)
                if len(content) != size or blob_process.stdout.read(1) != b"\n":
                    raise DiscoveryError(f"truncated pinned IUC blob: {relative}")
                if _git_blob_object_id(content) != descriptor.git_object_id:
                    raise DiscoveryError(f"staged IUC blob has the wrong Git object identity: {relative}")
                if _sha256(content) != descriptor.sha256:
                    raise DiscoveryError(f"pinned IUC blob digest changed: {relative}")
                destination = stage.joinpath(*pure.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                receipt: dict[str, object] = {
                    "path": relative,
                    "git_object_id": descriptor.git_object_id,
                    "git_mode": descriptor.git_mode,
                    "sha256": descriptor.sha256,
                    "size_bytes": len(content),
                }
                staged[relative] = receipt
                if descriptor.git_mode == "120000":
                    try:
                        target_text = content.decode("utf-8")
                    except UnicodeError as error:
                        raise DiscoveryError(f"pinned IUC symlink is not UTF-8: {relative}") from error
                    target = PurePosixPath(target_text)
                    normalized = posixpath.normpath(str(pure.parent / target))
                    if (
                        not target_text
                        or target.is_absolute()
                        or normalized == ".."
                        or normalized.startswith("../")
                    ):
                        raise DiscoveryError(f"pinned IUC symlink escapes the staging root: {relative}")
                    receipt["symlink_target"] = target_text
                    pending_symlinks.append((destination, target_text, normalized))
                else:
                    destination.write_bytes(content)
        finally:
            blob_process.stdin.close()
        blob_stderr = (
            blob_process.stderr.read().decode("utf-8", errors="replace")
            if blob_process.stderr is not None
            else ""
        )
        if blob_process.wait() != 0:
            raise DiscoveryError(f"git cat-file failed while staging IUC sources: {blob_stderr.strip()}")
        for destination, target_text, normalized in pending_symlinks:
            if normalized not in staged:
                raise DiscoveryError(f"pinned IUC symlink target was not staged: {normalized}")
            destination.symlink_to(target_text)
        for destination, _target_text, _normalized in pending_symlinks:
            try:
                resolved = destination.resolve(strict=True)
                resolved.relative_to(stage)
            except (FileNotFoundError, RuntimeError, ValueError) as error:
                raise DiscoveryError(f"pinned IUC symlink has an invalid target: {destination}") from error

        records: list[dict[str, object]] = []
        joins: list[dict[str, object]] = []
        status_counts: Counter[str] = Counter()
        classification_counts: Counter[str] = Counter()
        error_type_counts: Counter[str] = Counter()
        for relative, source_receipt in sorted(staged.items()):
            source_path = stage.joinpath(*PurePosixPath(relative).parts)
            item: dict[str, object] = {
                "schema_version": 1,
                "descriptor": source_receipt,
                "parser": {"package": "galaxy-tool-util", "version": parser_version},
                "status": "parser_error",
                "official_parser_classification": "source_loader_error_or_unclassified_xml",
                "gap_states": ["not_execution_admitted"],
            }
            try:
                source = get_tool_source(source_path)
                parsed_source_id = source.parse_id()
                if isinstance(parsed_source_id, str) and parsed_source_id:
                    item["official_parser_classification"] = "tool_source_with_id"
                    item["official_parser_tool_id"] = parsed_source_id
                else:
                    item["official_parser_classification"] = "xml_without_tool_id"
                parsed = parse_tool(source)
                model = parsed.model_dump(mode="json", by_alias=True)
                xrefs = _bounded_json_value(source.parse_xrefs(), label="xrefs")
                tests = _bounded_json_value(source.parse_tests_to_dict(), label="tests")
                macro_paths = tuple(str(value) for value in (getattr(source, "macro_paths", None) or ()))
                closure: list[dict[str, object]] = [source_receipt]
                resolved_source = source_path.resolve(strict=True)
                if resolved_source != source_path.absolute():
                    try:
                        resolved_source_relative = resolved_source.relative_to(stage).as_posix()
                    except ValueError as error:
                        raise DiscoveryError("official parser source symlink escapes the pinned staging root") from error
                    resolved_source_receipt = staged.get(resolved_source_relative)
                    if (
                        resolved_source_receipt is None
                        or _sha256(resolved_source.read_bytes()) != resolved_source_receipt["sha256"]
                    ):
                        raise DiscoveryError(
                            f"official parser used an unverified source symlink target: {resolved_source_relative}"
                        )
                    closure.append(resolved_source_receipt)
                for macro_path in sorted(set(macro_paths)):
                    candidate = Path(macro_path)
                    if not candidate.is_absolute():
                        candidate = source_path.parent / candidate
                    raw = candidate.absolute()
                    try:
                        raw_relative = raw.relative_to(stage).as_posix()
                    except ValueError as error:
                        raise DiscoveryError("official parser macro path escapes the pinned staging root") from error
                    raw_receipt = staged.get(raw_relative)
                    if raw_receipt is not None and raw_receipt not in closure:
                        closure.append(raw_receipt)
                    resolved = candidate.resolve(strict=True)
                    try:
                        macro_relative = resolved.relative_to(stage).as_posix()
                    except ValueError as error:
                        raise DiscoveryError("official parser macro path escapes the pinned staging root") from error
                    receipt = staged.get(macro_relative)
                    if receipt is None or _sha256(resolved.read_bytes()) != receipt["sha256"]:
                        raise DiscoveryError(f"official parser used an unverified macro import: {macro_relative}")
                    if receipt not in closure:
                        closure.append(receipt)
                selected_model = {
                    key: model.get(key)
                    for key in ("id", "name", "version", "profile", "inputs", "outputs", "stdio", "requirements")
                    if key in model
                }
                item.update(
                    {
                        "status": "parsed",
                        "official_parser_classification": "parsed_tool_wrapper",
                        "gap_states": [
                            "not_execution_admitted",
                            "galaxy_runtime_adapter_not_implemented",
                            "galaxy_test_and_data_table_closure_not_inventoried",
                        ],
                        "source_closure": closure,
                        "xrefs": xrefs,
                        "interface": _bounded_json_value(selected_model, label="interface"),
                        "tests": tests,
                    }
                )
                for xref in xrefs if isinstance(xrefs, list) else ():
                    if not isinstance(xref, Mapping):
                        continue
                    xref_type, xref_value = xref.get("type"), xref.get("value")
                    if (
                        isinstance(xref_type, str)
                        and xref_type.casefold() in {"bio.tools", "biotools"}
                        and isinstance(xref_value, str)
                        and re.fullmatch(r"[A-Za-z0-9._-]+", xref_value)
                    ):
                        key = xref_value.casefold()
                        matched = key in registry_accessions
                        joins.append(
                            {
                                "schema_version": 1,
                                "descriptor_path": relative,
                                "descriptor_sha256": source_receipt["sha256"],
                                "biotools_accession": xref_value,
                                "biotools_uri": f"https://bio.tools/{xref_value}",
                                "registry_match": matched,
                                "identity_basis": "official Galaxy parser explicit bio.tools xref",
                                "execution_status": "not_execution_admitted",
                            }
                        )
            except Exception as error:
                item["error"] = {
                    "type": type(error).__name__,
                    "message": str(error)[:2048],
                }
                error_type_counts[type(error).__name__] += 1
                item["gap_states"] = [
                    "not_execution_admitted",
                    "official_galaxy_parser_error_or_incomplete_source_closure",
                ]
            records.append(item)
            status_counts[str(item["status"])] += 1
            classification_counts[str(item["official_parser_classification"])] += 1

        parser_content = b"".join(_canonical_bytes(item) + b"\n" for item in records)
        join_content = b"".join(_canonical_bytes(item) + b"\n" for item in joins)
        _atomic_bytes(output / "galaxy-iuc-parser.jsonl", parser_content)
        _atomic_bytes(output / "galaxy-iuc-xref-joins.jsonl", join_content)
        summary = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "official parser discovery only; no wrapper is execution-admitted or scientifically verified",
            "source": {"repository": inventory.source_url, "revision": inventory.revision},
            "parser": {
                "package": "galaxy-tool-util",
                "version": parser_version,
                "python": sys.executable,
            },
            "staged_source_blobs": len(staged),
            "unstaged_source_blobs": (
                sum(len(item.descriptors) for item in inventory.repositories)
                + len(inventory.unassigned_xml)
                - len(staged)
            ),
            "status_counts": dict(sorted(status_counts.items())),
            "official_parser_classification_counts": dict(sorted(classification_counts.items())),
            "error_type_counts": dict(sorted(error_type_counts.items())),
            "explicit_biotools_xrefs": len(joins),
            "descriptors_with_explicit_biotools_xrefs": len(
                {str(item["descriptor_path"]) for item in joins}
            ),
            "unique_explicit_biotools_accessions": len(
                {str(item["biotools_accession"]).casefold() for item in joins}
            ),
            "registry_matched_xrefs": sum(item["registry_match"] is True for item in joins),
            "registry_matched_accessions": len(
                {
                    str(item["biotools_accession"]).casefold()
                    for item in joins
                    if item["registry_match"] is True
                }
            ),
            "registry_unmatched_xrefs": sum(item["registry_match"] is False for item in joins),
            "parser_ledger": {
                "path": "galaxy-iuc-parser.jsonl",
                "sha256": _sha256(parser_content),
                "records": len(records),
            },
            "xref_ledger": {
                "path": "galaxy-iuc-xref-joins.jsonl",
                "sha256": _sha256(join_content),
                "records": len(joins),
            },
        }
        _atomic_bytes(
            output / "galaxy-iuc-parser-summary.json",
            json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\n",
        )
        return summary
    finally:
        if stage.parent != staging_parent or not stage.name.startswith("iuc-parser-") or stage.is_symlink():
            raise RuntimeError("refusing to clean an invalid IUC parser staging directory")
        shutil.rmtree(stage)


def discover_registry(
    snapshot: Path,
    manifest_path: Path,
    output: Path,
    *,
    iuc: IucInventory | None = None,
) -> dict[str, object]:
    """Account for every verified registry record in an atomic JSONL audit."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if type(manifest) is not dict:
        raise DiscoveryError("registry manifest must be an object")
    output.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=".registry-discovery-", suffix=".jsonl", dir=output)
    status_counts: Counter[str] = Counter()
    gap_counts: Counter[str] = Counter()
    candidate_record_counts: Counter[str] = Counter()
    candidate_counts: Counter[str] = Counter()
    format_record_counts: Counter[str] = Counter()
    format_counts: Counter[str] = Counter()
    records = 0
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as stream:
            for record in _verified_records(snapshot, manifest):
                result = discover_record(record, iuc=iuc)
                line = _canonical_bytes(result) + b"\n"
                stream.write(line)
                digest.update(line)
                records += 1
                status_counts[str(result["status"])] += 1
                for gap in result["gap_states"]:
                    gap_counts[str(gap)] += 1
                kinds = {str(item["kind"]) for item in result["source_candidates"]}
                formats = {
                    str(item["format"])
                    for item in result["source_candidates"]
                    if item.get("format") is not None
                }
                candidate_record_counts.update(kinds)
                candidate_counts.update(str(item["kind"]) for item in result["source_candidates"])
                format_record_counts.update(formats)
                format_counts.update(
                    str(item["format"])
                    for item in result["source_candidates"]
                    if item.get("format") is not None
                )
            stream.flush()
            os.fsync(stream.fileno())
        if records != manifest["records"]:
            raise DiscoveryError("discovery output did not account for every verified registry record")
        final = output / "registry-discovery.jsonl"
        os.replace(temporary_name, final)
    finally:
        Path(temporary_name).unlink(missing_ok=True)

    iuc_summary = None
    if iuc is not None:
        iuc_summary = write_iuc_inventory(iuc, output / "galaxy-iuc-inventory.jsonl")
    for expected_format in ("cwl", "galaxy", "boutiques", "openapi"):
        format_record_counts.setdefault(expected_format, 0)
        format_counts.setdefault(expected_format, 0)
    summary: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "source discovery only; no candidate is execution-admitted or scientifically verified",
        "registry": {
            "source": manifest.get("source"),
            "snapshot_sha256": manifest["sha256"],
            "records": records,
            "completed_at": manifest.get("completed_at"),
        },
        "output": {
            "path": "registry-discovery.jsonl",
            "sha256": "sha256:" + digest.hexdigest(),
            "records": records,
        },
        "status_counts": dict(sorted(status_counts.items())),
        "gap_counts": dict(sorted(gap_counts.items())),
        "candidate_record_counts": dict(sorted(candidate_record_counts.items())),
        "candidate_counts": dict(sorted(candidate_counts.items())),
        "candidate_format_record_counts": dict(sorted(format_record_counts.items())),
        "candidate_format_counts": dict(sorted(format_counts.items())),
        "galaxy_iuc": iuc_summary,
    }
    write_discovery_summary(output, summary)
    return summary


__all__ = [
    "DiscoveryError",
    "IucDescriptor",
    "IucInventory",
    "IucRepository",
    "discover_record",
    "discover_registry",
    "discover_iuc_with_official_parser",
    "inventory_iuc_repository",
    "verified_registry_accessions",
    "write_discovery_summary",
]
