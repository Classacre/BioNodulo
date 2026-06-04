from __future__ import annotations

import builtins

import pytest
from fastapi.testclient import TestClient


def test_workflow_import_rejects_unavailable_converter_instead_of_placeholder_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from server import create_app

    real_import = builtins.__import__

    def import_with_missing_converter(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "bionodulo.converter.snakemake_converter":
            raise ImportError("simulated missing converter")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_with_missing_converter)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/workflow/import",
            json={"source": "snakemake", "content": "rule all:\n    shell: \"echo ok\""},
        )

    assert response.status_code == 500
    assert "Converter for snakemake is unavailable" in response.json()["detail"]
