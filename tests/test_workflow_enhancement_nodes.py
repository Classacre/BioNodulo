from __future__ import annotations

import gzip
import hashlib
import json
import os
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
        "memoize": ("Memoize", ["output", "hash", "memo_info"]),
        "cache_control": ("Cache Control", ["output", "cache_hit", "cache_info"]),
        "notification": ("Notification", ["success", "delivery_info"]),
        "retry": ("Retry", ["passthrough", "retry_log"]),
        "batch_submitter": ("Batch Submitter", ["job_ids", "status_summary", "batch_log"]),
        "workflow_trigger": ("Workflow Trigger", ["trigger_info", "triggered"]),
        "pause_resume": ("Pause / Resume", ["output", "approved", "pause_info"]),
        "sub_workflow": ("Sub-Workflow", ["outputs", "run_metadata"]),
    }
    for node_id, (display_name, output_names) in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == display_name
        assert node_info["category"] == "workflow"
        assert node_info["output_name"] == output_names
        assert node_info["search_aliases"]
        assert node_info["requires_external_tools"] is False
        assert node_info["required_executables"] == []


def test_workflow_trigger_object_info_preserves_enum_choices_for_editor() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    node_info = registry.object_info("workflow_trigger")
    trigger_type = node_info["input"]["required"]["trigger_type"]
    watch_event = node_info["input"]["optional"]["watch_event"]

    assert trigger_type == (
        "STRING",
        {"default": "webhook", "options": ["webhook", "schedule", "file_watch"]},
    )
    assert watch_event == (
        "STRING",
        {"default": "create", "options": ["create", "modify", "delete", "move"]},
    )


def test_control_nodes_declare_always_run_executor_cache_policy() -> None:
    for node_id in ("checkpoint", "memoize", "cache_control", "retry", "pause_resume", "sub_workflow"):
        assert getattr(_node_class(node_id), "EXECUTOR_CACHE_POLICY") == "always_run"


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
    context.run_metadata["sample_sheet"] = {
        "samples": ["S1", "S2"],
        "source": "metadata-probe",
    }
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
    assert saved["run_metadata"]["workflow"] == {
        "sample_sheet": {
            "samples": ["S1", "S2"],
            "source": "metadata-probe",
        }
    }
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


@pytest.mark.asyncio
async def test_checkpoint_updates_manifest_for_resume_resolution(tmp_path: Path) -> None:
    context = _context(tmp_path, "checkpoint-node")
    context.workspace_dir = tmp_path
    context.run_id = "run-42"
    context.node_type = "variant_annotation"
    payload = {"records": 12, "outputs": ["annotated.vcf"]}

    passthrough, checkpoint_file, info_json = await _node_class("checkpoint")().run(
        input=payload,
        checkpoint_name="after_annotation",
        include_upstream_metadata=False,
        compression=False,
        context=context,
    )

    info = json.loads(info_json)
    checkpoint_path = Path(checkpoint_file)
    manifest_path = tmp_path / "checkpoints" / "checkpoint_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    latest_by_run_node = manifest["latest_by_run_node"]["run-42:checkpoint-node"]
    assert passthrough == payload
    assert Path(info["manifest_path"]) == manifest_path
    assert info["resume_manifest_supported"] is True
    assert manifest["version"] == "1.0"
    assert manifest["latest_by_name"]["after_annotation"]["checkpoint_path"] == str(checkpoint_path)
    assert latest_by_run_node["checkpoint_name"] == "after_annotation"
    assert latest_by_run_node["checkpoint_path"] == str(checkpoint_path)
    assert latest_by_run_node["run_id"] == "run-42"
    assert latest_by_run_node["node_id"] == "checkpoint-node"
    assert latest_by_run_node["node_type"] == "variant_annotation"
    assert latest_by_run_node["compressed"] is False
    assert latest_by_run_node["size_bytes"] == checkpoint_path.stat().st_size
    resolved = _node_class("checkpoint").resolve_checkpoint(
        manifest_path=manifest_path,
        run_id="run-42",
        node_id="checkpoint-node",
    )
    assert resolved == latest_by_run_node


@pytest.mark.asyncio
async def test_memoize_hashes_inputs_and_records_cache_miss(tmp_path: Path) -> None:
    context = _context(tmp_path, "memo-node")
    context.workspace_dir = tmp_path

    output, input_hash, memo_info_json = await _node_class("memoize")().run(
        input={"query": "ACGT", "params": {"evalue": 1e-5}},
        salt="blast-2.15.0",
        hash_algorithm="sha256",
        context=context,
    )

    memo_info = json.loads(memo_info_json)
    assert output == {"query": "ACGT", "params": {"evalue": 1e-5}}
    assert len(input_hash) == 64
    assert memo_info["input_hash"] == input_hash
    assert memo_info["status"] == "miss"
    assert memo_info["cache_key"].startswith("memoize_")
    assert memo_info["cache_dir"] == str(tmp_path / "cache")
    assert context.logs[0][0] == "info"


@pytest.mark.asyncio
async def test_memoize_returns_cached_data_on_repeated_hash(tmp_path: Path) -> None:
    cache_dir = tmp_path / "memo-cache"
    node = _node_class("memoize")()

    first_output, first_hash, first_info_json = await node.run(
        input={"sample": "S1", "value": 42},
        salt="v1",
        hash_algorithm="blake2b",
        cache_dir=str(cache_dir),
    )
    second_output, second_hash, second_info_json = await node.run(
        input={"value": 42, "sample": "S1"},
        salt="v1",
        hash_algorithm="blake2b",
        cache_dir=str(cache_dir),
    )

    first_info = json.loads(first_info_json)
    second_info = json.loads(second_info_json)
    assert first_output == {"sample": "S1", "value": 42}
    assert second_output == {"sample": "S1", "value": 42}
    assert first_hash == second_hash
    assert first_info["status"] == "miss"
    assert second_info["status"] == "hit"
    assert second_info["cached_at"] is None
    assert second_info["cache_marker_found"] is True


@pytest.mark.asyncio
async def test_memoize_rejects_unknown_hash_algorithm() -> None:
    with pytest.raises(ValueError, match="Unsupported hash algorithm"):
        await _node_class("memoize")().run(
            input="reads.fasta",
            hash_algorithm="sha1",
        )


@pytest.mark.asyncio
async def test_cache_control_records_miss_then_hit_with_explicit_key(tmp_path: Path) -> None:
    context = _context(tmp_path, "cache-node")
    context.workspace_dir = tmp_path
    node = _node_class("cache_control")()

    output, cache_hit, cache_info_json = await node.run(
        input={"vcf": "variants.vcf"},
        cache_key="variant-qc",
        ttl_seconds=3600,
        cache_scope="run",
        context=context,
    )
    first_info = json.loads(cache_info_json)
    output2, cache_hit2, cache_info_json2 = await node.run(
        input={"vcf": "variants.vcf"},
        cache_key="variant-qc",
        ttl_seconds=3600,
        cache_scope="run",
        context=context,
    )
    second_info = json.loads(cache_info_json2)

    assert output == {"vcf": "variants.vcf"}
    assert output2 == {"vcf": "variants.vcf"}
    assert cache_hit is False
    assert cache_hit2 is True
    assert first_info["status"] == "miss"
    assert second_info["status"] == "hit"
    assert second_info["cache_key"] == first_info["cache_key"]
    assert second_info["executor_skip_supported"] is False
    assert context.logs[0][1].startswith("Cache Control miss")
    assert context.logs[1][1].startswith("Cache Control hit")


@pytest.mark.asyncio
async def test_cache_control_run_scope_is_isolated_by_run_id(tmp_path: Path) -> None:
    first_context = _context(tmp_path, "cache-run-1")
    first_context.workspace_dir = tmp_path
    first_context.run_id = "run-1"
    second_context = _context(tmp_path, "cache-run-2")
    second_context.workspace_dir = tmp_path
    second_context.run_id = "run-2"
    node = _node_class("cache_control")()

    _, first_hit, first_info_json = await node.run(
        input={"vcf": "variants.vcf"},
        cache_key="variant-qc",
        ttl_seconds=3600,
        cache_scope="run",
        context=first_context,
    )
    _, second_hit, second_info_json = await node.run(
        input={"vcf": "variants.vcf"},
        cache_key="variant-qc",
        ttl_seconds=3600,
        cache_scope="run",
        context=second_context,
    )

    first_info = json.loads(first_info_json)
    second_info = json.loads(second_info_json)
    assert first_hit is False
    assert second_hit is False
    assert first_info["status"] == "miss"
    assert second_info["status"] == "miss"
    assert first_info["cache_key"] == second_info["cache_key"]
    assert first_info["cache_dir"].endswith("cache/control/run/run-1")
    assert second_info["cache_dir"].endswith("cache/control/run/run-2")


@pytest.mark.asyncio
async def test_cache_control_force_refresh_and_invalidation_fingerprint(tmp_path: Path) -> None:
    cache_dir = tmp_path / "custom-cache"
    node = _node_class("cache_control")()

    _, hit1, info1_json = await node.run(
        input="result-a",
        cache_key="align",
        invalidate_on_change="ref=hg38",
        cache_scope="global",
        cache_dir=str(cache_dir),
    )
    _, hit2, info2_json = await node.run(
        input="result-a",
        cache_key="align",
        invalidate_on_change="ref=hg19",
        cache_scope="global",
        cache_dir=str(cache_dir),
    )
    _, hit3, info3_json = await node.run(
        input="result-a",
        cache_key="align",
        invalidate_on_change="ref=hg19",
        force_refresh=True,
        cache_scope="global",
        cache_dir=str(cache_dir),
    )

    info1 = json.loads(info1_json)
    info2 = json.loads(info2_json)
    info3 = json.loads(info3_json)
    assert hit1 is False
    assert hit2 is False
    assert hit3 is False
    assert info1["cache_key"] != info2["cache_key"]
    assert info3["status"] == "refresh"
    assert info3["force_refresh"] is True


@pytest.mark.asyncio
async def test_cache_control_ttl_expiry_and_auto_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_dir = tmp_path / "ttl-cache"
    node = _node_class("cache_control")()
    now = 1_000.0
    monkeypatch.setattr("bionodulo.nodes.builtin.workflow_enhancement.time.time", lambda: now)

    _, first_hit, first_info_json = await node.run(
        input={"sample": "S1"},
        cache_key="",
        ttl_seconds=10,
        cache_dir=str(cache_dir),
    )
    first_info = json.loads(first_info_json)
    now = 1_020.0
    _, second_hit, second_info_json = await node.run(
        input={"sample": "S1"},
        cache_key="",
        ttl_seconds=10,
        cache_dir=str(cache_dir),
    )
    second_info = json.loads(second_info_json)

    assert first_hit is False
    assert second_hit is False
    assert first_info["cache_key"].startswith("cache_control_")
    assert first_info["cache_key"] == second_info["cache_key"]
    assert second_info["status"] == "expired"
    assert second_info["age_seconds"] == 20.0


@pytest.mark.asyncio
async def test_notification_logs_message_without_webhook(tmp_path: Path) -> None:
    context = _context(tmp_path, "notify-node")
    context.run_metadata = {"status": "completed", "outputs": {"report": "multiqc.html"}}

    success, delivery_info_json = await _node_class("notification")().run(
        trigger="always",
        channel="log",
        message="QC complete",
        include_results=True,
        context=context,
    )

    delivery_info = json.loads(delivery_info_json)
    assert success is True
    assert delivery_info["status"] == "delivered"
    assert delivery_info["channel"] == "log"
    assert delivery_info["payload"]["message"] == "QC complete"
    assert delivery_info["payload"]["run_metadata"] == context.run_metadata
    assert context.logs[0] == ("info", "Notification [log]: QC complete")


@pytest.mark.asyncio
async def test_notification_webhook_skips_without_url() -> None:
    success, delivery_info_json = await _node_class("notification")().run(
        trigger="always",
        channel="webhook",
        webhook_url="",
        message="No URL",
    )

    delivery_info = json.loads(delivery_info_json)
    assert success is False
    assert delivery_info["status"] == "skipped"
    assert delivery_info["reason"] == "No webhook URL configured"


@pytest.mark.asyncio
async def test_notification_posts_resolved_secret_webhook(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    context = _context(tmp_path, "notify-secret")
    context.resolve_secret = lambda key: "https://hooks.example.test/secret" if key == "hook" else ""
    sent: list[dict[str, Any]] = []

    async def fake_post(self: Any, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        sent.append({"url": url, "payload": payload, "timeout": timeout})
        return {"status_code": 204, "body": ""}

    monkeypatch.setattr(_node_class("notification"), "_post_json", fake_post)

    success, delivery_info_json = await _node_class("notification")().run(
        trigger="on_complete",
        channel="slack",
        webhook_url="",
        message="Run finished",
        secret_key="hook",
        context=context,
    )

    delivery_info = json.loads(delivery_info_json)
    assert success is True
    assert sent[0]["url"] == "https://hooks.example.test/secret"
    assert sent[0]["payload"]["text"] == "Run finished"
    assert sent[0]["payload"]["blocks"][0]["text"]["text"] == "*run-1*"
    assert delivery_info["status"] == "delivered"
    assert delivery_info["http_status"] == 204
    assert delivery_info["webhook_url_configured"] is True
    assert "secret" not in delivery_info


@pytest.mark.asyncio
async def test_notification_sends_email_with_smtp_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    context = _context(tmp_path, "notify-email")
    sent: list[dict[str, Any]] = []

    async def fake_send_email(self: Any, settings: dict[str, Any], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        sent.append({"settings": settings, "payload": payload, "timeout": timeout})
        return {"message_id": "smtp-123", "recipients": ["ops@example.test"]}

    monkeypatch.setattr(_node_class("notification"), "_send_email", fake_send_email)

    success, delivery_info_json = await _node_class("notification")().run(
        trigger="on_error",
        channel="email",
        message="Variant workflow failed",
        smtp_host="smtp.example.test",
        smtp_port=2525,
        smtp_username="bio",
        smtp_password="secret-password",
        smtp_from="noreply@example.test",
        smtp_to="ops@example.test",
        smtp_use_tls=True,
        timeout_seconds=3.5,
        context=context,
    )

    delivery_info = json.loads(delivery_info_json)
    assert success is True
    assert sent[0]["settings"] == {
        "host": "smtp.example.test",
        "port": 2525,
        "username": "bio",
        "password": "secret-password",
        "from_address": "noreply@example.test",
        "to_addresses": ["ops@example.test"],
        "use_tls": True,
    }
    assert sent[0]["payload"]["message"] == "Variant workflow failed"
    assert sent[0]["timeout"] == 3.5
    assert delivery_info["status"] == "delivered"
    assert delivery_info["smtp_host_configured"] is True
    assert delivery_info["recipients"] == ["ops@example.test"]
    assert delivery_info["message_id"] == "smtp-123"
    assert "secret-password" not in delivery_info_json
    assert context.logs[0] == ("info", "Notification [email] delivered to 1 recipient(s)")


@pytest.mark.asyncio
async def test_notification_email_skips_without_smtp_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in tuple(os.environ):
        if key.startswith("BIONODULO_SMTP_"):
            monkeypatch.delenv(key, raising=False)

    success, delivery_info_json = await _node_class("notification")().run(
        trigger="always",
        channel="email",
        message="No SMTP",
    )

    delivery_info = json.loads(delivery_info_json)
    assert success is False
    assert delivery_info["status"] == "skipped"
    assert delivery_info["reason"] == "No SMTP host or recipients configured"


@pytest.mark.asyncio
async def test_notification_rejects_unsupported_channel() -> None:
    with pytest.raises(ValueError, match="Unsupported notification channel"):
        await _node_class("notification")().run(
            trigger="always",
            channel="sms",
            message="Hello",
        )


@pytest.mark.asyncio
async def test_retry_records_policy_in_context_metadata_and_event(tmp_path: Path) -> None:
    context = _context(tmp_path, "retry-node")

    passthrough, retry_log_json = await _node_class("retry")().run(
        input="reads.fastq.gz",
        max_retries=4,
        delay_seconds=2.5,
        backoff_multiplier=3.0,
        max_delay=30,
        retry_on="timeout",
        only_retry_specific_nodes="align, call_variants",
        context=context,
    )

    retry_log = json.loads(retry_log_json)
    assert passthrough == "reads.fastq.gz"
    assert retry_log["max_retries"] == 4
    assert retry_log["retry_on"] == "timeout"
    assert retry_log["target_nodes"] == ["align", "call_variants"]
    assert retry_log["delays_seconds"] == [2.5, 7.5, 22.5, 30.0]
    assert retry_log["executor_retry_supported"] is True
    assert context.run_metadata["retry_policies"][0]["node_id"] == "retry-node"
    assert context.events[0][0] == "retry_policy_registered"
    assert context.logs[0][0] == "info"


@pytest.mark.asyncio
async def test_retry_writes_policy_file_when_context_exists(tmp_path: Path) -> None:
    context = _context(tmp_path, "retry-file")

    _, retry_log_json = await _node_class("retry")().run(
        input={"sample": "S1"},
        max_retries=0,
        delay_seconds=1,
        context=context,
    )

    retry_log = json.loads(retry_log_json)
    policy_file = Path(retry_log["policy_file"])
    assert policy_file == tmp_path / "retry-file" / "retry_policy.json"
    assert json.loads(policy_file.read_text(encoding="utf-8"))["max_retries"] == 0


@pytest.mark.asyncio
async def test_retry_rejects_invalid_policy_values() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        await _node_class("retry")().run(input="x", max_retries=-1)

    with pytest.raises(ValueError, match="retry_on"):
        await _node_class("retry")().run(input="x", retry_on="network")


@pytest.mark.asyncio
async def test_batch_submitter_writes_planned_workflows_without_queue(tmp_path: Path) -> None:
    context = _context(tmp_path, "batch-node")
    workflow_template = json.dumps(
        {
            "name": "align-{{sample}}",
            "nodes": [
                {
                    "id": "input",
                    "type": "input_file",
                    "params": {"path": "{{fastq}}", "sample": "{{sample}}"},
                }
            ],
        }
    )
    param_matrix = json.dumps(
        [
            {"sample": "S1", "fastq": "s1.fastq.gz"},
            {"sample": "S2", "fastq": "s2.fastq.gz"},
        ]
    )

    job_ids_json, summary_json, batch_log = await _node_class("batch_submitter")().run(
        workflow_template=workflow_template,
        param_matrix=param_matrix,
        scheduler="slurm",
        array_size=1,
        partition="short",
        memory_per_job="4G",
        walltime="01:00:00",
        context=context,
    )

    jobs = json.loads(job_ids_json)
    summary = json.loads(summary_json)
    log_path = Path(batch_log)
    first_workflow = json.loads((context.node_dir / "batch_job_0.json").read_text(encoding="utf-8"))
    second_workflow = json.loads((context.node_dir / "batch_job_1.json").read_text(encoding="utf-8"))

    assert [job["status"] for job in jobs] == ["planned", "planned"]
    assert jobs[0]["job_id"] == "planned:batch-node:0"
    assert jobs[0]["workflow_file"] == str(context.node_dir / "batch_job_0.json")
    assert first_workflow["name"] == "align-S1"
    assert first_workflow["nodes"][0]["params"] == {"path": "s1.fastq.gz", "sample": "S1"}
    assert second_workflow["name"] == "align-S2"
    assert summary["total"] == 2
    assert summary["planned"] == 2
    assert summary["queued"] == 0
    assert summary["queue_submission_supported"] is False
    assert summary["hpc_submission_supported"] is False
    assert summary["array_size"] == 1
    assert summary["scheduler"] == "slurm"
    assert log_path == context.node_dir / "batch_submitter_log.json"
    assert json.loads(log_path.read_text(encoding="utf-8"))["jobs"] == jobs
    assert context.logs[0] == ("info", "Batch Submitter planned 2 jobs via slurm")


@pytest.mark.asyncio
async def test_batch_submitter_submits_workflows_to_context_queue(tmp_path: Path) -> None:
    context = _context(tmp_path, "batch-queue")
    submitted: list[dict[str, Any]] = []

    class FakeQueue:
        async def submit(self, **kwargs: Any) -> str:
            submitted.append(kwargs)
            return f"queued-{len(submitted)}"

    context.queue = FakeQueue()

    job_ids_json, summary_json, batch_log = await _node_class("batch_submitter")().run(
        workflow_template=json.dumps(
            {
                "name": "qc-{{sample}}",
                "nodes": [{"id": "qc", "type": "fastqc", "params": {"input": "{{fastq}}"}}],
            }
        ),
        param_matrix=[
            {"sample": "S1", "fastq": "s1.fq.gz"},
            {"sample": "S2", "fastq": "s2.fq.gz"},
        ],
        scheduler="local_queue",
        context=context,
    )

    jobs = json.loads(job_ids_json)
    summary = json.loads(summary_json)
    assert [job["job_id"] for job in jobs] == ["queued-1", "queued-2"]
    assert [job["status"] for job in jobs] == ["queued", "queued"]
    assert submitted[0]["workflow"]["name"] == "qc-S1"
    assert submitted[1]["workflow"]["nodes"][0]["params"]["input"] == "s2.fq.gz"
    assert submitted[0]["metadata"] == {
        "source": "batch_submitter",
        "parent_run_id": "run-1",
        "parent_node_id": "batch-queue",
        "batch_index": 0,
        "scheduler": "local_queue",
        "params": {"sample": "S1", "fastq": "s1.fq.gz"},
    }
    assert summary["total"] == 2
    assert summary["queued"] == 2
    assert summary["planned"] == 0
    assert summary["failed"] == 0
    assert summary["queue_submission_supported"] is True
    assert summary["hpc_submission_supported"] is False
    assert Path(batch_log).exists()
    assert context.events[0][0] == "batch_submitted"


@pytest.mark.asyncio
async def test_batch_submitter_rejects_invalid_json_inputs() -> None:
    with pytest.raises(ValueError, match="workflow_template must be valid JSON"):
        await _node_class("batch_submitter")().run(
            workflow_template="{not-json",
            param_matrix="[]",
        )

    with pytest.raises(ValueError, match="param_matrix must be a JSON array or object"):
        await _node_class("batch_submitter")().run(
            workflow_template="{}",
            param_matrix='"not-a-matrix"',
        )


@pytest.mark.asyncio
async def test_workflow_trigger_posts_webhook_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    context = _context(tmp_path, "trigger-webhook")
    sent: list[dict[str, Any]] = []

    async def fake_post(self: Any, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        sent.append({"url": url, "payload": payload, "timeout": timeout})
        return {"status_code": 202, "body": '{"queued": true}'}

    monkeypatch.setattr(_node_class("workflow_trigger"), "_post_json", fake_post)

    trigger_info_json, triggered = await _node_class("workflow_trigger")().run(
        trigger_type="webhook",
        webhook_url="https://hooks.example.test/workflows/run",
        payload='{"sample": "S1"}',
        timeout_seconds=12,
        target_workflow="qc-workflow",
        context=context,
    )

    trigger_info = json.loads(trigger_info_json)
    assert triggered is True
    assert sent == [
        {
            "url": "https://hooks.example.test/workflows/run",
            "payload": {"sample": "S1"},
            "timeout": 12.0,
        }
    ]
    assert trigger_info["trigger_type"] == "webhook"
    assert trigger_info["status"] == "triggered"
    assert trigger_info["http_status"] == 202
    assert trigger_info["response_body"] == '{"queued": true}'
    assert trigger_info["target_workflow"] == "qc-workflow"
    assert context.events[0][0] == "workflow_trigger"
    assert context.logs[0] == ("info", "Workflow Trigger [webhook]: triggered")


@pytest.mark.asyncio
async def test_workflow_trigger_records_schedule_intent(tmp_path: Path) -> None:
    context = _context(tmp_path, "trigger-schedule")
    context.workspace_dir = tmp_path

    trigger_info_json, triggered = await _node_class("workflow_trigger")().run(
        trigger_type="schedule",
        cron_expression="30 2 * * 1",
        timezone="Australia/Perth",
        target_workflow="weekly-qc",
        context=context,
    )

    trigger_info = json.loads(trigger_info_json)
    schedule_file = Path(trigger_info["schedule_file"])
    saved = json.loads(schedule_file.read_text(encoding="utf-8"))
    assert triggered is True
    assert trigger_info["status"] == "registered"
    assert trigger_info["cron_expression"] == "30 2 * * 1"
    assert trigger_info["timezone"] == "Australia/Perth"
    assert trigger_info["target_workflow"] == "weekly-qc"
    assert trigger_info["scheduler_runner_contract_supported"] is True
    assert trigger_info["durable_scheduler_supported"] is False
    assert trigger_info["note"].startswith("Schedule registration written")
    assert schedule_file == tmp_path / "workflow_triggers" / "schedule_trigger-schedule.json"
    assert saved["cron_expression"] == "30 2 * * 1"
    assert saved["target_workflow"] == "weekly-qc"
    assert saved["payload"] == {}
    assert saved["trigger_type"] == "schedule"
    assert context.events[0][0] == "workflow_trigger"


@pytest.mark.asyncio
async def test_workflow_trigger_schedule_calculates_next_run_in_timezone(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # 2026-06-05T01:45:00Z is Friday 09:45 in Australia/Perth.
    monkeypatch.setattr("bionodulo.nodes.builtin.workflow_enhancement.time.time", lambda: 1780623900.0)
    context = _context(tmp_path, "trigger-next-run")
    context.workspace_dir = tmp_path

    trigger_info_json, triggered = await _node_class("workflow_trigger")().run(
        trigger_type="schedule",
        cron_expression="30 2 * * 1",
        timezone="Australia/Perth",
        target_workflow="weekly-qc",
        context=context,
    )

    trigger_info = json.loads(trigger_info_json)
    schedule_file = Path(trigger_info["schedule_file"])
    saved = json.loads(schedule_file.read_text(encoding="utf-8"))
    assert triggered is True
    assert trigger_info["next_run_at"] == "2026-06-08T02:30:00+08:00"
    assert trigger_info["next_run_at_utc"] == "2026-06-07T18:30:00+00:00"
    assert trigger_info["seconds_until_next_run"] == 233100
    assert trigger_info["cron_fields"] == {
        "minute": "30",
        "hour": "2",
        "day_of_month": "*",
        "month": "*",
        "day_of_week": "1",
    }
    assert saved["next_run_at"] == trigger_info["next_run_at"]
    assert saved["next_run_at_utc"] == trigger_info["next_run_at_utc"]


@pytest.mark.asyncio
async def test_workflow_trigger_schedule_due_resolver_lists_due_registrations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # 2026-06-05T01:45:00Z is Friday 09:45 in Australia/Perth.
    monkeypatch.setattr("bionodulo.nodes.builtin.workflow_enhancement.time.time", lambda: 1780623900.0)
    node_class = _node_class("workflow_trigger")
    context = _context(tmp_path, "trigger-due-run")
    context.workspace_dir = tmp_path

    trigger_info_json, triggered = await node_class().run(
        trigger_type="schedule",
        cron_expression="30 2 * * 1",
        timezone="Australia/Perth",
        target_workflow="weekly-qc",
        payload={"sample": "S1"},
        context=context,
    )

    trigger_info = json.loads(trigger_info_json)
    trigger_dir = tmp_path / "workflow_triggers"
    assert triggered is True
    assert trigger_info["scheduler_runner_contract_supported"] is True
    assert node_class.due_schedule_triggers(
        trigger_dir,
        now="2026-06-07T18:29:59+00:00",
    ) == []
    due = node_class.due_schedule_triggers(
        trigger_dir,
        now="2026-06-07T18:30:00+00:00",
    )
    assert len(due) == 1
    assert due[0]["trigger_type"] == "schedule"
    assert due[0]["target_workflow"] == "weekly-qc"
    assert due[0]["payload"] == {"sample": "S1"}
    assert due[0]["next_run_at_utc"] == "2026-06-07T18:30:00+00:00"
    assert Path(due[0]["trigger_file"]) == tmp_path / "workflow_triggers" / "schedule_trigger-due-run.json"


@pytest.mark.asyncio
async def test_workflow_trigger_schedule_rejects_invalid_cron_and_timezone() -> None:
    with pytest.raises(ValueError, match="cron_expression must have exactly 5 fields"):
        await _node_class("workflow_trigger")().run(
            trigger_type="schedule",
            cron_expression="0 2 * *",
            timezone="UTC",
        )

    with pytest.raises(ValueError, match="Unsupported timezone"):
        await _node_class("workflow_trigger")().run(
            trigger_type="schedule",
            cron_expression="0 2 * * *",
            timezone="Mars/Olympus",
        )

    with pytest.raises(ValueError, match="Invalid minute field"):
        await _node_class("workflow_trigger")().run(
            trigger_type="schedule",
            cron_expression="99 2 * * *",
            timezone="UTC",
        )


@pytest.mark.asyncio
async def test_workflow_trigger_records_file_watch_intent(tmp_path: Path) -> None:
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    context = _context(tmp_path, "trigger-watch")
    context.workspace_dir = tmp_path

    trigger_info_json, triggered = await _node_class("workflow_trigger")().run(
        trigger_type="file_watch",
        watch_path=str(watch_dir),
        watch_event="create",
        target_workflow="auto-import",
        context=context,
    )

    trigger_info = json.loads(trigger_info_json)
    watch_file = Path(trigger_info["watch_file"])
    assert triggered is True
    assert trigger_info["status"] == "registered"
    assert trigger_info["watch_path"] == str(watch_dir)
    assert trigger_info["path_exists"] is True
    assert trigger_info["path_type"] == "directory"
    assert trigger_info["active_file_watcher_supported"] is False
    assert watch_file == tmp_path / "workflow_triggers" / "file_watch_trigger-watch.json"
    saved = json.loads(watch_file.read_text(encoding="utf-8"))
    assert saved["target_workflow"] == "auto-import"
    assert saved["trigger_type"] == "file_watch"


@pytest.mark.asyncio
async def test_workflow_trigger_file_watch_polling_detects_created_files(tmp_path: Path) -> None:
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    (watch_dir / "existing.fastq").write_text("@old\nACGT\n+\n!!!!\n", encoding="utf-8")
    node_class = _node_class("workflow_trigger")
    context = _context(tmp_path, "trigger-watch-create")
    context.workspace_dir = tmp_path

    trigger_info_json, triggered = await node_class().run(
        trigger_type="file_watch",
        watch_path=str(watch_dir),
        watch_event="create",
        target_workflow="auto-import",
        payload={"project": "P1"},
        context=context,
    )

    trigger_info = json.loads(trigger_info_json)
    assert triggered is True
    assert trigger_info["file_watch_runner_contract_supported"] is True
    assert node_class.due_file_watch_triggers(tmp_path / "workflow_triggers") == []

    new_file = watch_dir / "new.fastq"
    new_file.write_text("@new\nTGCA\n+\n!!!!\n", encoding="utf-8")

    due = node_class.due_file_watch_triggers(tmp_path / "workflow_triggers")
    assert len(due) == 1
    assert due[0]["trigger_type"] == "file_watch"
    assert due[0]["target_workflow"] == "auto-import"
    assert due[0]["payload"] == {"project": "P1"}
    assert due[0]["events"] == [
        {
            "event": "create",
            "path": str(new_file),
            "relative_path": "new.fastq",
        }
    ]
    assert Path(due[0]["trigger_file"]) == tmp_path / "workflow_triggers" / "file_watch_trigger-watch-create.json"


@pytest.mark.asyncio
async def test_workflow_trigger_file_watch_polling_detects_modified_files(tmp_path: Path) -> None:
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    existing_file = watch_dir / "existing.fastq"
    existing_file.write_text("@old\nACGT\n+\n!!!!\n", encoding="utf-8")
    node_class = _node_class("workflow_trigger")
    context = _context(tmp_path, "trigger-watch-modify")
    context.workspace_dir = tmp_path

    await node_class().run(
        trigger_type="file_watch",
        watch_path=str(watch_dir),
        watch_event="modify",
        target_workflow="auto-import",
        context=context,
    )

    assert node_class.due_file_watch_triggers(tmp_path / "workflow_triggers") == []
    existing_file.write_text("@old\nACGA\n+\n!!!!\n", encoding="utf-8")

    due = node_class.due_file_watch_triggers(tmp_path / "workflow_triggers")
    assert len(due) == 1
    assert due[0]["events"] == [
        {
            "event": "modify",
            "path": str(existing_file),
            "relative_path": "existing.fastq",
        }
    ]


@pytest.mark.asyncio
async def test_workflow_trigger_file_watch_polling_detects_deleted_files(tmp_path: Path) -> None:
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    removed_file = watch_dir / "removed.fastq"
    removed_file.write_text("@old\nACGT\n+\n!!!!\n", encoding="utf-8")
    node_class = _node_class("workflow_trigger")
    context = _context(tmp_path, "trigger-watch-delete")
    context.workspace_dir = tmp_path

    await node_class().run(
        trigger_type="file_watch",
        watch_path=str(watch_dir),
        watch_event="delete",
        target_workflow="auto-import",
        context=context,
    )

    assert node_class.due_file_watch_triggers(tmp_path / "workflow_triggers") == []
    removed_file.unlink()

    due = node_class.due_file_watch_triggers(tmp_path / "workflow_triggers")
    assert len(due) == 1
    assert due[0]["events"] == [
        {
            "event": "delete",
            "path": str(removed_file),
            "relative_path": "removed.fastq",
        }
    ]


@pytest.mark.asyncio
async def test_workflow_trigger_file_watch_polling_detects_moved_files(tmp_path: Path) -> None:
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    original_file = watch_dir / "original.fastq"
    moved_file = watch_dir / "renamed.fastq"
    original_file.write_text("@old\nACGT\n+\n!!!!\n", encoding="utf-8")
    node_class = _node_class("workflow_trigger")
    context = _context(tmp_path, "trigger-watch-move")
    context.workspace_dir = tmp_path

    await node_class().run(
        trigger_type="file_watch",
        watch_path=str(watch_dir),
        watch_event="move",
        target_workflow="auto-import",
        context=context,
    )

    assert node_class.due_file_watch_triggers(tmp_path / "workflow_triggers") == []
    original_file.rename(moved_file)

    due = node_class.due_file_watch_triggers(tmp_path / "workflow_triggers")
    assert len(due) == 1
    assert due[0]["events"] == [
        {
            "event": "move",
            "path": str(moved_file),
            "relative_path": "renamed.fastq",
            "previous_path": str(original_file),
            "previous_relative_path": "original.fastq",
        }
    ]


@pytest.mark.asyncio
async def test_workflow_trigger_file_watch_polling_detects_deleted_watched_file(tmp_path: Path) -> None:
    watched_file = tmp_path / "single.fastq"
    watched_file.write_text("@old\nACGT\n+\n!!!!\n", encoding="utf-8")
    node_class = _node_class("workflow_trigger")
    context = _context(tmp_path, "trigger-watch-file-delete")
    context.workspace_dir = tmp_path

    await node_class().run(
        trigger_type="file_watch",
        watch_path=str(watched_file),
        watch_event="delete",
        target_workflow="auto-import",
        context=context,
    )

    assert node_class.due_file_watch_triggers(tmp_path / "workflow_triggers") == []
    watched_file.unlink()

    due = node_class.due_file_watch_triggers(tmp_path / "workflow_triggers")
    assert len(due) == 1
    assert due[0]["events"] == [
        {
            "event": "delete",
            "path": str(watched_file),
            "relative_path": "single.fastq",
        }
    ]


@pytest.mark.asyncio
async def test_workflow_trigger_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="Unsupported trigger_type"):
        await _node_class("workflow_trigger")().run(trigger_type="email")

    with pytest.raises(ValueError, match="payload must be valid JSON"):
        await _node_class("workflow_trigger")().run(
            trigger_type="webhook",
            webhook_url="https://hooks.example.test/run",
            payload="{not-json",
        )

    with pytest.raises(ValueError, match="Unsupported watch_event"):
        await _node_class("workflow_trigger")().run(
            trigger_type="file_watch",
            watch_path=str(Path.cwd()),
            watch_event="chmod",
        )


@pytest.mark.asyncio
async def test_pause_resume_records_review_request_and_passes_through_file_preview(tmp_path: Path) -> None:
    source = tmp_path / "variants.vcf"
    source.write_text("##fileformat=VCFv4.3\n#CHROM\tPOS\tID\nchr1\t42\t.\n", encoding="utf-8")
    context = _context(tmp_path, "pause-node")
    context.workspace_dir = tmp_path

    output, approved, pause_info_json = await _node_class("pause_resume")().run(
        input=str(source),
        message="Review variant calls before annotation.",
        timeout_seconds=0,
        default_action="wait",
        show_preview=True,
        reviewers="ana, ben",
        context=context,
    )

    pause_info = json.loads(pause_info_json)
    pause_file = Path(pause_info["pause_file"])
    saved = json.loads(pause_file.read_text(encoding="utf-8"))
    assert output == str(source)
    assert approved is True
    assert pause_info["status"] == "waiting"
    assert pause_info["engine_pause_supported"] is False
    assert pause_info["reviewers"] == ["ana", "ben"]
    assert pause_info["preview"]["kind"] == "file"
    assert pause_info["preview"]["path"] == str(source)
    assert "chr1\t42" in pause_info["preview"]["text"]
    assert pause_file == tmp_path / "pause_requests" / "pause-node.json"
    assert saved["message"] == "Review variant calls before annotation."
    assert saved["engine_pause_supported"] is False
    assert context.events[0][0] == "pause_requested"
    assert context.logs[0] == ("info", "Pause / Resume requested: waiting")


@pytest.mark.asyncio
async def test_pause_resume_timeout_default_actions(tmp_path: Path) -> None:
    context = _context(tmp_path, "pause-approve")

    output, approved, pause_info_json = await _node_class("pause_resume")().run(
        input={"qc": "passed"},
        timeout_seconds=1,
        default_action="approve",
        show_preview=True,
        context=context,
    )

    pause_info = json.loads(pause_info_json)
    assert output == {"qc": "passed"}
    assert approved is True
    assert pause_info["status"] == "timeout_approved"
    assert pause_info["preview"]["kind"] == "json"
    assert '"qc": "passed"' in pause_info["preview"]["text"]

    _, rejected, rejected_info_json = await _node_class("pause_resume")().run(
        input="needs review",
        timeout_seconds=1,
        default_action="reject",
        show_preview=False,
    )

    rejected_info = json.loads(rejected_info_json)
    assert rejected is False
    assert rejected_info["status"] == "timeout_rejected"
    assert rejected_info["preview"] is None


@pytest.mark.asyncio
async def test_pause_resume_resolver_updates_persisted_review_decision(tmp_path: Path) -> None:
    context = _context(tmp_path, "pause-review")
    context.workspace_dir = tmp_path
    node_class = _node_class("pause_resume")

    _, _, pause_info_json = await node_class().run(
        input={"variants": 17},
        message="Approve annotation handoff?",
        timeout_seconds=0,
        default_action="wait",
        reviewers="ana",
        context=context,
    )

    pause_info = json.loads(pause_info_json)
    pause_file = Path(pause_info["pause_file"])
    resolved = node_class.resolve_pause_request(
        pause_file,
        action="approve",
        reviewer="ana",
        comment="QC reviewed",
    )
    saved = json.loads(pause_file.read_text(encoding="utf-8"))
    assert pause_info["review_decision_supported"] is True
    assert resolved["status"] == "approved"
    assert resolved["approved"] is True
    assert resolved["resolved_by"] == "ana"
    assert resolved["resolution_comment"] == "QC reviewed"
    assert isinstance(resolved["resolved_at"], float)
    assert saved["status"] == "approved"
    assert saved["approved"] is True
    assert saved["resolved_by"] == "ana"
    assert saved["resolution_comment"] == "QC reviewed"


@pytest.mark.asyncio
async def test_pause_resume_rejects_invalid_default_action() -> None:
    with pytest.raises(ValueError, match="Unsupported default_action"):
        await _node_class("pause_resume")().run(
            input="x",
            default_action="continue",
        )


@pytest.mark.asyncio
async def test_sub_workflow_records_planned_execution_without_executor(tmp_path: Path) -> None:
    workflow_path = tmp_path / "nested.json"
    workflow_path.write_text(
        json.dumps(
            {
                "name": "Nested QC",
                "nodes": [{"id": "input", "type": "string", "params": {"value": "{{sample}}"}}],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    context = _context(tmp_path, "sub-node")
    context.workspace_dir = tmp_path

    outputs_json, metadata_file = await _node_class("sub_workflow")().run(
        workflow_path="nested.json",
        inputs='{"sample": "S1"}',
        target_nodes="multiqc, report",
        timeout_seconds=30,
        inherit_secrets=True,
        context=context,
    )

    outputs = json.loads(outputs_json)
    metadata = json.loads(Path(metadata_file).read_text(encoding="utf-8"))
    prepared = json.loads((context.node_dir / "sub_workflow_prepared.json").read_text(encoding="utf-8"))
    assert outputs["status"] == "planned"
    assert outputs["execution_supported"] is False
    assert outputs["workflow_path"] == str(workflow_path)
    assert outputs["inputs"] == {"sample": "S1"}
    assert outputs["target_nodes"] == ["multiqc", "report"]
    assert metadata["status"] == "planned"
    assert metadata["executor_available"] is False
    assert metadata["prepared_workflow_file"] == str(context.node_dir / "sub_workflow_prepared.json")
    assert prepared["nodes"][0]["params"]["value"] == "S1"
    assert context.events[0][0] == "sub_workflow_planned"
    assert context.logs[0] == ("info", "Sub-workflow planned: Nested QC")


@pytest.mark.asyncio
async def test_sub_workflow_executes_when_context_executor_exists(tmp_path: Path) -> None:
    workflow_path = tmp_path / "nested-exec.json"
    workflow_path.write_text(
        json.dumps({"name": "Nested Exec", "nodes": [{"id": "n1", "type": "noop"}], "edges": []}),
        encoding="utf-8",
    )
    context = _context(tmp_path, "sub-exec")
    context.workspace_dir = tmp_path
    context.api_secrets = {"token": "secret"}
    context.cancel_event = object()
    calls: list[dict[str, Any]] = []

    class FakeExecutor:
        async def execute(self, **kwargs: Any) -> dict[str, Any]:
            calls.append(kwargs)
            return {
                "status": "completed",
                "outputs": {"report": "multiqc.html"},
                "metadata": {"duration": 1.25},
            }

    context.executor = FakeExecutor()

    outputs_json, metadata_file = await _node_class("sub_workflow")().run(
        workflow_path=str(workflow_path),
        inputs={"sample": "S2"},
        target_nodes="report",
        timeout_seconds=10,
        inherit_secrets=True,
        context=context,
    )

    outputs = json.loads(outputs_json)
    metadata = json.loads(Path(metadata_file).read_text(encoding="utf-8"))
    assert outputs == {"report": "multiqc.html"}
    assert metadata["status"] == "completed"
    assert metadata["execution_supported"] is True
    assert metadata["executor_metadata"] == {"duration": 1.25}
    assert calls[0]["run_id"] == "run-1_sub_sub-exec"
    assert calls[0]["workflow"]["name"] == "Nested Exec"
    assert calls[0]["options"]["target_nodes"] == ["report"]
    assert calls[0]["options"]["api_secrets"] == {"token": "secret"}
    assert calls[0]["cancel_event"] is context.cancel_event
    assert context.events[0][0] == "sub_workflow_started"
    assert context.events[1][0] == "sub_workflow_completed"


@pytest.mark.asyncio
async def test_sub_workflow_rejects_missing_or_invalid_inputs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Sub-workflow not found"):
        await _node_class("sub_workflow")().run(workflow_path=str(tmp_path / "missing.json"))

    workflow_path = tmp_path / "nested.json"
    workflow_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="inputs must be valid JSON"):
        await _node_class("sub_workflow")().run(
            workflow_path=str(workflow_path),
            inputs="{not-json",
        )
