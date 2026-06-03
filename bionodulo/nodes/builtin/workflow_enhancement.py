"""Workflow robustness and observability nodes."""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
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
