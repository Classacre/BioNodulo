from bionodulo.workflow.schema import Workflow


def test_old_workflow_json_gets_ui_and_groups_defaults():
    workflow = Workflow.model_validate({"nodes": [{"id": "a", "type": "input_file"}], "edges": []})

    assert workflow.groups == []
    assert workflow.nodes[0].ui.pinned is False
    assert workflow.nodes[0].ui.muted is False
    assert workflow.nodes[0].ui.bypassed is False


def test_workflow_groups_and_ui_round_trip():
    workflow = Workflow.model_validate(
        {
            "nodes": [{"id": "a", "type": "input_file", "ui": {"pinned": True, "group_id": "g1", "color": "#6b2020", "bgcolor": "#4a1515"}}],
            "groups": [{"id": "g1", "name": "Inputs", "position": {"x": 1, "y": 2}, "width": 300, "height": 200}],
        }
    )
    dumped = workflow.model_dump(by_alias=True)
    loaded = Workflow.model_validate(dumped)

    assert loaded.nodes[0].ui.pinned is True
    assert loaded.nodes[0].ui.group_id == "g1"
    assert loaded.nodes[0].ui.color == "#6b2020"
    assert loaded.nodes[0].ui.bgcolor == "#4a1515"
    assert loaded.groups[0].name == "Inputs"
