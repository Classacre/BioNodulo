from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.ml_design_family import CampaignConfigBuilderNode

CDS_A = "ATGGCCTTTAAACCCGGGTTT"
CDS_B = "ATGTTTGGGCCCAAATTTCCCGGG"


def _context(tmp_path: Path, name: str = "run") -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(node_dir=node_dir)


def _fasta(tmp_path: Path, name: str, sequence: str) -> str:
    path = tmp_path / f"{name}.fasta"
    path.write_text(f">{name} synthetic\n{sequence}\n", encoding="utf-8")
    return str(path)


@pytest.mark.asyncio
async def test_two_targets_two_seeds_make_four_ordered_rows(tmp_path: Path) -> None:
    fasta_a = _fasta(tmp_path, "egfp", CDS_A)
    fasta_b = _fasta(tmp_path, "luc", CDS_B)
    targets = f"egfp\t{fasta_a}\nluc\t{fasta_b}"
    node = CampaignConfigBuilderNode()

    pairs, pairs_jsonl, targets_jsonl, config_path, weights_path, ablations_jsonl = await node.run(
        targets=targets,
        seeds="13,101",
        iterations=5,
        batch_size=12,
        top_k=3,
        evaluator_weights='{"cai":2.0,"gc":1.0}',
        budget_usd=12.5,
        context=_context(tmp_path),
    )

    with Path(pairs).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert [row["pair_id"] for row in rows] == ["egfp__s13", "egfp__s101", "luc__s13", "luc__s101"]
    assert [row["seed"] for row in rows] == ["13", "101", "13", "101"]
    assert [row["target_id"] for row in rows] == ["egfp", "egfp", "luc", "luc"]
    assert rows[0]["cds_sequence"] == CDS_A
    assert rows[2]["cds_sequence"] == CDS_B

    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    assert config["n_pairs"] == 4
    assert config["iterations"] == 5
    assert config["batch_size"] == 12
    assert config["top_k"] == 3
    assert config["seeds"] == [13, 101]
    assert config["budget_usd"] == 12.5
    assert config["weights"] == {"cai": 2.0, "gc": 1.0}
    assert [meta["target_id"] for meta in config["targets_meta"]] == ["egfp", "luc"]
    assert config["targets_meta"][0]["n_codons"] == len(CDS_A) // 3

    assert json.loads(Path(weights_path).read_text(encoding="utf-8")) == {"cai": 2.0, "gc": 1.0}

    jsonl_rows = [json.loads(line) for line in Path(pairs_jsonl).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [row["pair_id"] for row in jsonl_rows] == [row["pair_id"] for row in rows]
    assert jsonl_rows[0]["cds_sequence"] == CDS_A
    assert json.loads(jsonl_rows[0]["weights_json"]) == {"scores_1": 2.0, "scores_3": 1.0}
    assert jsonl_rows[0]["model_path"] == ""
    target_rows = [json.loads(line) for line in Path(targets_jsonl).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [row["target_id"] for row in target_rows] == ["egfp", "luc"]
    assert Path(ablations_jsonl).read_text(encoding="utf-8") == ""


@pytest.mark.asyncio
async def test_semicolon_targets_and_defaults(tmp_path: Path) -> None:
    fasta = _fasta(tmp_path, "rbd", CDS_A)
    node = CampaignConfigBuilderNode()
    pairs, _, _, config_path, _, ablations_jsonl = await node.run(
        targets=f"rbd\t{fasta};",
        context=_context(tmp_path),
    )
    with Path(pairs).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == 5
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    assert config["seeds"] == [13, 101, 2024, 4242, 9001]
    assert config["iterations"] == 30
    assert config["weights"]["mirna"] == 1.0
    assert config["objective_ports"]["learned"] == "scores_6"
    assert config["ablations"] == []
    assert Path(ablations_jsonl).read_text(encoding="utf-8") == ""


@pytest.mark.asyncio
async def test_missing_fastas_all_listed(tmp_path: Path) -> None:
    fasta = _fasta(tmp_path, "present", CDS_A)
    node = CampaignConfigBuilderNode()
    with pytest.raises(ValueError) as excinfo:
        await node.run(
            targets=f"present\t{fasta}\ngoneA\tmissing_a.fasta\ngoneB\tmissing_b.fasta",
            context=_context(tmp_path),
        )
    message = str(excinfo.value)
    assert "missing_a.fasta" in message and "missing_b.fasta" in message


@pytest.mark.asyncio
async def test_bad_weights_rejected_clearly(tmp_path: Path) -> None:
    fasta = _fasta(tmp_path, "egfp", CDS_A)
    node = CampaignConfigBuilderNode()
    with pytest.raises(ValueError, match="evaluator_weights"):
        await node.run(targets=f"egfp\t{fasta}", evaluator_weights="{oops}", context=_context(tmp_path))
    with pytest.raises(ValueError, match="evaluator_weights"):
        await node.run(targets=f"egfp\t{fasta}", evaluator_weights="[1,2]", context=_context(tmp_path))
    with pytest.raises(ValueError, match="evaluator_weights"):
        await node.run(
            targets=f"egfp\t{fasta}",
            evaluator_weights='{"cai":"high"}',
            context=_context(tmp_path),
        )


@pytest.mark.asyncio
async def test_bad_targets_and_seeds_rejected(tmp_path: Path) -> None:
    node = CampaignConfigBuilderNode()
    with pytest.raises(ValueError, match="target_id<TAB>cds_fasta_path"):
        await node.run(targets="no_tab_here", context=_context(tmp_path))
    with pytest.raises(ValueError, match="duplicate target_id"):
        fasta = _fasta(tmp_path, "egfp", CDS_A)
        await node.run(
            targets=f"egfp\t{fasta}\negfp\t{fasta}",
            context=_context(tmp_path, "dup"),
        )
    with pytest.raises(ValueError, match="seeds"):
        await node.run(
            targets=f"egfp\t{fasta}",
            seeds="1,not_an_int",
            context=_context(tmp_path, "seeds"),
        )
    with pytest.raises(ValueError, match="multiple of three"):
        short = _fasta(tmp_path, "short", "ATGGGCC")
        await node.run(targets=f"short\t{short}", context=_context(tmp_path, "short"))


@pytest.mark.asyncio
async def test_ablations_annotate_and_jsonl_rows(tmp_path: Path) -> None:
    fasta = _fasta(tmp_path, "egfp", CDS_A)
    node = CampaignConfigBuilderNode()

    pairs, pairs_jsonl, targets_jsonl, config_path, weights_path, ablations_jsonl = await node.run(
        targets=f"egfp\t{fasta}",
        seeds="13",
        ablation_weights='no_immune\t{"immune":0.0}\nno_mirna\t{"mirna":0.0}',
        annotate_key="model_path",
        annotate_value=str(tmp_path / "model.json"),
        context=_context(tmp_path),
    )

    ablation_rows = [json.loads(line) for line in Path(ablations_jsonl).read_text(encoding="utf-8").splitlines()]
    assert [row["ablation"] for row in ablation_rows] == ["no_immune", "no_mirna"]
    no_immune = json.loads(ablation_rows[0]["evaluator_weights"])
    assert no_immune["immune"] == 0.0 and no_immune["mirna"] == 1.0
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    assert config["ablations"] == ["no_immune", "no_mirna"]

    row = json.loads(Path(pairs_jsonl).read_text(encoding="utf-8").splitlines()[0])
    assert row["model_path"] == str(tmp_path / "model.json")
    weights = json.loads(row["weights_json"])
    assert weights == {
        "scores_1": 1.0,
        "scores_2": 1.0,
        "scores_3": 1.0,
        "scores_4": 1.0,
        "scores_5": 1.0,
    }
    target_row = json.loads(Path(targets_jsonl).read_text(encoding="utf-8").splitlines()[0])
    assert target_row["model_path"] == str(tmp_path / "model.json")

    with pytest.raises(ValueError, match="ablation_weights"):
        await node.run(
            targets=f"egfp\t{fasta}",
            ablation_weights="bad\tnot json",
            context=_context(tmp_path, "bad-abl"),
        )
    validation = node.VALIDATE_INPUTS(
        {"targets": f"egfp\t{fasta}", "annotate_key": "model_path", "annotate_value": ""}
    )
    assert "annotate_value" in str(validation)
