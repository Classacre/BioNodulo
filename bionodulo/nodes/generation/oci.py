"""Read-only OCI registry resolution for source-declared CWL Docker images."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from bionodulo.nodes.contract.artifacts import _StrictFrozenModel
from bionodulo.nodes.contract.cwl_oci import CwlOciImportError, canonical_image
from bionodulo.nodes.contract.environments import ExecutionPlatform


_INDEX_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}
_MANIFEST_TYPES = {
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
}
_ACCEPT = ", ".join(sorted(_INDEX_TYPES | _MANIFEST_TYPES))
_MAX_METADATA_BYTES = 8 * 1024 * 1024
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BEARER_RE = re.compile(r'^Bearer realm="(?P<realm>https://[^\"]+)",service="(?P<service>[^\"]+)"(?:,scope="(?P<scope>[^\"]+)")?$', re.I)


class OciResolutionError(ValueError):
    """A tag cannot be bound to a verified platform image digest."""


class OciResolution(_StrictFrozenModel):
    source_pull: str
    image_index: str
    image_platform: str
    platform: ExecutionPlatform
    index_media_type: str
    manifest_media_type: str
    config_digest: str
    provenance: str = "registry_metadata_only"
    # Resolution does not prove a local image, container daemon, or cwltool run.


def _bounded_json(content: bytes, *, label: str) -> dict[str, Any]:
    if not content or len(content) > _MAX_METADATA_BYTES:
        raise OciResolutionError(f"{label} metadata is empty or exceeds 8 MiB")
    try:
        value = json.loads(content)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise OciResolutionError(f"{label} metadata is invalid JSON") from error
    if type(value) is not dict:
        raise OciResolutionError(f"{label} metadata must be an object")
    return value


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _verified_digest(content: bytes, expected: str, *, label: str) -> None:
    if _DIGEST_RE.fullmatch(expected) is None or _digest(content) != expected:
        raise OciResolutionError(f"{label} digest does not match registry bytes")


def _public_fetch(url: str, accept: str) -> bytes:
    """Fetch bounded public metadata, authenticating anonymously if challenged."""

    def read(request_url: str, *, authorization: str | None = None) -> bytes:
        headers = {"Accept": accept, "Accept-Encoding": "identity", "User-Agent": "BioNodulo-OCI-Discovery/1"}
        if authorization:
            headers["Authorization"] = authorization
        with urlopen(Request(request_url, headers=headers), timeout=20) as response:
            payload = response.read(_MAX_METADATA_BYTES + 1)
            if len(payload) > _MAX_METADATA_BYTES:
                raise OciResolutionError("OCI registry metadata exceeds 8 MiB")
            return payload

    if urlsplit(url).scheme != "https":
        raise OciResolutionError("OCI registry metadata requires HTTPS")
    try:
        return read(url)
    except HTTPError as error:
        if error.code != 401:
            raise OciResolutionError(f"OCI registry returned HTTP {error.code}") from error
        challenge = error.headers.get("WWW-Authenticate", "")
    match = _BEARER_RE.fullmatch(challenge)
    if match is None:
        raise OciResolutionError("OCI registry did not supply a supported anonymous Bearer challenge")
    realm = match.group("realm")
    if urlsplit(realm).scheme != "https" or urlsplit(realm).username or urlsplit(realm).password:
        raise OciResolutionError("OCI token realm must be credential-free HTTPS")
    query = {"service": match.group("service")}
    if match.group("scope"):
        query["scope"] = match.group("scope")
    separator = "&" if "?" in realm else "?"
    token_data = _bounded_json(read(realm + separator + urlencode(query)), label="OCI token")
    token = token_data.get("token", token_data.get("access_token"))
    if not isinstance(token, str) or not token or len(token) > 16_384:
        raise OciResolutionError("OCI registry did not return a bounded anonymous token")
    try:
        return read(url, authorization="Bearer " + token)
    except HTTPError as error:
        raise OciResolutionError(f"OCI registry returned HTTP {error.code} after authentication") from error


def resolve_oci_pull(
    source_pull: str,
    *,
    platform: ExecutionPlatform,
    fetch: Callable[[str, str], bytes] = _public_fetch,
) -> OciResolution:
    """Resolve a source image tag to index and platform manifest digests."""

    try:
        repository, tag, source_digest = canonical_image(source_pull)
    except CwlOciImportError as error:
        raise OciResolutionError(str(error)) from error
    if tag is None and source_digest is None:
        tag = "latest"  # Docker's documented default, recorded in source_pull.
    reference = "sha256:" + source_digest if source_digest else tag
    assert reference is not None
    registry, path = repository.split("/", 1)
    base = f"https://{registry}/v2/{path}"

    def get_metadata(kind: str, digest_or_tag: str, expected: str | None = None) -> tuple[bytes, dict[str, Any]]:
        url = f"{base}/{kind}/{quote(digest_or_tag, safe=':')}"
        content = fetch(url, _ACCEPT if kind == "manifests" else "application/octet-stream")
        if expected is not None:
            _verified_digest(content, expected, label=kind)
        return content, _bounded_json(content, label=kind)

    index_bytes, index = get_metadata("manifests", reference, "sha256:" + source_digest if source_digest else None)
    index_digest = _digest(index_bytes)
    index_type = index.get("mediaType")
    expected_os, expected_arch = platform.value.split("/", 1)
    if index_type in _INDEX_TYPES:
        manifests = index.get("manifests")
        if not isinstance(manifests, list):
            raise OciResolutionError("OCI index lacks manifests")
        choices = [entry for entry in manifests if isinstance(entry, dict) and isinstance(entry.get("platform"), dict)
                   and entry["platform"].get("os") == expected_os
                   and entry["platform"].get("architecture") == expected_arch
                   and entry["platform"].get("variant") in (None, "")]
        if len(choices) != 1:
            raise OciResolutionError("OCI index does not identify exactly one requested platform")
        platform_digest = choices[0].get("digest")
        if not isinstance(platform_digest, str) or _DIGEST_RE.fullmatch(platform_digest) is None:
            raise OciResolutionError("OCI index platform digest is missing or invalid")
        _, manifest = get_metadata("manifests", platform_digest, platform_digest)
    elif index_type in _MANIFEST_TYPES:
        platform_digest, manifest = index_digest, index
    else:
        raise OciResolutionError("OCI registry returned an unsupported manifest media type")
    manifest_type = manifest.get("mediaType")
    if manifest_type not in _MANIFEST_TYPES:
        raise OciResolutionError("OCI platform manifest has unsupported media type")
    config = manifest.get("config")
    if not isinstance(config, dict) or not isinstance(config.get("digest"), str):
        raise OciResolutionError("OCI platform manifest lacks image configuration digest")
    config_digest = config["digest"]
    if _DIGEST_RE.fullmatch(config_digest) is None:
        raise OciResolutionError("OCI image configuration digest is invalid")
    _, configuration = get_metadata("blobs", config_digest, config_digest)
    if configuration.get("os") != expected_os or configuration.get("architecture") != expected_arch:
        raise OciResolutionError("OCI image configuration does not match requested platform")
    return OciResolution(
        source_pull=source_pull,
        image_index=f"{repository}@{index_digest}",
        image_platform=f"{repository}@{platform_digest}",
        platform=platform,
        index_media_type=index_type,
        manifest_media_type=manifest_type,
        config_digest=config_digest,
    )
