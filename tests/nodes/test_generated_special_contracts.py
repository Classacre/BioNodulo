"""Regression checks for CLI help cases with nonstandard inputs or outputs."""

import pytest

from bionodulo.nodes.builtin.seqfu_family.seqfu_amplicheck import SeqfuAmplicheckNode
from bionodulo.nodes.builtin.seqfu_family.seqfu_lanes import SeqfuLanesNode
from bionodulo.nodes.builtin.seqfu_family.seqfu_subtract import SeqfuSubtractNode
from bionodulo.nodes.builtin.seqkit_family.seqkit_pair import SeqkitPairNode
from bionodulo.nodes.builtin.seqkit_family.seqkit_split import SeqkitSplitNode
from bionodulo.nodes.builtin.taxonkit_family.taxonkit_list import TaxonkitListNode
from bionodulo.nodes.builtin.unikmer_family.unikmer_grep import UnikmerGrepNode


@pytest.mark.parametrize(
    ("node", "inputs", "expected"),
    [
        (SeqfuAmplicheckNode, {"read1": "r1.fq", "read2": "r2.fq"},
         ["--outdir", "runs/seqfu_amplicheck", "r1.fq", "r2.fq"]),
        (SeqfuLanesNode, {"input_dir": "lanes"},
         ["--outdir", "runs/seqfu_lanes", "lanes"]),
        (SeqkitPairNode, {"read1": "r1.fq", "read2": "r2.fq"},
         ["--out-dir", "runs/seqkit_pair", "--read1", "r1.fq", "--read2", "r2.fq"]),
        (SeqkitSplitNode, {"sequence": "reads.fq"},
         ["--out-dir", "runs/seqkit_split", "reads.fq"]),
        (UnikmerGrepNode, {"input": "reads.unik", "query": "ACG"},
         ["--out-dir", "runs/unikmer_grep", "--out-prefix",
          "runs/unikmer_grep/output", "reads.unik"]),
    ],
)
def test_directory_commands_use_planned_directory(node, inputs, expected, tmp_path):
    outputs = node.PLAN_OUTPUTS(inputs, tmp_path / "runs")
    assert len(outputs) == 1
    assert outputs[0].is_dir()
    command = node.render_command({**inputs, "output": outputs[0]})
    assert command[-len(expected):] == [str(tmp_path / item) if item.startswith("runs/")
                                        else item for item in expected]
    with pytest.raises(RuntimeError, match="produced no files"):
        node.VERIFY_OUTPUTS(inputs, outputs)
    (outputs[0] / "result.txt").write_text("result")
    node.VERIFY_OUTPUTS(inputs, outputs)


def test_subtract_requires_two_file_ports():
    assert set(SeqfuSubtractNode.INPUT_TYPES()["required"]) == {"file1", "file2"}
    assert SeqfuSubtractNode.render_command({"file1": "a.fq", "file2": "b.fq"})[-2:] == [
        "a.fq", "b.fq",
    ]


def test_amplicheck_exposes_mixed_case_sweep_flags():
    optional = SeqfuAmplicheckNode.INPUT_TYPES()["optional"]
    assert "truncLen_grid" in optional and "maxEE_grid" in optional
    command = SeqfuAmplicheckNode.render_command({
        "read1": "r1.fq", "read2": "r2.fq", "truncLen_grid": "200,250",
    })
    assert ["--truncLen-grid", "200,250"] == command[command.index("--truncLen-grid"):][:2]


def test_taxonkit_container_home_is_not_a_ui_default():
    data_dir = TaxonkitListNode.INPUT_TYPES()["optional"]["data_dir"]
    assert "default" not in data_dir[1]
    command = TaxonkitListNode.render_command({
        "input": "taxids.txt", "data_dir": "taxdump", "output": "out",
    })
    assert command[command.index("--data-dir") + 1] == "taxdump"
