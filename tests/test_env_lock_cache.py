"""The lock cache must never break a run, and never serve the wrong lock."""
from __future__ import annotations

import pytest

from bionodulo.environments import manifest as environment_manifest
from bionodulo.environments.manifest import set_lock_cache
from bionodulo.execution import env_lock_cache


class FakeS3:
    def __init__(self, objects: dict[str, bytes] | None = None, fail: bool = False):
        self.objects = dict(objects or {})
        self.fail = fail
        self.puts: list[str] = []

    def get_object(self, Bucket: str, Key: str):  # noqa: N803 - boto3 kwarg names
        if self.fail:
            raise RuntimeError("storage unavailable")
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": _Body(self.objects[Key])}

    def put_object(self, Bucket: str, Key: str, Body: bytes):  # noqa: N803
        if self.fail:
            raise RuntimeError("storage unavailable")
        self.objects[Key] = Body
        self.puts.append(Key)


class _Body:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENV_LOCK_CACHE_BUCKET", "locks-bucket")
    monkeypatch.delenv("ENV_LOCK_CACHE_PREFIX", raising=False)
    set_lock_cache(None)
    yield
    set_lock_cache(None)


def _install(monkeypatch: pytest.MonkeyPatch, s3: FakeS3) -> None:
    monkeypatch.setattr(env_lock_cache, "_s3", lambda: s3)


def test_disabled_without_a_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENV_LOCK_CACHE_BUCKET", raising=False)
    assert env_lock_cache.cache_enabled() is False
    assert env_lock_cache.fetch("abc", "linux-64") is None
    assert env_lock_cache.install() is False


def test_key_separates_platforms() -> None:
    x86 = env_lock_cache.cache_key("abc", "linux-64", "pixi.lock")
    arm = env_lock_cache.cache_key("abc", "linux-aarch64", "pixi.lock")
    assert x86 != arm, "an aarch64 lock must not collide with a linux-64 lock"
    assert "linux-64" in x86 and "linux-aarch64" in arm


def test_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    s3 = FakeS3()
    _install(monkeypatch, s3)

    assert env_lock_cache.publish("abc", "linux-64", "[project]\n", b"version: 6\n") is True
    assert env_lock_cache.fetch("abc", "linux-64") == ("[project]\n", b"version: 6\n")


def test_publish_writes_the_lock_last(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch() reads the manifest first, so a torn write must look like a miss."""
    s3 = FakeS3()
    _install(monkeypatch, s3)
    env_lock_cache.publish("abc", "linux-64", "[project]\n", b"lock")
    assert s3.puts[-1].endswith("pixi.lock")


def test_miss_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, FakeS3())
    assert env_lock_cache.fetch("nothing-here", "linux-64") is None


def test_storage_failure_is_a_miss_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cache outage must never fail a run."""
    _install(monkeypatch, FakeS3(fail=True))
    assert env_lock_cache.fetch("abc", "linux-64") is None
    assert env_lock_cache.publish("abc", "linux-64", "[project]\n", b"lock") is False


def test_empty_lock_is_not_served(monkeypatch: pytest.MonkeyPatch) -> None:
    s3 = FakeS3()
    _install(monkeypatch, s3)
    s3.objects[env_lock_cache.cache_key("abc", "linux-64", "pixi.toml")] = b"[project]\n"
    s3.objects[env_lock_cache.cache_key("abc", "linux-64", "pixi.lock")] = b""
    assert env_lock_cache.fetch("abc", "linux-64") is None


def test_refuses_to_publish_an_empty_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, FakeS3())
    with pytest.raises(ValueError):
        env_lock_cache.publish("abc", "linux-64", "", b"lock")
    with pytest.raises(ValueError):
        env_lock_cache.publish("abc", "linux-64", "[project]\n", b"")


def test_install_wires_the_manifest_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """End to end: a published bundle satisfies materialize_committed_lock."""
    packages = ["definitely-not-a-real-package-xyz"]
    manifest_text = environment_manifest._manifest_text(packages)
    env_id = environment_manifest.get_env_id(packages)

    s3 = FakeS3()
    _install(monkeypatch, s3)
    env_lock_cache.publish(env_id, "linux-64", manifest_text, b"version: 6\n")
    assert env_lock_cache.install() is True

    digest = environment_manifest.materialize_committed_lock(tmp_path, packages)
    assert digest is not None
    assert (tmp_path / "pixi.lock").read_bytes() == b"version: 6\n"


def test_a_cached_bundle_for_the_wrong_environment_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    packages = ["definitely-not-a-real-package-xyz"]
    env_id = environment_manifest.get_env_id(packages)
    s3 = FakeS3()
    _install(monkeypatch, s3)
    env_lock_cache.publish(env_id, "linux-64", "[project]\nname = 'wrong'\n", b"lock")
    env_lock_cache.install()

    with pytest.raises(RuntimeError, match="stale"):
        environment_manifest.materialize_committed_lock(tmp_path, packages)
