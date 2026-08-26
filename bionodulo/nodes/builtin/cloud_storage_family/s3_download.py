"""AWS CLI 2.36.2 S3 download contract."""
from __future__ import annotations

import json
import os
import shutil
import urllib.request
from concurrent.futures import ThreadPoolExecutor
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

# Single-stream TCP over a long-fat path (e.g. cross-continent to an
# open-data bucket) saturates around 15 MB/s regardless of host bandwidth;
# ranged parallel streams restore line rate, matching aws-cli behaviour.
PARALLEL_THRESHOLD_BYTES = 256 * 1024 * 1024
PARALLEL_STREAMS = 8


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

        transport = "aws-cli"
        if shutil.which("aws") is None:
            # Hosts without the AWS CLI (e.g. OCI workers downloading public
            # open-data buckets) still work: anonymous HTTPS against the
            # bucket's endpoint. Large objects fetch as parallel ranged
            # streams; authenticated buckets keep requiring the CLI path.
            transport = "https-anonymous"
            bucket = str(run_inputs.get("bucket", "") or "").strip()
            key = str(run_inputs.get("key", "") or "").strip().lstrip("/")
            url = f"https://{bucket}.s3.amazonaws.com/{key}"
            try:
                request = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(request, timeout=60) as resp:
                    total = int(resp.headers.get("Content-Length") or 0)
                streams = 1
                if total > PARALLEL_THRESHOLD_BYTES:
                    streams = PARALLEL_STREAMS
                part_paths = []
                if streams == 1:
                    self._fetch_range_resumable(url, 0, None, transfer_path)
                else:
                    chunk = total // streams + 1
                    ranges = [
                        (offset, min(offset + chunk, total) - 1)
                        for offset in range(0, total, chunk)
                    ]
                    with ThreadPoolExecutor(max_workers=streams) as pool:
                        futures = []
                        for index, (start, end) in enumerate(ranges):
                            part = transfer_path.with_name(f"{transfer_path.name}.part{index:03d}")
                            part_paths.append(part)
                            futures.append(
                                pool.submit(self._fetch_range_resumable, url, start, end, part)
                            )
                        for future in futures:
                            future.result()
                    with open(transfer_path, "wb") as out:
                        for part in part_paths:
                            with open(part, "rb") as src:
                                while True:
                                    block = src.read(1024 * 1024)
                                    if not block:
                                        break
                                    out.write(block)
                            part.unlink(missing_ok=True)
                result = {"returncode": 0, "stdout": "", "stderr": ""}
            except Exception as exc:
                for part in transfer_path.parent.glob(f"{transfer_path.name}.part*"):
                    part.unlink(missing_ok=True)
                transfer_path.unlink(missing_ok=True)
                raise RuntimeError(
                    f"S3 Download anonymous HTTPS failed (aws CLI not installed "
                    f"on this host): {exc}"
                ) from exc
        else:
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
            "transport": transport,
            "bucket": str(run_inputs.get("bucket", "") or "").strip(),
            "key": str(run_inputs.get("key", "") or "").strip().lstrip("/"),
            "s3_uri": uri,
            "local_path": str(local_path),
            "size_bytes": local_path.stat().st_size,
            "command": redacted_command(command) if transport == "aws-cli" else url,
            "returncode": 0,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
        }
        metadata_path = output_dir / "download_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {"outputs": {"local_path": str(local_path), "metadata": str(metadata_path)}}

    @staticmethod
    def _fetch_range(url: str, start: int, end: int | None, destination: Any) -> None:
        """Stream one byte range (or the whole object) to destination."""
        headers = {"Range": f"bytes={start}-{end}"} if end is not None else {}
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=300) as resp, open(
            destination, "wb"
        ) as out:
            while True:
                block = resp.read(1024 * 1024)
                if not block:
                    break
                out.write(block)

    RANGE_MAX_RETRIES = 3

    @classmethod
    def _fetch_range_resumable(cls, url: str, start: int, end: int | None, destination: Any) -> None:
        """Fetch a range with per-stream retry and byte-level resume.

        Large cross-continent transfers stall momentarily; a single
        socket timeout on a multi-GB stream must not kill the whole
        parallel download (it did: the 467 GB campaign POD5 lost one
        range after 2.5 h and took the entire e4 leg with it).
        """
        import time as _time

        for attempt in range(cls.RANGE_MAX_RETRIES):
            try:
                # If a partial file exists, resume from its current size.
                offset = 0
                try:
                    offset = os.path.getsize(destination)
                except OSError:
                    pass
                if end is not None and offset >= (end - start + 1):
                    return  # already complete
                resume_start = start + offset
                headers = (
                    {"Range": f"bytes={resume_start}-{end}"}
                    if end is not None
                    else ({"Range": f"bytes={resume_start}-"} if offset > 0 else {})
                )
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=300) as resp, open(
                    destination, "ab" if offset > 0 else "wb"
                ) as out:
                    while True:
                        block = resp.read(1024 * 1024)
                        if not block:
                            break
                        out.write(block)
                return
            except Exception:
                if attempt == cls.RANGE_MAX_RETRIES - 1:
                    raise
                _time.sleep(5 * (attempt + 1))  # linear backoff
