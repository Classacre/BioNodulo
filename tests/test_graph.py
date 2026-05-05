from bionodulo.workflow.graph import topological_sort
from bionodulo.workflow.schema import Workflow


def test_topological_sort_orders_dependencies_first():
    workflow = Workflow.model_validate(
        {
            "nodes": [
                {"id": "c", "type": "collect_files"},
                {"id": "a", "type": "input_directory", "params": {"directory": "data"}},
                {"id": "b", "type": "collect_files"},
            ],
            "edges": [
                {"id": "ab", "from": {"node": "a", "output": "directory"}, "to": {"node": "b", "input": "first"}},
                {"id": "bc", "from": {"node": "b", "output": "directory"}, "to": {"node": "c", "input": "first"}},
            ],
        }
    )

    assert topological_sort(workflow) == ["a", "b", "c"]
