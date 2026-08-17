from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_effective_dump_redacts_api_secrets() -> None:
    from bionodulo.core.config import Settings

    settings = Settings(api_secrets={"openai_key": "sk-super-secret"})
    dump = settings.effective_dump()

    assert "sk-super-secret" not in json.dumps(dump)
    values = dump["api_secrets"]
    assert isinstance(values, dict)
    assert set(values.values()) == {"***"}


def test_effective_dump_redacts_nested_secret_like_values() -> None:
    from bionodulo.core.config import ExecutionSettings, Settings

    settings = Settings(
        api_secrets={"k": "v"},
        tool_paths={"samtools": "/usr/bin/samtools"},
        execution=ExecutionSettings(on_interrupt="auto_resume"),
    )
    dump = settings.effective_dump()

    assert dump["tool_paths"] == {"samtools": "/usr/bin/samtools"}
    assert dump["execution"]["on_interrupt"] == "auto_resume"
    assert json.dumps(dump).count("***") >= 1


def test_effective_dump_includes_env_override_nested_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    from bionodulo.core.config import Settings

    monkeypatch.setenv("BIONODULO_EXECUTION__ON_INTERRUPT", "auto_resume")
    settings = Settings.from_env()

    assert settings.execution.on_interrupt == "auto_resume"
    assert settings.effective_dump()["execution"]["on_interrupt"] == "auto_resume"

    monkeypatch.setenv("BIONODULO_EXECUTION__ON_INTERRUPT", "bogus")
    assert Settings.from_env().execution.on_interrupt == "manual"


def test_main_dump_effective_config_prints_json_without_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import main

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    monkeypatch.setenv(
        "BIONODULO_API_SECRETS",
        json.dumps({"provider": "super-secret-value"}),
    )

    main.dump_effective_config()

    printed = json.loads(capsys.readouterr().out)
    assert printed["execution"]["on_interrupt"] == "manual"
    assert "super-secret-value" not in json.dumps(printed)
    assert printed["api_secrets"] == {"provider": "***"}


def test_main_parses_dump_config_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    import main

    calls: list[str] = []

    def _fake_dump() -> None:
        calls.append("dumped")

    monkeypatch.setattr(main, "dump_effective_config", _fake_dump)
    monkeypatch.setattr(
        "sys.argv",
        ["main.py", "--dump-config", "--host", "0.0.0.0"],
    )

    main.main()

    assert calls == ["dumped"]
