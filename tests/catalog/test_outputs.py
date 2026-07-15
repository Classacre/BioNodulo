import json
import os
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from bionodulo.nodes.contract.artifacts import ArtifactContainer, Cardinality
from bionodulo.nodes.contract.outputs import (
    CollectedArtifact,
    CollectedOutputs,
    ConditionalCollector,
    DirectoryCollector,
    ExactCollector,
    GlobCollector,
    JsonValidator,
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
