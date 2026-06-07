"""Workflow robustness and observability nodes."""
from __future__ import annotations

import asyncio
import csv
import difflib
import gzip
import html
import hashlib
import json
import math
import os
import platform
import re
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bionodulo.execution.pause_state import PauseStateStore
from bionodulo.nodes.base import BaseNode


def _ctx_log(context: Any, level: str, message: str) -> None:
    if context is not None and hasattr(context, "log"):
        context.log(level, message)


def _ctx_emit(context: Any, event: str, payload: dict[str, Any]) -> None:
    if context is not None and hasattr(context, "emit"):
        context.emit(event, payload)


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    base.mkdir(parents=True, exist_ok=True)
    return base


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, default=str)


class TimerNode(BaseNode):
    """Record a workflow timestamp and pass data through unchanged."""

    NODE_ID = "timer"
    DISPLAY_NAME = "Timer"
    CATEGORY = "workflow"
    DESCRIPTION = "Measure execution time and emit timestamp metadata for workflow profiling"
    SEARCH_ALIASES = ["timer", "time", "duration", "benchmark", "profile", "elapsed"]
    RETURN_TYPES = ("ANY", "FLOAT", "JSON", "JSON")
    RETURN_NAMES = ("passthrough", "elapsed_seconds", "start_time", "end_time")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "Data to pass through"}),
            },
            "optional": {
                "label": ("STRING", {"default": "", "description": "Timer label"}),
                "log_level": (["debug", "info", "warning"], {"default": "info"}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, float, str, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        label = str(kwargs.get("label", "") or getattr(context, "node_id", self.NODE_ID))
        log_level = str(kwargs.get("log_level", "info") or "info")

        start = time.time()
        start_info = {
            "timestamp": start,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start)),
            "label": label,
            "run_id": getattr(context, "run_id", ""),
            "node_id": getattr(context, "node_id", self.NODE_ID),
        }
        end = time.time()
        end_info = {
            **start_info,
            "timestamp": end,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(end)),
        }
        elapsed = max(0.0, end - start)

        if context is not None and hasattr(context, "run_metadata"):
            timers = context.run_metadata.setdefault("timers", [])
            timers.append({"node_id": getattr(context, "node_id", self.NODE_ID), "label": label, "start": start, "end": end})
        _ctx_emit(
            context,
            "timer_elapsed",
            {
                "run_id": getattr(context, "run_id", ""),
                "node_id": getattr(context, "node_id", self.NODE_ID),
                "label": label,
                "elapsed_ms": round(elapsed * 1000, 3),
                "start_time": start_info["iso"],
                "end_time": end_info["iso"],
            },
        )
        _ctx_log(context, log_level, f"Timer '{label}' recorded {elapsed:.6f}s")
        return (data, elapsed, _json_text(start_info), _json_text(end_info))


class ResourceMonitorNode(BaseNode):
    """Check local CPU, memory, and disk availability before continuing."""

    NODE_ID = "resource_monitor"
    DISPLAY_NAME = "Resource Monitor"
    CATEGORY = "workflow"
    DESCRIPTION = "Monitor system resources and gate execution based on CPU, memory, and disk thresholds"
    SEARCH_ALIASES = ["resource", "monitor", "cpu", "memory", "disk", "gate", "threshold"]
    RETURN_TYPES = ("ANY", "BOOLEAN", "JSON")
    RETURN_NAMES = ("passthrough", "resources_ok", "resource_stats")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "Data to pass through when resources are checked"}),
            },
            "optional": {
                "min_free_memory_gb": ("FLOAT", {"default": 4.0, "min": 0.0}),
                "min_free_disk_gb": ("FLOAT", {"default": 10.0, "min": 0.0}),
                "max_cpu_percent": ("FLOAT", {"default": 95.0, "min": 0.0, "max": 100.0}),
                "fail_on_insufficient": ("BOOLEAN", {"default": False}),
                "check_interval_seconds": ("INT", {"default": 0, "min": 0}),
                "max_wait_seconds": ("INT", {"default": 0, "min": 0}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, bool, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        min_mem = float(kwargs.get("min_free_memory_gb", 4.0) or 0.0)
        min_disk = float(kwargs.get("min_free_disk_gb", 10.0) or 0.0)
        max_cpu = float(kwargs.get("max_cpu_percent", 95.0) or 100.0)
        fail_on_insufficient = bool(kwargs.get("fail_on_insufficient", False))
        check_interval = max(0, int(kwargs.get("check_interval_seconds", 0) or 0))
        max_wait = max(0, int(kwargs.get("max_wait_seconds", 0) or 0))

        started = time.time()
        stats = self._get_resource_stats()
        resources_ok = self._check_resources(stats, min_mem, min_disk, max_cpu)
        while not resources_ok and check_interval > 0 and max_wait > 0 and (time.time() - started) < max_wait:
            cancel_event = getattr(context, "cancel_event", None)
            if cancel_event is not None and cancel_event.is_set():
                break
            await asyncio.sleep(min(check_interval, max_wait))
            stats = self._get_resource_stats()
            resources_ok = self._check_resources(stats, min_mem, min_disk, max_cpu)

        stats = {
            **stats,
            "thresholds": {
                "min_free_memory_gb": min_mem,
                "min_free_disk_gb": min_disk,
                "max_cpu_percent": max_cpu,
            },
            "resources_ok": resources_ok,
            "waited_seconds": round(time.time() - started, 3),
        }
        _ctx_emit(
            context,
            "resource_check",
            {
                "run_id": getattr(context, "run_id", ""),
                "node_id": getattr(context, "node_id", self.NODE_ID),
                "passed": resources_ok,
                "stats": stats,
            },
        )

        if not resources_ok:
            message = (
                f"Insufficient resources: mem={stats.get('free_memory_gb')}GB "
                f"(need {min_mem}GB), disk={stats.get('free_disk_gb')}GB "
                f"(need {min_disk}GB), cpu={stats.get('cpu_percent')}% (max {max_cpu}%)"
            )
            _ctx_log(context, "warning", message)
            if fail_on_insufficient:
                raise RuntimeError(message)
        else:
            _ctx_log(context, "info", "Resources OK")

        return (data, resources_ok, _json_text(stats))

    def _get_resource_stats(self) -> dict[str, Any]:
        try:
            import psutil
        except ImportError:
            return {
                "free_memory_gb": 1_000_000.0,
                "free_disk_gb": 1_000_000.0,
                "cpu_percent": 0.0,
                "note": "psutil is not installed; resource check used permissive fallback",
            }

        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "free_memory_gb": round(mem.available / (1024**3), 3),
            "total_memory_gb": round(mem.total / (1024**3), 3),
            "memory_percent": mem.percent,
            "free_disk_gb": round(disk.free / (1024**3), 3),
            "total_disk_gb": round(disk.total / (1024**3), 3),
            "disk_percent": disk.percent,
            "cpu_percent": psutil.cpu_percent(interval=0.0),
            "cpu_count": psutil.cpu_count(),
        }

    @staticmethod
    def _check_resources(stats: dict[str, Any], min_mem: float, min_disk: float, max_cpu: float) -> bool:
        return (
            float(stats.get("free_memory_gb", 0.0)) >= min_mem
            and float(stats.get("free_disk_gb", 0.0)) >= min_disk
            and float(stats.get("cpu_percent", 100.0)) <= max_cpu
        )


class DataValidatorNode(BaseNode):
    """Validate file/data quality before downstream workflow steps."""

    NODE_ID = "data_validator"
    DISPLAY_NAME = "Data Validator"
    CATEGORY = "workflow"
    DESCRIPTION = "Validate data quality, file format, required fields, record counts, and checksums"
    SEARCH_ALIASES = ["validate", "validator", "qc", "check", "verify", "sanity", "format"]
    RETURN_TYPES = ("ANY", "BOOLEAN", "JSON", "FILE")
    RETURN_NAMES = ("passthrough", "passed", "validation_report", "report_file")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "File path or data value to validate"}),
            },
            "optional": {
                "expected_format": (
                    ["auto", "fasta", "fastq", "vcf", "bam", "csv", "tsv", "json", "yaml", "text", "directory"],
                    {"default": "auto"},
                ),
                "min_size_bytes": ("INT", {"default": 0, "min": 0}),
                "max_size_bytes": ("INT", {"default": 0, "min": 0}),
                "required_fields": ("STRING", {"default": "", "description": "Comma-separated required fields"}),
                "min_records": ("INT", {"default": 0, "min": 0}),
                "checksum_expected": ("STRING", {"default": "", "description": "Expected SHA-256 checksum"}),
                "fail_on_error": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, bool, str, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        expected_format = str(kwargs.get("expected_format", "auto") or "auto").lower()
        min_size = int(kwargs.get("min_size_bytes", 0) or 0)
        max_size = int(kwargs.get("max_size_bytes", 0) or 0)
        required_fields = [field.strip() for field in str(kwargs.get("required_fields", "") or "").split(",") if field.strip()]
        min_records = int(kwargs.get("min_records", 0) or 0)
        checksum_expected = str(kwargs.get("checksum_expected", "") or "").strip()
        fail_on_error = bool(kwargs.get("fail_on_error", True))

        report: dict[str, Any] = {
            "input": str(data)[:500],
            "expected_format": expected_format,
            "checks": {},
            "warnings": [],
            "errors": [],
        }
        passed = True
        if data == []:
            report["errors"].append("No input data provided")
            passed = False
        elif self._is_path_list(data, expected_format):
            passed = self._validate_path_list(
                [Path(str(item)) for item in data],
                expected_format,
                report,
                min_size,
                max_size,
                required_fields,
            )
            if passed and min_records > 0:
                records = self._record_count(report)
                if records < min_records:
                    report["errors"].append(f"Too few records: {records} (min: {min_records})")
                    passed = False
            if passed and checksum_expected:
                report["errors"].append("Checksum validation is not supported for multiple inputs")
                passed = False
        else:
            path = self._materialize_input(data, context)
            if path is None:
                report["errors"].append("No input data provided")
                passed = False
            else:
                passed = self._validate_path(path, expected_format, report, min_size, max_size)
                if passed and checksum_expected:
                    passed = self._verify_checksum(path, checksum_expected, report)
                if passed and min_records > 0:
                    records = self._record_count(report)
                    if records < min_records:
                        report["errors"].append(f"Too few records: {records} (min: {min_records})")
                        passed = False
                if passed and required_fields:
                    passed = self._check_required_fields(path, expected_format, required_fields, report)

        report["passed"] = passed
        report["check_count"] = len(report["checks"])
        report["error_count"] = len(report["errors"])

        report_file = ""
        if context is not None:
            report_path = _node_output_dir(self, context) / "validation_report.json"
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
            report_file = str(report_path)

        _ctx_log(context, "info" if passed else "warning", f"Validation: {'PASSED' if passed else 'FAILED'} ({report['error_count']} errors)")
        if not passed and fail_on_error:
            raise RuntimeError(f"Data validation failed: {'; '.join(report['errors'])}")

        return (data, passed, _json_text(report), report_file)

    @staticmethod
    def _is_path_list(data: Any, expected_format: str) -> bool:
        path_formats = {"auto", "fasta", "fastq", "vcf", "bam", "csv", "tsv", "text", "directory"}
        return (
            expected_format in path_formats
            and isinstance(data, (list, tuple))
            and bool(data)
            and all(isinstance(item, (str, Path)) for item in data)
        )

    @staticmethod
    def _record_count(report: dict[str, Any]) -> int:
        checks = report.get("checks", {})
        return int(checks.get("record_count", checks.get("row_count", checks.get("variant_count", 0))) or 0)

    def _materialize_input(self, data: Any, context: Any) -> Path | None:
        if data is None:
            return None
        if isinstance(data, (str, Path)):
            return Path(str(data))
        if context is None:
            return None
        path = _node_output_dir(self, context) / "validator_input.data"
        if isinstance(data, (dict, list)):
            path.write_text(json.dumps(data, sort_keys=True, default=str), encoding="utf-8")
        else:
            path.write_text(str(data), encoding="utf-8")
        return path

    def _validate_path_list(
        self,
        paths: list[Path],
        expected_format: str,
        report: dict[str, Any],
        min_size: int,
        max_size: int,
        required_fields: list[str],
    ) -> bool:
        file_reports: list[dict[str, Any]] = []
        passed = True
        total_size = 0
        total_records = 0

        for index, path in enumerate(paths, start=1):
            file_report: dict[str, Any] = {
                "input": str(path),
                "checks": {},
                "warnings": [],
                "errors": [],
            }
            file_passed = self._validate_path(path, expected_format, file_report, min_size, max_size)
            if file_passed and required_fields:
                file_passed = self._check_required_fields(path, expected_format, required_fields, file_report)

            if not file_passed:
                passed = False
                for error in file_report["errors"]:
                    report["errors"].append(f"Input {index} ({path}): {error}")
            report["warnings"].extend(f"Input {index} ({path}): {warning}" for warning in file_report["warnings"])

            total_size += int(file_report["checks"].get("file_size_bytes", 0) or 0)
            total_records += self._record_count(file_report)
            file_reports.append(file_report)

        report["checks"]["file_count"] = len(paths)
        report["checks"]["total_size_bytes"] = total_size
        report["checks"]["record_count"] = total_records
        report["checks"]["files"] = file_reports
        return passed

    def _validate_path(
        self,
        path: Path,
        expected_format: str,
        report: dict[str, Any],
        min_size: int,
        max_size: int,
    ) -> bool:
        if not path.exists():
            report["errors"].append(f"File not found: {path}")
            return False
        if expected_format == "directory":
            return self._validate_directory(path, report, min_size, max_size)
        if not path.is_file():
            report["errors"].append(f"Path is not a file: {path}")
            return False
        size = path.stat().st_size
        report["checks"]["file_exists"] = True
        report["checks"]["file_size_bytes"] = size
        if min_size > 0 and size < min_size:
            report["errors"].append(f"File too small: {size} bytes (min: {min_size})")
            return False
        if max_size > 0 and size > max_size:
            report["errors"].append(f"File too large: {size} bytes (max: {max_size})")
            return False
        report["checks"]["size_ok"] = True

        fmt = self._detect_format(path, expected_format)
        report["checks"]["detected_format"] = fmt
        validator = {
            "fasta": self._validate_fasta,
            "fastq": self._validate_fastq,
            "vcf": self._validate_vcf,
            "bam": self._validate_bam,
            "csv": self._validate_csv,
            "tsv": self._validate_tsv,
            "json": self._validate_json,
            "yaml": self._validate_yaml,
            "text": self._validate_text,
        }.get(fmt, self._validate_text)
        return validator(path, report)

    @staticmethod
    def _detect_format(path: Path, expected_format: str) -> str:
        if expected_format != "auto":
            return expected_format
        suffixes = [suffix.lower() for suffix in path.suffixes]
        if ".fasta" in suffixes or ".fa" in suffixes or ".fna" in suffixes:
            return "fasta"
        if ".fastq" in suffixes or ".fq" in suffixes:
            return "fastq"
        if ".vcf" in suffixes:
            return "vcf"
        if ".bam" in suffixes:
            return "bam"
        if ".csv" in suffixes:
            return "csv"
        if ".tsv" in suffixes:
            return "tsv"
        if ".json" in suffixes:
            return "json"
        if ".yaml" in suffixes or ".yml" in suffixes:
            return "yaml"
        return "text"

    def _validate_directory(
        self,
        path: Path,
        report: dict[str, Any],
        min_size: int,
        max_size: int,
    ) -> bool:
        if not path.is_dir():
            report["errors"].append(f"Path is not a directory: {path}")
            return False
        file_count = 0
        directory_count = 0
        total_size = 0
        try:
            for child in path.rglob("*"):
                if child.is_file():
                    file_count += 1
                    total_size += child.stat().st_size
                elif child.is_dir():
                    directory_count += 1
        except OSError as exc:
            report["errors"].append(f"Directory validation error: {exc}")
            return False

        report["checks"]["directory_exists"] = True
        report["checks"]["file_count"] = file_count
        report["checks"]["directory_count"] = directory_count
        report["checks"]["total_size_bytes"] = total_size
        if min_size > 0 and total_size < min_size:
            report["errors"].append(f"Directory contents too small: {total_size} bytes (min: {min_size})")
            return False
        if max_size > 0 and total_size > max_size:
            report["errors"].append(f"Directory contents too large: {total_size} bytes (max: {max_size})")
            return False
        report["checks"]["size_ok"] = True
        report["checks"]["format_valid"] = True
        return True

    @staticmethod
    def _read_text_lines(path: Path) -> list[str]:
        if path.suffix.lower() == ".gz":
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as handle:
                return handle.read().splitlines()
        return path.read_text(encoding="utf-8", errors="replace").splitlines()

    def _validate_fasta(self, path: Path, report: dict[str, Any]) -> bool:
        records = 0
        saw_sequence = False
        try:
            for line in self._read_text_lines(path):
                if line.startswith(">"):
                    records += 1
                    saw_sequence = False
                elif line.strip():
                    saw_sequence = True
            if records == 0 or not saw_sequence:
                report["errors"].append("FASTA: missing header or sequence")
                return False
            report["checks"]["record_count"] = records
            report["checks"]["format_valid"] = True
            return True
        except OSError as exc:
            report["errors"].append(f"FASTA validation error: {exc}")
            return False

    def _validate_fastq(self, path: Path, report: dict[str, Any]) -> bool:
        lines = self._read_text_lines(path)
        if len(lines) == 0 or len(lines) % 4 != 0:
            report["errors"].append(f"FASTQ: line count {len(lines)} is not divisible by 4")
            return False
        for idx in range(0, len(lines), 4):
            if not lines[idx].startswith("@") or not lines[idx + 2].startswith("+"):
                report["errors"].append(f"FASTQ: invalid record starting at line {idx + 1}")
                return False
        report["checks"]["record_count"] = len(lines) // 4
        report["checks"]["format_valid"] = True
        return True

    def _validate_vcf(self, path: Path, report: dict[str, Any]) -> bool:
        header_lines = 0
        variant_count = 0
        for line in self._read_text_lines(path):
            if line.startswith("#"):
                header_lines += 1
            elif line.strip():
                variant_count += 1
        if header_lines == 0:
            report["errors"].append("VCF: no header lines found")
            return False
        report["checks"]["header_lines"] = header_lines
        report["checks"]["variant_count"] = variant_count
        report["checks"]["format_valid"] = True
        return True

    def _validate_bam(self, path: Path, report: dict[str, Any]) -> bool:
        with path.open("rb") as handle:
            magic = handle.read(4)
        if magic != b"BAM\1":
            report["warnings"].append("BAM: file does not start with uncompressed BAM magic; compressed BAM cannot be deeply validated here")
        report["checks"]["format_valid"] = True
        return True

    def _validate_csv(self, path: Path, report: dict[str, Any]) -> bool:
        return self._validate_delimited(path, report, delimiter=",", label="CSV")

    def _validate_tsv(self, path: Path, report: dict[str, Any]) -> bool:
        return self._validate_delimited(path, report, delimiter="\t", label="TSV")

    def _validate_delimited(self, path: Path, report: dict[str, Any], *, delimiter: str, label: str) -> bool:
        try:
            with path.open(newline="", encoding="utf-8", errors="replace") as handle:
                rows = list(csv.reader(handle, delimiter=delimiter))
        except csv.Error as exc:
            report["errors"].append(f"{label}: {exc}")
            return False
        if not rows:
            report["errors"].append(f"{label}: empty file")
            return False
        report["checks"]["column_count"] = len(rows[0])
        report["checks"]["row_count"] = max(0, len(rows) - 1)
        report["checks"]["format_valid"] = True
        return True

    def _validate_json(self, path: Path, report: dict[str, Any]) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report["errors"].append(f"JSON validation error: {exc}")
            return False
        if isinstance(data, list):
            report["checks"]["record_count"] = len(data)
        elif isinstance(data, dict):
            report["checks"]["field_count"] = len(data)
        report["checks"]["format_valid"] = True
        return True

    def _validate_yaml(self, path: Path, report: dict[str, Any]) -> bool:
        try:
            import yaml
        except ImportError:
            report["errors"].append("YAML validation requires PyYAML")
            return False
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            report["errors"].append(f"YAML validation error: {exc}")
            return False
        if isinstance(data, list):
            report["checks"]["record_count"] = len(data)
        elif isinstance(data, dict):
            report["checks"]["field_count"] = len(data)
        report["checks"]["format_valid"] = True
        return True

    def _validate_text(self, path: Path, report: dict[str, Any]) -> bool:
        report["checks"]["line_count"] = len(self._read_text_lines(path))
        report["checks"]["format_valid"] = True
        return True

    def _verify_checksum(self, path: Path, expected: str, report: dict[str, Any]) -> bool:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        report["checks"]["checksum_expected"] = expected
        report["checks"]["checksum_actual"] = actual
        if actual.lower() != expected.lower():
            report["errors"].append(f"Checksum mismatch: expected {expected[:16]}..., got {actual[:16]}...")
            return False
        report["checks"]["checksum_ok"] = True
        return True

    def _check_required_fields(
        self,
        path: Path,
        expected_format: str,
        required_fields: list[str],
        report: dict[str, Any],
    ) -> bool:
        fmt = self._detect_format(path, expected_format)
        fields: set[str] = set()
        if fmt in {"csv", "tsv"}:
            delimiter = "\t" if fmt == "tsv" else ","
            with path.open(newline="", encoding="utf-8", errors="replace") as handle:
                rows = csv.reader(handle, delimiter=delimiter)
                fields = set(next(rows, []))
        elif fmt == "json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                fields = set(data.keys())
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                fields = set(data[0].keys())
        else:
            report["warnings"].append(f"Required fields are not supported for {fmt}")
            return True

        missing = [field for field in required_fields if field not in fields]
        if missing:
            report["errors"].append(f"Missing required fields: {missing}")
            return False
        report["checks"]["required_fields_ok"] = True
        return True


class ProvenanceNode(BaseNode):
    """Capture reproducibility metadata and pass data through unchanged."""

    NODE_ID = "provenance"
    DISPLAY_NAME = "Provenance"
    CATEGORY = "workflow"
    DESCRIPTION = "Capture provenance metadata for reproducibility, including tool versions, parameters, inputs, and environment"
    SEARCH_ALIASES = ["provenance", "metadata", "reproducibility", "audit", "trace", "lineage", "cwl"]
    RETURN_TYPES = ("ANY", "JSON", "FILE")
    RETURN_NAMES = ("passthrough", "provenance_record", "provenance_file")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "Data or artifact reference to pass through and record"}),
            },
            "optional": {
                "tool_name": ("STRING", {"default": "", "description": "Tool or workflow step name"}),
                "tool_version": ("STRING", {"default": "", "description": "Tool version"}),
                "tool_command": ("STRING", {"default": "", "multiline": True, "description": "Command or invocation"}),
                "description": ("STRING", {"default": "", "multiline": True, "description": "Human-readable provenance note"}),
                "custom_metadata": ("JSON", {"default": "{}", "multiline": True}),
                "include_system_info": ("BOOLEAN", {"default": True}),
                "standard": (["w3c", "cwlprov", "native"], {"default": "w3c"}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, str, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        standard = str(kwargs.get("standard", "w3c") or "w3c").lower()
        custom = self._parse_custom_metadata(kwargs.get("custom_metadata", "{}"))
        system_info = self._system_info() if bool(kwargs.get("include_system_info", True)) else {}
        params = self._merged_params(kwargs, context, system_info)

        if standard == "w3c":
            record = self._build_w3c_record(data, params, context, custom)
        elif standard == "cwlprov":
            record = self._build_cwlprov_record(data, params, context, custom)
        elif standard == "native":
            record = self._build_native_record(data, params, context, custom, system_info)
        else:
            raise ValueError(f"Unsupported provenance standard: {standard}")

        provenance_file = ""
        if context is not None:
            output_path = _node_output_dir(self, context) / "provenance.json"
            output_path.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8")
            provenance_file = str(output_path)

        tool_name = params.get("tool_name") or getattr(context, "node_id", self.NODE_ID)
        _ctx_log(context, "info", f"Provenance recorded for {tool_name}")
        return (data, _json_text(record), provenance_file)

    def _merged_params(self, kwargs: dict[str, Any], context: Any, system_info: dict[str, Any]) -> dict[str, Any]:
        context_params = getattr(context, "params", {}) if context is not None else {}
        merged = dict(context_params) if isinstance(context_params, dict) else {}
        merged.update(
            {
                "tool_name": str(kwargs.get("tool_name", "") or getattr(context, "node_type", "") or ""),
                "tool_version": str(kwargs.get("tool_version", "") or ""),
                "tool_command": str(kwargs.get("tool_command", "") or ""),
                "description": str(kwargs.get("description", "") or ""),
                "include_system_info": bool(kwargs.get("include_system_info", True)),
                "_timestamp": system_info.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "_timestamp_unix": system_info.get("timestamp_unix") or time.time(),
            }
        )
        return merged

    @staticmethod
    def _parse_custom_metadata(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value in (None, ""):
            return {}
        try:
            parsed = json.loads(str(value))
        except json.JSONDecodeError:
            return {"parse_error": str(value)}
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    @staticmethod
    def _system_info() -> dict[str, Any]:
        return {
            "platform": platform.platform(),
            "python_version": sys.version,
            "processor": platform.processor(),
            "machine": platform.machine(),
            "hostname": platform.node(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "timestamp_unix": time.time(),
        }

    def _build_w3c_record(
        self,
        data: Any,
        params: dict[str, Any],
        context: Any,
        custom: dict[str, Any],
    ) -> dict[str, Any]:
        node_id = getattr(context, "node_id", self.NODE_ID)
        tool_name = params.get("tool_name") or "unknown"
        return {
            "@context": "https://www.w3.org/ns/prov.jsonld",
            "@type": "Activity",
            "@id": f"urn:bionodulo:activity:{node_id}",
            "startedAtTime": params.get("_timestamp"),
            "endedAtTime": params.get("_timestamp"),
            "wasAssociatedWith": {
                "@type": "Agent",
                "@id": f"urn:bionodulo:agent:{tool_name}",
                "name": tool_name,
                "version": params.get("tool_version", ""),
            },
            "used": {
                "@type": "Entity",
                "@id": f"urn:bionodulo:entity:input:{node_id}",
                "value": self._record_value(data, 500),
            },
            "parameters": self._public_params(params),
            "custom_metadata": custom,
        }

    def _build_cwlprov_record(
        self,
        data: Any,
        params: dict[str, Any],
        context: Any,
        custom: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "class": "provenance_record",
            "run_id": getattr(context, "run_id", "unknown"),
            "step_id": getattr(context, "node_id", self.NODE_ID),
            "tool": {
                "name": params.get("tool_name", ""),
                "version": params.get("tool_version", ""),
                "command": params.get("tool_command", ""),
            },
            "inputs": {"data": self._record_value(data, 1000)},
            "parameters": self._public_params(params),
            "timestamp": params.get("_timestamp"),
            "custom": custom,
        }

    def _build_native_record(
        self,
        data: Any,
        params: dict[str, Any],
        context: Any,
        custom: dict[str, Any],
        system_info: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "bionodulo_provenance": {
                "version": "1.0",
                "run_id": getattr(context, "run_id", "unknown"),
                "node_id": getattr(context, "node_id", self.NODE_ID),
                "node_type": getattr(context, "node_type", "unknown"),
                "timestamp": params.get("_timestamp"),
                "tool": {
                    "name": params.get("tool_name", ""),
                    "version": params.get("tool_version", ""),
                    "command": params.get("tool_command", ""),
                },
                "description": params.get("description", ""),
                "inputs": {"data": self._record_value(data, 2000)},
                "parameters": self._public_params(params),
                "system": system_info if params.get("include_system_info", True) else {"omitted": True},
                "custom_metadata": custom,
            }
        }

    @staticmethod
    def _record_value(value: Any, max_length: int) -> Any:
        if isinstance(value, (dict, list)):
            return value
        return str(value)[:max_length]

    @staticmethod
    def _public_params(params: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in params.items() if not key.startswith("_")}


class CompareResultsNode(BaseNode):
    """Compare outputs from two workflow branches."""

    NODE_ID = "compare_results"
    DISPLAY_NAME = "Compare Results"
    CATEGORY = "workflow"
    DESCRIPTION = "Compare outputs from two branches. Diff, checksum, or statistical comparison. Generate comparison report."
    SEARCH_ALIASES = ["compare", "diff", "checksum", "validate", "benchmark", "test"]
    RETURN_TYPES = ("JSON", "BOOLEAN", "FILE")
    RETURN_NAMES = ("comparison_report", "match", "diff_file")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "result_a": ("ANY", {}),
                "result_b": ("ANY", {}),
            },
            "optional": {
                "comparison_method": (["checksum", "diff", "exact", "size", "statistical"], {"default": "checksum"}),
                "tolerance": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "output_format": (["json", "html", "txt"], {"default": "json"}),
                "ignore_patterns": ("STRING", {"default": ""}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, bool, str]:
        context = kwargs.pop("context", None)
        result_a = kwargs.get("result_a")
        result_b = kwargs.get("result_b")
        method = str(kwargs.get("comparison_method", "checksum") or "checksum").lower()
        tolerance = max(0.0, float(kwargs.get("tolerance", 0.0) or 0.0))
        output_format = str(kwargs.get("output_format", "json") or "json").lower()
        ignore_patterns = self._parse_ignore_patterns(kwargs.get("ignore_patterns", ""))

        report: dict[str, Any] = {
            "comparison_method": method,
            "result_a_type": type(result_a).__name__,
            "result_b_type": type(result_b).__name__,
            "tolerance": tolerance,
            "ignored_patterns": ignore_patterns,
        }
        diff_content = ""

        if method == "checksum":
            checksum_a = self._compute_checksum(result_a)
            checksum_b = self._compute_checksum(result_b)
            match = checksum_a == checksum_b
            report.update({"checksum_a": checksum_a, "checksum_b": checksum_b, "match": match})
        elif method == "exact":
            match = result_a == result_b
            report["match"] = match
        elif method == "diff":
            diff_content = self._diff_results(result_a, result_b, ignore_patterns)
            match = diff_content == ""
            report.update({"match": match, "diff_lines": len(diff_content.splitlines())})
        elif method == "size":
            size_a = self._size_of(result_a)
            size_b = self._size_of(result_b)
            difference = abs(size_a - size_b)
            match = difference <= tolerance
            report.update({"size_a": size_a, "size_b": size_b, "size_difference": difference, "match": match})
        elif method == "statistical":
            match = self._statistical_compare(result_a, result_b, tolerance, report)
        else:
            raise ValueError(f"Unsupported comparison method: {method}")

        report["overall_match"] = match
        diff_file = self._write_artifact(context, output_format, report, diff_content)

        level = "info" if match else "warning"
        _ctx_log(context, level, f"Compare Results [{method}]: match={match}")
        return (_json_text(report), match, diff_file)

    @staticmethod
    def _parse_ignore_patterns(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [pattern.strip() for pattern in str(value or "").split(",") if pattern.strip()]

    def _compute_checksum(self, value: Any) -> str:
        return hashlib.sha256(self._canonical_bytes(value)).hexdigest()

    def _canonical_bytes(self, value: Any) -> bytes:
        path = self._existing_path(value)
        if path is not None:
            return path.read_bytes()
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return str(value).encode("utf-8")

    @staticmethod
    def _existing_path(value: Any) -> Path | None:
        if not isinstance(value, (str, Path)):
            return None
        try:
            path = Path(value)
            return path if path.exists() and path.is_file() else None
        except OSError:
            return None

    def _diff_results(self, result_a: Any, result_b: Any, ignore_patterns: list[str]) -> str:
        lines_a = self._lines_for_diff(result_a)
        lines_b = self._lines_for_diff(result_b)
        if ignore_patterns:
            regexes = [re.compile(pattern) for pattern in ignore_patterns]
            lines_a = [line for line in lines_a if not any(regex.search(line) for regex in regexes)]
            lines_b = [line for line in lines_b if not any(regex.search(line) for regex in regexes)]
        diff = difflib.unified_diff(lines_a, lines_b, fromfile="result_a", tofile="result_b", lineterm="")
        return "\n".join(diff)

    @staticmethod
    def _lines_for_diff(value: Any) -> list[str]:
        path = CompareResultsNode._existing_path(value)
        if path is not None:
            try:
                return path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                return [path.read_bytes().hex()]
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, indent=2, sort_keys=True, default=str).splitlines()
        return str(value).splitlines()

    def _size_of(self, value: Any) -> int:
        path = self._existing_path(value)
        if path is not None:
            return path.stat().st_size
        return len(self._canonical_bytes(value))

    def _statistical_compare(self, result_a: Any, result_b: Any, tolerance: float, report: dict[str, Any]) -> bool:
        values_a = self._numeric_values(result_a)
        values_b = self._numeric_values(result_b)
        if len(values_a) != len(values_b):
            report.update({"match": False, "shape_mismatch": f"{len(values_a)} vs {len(values_b)}"})
            return False
        if not values_a:
            report.update({"match": True, "max_difference": 0.0, "mean_difference": 0.0})
            return True
        differences = [abs(a - b) for a, b in zip(values_a, values_b, strict=True)]
        max_difference = max(differences)
        mean_difference = math.fsum(differences) / len(differences)
        match = all(difference <= tolerance for difference in differences)
        report.update(
            {
                "match": match,
                "count": len(differences),
                "max_difference": max_difference,
                "mean_difference": mean_difference,
            }
        )
        return match

    @staticmethod
    def _numeric_values(value: Any) -> list[float]:
        if isinstance(value, dict):
            value = list(value.values())
        if isinstance(value, (list, tuple)):
            return [float(item) for item in value]
        return [float(value)]

    def _write_artifact(self, context: Any, output_format: str, report: dict[str, Any], diff_content: str) -> str:
        if context is None:
            return ""
        output_dir = _node_output_dir(self, context)
        if output_format == "html":
            path = output_dir / "comparison_report.html"
            path.write_text(self._format_html_report(report, diff_content), encoding="utf-8")
            return str(path)
        if output_format == "txt":
            path = output_dir / "comparison_report.txt"
            path.write_text(self._format_text_report(report, diff_content), encoding="utf-8")
            return str(path)
        if diff_content:
            path = output_dir / "diff.txt"
            path.write_text(diff_content, encoding="utf-8")
            return str(path)
        return ""

    @staticmethod
    def _format_text_report(report: dict[str, Any], diff_content: str) -> str:
        sections = ["Comparison Report", json.dumps(report, indent=2, sort_keys=True, default=str)]
        if diff_content:
            sections.extend(["Diff", diff_content])
        return "\n\n".join(sections)

    @staticmethod
    def _format_html_report(report: dict[str, Any], diff_content: str) -> str:
        status_color = "#15803d" if report.get("match") else "#b91c1c"
        status_text = "MATCH" if report.get("match") else "MISMATCH"
        report_json = html.escape(json.dumps(report, indent=2, sort_keys=True, default=str))
        diff_html = html.escape(diff_content[:20_000])
        return (
            "<!doctype html><html><head><meta charset=\"utf-8\"><title>Comparison Report</title>"
            "<style>body{font-family:system-ui,sans-serif;padding:24px;max-width:960px;margin:0 auto}"
            "pre{background:#f8fafc;padding:16px;border-radius:4px;overflow:auto}"
            f".status{{display:inline-block;padding:4px 10px;border-radius:4px;color:white;background:{status_color}}}"
            "</style></head><body>"
            f"<h1>Comparison Report <span class=\"status\">{status_text}</span></h1>"
            f"<pre>{report_json}</pre><h2>Diff</h2><pre>{diff_html}</pre></body></html>"
        )


class CheckpointNode(BaseNode):
    """Persist a workflow value to a checkpoint artifact."""

    NODE_ID = "checkpoint"
    DISPLAY_NAME = "Checkpoint"
    CATEGORY = "workflow"
    DESCRIPTION = "Save workflow state snapshot. Persist intermediate results for resumable workflows."
    SEARCH_ALIASES = ["checkpoint", "snapshot", "save", "resume", "persist", "state"]
    RETURN_TYPES = ("ANY", "FILE", "JSON")
    RETURN_NAMES = ("passthrough", "checkpoint_file", "checkpoint_info")
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = "always_run"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "Data to checkpoint"}),
            },
            "optional": {
                "checkpoint_name": ("STRING", {"default": "", "description": "Checkpoint name; generated from node and time when empty"}),
                "include_upstream_metadata": ("BOOLEAN", {"default": True}),
                "compression": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, str, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        include_metadata = bool(kwargs.get("include_upstream_metadata", True))
        compress = bool(kwargs.get("compression", True))
        checkpoint_name = self._checkpoint_name(kwargs.get("checkpoint_name", ""), context)
        checkpoint_dir = self._checkpoint_dir(context)

        timestamp = time.time()
        payload: dict[str, Any] = {
            "version": "1.0",
            "checkpoint_name": checkpoint_name,
            "timestamp": timestamp,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timestamp)),
            "data": data,
        }
        if include_metadata and context is not None:
            payload["run_metadata"] = self._context_metadata(context)

        suffix = ".json.gz" if compress else ".json"
        checkpoint_path = (checkpoint_dir / f"{checkpoint_name}{suffix}").resolve()
        json_bytes = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
        if compress:
            checkpoint_path.write_bytes(gzip.compress(json_bytes))
        else:
            checkpoint_path.write_bytes(json_bytes)

        checkpoint_info = {
            "checkpoint_name": checkpoint_name,
            "checkpoint_path": str(checkpoint_path),
            "timestamp": timestamp,
            "timestamp_iso": payload["timestamp_iso"],
            "compressed": compress,
            "size_bytes": checkpoint_path.stat().st_size,
            "resume_manifest_supported": True,
            "resume_supported": True,
            "note": "Checkpoint artifact and resume manifest written; downstream executor resume is supported for checkpoint nodes.",
        }
        manifest_path = self._update_checkpoint_manifest(checkpoint_dir, checkpoint_info, context)
        checkpoint_info["manifest_path"] = str(manifest_path)

        _ctx_log(context, "info", f"Checkpoint saved: {checkpoint_path}")
        _ctx_emit(
            context,
            "checkpoint_saved",
            {
                "run_id": getattr(context, "run_id", ""),
                "node_id": getattr(context, "node_id", self.NODE_ID),
                "checkpoint_path": str(checkpoint_path),
                "compressed": compress,
                "manifest_path": str(manifest_path),
            },
        )
        return (data, str(checkpoint_path), _json_text(checkpoint_info))

    def _checkpoint_dir(self, context: Any) -> Path:
        workspace_dir = getattr(context, "workspace_dir", None) if context is not None else None
        if workspace_dir:
            base = Path(workspace_dir) / "checkpoints"
        elif context is not None:
            base = _node_output_dir(self, context) / "checkpoints"
        else:
            base = Path("checkpoints")
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _checkpoint_name(self, value: Any, context: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            node_id = getattr(context, "node_id", self.NODE_ID)
            raw = f"{node_id}_{int(time.time())}"
        sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")
        return sanitized or f"{self.NODE_ID}_{int(time.time())}"

    @staticmethod
    def _context_metadata(context: Any) -> dict[str, Any]:
        params = getattr(context, "params", {})
        public_params = {key: value for key, value in params.items() if not str(key).startswith("_")} if isinstance(params, dict) else {}
        metadata = {
            "run_id": getattr(context, "run_id", ""),
            "node_id": getattr(context, "node_id", ""),
            "node_type": getattr(context, "node_type", ""),
            "params": public_params,
        }
        workflow_metadata = getattr(context, "run_metadata", None)
        if isinstance(workflow_metadata, dict) and workflow_metadata:
            metadata["workflow"] = json.loads(json.dumps(workflow_metadata, sort_keys=True, default=str))
        return metadata

    def _update_checkpoint_manifest(self, checkpoint_dir: Path, checkpoint_info: dict[str, Any], context: Any) -> Path:
        manifest_path = checkpoint_dir / "checkpoint_manifest.json"
        manifest = self._read_checkpoint_manifest(manifest_path)
        entry = {
            "checkpoint_name": checkpoint_info["checkpoint_name"],
            "checkpoint_path": checkpoint_info["checkpoint_path"],
            "timestamp": checkpoint_info["timestamp"],
            "timestamp_iso": checkpoint_info["timestamp_iso"],
            "compressed": checkpoint_info["compressed"],
            "size_bytes": checkpoint_info["size_bytes"],
            "run_id": getattr(context, "run_id", ""),
            "node_id": getattr(context, "node_id", self.NODE_ID),
            "node_type": getattr(context, "node_type", ""),
        }
        for key in ("resume_manifest_supported", "resume_supported", "note"):
            if key in checkpoint_info:
                entry[key] = checkpoint_info[key]
        manifest["updated_at"] = checkpoint_info["timestamp"]
        manifest["updated_at_iso"] = checkpoint_info["timestamp_iso"]
        manifest.setdefault("checkpoints", {})[entry["checkpoint_path"]] = entry
        manifest.setdefault("latest_by_name", {})[entry["checkpoint_name"]] = entry
        manifest.setdefault("latest_by_run_node", {})[self._run_node_key(entry["run_id"], entry["node_id"])] = entry
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return manifest_path

    @staticmethod
    def _read_checkpoint_manifest(manifest_path: Path) -> dict[str, Any]:
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"checkpoint manifest is not valid JSON: {manifest_path}") from exc
            if not isinstance(manifest, dict):
                raise ValueError(f"checkpoint manifest must be a JSON object: {manifest_path}")
            manifest.setdefault("version", "1.0")
            manifest.setdefault("checkpoints", {})
            manifest.setdefault("latest_by_name", {})
            manifest.setdefault("latest_by_run_node", {})
            return manifest
        return {
            "version": "1.0",
            "checkpoints": {},
            "latest_by_name": {},
            "latest_by_run_node": {},
        }

    @classmethod
    def resolve_checkpoint(cls, manifest_path: str | Path, run_id: str = "", node_id: str = "", checkpoint_name: str = "") -> dict[str, Any]:
        manifest = cls._read_checkpoint_manifest(Path(manifest_path))
        if run_id or node_id:
            entry = manifest.get("latest_by_run_node", {}).get(cls._run_node_key(run_id, node_id))
            if entry:
                return dict(entry)
        if checkpoint_name:
            entry = manifest.get("latest_by_name", {}).get(checkpoint_name)
            if entry:
                return dict(entry)
        return {}

    @staticmethod
    def _run_node_key(run_id: Any, node_id: Any) -> str:
        return f"{run_id}:{node_id}"


class MemoizeNode(BaseNode):
    """Hash inputs and persist a reusable memoization marker."""

    NODE_ID = "memoize"
    DISPLAY_NAME = "Memoize"
    CATEGORY = "workflow"
    DESCRIPTION = "Function memoization for expensive operations. Hash inputs, cache results, auto-invalidate on parameter changes."
    SEARCH_ALIASES = ["memoize", "memo", "hash", "fingerprint", "dedup"]
    RETURN_TYPES = ("ANY", "STRING", "JSON")
    RETURN_NAMES = ("output", "hash", "memo_info")
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = "always_run"
    SUPPORTED_ALGORITHMS = {"sha256", "md5", "blake2b"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "Input data to memoize"}),
            },
            "optional": {
                "salt": ("STRING", {"default": "", "description": "Extra salt for hash, such as tool version or database version"}),
                "hash_algorithm": (["sha256", "md5", "blake2b"], {"default": "sha256"}),
                "cache_dir": ("STRING", {"default": "", "description": "Custom cache directory"}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, str, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        salt = str(kwargs.get("salt", "") or "")
        algorithm = str(kwargs.get("hash_algorithm", "sha256") or "sha256").lower()
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

        input_hash = self._compute_hash(data, salt, algorithm)
        cache_key = f"memoize_{input_hash[:24]}"
        cache_dir = self._cache_dir(kwargs.get("cache_dir", ""), context)

        from bionodulo.execution.cache import CacheStore

        cache = CacheStore(cache_dir)
        try:
            memo_info = {
                "input_hash": input_hash,
                "algorithm": algorithm,
                "salt": salt,
                "cache_key": cache_key,
                "cache_dir": str(cache_dir),
                "executor_skip_supported": False,
            }

            cached_output = data
            if cache.is_hit(cache_key):
                marker = cache.read_marker(cache_key) or {}
                outputs = marker.get("outputs", {}) if isinstance(marker, dict) else {}
                cached_output = outputs.get("data", data)
                memo_info.update({"status": "hit", "cached_at": marker.get("cached_at"), "cache_marker_found": True})
                _ctx_log(context, "info", f"Memoize hit: hash={input_hash[:16]}...")
            else:
                cache.write_marker(cache_key, outputs={"data": data, "hash": input_hash})
                memo_info.update({"status": "miss", "cached_at": None})
                _ctx_log(context, "info", f"Memoize miss: stored hash={input_hash[:16]}...")
        finally:
            cache.close()

        return (cached_output, input_hash, _json_text(memo_info))

    def _compute_hash(self, data: Any, salt: str, algorithm: str) -> str:
        payload = {
            "input": data,
            "salt": salt,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        hasher = hashlib.new(algorithm)
        hasher.update(serialized.encode("utf-8"))
        return hasher.hexdigest()

    @staticmethod
    def _cache_dir(value: Any, context: Any) -> Path:
        custom = str(value or "").strip()
        if custom:
            base = Path(custom)
        else:
            workspace_dir = getattr(context, "workspace_dir", None) if context is not None else None
            base = Path(workspace_dir) / "cache" if workspace_dir else Path("cache")
        base.mkdir(parents=True, exist_ok=True)
        return base


class CacheControlNode(BaseNode):
    """Store and retrieve a value through an explicit cache marker."""

    NODE_ID = "cache_control"
    DISPLAY_NAME = "Cache Control"
    CATEGORY = "workflow"
    DESCRIPTION = "Explicit cache control. Check cache first, execute downstream only on cache miss. Supports TTL and invalidation rules."
    SEARCH_ALIASES = ["cache", "ttl", "invalidate", "store", "memo", "skip"]
    RETURN_TYPES = ("ANY", "BOOLEAN", "JSON")
    RETURN_NAMES = ("output", "cache_hit", "cache_info")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTOR_CACHE_POLICY = "always_run"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "Data to cache and pass through"}),
                "cache_key": ("STRING", {"default": "", "description": "Explicit cache key; auto-hash when empty"}),
            },
            "optional": {
                "ttl_seconds": ("INT", {"default": 0, "min": 0}),
                "invalidate_on_change": ("STRING", {"default": ""}),
                "force_refresh": ("BOOLEAN", {"default": False}),
                "cache_scope": (["run", "global", "user"], {"default": "run"}),
                "cache_dir": ("STRING", {"default": "", "description": "Custom cache directory"}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, bool, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        explicit_key = str(kwargs.get("cache_key", "") or "")
        ttl_seconds = max(0, int(kwargs.get("ttl_seconds", 0) or 0))
        invalidate_on_change = str(kwargs.get("invalidate_on_change", "") or "")
        force_refresh = bool(kwargs.get("force_refresh", False))
        cache_scope = str(kwargs.get("cache_scope", "run") or "run").lower()
        cache_dir = self._cache_dir(kwargs.get("cache_dir", ""), context, cache_scope)
        invalidation_fingerprint = self._fingerprint(invalidate_on_change)
        cache_key = self._cache_key(data, explicit_key, cache_scope, invalidation_fingerprint)
        now = time.time()

        from bionodulo.execution.cache import CacheStore

        cache = CacheStore(cache_dir)
        try:
            marker = cache.read_marker(cache_key) if cache.is_hit(cache_key) else None
            outputs = marker.get("outputs", {}) if isinstance(marker, dict) else {}
            stored_at = outputs.get("stored_at")
            age_seconds = round(now - float(stored_at), 3) if stored_at is not None else None
            expired = ttl_seconds > 0 and age_seconds is not None and age_seconds > ttl_seconds
            cache_hit = bool(marker and not force_refresh and not expired)

            cache_info = {
                "cache_key": cache_key,
                "cache_scope": cache_scope,
                "cache_dir": str(cache_dir),
                "ttl_seconds": ttl_seconds,
                "force_refresh": force_refresh,
                "invalidate_on_change": invalidate_on_change,
                "invalidation_fingerprint": invalidation_fingerprint,
                "age_seconds": age_seconds,
                "executor_skip_supported": True,
            }

            if cache_hit:
                output = outputs.get("data", data)
                cache_info.update({"status": "hit", "stored_at": stored_at})
                _ctx_log(context, "info", f"Cache Control hit: {cache_key}")
                return {
                    "outputs": {
                        "output": output,
                        "cache_hit": True,
                        "cache_info": _json_text(cache_info),
                    },
                    "inactive_outputs": ["output"],
                }

            if force_refresh:
                status = "refresh"
            elif expired:
                status = "expired"
            else:
                status = "miss"

            cache.write_marker(
                cache_key,
                outputs={
                    "data": data,
                    "stored_at": now,
                    "invalidation_fingerprint": invalidation_fingerprint,
                },
                params={
                    "cache_scope": cache_scope,
                    "ttl_seconds": ttl_seconds,
                    "invalidate_on_change": invalidate_on_change,
                    "force_refresh": force_refresh,
                },
                inputs={"input": data},
            )
            cache_info.update({"status": status, "stored_at": now})
            _ctx_log(context, "info", f"Cache Control {status}: {cache_key}")
            return {
                "outputs": {
                    "output": data,
                    "cache_hit": False,
                    "cache_info": _json_text(cache_info),
                },
                "inactive_outputs": [],
            }
        finally:
            cache.close()

    def _cache_key(self, data: Any, explicit_key: str, cache_scope: str, invalidation_fingerprint: str) -> str:
        raw_key = explicit_key.strip()
        if not raw_key:
            raw_key = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:24]
        safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_key).strip("._") or "auto"
        payload = json.dumps(
            {
                "scope": cache_scope,
                "key": safe_key,
                "invalidate": invalidation_fingerprint,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
        return f"cache_control_{safe_key}_{digest}"

    @staticmethod
    def _fingerprint(value: str) -> str:
        if not value:
            return ""
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _cache_dir(value: Any, context: Any, cache_scope: str) -> Path:
        custom = str(value or "").strip()
        if custom:
            base = Path(custom)
        else:
            workspace_dir = getattr(context, "workspace_dir", None) if context is not None else None
            root = Path(workspace_dir) / "cache" if workspace_dir else Path("cache")
            base = root / "control" / cache_scope
            if cache_scope == "run":
                run_id = str(getattr(context, "run_id", "") or "unknown_run")
                base = base / re.sub(r"[^A-Za-z0-9_.-]+", "_", run_id).strip("._")
        base.mkdir(parents=True, exist_ok=True)
        return base


class NotificationNode(BaseNode):
    """Send or record workflow notifications when this node is reached."""

    NODE_ID = "notification"
    DISPLAY_NAME = "Notification"
    CATEGORY = "workflow"
    DESCRIPTION = "Send notifications on workflow events. Supports webhook, Slack, Discord. Trigger: on complete, on error, or always."
    SEARCH_ALIASES = ["notify", "alert", "slack", "discord", "webhook", "email", "message"]
    RETURN_TYPES = ("BOOLEAN", "JSON")
    RETURN_NAMES = ("success", "delivery_info")
    REQUIRES_EXTERNAL_TOOLS = False
    SUPPORTED_CHANNELS = {"webhook", "slack", "discord", "email", "log", "noop"}
    SUPPORTED_TRIGGERS = {"on_complete", "on_error", "always"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "trigger": (["on_complete", "on_error", "always"], {"default": "always"}),
                "channel": (["webhook", "slack", "discord", "email", "log", "noop"], {"default": "webhook"}),
            },
            "optional": {
                "webhook_url": ("STRING", {"default": ""}),
                "message": ("STRING", {"default": "Workflow notification", "multiline": True}),
                "include_results": ("BOOLEAN", {"default": False}),
                "secret_key": ("STRING", {"default": "", "description": "Secret key that resolves to a webhook URL"}),
                "timeout_seconds": ("FLOAT", {"default": 10.0, "min": 0.1}),
                "smtp_host": ("STRING", {"default": "", "description": "SMTP host for email notifications"}),
                "smtp_port": ("INT", {"default": 587, "min": 1, "max": 65535}),
                "smtp_username": ("STRING", {"default": ""}),
                "smtp_password": ("STRING", {"default": "", "password": True}),
                "smtp_from": ("STRING", {"default": ""}),
                "smtp_to": ("STRING", {"default": "", "description": "Comma-separated email recipients"}),
                "smtp_use_tls": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[bool, str]:
        context = kwargs.pop("context", None)
        trigger = str(kwargs.get("trigger", "always") or "always").lower()
        channel = str(kwargs.get("channel", "webhook") or "webhook").lower()
        if trigger not in self.SUPPORTED_TRIGGERS:
            raise ValueError(f"Unsupported notification trigger: {trigger}")
        if channel not in self.SUPPORTED_CHANNELS:
            raise ValueError(f"Unsupported notification channel: {channel}")

        webhook_url = str(kwargs.get("webhook_url", "") or "")
        message = str(kwargs.get("message", "Workflow notification") or "Workflow notification")
        include_results = bool(kwargs.get("include_results", False))
        secret_key = str(kwargs.get("secret_key", "") or "")
        timeout = max(0.1, float(kwargs.get("timeout_seconds", 10.0) or 10.0))
        webhook_url = self._resolve_webhook_url(webhook_url, secret_key, context)

        run_info = {
            "run_id": getattr(context, "run_id", "unknown"),
            "node_id": getattr(context, "node_id", self.NODE_ID),
            "trigger": trigger,
            "status": getattr(context, "status", ""),
        }
        payload = self._build_payload(channel, message, run_info)
        if include_results and context is not None:
            payload["run_metadata"] = getattr(context, "run_metadata", {})

        delivery_info: dict[str, Any] = {
            "channel": channel,
            "trigger": trigger,
            "status": "pending",
            "message_length": len(message),
            "webhook_url_configured": bool(webhook_url),
            "payload": payload if channel in {"log", "noop"} else self._redacted_payload(payload),
        }

        if channel == "noop":
            delivery_info["status"] = "skipped"
            delivery_info["reason"] = "No-op notification channel"
            _ctx_log(context, "info", f"Notification [noop]: {message}")
            return (True, _json_text(delivery_info))

        if channel == "log":
            delivery_info["status"] = "delivered"
            _ctx_log(context, "info", f"Notification [log]: {message}")
            return (True, _json_text(delivery_info))

        if channel == "email":
            settings = self._resolve_email_settings(kwargs)
            delivery_info.update(
                {
                    "smtp_host_configured": bool(settings["host"]),
                    "recipients": settings["to_addresses"],
                }
            )
            if not settings["host"] or not settings["to_addresses"]:
                delivery_info["status"] = "skipped"
                delivery_info["reason"] = "No SMTP host or recipients configured"
                _ctx_log(context, "warning", "Notification [email] skipped: no SMTP host or recipients configured")
                return (False, _json_text(delivery_info))
            try:
                email_result = await self._send_email(settings, payload, timeout)
            except Exception as exc:
                delivery_info.update({"status": "failed", "error": str(exc)})
                _ctx_log(context, "error", f"Notification [email] failed: {exc}")
                return (False, _json_text(delivery_info))
            recipients = [str(item) for item in email_result.get("recipients", settings["to_addresses"])]
            delivery_info.update(
                {
                    "status": "delivered",
                    "message_id": email_result.get("message_id", ""),
                    "recipients": recipients,
                }
            )
            _ctx_log(context, "info", f"Notification [email] delivered to {len(recipients)} recipient(s)")
            return (True, _json_text(delivery_info))

        if not webhook_url:
            delivery_info["status"] = "skipped"
            delivery_info["reason"] = "No webhook URL configured"
            _ctx_log(context, "warning", f"Notification [{channel}] skipped: no webhook URL configured")
            return (False, _json_text(delivery_info))

        try:
            response = await self._post_json(webhook_url, payload, timeout)
        except Exception as exc:
            delivery_info.update({"status": "failed", "error": str(exc)})
            _ctx_log(context, "error", f"Notification [{channel}] failed: {exc}")
            return (False, _json_text(delivery_info))

        status_code = int(response.get("status_code", 0) or 0)
        success = 200 <= status_code < 300
        delivery_info.update(
            {
                "status": "delivered" if success else "failed",
                "http_status": status_code,
                "response_body": str(response.get("body", ""))[:500],
            }
        )
        _ctx_log(context, "info" if success else "warning", f"Notification [{channel}] HTTP {status_code}")
        return (success, _json_text(delivery_info))

    def _build_payload(self, channel: str, message: str, run_info: dict[str, Any]) -> dict[str, Any]:
        if channel == "slack":
            return {
                "text": message,
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": f"*{run_info.get('run_id', 'unknown')}*"}},
                    {"type": "section", "text": {"type": "mrkdwn", "text": message}},
                ],
            }
        if channel == "discord":
            color = 0x22C55E if run_info.get("status") == "completed" else 0xEF4444
            return {
                "content": message,
                "embeds": [
                    {
                        "title": f"BioNodulo: {run_info.get('run_id', 'unknown')}",
                        "description": message,
                        "color": color,
                    }
                ],
            }
        return {
            "message": message,
            "run_id": run_info.get("run_id"),
            "node_id": run_info.get("node_id"),
            "trigger": run_info.get("trigger"),
            "status": run_info.get("status"),
        }

    @staticmethod
    def _resolve_webhook_url(webhook_url: str, secret_key: str, context: Any) -> str:
        if not secret_key or context is None or not hasattr(context, "resolve_secret"):
            return webhook_url
        resolved = context.resolve_secret(secret_key)
        return str(resolved or webhook_url)

    @staticmethod
    def _redacted_payload(payload: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(payload, default=str))

    @staticmethod
    def _resolve_email_settings(inputs: dict[str, Any]) -> dict[str, Any]:
        host = str(inputs.get("smtp_host", "") or os.environ.get("BIONODULO_SMTP_HOST", "")).strip()
        port = int(inputs.get("smtp_port", 0) or os.environ.get("BIONODULO_SMTP_PORT", "587") or 587)
        username = str(inputs.get("smtp_username", "") or os.environ.get("BIONODULO_SMTP_USERNAME", "")).strip()
        password = str(inputs.get("smtp_password", "") or os.environ.get("BIONODULO_SMTP_PASSWORD", ""))
        from_address = str(inputs.get("smtp_from", "") or os.environ.get("BIONODULO_SMTP_FROM", "")).strip()
        to_text = str(inputs.get("smtp_to", "") or os.environ.get("BIONODULO_SMTP_TO", "")).strip()
        use_tls_raw = inputs.get("smtp_use_tls", os.environ.get("BIONODULO_SMTP_USE_TLS", "true"))
        if isinstance(use_tls_raw, str):
            use_tls = use_tls_raw.strip().lower() not in {"0", "false", "no", "off"}
        else:
            use_tls = bool(use_tls_raw)
        to_addresses = [item.strip() for item in re.split(r"[,;\n]+", to_text) if item.strip()]
        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "from_address": from_address or username,
            "to_addresses": to_addresses,
            "use_tls": use_tls,
        }

    async def _send_email(self, settings: dict[str, Any], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return await asyncio.to_thread(self._send_email_sync, settings, payload, timeout)

    @staticmethod
    def _send_email_sync(settings: dict[str, Any], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        from_address = str(settings.get("from_address", "") or "")
        recipients = [str(item) for item in settings.get("to_addresses", [])]
        if not from_address:
            raise ValueError("SMTP from address is required")
        if not recipients:
            raise ValueError("At least one email recipient is required")

        message = EmailMessage()
        message["Subject"] = f"BioNodulo notification: {payload.get('run_id', 'workflow')}"
        message["From"] = from_address
        message["To"] = ", ".join(recipients)
        message.set_content(
            "\n".join(
                [
                    str(payload.get("message", "Workflow notification")),
                    "",
                    f"Run ID: {payload.get('run_id', '')}",
                    f"Node ID: {payload.get('node_id', '')}",
                    f"Trigger: {payload.get('trigger', '')}",
                    f"Status: {payload.get('status', '')}",
                ]
            )
        )

        with smtplib.SMTP(str(settings["host"]), int(settings["port"]), timeout=timeout) as smtp:
            if settings.get("use_tls"):
                smtp.starttls()
            username = str(settings.get("username", "") or "")
            password = str(settings.get("password", "") or "")
            if username or password:
                smtp.login(username, password)
            refused = smtp.send_message(message)
        if refused:
            raise RuntimeError(f"SMTP refused recipients: {sorted(refused)}")
        return {"message_id": message.get("Message-ID", ""), "recipients": recipients}

    async def _post_json(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        return {"status_code": response.status_code, "body": response.text}


class RetryNode(BaseNode):
    """Record a retry policy and pass data through unchanged."""

    NODE_ID = "retry"
    DISPLAY_NAME = "Retry"
    CATEGORY = "workflow"
    DESCRIPTION = "Configure retry policy for downstream nodes. Attach upstream of a branch to enable automatic retry on failure."
    SEARCH_ALIASES = ["retry", "reexecute", "attempt", "failure", "recover"]
    RETURN_TYPES = ("ANY", "JSON")
    RETURN_NAMES = ("passthrough", "retry_log")
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = "always_run"
    RETRY_ON_OPTIONS = {"all", "timeout", "memory", "exit_code"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "Data to pass through to downstream nodes"}),
            },
            "optional": {
                "max_retries": ("INT", {"default": 3, "min": 0, "max": 10}),
                "delay_seconds": ("FLOAT", {"default": 5.0, "min": 0.0}),
                "backoff_multiplier": ("FLOAT", {"default": 2.0, "min": 1.0}),
                "max_delay": ("INT", {"default": 300, "min": 1}),
                "retry_on": (["all", "timeout", "memory", "exit_code"], {"default": "all"}),
                "only_retry_specific_nodes": ("STRING", {"default": ""}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        max_retries = int(kwargs.get("max_retries", 3) or 0)
        delay_seconds = max(0.0, float(kwargs.get("delay_seconds", 5.0) or 0.0))
        backoff_multiplier = max(1.0, float(kwargs.get("backoff_multiplier", 2.0) or 1.0))
        max_delay = max(1.0, float(kwargs.get("max_delay", 300) or 300))
        retry_on = str(kwargs.get("retry_on", "all") or "all").lower()
        target_nodes = self._target_nodes(kwargs.get("only_retry_specific_nodes", ""))

        if max_retries < 0 or max_retries > 10:
            raise ValueError("max_retries must be between 0 and 10")
        if retry_on not in self.RETRY_ON_OPTIONS:
            raise ValueError(f"Unsupported retry_on value: {retry_on}")

        policy = {
            "node_id": getattr(context, "node_id", self.NODE_ID),
            "run_id": getattr(context, "run_id", ""),
            "max_retries": max_retries,
            "delay_seconds": delay_seconds,
            "backoff_multiplier": backoff_multiplier,
            "max_delay": max_delay,
            "retry_on": retry_on,
            "target_nodes": target_nodes,
            "delays_seconds": self._delays(max_retries, delay_seconds, backoff_multiplier, max_delay),
            "timestamp": time.time(),
            "executor_retry_supported": True,
            "note": "Retry policy recorded; the executor applies it to downstream matching nodes.",
        }

        if context is not None and hasattr(context, "run_metadata"):
            context.run_metadata.setdefault("retry_policies", []).append(policy)
        policy_file = ""
        if context is not None:
            policy_path = _node_output_dir(self, context) / "retry_policy.json"
            policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True, default=str), encoding="utf-8")
            policy_file = str(policy_path)
            policy["policy_file"] = policy_file

        _ctx_emit(
            context,
            "retry_policy_registered",
            {
                "run_id": policy["run_id"],
                "node_id": policy["node_id"],
                "max_retries": max_retries,
                "retry_on": retry_on,
                "target_nodes": target_nodes,
                "policy_file": policy_file,
            },
        )
        _ctx_log(context, "info", f"Retry policy registered: {max_retries} retries, retry_on={retry_on}")
        return (data, _json_text(policy))

    @staticmethod
    def _target_nodes(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    @staticmethod
    def _delays(max_retries: int, delay_seconds: float, backoff_multiplier: float, max_delay: float) -> list[float]:
        delays: list[float] = []
        current = delay_seconds
        for _ in range(max_retries):
            delays.append(round(min(current, max_delay), 6))
            current *= backoff_multiplier
        return delays


class BatchSubmitterNode(BaseNode):
    """Create or queue one workflow run for each parameter set."""

    NODE_ID = "batch_submitter"
    DISPLAY_NAME = "Batch Submitter"
    CATEGORY = "workflow"
    DESCRIPTION = "Submit array jobs to batch systems. Monitor completion and collect results. Extends HPC integration."
    SEARCH_ALIASES = ["batch", "array", "slurm", "hpc", "submit", "queue", "cluster", "parallel"]
    RETURN_TYPES = ("JSON", "JSON", "FILE")
    RETURN_NAMES = ("job_ids", "status_summary", "batch_log")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "workflow_template": ("STRING", {"multiline": True}),
                "param_matrix": ("JSON", {}),
            },
            "optional": {
                "scheduler": ("STRING", {"default": "slurm"}),
                "array_size": ("INT", {"default": 0, "min": 0}),
                "poll_interval_seconds": ("INT", {"default": 60, "min": 5}),
                "max_wait_seconds": ("INT", {"default": 86400, "min": 0}),
                "partition": ("STRING", {"default": ""}),
                "memory_per_job": ("STRING", {"default": "8G"}),
                "walltime": ("STRING", {"default": "04:00:00"}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, str, str]:
        context = kwargs.pop("context", None)
        scheduler = str(kwargs.get("scheduler", "slurm") or "slurm")
        array_size = max(0, int(kwargs.get("array_size", 0) or 0))
        partition = str(kwargs.get("partition", "") or "")
        memory_per_job = str(kwargs.get("memory_per_job", "8G") or "8G")
        walltime = str(kwargs.get("walltime", "04:00:00") or "04:00:00")

        workflow_template = self._parse_workflow_template(kwargs.get("workflow_template", "{}"))
        param_sets = self._parse_param_matrix(kwargs.get("param_matrix", []))
        output_dir = _node_output_dir(self, context)
        queue = getattr(context, "queue", None) if context is not None else None
        hpc_backend = getattr(context, "hpc_backend", None) if context is not None else None
        queue_submission_supported = queue is not None and hasattr(queue, "submit")
        hpc_submission_supported = (
            not queue_submission_supported
            and hpc_backend is not None
            and hasattr(hpc_backend, "submit_workflow")
        )

        jobs: list[dict[str, Any]] = []
        for index, params in enumerate(param_sets):
            workflow = self._fill_template(workflow_template, params)
            if queue_submission_supported:
                job = await self._submit_to_queue(queue, workflow, params, index, scheduler, context)
            elif hpc_submission_supported:
                job = await self._submit_to_hpc_backend(
                    hpc_backend,
                    workflow,
                    params,
                    index,
                    scheduler,
                    memory_per_job,
                    walltime,
                )
            else:
                job = self._write_planned_workflow(output_dir, workflow, params, index, context)
            jobs.append(job)

        summary = self._summary(
            jobs=jobs,
            scheduler=scheduler,
            array_size=array_size,
            partition=partition,
            memory_per_job=memory_per_job,
            walltime=walltime,
            queue_submission_supported=queue_submission_supported,
            hpc_submission_supported=hpc_submission_supported,
        )
        log_path = output_dir / "batch_submitter_log.json"
        log_payload = {"summary": summary, "jobs": jobs}
        log_path.write_text(json.dumps(log_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

        event_payload = {
            "run_id": getattr(context, "run_id", ""),
            "node_id": getattr(context, "node_id", self.NODE_ID),
            "scheduler": scheduler,
            "total": summary["total"],
            "queued": summary["queued"],
            "planned": summary["planned"],
            "failed": summary["failed"],
            "batch_log": str(log_path),
        }
        _ctx_emit(context, "batch_submitted", event_payload)

        action = "queued" if queue_submission_supported else "submitted" if hpc_submission_supported else "planned"
        _ctx_log(context, "info", f"Batch Submitter {action} {summary['total']} jobs via {scheduler}")
        return (json.dumps(jobs, sort_keys=True, default=str), _json_text(summary), str(log_path))

    @staticmethod
    def _parse_workflow_template(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError(f"workflow_template must be valid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("workflow_template must be a JSON object")
        return value

    @staticmethod
    def _parse_param_matrix(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, str):
            try:
                value = json.loads(value or "[]")
            except json.JSONDecodeError as exc:
                raise ValueError(f"param_matrix must be valid JSON: {exc}") from exc
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            raise ValueError("param_matrix must be a JSON array or object")
        param_sets: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise ValueError(f"param_matrix entry {index} must be a JSON object")
            param_sets.append(item)
        return param_sets

    async def _submit_to_queue(
        self,
        queue: Any,
        workflow: dict[str, Any],
        params: dict[str, Any],
        index: int,
        scheduler: str,
        context: Any,
    ) -> dict[str, Any]:
        metadata = {
            "source": self.NODE_ID,
            "parent_run_id": getattr(context, "run_id", ""),
            "parent_node_id": getattr(context, "node_id", self.NODE_ID),
            "batch_index": index,
            "scheduler": scheduler,
            "params": params,
        }
        try:
            job_id = await queue.submit(workflow=workflow, metadata=metadata)
        except Exception as exc:
            return {
                "index": index,
                "job_id": None,
                "status": "failed",
                "error": str(exc),
                "params": params,
            }
        return {
            "index": index,
            "job_id": str(job_id),
            "status": "queued",
            "params": params,
        }

    async def _submit_to_hpc_backend(
        self,
        hpc_backend: Any,
        workflow: dict[str, Any],
        params: dict[str, Any],
        index: int,
        scheduler: str,
        memory_per_job: str,
        walltime: str,
    ) -> dict[str, Any]:
        try:
            job_id = await hpc_backend.submit_workflow(
                workflow=workflow,
                name=str(workflow.get("name") or f"batch_job_{index}"),
                cpus=None,
                memory=memory_per_job,
                walltime=walltime,
                dependency_jobs=[],
                parameters=params,
            )
        except Exception as exc:
            return {
                "index": index,
                "job_id": None,
                "status": "failed",
                "error": str(exc),
                "scheduler": scheduler,
                "params": params,
            }
        return {
            "index": index,
            "job_id": str(job_id),
            "status": "submitted",
            "scheduler": scheduler,
            "params": params,
        }

    def _write_planned_workflow(
        self,
        output_dir: Path,
        workflow: dict[str, Any],
        params: dict[str, Any],
        index: int,
        context: Any,
    ) -> dict[str, Any]:
        workflow_file = output_dir / f"batch_job_{index}.json"
        workflow_file.write_text(json.dumps(workflow, indent=2, sort_keys=True, default=str), encoding="utf-8")
        node_id = getattr(context, "node_id", self.NODE_ID)
        return {
            "index": index,
            "job_id": f"planned:{node_id}:{index}",
            "status": "planned",
            "workflow_file": str(workflow_file),
            "params": params,
        }

    @classmethod
    def _fill_template(cls, value: Any, params: dict[str, Any]) -> Any:
        if isinstance(value, dict):
            return {key: cls._fill_template(item, params) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._fill_template(item, params) for item in value]
        if isinstance(value, str):
            return cls._replace_placeholders(value, params)
        return value

    @staticmethod
    def _replace_placeholders(value: str, params: dict[str, Any]) -> str:
        rendered = value
        for key in sorted(params):
            rendered = rendered.replace(f"{{{{{key}}}}}", str(params[key]))
        return rendered

    @staticmethod
    def _summary(
        *,
        jobs: list[dict[str, Any]],
        scheduler: str,
        array_size: int,
        partition: str,
        memory_per_job: str,
        walltime: str,
        queue_submission_supported: bool,
        hpc_submission_supported: bool = False,
    ) -> dict[str, Any]:
        return {
            "total": len(jobs),
            "queued": sum(1 for job in jobs if job.get("status") == "queued"),
            "submitted": sum(1 for job in jobs if job.get("status") == "submitted"),
            "planned": sum(1 for job in jobs if job.get("status") == "planned"),
            "completed": sum(1 for job in jobs if job.get("status") == "completed"),
            "failed": sum(1 for job in jobs if job.get("status") == "failed"),
            "scheduler": scheduler,
            "array_size": array_size,
            "partition": partition,
            "memory_per_job": memory_per_job,
            "walltime": walltime,
            "queue_submission_supported": queue_submission_supported,
            "hpc_submission_supported": hpc_submission_supported,
        }


class WorkflowTriggerNode(BaseNode):
    """Trigger a webhook immediately or record a deferred trigger intent."""

    NODE_ID = "workflow_trigger"
    DISPLAY_NAME = "Workflow Trigger"
    CATEGORY = "workflow"
    DESCRIPTION = "Trigger workflows via webhook, schedule, or file watch. HTTP POST, cron-like scheduling, or filesystem events."
    SEARCH_ALIASES = ["trigger", "webhook", "cron", "schedule", "filewatch", "event", "http"]
    RETURN_TYPES = ("JSON", "BOOLEAN")
    RETURN_NAMES = ("trigger_info", "triggered")
    REQUIRES_EXTERNAL_TOOLS = False
    SUPPORTED_TRIGGER_TYPES = {"webhook", "schedule", "file_watch"}
    SUPPORTED_WATCH_EVENTS = {"create", "modify", "delete", "move"}
    CRON_FIELD_SPECS = {
        "minute": (0, 59),
        "hour": (0, 23),
        "day_of_month": (1, 31),
        "month": (1, 12),
        "day_of_week": (0, 7),
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "trigger_type": (["webhook", "schedule", "file_watch"], {"default": "webhook"}),
            },
            "optional": {
                "webhook_url": ("STRING", {"default": ""}),
                "payload": ("JSON", {"default": "{}"}),
                "cron_expression": ("STRING", {"default": "0 2 * * *"}),
                "timezone": ("STRING", {"default": "UTC"}),
                "watch_path": ("STRING", {"default": ""}),
                "watch_event": (["create", "modify", "delete", "move"], {"default": "create"}),
                "target_workflow": ("STRING", {"default": ""}),
                "timeout_seconds": ("FLOAT", {"default": 30.0, "min": 0.1}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, bool]:
        context = kwargs.pop("context", None)
        trigger_type = str(kwargs.get("trigger_type", "webhook") or "webhook").lower()
        if trigger_type not in self.SUPPORTED_TRIGGER_TYPES:
            raise ValueError(f"Unsupported trigger_type: {trigger_type}")

        target_workflow = str(kwargs.get("target_workflow", "") or "")
        timestamp = time.time()
        payload = self._parse_payload(kwargs.get("payload", "{}"))
        timeout = max(0.1, float(kwargs.get("timeout_seconds", 30.0) or 30.0))

        if trigger_type == "webhook":
            info, triggered = await self._trigger_webhook(
                webhook_url=str(kwargs.get("webhook_url", "") or ""),
                payload=payload,
                timeout=timeout,
            )
        elif trigger_type == "schedule":
            info, triggered = self._record_schedule(
                context=context,
                cron_expression=str(kwargs.get("cron_expression", "0 2 * * *") or "0 2 * * *"),
                timezone=str(kwargs.get("timezone", "UTC") or "UTC"),
            )
        else:
            info, triggered = self._record_file_watch(
                context=context,
                watch_path=str(kwargs.get("watch_path", "") or ""),
                watch_event=str(kwargs.get("watch_event", "create") or "create"),
            )

        info.update(
            {
                "trigger_type": trigger_type,
                "target_workflow": target_workflow,
                "payload": payload,
                "timestamp": timestamp,
            }
        )
        trigger_file = ""
        if trigger_type in {"schedule", "file_watch"} and triggered:
            trigger_file = self._write_trigger_file(context, trigger_type, info)
            if trigger_file:
                info["schedule_file" if trigger_type == "schedule" else "watch_file"] = trigger_file
                self._write_trigger_file(context, trigger_type, info)
        event_payload = {
            "run_id": getattr(context, "run_id", ""),
            "node_id": getattr(context, "node_id", self.NODE_ID),
            "trigger_type": trigger_type,
            "status": info.get("status", "unknown"),
            "triggered": triggered,
            "target_workflow": target_workflow,
        }
        _ctx_emit(context, "workflow_trigger", event_payload)
        _ctx_log(context, "info" if triggered else "warning", f"Workflow Trigger [{trigger_type}]: {info.get('status')}")
        return (_json_text(info), triggered)

    @staticmethod
    def _parse_payload(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError(f"payload must be valid JSON: {exc}") from exc
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("payload must be a JSON object")
        return value

    async def _trigger_webhook(self, webhook_url: str, payload: dict[str, Any], timeout: float) -> tuple[dict[str, Any], bool]:
        if not webhook_url:
            return (
                {
                    "status": "skipped",
                    "reason": "No webhook URL configured",
                    "webhook_url_configured": False,
                },
                False,
            )

        try:
            response = await self._post_json(webhook_url, payload, timeout)
        except Exception as exc:
            return (
                {
                    "status": "failed",
                    "error": str(exc),
                    "webhook_url_configured": True,
                },
                False,
            )

        status_code = int(response.get("status_code", 0) or 0)
        success = 200 <= status_code < 300
        return (
            {
                "status": "triggered" if success else "failed",
                "http_status": status_code,
                "response_body": str(response.get("body", ""))[:1000],
                "webhook_url_configured": True,
            },
            success,
        )

    def _record_schedule(self, context: Any, cron_expression: str, timezone: str) -> tuple[dict[str, Any], bool]:
        cron_fields, allowed = self._parse_cron_expression(cron_expression)
        try:
            zone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unsupported timezone: {timezone}") from exc

        now = datetime.fromtimestamp(time.time(), tz=zone)
        next_run = self._next_cron_run(now, allowed)
        next_run_utc = next_run.astimezone(dt_timezone.utc)
        info = {
            "status": "registered",
            "cron_expression": cron_expression,
            "cron_fields": cron_fields,
            "timezone": timezone,
            "next_run_at": next_run.isoformat(),
            "next_run_at_utc": next_run_utc.isoformat(),
            "seconds_until_next_run": int((next_run_utc - now.astimezone(dt_timezone.utc)).total_seconds()),
            "scheduler_runner_contract_supported": True,
            "durable_scheduler_supported": True,
            "note": "Schedule registration written with pollable due-run metadata and durable runner support.",
        }
        return (info, True)

    def _parse_cron_expression(self, cron_expression: str) -> tuple[dict[str, str], dict[str, set[int]]]:
        fields = cron_expression.split()
        if len(fields) != 5:
            raise ValueError("cron_expression must have exactly 5 fields")
        names = ["minute", "hour", "day_of_month", "month", "day_of_week"]
        cron_fields = dict(zip(names, fields, strict=True))
        allowed = {
            name: self._parse_cron_field(name, cron_fields[name], *self.CRON_FIELD_SPECS[name])
            for name in names
        }
        if 7 in allowed["day_of_week"]:
            allowed["day_of_week"].add(0)
            allowed["day_of_week"].discard(7)
        return cron_fields, allowed

    def _parse_cron_field(self, name: str, value: str, minimum: int, maximum: int) -> set[int]:
        allowed: set[int] = set()
        for part in value.split(","):
            part = part.strip()
            if not part:
                raise ValueError(f"Invalid {name} field: {value}")
            step = 1
            base = part
            if "/" in part:
                base, step_text = part.split("/", 1)
                if not step_text.isdigit() or int(step_text) <= 0:
                    raise ValueError(f"Invalid {name} field: {value}")
                step = int(step_text)
            if base == "*":
                start, end = minimum, maximum
            elif "-" in base:
                start_text, end_text = base.split("-", 1)
                if not start_text.isdigit() or not end_text.isdigit():
                    raise ValueError(f"Invalid {name} field: {value}")
                start, end = int(start_text), int(end_text)
                if start > end:
                    raise ValueError(f"Invalid {name} field: {value}")
            else:
                if not base.isdigit():
                    raise ValueError(f"Invalid {name} field: {value}")
                start = end = int(base)
            if start < minimum or end > maximum:
                raise ValueError(f"Invalid {name} field: {value}")
            allowed.update(range(start, end + 1, step))
        return allowed

    def _next_cron_run(self, now: datetime, allowed: dict[str, set[int]]) -> datetime:
        candidate = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        deadline = candidate + timedelta(days=366 * 5)
        while candidate <= deadline:
            cron_weekday = (candidate.weekday() + 1) % 7
            if (
                candidate.minute in allowed["minute"]
                and candidate.hour in allowed["hour"]
                and candidate.month in allowed["month"]
                and self._cron_day_matches(candidate.day, cron_weekday, allowed)
            ):
                return candidate
            candidate += timedelta(minutes=1)
        raise ValueError("cron_expression did not produce a next run within 5 years")

    def _cron_day_matches(self, day_of_month: int, day_of_week: int, allowed: dict[str, set[int]]) -> bool:
        all_days = set(range(1, 32))
        all_weekdays = set(range(0, 7))
        dom_allowed = allowed["day_of_month"]
        dow_allowed = allowed["day_of_week"]
        dom_is_wildcard = dom_allowed == all_days
        dow_is_wildcard = dow_allowed == all_weekdays
        dom_matches = day_of_month in dom_allowed
        dow_matches = day_of_week in dow_allowed
        if dom_is_wildcard and dow_is_wildcard:
            return True
        if dom_is_wildcard:
            return dow_matches
        if dow_is_wildcard:
            return dom_matches
        return dom_matches or dow_matches

    def _record_file_watch(self, context: Any, watch_path: str, watch_event: str) -> tuple[dict[str, Any], bool]:
        watch_event = watch_event.lower()
        if watch_event not in self.SUPPORTED_WATCH_EVENTS:
            raise ValueError(f"Unsupported watch_event: {watch_event}")
        path = Path(watch_path) if watch_path else None
        exists = bool(path and path.exists())
        info = {
            "status": "registered" if exists else "failed",
            "watch_path": watch_path,
            "watch_event": watch_event,
            "path_exists": exists,
            "path_type": "directory" if path and path.is_dir() else "file" if path and path.is_file() else "missing",
            "baseline_snapshot": self._file_watch_snapshot(path) if exists and path is not None else {},
            "file_watch_runner_contract_supported": exists,
            "active_file_watcher_supported": False,
            "durable_trigger_runner_supported": exists,
            "note": (
                "File-watch registration written with pollable baseline metadata; durable polling runner "
                "evaluation can submit embedded workflows, while native filesystem watcher execution is not implemented yet."
            ),
        }
        if not exists:
            info["error"] = f"Watch path does not exist: {watch_path}"
            return (info, False)
        return (info, True)

    def _write_trigger_file(self, context: Any, trigger_type: str, info: dict[str, Any]) -> str:
        if context is None:
            return ""
        workspace_dir = getattr(context, "workspace_dir", None)
        base = Path(workspace_dir) if workspace_dir else _node_output_dir(self, context)
        trigger_dir = base / "workflow_triggers"
        trigger_dir.mkdir(parents=True, exist_ok=True)
        node_id = getattr(context, "node_id", self.NODE_ID)
        trigger_file = trigger_dir / f"{trigger_type}_{node_id}.json"
        trigger_file.write_text(json.dumps(info, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return str(trigger_file)

    @classmethod
    def due_schedule_triggers(cls, trigger_dir: str | Path, now: str | datetime | None = None) -> list[dict[str, Any]]:
        base = Path(trigger_dir)
        if not base.exists():
            return []
        now_utc = cls._coerce_utc_datetime(now)
        due: list[dict[str, Any]] = []
        for trigger_file in sorted(base.glob("schedule_*.json")):
            try:
                info = json.loads(trigger_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"schedule trigger file is not valid JSON: {trigger_file}") from exc
            if not isinstance(info, dict) or info.get("trigger_type") != "schedule":
                continue
            next_run = cls._coerce_utc_datetime(info.get("next_run_at_utc"))
            if next_run <= now_utc:
                due_info = dict(info)
                due_info["trigger_file"] = str(trigger_file)
                due.append(due_info)
        return due

    @classmethod
    def due_file_watch_triggers(cls, trigger_dir: str | Path) -> list[dict[str, Any]]:
        base = Path(trigger_dir)
        if not base.exists():
            return []
        due: list[dict[str, Any]] = []
        for trigger_file in sorted(base.glob("file_watch_*.json")):
            try:
                info = json.loads(trigger_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"file-watch trigger file is not valid JSON: {trigger_file}") from exc
            if not isinstance(info, dict) or info.get("trigger_type") != "file_watch":
                continue
            events = cls._file_watch_events(info)
            if events:
                due_info = dict(info)
                due_info["trigger_file"] = str(trigger_file)
                due_info["events"] = events
                due.append(due_info)
        return due

    @classmethod
    def _file_watch_events(cls, info: dict[str, Any]) -> list[dict[str, str]]:
        path = Path(str(info.get("watch_path", "") or ""))
        watch_event = str(info.get("watch_event", "create") or "create")
        if not path.exists() and watch_event != "delete":
            return []
        baseline = info.get("baseline_snapshot", {})
        if not isinstance(baseline, dict):
            baseline = {}
        current = cls._file_watch_snapshot(path) if path.exists() else {}
        events: list[dict[str, str]] = []
        if watch_event == "create":
            for relative_path in sorted(set(current) - set(baseline)):
                events.append(
                    {
                        "event": "create",
                        "path": current[relative_path]["path"],
                        "relative_path": relative_path,
                    }
                )
        elif watch_event == "modify":
            for relative_path in sorted(set(current) & set(baseline)):
                if cls._file_watch_signature(current[relative_path]) != cls._file_watch_signature(baseline[relative_path]):
                    events.append(
                        {
                            "event": "modify",
                            "path": current[relative_path]["path"],
                            "relative_path": relative_path,
                        }
                    )
        elif watch_event == "delete":
            for relative_path in sorted(set(baseline) - set(current)):
                events.append(
                    {
                        "event": "delete",
                        "path": baseline[relative_path]["path"],
                        "relative_path": relative_path,
                    }
                )
        elif watch_event == "move":
            created_paths = sorted(set(current) - set(baseline))
            deleted_paths = sorted(set(baseline) - set(current))
            unmatched_created = list(created_paths)
            for deleted_path in deleted_paths:
                deleted_signature = cls._file_watch_signature(baseline[deleted_path])
                match = next(
                    (
                        created_path
                        for created_path in unmatched_created
                        if cls._file_watch_signature(current[created_path]) == deleted_signature
                    ),
                    None,
                )
                if match is None:
                    continue
                unmatched_created.remove(match)
                events.append(
                    {
                        "event": "move",
                        "path": current[match]["path"],
                        "relative_path": match,
                        "previous_path": baseline[deleted_path]["path"],
                        "previous_relative_path": deleted_path,
                    }
                )
        return events

    @staticmethod
    def _file_watch_signature(entry: dict[str, Any]) -> tuple[Any, Any]:
        return (entry.get("size_bytes"), entry.get("mtime_ns"))

    @staticmethod
    def _file_watch_snapshot(path: Path) -> dict[str, dict[str, Any]]:
        if path.is_file():
            paths = [path]
            root = path.parent
        else:
            paths = [entry for entry in path.rglob("*") if entry.is_file()]
            root = path
        snapshot: dict[str, dict[str, Any]] = {}
        for entry in sorted(paths):
            try:
                stat = entry.stat()
            except OSError:
                continue
            snapshot[entry.relative_to(root).as_posix()] = {
                "path": str(entry),
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        return snapshot

    @staticmethod
    def _coerce_utc_datetime(value: str | datetime | None) -> datetime:
        if value is None:
            return datetime.fromtimestamp(time.time(), tz=dt_timezone.utc)
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt_timezone.utc)
        return parsed.astimezone(dt_timezone.utc)

    async def _post_json(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        import httpx

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
        return {"status_code": response.status_code, "body": response.text}


class PauseResumeNode(BaseNode):
    """Record a human review gate and optionally block until a decision."""

    NODE_ID = "pause_resume"
    DISPLAY_NAME = "Pause / Resume"
    CATEGORY = "workflow"
    DESCRIPTION = "Human review gate. Record review requests and block execution until approval or rejection."
    SEARCH_ALIASES = ["pause", "human", "approval", "review", "gate", "confirm", "breakpoint"]
    RETURN_TYPES = ("ANY", "BOOLEAN", "JSON")
    RETURN_NAMES = ("output", "approved", "pause_info")
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = "always_run"
    DEFAULT_ACTIONS = {"wait", "approve", "reject"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("ANY", {"description": "Data to review before proceeding"}),
            },
            "optional": {
                "message": ("STRING", {"default": "Please review the intermediate results.", "multiline": True}),
                "timeout_seconds": ("INT", {"default": 0, "min": 0}),
                "default_action": (["wait", "approve", "reject"], {"default": "wait"}),
                "show_preview": ("BOOLEAN", {"default": True}),
                "reviewers": ("STRING", {"default": ""}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[Any, bool, str]:
        context = kwargs.pop("context", None)
        data = kwargs.get("input")
        message = str(kwargs.get("message", "Please review the intermediate results.") or "")
        timeout_seconds = max(0, int(kwargs.get("timeout_seconds", 0) or 0))
        default_action = str(kwargs.get("default_action", "wait") or "wait").lower()
        show_preview = bool(kwargs.get("show_preview", True))
        reviewers = self._reviewers(kwargs.get("reviewers", ""))

        if default_action not in self.DEFAULT_ACTIONS:
            raise ValueError(f"Unsupported default_action: {default_action}")

        status, approved = self._decision(timeout_seconds, default_action)
        pause_info: dict[str, Any] = {
            "run_id": getattr(context, "run_id", ""),
            "node_id": getattr(context, "node_id", self.NODE_ID),
            "message": message,
            "status": status,
            "approved": approved,
            "timeout_seconds": timeout_seconds,
            "default_action": default_action,
            "reviewers": reviewers,
            "preview": self._preview(data) if show_preview else None,
            "created_at": time.time(),
            "review_decision_supported": True,
            "engine_pause_supported": True,
            "note": "Review request recorded with persistent approval metadata; executor-level blocking pause/resume is supported.",
        }

        pause_file = self._write_pause_file(context, pause_info)
        if pause_file:
            pause_info["pause_file"] = pause_file
            self._write_pause_file(context, pause_info)

        _ctx_emit(
            context,
            "pause_requested",
            {
                "run_id": pause_info["run_id"],
                "node_id": pause_info["node_id"],
                "message": message,
                "status": status,
                "approved": approved,
                "timeout_seconds": timeout_seconds,
                "reviewers": reviewers,
                "pause_file": pause_file,
                "preview_data": pause_info["preview"],
                "review_decision_supported": True,
                "engine_pause_supported": True,
            },
        )
        if status == "waiting" and pause_file:
            pause_info = await self._wait_for_decision(Path(pause_file), context)
            status = str(pause_info.get("status", status))
            approved = bool(pause_info.get("approved", False))
        _ctx_log(context, "info" if approved else "warning", f"Pause / Resume requested: {status}")
        if not approved:
            raise RuntimeError(f"Pause request rejected: {pause_info.get('resolution_comment', '')}")
        return (data, approved, _json_text(pause_info))

    @staticmethod
    def _reviewers(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    @staticmethod
    def _decision(timeout_seconds: int, default_action: str) -> tuple[str, bool]:
        if timeout_seconds > 0 and default_action == "approve":
            return ("timeout_approved", True)
        if timeout_seconds > 0 and default_action == "reject":
            return ("timeout_rejected", False)
        return ("waiting", True)

    def _preview(self, data: Any) -> dict[str, Any]:
        if isinstance(data, (str, Path)):
            path = Path(str(data))
            if path.exists():
                size = path.stat().st_size
                preview: dict[str, Any] = {
                    "kind": "file",
                    "path": str(path),
                    "name": path.name,
                    "size_bytes": size,
                }
                if size <= 1_000_000:
                    try:
                        preview["text"] = path.read_text(encoding="utf-8", errors="replace")[:5000]
                    except OSError as exc:
                        preview["error"] = str(exc)
                else:
                    preview["text"] = f"File preview omitted: {path.name} is {size} bytes"
                return preview
        if isinstance(data, (dict, list)):
            return {"kind": "json", "text": json.dumps(data, indent=2, sort_keys=True, default=str)[:5000]}
        return {"kind": "text", "text": str(data)[:5000]}

    @classmethod
    def pause_store(cls, context: Any | None = None, workspace_dir: str | Path | None = None) -> PauseStateStore:
        if workspace_dir is not None:
            base = Path(workspace_dir)
        elif context is not None:
            context_workspace = getattr(context, "workspace_dir", None)
            base = Path(context_workspace) if context_workspace else _node_output_dir(cls(), context)
        else:
            base = Path(".")
        return PauseStateStore(base / "pause_requests")

    def _write_pause_file(self, context: Any, pause_info: dict[str, Any]) -> str:
        if context is None:
            return ""
        store = self.pause_store(context)
        return str(store.save(pause_info))

    async def _wait_for_decision(self, pause_file: Path, context: Any) -> dict[str, Any]:
        store = PauseStateStore(pause_file.parent)
        cancel_event = getattr(context, "cancel_event", None)
        while True:
            if cancel_event is not None and cancel_event.is_set():
                try:
                    return store.cancel(pause_file)
                except (OSError, ValueError):
                    return {
                        "pause_file": str(pause_file),
                        "status": "cancelled",
                        "approved": False,
                        "resolved_at": time.time(),
                        "review_decision_supported": True,
                        "engine_pause_supported": True,
                        "note": "Review request cancelled while waiting for approval.",
                    }
            try:
                pause_info = store.load(pause_file)
            except (OSError, ValueError):
                await asyncio.sleep(0.1)
                continue
            status = str(pause_info.get("status", "") or "").lower()
            if status in {"approved", "rejected", "cancelled"}:
                pause_info.setdefault("pause_file", str(pause_file))
                return pause_info
            await asyncio.sleep(0.1)

    @staticmethod
    def resolve_pause_request(pause_file: str | Path, action: str, reviewer: str = "", comment: str = "") -> dict[str, Any]:
        path = Path(pause_file)
        return PauseStateStore(path.parent).resolve(
            pause_file=path,
            action=action,
            reviewer=reviewer,
            comment=comment,
        )

    @staticmethod
    def resolve_pause_request_by_id(
        workspace_dir: str | Path,
        run_id: str,
        node_id: str,
        action: str,
        reviewer: str = "",
        comment: str = "",
    ) -> dict[str, Any]:
        return PauseStateStore(Path(workspace_dir) / "pause_requests").resolve(
            run_id=run_id,
            node_id=node_id,
            action=action,
            reviewer=reviewer,
            comment=comment,
        )


class SubWorkflowNode(BaseNode):
    """Prepare or execute another workflow as a nested routine."""

    NODE_ID = "sub_workflow"
    DISPLAY_NAME = "Sub-Workflow"
    CATEGORY = "workflow"
    DESCRIPTION = "Execute another workflow as a sub-routine. Pass inputs, run the sub-workflow, receive outputs."
    SEARCH_ALIASES = ["subworkflow", "sub", "nested", "call", "routine", "module"]
    RETURN_TYPES = ("JSON", "FILE")
    RETURN_NAMES = ("outputs", "run_metadata")
    REQUIRES_EXTERNAL_TOOLS = False
    EXECUTOR_CACHE_POLICY = "always_run"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "workflow_path": ("STRING", {"description": "Path to workflow JSON file or template name"}),
            },
            "optional": {
                "inputs": ("JSON", {"default": "{}", "description": "JSON dict of inputs"}),
                "target_nodes": ("STRING", {"default": "", "description": "Comma-separated output node IDs"}),
                "timeout_seconds": ("INT", {"default": 3600, "min": 1}),
                "inherit_secrets": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        workflow_ref = str(kwargs.get("workflow_path", "") or "")
        inputs = self._parse_inputs(kwargs.get("inputs", {}))
        target_nodes = self._target_nodes(kwargs.get("target_nodes", ""))
        timeout_seconds = max(1, int(kwargs.get("timeout_seconds", 3600) or 3600))
        inherit_secrets = bool(kwargs.get("inherit_secrets", True))

        workflow_path = self._resolve_workflow_path(workflow_ref, context)
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
        prepared_workflow = BatchSubmitterNode._fill_template(workflow, inputs)
        node_dir = _node_output_dir(self, context)
        prepared_file = node_dir / "sub_workflow_prepared.json"
        prepared_file.write_text(json.dumps(prepared_workflow, indent=2, sort_keys=True, default=str), encoding="utf-8")

        executor = getattr(context, "executor", None) if context is not None else None
        sub_run_id = f"{getattr(context, 'run_id', 'run')}_sub_{getattr(context, 'node_id', self.NODE_ID)}"
        if executor is None or not hasattr(executor, "execute"):
            outputs = {
                "status": "planned",
                "execution_supported": False,
                "workflow_path": str(workflow_path),
                "prepared_workflow_file": str(prepared_file),
                "inputs": inputs,
                "target_nodes": target_nodes,
                "note": "Sub-workflow prepared; context.executor is not available for nested execution.",
            }
            metadata = {
                "status": "planned",
                "executor_available": False,
                "execution_supported": False,
                "sub_run_id": sub_run_id,
                "workflow_path": str(workflow_path),
                "workflow_name": prepared_workflow.get("name", workflow_path.stem),
                "prepared_workflow_file": str(prepared_file),
                "inputs": inputs,
                "target_nodes": target_nodes,
            }
            metadata_file = self._write_metadata(node_dir, metadata)
            _ctx_emit(context, "sub_workflow_planned", metadata)
            _ctx_log(context, "info", f"Sub-workflow planned: {metadata['workflow_name']}")
            return (json.dumps(outputs, sort_keys=True, default=str), metadata_file)

        options: dict[str, Any] = {"target_nodes": target_nodes}
        if inherit_secrets and context is not None and hasattr(context, "api_secrets"):
            options["api_secrets"] = getattr(context, "api_secrets")

        _ctx_emit(
            context,
            "sub_workflow_started",
            {
                "run_id": getattr(context, "run_id", ""),
                "node_id": getattr(context, "node_id", self.NODE_ID),
                "sub_run_id": sub_run_id,
                "workflow_path": str(workflow_path),
                "target_nodes": target_nodes,
            },
        )
        try:
            result = await asyncio.wait_for(
                executor.execute(
                    run_id=sub_run_id,
                    workflow=prepared_workflow,
                    options=options,
                    cancel_event=getattr(context, "cancel_event", None),
                    emit=getattr(context, "emit", None),
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Sub-workflow timed out after {timeout_seconds}s") from exc

        outputs = result.get("outputs", {})
        metadata = {
            "status": result.get("status", "unknown"),
            "executor_available": True,
            "execution_supported": True,
            "sub_run_id": sub_run_id,
            "workflow_path": str(workflow_path),
            "workflow_name": prepared_workflow.get("name", workflow_path.stem),
            "prepared_workflow_file": str(prepared_file),
            "inputs": inputs,
            "target_nodes": target_nodes,
            "executor_metadata": result.get("metadata", {}),
        }
        metadata_file = self._write_metadata(node_dir, metadata)
        _ctx_emit(context, "sub_workflow_completed", metadata)
        _ctx_log(context, "info", f"Sub-workflow completed: {metadata['status']}")
        return (json.dumps(outputs, sort_keys=True, default=str), metadata_file)

    @staticmethod
    def _parse_inputs(value: Any) -> dict[str, Any]:
        if isinstance(value, str):
            try:
                value = json.loads(value or "{}")
            except json.JSONDecodeError as exc:
                raise ValueError(f"inputs must be valid JSON: {exc}") from exc
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("inputs must be a JSON object")
        return value

    @staticmethod
    def _target_nodes(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    @staticmethod
    def _resolve_workflow_path(workflow_ref: str, context: Any) -> Path:
        candidates: list[Path] = []
        ref_path = Path(workflow_ref)
        candidates.append(ref_path)
        workspace_dir = getattr(context, "workspace_dir", None) if context is not None else None
        if workspace_dir is not None and not ref_path.is_absolute():
            workspace = Path(workspace_dir)
            candidates.append(workspace / workflow_ref)
            candidates.append(workspace / "workflows" / workflow_ref)
            if not workflow_ref.endswith(".json"):
                candidates.append(workspace / "workflows" / f"{workflow_ref}.json")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Sub-workflow not found: {workflow_ref}")

    @staticmethod
    def _write_metadata(node_dir: Path, metadata: dict[str, Any]) -> str:
        metadata_file = node_dir / "sub_workflow_metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return str(metadata_file)
