"""AWS CLI 2.36.2 S3 upload contract."""
from __future__ import annotations

import json
from typing import Any

from .adapter import (
    S3BaseNode,
    S3_STORAGE_CLASSES,
    node_output_dir,
    normalized_local_path,
    redacted_command,
    require_returncode,
    required_text,
    run_command,
    s3_uri,
)


class S3UploadNode(S3BaseNode):
    """Upload one local file with ``aws s3 cp``."""

    NODE_ID = "s3_upload"
    DISPLAY_NAME = "S3 Upload"
    DESCRIPTION = "Upload one local workflow file to Amazon S3 using AWS CLI 2.36.2."
    SEARCH_ALIASES = [*S3BaseNode.SEARCH_ALIASES, "upload", "aws s3 cp"]
    RETURN_TYPES = ("STRING", "JSON")
    RETURN_NAMES = ("s3_uri", "metadata")
    UPSTREAM_SOURCE = "awscli/customizations/s3 cp command"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "local_path": ("FILE", {"description": "Local file to upload"}),
                "bucket": ("STRING", {"description": "Bare S3 bucket name"}),
                "key": ("STRING", {"description": "Destination object key"}),
            },
            "optional": {
                "storage_class": (list(S3_STORAGE_CLASSES), {"default": "STANDARD"}),
                **cls.common_input_types(),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for field in ("local_path", "bucket", "key"):
            error = required_text(inputs, field, cls.DISPLAY_NAME)
            if error:
                return error
        local_path = normalized_local_path(inputs.get("local_path"), inputs.get("_working_dir"))
        if not local_path.exists():
            return "S3 Upload local_path does not exist"
        if not local_path.is_file():
            return "S3 Upload local_path must be a file"
        storage_class = str(inputs.get("storage_class", "STANDARD") or "STANDARD")
        if storage_class not in S3_STORAGE_CLASSES:
            return f"Unsupported S3 storage_class: {storage_class}"
        return cls.validate_common(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "aws",
            "s3",
            "cp",
            str(normalized_local_path(inputs.get("local_path"), inputs.get("_working_dir"))),
            s3_uri(inputs.get("bucket"), inputs.get("key")),
        ]
        storage_class = str(inputs.get("storage_class", "STANDARD") or "STANDARD").strip()
        if storage_class:
            command.extend(["--storage-class", storage_class])
        return cls.append_common_args(command, inputs)

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_dir = node_output_dir(self, context)
        run_inputs = {
            **kwargs,
            "_working_dir": str(output_dir),
            "local_path": str(normalized_local_path(kwargs.get("local_path"), output_dir)),
        }
        validation = self.__class__.VALIDATE_INPUTS(run_inputs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")

        command = self.__class__.render_command(run_inputs)
        result = await run_command(command, output_dir, context)
        returncode = require_returncode(result, self.DISPLAY_NAME)
        if returncode != 0:
            stderr = str(result.get("stderr", ""))
            raise RuntimeError(f"S3 Upload failed (exit {returncode}): {stderr[:500]}")

        uri = s3_uri(run_inputs.get("bucket"), run_inputs.get("key"))
        metadata = {
            "operation": "upload",
            "aws_cli_version": self.VERSION,
            "bucket": str(run_inputs.get("bucket", "") or "").strip(),
            "key": str(run_inputs.get("key", "") or "").strip().lstrip("/"),
            "s3_uri": uri,
            "local_path": str(run_inputs["local_path"]),
            "command": redacted_command(command),
            "returncode": returncode,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }
        metadata_path = output_dir / "upload_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"outputs": {"s3_uri": uri, "metadata": str(metadata_path)}}
