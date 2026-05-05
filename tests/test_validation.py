from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow
from bionodulo.workflow.validation import validate_workflow


def registry():
    reg = NodeRegistry()
    reg.load_builtin_nodes()
    return reg


def test_validation_accepts_sample_workflow():
    workflow = Workflow.model_validate_json(open("examples/workflows/fastq_qc_pipeline.bionodulo.json", encoding="utf-8").read())
    result = validate_workflow(workflow, registry(), mock_tools=True)

    assert result.valid, result.errors
    assert "multiqc-1" in result.topological_order


def test_validation_detects_cycle():
    workflow = Workflow.model_validate(
        {
            "nodes": [
                {"id": "a", "type": "collect_files", "params": {}},
                {"id": "b", "type": "collect_files", "params": {}},
            ],
            "edges": [
                {"id": "ab", "from": {"node": "a", "output": "directory"}, "to": {"node": "b", "input": "first"}},
                {"id": "ba", "from": {"node": "b", "output": "directory"}, "to": {"node": "a", "input": "first"}},
            ],
        }
    )
    result = validate_workflow(workflow, registry(), mock_tools=True)

    assert not result.valid
    assert any(error.code == "cycle_detected" for error in result.errors)


def test_validation_reports_missing_executable_in_real_mode():
    workflow = Workflow.model_validate(
        {
            "nodes": [
                {"id": "input", "type": "input_fastq", "params": {"files": ["x_R1.fastq.gz", "x_R2.fastq.gz"]}},
                {"id": "qc", "type": "fastqc", "params": {"threads": 1}},
            ],
            "edges": [
                {"id": "edge", "from": {"node": "input", "output": "reads"}, "to": {"node": "qc", "input": "reads"}}
            ],
            "outputs": ["qc"],
        }
    )
    result = validate_workflow(workflow, registry(), mock_tools=False)

    assert not result.valid
    assert any(error.code == "missing_executable" and "fastqc" in error.message for error in result.errors)
