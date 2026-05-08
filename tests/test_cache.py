from pathlib import Path

from bionodulo.execution.cache import CacheStore, cache_key_for_node


def test_cache_key_changes_when_params_change():
    first = cache_key_for_node(
        node_type="fastqc",
        node_version="0.1.0",
        command_template=["fastqc", "{inputs.reads[0]}"],
        params={"threads": 1},
        inputs={"reads": ["reads.fastq.gz"]},
        upstream_cache_keys=[],
    )
    second = cache_key_for_node(
        node_type="fastqc",
        node_version="0.1.0",
        command_template=["fastqc", "{inputs.reads[0]}"],
        params={"threads": 8},
        inputs={"reads": ["reads.fastq.gz"]},
        upstream_cache_keys=[],
    )

    assert first != second


def test_cache_hit_uses_marker_outputs(tmp_path: Path):
    output = tmp_path / "runs" / "run-1" / "node" / "out.txt"
    output.parent.mkdir(parents=True)
    output.write_text("ok", encoding="utf-8")
    store = CacheStore(tmp_path / "cache")
    store.write_marker("abc", {"outputs": {"file": str(output)}})

    assert store.is_hit("abc", {"file": str(tmp_path / "runs" / "run-2" / "node" / "out.txt")})


def test_cache_key_uses_is_changed_fingerprint():
    first = cache_key_for_node(
        node_type="example",
        node_version="0.1.0",
        command_template=None,
        params={},
        inputs={},
        upstream_cache_keys=[],
        change_fingerprint={"mtime": 1},
    )
    second = cache_key_for_node(
        node_type="example",
        node_version="0.1.0",
        command_template=None,
        params={},
        inputs={},
        upstream_cache_keys=[],
        change_fingerprint={"mtime": 2},
    )

    assert first != second
