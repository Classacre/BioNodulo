"""A version bump releases the desktop app, without anyone remembering to.

The desktop app shipped 0.1.0-alpha.10 while the cloud editor served alpha.13,
because `desktop-release.yml` only fired on a `desktop-v*` tag and tagging was a
manual step after every bump. Three bumps in a row, nobody tagged, and the two
halves of one product reported different versions to the same user.

CI now releases on its own. These assert the properties that make that safe --
it is a release trigger, so failing open is worse than it not existing at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parents[1]
CI = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
RELEASE_TEXT = (REPO / ".github" / "workflows" / "desktop-release.yml").read_text()
RELEASE = yaml.safe_load(RELEASE_TEXT)

CHECK = "check-desktop-release"
CALL = "desktop-release"


def _triggers(workflow: dict) -> dict:
    # PyYAML parses the bare `on:` key as the boolean True.
    return workflow.get("on", workflow.get(True))


def test_ci_releases_the_desktop_app() -> None:
    assert CHECK in CI["jobs"]
    assert CALL in CI["jobs"]


def test_it_calls_the_release_workflow_rather_than_pushing_a_tag() -> None:
    """A tag pushed with GITHUB_TOKEN does not start another workflow run.

    Tagging from CI would therefore tag every release and build none of them --
    silently, since the tag would exist and look like success.
    """
    assert CI["jobs"][CALL]["uses"] == "./.github/workflows/desktop-release.yml"
    assert "workflow_call" in _triggers(RELEASE)

    # And the check job must not push one behind our back.
    check = yaml.dump(CI["jobs"][CHECK])
    assert "git push" not in check
    assert "git tag" not in check


def test_the_release_names_the_tag_it_was_given() -> None:
    """Called from ci.yml, `github.ref_name` is the branch, not a tag.

    Left unparameterised it would publish a release called "main" and overwrite
    it on every version.
    """
    assert "inputs.tag || github.ref_name" in RELEASE_TEXT
    assert _triggers(RELEASE)["workflow_call"]["inputs"]["tag"]["required"] is True
    assert "desktop-v${version}" in CI["jobs"][CHECK]["steps"][-1]["run"]


def test_the_manual_tag_path_still_works() -> None:
    patterns = _triggers(RELEASE)["push"]["tags"]

    assert any(p.startswith("desktop-v") for p in patterns), patterns


def test_it_waits_for_the_tests() -> None:
    # A release built from a red commit is worse than a late release.
    needs = CI["jobs"][CALL]["needs"]

    for job in ("python", "python-quality", "frontend", "e2e"):
        assert job in needs, f"{job} missing from {needs}"


def test_the_version_test_is_among_them() -> None:
    """`python` runs test_version_consistency, so a release cannot be built
    from a tree whose six version declarations disagree."""
    assert "python" in CI["jobs"][CALL]["needs"]
    assert (REPO / "tests" / "test_version_consistency.py").is_file()


def test_it_only_releases_from_main() -> None:
    condition = CI["jobs"][CHECK]["if"]

    assert "refs/heads/main" in condition
    # A pull_request run would release someone's branch.
    assert "push" in condition


def test_it_cannot_release_the_same_version_twice() -> None:
    """Re-runs, merges and force-pushes all replay this job.

    Keying on what was published (rather than diffing against the previous
    commit) also means a bump that landed while CI was red still releases on the
    next green push, instead of being skipped forever.
    """
    run = CI["jobs"][CHECK]["steps"][-1]["run"]

    assert "gh release view" in run
    assert "needed=false" in run
    assert CI["jobs"][CALL]["if"] == (
        "needs.check-desktop-release.outputs.needed == 'true'"
    )


def test_a_tag_alone_does_not_count_as_released() -> None:
    """tauri-action creates the tag BEFORE the per-OS builds finish.

    alpha.16 published with no Windows installer: a push cancelled that build,
    and because the check asked only whether the tag existed, every later run
    saw one and skipped. The gap was permanent.
    """
    run = CI["jobs"][CHECK]["steps"][-1]["run"]

    # Every platform's installer, or the release is incomplete and re-runs.
    for artifact in ("_x64-setup.exe", "_amd64.deb", "_x64.dmg", "_aarch64.dmg"):
        assert artifact in run, artifact
    assert "incomplete" in run


def test_a_push_cannot_cancel_a_release() -> None:
    """Releases run on main, and cancel-in-progress killed one mid-build."""
    cancel = CI["concurrency"]["cancel-in-progress"]

    assert "refs/heads/main" in str(cancel), cancel
    # Branches and PRs keep cancelling; fast feedback matters more there.
    assert "!=" in str(cancel), cancel


def test_an_incomplete_release_can_be_repaired_without_a_version_bump() -> None:
    triggers = _triggers(RELEASE)

    assert "tag" in triggers["workflow_dispatch"]["inputs"]


def test_the_release_may_write_contents() -> None:
    # ci.yml's top-level permission is contents: read, and a called workflow
    # cannot widen it for itself.
    assert CI["jobs"][CALL]["permissions"]["contents"] == "write"
    assert RELEASE["permissions"]["contents"] == "write"


def test_it_reads_the_version_from_the_repo() -> None:
    # A hardcoded version here would be the same manual step in a new place.
    assert "web/package.json" in CI["jobs"][CHECK]["steps"][-1]["run"]
