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
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any

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
                "expected_format": (["auto", "fasta", "fastq", "vcf", "bam", "csv", "tsv", "json", "yaml", "text"], {"default": "auto"}),
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
        path = self._materialize_input(data, context)
        passed = True
        if path is None:
            report["errors"].append("No input data provided")
            passed = False
        else:
            passed = self._validate_path(path, expected_format, report, min_size, max_size)
            if passed and checksum_expected:
                passed = self._verify_checksum(path, checksum_expected, report)
            if passed and min_records > 0:
                records = int(report["checks"].get("record_count", report["checks"].get("row_count", report["checks"].get("variant_count", 0))) or 0)
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

    def _validate_fasta(self, path: Path, report: dict[str, Any]) -> bool:
        records = 0
        saw_sequence = False
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
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
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
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
        text = path.read_text(encoding="utf-8", errors="replace")
        report["checks"]["line_count"] = len(text.splitlines())
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
            "resume_supported": False,
            "note": "Checkpoint artifact written; executor-level resume is not implemented yet.",
        }

        _ctx_log(context, "info", f"Checkpoint saved: {checkpoint_path}")
        _ctx_emit(
            context,
            "checkpoint_saved",
            {
                "run_id": getattr(context, "run_id", ""),
                "node_id": getattr(context, "node_id", self.NODE_ID),
                "checkpoint_path": str(checkpoint_path),
                "compressed": compress,
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
        return {
            "run_id": getattr(context, "run_id", ""),
            "node_id": getattr(context, "node_id", ""),
            "node_type": getattr(context, "node_type", ""),
            "params": public_params,
        }


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
                "executor_skip_supported": False,
            }

            if cache_hit:
                output = outputs.get("data", data)
                cache_info.update({"status": "hit", "stored_at": stored_at})
                _ctx_log(context, "info", f"Cache Control hit: {cache_key}")
                return (output, True, _json_text(cache_info))

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
            return (data, False, _json_text(cache_info))
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
            delivery_info["status"] = "skipped"
            delivery_info["reason"] = "Email delivery requires SMTP settings and is not implemented in this node"
            _ctx_log(context, "warning", "Notification [email] skipped: SMTP delivery is not configured")
            return (False, _json_text(delivery_info))

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
            "executor_retry_supported": False,
            "note": "Retry policy recorded; executor-level downstream retry consumption is not implemented yet.",
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
        queue_submission_supported = queue is not None and hasattr(queue, "submit")

        jobs: list[dict[str, Any]] = []
        for index, params in enumerate(param_sets):
            workflow = self._fill_template(workflow_template, params)
            if queue_submission_supported:
                job = await self._submit_to_queue(queue, workflow, params, index, scheduler, context)
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

        action = "queued" if queue_submission_supported else "planned"
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
    ) -> dict[str, Any]:
        return {
            "total": len(jobs),
            "queued": sum(1 for job in jobs if job.get("status") == "queued"),
            "planned": sum(1 for job in jobs if job.get("status") == "planned"),
            "completed": sum(1 for job in jobs if job.get("status") == "completed"),
            "failed": sum(1 for job in jobs if job.get("status") == "failed"),
            "scheduler": scheduler,
            "array_size": array_size,
            "partition": partition,
            "memory_per_job": memory_per_job,
            "walltime": walltime,
            "queue_submission_supported": queue_submission_supported,
            "hpc_submission_supported": False,
        }
