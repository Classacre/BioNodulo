from __future__ import annotations

from bionodulo.api.collab_routes import _diff_snapshots
from bionodulo.collab.models import CollabStore, Comment, WorkflowShare, WorkflowTemplate, WorkflowVersion
from bionodulo.collab.permissions import PermissionChecker


def test_collab_routes_are_mounted_once() -> None:
    from server import app

    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/collab/workflows/{workflow_id}/comments" in paths
    assert "/api/collab/templates/{template_id}/fork" in paths
    assert all(not path.startswith("/api/api/collab") for path in paths)


def test_comment_role_can_comment_but_cannot_write(tmp_path) -> None:
    store = CollabStore(tmp_path / "collab.db")
    checker = PermissionChecker(store=store)

    store.add_share(
        WorkflowShare(
            workflow_id="wf-1",
            user_id="commenter-1",
            role="commenter",
            invited_by="owner-1",
        )
    )
    store.add_share(
        WorkflowShare(
            workflow_id="wf-1",
            user_id="viewer-1",
            role="viewer",
            invited_by="owner-1",
        )
    )

    assert checker.can_comment("wf-1", "commenter-1")
    assert not checker.can_write("wf-1", "commenter-1")
    assert not checker.can_comment("wf-1", "viewer-1")


def test_collab_store_round_trips_phase3_dataclasses(tmp_path) -> None:
    store = CollabStore(tmp_path / "collab.db")
    snapshot = {
        "meta": {"name": "Example"},
        "nodes": {"n1": {"id": "n1"}},
        "edges": {"e1": {"id": "e1"}},
        "groups": {},
        "viewport": {"x": 0, "y": 0, "scale": 1},
    }

    parent = store.add_comment(
        Comment(
            id="c1",
            workflow_id="wf-1",
            node_id="n1",
            user_id="u1",
            user_name="User One",
            content="Parent",
        )
    )
    store.add_comment(
        Comment(
            id="c2",
            workflow_id="wf-1",
            node_id="n1",
            user_id="u2",
            user_name="User Two",
            content="Reply",
            parent_id=parent.id,
        )
    )
    version = store.add_version(
        WorkflowVersion(
            id="v1",
            workflow_id="wf-1",
            user_id="u1",
            snapshot=snapshot,
            name="First",
        )
    )
    template = store.add_template(
        WorkflowTemplate(
            id="t1",
            workflow_id="wf-1",
            user_id="u1",
            title="Template",
            snapshot=snapshot,
            is_public=True,
        )
    )

    comments = store.list_comments("wf-1", node_id="n1")

    assert comments[0].id == "c1"
    assert comments[0].replies[0].id == "c2"
    assert version.node_count == 1
    assert version.edge_count == 1
    assert store.get_version("v1").snapshot == snapshot
    assert store.get_template(template.id).snapshot == snapshot


def test_version_diff_matches_frontend_contract() -> None:
    diff = _diff_snapshots(
        {
            "nodes": {"same": {"x": 1}, "changed": {"x": 1}, "old": {"x": 1}},
            "edges": {},
            "groups": {"g1": {"title": "Before"}},
            "meta": {"name": "Before"},
        },
        {
            "nodes": {"same": {"x": 1}, "changed": {"x": 2}, "new": {"x": 1}},
            "edges": {"e1": {"from": "same", "to": "new"}},
            "groups": {"g1": {"title": "After"}},
            "meta": {"name": "After"},
        },
    )

    assert diff["nodes"] == {
        "added": ["new"],
        "removed": ["old"],
        "modified": ["changed"],
        "common": ["same"],
    }
    assert diff["edges"]["added"] == ["e1"]
    assert diff["groups"]["modified"] == ["g1"]
    assert diff["meta_changes"]["meta"] == {
        "before": {"name": "Before"},
        "after": {"name": "After"},
    }
