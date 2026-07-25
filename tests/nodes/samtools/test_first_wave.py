from __future__ import annotations

import errno
import importlib
import os
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.base import BaseNode


NODES = {
    "samtools_view": ("view", "SamtoolsViewNode", "alignment", "input.sam", 4),
    "samtools_collate": ("collate", "SamtoolsCollateNode", "bam", "input.bam", 4),
    "samtools_fixmate": ("fixmate", "SamtoolsFixmateNode", "bam", "input.bam", 4),
    "samtools_sort": ("sort", "SamtoolsSortNode", "alignment", "input.sam", 4),
    "samtools_markdup": ("markdup", "SamtoolsMarkdupNode", "bam", "input.bam", 4),
    "samtools_index": ("index", "SamtoolsIndexNode", "bam", "input.bam", 2),
    "samtools_flagstat": ("flagstat", "SamtoolsFlagstatNode", "bam", "input.bam", 2),
}


THREADS_4 = ("INT", {"default": 4, "min": 1, "max": 64})
THREADS_2 = ("INT", {"default": 2, "min": 1, "max": 64})
ALLOWED_LINK_FALLBACK_ERRORS = tuple(
    (name, getattr(errno, name))
    for name in ("EXDEV", "ENOTSUP", "EOPNOTSUPP", "ENOSYS", "EPERM")
    if hasattr(errno, name)
)
PROPAGATED_LINK_ERRORS = (("EACCES", errno.EACCES), ("EIO", errno.EIO))


EXPECTED_INPUT_TYPES = {
    "samtools_view": {
        "required": {
            "alignment": (("SAM", "BAM"), {"description": "Input SAM or BAM alignment file"}),
            "threads": THREADS_4,
        },
        "optional": {
            "require_all_flags": ("INT", {"default": None}),
            "exclude_any_flags": ("INT", {"default": None}),
        },
        "hidden": {"output": ("STRING", {})},
    },
    "samtools_collate": {
        "required": {
            "bam": ("BAM", {"description": "Input BAM file"}),
            "threads": THREADS_4,
        },
        "optional": {},
        "hidden": {"output": ("STRING", {})},
    },
    "samtools_fixmate": {
        "required": {
            "bam": ("BAM", {"description": "Name-collated BAM from samtools collate"}),
            "threads": THREADS_4,
        },
        "optional": {
            "add_markdup_tags": ("BOOLEAN", {"default": False}),
            "remove_secondary_unmapped": ("BOOLEAN", {"default": False}),
        },
        "hidden": {"output": ("STRING", {})},
    },
    "samtools_sort": {
        "required": {
            "alignment": (("SAM", "BAM"), {"description": "Input SAM or BAM alignment file"}),
            "threads": THREADS_4,
        },
        "optional": {
            "memory_per_thread": ("STRING", {"default": "768M"}),
        },
        "hidden": {"output": ("STRING", {})},
    },
    "samtools_markdup": {
        "required": {
            "bam": (
                "BAM",
                {"description": "Coordinate-sorted BAM prepared with samtools fixmate -m"},
            ),
            "threads": THREADS_4,
        },
        "optional": {
            "remove_duplicates": ("BOOLEAN", {"default": False}),
            "mark_supplementary": ("BOOLEAN", {"default": False}),
            "optical_distance": ("INT", {"default": 0, "min": 0}),
            "read_coords": ("STRING", {"default": ""}),
            "clear_existing": ("BOOLEAN", {"default": False}),
        },
        "hidden": {"output": ("STRING", {})},
    },
    "samtools_index": {
        "required": {
            "bam": ("BAM", {"description": "Coordinate-sorted BAM file to index"}),
            "threads": THREADS_2,
        },
        "optional": {},
        "hidden": {"output": ("STRING", {})},
    },
    "samtools_flagstat": {
        "required": {
            "bam": ("BAM", {"description": "Input BAM file"}),
            "threads": THREADS_2,
        },
        "optional": {},
        "hidden": {"output": ("STRING", {})},
    },
}


OUTPUT_CONTRACTS = {
    "samtools_view": (("BAM",), ("bam",), ("bam.bam",)),
    "samtools_collate": (("BAM",), ("name_collated_bam",), ("name_collated_bam.bam",)),
    "samtools_fixmate": (("BAM",), ("fixmate_bam",), ("fixmate_bam.bam",)),
    "samtools_sort": (("BAM",), ("sorted_bam",), ("sorted_bam.bam",)),
    "samtools_markdup": (
        ("BAM", "STATS_FILE"),
        ("marked_bam", "duplicate_stats"),
        ("marked_bam.bam", "duplicate_stats.stats.txt"),
    ),
    "samtools_index": (
        ("BAM", "BAI"),
        ("indexed_bam", "bai"),
        ("indexed_bam.bam", "indexed_bam.bam.bai"),
    ),
    "samtools_flagstat": (("STATS_FILE",), ("stats",), ("stats.stats.txt",)),
}


def _node(node_id: str) -> type[BaseNode]:
    operation, class_name, _input_name, _input_path, _threads = NODES[node_id]
    module = importlib.import_module(f"bionodulo.nodes.builtin.samtools_family.{operation}")
    return getattr(module, class_name)


def _valid_inputs(node_id: str, **updates: Any) -> dict[str, Any]:
    _operation, _class_name, input_name, input_path, threads = NODES[node_id]
    inputs: dict[str, Any] = {input_name: input_path, "threads": threads}
    inputs.update(updates)
    return inputs


@pytest.mark.parametrize("node_id", tuple(NODES))
def test_input_types_are_exact(node_id: str) -> None:
    assert _node(node_id).INPUT_TYPES() == EXPECTED_INPUT_TYPES[node_id]


@pytest.mark.parametrize("node_id", tuple(NODES))
def test_return_contract_and_fixed_output_paths_are_exact(node_id: str, tmp_path: Path) -> None:
    node = _node(node_id)
    return_types, return_names, filenames = OUTPUT_CONTRACTS[node_id]

    assert node.RETURN_TYPES == return_types
    assert node.RETURN_NAMES == return_names
    assert node.OUTPUT_FILENAMES == filenames
    assert node.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / node_id / name for name in filenames]


@pytest.mark.parametrize("node_id", tuple(NODES))
def test_default_argv_is_exact(node_id: str, tmp_path: Path) -> None:
    node = _node(node_id)
    _operation, _class_name, input_name, input_path, _threads = NODES[node_id]
    node_output = tmp_path / node_id
    output_paths = [node_output / filename for filename in OUTPUT_CONTRACTS[node_id][2]]
    command_inputs = {input_name: input_path, "output": str(node_output)}
    if node_id == "samtools_index":
        source = tmp_path / input_path
        source.write_bytes(b"BAM payload")
        command_inputs[input_name] = str(source)
        node.PREPARE_EXECUTION(command_inputs, output_paths)
        input_path = str(output_paths[0])
    expected_by_node = {
        "samtools_view": [
            "samtools", "view", "-b", "-@", "4", "-o", str(output_paths[0]), input_path,
        ],
        "samtools_collate": [
            "samtools", "collate", "-@", "4", "-T", str(node_output / "tmp"),
            "-o", str(output_paths[0]), input_path,
        ],
        "samtools_fixmate": [
            "samtools", "fixmate", "-@", "4", input_path, str(output_paths[0]),
        ],
        "samtools_sort": [
            "samtools", "sort", "-@", "4", "-m", "768M", "-T", str(node_output / "tmp"),
            "-o", str(output_paths[0]), input_path,
        ],
        "samtools_markdup": [
            "samtools", "markdup", "-@", "4", "-f", str(node_output / "duplicate_stats.stats.txt"),
            input_path, str(output_paths[0]),
        ],
        "samtools_flagstat": ["samtools", "flagstat", "-@", "2", input_path],
    }
    if node_id == "samtools_index":
        expected = [
            "samtools", "index", "-@", "2", "-b", "-o", str(output_paths[1]), input_path,
        ]
    else:
        expected = expected_by_node[node_id]

    assert node.render_command(command_inputs) == expected


def test_index_prepares_colocated_bam_as_hard_link(tmp_path: Path) -> None:
    node = _node("samtools_index")
    source = tmp_path / "source alignment.bam"
    source.write_bytes(b"coordinate-sorted BAM")
    outputs = node.PLAN_OUTPUTS({}, tmp_path)
    inputs = {"bam": source, "threads": 2, "output": str(outputs[0].parent)}

    node.PREPARE_EXECUTION(inputs, outputs)

    assert outputs[0].read_bytes() == source.read_bytes()
    assert os.path.samefile(source, outputs[0])
    assert inputs["bam"] == str(outputs[0])
    assert outputs[1] == Path(f"{outputs[0]}.bai")
    assert node.render_command(inputs) == [
        "samtools",
        "index",
        "-@",
        "2",
        "-b",
        "-o",
        str(outputs[1]),
        str(outputs[0]),
    ]


@pytest.mark.parametrize(
    ("errno_name", "errno_value"),
    ALLOWED_LINK_FALLBACK_ERRORS,
    ids=[name for name, _value in ALLOWED_LINK_FALLBACK_ERRORS],
)
def test_index_copies_for_supported_hard_link_fallback_errors(
    errno_name: str,
    errno_value: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_module = importlib.import_module("bionodulo.nodes.builtin.samtools_family.index")
    node = index_module.SamtoolsIndexNode
    source = tmp_path / "source.bam"
    source.write_bytes(b"copy fallback")
    outputs = node.PLAN_OUTPUTS({}, tmp_path)

    def raise_link_error(_source: Path, _destination: Path) -> None:
        raise OSError(errno_value, errno_name)

    monkeypatch.setattr(index_module.os, "link", raise_link_error)
    inputs = {"bam": source, "threads": 2}

    node.PREPARE_EXECUTION(inputs, outputs)

    assert outputs[0].read_bytes() == source.read_bytes()
    assert not os.path.samefile(source, outputs[0])
    assert inputs["bam"] == str(outputs[0])


@pytest.mark.parametrize(
    ("errno_name", "errno_value"),
    PROPAGATED_LINK_ERRORS,
    ids=[name for name, _value in PROPAGATED_LINK_ERRORS],
)
def test_index_propagates_disallowed_hard_link_errors(
    errno_name: str,
    errno_value: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_module = importlib.import_module("bionodulo.nodes.builtin.samtools_family.index")
    node = index_module.SamtoolsIndexNode
    source = tmp_path / "source.bam"
    source.write_bytes(b"input")
    outputs = node.PLAN_OUTPUTS({}, tmp_path)

    def raise_link_error(_source: Path, _destination: Path) -> None:
        raise OSError(errno_value, errno_name)

    monkeypatch.setattr(index_module.os, "link", raise_link_error)

    with pytest.raises(OSError, match=errno_name):
        node.PREPARE_EXECUTION({"bam": source, "threads": 2}, outputs)


def test_index_does_not_replace_a_lexically_identical_source(tmp_path: Path) -> None:
    node = _node("samtools_index")
    source = tmp_path / "indexed_bam.bam"
    source.write_bytes(b"same path")
    inputs = {"bam": source, "threads": 2}

    node.PREPARE_EXECUTION(inputs, [source, Path(f"{source}.bai")])

    assert source.read_bytes() == b"same path"
    assert inputs["bam"] == str(source)


def test_index_does_not_replace_source_reached_through_output_alias(tmp_path: Path) -> None:
    real_output = tmp_path / "output directory"
    staged_bam = real_output / "samtools_index" / "indexed_bam.bam"
    staged_bam.parent.mkdir(parents=True)
    staged_bam.write_bytes(b"same file through alias")
    alias_output = tmp_path / "output_alias"
    alias_output.symlink_to(real_output, target_is_directory=True)
    aliased_bam = alias_output / "samtools_index" / "indexed_bam.bam"
    inputs = {"bam": staged_bam, "threads": 2}

    _node("samtools_index").PREPARE_EXECUTION(
        inputs,
        [aliased_bam, Path(f"{aliased_bam}.bai")],
    )

    assert staged_bam.read_bytes() == b"same file through alias"
    assert inputs["bam"] == str(aliased_bam)


def test_index_replaces_staged_leaf_symlink_with_regular_hard_link(tmp_path: Path) -> None:
    source = tmp_path / "source.bam"
    source.write_bytes(b"staged BAM contents")
    staged_bam = tmp_path / "samtools_index" / "indexed_bam.bam"
    staged_bam.parent.mkdir(parents=True)
    staged_bam.symlink_to(source)
    inputs = {"bam": source, "threads": 2}

    _node("samtools_index").PREPARE_EXECUTION(
        inputs,
        [staged_bam, Path(f"{staged_bam}.bai")],
    )

    assert staged_bam.exists()
    assert not staged_bam.is_symlink()
    assert staged_bam.read_bytes() == source.read_bytes()
    assert os.path.samefile(source, staged_bam)
    assert inputs["bam"] == str(staged_bam)


@pytest.mark.asyncio
async def test_index_fake_execution_returns_stable_bam_and_bai_paths(tmp_path: Path) -> None:
    node = _node("samtools_index")
    source = tmp_path / "source.bam"
    source.write_bytes(b"indexed input")
    output_dir = tmp_path / "output directory with spaces"

    class IndexContext:
        def __init__(self) -> None:
            self.node_dir = output_dir
            self.command: list[str] | None = None

        async def run_command(self, cmd: str | list[str], **_kwargs: Any) -> dict[str, Any]:
            assert isinstance(cmd, list)
            self.command = cmd
            staged_bam = Path(cmd[-1])
            bai = Path(cmd[-2])
            assert staged_bam.exists()
            assert os.path.samefile(source, staged_bam)
            bai.write_bytes(b"BAI")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = IndexContext()

    result = await node().run(
        bam=source,
        threads=2,
        context=context,
        output_dir=output_dir,
    )

    stable_bam = output_dir / "samtools_index" / "indexed_bam.bam"
    stable_bai = Path(f"{stable_bam}.bai")
    assert context.command == [
        "samtools",
        "index",
        "-@",
        "2",
        "-b",
        "-o",
        context.command[-2],
        context.command[-1],
    ]
    assert " " not in context.command[-2]
    assert " " not in context.command[-1]
    assert Path(context.command[-2]) == Path(f"{context.command[-1]}.bai")
    assert stable_bam.exists()
    assert stable_bai.read_bytes() == b"BAI"
    assert os.path.samefile(source, stable_bam)
    assert result == (str(stable_bam), str(stable_bai))


def test_view_option_argv_order_is_exact(tmp_path: Path) -> None:
    node = _node("samtools_view")
    output = tmp_path / node.NODE_ID

    assert node.render_command(
        {
            "alignment": "input.bam",
            "threads": 7,
            "require_all_flags": 3,
            "exclude_any_flags": 12,
            "output": str(output),
        }
    ) == [
        "samtools", "view", "-b", "-@", "7", "-f", "3", "-F", "12",
        "-o", str(output / "bam.bam"), "input.bam",
    ]


def test_fixmate_option_argv_order_is_exact(tmp_path: Path) -> None:
    node = _node("samtools_fixmate")
    output = tmp_path / node.NODE_ID

    assert node.render_command(
        {
            "bam": "input.bam",
            "threads": 6,
            "add_markdup_tags": True,
            "remove_secondary_unmapped": True,
            "output": str(output),
        }
    ) == [
        "samtools", "fixmate", "-@", "6", "-m", "-r",
        "input.bam", str(output / "fixmate_bam.bam"),
    ]


def test_markdup_option_argv_order_is_exact(tmp_path: Path) -> None:
    node = _node("samtools_markdup")
    output = tmp_path / node.NODE_ID

    assert node.render_command(
        {
            "bam": "input.bam",
            "threads": 8,
            "remove_duplicates": True,
            "mark_supplementary": True,
            "optical_distance": 2500,
            "read_coords": r"^([^:]+):([0-9]+):([0-9]+)$",
            "clear_existing": True,
            "output": str(output),
        }
    ) == [
        "samtools", "markdup", "-@", "8", "-r", "-S", "-d", "2500",
        "--read-coords", r"^([^:]+):([0-9]+):([0-9]+)$", "-c",
        "-f", str(output / "duplicate_stats.stats.txt"),
        "input.bam", str(output / "marked_bam.bam"),
    ]


@pytest.mark.parametrize("node_id", tuple(NODES))
@pytest.mark.parametrize("invalid_value", [None, "", "   ", 42])
def test_required_file_inputs_reject_missing_empty_and_non_path_values(
    node_id: str,
    invalid_value: Any,
) -> None:
    node = _node(node_id)
    _operation, _class_name, input_name, _input_path, threads = NODES[node_id]

    result = node.VALIDATE_INPUTS({input_name: invalid_value, "threads": threads})

    assert result is not True
    assert input_name in str(result)


@pytest.mark.parametrize("node_id", tuple(NODES))
def test_required_file_inputs_accept_pathlike_values(node_id: str) -> None:
    node = _node(node_id)
    _operation, _class_name, input_name, _input_path, threads = NODES[node_id]

    assert node.VALIDATE_INPUTS({input_name: Path("input.bam"), "threads": threads}) is True


@pytest.mark.parametrize("node_id", tuple(NODES))
@pytest.mark.parametrize("invalid_threads", [True, 1.5, "4", 0, 65])
def test_threads_reject_non_integer_boolean_and_out_of_range_values(
    node_id: str,
    invalid_threads: Any,
) -> None:
    node = _node(node_id)
    inputs = _valid_inputs(node_id, threads=invalid_threads)

    result = node.VALIDATE_INPUTS(inputs)

    assert result is not True
    assert "threads" in str(result)


@pytest.mark.parametrize("node_id", tuple(NODES))
@pytest.mark.parametrize("threads", [1, 64])
def test_threads_accept_range_boundaries(node_id: str, threads: int) -> None:
    node = _node(node_id)

    assert node.VALIDATE_INPUTS(_valid_inputs(node_id, threads=threads)) is True


def test_adapter_calls_base_validation_before_operation_checks() -> None:
    markdup = _node("samtools_markdup")

    assert markdup.VALIDATE_INPUTS({"threads": 4, "optical_distance": -1}) == (
        "Required input 'bam' is missing"
    )
    assert markdup.VALIDATE_INPUTS(
        _valid_inputs("samtools_markdup", remove_duplicates="yes", optical_distance=-1)
    ) == "Input 'remove_duplicates' must be a boolean"


@pytest.mark.parametrize("mask_name", ["require_all_flags", "exclude_any_flags"])
@pytest.mark.parametrize("invalid_mask", [True, -1, 65536, 1.5, "1"])
def test_view_masks_reject_boolean_non_integer_and_out_of_range_values(
    mask_name: str,
    invalid_mask: Any,
) -> None:
    view = _node("samtools_view")

    result = view.VALIDATE_INPUTS(_valid_inputs("samtools_view", **{mask_name: invalid_mask}))

    assert result is not True
    assert mask_name in str(result)


@pytest.mark.parametrize("mask_name", ["require_all_flags", "exclude_any_flags"])
@pytest.mark.parametrize("mask", [None, 0, 65535])
def test_view_masks_accept_none_and_range_boundaries(mask_name: str, mask: int | None) -> None:
    view = _node("samtools_view")

    assert view.VALIDATE_INPUTS(_valid_inputs("samtools_view", **{mask_name: mask})) is True


@pytest.mark.parametrize(
    "invalid_memory",
    ["", "1.5M", "-1M", "1m", "1MB", "1048575", "1023K", "0G", " 1M", "1M ", "１M"],
)
def test_sort_memory_rejects_invalid_grammar_and_values_below_one_mib(
    invalid_memory: str,
) -> None:
    sort = _node("samtools_sort")

    result = sort.VALIDATE_INPUTS(
        _valid_inputs("samtools_sort", memory_per_thread=invalid_memory)
    )

    assert result is not True
    assert "memory_per_thread" in str(result)


@pytest.mark.parametrize("memory", ["1048576", "1M", "1024K", "1G", "0001048576"])
def test_sort_memory_accepts_documented_grammar_at_or_above_one_mib(memory: str) -> None:
    sort = _node("samtools_sort")

    assert sort.VALIDATE_INPUTS(
        _valid_inputs("samtools_sort", memory_per_thread=memory)
    ) is True


@pytest.mark.parametrize("invalid_distance", [True, -1, 1.5, "1"])
def test_markdup_optical_distance_rejects_boolean_non_integer_and_negative_values(
    invalid_distance: Any,
) -> None:
    markdup = _node("samtools_markdup")

    result = markdup.VALIDATE_INPUTS(
        _valid_inputs("samtools_markdup", optical_distance=invalid_distance)
    )

    assert result is not True
    assert "optical_distance" in str(result)


def test_markdup_read_coords_requires_positive_optical_distance() -> None:
    markdup = _node("samtools_markdup")

    result = markdup.VALIDATE_INPUTS(
        _valid_inputs("samtools_markdup", optical_distance=0, read_coords="regex")
    )

    assert result is not True
    assert "read_coords" in str(result)
    assert markdup.VALIDATE_INPUTS(
        _valid_inputs("samtools_markdup", optical_distance=1, read_coords="regex")
    ) is True


def test_flagstat_declares_stdout_output_without_shell_redirection(tmp_path: Path) -> None:
    flagstat = _node("samtools_flagstat")
    command = flagstat.render_command(
        {"bam": "input.bam", "threads": 2, "output": str(tmp_path / flagstat.NODE_ID)}
    )

    assert flagstat.STDOUT_OUTPUT_INDEX == 0
    assert flagstat.SHELL is False
    assert isinstance(command, list)
    assert command == ["samtools", "flagstat", "-@", "2", "input.bam"]
    assert ">" not in command
