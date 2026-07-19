"""AWS CLI 2.36.2 S3 download contract."""
from __future__ import annotations

import json
from typing import Any

from .adapter import (
    S3BaseNode,
    node_output_dir,
    normalized_local_path,
    redacted_command,
    require_returncode,
    required_text,
    run_command,
    s3_uri,
)


class S3DownloadNode(S3BaseNode):
    """Download one S3 object with ``aws s3 cp`` and verify the artifact."""

    NODE_ID = "s3_download"
    DISPLAY_NAME = "S3 Download"
    DESCRIPTION = "Download one Amazon S3 object to a verified local workflow file using AWS CLI 2.36.2."
    SEARCH_ALIASES = [*S3BaseNode.SEARCH_ALIASES, "download", "fetch", "aws s3 cp"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("local_path", "metadata")
    UPSTREAM_SOURCE = "awscli/customizations/s3 cp command"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bucket": ("STRING", {"description": "Bare S3 bucket name"}),
                "key": ("STRING", {"description": "Source object key"}),
                "local_path": ("STRING", {"description": "Local destination file path"}),
            },
            "optional": cls.common_input_types(),
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for field in ("bucket", "key", "local_path"):
            error = required_text(inputs, field, cls.DISPLAY_NAME)
            if error:
                return error
        local_path = normalized_local_path(inputs.get("local_path"), inputs.get("_working_dir"))
        if local_path.exists() and local_path.is_dir():
            return "S3 Download local_path must name a file, not a directory"
        return cls.validate_common(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "aws",
            "s3",
            "cp",
            s3_uri(inputs.get("bucket"), inputs.get("key")),
            str(normalized_local_path(inputs.get("local_path"), inputs.get("_working_dir"))),
        ]
        return cls.append_common_args(command, inputs)

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_dir = node_output_dir(self, context)
        local_path = normalized_local_path(kwargs.get("local_path"), output_dir)
        run_inputs = {
            **kwargs,
            "_working_dir": str(output_dir),
            "local_path": str(local_path),
        }
        validation = self.__class__.VALIDATE_INPUTS(run_inputs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")

        local_path.parent.mkdir(parents=True, exist_ok=True)
        transfer_path = local_path.with_name(f".{local_path.name}.bionodulo-part")
        transfer_path.unlink(missing_ok=True)
        command = self.__class__.render_command({**run_inputs, "local_path": str(transfer_path)})
        try:
            result = await run_command(command, output_dir, context)
        except Exception:
            transfer_path.unlink(missing_ok=True)
            raise
        returncode = require_returncode(result, self.DISPLAY_NAME)
        if returncode != 0:
            transfer_path.unlink(missing_ok=True)
            stderr = str(result.get("stderr", ""))
            raise RuntimeError(f"S3 Download failed (exit {returncode}): {stderr[:500]}")
        if not transfer_path.is_file():
            raise RuntimeError("S3 Download exited successfully but did not create the requested file")
        transfer_path.replace(local_path)

        uri = s3_uri(run_inputs.get("bucket"), run_inputs.get("key"))
        metadata = {
            "operation": "download",
            "aws_cli_version": self.VERSION,
            "bucket": str(run_inputs.get("bucket", "") or "").strip(),
            "key": str(run_inputs.get("key", "") or "").strip().lstrip("/"),
            "s3_uri": uri,
            "local_path": str(local_path),
            "size_bytes": local_path.stat().st_size,
            "command": redacted_command(command),
            "returncode": returncode,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }
        metadata_path = output_dir / "download_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"outputs": {"local_path": str(local_path), "metadata": str(metadata_path)}}
