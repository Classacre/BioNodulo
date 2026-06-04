"""Cloud storage nodes backed by provider CLI tools."""
from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.execution.subprocess_runner import run_subprocess
from bionodulo.nodes.base import BaseNode


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


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _required_text(inputs: dict[str, Any], field: str, display_name: str) -> str | None:
    value = str(inputs.get(field, "") or "").strip()
    if not value:
        return f"{display_name} requires {field}"
    return None


def _s3_uri(bucket: Any, key: Any) -> str:
    bucket_text = str(bucket or "").strip().removeprefix("s3://").strip("/")
    key_text = str(key or "").strip().lstrip("/")
    return f"s3://{bucket_text}/{key_text}"


def _extra_args(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return shlex.split(text)


async def _run_command(cmd: list[str], cwd: Path, context: Any) -> dict[str, Any]:
    if context is not None and hasattr(context, "run_command"):
        return await context.run_command(cmd, cwd=str(cwd))
    return await run_subprocess(cmd, cwd=cwd)


class _S3BaseNode(BaseNode):
    CATEGORY = "storage"
    SEARCH_ALIASES: ClassVar[list[str]] = ["s3", "aws", "cloud storage", "object storage", "bucket"]
    RETURN_TYPES = ("STRING", "JSON")
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["aws"]
    REQUIRED_CONDA_PACKAGES = ["awscli"]
    DOCUMENTATION_URL = "https://docs.aws.amazon.com/cli/latest/reference/s3/cp.html"
    EXPERIMENTAL = True

    @classmethod
    def _common_input_types(cls) -> dict[str, Any]:
        return {
            "profile": ("STRING", {"default": "", "description": "Optional AWS CLI profile name"}),
            "region": ("STRING", {"default": "", "description": "Optional AWS region override"}),
            "extra_args": (
                "STRING",
                {
                    "default": "",
                    "advanced": True,
                    "description": "Additional aws s3 cp arguments, parsed like a shell command line",
                },
            ),
        }

    @classmethod
    def _append_common_args(cls, command: list[str], inputs: dict[str, Any]) -> list[str]:
        profile = str(inputs.get("profile", "") or "").strip()
        region = str(inputs.get("region", "") or "").strip()
        if profile:
            command.extend(["--profile", profile])
        if region:
            command.extend(["--region", region])
        command.extend(_extra_args(inputs.get("extra_args", "")))
        return command


class S3UploadNode(_S3BaseNode):
    """Upload a local file to Amazon S3 using the AWS CLI."""

    NODE_ID = "s3_upload"
    DISPLAY_NAME = "S3 Upload"
    DESCRIPTION = "Upload a local workflow file to Amazon S3 using the AWS CLI; requires configured AWS credentials."
    SEARCH_ALIASES = [*_S3BaseNode.SEARCH_ALIASES, "upload", "aws s3 cp"]
    RETURN_NAMES = ("s3_uri", "metadata")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "local_path": ("FILE", {"default": "", "description": "Local file to upload"}),
                "bucket": ("STRING", {"default": "", "description": "S3 bucket name"}),
                "key": ("STRING", {"default": "", "description": "Destination object key"}),
            },
            "optional": {
                "storage_class": (list(S3_STORAGE_CLASSES), {"default": "STANDARD"}),
                **cls._common_input_types(),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for field in ("local_path", "bucket", "key"):
            error = _required_text(inputs, field, cls.DISPLAY_NAME)
            if error:
                return error
        local_path = Path(str(inputs.get("local_path", "")))
        if not local_path.exists():
            return "S3 Upload local_path does not exist"
        if not local_path.is_file():
            return "S3 Upload local_path must be a file"
        storage_class = str(inputs.get("storage_class", "STANDARD") or "STANDARD")
        if storage_class not in S3_STORAGE_CLASSES:
            return f"Unsupported S3 storage_class: {storage_class}"
        try:
            _extra_args(inputs.get("extra_args", ""))
        except ValueError as exc:
            return f"S3 Upload extra_args are invalid: {exc}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        s3_uri = _s3_uri(inputs.get("bucket", ""), inputs.get("key", ""))
        command = ["aws", "s3", "cp", str(inputs.get("local_path", "")), s3_uri]
        storage_class = str(inputs.get("storage_class", "STANDARD") or "STANDARD").strip()
        if storage_class:
            command.extend(["--storage-class", storage_class])
        return cls._append_common_args(command, inputs)

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")

        out_dir = _node_output_dir(self, context)
        command = self.__class__.render_command(kwargs)
        result = await _run_command(command, out_dir, context)
        if result.get("returncode", 0) != 0:
            stderr = str(result.get("stderr", ""))
            raise RuntimeError(f"S3 Upload failed (exit {result.get('returncode')}): {stderr[:500]}")

        s3_uri = _s3_uri(kwargs.get("bucket", ""), kwargs.get("key", ""))
        metadata = {
            "operation": "upload",
            "bucket": str(kwargs.get("bucket", "") or "").strip(),
            "key": str(kwargs.get("key", "") or "").strip().lstrip("/"),
            "s3_uri": s3_uri,
            "local_path": str(kwargs.get("local_path", "")),
            "command": command,
            "returncode": result.get("returncode", 0),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }
        metadata_path = out_dir / "upload_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "outputs": {
                "s3_uri": s3_uri,
                "metadata": str(metadata_path),
            }
        }


class S3DownloadNode(_S3BaseNode):
    """Download an S3 object to a local path using the AWS CLI."""

    NODE_ID = "s3_download"
    DISPLAY_NAME = "S3 Download"
    DESCRIPTION = "Download an object from Amazon S3 to a local workflow file using the AWS CLI."
    SEARCH_ALIASES = [*_S3BaseNode.SEARCH_ALIASES, "download", "fetch", "aws s3 cp"]
    RETURN_NAMES = ("local_path", "metadata")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bucket": ("STRING", {"default": "", "description": "S3 bucket name"}),
                "key": ("STRING", {"default": "", "description": "Source object key"}),
                "local_path": ("FILE", {"default": "", "description": "Local destination path"}),
            },
            "optional": cls._common_input_types(),
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for field in ("bucket", "key", "local_path"):
            error = _required_text(inputs, field, cls.DISPLAY_NAME)
            if error:
                return error
        try:
            _extra_args(inputs.get("extra_args", ""))
        except ValueError as exc:
            return f"S3 Download extra_args are invalid: {exc}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        s3_uri = _s3_uri(inputs.get("bucket", ""), inputs.get("key", ""))
        command = ["aws", "s3", "cp", s3_uri, str(inputs.get("local_path", ""))]
        return cls._append_common_args(command, inputs)

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")

        out_dir = _node_output_dir(self, context)
        local_path = Path(str(kwargs.get("local_path", "")))
        local_path.parent.mkdir(parents=True, exist_ok=True)
        command = self.__class__.render_command(kwargs)
        result = await _run_command(command, out_dir, context)
        if result.get("returncode", 0) != 0:
            stderr = str(result.get("stderr", ""))
            raise RuntimeError(f"S3 Download failed (exit {result.get('returncode')}): {stderr[:500]}")

        s3_uri = _s3_uri(kwargs.get("bucket", ""), kwargs.get("key", ""))
        metadata = {
            "operation": "download",
            "bucket": str(kwargs.get("bucket", "") or "").strip(),
            "key": str(kwargs.get("key", "") or "").strip().lstrip("/"),
            "s3_uri": s3_uri,
            "local_path": str(local_path),
            "command": command,
            "returncode": result.get("returncode", 0),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }
        metadata_path = out_dir / "download_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "outputs": {
                "local_path": str(local_path),
                "metadata": str(metadata_path),
            }
        }
