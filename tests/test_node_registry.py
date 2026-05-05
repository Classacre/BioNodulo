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
