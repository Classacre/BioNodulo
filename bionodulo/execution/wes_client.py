"""GA4GH Workflow Execution Service (WES) 1.1 client with custodian pinning.

Aim B data-sovereignty groundwork: BioNodulo must be able to ship workflows to
remote WES endpoints without ever letting sensitive inputs leave their
custodian's infrastructure. This module provides:

- :class:`WESClient` — a stdlib-only (``urllib``) client for the WES 1.1
  endpoints (``GET /service-info``, ``POST /runs``, ``GET /runs/{run_id}``,
  ``GET /runs/{run_id}/status``, ``POST /runs/{run_id}/cancel``). ``POST
  /runs`` is sent as ``multipart/form-data`` per the WES 1.1 spec, encoded
  manually because ``requests`` is not a guaranteed dependency.
- :class:`DRSCustodianPolicy` + :func:`enforce_custodian_policy` — the
  pre-flight gate that refuses to run when a sensitive input is not referenced
  by a ``drs://`` URI, or when the chosen WES endpoint is not the pinned
  custodian for that URI.
- :func:`build_wes_request` — compiles a BioNodulo workflow (nodes/edges) to
  a WES run request via the existing converters, attaching the exported
  files as ``workflow_attachment`` entries.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from urllib.parse import urlparse, quote

WORKFLOW_TYPES = ("CWL", "snakemake", "nextflow", "galaxy")
"""Workflow types accepted by :meth:`WESClient.run_workflow` (per WES 1.1)."""

_DRS_SCHEME = "drs://"


class WESClientError(Exception):
    """A WES HTTP request failed (non-2xx or unreachable endpoint)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CustodianPinViolation(Exception):
    """A run request would move sensitive data off its pinned custodian."""

    def __init__(
        self,
        message: str,
        *,
        input_ref: str | None = None,
        drs_uri: str | None = None,
        required_host: str | None = None,
    ) -> None:
        super().__init__(message)
        self.input_ref = input_ref
        self.drs_uri = drs_uri
        self.required_host = required_host


def encode_multipart(
    fields: list[tuple[str, str]],
    files: list[tuple[str, str | bytes]],
) -> tuple[bytes, str]:
    """Encode ``multipart/form-data`` fields and file parts with stdlib only.

    File parts are emitted with the WES spec's ``workflow_attachment`` part
    name so remote endpoints treat them as workflow attachments.

    Args:
        fields: Ordered ``(name, value)`` form fields.
        files: ``(filename, content)`` attachment parts.

    Returns:
        ``(body, content_type)`` ready for an ``urllib`` POST.
    """
    boundary = "bionodulo-wes-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.append(
            (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode("utf-8")
        )
    for filename, content in files:
        chunks.append(
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="workflow_attachment"; '
                f'filename="{filename}"\r\n'
                "Content-Type: application/octet-stream\r\n"
                "\r\n"
            ).encode("utf-8")
        )
        chunks.append(content.encode("utf-8") if isinstance(content, str) else content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    content_type = f"multipart/form-data; boundary={boundary}"
    return b"".join(chunks), content_type


class WESClient:
    """Minimal GA4GH WES 1.1 client built on ``urllib``.

    Args:
        base_url: WES API root, including the versioned path prefix
            (e.g. ``https://wes.example.org/ga4gh/wes/v1``).
        timeout: Per-request timeout in seconds.
        auth_token: Optional bearer token sent as ``Authorization: Bearer``.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        auth_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token

    # -- HTTP plumbing ------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        content_type: str | None = None,
    ) -> Any:
        request = urllib.request.Request(self._url(path), data=data, method=method)
        if self.auth_token:
            request.add_header("Authorization", f"Bearer {self.auth_token}")
        if content_type:
            request.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except OSError:
                detail = ""
            raise WESClientError(
                f"WES {method} {path} failed with HTTP {exc.code}: {detail}",
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise WESClientError(f"WES {method} {path} unreachable: {exc.reason}") from exc
        if not raw:
            return {}
        return json.loads(raw)

    # -- WES 1.1 endpoints ---------------------------------------------------

    def get_service_info(self) -> dict[str, Any]:
        """``GET /service-info`` — service metadata and supported versions."""
        return self._request("GET", "service-info")

    def run_workflow(
        self,
        workflow_params: dict[str, Any],
        workflow_type: str,
        workflow_type_version: str,
        workflow_url: str = "",
        workflow_attachment: list[tuple[str, str | bytes]] | None = None,
        tags: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """``POST /runs`` — start a workflow run.

        Either ``workflow_url`` or ``workflow_attachment`` must be provided
        (the latter per WES 1.1 with ``workflow_url`` naming the relpath of
        the main document inside the attachments).

        Args:
            workflow_params: Input values, serialized as a JSON string field.
            workflow_type: One of :data:`WORKFLOW_TYPES`.
            workflow_type_version: Version string for the workflow type.
            workflow_url: URL (or attachment relpath) of the main document.
            workflow_attachment: ``(filename, content)`` exported files.
            tags: Optional run tags, serialized as a JSON string field.

        Returns:
            The WES response, at minimum ``{"run_id": ...}``.

        Raises:
            ValueError: If the arguments cannot form a valid WES run request.
            WESClientError: If the endpoint rejects the request.
        """
        if workflow_type not in WORKFLOW_TYPES:
            raise ValueError(f"Unsupported workflow_type {workflow_type!r}; expected one of {WORKFLOW_TYPES}")
        if not workflow_url and not workflow_attachment:
            raise ValueError("run_workflow requires workflow_url or workflow_attachment")
        fields: list[tuple[str, str]] = [
            ("workflow_params", json.dumps(workflow_params)),
            ("workflow_type", workflow_type),
            ("workflow_type_version", workflow_type_version),
        ]
        if workflow_url:
            fields.append(("workflow_url", workflow_url))
        if tags:
            fields.append(("tags", json.dumps(tags)))
        body, content_type = encode_multipart(fields, workflow_attachment or [])
        return self._request("POST", "runs", data=body, content_type=content_type)

    def get_run_status(self, run_id: str) -> dict[str, Any]:
        """``GET /runs/{run_id}/status`` — cheap poll of run state."""
        return self._request("GET", f"runs/{quote(run_id, safe='')}/status")

    def get_run_log(self, run_id: str) -> dict[str, Any]:
        """``GET /runs/{run_id}`` — full run log (inputs, outputs, task logs)."""
        return self._request("GET", f"runs/{quote(run_id, safe='')}")

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        """``POST /runs/{run_id}/cancel`` — request cancellation of a run."""
        return self._request("POST", f"runs/{quote(run_id, safe='')}/cancel", data=b"")


# ---------------------------------------------------------------------------
# DRS custodian pinning (data-sovereignty pre-flight gate)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DRSCustodianPolicy:
    """Maps DRS URI prefixes to the WES endpoint host that must run them.

    Attributes:
        pin_map: Mapping of DRS URI prefix (e.g. ``drs://fid.example``) to the
            hostname of the WES endpoint allowed to receive that data.
    """

    pin_map: dict[str, str] = field(default_factory=dict)

    def custodian_for(self, drs_uri: str) -> str | None:
        """Return the pinned host for the longest matching DRS prefix, if any."""
        best_prefix = ""
        best_host: str | None = None
        for prefix, host in self.pin_map.items():
            if drs_uri.startswith(prefix) and len(prefix) > len(best_prefix):
                best_prefix = prefix
                best_host = host
        return best_host


def _input_value(spec: Any) -> Any:
    """Extract the current value from a node input spec (``{"value": ...}`` or raw)."""
    if isinstance(spec, dict):
        return spec.get("value", "")
    return spec


def _is_sensitive(node_id: str, port: str, spec: Any, workflow: dict[str, Any]) -> bool:
    """Whether a node input is flagged sensitive.

    Recognises an explicit ``"sensitive": true`` flag on the input spec, or an
    entry in the workflow-level ``sensitive_inputs`` list — either a bare node
    id (all of the node's inputs) or ``"node_id/port"``.
    """
    if isinstance(spec, dict) and spec.get("sensitive"):
        return True
    marked = workflow.get("sensitive_inputs")
    if isinstance(marked, (list, tuple, set)):
        return f"{node_id}/{port}" in marked or node_id in marked
    return False


def enforce_custodian_policy(
    policy: DRSCustodianPolicy,
    workflow: dict[str, Any],
    input_refs: dict[str, str],
    endpoint_url: str,
) -> dict[str, Any]:
    """Verify a run keeps every sensitive input on its pinned custodian.

    For each sensitive node input, resolve its reference through
    ``input_refs`` (current input value -> ``drs://`` URI) and check that:

    1. the resolved reference is a ``drs://`` URI — never a bare local path
       or an ``http(s)://`` URL, and
    2. the longest matching prefix in ``policy.pin_map`` pins that URI to the
       host of ``endpoint_url``.

    Args:
        policy: Prefix -> required endpoint host pins.
        workflow: BioNodulo workflow dict with ``nodes`` (and ``edges``).
        input_refs: Mapping of current input file references to DRS URIs.
        endpoint_url: The chosen custodian WES endpoint (base URL).

    Returns:
        A resolved run request payload: ``{"endpoint": ..., "workflow_params":
        {node_id/port: resolved reference, ...}}`` where sensitive inputs are
        replaced by their DRS URIs and other inputs pass through unchanged.

    Raises:
        CustodianPinViolation: Naming the offending input (and, where known,
            the required endpoint) when either check fails.
        ValueError: If ``endpoint_url`` has no host component.
    """
    target_host = urlparse(endpoint_url).hostname
    if not target_host:
        raise ValueError(f"endpoint_url must be an absolute URL with a host, got {endpoint_url!r}")

    workflow_params: dict[str, Any] = {}
    for node in workflow.get("nodes", []):
        node_id = str(node.get("id", ""))
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        for port, spec in inputs.items():
            key = f"{node_id}/{port}"
            value = _input_value(spec)
            resolved: Any = input_refs.get(value, value) if isinstance(value, str) else value
            if _is_sensitive(node_id, str(port), spec, workflow):
                if not isinstance(resolved, str) or not resolved.startswith(_DRS_SCHEME):
                    raise CustodianPinViolation(
                        f"Sensitive input '{key}' is referenced by {resolved!r}, but data-sovereignty "
                        f"policy requires a DRS URI ({_DRS_SCHEME}...) so the input never leaves its "
                        f"custodian as a local path or plain http URL",
                        input_ref=key,
                        drs_uri=resolved if isinstance(resolved, str) else None,
                    )
                required_host = policy.custodian_for(resolved)
                if required_host is None:
                    raise CustodianPinViolation(
                        f"Sensitive input '{key}' resolves to {resolved}, which no custodian pin "
                        f"covers; refusing to submit unpinned sensitive data",
                        input_ref=key,
                        drs_uri=resolved,
                    )
                if required_host.lower() != target_host.lower():
                    raise CustodianPinViolation(
                        f"Sensitive input '{key}' resolves to {resolved}, pinned to custodian "
                        f"'{required_host}', but the run targets endpoint host '{target_host}'; "
                        f"refusing to execute outside the custodian",
                        input_ref=key,
                        drs_uri=resolved,
                        required_host=required_host,
                    )
            workflow_params[key] = resolved
    return {"endpoint": endpoint_url, "workflow_params": workflow_params}


# ---------------------------------------------------------------------------
# BioNodulo workflow -> WES run request
# ---------------------------------------------------------------------------

_CONVERTER_SPECS: dict[str, tuple[str, str, str]] = {
    # converter -> (WES workflow_type, workflow_type_version, main document)
    "cwl": ("CWL", "v1.2", "workflow.cwl"),
    "snakemake": ("snakemake", "7", "Snakefile"),
    "nextflow": ("nextflow", "22.10.0", "main.nf"),
    "galaxy": ("galaxy", "21.09", "workflow.ga"),
}


def build_wes_request(
    workflow: dict[str, Any],
    converter: Literal["cwl", "snakemake", "nextflow", "galaxy"] = "cwl",
) -> dict[str, Any]:
    """Compile a BioNodulo workflow to a WES run request payload.

    Converter imports are lazy so this module stays importable standalone
    (the converter package drags in the node registry).

    Args:
        workflow: BioNodulo workflow dict with ``nodes`` and ``edges``.
        converter: Which exporter to use; CWL exports one file per node plus
            the main ``workflow.cwl``, the others export a single document.

    Returns:
        A payload matching :meth:`WESClient.run_workflow` keyword arguments:
        ``workflow_type``, ``workflow_type_version``, ``workflow_url``
        (relpath of the main document), ``workflow_params`` (unconnected
        inputs keyed by ``node_id/port``), ``workflow_attachment`` and
        ``tags``.
    """
    # Lazy: bionodulo.converter pulls the node registry; keep this module light.
    from bionodulo.converter import (
        export_to_cwl,
        export_to_galaxy,
        export_to_nextflow,
        export_to_snakemake,
    )
    from bionodulo.converter.edge_utils import edge_target, edge_target_port

    if converter not in _CONVERTER_SPECS:
        raise ValueError(f"Unknown converter {converter!r}; expected one of {sorted(_CONVERTER_SPECS)}")
    workflow_type, type_version, main_name = _CONVERTER_SPECS[converter]

    attachments: list[tuple[str, str]]
    if converter == "cwl":
        exported = export_to_cwl(workflow)
        attachments = sorted(exported.items())
    else:
        string_exporters: dict[str, Callable[[dict[str, Any]], str]] = {
            "snakemake": export_to_snakemake,
            "nextflow": export_to_nextflow,
            "galaxy": export_to_galaxy,
        }
        attachments = [(main_name, string_exporters[converter](workflow))]
    if not any(filename == main_name for filename, _ in attachments):
        raise ValueError(f"Converter {converter!r} did not produce the main document {main_name!r}")

    connected = {(str(edge_target(edge)), edge_target_port(edge)) for edge in workflow.get("edges", [])}
    workflow_params: dict[str, Any] = {}
    for node in workflow.get("nodes", []):
        node_id = str(node.get("id", ""))
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        for port, spec in inputs.items():
            if (node_id, str(port)) in connected:
                continue
            workflow_params[f"{node_id}/{port}"] = _input_value(spec)

    return {
        "workflow_type": workflow_type,
        "workflow_type_version": type_version,
        "workflow_url": main_name,
        "workflow_params": workflow_params,
        "workflow_attachment": attachments,
        "tags": {
            "bionodulo:converter": converter,
            "bionodulo:workflow_id": str(workflow.get("id", "")),
        },
    }
