from pathlib import Path

from fastapi.testclient import TestClient

from server import create_app


def test_config_export_and_manager_registry_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:
        config = client.get("/config/effective")
        assert config.status_code == 200
        assert config.json()["project_root"] == str(tmp_path.resolve())

        workflow = {"nodes": [{"id": "input", "type": "input_file"}], "edges": []}
        export = client.post("/workflow/export", json={"workflow": workflow, "format": "snakemake"})
        assert export.status_code == 200
        assert export.json()["filename"] == "Snakefile"

        registry = client.get("/manager/registry")
        assert registry.status_code == 200
        assert "registry" in registry.json()


def test_run_plan_preview_and_artifact_apis(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:
        workflow = {
            "nodes": [{"id": "input", "type": "input_file", "params": {"file": "x.txt"}}],
            "outputs": ["input"],
        }
        run = client.post("/runs", json={"workflow": workflow, "mock_tools": True}).json()
        run_id = run["run_id"]
        client.app.state.run_queue._worker_task.cancel()

        plan = client.get(f"/runs/{run_id}/execution-plan")
        previews = client.get(f"/runs/{run_id}/previews")
        artifacts = client.get(f"/runs/{run_id}/artifacts")

        assert plan.status_code == 200
        assert previews.status_code == 200
        assert artifacts.status_code == 200
