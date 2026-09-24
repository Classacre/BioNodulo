"""Acquire only explicitly typed CWL links from a verified bio.tools snapshot.

This is a source-evidence pass, not execution admission. Every typed link gets
one ledger row, including directory links, retrieval errors and parser errors.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import tempfile
import time
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import yaml

from bionodulo.nodes.generation.acquisition import package_identity
from bionodulo.nodes.generation.discovery import _verified_records
from bionodulo.nodes.import_cwl import _UniqueKeyLoader


MAX_SOURCE_BYTES = 4 * 1024 * 1024


class PrivateTargetError(ValueError):
    """A declared source resolves to a local or otherwise non-public address."""


def _atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cwl-source-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _source_url(declared: str) -> tuple[str | None, str]:
    """Map an exact file link to a fetch URL; never guess files in a directory."""
    try:
        parsed = urlsplit(declared)
        port = parsed.port
    except ValueError:
        return None, "invalid_url"
    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or len(declared) > 8192
    ):
        return None, "unsupported_url"
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None, "ip_literal_disallowed"
    if host.casefold() in {"localhost"} or host.casefold().endswith((".localhost", ".local", ".internal")):
        return None, "local_host_disallowed"
    path = unquote(parsed.path)
    if not path.casefold().endswith(".cwl"):
        return None, "not_a_direct_cwl_file"
    if host.casefold() == "github.com":
        parts = path.strip("/").split("/")
        if len(parts) < 5 or parts[2] != "blob" or not all(parts[:2]):
            return None, "github_link_not_exact_blob"
        # The blob URL supplies the repository, ref and exact file path.
        return "https://raw.githubusercontent.com/" + "/".join(
            quote(part, safe="") for part in (parts[:2] + parts[3:])
        ), "github_blob_to_raw"
    return declared, "direct_https_cwl"


def inventory_typed_cwl(snapshot: Path, manifest_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("registry manifest must be an object")
    rows: list[dict[str, Any]] = []
    for record in _verified_records(snapshot, manifest):
        canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        for field in ("download", "link", "documentation"):
            links = record.get(field)
            if not isinstance(links, list):
                continue
            for index, link in enumerate(links):
                if not isinstance(link, dict):
                    continue
                link_types = link.get("type")
                types = [link_types] if isinstance(link_types, str) else link_types
                if not isinstance(types, list) or "Tool wrapper (CWL)" not in types:
                    continue
                declared = link.get("url")
                fetch_url, classification = (
                    _source_url(declared) if isinstance(declared, str) else (None, "missing_url")
                )
                rows.append(
                    {
                        "biotools_accession": record["biotoolsID"],
                        "biotools_uri": f"https://bio.tools/{record['biotoolsID']}",
                        "registry_record_sha256": "sha256:" + hashlib.sha256(canonical).hexdigest(),
                        "evidence_path": f"{field}[{index}]",
                        "evidence_type": "Tool wrapper (CWL)",
                        "declared_url": declared,
                        "fetch_url": fetch_url,
                        "link_classification": classification,
                    }
                )
    rows.sort(
        key=lambda item: (item["biotools_accession"].casefold(), item["evidence_path"], str(item["declared_url"]))
    )
    return rows, {
        "registry_records": manifest["records"],
        "snapshot_sha256": manifest["sha256"],
        "typed_cwl_links": len(rows),
        "accessions_with_typed_cwl_links": len({row["biotools_accession"].casefold() for row in rows}),
    }


def _public_address(host: str) -> str:
    """Resolve once and reject a hostname with any non-public DNS answer."""
    addresses = {str(answer[4][0]) for answer in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise PrivateTargetError("DNS target is not exclusively public")
    return sorted(addresses)[0]


def _connect_pinned(host: str, address: str, timeout: float) -> http.client.HTTPSConnection:
    """Connect to the checked address while verifying TLS for the original host."""
    connection = http.client.HTTPSConnection(host, timeout=timeout)

    def connect() -> None:
        plain = socket.create_connection((address, 443), timeout=timeout)
        try:
            connection.sock = ssl.create_default_context().wrap_socket(plain, server_hostname=host)
        except BaseException:
            plain.close()
            raise

    connection.connect = connect  # type: ignore[method-assign]
    return connection


def _retrieve(url: str, *, timeout: float) -> tuple[bytes | None, dict[str, Any]]:
    parsed = urlsplit(url)
    if _source_url(url)[0] is None:
        return None, {"status": "unsupported_url"}
    if parsed.scheme != "https" or not parsed.hostname or parsed.port is not None or parsed.query or parsed.fragment:
        return None, {"status": "unsupported_url"}
    connection: http.client.HTTPSConnection | None = None
    try:
        address = _public_address(parsed.hostname)
        connection = _connect_pinned(parsed.hostname, address, timeout)
        connection.request(
            "GET",
            parsed.path,
            headers={
                "Accept": "text/plain, application/yaml, application/json",
                "User-Agent": "BioNodulo-CWL-source-acquisition/1.0",
            },
        )
        response = connection.getresponse()
        if 300 <= response.status < 400:
            return None, {"status": "redirect_refused", "http_status": response.status}
        if response.status != 200:
            return None, {"status": "http_error", "http_status": response.status}
        length = response.getheader("Content-Length")
        if length is not None and int(length) > MAX_SOURCE_BYTES:
            return None, {"status": "too_large", "http_status": response.status}
        raw = response.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            return None, {"status": "too_large", "http_status": response.status}
        return raw, {
            "status": "fetched",
            "http_status": response.status,
            "content_type": response.getheader("Content-Type"),
        }
    except PrivateTargetError as error:
        return None, {"status": "private_target_refused", "reason": str(error)}
    except (TimeoutError, OSError, ValueError, ssl.SSLError, http.client.HTTPException) as error:
        return None, {"status": "network_error", "error_type": type(error).__name__, "reason": str(error)[:300]}
    finally:
        if connection is not None:
            connection.close()


def _inspect(content: bytes, accession: str) -> dict[str, Any]:
    try:
        document = yaml.load(content.decode("utf-8"), Loader=_UniqueKeyLoader)
        if not isinstance(document, dict):
            raise ValueError("CWL document root must be a mapping")
    except (UnicodeError, yaml.YAMLError, ValueError, TypeError) as error:
        return {"status": "parse_error", "reason": str(error)[:500]}
    result: dict[str, Any] = {
        "status": "parsed",
        "document_class": document.get("class"),
        "cwl_version": document.get("cwlVersion"),
    }
    try:
        identity, package, version, requests = package_identity(document)
        result["explicit_package_identity"] = {
            "biotools_accession": identity,
            "package": package,
            "version": version,
            "requests": list(requests),
        }
        result["identity_matches_registry_link"] = identity.casefold() == accession.casefold()
    except (ValueError, TypeError, KeyError) as error:
        result["package_identity_status"] = "unavailable"
        result["package_identity_reason"] = str(error)[:500]
    try:
        from bionodulo.nodes.contract.cwl_reference import inspect_reference_document

        inspection = inspect_reference_document(document)
        result["native_reference_status"] = "inspectable"
        result["native_reference_inputs"] = len(inspection.input_mappings)
        result["native_reference_outputs"] = len(inspection.output_mappings)
    except (ValueError, TypeError, KeyError) as error:
        result["native_reference_status"] = "unsupported"
        result["native_reference_reason"] = str(error)[:500]
    result["admission_status"] = "source_evidence_only"
    return result


def acquire_typed_cwl(
    snapshot: Path,
    manifest_path: Path,
    output: Path,
    *,
    timeout: float = 15,
    delay: float = 0.25,
    max_requests: int | None = None,
) -> dict[str, Any]:
    if timeout <= 0 or delay < 0 or max_requests is not None and max_requests < 0:
        raise ValueError("timeout and request budget must be positive; delay must be nonnegative")
    rows, header = inventory_typed_cwl(snapshot, manifest_path)
    output.mkdir(parents=True, exist_ok=True)
    cache = output / "cache"
    sources = output / "sources"
    status_counts: Counter[str] = Counter()
    requests = 0
    results = []
    for row in rows:
        result = dict(row)
        url = row["fetch_url"]
        if url is None:
            result["acquisition"] = {"status": "unsupported_link", "reason": row["link_classification"]}
        else:
            key = hashlib.sha256(url.encode("utf-8")).hexdigest()
            receipt_path = cache / f"{key}.json"
            try:
                receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else None
            except (OSError, UnicodeError, json.JSONDecodeError):
                receipt = None
            raw = None
            if isinstance(receipt, dict) and receipt.get("fetch_url") == url and receipt.get("status") == "fetched":
                digest = receipt.get("source_sha256")
                if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
                    source_path = sources / f"{digest}.cwl"
                    if source_path.exists():
                        possible = source_path.read_bytes()
                        if hashlib.sha256(possible).hexdigest() == digest and len(possible) <= MAX_SOURCE_BYTES:
                            raw = possible
                            receipt = dict(receipt, source_size_bytes=len(raw), source_path=f"sources/{digest}.cwl")
            if raw is None:
                if max_requests is not None and requests >= max_requests:
                    result["acquisition"] = {"status": "request_budget_exhausted"}
                    status_counts["request_budget_exhausted"] += 1
                    results.append(result)
                    continue
                if requests and delay:
                    time.sleep(delay)
                raw, receipt = _retrieve(url, timeout=timeout)
                requests += 1
                receipt = dict(receipt, fetch_url=url)
                if raw is not None:
                    digest = hashlib.sha256(raw).hexdigest()
                    _atomic(sources / f"{digest}.cwl", raw)
                    receipt.update(
                        source_sha256=digest, source_size_bytes=len(raw), source_path=f"sources/{digest}.cwl"
                    )
                _atomic(receipt_path, _json_bytes(receipt))
            result["acquisition"] = receipt
            if raw is not None:
                result["inspection"] = _inspect(raw, row["biotools_accession"])
        status_counts[result["acquisition"]["status"]] += 1
        results.append(result)
    _atomic(output / "typed-cwl-links.jsonl", b"".join(_json_bytes(row) for row in results))
    summary = dict(
        header,
        schema_version=1,
        scope="explicitly typed CWL links only; source evidence, no execution admission",
        acquisition_status_counts=dict(sorted(status_counts.items())),
        network_requests=requests,
        parsed=sum(row.get("inspection", {}).get("status") == "parsed" for row in results),
        native_reference_inspectable=sum(
            row.get("inspection", {}).get("native_reference_status") == "inspectable" for row in results
        ),
        explicit_package_identity_matches=sum(
            row.get("inspection", {}).get("identity_matches_registry_link") is True for row in results
        ),
    )
    _atomic(output / "summary.json", json.dumps(summary, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    return summary
