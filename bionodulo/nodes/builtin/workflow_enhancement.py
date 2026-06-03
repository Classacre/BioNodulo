"""Workflow robustness and observability nodes."""
from __future__ import annotations

import asyncio
import csv
import difflib
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
