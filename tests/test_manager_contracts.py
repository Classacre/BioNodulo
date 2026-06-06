from __future__ import annotations

from fastapi.testclient import TestClient


def test_host_diagnostics_reports_python_sandbox_prerequisites(monkeypatch) -> None:
    from bionodulo.manager import diagnostics
    from bionodulo.manager import runtime_installer

    monkeypatch.setattr(runtime_installer, "get_pixi_path", lambda: "/usr/bin/pixi")
    monkeypatch.setattr(
        diagnostics.shutil,
        "which",
        lambda executable: {
            "python3": "/usr/bin/python3",
            "python": "/usr/bin/python",
            "node": "/usr/bin/node",
            "Rscript": None,
            "bwrap": "/usr/bin/bwrap",
            "newuidmap": "/usr/bin/newuidmap",
            "newgidmap": None,
        }.get(executable),
    )

    payload = diagnostics.host_diagnostics()

    assert payload["checks"]["bwrap"]["available"] is True
    assert payload["checks"]["newuidmap"]["available"] is True
    assert payload["checks"]["newgidmap"]["available"] is False
    assert payload["checks"]["newgidmap"]["required"] is True
    assert "newgidmap" in payload["missing_required"]


def test_manager_status_reports_node_registry_contract() -> None:
    from server import create_app

    with TestClient(create_app()) as client:
        response = client.get("/api/manager/status")

    assert response.status_code == 200
    payload = response.json()

    assert set(payload) == {"custom_nodes_dir", "installed_nodes", "total"}
    assert isinstance(payload["custom_nodes_dir"], str)
    assert isinstance(payload["installed_nodes"], list)
    assert payload["total"] == len(payload["installed_nodes"])
    assert payload["total"] > 0

    first_node = payload["installed_nodes"][0]
    assert {"name", "version", "category", "builtin"} <= set(first_node)
    assert isinstance(first_node["name"], str)
    assert isinstance(first_node["version"], str)
    assert isinstance(first_node["category"], str)
    assert isinstance(first_node["builtin"], bool)


def test_manager_registry_reports_community_catalog_and_installed_packages(monkeypatch, tmp_path) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    custom_nodes = tmp_path / "custom_nodes" / "community_nodes"
    custom_nodes.mkdir(parents=True)
    (custom_nodes / "bionodulo.toml").write_text(
        """
[package]
name = "community-nodes"
version = "0.1.0"
repository = "https://github.com/bionodulo/community-nodes.git"
""".strip(),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/manager/registry")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"registries", "tool_paths", "custom_node_registries", "installed_packages"}
    assert payload["installed_packages"][0]["name"] == "community-nodes"
    community = payload["custom_node_registries"]["bionodulo-community"]
    assert community["installed"] is True
    assert community["install_status"] == "installed"
    assert community["installed_package"]["name"] == "community-nodes"
    assert community["compatibility"]["supported_manifest"] == "bionodulo.toml"
