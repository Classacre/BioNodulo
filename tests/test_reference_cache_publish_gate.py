"""The shared reference cache must never be written before the build is verified.

A cache entry is shared by every user and every later run. Publishing one that
does not actually contain a usable reference poisons it permanently, and the
damage is self-perpetuating: later runs stage the bad entry, skip the build, and
so can never repair it.

This is exactly how ChIP-Seq `bt2build_001` failed in production — it errored in
3.4s with no `bowtie2-build` subprocess in the log, because the build had been
skipped in favour of an incomplete cached index.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bionodulo.nodes.command_node import CommandNode  # noqa: E402


class _OkContext:
    """A command that exits 0 without producing what the node promised."""

    def __init__(self, produce: Path | None = None) -> None:
        self.produce = produce
        self.calls = 0

    async def run_command(self, cmd: str | list[str], **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if self.produce is not None:
            self.produce.parent.mkdir(parents=True, exist_ok=True)
            self.produce.write_text("real artifact\n", encoding="utf-8")
        return {"returncode": 0, "stdout": "", "stderr": ""}


class _SpyCache:
    def __init__(self, staged: Path | None = None) -> None:
        self.published: list[tuple[str, Path]] = []
        self.staged = staged

    def cache_enabled(self) -> bool:
        return True

    def stage(self, ref_id: str) -> Path | None:
        return self.staged

    def publish(self, ref_id: str, local_path: Path) -> None:
        self.published.append((ref_id, Path(local_path)))


def _install(monkeypatch: pytest.MonkeyPatch, spy: _SpyCache) -> None:
    """Patch both the parent-package attribute and sys.modules.

    CommandNode does `from bionodulo.execution import reference_cache`, which
    reads the *attribute* off the parent package once that submodule has been
    imported anywhere — so patching sys.modules alone silently does nothing as
    soon as another test has imported the real module. That made this suite pass
    in isolation and fail in a parallel run.
    """
    import bionodulo.execution as _execution_pkg

    monkeypatch.setitem(sys.modules, "bionodulo.execution.reference_cache", spy)
    monkeypatch.setattr(_execution_pkg, "reference_cache", spy, raising=False)


class _CachedNode(CommandNode):
    NODE_ID = "cached_probe"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("artifact",)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return [Path(output_dir) / cls.NODE_ID / "artifact.txt"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return ["true"]

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> str:
        return "probe-ref-id"


@pytest.mark.asyncio
async def test_a_build_that_produced_nothing_is_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit 0 with missing outputs must fail the run AND leave the cache untouched."""
    spy = _SpyCache()
    _install(monkeypatch, spy)

    node = _CachedNode()
    with pytest.raises(RuntimeError, match="did not create expected output"):
        await node.run(output_dir=str(tmp_path), context=_OkContext())

    assert spy.published == [], (
        "an unverified build was published to the shared cache; "
        "every later run would stage it, skip the build, and fail"
    )


@pytest.mark.asyncio
async def test_a_verified_build_is_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate must not break the feature it guards."""
    spy = _SpyCache()
    _install(monkeypatch, spy)

    produced = tmp_path / _CachedNode.NODE_ID / "artifact.txt"
    node = _CachedNode()
    await node.run(output_dir=str(tmp_path), context=_OkContext(produce=produced))

    assert [ref for ref, _ in spy.published] == ["probe-ref-id"]


@pytest.mark.asyncio
async def test_a_node_specific_check_can_veto_the_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existence is not sufficiency.

    bowtie2 needs a complete sibling set of six .bt2 files; the index directory
    existing proves nothing. VERIFY_OUTPUTS lets a node say so before its result
    becomes every other user's cached reference.
    """
    spy = _SpyCache()
    _install(monkeypatch, spy)

    class _PickyNode(_CachedNode):
        NODE_ID = "picky_probe"

        @classmethod
        def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
            raise FileNotFoundError("index is incomplete")

    produced = tmp_path / _PickyNode.NODE_ID / "artifact.txt"
    node = _PickyNode()
    with pytest.raises(FileNotFoundError, match="index is incomplete"):
        await node.run(output_dir=str(tmp_path), context=_OkContext(produce=produced))

    assert spy.published == [], "a node that rejected its own output must not publish it"


@pytest.mark.asyncio
async def test_an_unusable_cached_entry_is_rebuilt_not_trusted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A poisoned entry must self-heal rather than skip the build forever.

    Without this, a bad entry is permanent: every run stages it, skips the
    build, and fails, so nothing ever republishes a good one. This is also what
    repairs entries poisoned before the publish gate existed, with no manual
    purge of the shared bucket.
    """
    bad_entry = tmp_path / "staged"
    (bad_entry).mkdir()
    (bad_entry / "leftover.txt").write_text("incomplete index\n", encoding="utf-8")
    spy = _SpyCache(staged=bad_entry)
    _install(monkeypatch, spy)

    seen: list[bool] = []

    class _PickyNode(_CachedNode):
        NODE_ID = "healing_probe"

        @classmethod
        def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
            ok = outputs[0].exists()
            seen.append(ok)
            if not ok:
                raise FileNotFoundError("staged reference is incomplete")

    produced = tmp_path / _PickyNode.NODE_ID / "artifact.txt"
    ctx = _OkContext(produce=produced)
    await _PickyNode().run(output_dir=str(tmp_path), context=ctx)

    assert ctx.calls == 1, "the build must actually run after rejecting the bad entry"
    assert seen == [False, True], "verify should reject the staged entry, then accept the build"
    assert (tmp_path / _PickyNode.NODE_ID / "leftover.txt").exists() is False, (
        "the rejected entry's files must be cleared so they cannot confuse the rebuild"
    )
    assert [ref for ref, _ in spy.published] == ["probe-ref-id"], (
        "the freshly built, verified reference should replace the poisoned entry"
    )


@pytest.mark.asyncio
async def test_a_good_cached_entry_still_skips_the_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of the cache: a valid entry must still skip the build."""
    good = tmp_path / "staged"
    good.mkdir()
    (good / "artifact.txt").write_text("cached artifact\n", encoding="utf-8")
    spy = _SpyCache(staged=good)
    _install(monkeypatch, spy)

    ctx = _OkContext()
    await _CachedNode().run(output_dir=str(tmp_path), context=ctx)

    assert ctx.calls == 0, "a valid cached reference must skip the build"
    assert spy.published == [], "a staged reference must not be re-published"


@pytest.mark.asyncio
async def test_a_failing_command_is_not_published(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = _SpyCache()
    _install(monkeypatch, spy)

    class _FailingContext:
        async def run_command(self, cmd: str | list[str], **kwargs: Any) -> dict[str, Any]:
            return {"returncode": 1, "stdout": "", "stderr": "boom"}

    node = _CachedNode()
    with pytest.raises(RuntimeError):
        await node.run(output_dir=str(tmp_path), context=_FailingContext())

    assert spy.published == []
