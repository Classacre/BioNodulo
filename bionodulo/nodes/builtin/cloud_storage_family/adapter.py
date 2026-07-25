"""Shared AWS CLI 2.36.2 contracts for S3 operations."""
from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.execution.subprocess_runner import run_subprocess
from bionodulo.nodes.base import BaseNode


AWS_CLI_GIT_URL = "https://github.com/aws/aws-cli.git"
AWS_CLI_GIT_COMMIT = "f656cacd23b2ceb815189546245da99857c5c3a3"
SENSITIVE_AWS_OPTIONS = {
    "--sse-c-key",
    "--sse-c-copy-source-key",
    "--cli-input-json",
    "--cli-input-yaml",
}
DISALLOWED_S3_CP_OPTIONS = {
    "--dryrun",
    "--recursive",
}
S3_STORAGE_CLASSES = (
    "STANDARD",
    "REDUCED_REDUNDANCY",
    "STANDARD_IA",
    "ONEZONE_IA",
    "INTELLIGENT_TIERING",
    "GLACIER",
    "DEEP_ARCHIVE",
    "GLACIER_IR",
)


def node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output_dir = base / node.NODE_ID
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def required_text(inputs: dict[str, Any], field: str, display_name: str) -> str | None:
    if not str(inputs.get(field, "") or "").strip():
        return f"{display_name} requires {field}"
    return None


def validate_bucket(value: Any) -> bool | str:
    bucket = str(value or "").strip()
    if bucket.startswith("s3://") or "/" in bucket or any(char.isspace() for char in bucket):
        return "S3 bucket must be a bare bucket name without s3://, slashes, or whitespace"
    return True


def s3_uri(bucket: Any, key: Any) -> str:
    bucket_text = str(bucket or "").strip()
    key_text = str(key or "").strip().lstrip("/")
    return f"s3://{bucket_text}/{key_text}"


def extra_args(value: Any) -> list[str]:
    text = str(value or "").strip()
    return shlex.split(text) if text else []


def normalized_local_path(value: Any, base_dir: str | Path | None = None) -> Path:
    path = Path(str(value or "")).expanduser()
    if path.is_absolute():
        return path.resolve(strict=False)
    base = Path(base_dir).expanduser() if base_dir is not None else Path.cwd()
    return (base / path).resolve(strict=False)


def require_returncode(result: dict[str, Any], display_name: str) -> int:
    returncode = result.get("returncode")
    if isinstance(returncode, bool) or not isinstance(returncode, int):
        raise RuntimeError(f"{display_name} runner did not report an integer return code")
    return returncode


def redacted_command(command: list[str]) -> list[str]:
    redacted = list(command)
    redact_next = False
    for index, token in enumerate(redacted):
        if redact_next:
            redacted[index] = "[REDACTED]"
            redact_next = False
            continue
        option = token.split("=", 1)[0]
        if option in SENSITIVE_AWS_OPTIONS:
            if "=" in token:
                redacted[index] = f"{option}=[REDACTED]"
            else:
                redact_next = True
    return redacted


async def run_command(command: list[str], cwd: Path, context: Any) -> dict[str, Any]:
    if context is not None and hasattr(context, "run_command"):
        return await context.run_command(command, cwd=str(cwd))
    return await run_subprocess(command, cwd=cwd)


class S3BaseNode(BaseNode):
    """Common AWS CLI metadata and options."""

    CATEGORY = "storage"
    SEARCH_ALIASES: ClassVar[list[str]] = ["s3", "aws", "cloud storage", "object storage", "bucket"]
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["aws"]
    REQUIRED_CONDA_PACKAGES = ["awscli"]
    VERSION = "2.36.2"
    GIT_URL = AWS_CLI_GIT_URL
    GIT_COMMIT = AWS_CLI_GIT_COMMIT
    PACKAGE_AUTHORITY = "conda-forge awscli 2.36.2"
    DOCUMENTATION_URL = "https://docs.aws.amazon.com/cli/latest/reference/s3/cp.html"
    EXPERIMENTAL = True

    @classmethod
    def common_input_types(cls) -> dict[str, Any]:
        return {
            "profile": ("STRING", {"default": "", "description": "Optional AWS CLI profile name"}),
            "region": ("STRING", {"default": "", "description": "Optional AWS region override"}),
            "extra_args": (
                "STRING",
                {
                    "default": "",
                    "advanced": True,
                    "description": "Additional aws s3 cp arguments parsed with POSIX shell quoting",
                },
            ),
        }

    @classmethod
    def append_common_args(cls, command: list[str], inputs: dict[str, Any]) -> list[str]:
        profile = str(inputs.get("profile", "") or "").strip()
        region = str(inputs.get("region", "") or "").strip()
        if profile:
            command.extend(["--profile", profile])
        if region:
            command.extend(["--region", region])
        command.extend(extra_args(inputs.get("extra_args", "")))
        return command

    @classmethod
    def validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        bucket_validation = validate_bucket(inputs.get("bucket"))
        if bucket_validation is not True:
            return bucket_validation
        try:
            parsed_extra_args = extra_args(inputs.get("extra_args", ""))
        except ValueError as exc:
            return f"{cls.DISPLAY_NAME} extra_args are invalid: {exc}"
        disallowed = sorted(
            {
                token.split("=", 1)[0].lower()
                for token in parsed_extra_args
                if token.split("=", 1)[0].lower() in DISALLOWED_S3_CP_OPTIONS
            }
        )
        if disallowed:
            return (
                f"{cls.DISPLAY_NAME} extra_args may not use {', '.join(disallowed)}; "
                "the node contract requires one real object transfer"
            )
        return True
