from __future__ import annotations

from types import SimpleNamespace

import pycrdt
from fastapi.testclient import TestClient

from bionodulo.api.collab_routes import _diff_snapshots
from bionodulo.api.routes import _workflow_payload_to_flat_snapshot
from bionodulo.collab.doc_store import extract_flat_snapshot
from bionodulo.collab.models import CollabStore, Comment, WorkflowShare, WorkflowTemplate, WorkflowVersion
from bionodulo.collab.permissions import PermissionChecker
from bionodulo.collab.yjs_native_handler import _replace_flat_snapshot, _room_presence_payload


def test_collab_routes_are_mounted_once() -> None:
    from server import app

    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/collab/workflows/{workflow_id}/comments" in paths
    assert "/api/collab/templates/{template_id}/fork" in paths
    assert all(not path.startswith("/api/api/collab") for path in paths)


def test_colab_default_workflow_redirects_root_visits(monkeypatch) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_COLLAB_DEFAULT_WORKFLOW", "colab-room")

    with TestClient(create_app()) as client:
        response = client.get("/", follow_redirects=False)
        pinned_response = client.get("/?workflow=explicit-room", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"].endswith("/?workflow=colab-room")
    assert pinned_response.status_code == 200


def test_proxy_prefix_middleware_strips_hosted_asset_api_and_ws_paths() -> None:
    from server import ProxyPrefixMiddleware

    assert ProxyPrefixMiddleware._normalise_path("/proxy/8000/ws") == "/ws"
    assert ProxyPrefixMiddleware._normalise_path("/proxy/8000/assets/index.js") == "/assets/index.js"
    assert ProxyPrefixMiddleware._normalise_path("/proxy/8000/api/object_info") == "/api/object_info"
    assert ProxyPrefixMiddleware._normalise_path("/proxy/8000/ws/collab/workflow-1") == "/ws/collab/workflow-1"
    assert ProxyPrefixMiddleware._normalise_path("/proxy/8000/") == "/proxy/8000/"


def test_example_data_download_progress_crosses_worker_thread(monkeypatch) -> None:
    from bionodulo.api import routes
    from server import create_app

    def fake_download(*, project_root, emit):
        emit("threaded progress", "info")
        return {
            "total": 0,
            "downloaded": [],
            "skipped": [],
            "failed": [],
            "success": True,
        }

    monkeypatch.setattr(routes, "download_example_data", fake_download)

    with TestClient(create_app()) as client:
        response = client.post("/api/getting-started/download", json={})

    assert response.status_code == 200
    assert response.json()["download_result"]["success"] is True


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


def test_native_room_presence_roster_uses_socket_metadata() -> None:
    room_sockets = {
        "wf-room": [
            SimpleNamespace(state=SimpleNamespace(yjs_presence={
                "session_id": "s1",
                "user_id": "u1",
                "name": "User One",
                "color": "#123456",
            })),
            SimpleNamespace(state=SimpleNamespace(yjs_presence={
                "session_id": "s2",
                "user_id": "u2",
                "name": "User Two",
                "color": "#abcdef",
            })),
        ],
    }

    assert _room_presence_payload("wf-room", room_sockets) == {
        "type": "room.presence",
        "workflow_id": "wf-room",
        "users": [
            {"session_id": "s1", "user_id": "u1", "name": "User One", "color": "#123456"},
            {"session_id": "s2", "user_id": "u2", "name": "User Two", "color": "#abcdef"},
        ],
    }


def test_open_room_api_access_grants_before_permission_checks(tmp_path, monkeypatch) -> None:
    from bionodulo.api.routes import _ensure_open_room_access

    monkeypatch.setenv("BIONODULO_COLLAB_OPEN_ROOMS", "1")
    checker = PermissionChecker(store=CollabStore(tmp_path / "collab.db"))
    checker.ensure_owner("wf-room", "owner")
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(permission_checker=checker)))

    assert not checker.can_read("wf-room", "guest")

    _ensure_open_room_access(request, "wf-room", "guest")

    assert checker.can_write("wf-room", "guest")


def test_workflow_snapshot_publish_contract_replaces_flat_crdt_maps() -> None:
    doc = pycrdt.Doc()
    first = _workflow_payload_to_flat_snapshot(
        "wf-room",
        {
            "workflow": {
                "version": "2.0",
                "name": "Genome Assembly",
                "nodes": [{"id": "n1", "type": "input_fastq"}],
                "edges": [{"id": "e1", "from": {"node": "n1"}, "to": {"node": "n2"}}],
                "groups": [],
            }
        },
    )
    second = _workflow_payload_to_flat_snapshot(
        "wf-room",
        {
            "workflow": {
                "version": "2.0",
                "name": "Variant Calling",
                "nodes": [{"id": "n2", "type": "input_vcf"}],
                "edges": [],
                "groups": [],
            }
        },
    )

    _replace_flat_snapshot(doc, first)
    _replace_flat_snapshot(doc, second)
    snapshot = extract_flat_snapshot(doc)

    assert snapshot["meta"]["id"] == "wf-room"
    assert snapshot["meta"]["name"] == "Variant Calling"
    assert "n1" not in snapshot["nodes"]
    assert snapshot["nodes"]["n2"]["type"] == "input_vcf"
    assert snapshot["edges"] == {}
