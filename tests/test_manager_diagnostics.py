from bionodulo.manager import diagnose_workflow, environment_status
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow


def registry():
    reg = NodeRegistry()
    reg.load_builtin_nodes()
    return reg


def test_manager_reports_missing_node_type(tmp_path):
    workflow = Workflow.model_validate(
        {"nodes": [{"id": "mystery", "type": "unknown_custom_node", "params": {}}], "edges": [], "outputs": ["mystery"]}
    )
    result = diagnose_workflow(workflow, registry())

    assert result["missing_node_types"] == ["unknown_custom_node"]
    custom_plan = next(plan for plan in result["install_plans"] if plan["kind"] == "custom_node")
    assert custom_plan["target"] == "unknown_custom_node"
    assert custom_plan["requires_confirmation"] is True


def test_environment_status_lists_required_tools(tmp_path):
    result = environment_status(registry(), custom_nodes_dir=tmp_path)
    tools = {tool["name"] for tool in result["tools"]}

    assert {"fastqc", "fastp", "multiqc", "bwa", "samtools"}.issubset(tools)
    assert result["manager"]["mode"] == "install-with-confirmation"


def test_workflow_environment_defaults_to_conda():
    workflow = Workflow.model_validate({"nodes": [], "edges": []})
    result = diagnose_workflow(workflow, registry())

    assert workflow.environment.type == "conda"
    assert result["environment"]["type"] == "conda"
    assert result["environment_plan"]["action"] == "create_conda_environment"


def test_conda_tool_install_plan_targets_selected_environment(monkeypatch):
    monkeypatch.setattr("bionodulo.manager.diagnostics.shutil.which", lambda name: None)
    workflow = Workflow.model_validate(
        {
            "nodes": [{"id": "fastqc-1", "type": "fastqc", "params": {}}],
            "edges": [],
            "outputs": ["fastqc-1"],
            "environment": {"type": "conda", "name": "selected-qc-env", "packages": ["fastqc"]},
        }
    )

    result = diagnose_workflow(workflow, registry())
    fastqc_plan = next(plan for plan in result["install_plans"] if plan["target"] == "fastqc")

    assert fastqc_plan["command"][:5] == ["mamba", "install", "-y", "-n", "selected-qc-env"]
    assert fastqc_plan["environment"]["name"] == "selected-qc-env"
