"""Proof-gated preparation of a generic cwltool container invocation.

Registration is explicit through a data-only catalog. Readiness and every run
require a host-local pinned runtime config; without it, the node fails closed.
The isolated audit host has demonstrated queue execution and provenance for
one image, while broader image coverage remains unverified.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated, Any, ClassVar

from pydantic import Field, StringConstraints, model_validator
import yaml  # type: ignore[import-untyped]

from bionodulo.nodes.contract.artifacts import _StrictFrozenModel
from bionodulo.nodes.contract.cwl_oci import CwlOciContract
from bionodulo.nodes.contract.cwl_reference import _UniqueKeyLoader
from bionodulo.nodes.contract.environments import Sha256Digest
from bionodulo.nodes.contract.environments import ContainerEnvironment
from bionodulo.nodes.contract.model import ExecutionKind, NodeSpec
from bionodulo.nodes.contract.outputs import collect_outputs
from bionodulo.nodes.cwl_reference_runtime import (
    CwlReferenceNode, REFERENCE_RESULT_MAX_BYTES, _build_job, _publish_outputs,
    _run_process, _strict_result,
)
from bionodulo.nodes.declarative_cwl import (
    _artifact_widget_type, _execution_timeout, _result_values, _validate_output_root,
)


class OciRuntimeUnavailable(RuntimeError):
    """The host cannot prove an immutable container execution path."""


class CwlOciRuntimeConfig(_StrictFrozenModel):
    cwltool: Path
    cwltool_sha256: Sha256Digest
    cwltool_version: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    docker: Path
    docker_sha256: Sha256Digest
    nodejs: Path | None = None
    nodejs_sha256: Sha256Digest | None = None
    nodejs_version: str | None = None
    max_cores: Annotated[int, Field(strict=True, ge=1, le=64)] = 2
    max_ram_mib: Annotated[int, Field(strict=True, ge=256, le=262_144)] = 2048

    @model_validator(mode="after")
    def _nodejs_identity(self) -> CwlOciRuntimeConfig:
        if (self.nodejs is None) != (self.nodejs_sha256 is None) or (self.nodejs is None) != (self.nodejs_version is None):
            raise ValueError("Node.js path, digest, and version must be configured together")
        return self


def configured_oci_runtime() -> CwlOciRuntimeConfig:
    """Read one explicit host-local runtime lock; absence denies readiness."""

    raw = os.environ.get("BIONODULO_OCI_RUNTIME_CONFIG", "")
    if not raw:
        raise OciRuntimeUnavailable("BIONODULO_OCI_RUNTIME_CONFIG is not configured")
    path = Path(raw)
    if not path.is_absolute() or not path.is_file() or path.is_symlink() or path.stat().st_size > 16_384:
        raise OciRuntimeUnavailable("OCI runtime config must be an absolute nonsymlink file under 16 KiB")
    try:
        return CwlOciRuntimeConfig.model_validate_json(path.read_bytes())
    except ValueError as error:
        raise OciRuntimeUnavailable(f"OCI runtime config is invalid: {error}") from error


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _trusted_executable(path: Path, expected_sha256: str, *, label: str) -> Path:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise OciRuntimeUnavailable(f"{label} must be an absolute nonsymlink executable file")
    resolved = path.resolve(strict=True)
    if resolved != path or _sha256_file(path) != expected_sha256:
        raise OciRuntimeUnavailable(f"{label} executable identity does not match its pinned digest")
    return path


def _execution_environment(config: CwlOciRuntimeConfig, *, docker_wrapper: Path | None = None) -> dict[str, str]:
    if config.docker.name != "docker":
        raise OciRuntimeUnavailable("pinned Docker executable must be named docker for cwltool")
    paths = [str((docker_wrapper or config.docker).parent), str(config.cwltool.parent)]
    if config.nodejs is not None:
        paths.append(str(config.nodejs.parent))
    paths.extend(("/usr/bin", "/bin"))
    environment = {
        "PATH": os.pathsep.join(paths),
        "PYTHONDONTWRITEBYTECODE": "1",
        "HOME": "/nonexistent",
        "DOCKER_CONFIG": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": "/tmp",
    }
    if shutil.which("docker", path=environment["PATH"]) != str(docker_wrapper or config.docker):
        raise OciRuntimeUnavailable("cwltool PATH does not resolve the pinned Docker executable")
    if config.nodejs is not None and shutil.which("node", path=environment["PATH"]) != str(config.nodejs):
        raise OciRuntimeUnavailable("cwltool PATH does not resolve the pinned Node.js executable")
    return environment


def _validated_resource_budget(contract: CwlOciContract, config: CwlOciRuntimeConfig) -> tuple[int, int]:
    """Bound cwltool's static resource request before it can reach Docker."""

    document = yaml.load(contract.source_text, Loader=_UniqueKeyLoader)
    declarations: list[dict[str, Any]] = []
    for location in ("requirements", "hints"):
        raw = document.get(location)
        if isinstance(raw, dict):
            entry = raw.get("ResourceRequirement")
            if entry is not None:
                declarations.append(entry)
        elif isinstance(raw, list):
            declarations.extend(item for item in raw if isinstance(item, dict) and item.get("class") == "ResourceRequirement")
    if len(declarations) > 1:
        raise OciRuntimeUnavailable("OCI resource declarations are ambiguous")
    cores = 1
    ram = 1024 if contract.inspection.cwl_version == "v1.0" else 256
    if declarations:
        declaration = declarations[0]
        if not isinstance(declaration, dict):
            raise OciRuntimeUnavailable("OCI ResourceRequirement must be an object")
        for key in ("coresMin", "coresMax", "ramMin", "ramMax"):
            value = declaration.get(key)
            if value is None:
                continue
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise OciRuntimeUnavailable(f"OCI {key} must be a static positive finite number")
            if key.startswith("cores"):
                cores = max(cores, math.ceil(value))
            else:
                ram = max(ram, math.ceil(value))
    if cores > config.max_cores or ram > config.max_ram_mib:
        raise OciRuntimeUnavailable("OCI source resource request exceeds configured CPU or RAM cap")
    return cores, ram


def prove_oci_runtime(contract: CwlOciContract, config: CwlOciRuntimeConfig) -> dict[str, str]:
    """Require a live daemon and the exact platform digest in its local store."""

    if contract.image_index != contract.image_platform:
        raise OciRuntimeUnavailable("OCI execution of a multiarch index requires retained index-to-platform proof")
    engine = _trusted_executable(config.cwltool, config.cwltool_sha256, label="cwltool")
    docker = _trusted_executable(config.docker, config.docker_sha256, label="Docker")
    if config.nodejs is None or config.nodejs_sha256 is None or config.nodejs_version is None:
        raise OciRuntimeUnavailable("OCI execution requires a pinned Node.js runtime")
    nodejs = _trusted_executable(config.nodejs, config.nodejs_sha256, label="Node.js")
    environment = _execution_environment(config)
    budget_cores, budget_ram = _validated_resource_budget(contract, config)
    try:
        version = subprocess.run([str(engine), "--version"], env=environment, capture_output=True, text=True, timeout=30, check=True)
        if version.stdout.strip().split()[-1] != config.cwltool_version:
            raise OciRuntimeUnavailable("cwltool version differs from pinned runtime config")
        node_version = subprocess.run(
            [str(nodejs), "--version"], env=environment, capture_output=True, text=True, timeout=30, check=True,
        )
        if node_version.stdout.strip() != config.nodejs_version:
            raise OciRuntimeUnavailable("Node.js version differs from pinned runtime config")
        daemon = subprocess.run(
            [str(docker), "info", "--format", "{{json .}}"],
            env=environment, capture_output=True, text=True, timeout=30, check=True,
        )
        daemon_info = json.loads(daemon.stdout)
        if not isinstance(daemon_info, dict):
            raise OciRuntimeUnavailable("Docker daemon identity is not an object")
        server_version = daemon_info.get("ServerVersion")
        if not isinstance(server_version, str) or not server_version:
            raise OciRuntimeUnavailable("Docker daemon did not report a server version")
        architectures = {"linux/amd64": {"x86_64", "amd64"}, "linux/arm64": {"aarch64", "arm64"}}
        if daemon_info.get("OSType") != "linux" or daemon_info.get("Architecture") not in architectures[contract.platform.value]:
            raise OciRuntimeUnavailable(f"Docker daemon is not the requested {contract.platform.value} platform")
        inspection = subprocess.run(
            [str(docker), "image", "inspect", contract.image_platform, "--format", "{{json .RepoDigests}}"],
            env=environment, capture_output=True, text=True, timeout=30, check=True,
        )
        digests = json.loads(inspection.stdout)
        if not isinstance(digests, list) or contract.image_platform not in digests:
            raise OciRuntimeUnavailable("exact OCI platform image digest is absent from local Docker store")
    except (OSError, subprocess.SubprocessError, ValueError, IndexError) as error:
        raise OciRuntimeUnavailable(f"OCI runtime proof failed: {error}") from error
    return {
        "cwltool_sha256": config.cwltool_sha256,
        "cwltool_version": config.cwltool_version,
        "docker_sha256": config.docker_sha256,
        "docker_server_version": server_version,
        "docker_server_platform": contract.platform.value,
        "nodejs_sha256": config.nodejs_sha256 or "",
        "nodejs_version": config.nodejs_version or "",
        "image_index": contract.image_index,
        "image_platform": contract.image_platform,
        "source_sha256": contract.source_sha256,
        "resource_cap_cores": str(config.max_cores),
        "resource_cap_ram_mib": str(config.max_ram_mib),
        "source_request_cores_upper": str(budget_cores),
        "source_request_ram_mib_upper": str(budget_ram),
    }


def prepare_oci_invocation(
    contract: CwlOciContract,
    config: CwlOciRuntimeConfig,
    *,
    workspace: Path,
    job_path: Path,
) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """Prepare a no-pull command only after the live digest proof succeeds."""

    receipt = prove_oci_runtime(contract, config)
    environment = _execution_environment(config)
    if not workspace.is_absolute() or not workspace.is_dir() or workspace.is_symlink():
        raise OciRuntimeUnavailable("OCI workspace must be an existing absolute nonsymlink directory")
    if not job_path.is_absolute() or not job_path.is_file() or job_path.is_symlink():
        raise OciRuntimeUnavailable("OCI job must be an existing absolute nonsymlink file")
    if not job_path.resolve(strict=True).is_relative_to(workspace.resolve(strict=True)):
        raise OciRuntimeUnavailable("OCI job must be staged inside the execution workspace")
    effective_source, effective_sha256 = contract.effective_source()
    descriptor = workspace / "tool.oci.cwl"
    if descriptor.exists():
        raise OciRuntimeUnavailable("refusing to overwrite an existing OCI descriptor")
    descriptor.write_bytes(effective_source)
    if _sha256_file(descriptor) != effective_sha256:
        raise OciRuntimeUnavailable("effective OCI descriptor changed while staging")
    outdir = workspace / "engine-output"
    outdir.mkdir(mode=0o700, exist_ok=False)
    temporary = workspace / "engine-tmp"
    temporary.mkdir(mode=0o700, exist_ok=False)
    cid_directory = workspace / "container-ids"
    cid_directory.mkdir(mode=0o700, exist_ok=False)
    attempt_label = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:32]
    wrapper_dir = workspace / "docker-cli"
    wrapper_dir.mkdir(mode=0o700, exist_ok=False)
    wrapper = wrapper_dir / "docker"
    docker_path = shlex.quote(str(config.docker))
    wrapper.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = run ]; then\n"
        "  shift\n"
        f"  exec {docker_path} run --label org.bionodulo.oci.attempt={attempt_label} \"$@\"\n"
        "fi\n"
        f"exec {docker_path} \"$@\"\n",
        encoding="ascii",
    )
    wrapper.chmod(0o700)
    environment = _execution_environment(config, docker_wrapper=wrapper)
    receipt["docker_wrapper_sha256"] = _sha256_file(wrapper)
    receipt["attempt_label"] = attempt_label
    receipt["effective_source_sha256"] = effective_sha256
    return [
        str(config.cwltool), "--disable-pull", "--disable-color", "--custom-net", "none",
        "--strict-memory-limit", "--strict-cpu-limit", "--rm-container",
        "--cidfile-dir", str(cid_directory),
        "--outdir", str(outdir),
        "--tmpdir-prefix", str(temporary / "tmp-"),
        "--tmp-outdir-prefix", str(temporary / "out-"),
        str(descriptor), str(job_path),
    ], receipt, environment


_CONTAINER_ID_RE = re.compile(r"^[0-9a-f]{64}$")


def _cleanup_oci_containers(
    root: Path, config: CwlOciRuntimeConfig, environment: dict[str, str], attempt_label: str,
) -> list[str]:
    """Remove containers by both cidfile and daemon-side attempt label."""

    directory = root / "container-ids"
    if re.fullmatch(r"[0-9a-f]{32}", attempt_label) is None:
        raise OciRuntimeUnavailable("OCI attempt label is missing or invalid")
    files = sorted(directory.iterdir()) if directory.is_dir() and not directory.is_symlink() else []
    if len(files) > 8:
        raise OciRuntimeUnavailable("OCI attempt recorded too many container IDs")
    recorded: set[str] = set()
    for path in files:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 128:
            raise OciRuntimeUnavailable("OCI container ID receipt is not a bounded regular file")
        cid = path.read_text(encoding="ascii").strip()
        if _CONTAINER_ID_RE.fullmatch(cid) is None:
            raise OciRuntimeUnavailable("OCI container ID receipt is malformed")
        recorded.add(cid)
    listed = subprocess.run(
        [str(config.docker), "container", "ls", "-aq", "--no-trunc", "--filter", f"label=org.bionodulo.oci.attempt={attempt_label}"],
        env=environment, capture_output=True, text=True, timeout=15, check=True,
    )
    for cid in listed.stdout.splitlines():
        if _CONTAINER_ID_RE.fullmatch(cid) is None:
            raise OciRuntimeUnavailable("Docker returned a malformed OCI container ID")
        recorded.add(cid)
    cleaned: list[str] = []
    for cid in sorted(recorded):
        check = subprocess.run(
            [str(config.docker), "container", "inspect", cid, "--format", "{{json .Id}}|{{json .Config.Labels}}"],
            env=environment, capture_output=True, text=True, timeout=15,
        )
        if check.returncode == 0:
            try:
                identity, labels = check.stdout.strip().split("|", 1)
                inspected_id = json.loads(identity)
                inspected_labels = json.loads(labels)
            except (ValueError, json.JSONDecodeError) as error:
                raise OciRuntimeUnavailable("Docker container identity metadata is invalid") from error
            if inspected_id != cid or not isinstance(inspected_labels, dict) or inspected_labels.get(
                "org.bionodulo.oci.attempt"
            ) != attempt_label:
                raise OciRuntimeUnavailable("Docker container is not owned by this OCI attempt")
            removal = subprocess.run(
                [str(config.docker), "rm", "-f", cid],
                env=environment, capture_output=True, text=True, timeout=30,
            )
            if removal.returncode != 0:
                raise OciRuntimeUnavailable(f"failed to remove OCI container {cid[:12]}")
            cleaned.append(cid)
        elif "No such object" not in check.stderr and "No such container" not in check.stderr:
            raise OciRuntimeUnavailable("Docker could not prove the OCI container absent")
    remaining = subprocess.run(
        [str(config.docker), "container", "ls", "-aq", "--no-trunc", "--filter", f"label=org.bionodulo.oci.attempt={attempt_label}"],
        env=environment, capture_output=True, text=True, timeout=15, check=True,
    )
    if remaining.stdout.strip():
        raise OciRuntimeUnavailable("OCI attempt still has daemon-side containers after cleanup")
    return cleaned


def _bounded_tail(path: Path, maximum: int = 64 * 1024) -> str:
    if not path.is_file() or path.is_symlink():
        return ""
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        stream.seek(max(0, stream.tell() - maximum))
        return stream.read(maximum).decode("utf-8", errors="replace")


class CwlOciNode(CwlReferenceNode):
    """Opt-in generic CWL artifact bridge using a proven OCI runtime."""

    CONTRACT_SPEC: ClassVar[NodeSpec]
    EXECUTOR_CACHE_POLICY = "always_run"

    @classmethod
    def metadata(cls) -> dict[str, Any]:
        from bionodulo.nodes.base import BaseNode

        metadata = BaseNode.metadata.__func__(cls)  # type: ignore[attr-defined]
        contract = cls.CONTRACT_SPEC.cwl_oci
        assert contract is not None
        metadata["runtime_descriptor"] = {
            "profile": contract.profile,
            "source_uri": contract.source_uri,
            "source_sha256": contract.source_sha256,
            "image_index": contract.image_index,
            "image_platform": contract.image_platform,
            "verification": contract.verification,
            "contract_digest": cls.CONTRACT_DIGEST,
        }
        return metadata

    async def run(self, **kwargs: Any) -> tuple[object, ...]:
        context = kwargs.pop("context", None)
        explicit_output_dir = kwargs.pop("output_dir", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        contract = self.CONTRACT_SPEC.cwl_oci
        if contract is None:
            raise ValueError("OCI node lacks its source contract")
        root_value = explicit_output_dir or getattr(context, "node_dir", None)
        base_root = _validate_output_root(Path(root_value or "."))
        root = _validate_output_root(Path(tempfile.mkdtemp(prefix=".cwl-oci-attempt-", dir=base_root)))
        config: CwlOciRuntimeConfig | None = None
        environment: dict[str, str] | None = None
        runtime_receipt: dict[str, str] = {}
        try:
            staging = root / "inputs"
            staging.mkdir(mode=0o700)
            # The OCI source exposes the same validated mapping projection as
            # CwlReferenceContract; only runtime/environment fields differ.
            job, input_receipts = _build_job(contract, kwargs, staging)  # type: ignore[arg-type]
            job_path = root / "job.json"
            job_path.write_bytes(json.dumps(job, allow_nan=False, sort_keys=True).encode("utf-8"))
            config = configured_oci_runtime()
            command, runtime_receipt, environment = prepare_oci_invocation(
                contract, config, workspace=root, job_path=job_path,
            )
            if "external_schema_not_loaded" in contract.unfulfilled_hints:
                command.insert(1, "--skip-schemas")
            result_path = root / "cwltool-result.json"
            await _run_process(
                command, cwd=root, context=context, env=environment, replace_env=True,
                stdout_path=result_path, stderr_path=root / "cwltool.stderr.log",
                stdout_binary=True, stdout_max_bytes=REFERENCE_RESULT_MAX_BYTES,
                timeout=_execution_timeout(context),
            )
            result = _strict_result(result_path)
            output_receipts = _publish_outputs(contract, result, root)  # type: ignore[arg-type]
            collected = collect_outputs(self.CONTRACT_SPEC.outputs, root, conditions=kwargs)
            runtime_receipt["container_cleanup_count"] = str(len(_cleanup_oci_containers(
                root, config, environment, runtime_receipt["attempt_label"],
            )))
        except BaseException as error:
            cleanup_error: str | None = None
            if config is not None and environment is not None and "attempt_label" in runtime_receipt:
                try:
                    _cleanup_oci_containers(root, config, environment, runtime_receipt["attempt_label"])
                except (OSError, ValueError, subprocess.SubprocessError, OciRuntimeUnavailable) as cleanup_failure:
                    cleanup_error = str(cleanup_failure)[:4096]
            failure = {
                "profile": contract.profile,
                "source_uri": contract.source_uri,
                "source_sha256": contract.source_sha256,
                "image_platform": contract.image_platform,
                "runtime": runtime_receipt,
                "error_type": type(error).__name__,
                "error": str(error)[:4096],
                "cleanup_error": cleanup_error,
                "stderr_tail": _bounded_tail(root / "cwltool.stderr.log"),
                "result_tail": _bounded_tail(root / "cwltool-result.json"),
            }
            failure_path = base_root / f"{root.name}.failure.json"
            with failure_path.open("x", encoding="utf-8") as stream:
                json.dump(failure, stream, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
            if context is not None and isinstance(getattr(context, "run_metadata", None), dict):
                context.run_metadata.setdefault("cwl_oci_failures", {})[str(getattr(context, "node_id", self.NODE_ID))] = {
                    "receipt": failure_path.name,
                    "source_sha256": contract.source_sha256,
                    "image_platform": contract.image_platform,
                    "error_type": type(error).__name__,
                    "cleanup_error": cleanup_error,
                }
            if root.parent != base_root or not root.name.startswith(".cwl-oci-attempt-") or root.is_symlink():
                raise RuntimeError("refusing to clean an invalid OCI attempt workspace")
            shutil.rmtree(root)
            if cleanup_error is not None:
                raise OciRuntimeUnavailable(f"OCI container cleanup failed: {cleanup_error}") from error
            raise
        if context is not None and isinstance(getattr(context, "run_metadata", None), dict):
            environment_contract = self.CONTRACT_SPEC.environment
            assert isinstance(environment_contract, ContainerEnvironment)
            context.run_metadata.setdefault("cwl_oci", {})[str(getattr(context, "node_id", self.NODE_ID))] = {
                "profile": contract.profile,
                "source_uri": contract.source_uri,
                "source_sha256": contract.source_sha256,
                "source_size_bytes": contract.source_size_bytes,
                "source_docker_pull": contract.source_docker_pull,
                "contract_digest": self.CONTRACT_DIGEST,
                "environment_digest": environment_contract.environment_digest(),
                "input_staging": list(input_receipts),
                "output_publication": list(output_receipts),
                "attempt_workspace": root.name,
                **runtime_receipt,
            }
        return _result_values(self.CONTRACT_SPEC.outputs, root, collected)


def bind_cwl_oci_node(spec: NodeSpec) -> type[CwlOciNode]:
    validated = NodeSpec.model_validate(spec)
    contract = validated.cwl_oci
    environment = validated.environment
    if contract is None or not isinstance(environment, ContainerEnvironment):
        raise ValueError("OCI node requires a locked source and container environment")
    if validated.execution_factory != "bionodulo.nodes.cwl_oci_runtime:CwlOciNode":
        raise ValueError("OCI node factory differs from shared container adapter")
    if validated.execution_kind is not ExecutionKind.CONTAINER or not environment.is_fully_locked:
        raise ValueError("OCI node must have a fully locked container execution environment")
    attributes: dict[str, object] = {
        "__module__": __name__,
        "CONTRACT_SPEC": validated,
        "NODE_ID": validated.identity.machine_id,
        "DISPLAY_NAME": validated.presentation.display_name,
        "CATEGORY": "/".join(validated.presentation.palette_path),
        "DESCRIPTION": validated.presentation.description,
        "RETURN_TYPES": tuple(_artifact_widget_type(output.artifact_type) for output in validated.outputs),
        "RETURN_NAMES": tuple(output.port_id for output in validated.outputs),
        "REQUIRES_EXTERNAL_TOOLS": True,
        "REQUIRED_EXECUTABLES": [],
        "REQUIRED_CONDA_PACKAGES": [],
        "ENVIRONMENT": {
            "type": "declarative_oci", "name": environment.environment_id,
            "digest": environment.environment_digest(), "image": contract.image_platform,
        },
        "VERSION": "1.0.0+oci." + contract.source_sha256[7:19] + "." + contract.image_platform.rsplit(":", 1)[-1][:12],
        "EXPERIMENTAL": True,
        "CONTRACT_DIGEST": validated.contract_digest(),
        "SOURCE_DIGEST": contract.source_sha256,
        "SOURCE_DIGESTS": (contract.source_sha256,),
        "SOURCE_URI": contract.source_uri,
    }
    return type("CwlOciNode_" + validated.identity.machine_id, (CwlOciNode,), attributes)
