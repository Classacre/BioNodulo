"""Offline argv regressions against the exact upstream 0.4.3 Clap contract."""

from __future__ import annotations

import json
from pathlib import Path
import tomllib

import pytest
import yaml

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.execution.cache import CacheStore
from bionodulo.nodes.builtin.long_read_family import ModkitPileupNode


ROOT = Path(__file__).resolve().parents[3]
CONTRACT = json.loads((ROOT / "tests/fixtures/modkit_pileup_v0_4_3_contract.json").read_text(encoding="utf-8"))
BASE = {"bam": "/data/a sample.bam", "bam_index": "/data/a sample.bam.bai"}


def _parse_pinned_options(argv: list[str]) -> dict[str, str | bool]:
    """Check option names/arity from upstream, without installing or running Modkit."""
    assert argv[:2] == ["modkit", "pileup"]
    assert argv[2] == BASE["bam"]
    assert argv[3].endswith("/bedmethyl.bed")
    parsed: dict[str, str | bool] = {}
    index = 4
    while index < len(argv):
        name = argv[index]
        spec = CONTRACT["options"][name]  # Unknown native options must fail here.
        assert name not in parsed
        if spec["takes_value"]:
            assert index + 1 < len(argv)
            parsed[name] = argv[index + 1]
            index += 2
        else:
            parsed[name] = True
            index += 1
    return parsed


def test_modkit_metadata_matches_the_actual_locked_linux_package() -> None:
    environment = ROOT / "bionodulo/environments/locks/a6d14540abf27c14"
    manifest = tomllib.loads((environment / "pixi.toml").read_text(encoding="utf-8"))
    lock = yaml.safe_load((environment / "pixi.lock").read_text(encoding="utf-8"))
    package = CONTRACT["linux_package"]
    entries = [item for item in lock["packages"] if item.get("conda", "").endswith("/linux-64/" + package["filename"])]
    assert len(entries) == 1
    assert entries[0]["sha256"] == package["sha256"]
    assert manifest["dependencies"]["ont-modkit"] == CONTRACT["upstream_version"]
    assert PACKAGE_MIN_VERSIONS["ont-modkit"] == CONTRACT["upstream_version"]
    assert ModkitPileupNode.VERSION == CONTRACT["upstream_version"]
    assert ModkitPileupNode.PACKAGE_CONSTRAINT == "ont-modkit = " + CONTRACT["upstream_version"]
    assert ModkitPileupNode.GIT_COMMIT == CONTRACT["git_commit"]
    assert ModkitPileupNode.SOURCE_TAG == CONTRACT["source_tag"]


@pytest.mark.parametrize("overrides", [{}, {"modified_bases": ""}, {"modified_bases": None}])
def test_modkit_default_argv_preserves_depth_and_filtering(overrides: dict) -> None:
    argv = ModkitPileupNode.render_command({**BASE, **overrides})
    parsed = _parse_pinned_options(argv)
    assert parsed == {
        "--threads": "4",
        "--max-depth": str(CONTRACT["defaults"]["max_depth"]),
        "--filter-percentile": str(CONTRACT["defaults"]["filter_percentile"]),
    }
    assert "--high-depth" not in argv
    assert "--modified-bases" not in argv


def test_modkit_custom_argv_uses_only_supported_options_without_splitting_paths() -> None:
    argv = ModkitPileupNode.render_command(
        {
            **BASE,
            "reference": "/refs/a reference.fa",
            "reference_index": "/refs/a reference.fa.fai",
            "threads": 8,
            "max_depth": 16000,
            "filter_percentile": 0.2,
            "region": "chr1:1-1000",
            "cpg": True,
            "combine_strands": True,
            "with_header": True,
            "output": "/results/a directory",
        }
    )
    parsed = _parse_pinned_options(argv)
    assert argv[3] == "/results/a directory/bedmethyl.bed"
    assert parsed == {
        "--threads": "8",
        "--max-depth": "16000",
        "--filter-percentile": "0.2",
        "--region": "chr1:1-1000",
        "--ref": "/refs/a reference.fa",
        "--cpg": True,
        "--combine-strands": True,
        "--header": True,
    }


def test_modkit_explicit_no_filtering_keeps_native_mutual_exclusion() -> None:
    parsed = _parse_pinned_options(ModkitPileupNode.render_command({**BASE, "no_filtering": True}))
    assert parsed["--no-filtering"] is True
    assert "--filter-percentile" not in parsed
    assert parsed["--max-depth"] == "8000"
    with pytest.raises(ValueError, match="cannot be combined"):
        ModkitPileupNode.render_command({**BASE, "no_filtering": True, "filter_percentile": 0.2})


@pytest.mark.parametrize("selection", ["5mC", "6mA", "5mC,6mA", "pseU", " --high-depth "])
def test_modkit_legacy_selections_fail_explicitly_before_execution(selection: str) -> None:
    inputs = {**BASE, "modified_bases": selection}
    assert "unsupported by pinned Modkit 0.4.3" in str(ModkitPileupNode.VALIDATE_INPUTS(inputs))
    with pytest.raises(ValueError, match="unsupported by pinned Modkit 0.4.3"):
        ModkitPileupNode.render_command(inputs)


def test_modkit_corrected_version_cannot_reuse_old_incompatible_argv_cache(tmp_path: Path) -> None:
    cache = CacheStore(tmp_path / "cache")
    try:
        arguments = dict(node_id="modkit", node_type="modkit_pileup", params={}, inputs=BASE, upstream_keys={})
        old = cache.cache_key_for_node(**arguments, tool_version="0.6.4")
        corrected = cache.cache_key_for_node(**arguments, tool_version=ModkitPileupNode.VERSION)
        output = tmp_path / "old.bed"
        output.write_text("# bedMethyl\n", encoding="utf-8")
        cache.write_marker(old, {"bedmethyl": str(output)})
        assert cache.is_hit(old)
        assert not cache.is_hit(corrected)
    finally:
        cache.close()
