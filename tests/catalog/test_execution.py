from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

import bionodulo.nodes.contract.execution as execution
from bionodulo.nodes.contract.environments import ExecutionPlatform


SECRET_BASE_NAMES = (
    "AUTH",
    "AUTHORIZATION",
    "COOKIE",
    "COOKIES",
    "CREDENTIAL",
    "CREDENTIALS",
    "PASSWORD",
    "PASSWORDS",
    "SECRET",
    "SECRETS",
    "TOKEN",
    "TOKENS",
    "KEY",
    "KEYS",
    "ACCESS_KEY",
    "API_KEY",
    "CLIENT_SECRET",
    "PRIVATE_KEY",
)
SECRET_ENVIRONMENT_NAMES = (*SECRET_BASE_NAMES, *(f"SERVICE_{name}" for name in SECRET_BASE_NAMES))
SECRET_HEADER_NAMES = tuple(
    (
        name.lower().replace("_", "-"),
        f"x-{name.lower().replace('_', '-')}",
    )
    for name in SECRET_BASE_NAMES
)
SECRET_HEADER_NAMES = tuple(name for pair in SECRET_HEADER_NAMES for name in pair)
SECRET_QUERY_NAMES = (
    *tuple(name.lower() for name in SECRET_BASE_NAMES),
    *(f"filter_{name.lower()}" for name in SECRET_BASE_NAMES),
)
NON_SECRET_NAMES = ("MONKEY", "HOCKEY", "TURKEY", "KEYSTONE")

_ALLOWED_CONTRACT_IMPORT_MODULES = frozenset(
    {
        "__future__",
        "bionodulo.nodes.contract._package_identity",
        "bionodulo.nodes.contract.artifacts",
        "bionodulo.nodes.contract.environments",
        "enum",
        "hashlib",
        "ipaddress",
        "json",
        "math",
        "pydantic",
        "re",
        "typing",
        "urllib.parse",
    }
)
_PROHIBITED_CALLS = frozenset(
    {
        "__import__",
        "builtins.__import__",
        "importlib.import_module",
        "os.popen",
        "os.system",
        "shlex.join",
    }
)
_PROHIBITED_MODULE_PREFIXES = (
    "aiohttp",
    "aiodocker",
    "apptainer",
    "bionodulo.execution",
    "bionodulo.environments",
    "bionodulo.manager.runtime_installer",
    "bionodulo.nodes.base",
    "bionodulo.nodes.builtin",
    "bionodulo.nodes.command_node",
    "bionodulo.nodes.legacy",
    "bionodulo.nodes.registry",
    "bionodulo.nodes.types",
    "containerd",
    "curl_cffi",
    "docker",
    "http.client",
    "httpcore",
    "httplib2",
    "httpx",
    "kubernetes",
    "legacy",
    "podman",
    "pycurl",
    "requests",
    "shlex",
    "singularity",
    "spython",
    "subprocess",
    "urllib.request",
    "urllib3",
)


def _dotted_ast_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_ast_name(node.value)
        if parent is not None:
            return f"{parent}.{node.attr}"
    return None


def _expand_ast_binding(value: str, bindings: dict[str, str]) -> str:
    first, separator, remainder = value.partition(".")
    seen: set[str] = set()
    while first in bindings and first not in seen:
        seen.add(first)
        replacement = bindings[first]
        value = replacement + (f".{remainder}" if separator else "")
        first, separator, remainder = value.partition(".")
    return value


def _is_prohibited_reference(value: str) -> bool:
    return (
        value in _PROHIBITED_CALLS
        or value == "_shell_join"
        or value.endswith("._shell_join")
        or any(value == prefix or value.startswith(prefix + ".") for prefix in _PROHIBITED_MODULE_PREFIXES)
    )


def _contract_ast_violations(source: str, *, filename: str) -> tuple[str, ...]:
    tree = ast.parse(source, filename=filename)
    bindings: dict[str, str] = {}
    violations: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in _ALLOWED_CONTRACT_IMPORT_MODULES:
                    violations.add(f"{filename}:{node.lineno}: prohibited import {alias.name}")
                local_name = alias.asname or alias.name.split(".", 1)[0]
                bindings[local_name] = alias.name if alias.asname else local_name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level or module not in _ALLOWED_CONTRACT_IMPORT_MODULES:
                violations.add(f"{filename}:{node.lineno}: prohibited import {module or '<relative>'}")
            for alias in node.names:
                if alias.name == "*":
                    violations.add(f"{filename}:{node.lineno}: wildcard import")
                    continue
                bindings[alias.asname or alias.name] = f"{module}.{alias.name}"

    assignments = sorted(
        (node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))),
        key=lambda node: (node.lineno, node.col_offset),
    )
    for node in assignments:
        dotted = _dotted_ast_name(node.value)
        if dotted is None:
            continue
        resolved = _expand_ast_binding(dotted, bindings)
        targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
        for target in targets:
            if isinstance(target, ast.Name):
                bindings[target.id] = resolved

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_shell_join":
            violations.add(f"{filename}:{node.lineno}: prohibited helper _shell_join")
        if isinstance(node, ast.Call):
            dotted = _dotted_ast_name(node.func)
            if dotted is None:
                continue
            resolved = _expand_ast_binding(dotted, bindings)
            if _is_prohibited_reference(resolved):
                violations.add(f"{filename}:{node.lineno}: prohibited call {resolved}")

    return tuple(sorted(violations))


def resources(**updates: object) -> execution.ResourceSpec:
    values: dict[str, object] = {
        "cpus": 2,
        "memory_gib": 4.0,
        "scratch_disk_gib": 8.0,
        "wall_timeout_seconds": 3600,
        "gpu_count": 0,
        "gpu_type": None,
        "allowed_platforms": (ExecutionPlatform.LINUX_AMD64,),
    }
    values.update(updates)
    return execution.ResourceSpec(**values)


def retry_exit_codes() -> execution.RetryPolicy:
    return execution.RetryPolicy(
        attempts=3,
        initial_backoff_seconds=1.0,
        maximum_backoff_seconds=4.0,
        multiplier=2.0,
        jitter_seconds=0.25,
        exit_codes=(1, 2),
    )


def checkpoint() -> execution.CheckpointPolicy:
    return execution.CheckpointPolicy(
        mode=execution.CheckpointMode.PROCESS_SIGNAL,
        signal=execution.CheckpointSignal.SIGUSR1,
        grace_seconds=30,
        relative_path="checkpoints/state.json",
    )


def argv_plan(**updates: object) -> execution.ArgvPlan:
    values: dict[str, object] = {
        "executable": "samtools",
        "arguments": ("view", "-b", "input.bam"),
        "resources": resources(),
    }
    values.update(updates)
    return execution.ArgvPlan(**values)


def pipeline_plan(**updates: object) -> execution.PipelinePlan:
    values: dict[str, object] = {
        "stages": (
            execution.PipelineStage(
                stage_id="read",
                executable="samtools",
                arguments=("view", "input.bam"),
            ),
            execution.PipelineStage(
                stage_id="sort",
                executable="samtools-sort",
                arguments=("-o", "sorted.bam"),
            ),
        ),
        "resources": resources(),
    }
    values.update(updates)
    return execution.PipelinePlan(**values)


def test_resource_spec_is_explicit_bounded_and_hashable() -> None:
    spec = resources(
        gpu_count=1,
        gpu_type="nvidia-a100",
        allowed_platforms=(
            ExecutionPlatform.LINUX_AMD64,
            ExecutionPlatform.LINUX_ARM64,
        ),
    )

    assert spec.cpus == 2
    assert spec.allowed_platforms[1] is ExecutionPlatform.LINUX_ARM64
    assert hash(spec)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("cpus", True),
        ("cpus", 0),
        ("cpus", 257),
        ("memory_gib", True),
        ("memory_gib", 4),
        ("memory_gib", 0.0),
        ("memory_gib", math.nan),
        ("memory_gib", math.inf),
        ("scratch_disk_gib", -1.0),
        ("scratch_disk_gib", -math.inf),
        ("wall_timeout_seconds", True),
        ("wall_timeout_seconds", 0),
        ("wall_timeout_seconds", 604801),
        ("gpu_count", True),
        ("gpu_count", -1),
        ("allowed_platforms", ()),
        ("allowed_platforms", [ExecutionPlatform.LINUX_AMD64]),
        (
            "allowed_platforms",
            (ExecutionPlatform.LINUX_ARM64, ExecutionPlatform.LINUX_AMD64),
        ),
        (
            "allowed_platforms",
            (ExecutionPlatform.LINUX_AMD64, ExecutionPlatform.LINUX_AMD64),
        ),
    ),
)
def test_resource_spec_rejects_coercion_nonfinite_values_and_bad_bounds(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        resources(**{field: value})


@pytest.mark.parametrize(
    ("gpu_count", "gpu_type"),
    ((0, "nvidia-a100"), (1, None), (1, ""), (1, "GPU With Spaces")),
)
def test_gpu_count_and_type_are_consistent(gpu_count: int, gpu_type: str | None) -> None:
    with pytest.raises(ValidationError):
        resources(gpu_count=gpu_count, gpu_type=gpu_type)


def test_network_policy_defaults_to_fail_closed() -> None:
    policy = execution.NetworkPolicy()

    assert policy.mode is execution.NetworkMode.NONE
    assert policy.allowlist == ()


def test_network_policy_allows_only_canonical_https_endpoints() -> None:
    policy = execution.NetworkPolicy(
        mode=execution.NetworkMode.HTTPS_ALLOWLIST,
        allowlist=(execution.HttpsEndpoint(host="api.example.org", port=443),),
    )

    assert policy.allowlist[0].host == "api.example.org"


@pytest.mark.parametrize(
    "host",
    (
        "",
        "localhost",
        "API.example.org",
        "*.example.org",
        "127.0.0.1",
        "[::1]",
        "https://api.example.org",
        "api.example.org/path",
        "user@api.example.org",
        "api.example.org.",
    ),
)
def test_network_endpoints_reject_ip_wildcard_or_url_confusion(host: str) -> None:
    with pytest.raises(ValidationError):
        execution.HttpsEndpoint(host=host, port=443)


def test_network_mode_and_allowlist_must_agree() -> None:
    endpoint = execution.HttpsEndpoint(host="api.example.org", port=443)

    with pytest.raises(ValidationError):
        execution.NetworkPolicy(mode=execution.NetworkMode.NONE, allowlist=(endpoint,))
    with pytest.raises(ValidationError):
        execution.NetworkPolicy(mode=execution.NetworkMode.HTTPS_ALLOWLIST, allowlist=())
    with pytest.raises(ValidationError):
        execution.NetworkPolicy(
            mode=execution.NetworkMode.HTTPS_ALLOWLIST,
            allowlist=(endpoint, endpoint),
        )
    with pytest.raises(ValidationError):
        execution.HttpsEndpoint(host="api.example.org", port=True)


def test_retry_policy_defaults_to_one_attempt_and_no_conditions() -> None:
    policy = execution.RetryPolicy()

    assert policy.attempts == 1
    assert policy.exit_codes == ()
    assert policy.http_statuses == ()


def test_retry_policy_accepts_bounded_exit_code_retries() -> None:
    policy = retry_exit_codes()

    assert policy.exit_codes == (1, 2)
    assert hash(policy)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("attempts", True),
        ("attempts", 0),
        ("attempts", 11),
        ("initial_backoff_seconds", True),
        ("initial_backoff_seconds", -1.0),
        ("initial_backoff_seconds", math.nan),
        ("maximum_backoff_seconds", math.inf),
        ("multiplier", 0.5),
        ("jitter_seconds", -0.1),
        ("exit_codes", (2, 1)),
        ("exit_codes", (1, 1)),
        ("exit_codes", (0,)),
        ("exit_codes", (True,)),
        ("http_statuses", (503, 500)),
        ("http_statuses", (500, 500)),
        ("http_statuses", (200,)),
    ),
)
def test_retry_policy_rejects_nonfinite_coercible_or_noncanonical_values(
    field: str,
    value: object,
) -> None:
    values = retry_exit_codes().model_dump(mode="python")
    values[field] = value

    with pytest.raises(ValidationError):
        execution.RetryPolicy.model_validate(values)


def test_retry_policy_delays_and_attempts_are_internally_consistent() -> None:
    with pytest.raises(ValidationError):
        execution.RetryPolicy(attempts=2)
    with pytest.raises(ValidationError):
        retry_exit_codes().model_copy(update={"maximum_backoff_seconds": 0.5})
    with pytest.raises(ValidationError):
        retry_exit_codes().model_copy(update={"jitter_seconds": 5.0})
    with pytest.raises(ValidationError):
        execution.RetryPolicy(exit_codes=(1,))


def test_negative_zero_retry_fields_are_canonical_in_models_dumps_and_digests() -> None:
    negative_retry = execution.RetryPolicy(
        initial_backoff_seconds=-0.0,
        maximum_backoff_seconds=-0.0,
        jitter_seconds=-0.0,
    )
    canonical_retry = execution.RetryPolicy(
        initial_backoff_seconds=0.0,
        maximum_backoff_seconds=0.0,
        jitter_seconds=0.0,
    )
    negative_plan = argv_plan(retry=negative_retry)
    canonical_plan = argv_plan(retry=canonical_retry)

    assert negative_plan == canonical_plan
    assert negative_plan.model_dump(mode="json") == canonical_plan.model_dump(mode="json")
    assert negative_plan.model_dump_json() == canonical_plan.model_dump_json()
    assert negative_plan.plan_digest() == canonical_plan.plan_digest()
    assert all(
        math.copysign(1.0, value) == 1.0
        for value in (
            negative_plan.retry.initial_backoff_seconds,
            negative_plan.retry.maximum_backoff_seconds,
            negative_plan.retry.jitter_seconds,
        )
    )


def test_negative_zero_remains_invalid_for_positive_only_float_fields() -> None:
    with pytest.raises(ValidationError):
        resources(memory_gib=-0.0)
    with pytest.raises(ValidationError):
        resources(scratch_disk_gib=-0.0)
    with pytest.raises(ValidationError):
        execution.RetryPolicy(multiplier=-0.0)
    with pytest.raises(ValidationError):
        execution.RateLimitPolicy(max_requests=10, per_seconds=-0.0)


def test_checkpoint_policy_defaults_to_explicit_disabled_state() -> None:
    policy = execution.CheckpointPolicy()

    assert policy.mode is execution.CheckpointMode.DISABLED
    assert policy.signal is None
    assert policy.relative_path is None


def test_process_checkpoint_requires_signal_grace_and_safe_relative_path() -> None:
    policy = checkpoint()

    assert policy.relative_path == "checkpoints/state.json"
    assert hash(policy)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("relative_path", ""),
        ("relative_path", "../state.json"),
        ("relative_path", "/tmp/state.json"),
        ("relative_path", "checkpoints\\state.json"),
        ("relative_path", "checkpoints//state.json"),
        ("relative_path", "checkpoints/state\x00"),
        ("grace_seconds", True),
        ("grace_seconds", 0),
        ("grace_seconds", 3601),
    ),
)
def test_checkpoint_rejects_unsafe_paths_and_invalid_grace(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        checkpoint().model_copy(update={field: value})


def test_checkpoint_disabled_and_enabled_fields_cannot_be_mixed() -> None:
    with pytest.raises(ValidationError):
        execution.CheckpointPolicy(relative_path="state.json")
    with pytest.raises(ValidationError):
        execution.CheckpointPolicy(mode=execution.CheckpointMode.PROCESS_SIGNAL)


def test_argv_plan_roundtrips_literal_tokens_without_shell_semantics() -> None:
    tokens = (
        "a b",
        ">",
        "2>&1",
        "$(touch /tmp/x)",
        ";",
        "line one\nline two",
        "",
    )
    plan = argv_plan(arguments=tokens)
    rebuilt = execution.ArgvPlan.model_validate_json(plan.model_dump_json())

    assert rebuilt.arguments == tokens
    assert rebuilt.token_array() == ("samtools", *tokens)
    assert hash(rebuilt)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("executable", "bin/samtools"),
        ("executable", "Samtools"),
        ("executable", ""),
        ("arguments", "view"),
        ("arguments", ["view"]),
        ("arguments", ("bad\x00token",)),
    ),
)
def test_argv_plan_requires_probe_id_and_exact_argument_tuple(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        argv_plan(**{field: value})


@pytest.mark.parametrize("extra", ({"command": "samtools view"}, {"shell": True}, {"redirect": "out.bam"}))
def test_argv_plan_has_no_shell_or_command_surface(extra: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        argv_plan(**extra)


def test_environment_bindings_are_typed_sorted_and_unique() -> None:
    bindings = (
        execution.LiteralEnvironmentVariable(
            name="OMP_NUM_THREADS",
            value="2",
        ),
        execution.SecretEnvironmentVariable(
            name="SERVICE_TOKEN",
            secret_id="service-token",
        ),
    )
    plan = argv_plan(environment=bindings)

    assert plan.environment == bindings
    with pytest.raises(ValidationError, match="unique"):
        argv_plan(environment=(bindings[0], bindings[0]))
    with pytest.raises(ValidationError):
        execution.SecretEnvironmentVariable(
            name="SERVICE_TOKEN",
            secret_id="service-token",
            value="literal-secret",
        )
    with pytest.raises(ValidationError, match="secret reference"):
        execution.LiteralEnvironmentVariable(name="API_KEY", value="literal-secret")
    assert execution.LiteralEnvironmentVariable(name="MONKEY", value="public").value == "public"


@pytest.mark.parametrize("name", SECRET_ENVIRONMENT_NAMES)
def test_secret_named_environment_variables_require_references(name: str) -> None:
    with pytest.raises(ValidationError, match="secret reference"):
        execution.LiteralEnvironmentVariable(name=name, value="literal-secret")

    assert execution.SecretEnvironmentVariable(name=name, secret_id="service-secret").name == name


@pytest.mark.parametrize("name", NON_SECRET_NAMES)
def test_nonsecret_key_substrings_remain_literal_environment_values(name: str) -> None:
    assert execution.LiteralEnvironmentVariable(name=name, value="public").value == "public"


def test_pipeline_is_structural_and_serializes_to_token_arrays() -> None:
    plan = pipeline_plan()
    rebuilt = execution.PipelinePlan.model_validate_json(plan.model_dump_json())

    assert rebuilt.token_arrays() == (
        ("samtools", "view", "input.bam"),
        ("samtools-sort", "-o", "sorted.bam"),
    )


@pytest.mark.parametrize(
    "stages",
    (
        (),
        (
            {
                "stage_id": "read",
                "executable": "samtools",
                "arguments": ("view",),
            },
        ),
        "samtools view | samtools sort",
        [
            {"stage_id": "read", "executable": "samtools", "arguments": ()},
            {"stage_id": "sort", "executable": "samtools-sort", "arguments": ()},
        ],
    ),
)
def test_pipeline_requires_at_least_two_exact_stage_objects(stages: object) -> None:
    with pytest.raises(ValidationError):
        pipeline_plan(stages=stages)


def test_pipeline_stage_ids_are_unique() -> None:
    first, second = pipeline_plan().stages

    with pytest.raises(ValidationError, match="unique"):
        pipeline_plan(stages=(first, second.model_copy(update={"stage_id": first.stage_id})))


def test_process_plans_reject_http_retry_statuses() -> None:
    retry = retry_exit_codes().model_copy(
        update={"exit_codes": (), "http_statuses": (503,)},
    )

    with pytest.raises(ValidationError, match="HTTP"):
        argv_plan(retry=retry)
    with pytest.raises(ValidationError, match="HTTP"):
        pipeline_plan(retry=retry)


def script_plan(**updates: object) -> execution.ScriptPlan:
    values: dict[str, object] = {
        "interpreter": "bash",
        "script": 'set -euo pipefail\nsamtools view "$1" > output.bam\n',
        "audit_reason": "The upstream tool requires audited shell redirection semantics.",
        "arguments": ("input file.bam",),
        "resources": resources(),
    }
    values.update(updates)
    return execution.ScriptPlan(**values)


def python_plan(**updates: object) -> execution.PythonPlan:
    values: dict[str, object] = {
        "callable_ref": "bionodulo.nodes.catalog.alignment:run_alignment",
        "arguments": ("sample", 3, 0.25, None),
        "keywords": (
            execution.PythonKeyword(name="output_name", value="result.bam"),
            execution.PythonKeyword(name="threads", value=2),
        ),
        "resources": resources(),
    }
    values.update(updates)
    return execution.PythonPlan(**values)


def r_plan(**updates: object) -> execution.RPlan:
    values: dict[str, object] = {
        "interpreter": "rscript",
        "resource": execution.PackagedResource(
            package_id="analysis-resources",
            relative_path="r/plot_counts.R",
        ),
        "arguments": ("counts.tsv", "plot.pdf"),
        "resources": resources(),
    }
    values.update(updates)
    return execution.RPlan(**values)


def http_network(host: str = "api.example.org", port: int = 443) -> execution.NetworkPolicy:
    return execution.NetworkPolicy(
        mode=execution.NetworkMode.HTTPS_ALLOWLIST,
        allowlist=(execution.HttpsEndpoint(host=host, port=port),),
    )


def http_plan(**updates: object) -> execution.HttpPlan:
    values: dict[str, object] = {
        "method": execution.HttpMethod.GET,
        "url": "https://api.example.org/v1/jobs?page=1",
        "headers": (execution.LiteralHttpHeader(name="accept", value="application/json"),),
        "body": None,
        "response_validator": "job-response",
        "rate_limit": execution.RateLimitPolicy(max_requests=10, per_seconds=1.0),
        "resources": resources(),
        "network": http_network(),
    }
    values.update(updates)
    return execution.HttpPlan(**values)


def container_plan(**updates: object) -> execution.ContainerPlan:
    values: dict[str, object] = {
        "environment_id": "container-tools",
        "entrypoint": ("samtools",),
        "arguments": ("view", "input.bam"),
        "resources": resources(),
    }
    values.update(updates)
    return execution.ContainerPlan(**values)


def test_script_plan_is_the_only_explicit_audited_script_surface() -> None:
    plan = script_plan()

    assert plan.script_sha256 == "sha256:" + hashlib.sha256(plan.script.encode()).hexdigest()
    assert plan.arguments == ("input file.bam",)
    assert plan.script.startswith("set -euo pipefail")


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("interpreter", ""),
        ("interpreter", "/bin/bash"),
        ("script", ""),
        ("script", "\x00"),
        ("audit_reason", "needed"),
        ("audit_reason", "This is required."),
        ("arguments", ["input.bam"]),
    ),
)
def test_script_plan_requires_probe_body_and_nontrivial_reason(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        script_plan(**{field: value})


@pytest.mark.parametrize("extra", ({"shell": True}, {"command": "samtools view"}))
def test_script_plan_rejects_implicit_or_duplicate_script_surfaces(extra: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        script_plan(**extra)


def test_python_plan_accepts_only_frozen_scalar_bindings() -> None:
    plan = python_plan()
    rebuilt = execution.PythonPlan.model_validate_json(plan.model_dump_json())

    assert rebuilt == plan
    assert hash(rebuilt)


def test_negative_zero_python_scalars_are_canonical_in_models_dumps_and_digests() -> None:
    negative_plan = python_plan(
        arguments=(-0.0,),
        keywords=(execution.PythonKeyword(name="threshold", value=-0.0),),
    )
    canonical_plan = python_plan(
        arguments=(0.0,),
        keywords=(execution.PythonKeyword(name="threshold", value=0.0),),
    )

    assert negative_plan == canonical_plan
    assert negative_plan.model_dump(mode="json") == canonical_plan.model_dump(mode="json")
    assert negative_plan.model_dump_json() == canonical_plan.model_dump_json()
    assert negative_plan.plan_digest() == canonical_plan.plan_digest()
    assert math.copysign(1.0, negative_plan.arguments[0]) == 1.0
    assert math.copysign(1.0, negative_plan.keywords[0].value) == 1.0


@pytest.mark.parametrize("value", (True, False))
def test_python_bool_scalars_roundtrip_copy_and_digest(value: bool) -> None:
    plan = python_plan(
        arguments=(value,),
        keywords=(execution.PythonKeyword(name="enabled", value=value),),
    )
    rebuilt = execution.PythonPlan.model_validate_json(plan.model_dump_json())
    copied = plan.model_copy()

    assert rebuilt == plan
    assert copied == plan
    assert type(rebuilt.arguments[0]) is bool
    assert type(rebuilt.keywords[0].value) is bool
    assert rebuilt.plan_digest() == plan.plan_digest()
    assert copied.plan_digest() == plan.plan_digest()


@pytest.mark.parametrize("placement", ("argument", "keyword"))
def test_python_signed_int64_rejects_out_of_range_values(placement: str) -> None:
    for value in (-(2**63) - 1, 2**63):
        with pytest.raises(ValidationError):
            if placement == "argument":
                python_plan(arguments=(value,))
            else:
                execution.PythonKeyword(name="value", value=value)


@pytest.mark.parametrize("placement", ("argument", "keyword"))
def test_python_signed_int64_copies_revalidate_bounds(placement: str) -> None:
    plan = python_plan(arguments=(0,))
    keyword = execution.PythonKeyword(name="value", value=0)

    for value in (-(2**63) - 1, 2**63):
        with pytest.raises(ValidationError):
            if placement == "argument":
                plan.model_copy(update={"arguments": (value,)})
            else:
                keyword.model_copy(update={"value": value})


@pytest.mark.parametrize("placement", ("argument", "keyword"))
def test_python_signed_int64_json_revalidates_bounds(placement: str) -> None:
    plan = python_plan(
        arguments=(0,),
        keywords=(execution.PythonKeyword(name="value", value=0),),
    )

    for value in (-(2**63) - 1, 2**63):
        payload = plan.model_dump(mode="json")
        if placement == "argument":
            payload["arguments"] = [value]
        else:
            payload["keywords"][0]["value"] = value
        with pytest.raises(ValidationError):
            execution.PythonPlan.model_validate_json(json.dumps(payload))


def test_python_signed_int64_boundaries_roundtrip_and_digest() -> None:
    lower = -(2**63)
    upper = 2**63 - 1
    plan = python_plan(
        arguments=(lower, upper),
        keywords=(
            execution.PythonKeyword(name="lower", value=lower),
            execution.PythonKeyword(name="upper", value=upper),
        ),
    )
    rebuilt = execution.PythonPlan.model_validate_json(plan.model_dump_json())
    copied = plan.model_copy()

    assert rebuilt == plan
    assert copied == plan
    assert rebuilt.plan_digest() == plan.plan_digest()
    assert copied.plan_digest() == plan.plan_digest()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", plan.plan_digest())


@pytest.mark.parametrize(
    "callable_ref",
    (
        "",
        "module",
        "module:",
        ":symbol",
        "../module:symbol",
        "module:<locals>.function",
        "module:symbol..child",
        "module: symbol",
        "module:symbol\n",
        "builtins:eval",
        "builtins:exec",
        "builtins:__import__",
        "os:system",
        "subprocess:run",
        "pickle:load",
        "pickle:loads",
        "_pickle:loads",
        "bionodulo.nodes.catalog:run",
        "bionodulo.nodes.catalogue.tool:run",
        "bionodulo.nodes.catalog.__private__:run",
        "bionodulo.nodes.catalog.tool:__import__",
        "bionodulo.nodes.catalog.tool:Runner.__dict__",
        "bionodulo.nodes.catalog.tool:run.__call__",
    ),
)
def test_python_callable_reference_rejects_traversal_or_dynamic_names(callable_ref: str) -> None:
    with pytest.raises(ValidationError):
        python_plan(callable_ref=callable_ref)


@pytest.mark.parametrize(
    "callable_ref",
    (
        "bionodulo.nodes.catalog.tool:subprocess.run",
        "bionodulo.nodes.catalog.tool:os.system",
        "bionodulo.nodes.catalog.tool:pickle.loads",
    ),
)
def test_python_callable_reference_rejects_trusted_nested_attributes(callable_ref: str) -> None:
    with pytest.raises(ValidationError):
        python_plan(callable_ref=callable_ref)


@pytest.mark.parametrize(
    "value",
    (b"bytes", [1], {"a": 1}, (1,), math.nan, math.inf),
)
def test_python_arguments_reject_mutable_or_nonfinite_values(value: object) -> None:
    with pytest.raises(ValidationError):
        python_plan(arguments=(value,))


def test_python_keyword_names_are_unique_and_canonically_ordered() -> None:
    alpha = execution.PythonKeyword(name="alpha", value=1)
    zeta = execution.PythonKeyword(name="zeta", value=2)

    with pytest.raises(ValidationError, match="canonically ordered"):
        python_plan(keywords=(zeta, alpha))
    with pytest.raises(ValidationError, match="unique"):
        python_plan(keywords=(alpha, alpha))
    with pytest.raises(ValidationError):
        execution.PythonKeyword(name="bad-name", value=1)


def test_python_plan_has_no_code_eval_or_pickle_surface() -> None:
    for extra in ({"code": "print(1)"}, {"eval": "1+1"}, {"pickle": b"payload"}):
        with pytest.raises(ValidationError):
            python_plan(**extra)


def test_r_plan_references_a_trusted_packaged_resource() -> None:
    plan = r_plan()
    rebuilt = execution.RPlan.model_validate_json(plan.model_dump_json())

    assert rebuilt.resource.relative_path == "r/plot_counts.R"
    assert rebuilt == plan


@pytest.mark.parametrize(
    "relative_path",
    ("", "plot.R", "../plot.R", "/tmp/plot.R", "r\\plot.R", "r/plot.r", "r/plot.R\x00"),
)
def test_r_resource_reference_is_safe_and_explicit(relative_path: str) -> None:
    with pytest.raises(ValidationError):
        execution.PackagedResource(
            package_id="analysis-resources",
            relative_path=relative_path,
        )


def test_r_plan_rejects_inline_script_surface() -> None:
    with pytest.raises(ValidationError):
        r_plan(script="system('touch /tmp/x')")


def test_http_plan_requires_exact_https_network_allowance() -> None:
    plan = http_plan()

    assert plan.network.allowlist == (execution.HttpsEndpoint(host="api.example.org", port=443),)
    with pytest.raises(ValidationError, match="network"):
        http_plan(network=execution.NetworkPolicy())
    with pytest.raises(ValidationError, match="network"):
        http_plan(network=http_network("other.example.org"))


@pytest.mark.parametrize(
    "url",
    (
        "http://api.example.org/v1/jobs",
        "HTTPS://api.example.org/v1/jobs",
        "Https://api.example.org/v1/jobs",
        "https://user:secret@api.example.org/v1/jobs",
        "https://API.example.org/v1/jobs",
        "https://api.example.org:0/v1/jobs",
        "https://api.example.org:443/v1/jobs",
        "https://api.example.org/v1/%6aobs",
        "https://api.example.org/v1/jobs%0aextra",
        "https://api.example.org/v1/../jobs",
        "https://api.example.org//v1/jobs",
        "https://api.example.org/v1/jobs#fragment",
        "https://api.example.org/v1/jobs#",
        "https://api.example.org/v1/jobs?",
        "https://api.example.org/v1/jobs?token=secret",
        "https://api.example.org/v1/jobs?access_token=secret",
        "https://api.example.org/v1/jobs?api_key=secret",
        "https://api.example.org/v1/jobs?client_secret=secret",
        "https://api.example.org/v1/jobs?page=%31",
        "https://api.example.org/v1/jobs?page=one+two",
        "https://api.example.org/v1/jobs?page=1&page=2",
        "https://api.example.org/v1/jobs?z=1&a=2",
    ),
)
def test_http_url_rejects_ambiguous_or_secret_bearing_forms(url: str) -> None:
    with pytest.raises(ValidationError):
        http_plan(url=url)


@pytest.mark.parametrize("port", ("080", "08443", "065535"))
def test_http_url_rejects_noncanonical_decimal_ports(port: str) -> None:
    numeric_port = int(port)

    with pytest.raises(ValidationError, match="canonical"):
        http_plan(
            url=f"https://api.example.org:{port}/v1/jobs",
            network=http_network(port=numeric_port),
        )


def test_http_root_and_nondefault_port_urls_have_one_canonical_spelling() -> None:
    root = http_plan(url="https://api.example.org/")
    nondefault = http_plan(
        url="https://api.example.org:8443/v1/jobs",
        network=http_network(port=8443),
    )

    assert root.url == "https://api.example.org/"
    assert nondefault.url == "https://api.example.org:8443/v1/jobs"
    assert execution.HttpPlan.model_validate_json(root.model_dump_json()).plan_digest() == root.plan_digest()
    with pytest.raises(ValidationError, match="path"):
        http_plan(url="https://api.example.org")


@pytest.mark.parametrize(
    "name",
    ("authorization", "cookie", "proxy-authorization", "x-api-key"),
)
def test_http_sensitive_headers_require_secret_references(name: str) -> None:
    with pytest.raises(ValidationError):
        execution.LiteralHttpHeader(name=name, value="Bearer literal-secret")

    header = execution.SecretHttpHeader(name=name, secret_id="service-token")
    assert header.secret_id == "service-token"


@pytest.mark.parametrize("name", SECRET_HEADER_NAMES)
def test_tokenized_secret_http_headers_require_references(name: str) -> None:
    with pytest.raises(ValidationError, match="secret reference"):
        execution.LiteralHttpHeader(name=name, value="literal-secret")

    assert execution.SecretHttpHeader(name=name, secret_id="service-secret").name == name


@pytest.mark.parametrize("name", tuple(name.lower() for name in NON_SECRET_NAMES))
def test_nonsecret_key_substrings_remain_literal_http_headers(name: str) -> None:
    assert execution.LiteralHttpHeader(name=name, value="public").value == "public"


@pytest.mark.parametrize("name", SECRET_QUERY_NAMES)
def test_tokenized_secret_http_query_keys_are_rejected(name: str) -> None:
    with pytest.raises(ValidationError, match="secret-bearing"):
        http_plan(url=f"https://api.example.org/v1/jobs?{name}=literal-secret")


@pytest.mark.parametrize("name", tuple(name.lower() for name in NON_SECRET_NAMES))
def test_nonsecret_key_substrings_remain_http_query_keys(name: str) -> None:
    plan = http_plan(url=f"https://api.example.org/v1/jobs?{name}=public")

    assert plan.url.endswith(f"?{name}=public")


@pytest.mark.parametrize(
    "name",
    (
        "sig",
        "signature",
        "service_signature",
        "x-amz-signature",
        "x-goog-signature",
        "serviceSignature",
        "xAmzSignature",
        "accessToken",
        "clientSecret",
    ),
)
def test_signature_and_camel_case_query_credentials_are_rejected(name: str) -> None:
    with pytest.raises(ValidationError, match="secret-bearing"):
        http_plan(url=f"https://api.example.org/v1/jobs?{name}=literal-secret")


def test_signature_algorithm_environment_metadata_remains_literal() -> None:
    binding = execution.LiteralEnvironmentVariable(name="SIGNATURE_ALGORITHM", value="ed25519")

    assert binding.value == "ed25519"


def test_signature_input_header_metadata_remains_literal() -> None:
    header = execution.LiteralHttpHeader(name="signature-input", value='sig1=("@method")')

    assert header.value == 'sig1=("@method")'


@pytest.mark.parametrize("name", ("signature_algorithm", "signature_input"))
def test_signature_query_metadata_controls_remain_literal(name: str) -> None:
    plan = http_plan(url=f"https://api.example.org/v1/jobs?{name}=public")

    assert plan.url.endswith(f"?{name}=public")


def test_design_names_remain_nonsecret_in_literal_contexts() -> None:
    environment = execution.LiteralEnvironmentVariable(name="DESIGN", value="public")
    header = execution.LiteralHttpHeader(name="design", value="public")
    plan = http_plan(url="https://api.example.org/v1/jobs?design=public")

    assert environment.name == "DESIGN"
    assert header.name == "design"
    assert plan.url.endswith("?design=public")


def test_http_headers_are_unique_ordered_and_control_free() -> None:
    accept = execution.LiteralHttpHeader(name="accept", value="application/json")
    trace = execution.LiteralHttpHeader(name="x-trace-id", value="catalog-test")

    with pytest.raises(ValidationError, match="canonically ordered"):
        http_plan(headers=(trace, accept))
    with pytest.raises(ValidationError, match="unique"):
        http_plan(headers=(accept, accept))
    with pytest.raises(ValidationError):
        execution.LiteralHttpHeader(name="Accept", value="application/json")
    with pytest.raises(ValidationError):
        execution.LiteralHttpHeader(name="x-test", value="one\ntwo")


def test_http_body_is_an_immutable_content_addressed_reference() -> None:
    body = execution.HttpBodyReference(
        artifact_id="request-body",
        media_type="application/json",
        sha256="sha256:" + "a" * 64,
        size_bytes=128,
    )
    plan = http_plan(method=execution.HttpMethod.POST, body=body)

    assert hash(plan.body)
    with pytest.raises(ValidationError):
        http_plan(body=body)
    with pytest.raises(ValidationError):
        body.model_copy(update={"size_bytes": True})


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("max_requests", True),
        ("max_requests", 0),
        ("per_seconds", True),
        ("per_seconds", 1),
        ("per_seconds", 0.0),
        ("per_seconds", math.nan),
        ("per_seconds", math.inf),
    ),
)
def test_rate_limit_policy_is_finite_exact_and_bounded(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        execution.RateLimitPolicy(max_requests=10, per_seconds=1.0).model_copy(update={field: value})


def test_http_retry_accepts_statuses_and_rejects_exit_codes() -> None:
    retry = execution.RetryPolicy(
        attempts=2,
        initial_backoff_seconds=1.0,
        maximum_backoff_seconds=2.0,
        multiplier=2.0,
        jitter_seconds=0.0,
        http_statuses=(429, 503),
    )
    assert http_plan(retry=retry).retry.http_statuses == (429, 503)

    exit_retry = retry.model_copy(update={"http_statuses": (), "exit_codes": (1,)})
    with pytest.raises(ValidationError, match="exit"):
        http_plan(retry=exit_retry)


def test_container_plan_references_environment_and_literal_token_arrays() -> None:
    plan = container_plan(arguments=("a b", ">", "$(id)"))
    rebuilt = execution.ContainerPlan.model_validate_json(plan.model_dump_json())

    assert rebuilt.entrypoint == ("samtools",)
    assert rebuilt.arguments == ("a b", ">", "$(id)")
    assert rebuilt.token_arrays() == (("samtools",), ("a b", ">", "$(id)"))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("environment_id", ""),
        ("entrypoint", ()),
        ("entrypoint", ["samtools"]),
        ("entrypoint", ("bin/samtools",)),
        ("entrypoint", ("samtools", "bad\x00token")),
        ("arguments", ["view"]),
    ),
)
def test_container_plan_requires_environment_probe_and_exact_tokens(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        container_plan(**{field: value})


@pytest.mark.parametrize(
    "extra",
    (
        {"image": "example.org/tool:latest"},
        {"command": "samtools view"},
        {"shell": True},
        {"privileged": True},
        {"host_network": True},
        {"volumes": ("/tmp:/host",)},
    ),
)
def test_container_plan_has_no_image_or_privileged_runtime_surface(extra: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        container_plan(**extra)


def test_checkpoint_and_retry_are_restricted_to_meaningful_variants() -> None:
    assert script_plan(checkpoint=checkpoint()).checkpoint.mode is execution.CheckpointMode.PROCESS_SIGNAL
    assert r_plan(retry=retry_exit_codes()).retry.exit_codes == (1, 2)
    assert container_plan(checkpoint=checkpoint()).checkpoint.relative_path == "checkpoints/state.json"

    with pytest.raises(ValidationError, match="checkpoint"):
        python_plan(checkpoint=checkpoint())
    with pytest.raises(ValidationError, match="checkpoint"):
        http_plan(checkpoint=checkpoint())
    with pytest.raises(ValidationError, match="exit"):
        python_plan(retry=retry_exit_codes())


@pytest.mark.parametrize(
    "factory",
    (
        argv_plan,
        pipeline_plan,
        script_plan,
        python_plan,
        r_plan,
        http_plan,
        container_plan,
    ),
)
def test_all_execution_variants_are_frozen_hashable_and_union_roundtrip(factory: object) -> None:
    plan = factory()
    rebuilt = TypeAdapter(execution.ExecutionPlan).validate_json(plan.model_dump_json())

    assert rebuilt == plan
    assert hash(rebuilt) == hash(plan)
    assert rebuilt.plan_digest() == plan.plan_digest()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", plan.plan_digest())
    with pytest.raises(ValidationError, match="frozen_instance"):
        plan.resources = resources(cpus=3)


def test_execution_union_has_a_kind_discriminator_and_all_seven_variants() -> None:
    adapter = TypeAdapter(execution.ExecutionPlan)
    plans = (
        argv_plan(),
        pipeline_plan(),
        script_plan(),
        python_plan(),
        r_plan(),
        http_plan(),
        container_plan(),
    )

    rebuilt = tuple(adapter.validate_json(plan.model_dump_json()) for plan in plans)

    assert tuple(type(plan) for plan in rebuilt) == tuple(type(plan) for plan in plans)
    assert adapter.json_schema()["discriminator"]["propertyName"] == "kind"


@pytest.mark.parametrize(
    "model_name",
    (
        "ResourceSpec",
        "HttpsEndpoint",
        "NetworkPolicy",
        "RetryPolicy",
        "CheckpointPolicy",
        "LiteralEnvironmentVariable",
        "SecretEnvironmentVariable",
        "PipelineStage",
        "PythonKeyword",
        "PackagedResource",
        "LiteralHttpHeader",
        "SecretHttpHeader",
        "HttpBodyReference",
        "RateLimitPolicy",
        "ArgvPlan",
        "PipelinePlan",
        "ScriptPlan",
        "PythonPlan",
        "RPlan",
        "HttpPlan",
        "ContainerPlan",
    ),
)
def test_all_execution_models_use_the_strict_frozen_contract(model_name: str) -> None:
    model = getattr(execution, model_name)

    assert model.model_config["strict"] is True
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["revalidate_instances"] == "always"


def test_plan_copy_and_construct_revalidate_nested_instances() -> None:
    invalid_resources = execution.ResourceSpec.model_construct(
        cpus=True,
        memory_gib=4.0,
        scratch_disk_gib=8.0,
        wall_timeout_seconds=3600,
        gpu_count=0,
        gpu_type=None,
        allowed_platforms=(ExecutionPlatform.LINUX_AMD64,),
    )
    valid = argv_plan()
    forged = execution.ArgvPlan.model_construct(**{**valid.model_dump(mode="python"), "resources": invalid_resources})

    with pytest.raises(ValidationError):
        execution.ArgvPlan.model_validate(forged)
    with pytest.raises(ValidationError):
        forged.model_copy()
    with pytest.raises(ValidationError):
        valid.model_copy(update={"arguments": ["view"]})


def test_plan_digest_distinguishes_token_boundaries_and_semantic_fields() -> None:
    first = argv_plan(arguments=("ab", "c"))
    second = argv_plan(arguments=("a", "bc"))
    different_resources = argv_plan(
        arguments=("ab", "c"),
        resources=resources(cpus=3),
    )

    assert first.plan_digest() != second.plan_digest()
    assert first.plan_digest() != different_resources.plan_digest()
    assert execution.ArgvPlan.model_validate_json(first.model_dump_json()).plan_digest() == first.plan_digest()


@pytest.mark.parametrize(
    "source",
    (
        "import subprocess as process\nprocess.run(('tool',))\n",
        "from os import system as launch\nlaunch('tool')\n",
        "import os as operating\nrunner = operating.popen\nrunner('tool')\n",
        "from shlex import join as render\nrender(('tool',))\n",
        "from urllib import request as web\nweb.urlopen('https://example.org')\n",
        "import httpx as client\nclient.get('https://example.org')\n",
        "import docker as runtime\nruntime.from_env()\n",
        "from bionodulo.nodes.legacy import executor\nexecutor.run()\n",
        "def _shell_join(tokens):\n    return ' '.join(tokens)\n_shell_join(('tool',))\n",
        "loader = __import__\nloader('subprocess')\n",
    ),
)
def test_ast_isolation_rejects_prohibited_aliases(source: str) -> None:
    assert _contract_ast_violations(source, filename="synthetic.py")


def test_contract_modules_pass_ast_execution_isolation() -> None:
    paths = (
        Path(execution.__file__).with_name("environments.py"),
        Path(execution.__file__),
    )

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert _contract_ast_violations(source, filename=str(path)) == ()
