"""Reference-data cache (perf §15 #3) — id determinism, opt-in, graceful fallback."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bionodulo.execution import reference_cache as rc  # noqa: E402
from bionodulo.nodes.base import BaseNode  # noqa: E402
from bionodulo.nodes.builtin.alignment import STARIndexNode  # noqa: E402


def _clear(monkeypatch):
    for k in ("REFERENCE_CACHE_BUCKET", "REFERENCE_CACHE_PREFIX", "REFERENCE_LOCAL_DIR"):
        monkeypatch.delenv(k, raising=False)


def test_disabled_by_default(monkeypatch):
    _clear(monkeypatch)
    assert rc.cache_enabled() is False


def test_enabled_with_bucket(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("REFERENCE_CACHE_BUCKET", "bn-refs")
    assert rc.cache_enabled() is True


def test_ref_id_is_content_addressed():
    a = rc.compute_ref_id("star", ["g:1", "t:2", "STAR2.7", "sa14", "oh100"])
    b = rc.compute_ref_id("star", ["g:1", "t:2", "STAR2.7", "sa14", "oh100"])
    c = rc.compute_ref_id("star", ["g:999", "t:2", "STAR2.7", "sa14", "oh100"])
    assert a == b          # same inputs → shared cache key across all users
    assert a != c          # any change → new key
    assert a.startswith("star-")


def test_file_identity_uses_name_and_size(tmp_path):
    f = tmp_path / "genome.fa"
    f.write_bytes(b"ACGT" * 10)
    assert rc.file_identity(f) == f"genome.fa:{f.stat().st_size}"
    # missing file → basename, still deterministic
    assert rc.file_identity(tmp_path / "missing.fa") == "missing.fa"


def test_star_node_opts_in():
    rid = STARIndexNode.reference_cache_id(
        {"reference": "/x/genome.fa", "gtf": "/x/genes.gtf", "sjdb_overhang": 100}
    )
    assert rid and rid.startswith("star-")
    # params change the id (a different index is a different cache entry)
    rid2 = STARIndexNode.reference_cache_id(
        {"reference": "/x/genome.fa", "gtf": "/x/genes.gtf", "sjdb_overhang": 75}
    )
    assert rid != rid2


def test_base_node_does_not_opt_in():
    # nodes that don't build references return None → normal execution
    assert BaseNode.reference_cache_id.__func__(BaseNode, {}) is None


def test_stage_and_publish_noop_when_disabled(monkeypatch, tmp_path):
    _clear(monkeypatch)
    assert rc.stage("star-abc") is None      # no network, no error
    rc.publish("star-abc", tmp_path)          # no exception = pass
