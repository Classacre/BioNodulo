from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _context(tmp_path: Path, node_id: str = "node") -> SimpleNamespace:
    node_dir = tmp_path / node_id
    node_dir.mkdir()
    events: list[tuple[str, dict[str, Any]]] = []
    logs: list[tuple[str, str]] = []
    return SimpleNamespace(
        run_id="run-1",
        node_id=node_id,
        node_dir=node_dir,
        run_metadata={},
        emit=lambda event, payload: events.append((event, payload)),
        log=lambda level, message: logs.append((level, message)),
        events=events,
        logs=logs,
    )


def test_workflow_enhancement_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "timer": ("Timer", ["passthrough", "elapsed_seconds", "start_time", "end_time"]),
        "resource_monitor": ("Resource Monitor", ["passthrough", "resources_ok", "resource_stats"]),
        "data_validator": ("Data Validator", ["passthrough", "passed", "validation_report", "report_file"]),
        "provenance": ("Provenance", ["passthrough", "provenance_record", "provenance_file"]),
        "compare_results": ("Compare Results", ["comparison_report", "match", "diff_file"]),
        "checkpoint": ("Checkpoint", ["passthrough", "checkpoint_file", "checkpoint_info"]),
    }
    for node_id, (display_name, output_names) in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == display_name
        assert node_info["category"] == "workflow"
        assert node_info["output_name"] == output_names
        assert node_info["search_aliases"]
        assert node_info["requires_external_tools"] is False
        assert node_info["required_executables"] == []


@pytest.mark.asyncio
async def test_timer_passes_value_and_records_timing_metadata(tmp_path: Path) -> None:
    context = _context(tmp_path, "timer-node")

    passthrough, elapsed, start_info, end_info = await _node_class("timer")().run(
        input="reads.fastq.gz",
        label="qc phase",
        context=context,
    )

    start = json.loads(start_info)
    end = json.loads(end_info)
    assert passthrough == "reads.fastq.gz"
    assert elapsed >= 0
    assert start["label"] == "qc phase"
    assert end["label"] == "qc phase"
    assert end["timestamp"] >= start["timestamp"]
    assert context.run_metadata["timers"][0]["label"] == "qc phase"
    assert context.logs[0][0] == "info"


@pytest.mark.asyncio
async def test_resource_monitor_reports_stats_and_can_fail_on_thresholds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    node_class = _node_class("resource_monitor")
    node = node_class()
    monkeypatch.setattr(
        node,
        "_get_resource_stats",
        lambda: {
            "free_memory_gb": 8.0,
            "total_memory_gb": 16.0,
            "free_disk_gb": 100.0,
            "total_disk_gb": 200.0,
            "cpu_percent": 12.5,
            "cpu_count": 8,
        },
    )
    context = _context(tmp_path, "resource-node")

    passthrough, ok, stats_json = await node.run(
        input="sample.bam",
        min_free_memory_gb=4.0,
        min_free_disk_gb=10.0,
        max_cpu_percent=80.0,
        context=context,
    )

    stats = json.loads(stats_json)
    assert passthrough == "sample.bam"
    assert ok is True
    assert stats["resources_ok"] is True
    assert stats["thresholds"]["min_free_memory_gb"] == 4.0
    assert context.events[0][0] == "resource_check"

    monkeypatch.setattr(node, "_get_resource_stats", lambda: {"free_memory_gb": 1.0, "free_disk_gb": 2.0, "cpu_percent": 99.0})
    with pytest.raises(RuntimeError, match="Insufficient resources"):
        await node.run(
            input="sample.bam",
            min_free_memory_gb=4.0,
            min_free_disk_gb=10.0,
            max_cpu_percent=80.0,
            fail_on_insufficient=True,
            context=context,
        )


@pytest.mark.asyncio
async def test_data_validator_accepts_valid_csv_and_writes_report(tmp_path: Path) -> None:
    source = tmp_path / "samples.csv"
    source.write_text("sample,depth,status\nS1,30,pass\nS2,18,review\n", encoding="utf-8")
    expected_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    context = _context(tmp_path, "validator-node")

    passthrough, passed, report, report_file = await _node_class("data_validator")().run(
        input=str(source),
        expected_format="csv",
        required_fields="sample,status",
        min_records=2,
        checksum_expected=expected_sha,
        context=context,
    )

    parsed = json.loads(report)
    report_path = Path(report_file)
    assert passthrough == str(source)
    assert passed is True
    assert parsed["passed"] is True
    assert parsed["checks"]["row_count"] == 2
    assert parsed["checks"]["required_fields_ok"] is True
    assert parsed["checks"]["checksum_ok"] is True
    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8"))["passed"] is True


@pytest.mark.asyncio
async def test_data_validator_reports_failures_without_raising_when_configured(tmp_path: Path) -> None:
    source = tmp_path / "broken.fastq"
    source.write_text("@read1\nACGT\n+\n!!!!\n@read2\nACGT\n", encoding="utf-8")

    passthrough, passed, report, report_file = await _node_class("data_validator")().run(
        input=str(source),
        expected_format="fastq",
        min_records=2,
        fail_on_error=False,
        context=_context(tmp_path, "validator-fail"),
    )

    parsed = json.loads(report)
    assert passthrough == str(source)
    assert passed is False
    assert "FASTQ" in "; ".join(parsed["errors"])
    assert Path(report_file).exists()


@pytest.mark.asyncio
async def test_data_validator_raises_on_failure_by_default(tmp_path: Path) -> None:
    missing = tmp_path / "missing.vcf"

    with pytest.raises(RuntimeError, match="Data validation failed"):
        await _node_class("data_validator")().run(input=str(missing), expected_format="vcf")


@pytest.mark.asyncio
async def test_provenance_writes_w3c_record_with_context_and_custom_metadata(tmp_path: Path) -> None:
    context = _context(tmp_path, "provenance-node")
    context.node_type = "bwa_mem"
    context.params = {"threads": 8, "reference": "hg38.fa"}

    passthrough, record_json, provenance_file = await _node_class("provenance")().run(
        input="aligned.bam",
        tool_name="BWA-MEM",
        tool_version="0.7.17",
        tool_command="bwa mem -t 8 hg38.fa reads.fq",
        description="Align reads to hg38",
        custom_metadata='{"sample": "S1"}',
        standard="w3c",
        context=context,
    )

    record = json.loads(record_json)
    file_record = json.loads(Path(provenance_file).read_text(encoding="utf-8"))
    assert passthrough == "aligned.bam"
    assert record["@context"] == "https://www.w3.org/ns/prov.jsonld"
    assert record["@type"] == "Activity"
    assert record["wasAssociatedWith"]["name"] == "BWA-MEM"
    assert record["wasAssociatedWith"]["version"] == "0.7.17"
    assert record["parameters"]["threads"] == 8
    assert record["custom_metadata"] == {"sample": "S1"}
    assert file_record == record
    assert context.logs[0] == ("info", "Provenance recorded for BWA-MEM")


@pytest.mark.asyncio
async def test_provenance_supports_cwlprov_and_native_standards(tmp_path: Path) -> None:
    context = _context(tmp_path, "provenance-standards")
    context.node_type = "fastqc"
    context.params = {"quality": "high"}

    _, cwl_json, _ = await _node_class("provenance")().run(
        input={"fastq": "reads.fq"},
        tool_name="FastQC",
        standard="cwlprov",
        context=context,
    )
    cwl = json.loads(cwl_json)
    assert cwl["class"] == "provenance_record"
    assert cwl["run_id"] == "run-1"
    assert cwl["step_id"] == "provenance-standards"
    assert cwl["tool"]["name"] == "FastQC"

    _, fallback_json, _ = await _node_class("provenance")().run(
        input={"fastq": "reads.fq"},
        standard="w3c",
        context=context,
    )
    fallback = json.loads(fallback_json)
    assert fallback["wasAssociatedWith"]["name"] == "fastqc"

    _, native_json, _ = await _node_class("provenance")().run(
        input=["reads.fq", "report.html"],
        tool_name="FastQC",
        include_system_info=False,
        standard="native",
        context=context,
    )
    native = json.loads(native_json)["bionodulo_provenance"]
    assert native["run_id"] == "run-1"
    assert native["node_type"] == "fastqc"
    assert native["system"] == {"omitted": True}


@pytest.mark.asyncio
async def test_provenance_records_invalid_custom_metadata_without_context() -> None:
    passthrough, record_json, provenance_file = await _node_class("provenance")().run(
        input="variants.vcf",
        tool_name="bcftools",
        custom_metadata="{not json",
        standard="native",
    )

    record = json.loads(record_json)["bionodulo_provenance"]
    assert passthrough == "variants.vcf"
    assert provenance_file == ""
    assert record["custom_metadata"] == {"parse_error": "{not json"}


@pytest.mark.asyncio
async def test_compare_results_checksum_and_exact_modes() -> None:
    report_json, match, diff_file = await _node_class("compare_results")().run(
        result_a={"sample": "S1", "variants": [3, 1, 2]},
        result_b={"variants": [3, 1, 2], "sample": "S1"},
        comparison_method="checksum",
    )
    report = json.loads(report_json)

    assert match is True
    assert diff_file == ""
    assert report["comparison_method"] == "checksum"
    assert report["match"] is True
    assert len(report["checksum_a"]) == 64
    assert report["checksum_a"] == report["checksum_b"]

    report_json, match, _ = await _node_class("compare_results")().run(
        result_a=["A", "B"],
        result_b=["B", "A"],
        comparison_method="exact",
    )
    report = json.loads(report_json)
    assert match is False
    assert report["match"] is False


@pytest.mark.asyncio
async def test_compare_results_diff_writes_diff_file_and_honors_ignore_patterns(tmp_path: Path) -> None:
    file_a = tmp_path / "caller_a.vcf"
    file_b = tmp_path / "caller_b.vcf"
    file_a.write_text("##date=2026-01-01\n#CHROM\tPOS\nchr1\t10\tA\n", encoding="utf-8")
    file_b.write_text("##date=2026-01-02\n#CHROM\tPOS\nchr1\t11\tG\n", encoding="utf-8")
    context = _context(tmp_path, "compare-node")

    report_json, match, diff_file = await _node_class("compare_results")().run(
        result_a=str(file_a),
        result_b=str(file_b),
        comparison_method="diff",
        ignore_patterns="^##date=",
        context=context,
    )
    report = json.loads(report_json)
    diff_text = Path(diff_file).read_text(encoding="utf-8")

    assert match is False
    assert report["comparison_method"] == "diff"
    assert report["ignored_patterns"] == ["^##date="]
    assert report["diff_lines"] > 0
    assert "chr1\t10\tA" in diff_text
    assert "chr1\t11\tG" in diff_text
    assert "2026-01" not in diff_text
    assert context.logs[0] == ("warning", "Compare Results [diff]: match=False")


@pytest.mark.asyncio
async def test_compare_results_size_and_statistical_tolerance() -> None:
    report_json, match, _ = await _node_class("compare_results")().run(
        result_a="AAAA",
        result_b="AAAABB",
        comparison_method="size",
        tolerance=2,
    )
    report = json.loads(report_json)
    assert match is True
    assert report["size_a"] == 4
    assert report["size_b"] == 6
    assert report["size_difference"] == 2

    report_json, match, _ = await _node_class("compare_results")().run(
        result_a=[1.0, 2.0, 3.0],
        result_b=[1.05, 1.95, 3.1],
        comparison_method="statistical",
        tolerance=0.11,
    )
    report = json.loads(report_json)
    assert match is True
    assert report["max_difference"] == pytest.approx(0.1)
    assert report["mean_difference"] == pytest.approx(0.066666, rel=1e-3)


@pytest.mark.asyncio
async def test_compare_results_rejects_unknown_method() -> None:
    with pytest.raises(ValueError, match="Unsupported comparison method"):
        await _node_class("compare_results")().run(
            result_a="A",
            result_b="B",
            comparison_method="side_by_side",
        )


@pytest.mark.asyncio
async def test_checkpoint_writes_compressed_snapshot_with_context_metadata(tmp_path: Path) -> None:
    context = _context(tmp_path, "checkpoint-node")
    context.node_type = "fastqc"
    context.params = {"threads": 4, "_secret": "hidden"}
    payload = {"report": "fastqc.html", "metrics": {"gc": 51.2}}

    passthrough, checkpoint_file, info_json = await _node_class("checkpoint")().run(
        input=payload,
        checkpoint_name="post_qc",
        include_upstream_metadata=True,
        compression=True,
        context=context,
    )

    info = json.loads(info_json)
    checkpoint_path = Path(checkpoint_file)
    saved = json.loads(gzip.decompress(checkpoint_path.read_bytes()).decode("utf-8"))
    assert passthrough == payload
    assert checkpoint_path.name == "post_qc.json.gz"
    assert info["checkpoint_name"] == "post_qc"
    assert info["compressed"] is True
    assert info["resume_supported"] is False
    assert info["size_bytes"] == checkpoint_path.stat().st_size
    assert saved["data"] == payload
    assert saved["run_metadata"]["run_id"] == "run-1"
    assert saved["run_metadata"]["node_type"] == "fastqc"
    assert saved["run_metadata"]["params"] == {"threads": 4}
    assert context.events[0][0] == "checkpoint_saved"
    assert context.logs[0][0] == "info"


@pytest.mark.asyncio
async def test_checkpoint_writes_uncompressed_snapshot_without_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    passthrough, checkpoint_file, info_json = await _node_class("checkpoint")().run(
        input=["sample.bam", "sample.bai"],
        checkpoint_name="manual_checkpoint",
        include_upstream_metadata=True,
        compression=False,
    )

    info = json.loads(info_json)
    checkpoint_path = Path(checkpoint_file)
    saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert passthrough == ["sample.bam", "sample.bai"]
    assert checkpoint_path == tmp_path / "checkpoints" / "manual_checkpoint.json"
    assert info["compressed"] is False
    assert info["checkpoint_path"] == str(checkpoint_path)
    assert "run_metadata" not in saved
