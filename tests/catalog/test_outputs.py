import errno
import json
import os
import stat
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

import bionodulo.nodes.contract.outputs as output_contract
from bionodulo.nodes.contract.artifacts import ArtifactContainer, Cardinality
from bionodulo.nodes.contract.outputs import (
    CollectedArtifact,
    CollectedOutputs,
    ConditionalCollector,
    DirectoryCollector,
    ExactCollector,
    GlobCollector,
    JsonValidator,
    MAX_CONTENT_VALIDATOR_BYTES,
    MAX_DIRECTORY_ENTRIES,
    MAX_GLOB_MATCHES,
    MAX_STDOUT_BYTES,
    OutputCollectionError,
    OutputCollector,
    OutputIdentityError,
    OutputRootError,
    OutputSpec,
    StdoutCollector,
    Utf8TextValidator,
    collect_outputs,
)


def output_spec(
    collector: object,
    *,
    port_id: str = "output",
    cardinality: Cardinality = Cardinality.ONE,
    require_nonempty: bool = False,
    allowed_extensions: tuple[str, ...] = (),
    validators: tuple[object, ...] = (),
) -> OutputSpec:
    return OutputSpec(
        port_id=port_id,
        artifact_type="artifact.file",
        cardinality=cardinality,
        collector=collector,
        require_nonempty=require_nonempty,
        allowed_extensions=allowed_extensions,
        validators=validators,
    )


def relative_paths(value: tuple[CollectedArtifact, ...]) -> tuple[str, ...]:
    return tuple(artifact.relative_path for artifact in value)


def open_descriptor_count() -> int:
    descriptor_directory = Path("/proc/self/fd")
    if not descriptor_directory.is_dir():
        pytest.skip("descriptor counting requires Linux /proc/self/fd")
    return len(os.listdir(descriptor_directory))


def instrument_scandir(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    real_scandir = output_contract.os.scandir
    observed: list[str] = []

    class CountingScandir:
        def __init__(self, directory: object) -> None:
            self._entries = real_scandir(directory)

        def __enter__(self) -> "CountingScandir":
            self._entries.__enter__()
            return self

        def __exit__(self, *args: object) -> object:
            return self._entries.__exit__(*args)

        def __iter__(self) -> "CountingScandir":
            return self

        def __next__(self) -> os.DirEntry[str]:
            entry = next(self._entries)
            observed.append(entry.name)
            return entry

    monkeypatch.setattr(output_contract, "_require_descriptor_primitives", lambda: None)
    monkeypatch.setattr(output_contract.os, "scandir", CountingScandir)
    return observed


def test_glob_collects_before_validating_the_logical_port(tmp_path: Path) -> None:
    (tmp_path / "sample_peaks.narrowPeak").write_text(
        "chr1\t1\t10\n",
        encoding="utf-8",
    )
    spec = output_spec(
        GlobCollector(
            pattern="*_peaks.narrowPeak",
            minimum=1,
            maximum=1,
        ),
        port_id="peaks",
        require_nonempty=True,
        allowed_extensions=(".narrowPeak",),
    )

    result = collect_outputs((spec,), tmp_path, stdout=None)

    artifact = result["peaks"]
    assert isinstance(artifact, CollectedArtifact)
    assert artifact.relative_path == "sample_peaks.narrowPeak"


def test_exact_missing_output_is_port_specific(tmp_path: Path) -> None:
    spec = output_spec(
        ExactCollector(relative_path="report.html"),
        port_id="report",
    )

    with pytest.raises(FileNotFoundError, match=r"report.*report\.html") as caught:
        collect_outputs((spec,), tmp_path, stdout=None)

    assert str(tmp_path) not in str(caught.value)


def test_stdout_collector_roundtrips_the_complete_declared_capture(
    tmp_path: Path,
) -> None:
    spec = output_spec(
        StdoutCollector(relative_path="tree.nwk", maximum_bytes=64),
        port_id="tree",
        require_nonempty=True,
    )

    result = collect_outputs(
        (spec,),
        tmp_path,
        stdout="(A,B);\n",
        stdout_truncated=False,
    )

    artifact = result["tree"]
    assert isinstance(artifact, CollectedArtifact)
    assert artifact.read_bytes_verified(tmp_path) == b"(A,B);\n"
    assert (tmp_path / "tree.nwk").read_bytes() == b"(A,B);\n"


@pytest.mark.parametrize(
    ("cardinality", "exists", "expected_shape"),
    (
        (Cardinality.ONE, True, "scalar"),
        (Cardinality.OPTIONAL_ONE, True, "scalar"),
        (Cardinality.OPTIONAL_ONE, False, "none"),
        (Cardinality.MANY, True, "tuple_one"),
        (Cardinality.MANY, False, "tuple_empty"),
        (Cardinality.NONEMPTY_MANY, True, "tuple_one"),
    ),
)
def test_exact_collector_preserves_cardinality_shapes(
    tmp_path: Path,
    cardinality: Cardinality,
    exists: bool,
    expected_shape: str,
) -> None:
    if exists:
        (tmp_path / "result.txt").write_text("value", encoding="utf-8")
    spec = output_spec(
        ExactCollector(relative_path="result.txt"),
        cardinality=cardinality,
    )

    value = collect_outputs((spec,), tmp_path, stdout=None)["output"]

    if expected_shape == "scalar":
        assert isinstance(value, CollectedArtifact)
    elif expected_shape == "none":
        assert value is None
    elif expected_shape == "tuple_one":
        assert isinstance(value, tuple)
        assert relative_paths(value) == ("result.txt",)
    else:
        assert value == ()
        assert isinstance(value, tuple)


@pytest.mark.parametrize("cardinality", (Cardinality.ONE, Cardinality.NONEMPTY_MANY))
def test_exact_collector_rejects_missing_required_shapes(
    tmp_path: Path,
    cardinality: Cardinality,
) -> None:
    spec = output_spec(
        ExactCollector(relative_path="missing.txt"),
        cardinality=cardinality,
    )

    with pytest.raises(FileNotFoundError, match="output"):
        collect_outputs((spec,), tmp_path, stdout=None)


@pytest.mark.parametrize(
    ("cardinality", "count", "expected_shape"),
    (
        (Cardinality.ONE, 1, "scalar"),
        (Cardinality.OPTIONAL_ONE, 0, "none"),
        (Cardinality.OPTIONAL_ONE, 1, "scalar"),
        (Cardinality.MANY, 0, "tuple_empty"),
        (Cardinality.MANY, 1, "tuple_one"),
        (Cardinality.NONEMPTY_MANY, 1, "tuple_one"),
    ),
)
def test_glob_collector_preserves_cardinality_shapes(
    tmp_path: Path,
    cardinality: Cardinality,
    count: int,
    expected_shape: str,
) -> None:
    for index in range(count):
        (tmp_path / f"result-{index}.txt").write_text("value", encoding="utf-8")
    spec = output_spec(
        GlobCollector(pattern="result-*.txt", minimum=0, maximum=3),
        cardinality=cardinality,
    )

    value = collect_outputs((spec,), tmp_path, stdout=None)["output"]

    if expected_shape == "scalar":
        assert isinstance(value, CollectedArtifact)
    elif expected_shape == "none":
        assert value is None
    elif expected_shape == "tuple_one":
        assert isinstance(value, tuple)
        assert len(value) == 1
    else:
        assert value == ()
        assert isinstance(value, tuple)


@pytest.mark.parametrize(
    ("cardinality", "count"),
    (
        (Cardinality.ONE, 0),
        (Cardinality.ONE, 2),
        (Cardinality.OPTIONAL_ONE, 2),
        (Cardinality.NONEMPTY_MANY, 0),
    ),
)
def test_glob_collector_rejects_cardinality_mismatches(
    tmp_path: Path,
    cardinality: Cardinality,
    count: int,
) -> None:
    for index in range(count):
        (tmp_path / f"result-{index}.txt").write_text("value", encoding="utf-8")
    spec = output_spec(
        GlobCollector(pattern="result-*.txt", minimum=0, maximum=3),
        cardinality=cardinality,
    )

    with pytest.raises(OutputCollectionError, match=r"output.*cardinality"):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_glob_results_have_canonical_posix_order(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    for relative_path in ("z.txt", "a.txt", "nested/c.txt", "nested/b.txt"):
        (tmp_path / relative_path).write_text(relative_path, encoding="utf-8")
    spec = output_spec(
        GlobCollector(pattern="nested/*.txt", minimum=0, maximum=10),
        cardinality=Cardinality.MANY,
    )

    value = collect_outputs((spec,), tmp_path, stdout=None)["output"]

    assert isinstance(value, tuple)
    assert relative_paths(value) == ("nested/b.txt", "nested/c.txt")


def test_glob_stops_at_maximum_plus_one(tmp_path: Path) -> None:
    for index in range(3):
        (tmp_path / f"result-{index}.txt").write_text("value", encoding="utf-8")
    spec = output_spec(
        GlobCollector(pattern="result-*.txt", minimum=0, maximum=2),
        cardinality=Cardinality.MANY,
    )

    with pytest.raises(OutputCollectionError, match=r"output.*maximum.*2"):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_glob_iteration_stops_at_maximum_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for index in range(8):
        (tmp_path / f"result-{index}.txt").write_text("value", encoding="utf-8")
    observed = instrument_scandir(monkeypatch)
    spec = output_spec(
        GlobCollector(pattern="*.txt", minimum=0, maximum=2),
        cardinality=Cardinality.MANY,
    )

    with pytest.raises(OutputCollectionError, match="maximum"):
        collect_outputs((spec,), tmp_path, stdout=None)

    assert len(observed) == 3


def test_glob_enforces_declared_minimum(tmp_path: Path) -> None:
    (tmp_path / "only.txt").write_text("value", encoding="utf-8")
    spec = output_spec(
        GlobCollector(pattern="*.txt", minimum=2, maximum=3),
        cardinality=Cardinality.MANY,
    )

    with pytest.raises(OutputCollectionError, match=r"minimum.*2"):
        collect_outputs((spec,), tmp_path, stdout=None)


@pytest.mark.parametrize(
    "relative_path",
    (
        "",
        ".",
        "./result.txt",
        "nested/./result.txt",
        "../result.txt",
        "nested/../result.txt",
        "/tmp/result.txt",
        "C:\\temp\\result.txt",
        "\\\\server\\share\\result.txt",
        "nested\\result.txt",
        "nested//result.txt",
        "result\x00.txt",
    ),
)
@pytest.mark.parametrize(
    "collector_type",
    (ExactCollector, StdoutCollector, DirectoryCollector),
)
def test_exact_style_collectors_reject_unsafe_relative_paths(
    relative_path: str,
    collector_type: type,
) -> None:
    with pytest.raises(ValidationError):
        collector_type(relative_path=relative_path)


@pytest.mark.parametrize(
    "pattern",
    (
        "",
        ".",
        "./*.txt",
        "../*.txt",
        "nested/../*.txt",
        "/tmp/*.txt",
        "C:\\temp\\*.txt",
        "\\\\server\\share\\*.txt",
        "nested\\*.txt",
        "nested//*.txt",
        "**/*.txt",
        "nested/**/result.txt",
        "result\x00*.txt",
        "result[.txt",
    ),
)
def test_glob_collector_rejects_unsafe_or_unbounded_patterns(pattern: str) -> None:
    with pytest.raises(ValidationError):
        GlobCollector(pattern=pattern, minimum=0, maximum=1)


def test_output_root_must_be_absolute_existing_directory(tmp_path: Path) -> None:
    file_root = tmp_path / "file"
    file_root.write_text("not a directory", encoding="utf-8")
    spec = output_spec(
        ExactCollector(relative_path="missing.txt"),
        cardinality=Cardinality.OPTIONAL_ONE,
    )

    for root in (Path("relative"), tmp_path / "missing", file_root):
        with pytest.raises(OutputRootError):
            collect_outputs((spec,), root, stdout=None)


def test_output_root_rejects_symlink(tmp_path: Path) -> None:
    actual_root = tmp_path / "actual"
    actual_root.mkdir()
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(actual_root, target_is_directory=True)
    spec = output_spec(
        ExactCollector(relative_path="missing.txt"),
        cardinality=Cardinality.OPTIONAL_ONE,
    )

    with pytest.raises(OutputRootError, match="symlink"):
        collect_outputs((spec,), linked_root, stdout=None)


def test_invalid_encoding_root_is_normalized_without_descriptor_leaks() -> None:
    before = open_descriptor_count()

    for _ in range(32):
        with pytest.raises(OutputRootError) as caught:
            collect_outputs((), "/\ud800", stdout=None)
        assert "\ud800" not in str(caught.value)

    assert open_descriptor_count() == before


def test_symlinked_root_ancestor_is_rejected_without_descriptor_leaks(
    tmp_path: Path,
) -> None:
    actual = tmp_path / "actual"
    (actual / "root").mkdir(parents=True)
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    unsafe_root = linked / "root"
    before = open_descriptor_count()

    for _ in range(32):
        with pytest.raises(OutputRootError) as caught:
            collect_outputs((), unsafe_root, stdout=None)
        assert str(unsafe_root) not in str(caught.value)

    assert open_descriptor_count() == before


def test_exact_rejects_symlink_leaf_without_leaking_root(tmp_path: Path) -> None:
    (tmp_path / "target.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "result.txt").symlink_to("target.txt")
    spec = output_spec(ExactCollector(relative_path="result.txt"))

    with pytest.raises(OutputCollectionError, match=r"output.*result\.txt.*symlink") as caught:
        collect_outputs((spec,), tmp_path, stdout=None)

    assert str(tmp_path) not in str(caught.value)


def test_exact_rejects_symlink_intermediate_directory(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "result.txt").write_text("value", encoding="utf-8")
    (tmp_path / "linked").symlink_to(actual, target_is_directory=True)
    spec = output_spec(ExactCollector(relative_path="linked/result.txt"))

    with pytest.raises(OutputCollectionError, match=r"output.*linked/result\.txt.*symlink"):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_glob_rejects_symlink_leaf_and_intermediate_directory(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "target.txt").write_text("value", encoding="utf-8")
    (actual / "linked.txt").symlink_to("target.txt")
    (tmp_path / "linked-dir").symlink_to(actual, target_is_directory=True)

    leaf_spec = output_spec(
        GlobCollector(pattern="actual/*.txt", minimum=0, maximum=10),
        cardinality=Cardinality.MANY,
    )
    with pytest.raises(OutputCollectionError, match="symlink"):
        collect_outputs((leaf_spec,), tmp_path, stdout=None)

    intermediate_spec = output_spec(
        GlobCollector(pattern="linked-dir/*.txt", minimum=0, maximum=10),
        cardinality=Cardinality.MANY,
    )
    with pytest.raises(OutputCollectionError, match="symlink"):
        collect_outputs((intermediate_spec,), tmp_path, stdout=None)


def test_exact_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "result.pipe")
    spec = output_spec(ExactCollector(relative_path="result.pipe"))

    with pytest.raises(OutputCollectionError, match=r"output.*regular file"):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_collectors_reject_file_directory_kind_mismatches(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("value", encoding="utf-8")
    (tmp_path / "directory").mkdir()

    with pytest.raises(OutputCollectionError, match="directory"):
        collect_outputs(
            (
                OutputSpec(
                    port_id="directory",
                    artifact_type="artifact.directory",
                    collector=DirectoryCollector(relative_path="file.txt"),
                ),
            ),
            tmp_path,
            stdout=None,
        )

    with pytest.raises(OutputCollectionError, match="regular file"):
        collect_outputs(
            (output_spec(ExactCollector(relative_path="directory")),),
            tmp_path,
            stdout=None,
        )


@pytest.mark.parametrize("preexisting_kind", ("file", "symlink"))
def test_stdout_never_overwrites_preexisting_objects(
    tmp_path: Path,
    preexisting_kind: str,
) -> None:
    target = tmp_path / "stdout.txt"
    if preexisting_kind == "file":
        target.write_text("original", encoding="utf-8")
    else:
        (tmp_path / "original.txt").write_text("original", encoding="utf-8")
        target.symlink_to("original.txt")
    original_identity = target.lstat()
    spec = output_spec(StdoutCollector(relative_path="stdout.txt", maximum_bytes=64))

    with pytest.raises(OutputCollectionError, match=r"output.*stdout\.txt.*exists"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="replacement",
            stdout_truncated=False,
        )

    preserved = tmp_path / "original.txt" if preexisting_kind == "symlink" else target
    assert preserved.read_text(encoding="utf-8") == "original"
    assert target.lstat().st_ino == original_identity.st_ino
    if preexisting_kind == "symlink":
        assert stat.S_ISLNK(target.lstat().st_mode)
        assert os.readlink(target) == "original.txt"


@pytest.mark.parametrize("preexisting_kind", ("directory", "fifo"))
def test_stdout_never_opens_or_overwrites_preexisting_special_targets(
    tmp_path: Path,
    preexisting_kind: str,
) -> None:
    target = tmp_path / "stdout.txt"
    if preexisting_kind == "directory":
        target.mkdir()
    else:
        os.mkfifo(target)
    original_identity = target.lstat()
    spec = output_spec(StdoutCollector(relative_path="stdout.txt", maximum_bytes=64))

    with pytest.raises(OutputCollectionError, match=r"output.*stdout\.txt.*exists"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="replacement",
            stdout_truncated=False,
        )

    assert target.lstat().st_ino == original_identity.st_ino
    if preexisting_kind == "directory":
        assert stat.S_ISDIR(target.lstat().st_mode)
    else:
        assert stat.S_ISFIFO(target.lstat().st_mode)


def test_stdout_rejects_truncated_or_unmarked_capture_without_writing(
    tmp_path: Path,
) -> None:
    spec = output_spec(StdoutCollector(relative_path="stdout.txt", maximum_bytes=64))

    with pytest.raises(OutputCollectionError, match=r"output.*truncated"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="tail",
            stdout_truncated=True,
        )
    assert not (tmp_path / "stdout.txt").exists()

    with pytest.raises(OutputCollectionError, match=r"output.*truncation metadata"):
        collect_outputs((spec,), tmp_path, stdout="complete")
    assert not (tmp_path / "stdout.txt").exists()


@pytest.mark.parametrize("stdout_truncated", (None, False))
def test_active_required_stdout_without_payload_is_missing(
    tmp_path: Path,
    stdout_truncated: bool | None,
) -> None:
    spec = output_spec(StdoutCollector(relative_path="stdout.txt", maximum_bytes=64))

    with pytest.raises(FileNotFoundError, match="output"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout=None,
            stdout_truncated=stdout_truncated,
        )


@pytest.mark.parametrize(
    "cardinality",
    (Cardinality.ONE, Cardinality.OPTIONAL_ONE),
)
def test_active_stdout_rejects_truncated_capture_without_payload(
    tmp_path: Path,
    cardinality: Cardinality,
) -> None:
    spec = output_spec(
        StdoutCollector(relative_path="stdout.txt", maximum_bytes=64),
        cardinality=cardinality,
    )

    with pytest.raises(OutputCollectionError, match=r"output.*truncated"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout=None,
            stdout_truncated=True,
        )

    assert not (tmp_path / "stdout.txt").exists()


def test_stdout_rejects_encoded_byte_limit_before_writing(tmp_path: Path) -> None:
    spec = output_spec(StdoutCollector(relative_path="stdout.txt", maximum_bytes=4))

    with pytest.raises(OutputCollectionError, match=r"output.*maximum.*4"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="\u00e9\u00e9\u00e9",
            stdout_truncated=False,
        )

    assert not (tmp_path / "stdout.txt").exists()


@pytest.mark.parametrize(
    "updates",
    (
        {"require_nonempty": True},
        {"validators": (JsonValidator(maximum_bytes=64),)},
    ),
)
def test_stdout_removes_only_its_new_file_when_validation_fails(
    tmp_path: Path,
    updates: dict[str, object],
) -> None:
    spec = output_spec(
        StdoutCollector(relative_path="stdout.txt", maximum_bytes=64),
        **updates,
    )

    with pytest.raises(OutputCollectionError):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="",
            stdout_truncated=False,
        )

    assert not (tmp_path / "stdout.txt").exists()


def test_stdout_target_remains_hidden_until_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "stdout.json"
    spec = output_spec(
        StdoutCollector(relative_path="stdout.json", maximum_bytes=64),
        validators=(JsonValidator(maximum_bytes=64),),
    )
    real_validate = output_contract._validate_content
    validation_observed = False

    def validate_while_hidden(*args: object) -> None:
        nonlocal validation_observed
        validation_observed = True
        assert not target.exists()
        real_validate(*args)

    monkeypatch.setattr(output_contract, "_validate_content", validate_while_hidden)

    collect_outputs(
        (spec,),
        tmp_path,
        stdout='{"ok":true}',
        stdout_truncated=False,
    )

    assert validation_observed
    assert target.read_text(encoding="utf-8") == '{"ok":true}'


def test_stdout_validation_failure_never_unlinks_a_racing_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "stdout.json"
    replacement = tmp_path / "replacement.json"
    spec = output_spec(
        StdoutCollector(relative_path="stdout.json", maximum_bytes=64),
        validators=(JsonValidator(maximum_bytes=64),),
    )
    real_stat_entry = output_contract._stat_entry
    race_triggered = False

    def replace_after_stat(parent_fd: int, path: str) -> os.stat_result | None:
        nonlocal race_triggered
        captured_stat = real_stat_entry(parent_fd, path)
        if path == "stdout.json" and captured_stat is not None:
            race_triggered = True
            replacement.write_text('{"replacement":true}', encoding="utf-8")
            replacement.replace(target)
        return captured_stat

    monkeypatch.setattr(output_contract, "_stat_entry", replace_after_stat)

    with pytest.raises(OutputCollectionError, match="JSON"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="{broken",
            stdout_truncated=False,
        )

    assert not race_triggered
    if target.exists():
        assert target.read_text(encoding="utf-8") == '{"replacement":true}'


def test_stdout_post_link_replacement_is_detected_and_never_rolled_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "stdout.txt"
    replacement = tmp_path / "replacement.txt"
    replacement.write_bytes(b"other")
    replacement_identity = replacement.lstat()
    spec = output_spec(StdoutCollector(relative_path="stdout.txt", maximum_bytes=64))
    real_link = output_contract._link_anonymous_file

    def link_then_replace(source_fd: int, parent_fd: int, name: str) -> None:
        real_link(source_fd, parent_fd, name)
        replacement.replace(target)

    monkeypatch.setattr(output_contract, "_link_anonymous_file", link_then_replace)

    with pytest.raises(OutputCollectionError, match=r"output.*stdout\.txt.*changed"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="first",
            stdout_truncated=False,
        )

    assert target.read_bytes() == b"other"
    assert target.lstat().st_ino == replacement_identity.st_ino


def test_multiple_active_stdout_collectors_fail_before_any_filesystem_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = (
        output_spec(
            StdoutCollector(relative_path="first.txt", maximum_bytes=64),
            port_id="first",
        ),
        output_spec(
            StdoutCollector(relative_path="second.txt", maximum_bytes=64),
            port_id="second",
        ),
    )

    filesystem_calls: list[str] = []

    def unexpected_filesystem_call(*_args: object, **_kwargs: object) -> object:
        filesystem_calls.append("called")
        raise AssertionError("filesystem I/O occurred before stdout preflight")

    monkeypatch.setattr(output_contract, "_open_root", unexpected_filesystem_call)
    monkeypatch.setattr(output_contract, "_create_stdout_artifact", unexpected_filesystem_call)

    with pytest.raises(OutputCollectionError) as caught:
        collect_outputs(
            specs,
            tmp_path,
            stdout="value",
            stdout_truncated=False,
        )

    assert str(caught.value) == (
        "multiple active stdout collectors conflict: port 'first' path 'first.txt'; port 'second' path 'second.txt'"
    )
    assert str(tmp_path) not in str(caught.value)
    assert filesystem_calls == []
    assert not (tmp_path / "first.txt").exists()
    assert not (tmp_path / "second.txt").exists()


def test_inactive_conditional_stdout_does_not_count_as_a_conflict(tmp_path: Path) -> None:
    specs = (
        output_spec(
            StdoutCollector(relative_path="active.txt", maximum_bytes=64),
            port_id="active",
        ),
        output_spec(
            ConditionalCollector(
                condition_key="emit_second",
                expected_value=True,
                collector=StdoutCollector(
                    relative_path="inactive.txt",
                    maximum_bytes=64,
                ),
            ),
            port_id="inactive",
            cardinality=Cardinality.OPTIONAL_ONE,
        ),
    )

    result = collect_outputs(
        specs,
        tmp_path,
        stdout="value",
        stdout_truncated=False,
        conditions={"emit_second": False},
    )

    assert isinstance(result["active"], CollectedArtifact)
    assert result["inactive"] is None
    assert (tmp_path / "active.txt").read_text(encoding="utf-8") == "value"
    assert not (tmp_path / "inactive.txt").exists()


@pytest.mark.parametrize("staging_failure", ("missing", "failed"))
def test_stdout_unsupported_anonymous_staging_fails_closed_without_leaks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    staging_failure: str,
) -> None:
    target = tmp_path / "stdout.txt"
    spec = output_spec(
        StdoutCollector(relative_path="stdout.txt", maximum_bytes=64),
        port_id="captured_stdout",
    )
    tmpfile_flag = output_contract.os.O_TMPFILE
    if staging_failure == "missing":
        monkeypatch.delattr(output_contract.os, "O_TMPFILE")
    else:
        real_open = output_contract.os.open

        def fail_anonymous_open(
            path: object,
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            if path == "." and flags & tmpfile_flag:
                raise OSError(errno.EOPNOTSUPP, "unsupported")
            return real_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(output_contract, "_require_descriptor_primitives", lambda: None)
        monkeypatch.setattr(output_contract.os, "open", fail_anonymous_open)
    before = open_descriptor_count()

    with pytest.raises(
        OutputCollectionError,
        match=r"captured_stdout.*stdout\.txt.*support",
    ) as caught:
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="value",
            stdout_truncated=False,
        )

    assert str(tmp_path) not in str(caught.value)
    assert not target.exists()
    assert open_descriptor_count() == before


@pytest.mark.parametrize(
    "error_number",
    (errno.ENOSYS, errno.EOPNOTSUPP, errno.EPERM, errno.EINVAL),
)
def test_stdout_unsupported_linkat_fails_closed_without_leaks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_number: int,
) -> None:
    target = tmp_path / "stdout.txt"
    spec = output_spec(
        StdoutCollector(relative_path="stdout.txt", maximum_bytes=64),
        port_id="captured_stdout",
    )
    monkeypatch.setattr(
        output_contract,
        "_link_anonymous_file",
        lambda *_args: (_ for _ in ()).throw(OSError(error_number, "unsupported")),
    )
    before = open_descriptor_count()

    with pytest.raises(
        OutputCollectionError,
        match=r"captured_stdout.*stdout\.txt.*support",
    ) as caught:
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="value",
            stdout_truncated=False,
        )

    assert str(tmp_path) not in str(caught.value)
    assert not target.exists()
    assert open_descriptor_count() == before


def test_utf8_text_validator_accepts_bounded_text(tmp_path: Path) -> None:
    (tmp_path / "text.txt").write_bytes("caf\u00e9".encode())
    spec = output_spec(
        ExactCollector(relative_path="text.txt"),
        validators=(Utf8TextValidator(maximum_bytes=5),),
    )

    artifact = collect_outputs((spec,), tmp_path, stdout=None)["output"]

    assert isinstance(artifact, CollectedArtifact)


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (b"123456", "maximum"),
        (b"bad\xff", "UTF-8"),
    ),
)
def test_utf8_text_validator_rejects_over_limit_and_invalid_text(
    tmp_path: Path,
    payload: bytes,
    message: str,
) -> None:
    (tmp_path / "text.txt").write_bytes(payload)
    spec = output_spec(
        ExactCollector(relative_path="text.txt"),
        validators=(Utf8TextValidator(maximum_bytes=5),),
    )

    with pytest.raises(OutputCollectionError, match=message):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_json_validator_accepts_bounded_json(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text('{"ok":true}', encoding="utf-8")
    spec = output_spec(
        ExactCollector(relative_path="data.json"),
        validators=(JsonValidator(maximum_bytes=32),),
    )

    artifact = collect_outputs((spec,), tmp_path, stdout=None)["output"]

    assert isinstance(artifact, CollectedArtifact)


@pytest.mark.parametrize(
    ("payload", "maximum_bytes", "message"),
    (
        (b'{"too":"large"}', 8, "maximum"),
        (b"{broken", 32, "JSON"),
        (b'{"bad":"\xff"}', 32, "UTF-8"),
    ),
)
def test_json_validator_rejects_bounded_or_malformed_content(
    tmp_path: Path,
    payload: bytes,
    maximum_bytes: int,
    message: str,
) -> None:
    (tmp_path / "data.json").write_bytes(payload)
    spec = output_spec(
        ExactCollector(relative_path="data.json"),
        validators=(JsonValidator(maximum_bytes=maximum_bytes),),
    )

    with pytest.raises(OutputCollectionError, match=message):
        collect_outputs((spec,), tmp_path, stdout=None)


@pytest.mark.parametrize(
    "payload",
    (
        b"1e9999",
        b"-1e9999",
        b"NaN",
        b"Infinity",
        b"-Infinity",
        b"{} trailing",
    ),
)
def test_json_validator_rejects_every_nonfinite_or_trailing_form(
    tmp_path: Path,
    payload: bytes,
) -> None:
    (tmp_path / "data.json").write_bytes(payload)
    spec = output_spec(
        ExactCollector(relative_path="data.json"),
        validators=(JsonValidator(maximum_bytes=32),),
    )

    with pytest.raises(OutputCollectionError, match=r"output.*data\.json.*JSON"):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_require_nonempty_rejects_empty_files_and_directories(tmp_path: Path) -> None:
    (tmp_path / "empty.txt").touch()
    (tmp_path / "empty-dir").mkdir()

    with pytest.raises(OutputCollectionError, match=r"file.*empty"):
        collect_outputs(
            (
                output_spec(
                    ExactCollector(relative_path="empty.txt"),
                    require_nonempty=True,
                ),
            ),
            tmp_path,
            stdout=None,
        )

    directory_spec = OutputSpec(
        port_id="directory",
        artifact_type="artifact.directory",
        collector=DirectoryCollector(relative_path="empty-dir", maximum_entries=5),
        require_nonempty=True,
    )
    with pytest.raises(OutputCollectionError, match=r"directory.*empty"):
        collect_outputs((directory_spec,), tmp_path, stdout=None)


def test_directory_nonempty_means_a_real_descendant_entry(tmp_path: Path) -> None:
    (tmp_path / "tree").mkdir()
    (tmp_path / "tree" / "empty-child").mkdir()
    spec = OutputSpec(
        port_id="directory",
        artifact_type="artifact.directory",
        collector=DirectoryCollector(relative_path="tree", maximum_entries=5),
        require_nonempty=True,
    )

    artifact = collect_outputs((spec,), tmp_path, stdout=None)["directory"]

    assert isinstance(artifact, CollectedArtifact)
    assert tuple(entry.relative_path for entry in artifact.entries) == ("tree/empty-child",)


def conditional_spec(
    cardinality: Cardinality = Cardinality.OPTIONAL_ONE,
) -> OutputSpec:
    return output_spec(
        ConditionalCollector(
            condition_key="emit",
            expected_value=True,
            collector=ExactCollector(relative_path="result.txt"),
        ),
        cardinality=cardinality,
        require_nonempty=True,
    )


def test_conditional_collector_true_and_false_shapes(tmp_path: Path) -> None:
    (tmp_path / "result.txt").write_text("value", encoding="utf-8")
    optional = conditional_spec()

    active = collect_outputs(
        (optional,),
        tmp_path,
        stdout=None,
        conditions={"emit": True},
    )["output"]
    inactive = collect_outputs(
        (optional,),
        tmp_path,
        stdout=None,
        conditions={"emit": False},
    )["output"]

    assert isinstance(active, CollectedArtifact)
    assert inactive is None

    many = conditional_spec(Cardinality.MANY)
    many_inactive = collect_outputs(
        (many,),
        tmp_path,
        stdout=None,
        conditions={"emit": False},
    )["output"]
    assert many_inactive == ()
    assert isinstance(many_inactive, tuple)


def test_conditional_collector_missing_condition_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(OutputCollectionError, match=r"output.*emit.*missing"):
        collect_outputs(
            (conditional_spec(),),
            tmp_path,
            stdout=None,
            conditions={},
        )


def test_conditional_comparison_is_type_exact(tmp_path: Path) -> None:
    (tmp_path / "result.txt").write_text("value", encoding="utf-8")

    value = collect_outputs(
        (conditional_spec(),),
        tmp_path,
        stdout=None,
        conditions={"emit": 1},
    )["output"]

    assert value is None


def test_inactive_conditional_exact_ignores_missing_and_symlink_paths(
    tmp_path: Path,
) -> None:
    spec = conditional_spec()

    assert (
        collect_outputs(
            (spec,),
            tmp_path,
            stdout=None,
            conditions={"emit": False},
        )["output"]
        is None
    )

    (tmp_path / "target.txt").write_text("value", encoding="utf-8")
    (tmp_path / "result.txt").symlink_to("target.txt")
    assert (
        collect_outputs(
            (spec,),
            tmp_path,
            stdout=None,
            conditions={"emit": False},
        )["output"]
        is None
    )
    with pytest.raises(OutputCollectionError, match="symlink"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout=None,
            conditions={"emit": True},
        )


def test_inactive_conditional_glob_skips_minimum_enforcement(tmp_path: Path) -> None:
    spec = output_spec(
        ConditionalCollector(
            condition_key="emit",
            expected_value=True,
            collector=GlobCollector(pattern="*.txt", minimum=1, maximum=2),
        ),
        cardinality=Cardinality.MANY,
    )

    assert (
        collect_outputs(
            (spec,),
            tmp_path,
            stdout=None,
            conditions={"emit": False},
        )["output"]
        == ()
    )
    with pytest.raises(OutputCollectionError, match="minimum"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout=None,
            conditions={"emit": True},
        )


def test_inactive_conditional_stdout_ignores_payload_and_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "stdout.txt"
    (tmp_path / "existing.txt").write_text("existing", encoding="utf-8")
    target.symlink_to("existing.txt")
    spec = output_spec(
        ConditionalCollector(
            condition_key="emit",
            expected_value=True,
            collector=StdoutCollector(relative_path="stdout.txt", maximum_bytes=64),
        ),
        cardinality=Cardinality.OPTIONAL_ONE,
    )

    assert (
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="ignored",
            conditions={"emit": False},
        )["output"]
        is None
    )
    assert target.is_symlink()
    assert target.read_text(encoding="utf-8") == "existing"

    with pytest.raises(OutputCollectionError, match="exists"):
        collect_outputs(
            (spec,),
            tmp_path,
            stdout="active",
            stdout_truncated=False,
            conditions={"emit": True},
        )


@pytest.mark.parametrize(
    "cardinality",
    (
        Cardinality.ONE,
        Cardinality.NONEMPTY_MANY,
    ),
)
def test_conditional_specs_cannot_claim_required_outputs(
    cardinality: Cardinality,
) -> None:
    with pytest.raises(ValidationError, match="conditional"):
        output_spec(
            ConditionalCollector(
                condition_key="emit",
                expected_value=True,
                collector=ExactCollector(relative_path="result.txt"),
            ),
            cardinality=cardinality,
        )


def test_duplicate_port_ids_fail_before_stdout_side_effects(tmp_path: Path) -> None:
    first = output_spec(
        StdoutCollector(relative_path="first.txt", maximum_bytes=64),
        port_id="duplicate",
    )
    second = output_spec(
        ExactCollector(relative_path="second.txt"),
        port_id="duplicate",
    )

    with pytest.raises(OutputCollectionError, match=r"duplicate.*port"):
        collect_outputs(
            (first, second),
            tmp_path,
            stdout="value",
            stdout_truncated=False,
        )

    assert not (tmp_path / "first.txt").exists()


def test_unrelated_workspace_files_are_not_returned(tmp_path: Path) -> None:
    (tmp_path / "declared.txt").write_text("declared", encoding="utf-8")
    (tmp_path / "unrelated.txt").write_text("unrelated", encoding="utf-8")
    spec = output_spec(
        ExactCollector(relative_path="declared.txt"),
        port_id="declared",
    )

    result = collect_outputs((spec,), tmp_path, stdout=None)

    assert tuple(result) == ("declared",)
    assert set(result.keys()) == {"declared"}


def test_allowed_extensions_are_exact_and_apply_to_every_file(
    tmp_path: Path,
) -> None:
    (tmp_path / "first.tar.gz").write_text("one", encoding="utf-8")
    (tmp_path / "second.gz").write_text("two", encoding="utf-8")
    spec = output_spec(
        GlobCollector(pattern="*.gz", minimum=0, maximum=5),
        cardinality=Cardinality.MANY,
        allowed_extensions=(".tar.gz",),
    )

    with pytest.raises(OutputCollectionError, match=r"output.*second\.gz.*extension"):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_glob_directory_outputs_require_explicit_container(tmp_path: Path) -> None:
    (tmp_path / "tree-a").mkdir()

    implicit_file_spec = output_spec(
        GlobCollector(pattern="tree-*", minimum=0, maximum=5),
        cardinality=Cardinality.MANY,
    )
    with pytest.raises(OutputCollectionError, match="regular file"):
        collect_outputs((implicit_file_spec,), tmp_path, stdout=None)

    directory_spec = OutputSpec(
        port_id="directories",
        artifact_type="artifact.directory",
        cardinality=Cardinality.MANY,
        collector=GlobCollector(
            pattern="tree-*",
            minimum=0,
            maximum=5,
            container=ArtifactContainer.DIRECTORY,
            maximum_directory_entries=5,
        ),
    )
    value = collect_outputs((directory_spec,), tmp_path, stdout=None)["directories"]
    assert isinstance(value, tuple)
    assert len(value) == 1
    assert value[0].container is ArtifactContainer.DIRECTORY


def test_output_spec_rejects_directory_extension_and_content_validation() -> None:
    collector = DirectoryCollector(relative_path="tree", maximum_entries=5)

    with pytest.raises(ValidationError, match="file"):
        OutputSpec(
            port_id="directory",
            artifact_type="artifact.directory",
            collector=collector,
            allowed_extensions=(".txt",),
        )
    with pytest.raises(ValidationError, match="file"):
        OutputSpec(
            port_id="directory",
            artifact_type="artifact.directory",
            collector=collector,
            validators=(Utf8TextValidator(maximum_bytes=5),),
        )


@pytest.mark.parametrize(
    "extension",
    ("", "txt", ".", "..txt", ".tar.", ".bad/path", " .txt", ".txt "),
)
def test_output_spec_rejects_malformed_extensions(extension: str) -> None:
    with pytest.raises(ValidationError, match="extension"):
        output_spec(
            ExactCollector(relative_path="result.txt"),
            allowed_extensions=(extension,),
        )


def test_collector_union_is_discriminated_and_json_roundtrips() -> None:
    adapter = TypeAdapter(OutputCollector)
    collector = ConditionalCollector(
        condition_key="emit",
        expected_value="yes",
        collector=GlobCollector(pattern="*.txt", minimum=0, maximum=2),
    )

    payload = adapter.dump_json(collector)

    assert json.loads(payload)["kind"] == "conditional"
    assert adapter.validate_json(payload) == collector


@pytest.mark.parametrize(
    "model",
    (
        ExactCollector,
        GlobCollector,
        StdoutCollector,
        DirectoryCollector,
        ConditionalCollector,
        Utf8TextValidator,
        JsonValidator,
        OutputSpec,
    ),
)
def test_output_models_are_strict_frozen_and_extra_forbid(model: type) -> None:
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["frozen"] is True
    assert model.model_config["strict"] is True
    assert model.model_config["validate_default"] is True
    assert model.model_config["revalidate_instances"] == "always"


def test_output_models_reject_mutation_coercion_and_extras() -> None:
    collector = GlobCollector(pattern="*.txt", minimum=0, maximum=2)
    with pytest.raises(ValidationError, match="frozen_instance"):
        collector.maximum = 3
    with pytest.raises(ValidationError):
        GlobCollector(pattern="*.txt", minimum=False, maximum=2)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ExactCollector(relative_path="result.txt", unexpected=True)
    with pytest.raises(ValidationError):
        output_spec(
            ExactCollector(relative_path="result.txt"),
            validators=[Utf8TextValidator(maximum_bytes=5)],
        )


@pytest.mark.parametrize(
    ("instance", "update"),
    (
        (
            GlobCollector(pattern="*.txt", minimum=0, maximum=2),
            {"maximum": 100_000_000},
        ),
        (
            StdoutCollector(relative_path="stdout.txt", maximum_bytes=64),
            {"maximum_bytes": 100_000_000},
        ),
        (
            DirectoryCollector(relative_path="tree", maximum_entries=5),
            {"maximum_entries": 100_000_000},
        ),
        (
            JsonValidator(maximum_bytes=64),
            {"maximum_bytes": 100_000_000},
        ),
    ),
)
def test_output_model_copy_revalidates_hard_bounds(
    instance: object,
    update: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        instance.model_copy(update=update)


@pytest.mark.parametrize(
    ("factory", "minimum", "maximum"),
    (
        (
            lambda value: GlobCollector(
                pattern="*.txt",
                minimum=value,
                maximum=MAX_GLOB_MATCHES,
            ),
            0,
            MAX_GLOB_MATCHES,
        ),
        (
            lambda value: GlobCollector(pattern="*.txt", minimum=0, maximum=value),
            0,
            MAX_GLOB_MATCHES,
        ),
        (
            lambda value: GlobCollector(
                pattern="*.txt",
                minimum=0,
                maximum=1,
                maximum_directory_entries=value,
            ),
            0,
            MAX_DIRECTORY_ENTRIES,
        ),
        (
            lambda value: StdoutCollector(relative_path="stdout.txt", maximum_bytes=value),
            1,
            MAX_STDOUT_BYTES,
        ),
        (
            lambda value: Utf8TextValidator(maximum_bytes=value),
            1,
            MAX_CONTENT_VALIDATOR_BYTES,
        ),
        (
            lambda value: JsonValidator(maximum_bytes=value),
            1,
            MAX_CONTENT_VALIDATOR_BYTES,
        ),
        (
            lambda value: DirectoryCollector(relative_path="tree", maximum_entries=value),
            0,
            MAX_DIRECTORY_ENTRIES,
        ),
    ),
)
def test_bounded_integer_fields_enforce_exact_lower_and_upper_limits(
    factory: Callable[[object], object],
    minimum: int,
    maximum: int,
) -> None:
    factory(minimum)
    with pytest.raises(ValidationError):
        factory(minimum - 1)
    with pytest.raises(ValidationError):
        factory(False)
    factory(maximum)
    with pytest.raises(ValidationError):
        factory(maximum + 1)
    with pytest.raises(ValidationError):
        factory(True)


def test_constructed_collectors_and_specs_are_revalidated(tmp_path: Path) -> None:
    invalid_collector = GlobCollector.model_construct(
        kind="glob",
        pattern="../*.txt",
        minimum=0,
        maximum=100_000_000,
        container=ArtifactContainer.FILE,
        maximum_directory_entries=5,
    )
    with pytest.raises(ValidationError):
        output_spec(invalid_collector)

    invalid_spec = OutputSpec.model_construct(
        port_id="BAD",
        artifact_type="artifact.file",
        cardinality=Cardinality.ONE,
        collector=invalid_collector,
        require_nonempty=False,
        allowed_extensions=(),
        validators=(),
    )
    with pytest.raises(ValidationError):
        collect_outputs((invalid_spec,), tmp_path, stdout=None)
    with pytest.raises(ValidationError):
        invalid_spec.model_copy()


def test_constructed_missing_and_wrong_nested_models_fail_cleanly(tmp_path: Path) -> None:
    missing_path = ExactCollector.model_construct(kind="exact")
    malformed_validator = JsonValidator.model_construct(
        kind="json",
        maximum_bytes="64",
    )

    with pytest.raises(ValidationError):
        output_spec(missing_path)
    with pytest.raises(ValidationError):
        missing_path.model_copy()
    with pytest.raises(ValidationError):
        output_spec(
            ExactCollector(relative_path="result.json"),
            validators=(malformed_validator,),
        )

    wrong_nested = OutputSpec.model_construct(
        port_id="output",
        artifact_type="artifact.file",
        cardinality=Cardinality.ONE,
        collector=Utf8TextValidator(maximum_bytes=64),
        require_nonempty=False,
        allowed_extensions=(),
        validators=(),
    )
    with pytest.raises(ValidationError):
        collect_outputs((wrong_nested,), tmp_path, stdout=None)


def test_collected_identity_detects_leaf_replacement(tmp_path: Path) -> None:
    path = tmp_path / "result.txt"
    path.write_bytes(b"first")
    artifact = collect_outputs(
        (output_spec(ExactCollector(relative_path="result.txt")),),
        tmp_path,
        stdout=None,
    )["output"]
    assert isinstance(artifact, CollectedArtifact)
    assert artifact.read_bytes_verified(tmp_path) == b"first"

    replacement = tmp_path / "replacement.txt"
    replacement.write_bytes(b"other")
    replacement.replace(path)

    with pytest.raises(OutputIdentityError, match="changed"):
        artifact.read_bytes_verified(tmp_path)


def test_collected_identity_detects_same_inode_same_size_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "result.txt"
    path.write_bytes(b"first")
    artifact = collect_outputs(
        (output_spec(ExactCollector(relative_path="result.txt")),),
        tmp_path,
        stdout=None,
    )["output"]
    assert isinstance(artifact, CollectedArtifact)

    path.write_bytes(b"other")
    rewritten = path.stat()
    os.utime(
        path,
        ns=(rewritten.st_atime_ns, artifact.identity.modified_time_ns + 1_000_000_000),
    )

    assert path.stat().st_ino == artifact.identity.inode
    assert path.stat().st_size == artifact.identity.size
    with pytest.raises(OutputIdentityError, match="changed"):
        artifact.read_bytes_verified(tmp_path)


def test_verified_open_detects_in_context_rewrite_on_exit(tmp_path: Path) -> None:
    path = tmp_path / "result.txt"
    path.write_bytes(b"first")
    artifact = collect_outputs(
        (output_spec(ExactCollector(relative_path="result.txt")),),
        tmp_path,
        stdout=None,
    )["output"]
    assert isinstance(artifact, CollectedArtifact)

    with pytest.raises(OutputIdentityError, match="changed"):
        with artifact.open_verified(tmp_path) as opened:
            assert opened.read() == b"first"
            path.write_bytes(b"other")


def test_verified_read_detects_rewrite_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "result.txt"
    path.write_bytes(b"first")
    artifact = collect_outputs(
        (output_spec(ExactCollector(relative_path="result.txt")),),
        tmp_path,
        stdout=None,
    )["output"]
    assert isinstance(artifact, CollectedArtifact)
    real_fdopen = output_contract.os.fdopen

    class RewritingReader:
        def __init__(self, descriptor: int) -> None:
            self._opened = real_fdopen(descriptor, "rb", closefd=True)

        def read(self, size: int = -1) -> bytes:
            path.write_bytes(b"other")
            return self._opened.read(size)

        def fileno(self) -> int:
            return self._opened.fileno()

        def close(self) -> None:
            self._opened.close()

        @property
        def closed(self) -> bool:
            return self._opened.closed

    monkeypatch.setattr(
        output_contract.os,
        "fdopen",
        lambda descriptor, _mode, *, closefd: RewritingReader(descriptor),
    )

    with pytest.raises(OutputIdentityError, match="changed"):
        artifact.read_bytes_verified(tmp_path)


def test_verified_open_preserves_caller_exception_during_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "result.txt"
    path.write_bytes(b"first")
    artifact = collect_outputs(
        (output_spec(ExactCollector(relative_path="result.txt")),),
        tmp_path,
        stdout=None,
    )["output"]
    assert isinstance(artifact, CollectedArtifact)

    with pytest.raises(RuntimeError, match="caller failed"):
        with artifact.open_verified(tmp_path):
            path.write_bytes(b"other")
            raise RuntimeError("caller failed")


def test_collected_directory_identity_detects_descendant_replacement(
    tmp_path: Path,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    child = tree / "child.txt"
    child.write_bytes(b"first")
    spec = OutputSpec(
        port_id="directory",
        artifact_type="artifact.directory",
        collector=DirectoryCollector(relative_path="tree", maximum_entries=5),
    )
    artifact = collect_outputs((spec,), tmp_path, stdout=None)["directory"]
    assert isinstance(artifact, CollectedArtifact)
    artifact.verify_identity(tmp_path)

    replacement = tree / "replacement.txt"
    replacement.write_bytes(b"other")
    replacement.replace(child)

    with pytest.raises(OutputIdentityError, match="changed"):
        artifact.verify_identity(tmp_path)


def test_directory_tree_is_deterministic_and_bounded(tmp_path: Path) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "z").mkdir()
    (tree / "z" / "b.txt").write_text("b", encoding="utf-8")
    (tree / "a.txt").write_text("a", encoding="utf-8")
    spec = OutputSpec(
        port_id="directory",
        artifact_type="artifact.directory",
        collector=DirectoryCollector(relative_path="tree", maximum_entries=3),
    )

    artifact = collect_outputs((spec,), tmp_path, stdout=None)["directory"]

    assert isinstance(artifact, CollectedArtifact)
    assert tuple(entry.relative_path for entry in artifact.entries) == (
        "tree/a.txt",
        "tree/z",
        "tree/z/b.txt",
    )

    too_small = spec.model_copy(
        update={
            "collector": DirectoryCollector(
                relative_path="tree",
                maximum_entries=2,
            )
        }
    )
    with pytest.raises(OutputCollectionError, match=r"directory.*maximum.*2"):
        collect_outputs((too_small,), tmp_path, stdout=None)


def test_directory_iteration_stops_at_entry_cap_plus_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    for index in range(8):
        (tree / f"entry-{index}.txt").write_text("value", encoding="utf-8")
    observed = instrument_scandir(monkeypatch)
    spec = OutputSpec(
        port_id="directory",
        artifact_type="artifact.directory",
        collector=DirectoryCollector(relative_path="tree", maximum_entries=2),
    )

    with pytest.raises(OutputCollectionError, match="maximum"):
        collect_outputs((spec,), tmp_path, stdout=None)

    assert len(observed) == 3


@pytest.mark.parametrize("unsafe_kind", ("symlink", "fifo"))
def test_directory_tree_rejects_unsafe_descendants(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    if unsafe_kind == "symlink":
        (tmp_path / "outside.txt").write_text("outside", encoding="utf-8")
        (tree / "unsafe").symlink_to(tmp_path / "outside.txt")
    else:
        os.mkfifo(tree / "unsafe")
    spec = OutputSpec(
        port_id="directory",
        artifact_type="artifact.directory",
        collector=DirectoryCollector(relative_path="tree", maximum_entries=5),
    )

    with pytest.raises(OutputCollectionError, match=unsafe_kind):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_collected_results_are_immutable_hashable_and_manifest_safe(
    tmp_path: Path,
) -> None:
    (tmp_path / "result.txt").write_text("value", encoding="utf-8")
    spec = output_spec(ExactCollector(relative_path="result.txt"))

    first = collect_outputs((spec,), tmp_path, stdout=None)
    second = collect_outputs((spec,), tmp_path, stdout=None)
    manifest = first.to_manifest()

    assert isinstance(first, CollectedOutputs)
    assert first == second
    assert hash(first) == hash(second)
    assert manifest["outputs"][0]["artifacts"][0]["relative_path"] == "result.txt"
    serialized = json.dumps(manifest, sort_keys=True)
    assert str(tmp_path) not in serialized
    assert "fd" not in serialized
    with pytest.raises(ValidationError, match="frozen_instance"):
        first.outputs = ()


def test_verified_open_context_closes_its_descriptor(tmp_path: Path) -> None:
    (tmp_path / "result.txt").write_bytes(b"value")
    artifact = collect_outputs(
        (output_spec(ExactCollector(relative_path="result.txt")),),
        tmp_path,
        stdout=None,
    )["output"]
    assert isinstance(artifact, CollectedArtifact)

    with artifact.open_verified(tmp_path) as opened:
        assert opened.read() == b"value"

    assert opened.closed


def test_collection_success_and_failure_paths_do_not_leak_descriptors(
    tmp_path: Path,
) -> None:
    (tmp_path / "result.txt").write_text("value", encoding="utf-8")
    exact = output_spec(ExactCollector(relative_path="result.txt"))
    invalid_stdout = output_spec(
        StdoutCollector(relative_path="stdout.json", maximum_bytes=64),
        validators=(JsonValidator(maximum_bytes=64),),
    )
    before = open_descriptor_count()

    for _ in range(16):
        collect_outputs((exact,), tmp_path, stdout=None)
        with pytest.raises(OutputCollectionError, match="JSON"):
            collect_outputs(
                (invalid_stdout,),
                tmp_path,
                stdout="{broken",
                stdout_truncated=False,
            )

    assert open_descriptor_count() == before
