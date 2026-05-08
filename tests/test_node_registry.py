from bionodulo.nodes.registry import NodeRegistry


def test_builtin_registry_contains_qc_nodes():
    registry = NodeRegistry()
    registry.load_builtin_nodes()

    assert registry.has("fastqc")
    assert registry.has("fastp")
    assert registry.has("multiqc")


def test_node_metadata_serialization():
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    info = registry.object_info()["fastqc"]

    assert info["display_name"] == "FastQC"
    assert info["inputs"]["required"]["reads"]["type"] == "FASTQ_LIST"
    assert info["outputs"][0] == {"name": "report_dir", "type": "QC_REPORT_DIR"}
    assert "qc" in info["search_aliases"]


def test_example_custom_node_loads_and_exposes_real_bio_metadata(tmp_path):
    custom_dir = tmp_path / "custom_nodes"
    custom_dir.mkdir()
    source = open("custom_nodes/example_node.py.example", encoding="utf-8").read()
    (custom_dir / "example_node.py").write_text(source, encoding="utf-8")

    registry = NodeRegistry()
    registry.load_custom_nodes(custom_dir)
    info = registry.object_info()["example_fastq_summary"]

    assert info["output_node"] is True
    assert info["category"] == "example"
    assert info["function"] == "execute"
    assert info["inputs"]["required"]["reads"]["type"] == "STRING"
    assert info["inputs"]["required"]["reads"]["widget"] == "textarea"
    assert info["inputs"]["required"]["max_records"]["widget"] == "slider"
    assert info["inputs"]["required"]["max_records"]["tooltip"]
    assert info["outputs"] == [
        {"name": "summary_txt", "type": "STRING"},
        {"name": "summary_json", "type": "STRING"},
        {"name": "per_file_reports", "type": "STRING"},
        {"name": "read_count", "type": "INT"},
        {"name": "base_count", "type": "INT"},
    ]

    node_cls = registry.get("example_fastq_summary")
    result = node_cls().run(reads="missing.fastq", output_dir=str(tmp_path / "out"), max_records=10, fail_on_missing=False)
    assert result["read_count"] == 0
    assert result["summary_txt"].endswith("fastq_summary.txt")
