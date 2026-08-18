from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.ml_design_family import PairedStatsNode


def _context(tmp_path: Path) -> SimpleNamespace:
    node_dir = tmp_path / "run"
    node_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(node_dir=node_dir)


async def _run(node: PairedStatsNode, tmp_path: Path, **kwargs: object) -> dict[str, object]:
    stats_path = await node.run(context=_context(tmp_path), **kwargs)
    return json.loads(Path(stats_path[0]).read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_exact_wilcoxon_matches_hand_enumeration(tmp_path: Path) -> None:
    node = PairedStatsNode()
    payload = await _run(node, tmp_path, values_a="1,2,3,4,5", values_b="0,0,0,0,0")
    assert payload["statistic"] == pytest.approx(15.0)
    assert payload["p_value"] == pytest.approx(2 / 32)
    assert payload["exact"] is True
    assert payload["n_nonzero_diffs"] == 5

    greater = await _run(
        node,
        tmp_path / "g",
        values_a="1,2,3,4,5",
        values_b="0,0,0,0,0",
        alternative="greater",
    )
    assert greater["p_value"] == pytest.approx(1 / 32)

    less = await _run(
        node,
        tmp_path / "l",
        values_a="0,0,0,0,0",
        values_b="1,2,3,4,5",
        alternative="greater",
    )
    assert less["statistic"] == pytest.approx(0.0)
    assert less["p_value"] == pytest.approx(1.0)
    mirrored = await _run(
        node,
        tmp_path / "m",
        values_a="0,0,0,0,0",
        values_b="1,2,3,4,5",
        alternative="less",
    )
    assert mirrored["p_value"] == pytest.approx(1 / 32)


@pytest.mark.asyncio
async def test_wilcoxon_drops_zero_diffs(tmp_path: Path) -> None:
    node = PairedStatsNode()
    payload = await _run(
        node,
        tmp_path,
        values_a=json.dumps([1.0, 5.0, 5.0, 5.0, 5.0]),
        values_b=json.dumps([1.0, 4.0, 4.0, 4.0, 4.0]),
    )
    assert payload["n_nonzero_diffs"] == 4
    assert payload["statistic"] == pytest.approx(10.0)
    assert payload["p_value"] == pytest.approx(2 / 16)
    assert payload["mean_diff"] == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_wilcoxon_normal_approximation_beyond_exact_cap(tmp_path: Path) -> None:
    node = PairedStatsNode()
    values_a = ",".join(str(index) for index in range(1, 23))
    payload = await _run(node, tmp_path, values_a=values_a, values_b="0" * 1 + ",0" * 21)
    assert payload["exact"] is False
    assert payload["n_nonzero_diffs"] == 22
    assert payload["statistic"] == pytest.approx(253.0)
    assert 0.0 < payload["p_value"] < 0.001


@pytest.mark.asyncio
async def test_paired_t_against_known_example(tmp_path: Path) -> None:
    node = PairedStatsNode()
    payload = await _run(
        node,
        tmp_path,
        values_a="5,6,7,8,10",
        values_b="4,6,6,9,9",
        test="paired_t",
    )
    assert payload["statistic"] == pytest.approx(1.0)
    assert payload["p_value"] == pytest.approx(0.37390, abs=2e-5)
    assert payload["effect_mean_a"] == pytest.approx(7.2)
    assert payload["effect_mean_b"] == pytest.approx(6.8)
    assert payload["mean_diff"] == pytest.approx(0.4)
    assert payload["ci95_low"] <= 0.4 <= payload["ci95_high"]
    assert payload["significant"] is False

    one_sided = await _run(
        node,
        tmp_path / "os",
        values_a="5,6,7,8,10",
        values_b="4,6,6,9,9",
        test="paired_t",
        alternative="greater",
    )
    assert one_sided["p_value"] == pytest.approx(0.37390 / 2, abs=2e-5)


@pytest.mark.asyncio
async def test_spearman_perfect_correlation(tmp_path: Path) -> None:
    node = PairedStatsNode()
    payload = await _run(
        node,
        tmp_path,
        values_a="1,2,3,4",
        values_b="10,20,30,40",
        test="spearman",
    )
    assert payload["statistic"] == pytest.approx(1.0)
    assert payload["p_value"] == 0.0

    inverted = await _run(
        node,
        tmp_path / "inv",
        values_a="1,2,3,4",
        values_b="40,30,20,10",
        test="spearman",
    )
    assert inverted["statistic"] == pytest.approx(-1.0)
    assert inverted["p_value"] == 0.0


@pytest.mark.asyncio
async def test_tsv_column_input_and_length_mismatch(tmp_path: Path) -> None:
    table = tmp_path / "scores.tsv"
    table.write_text(
        "id\tscore_a\tscore_b\nE1\t1.0\t3.0\nE2\t2.0\t1.0\nE3\t3.0\t4.0\nE4\t4.0\t2.0\n",
        encoding="utf-8",
    )
    node = PairedStatsNode()
    payload = await _run(
        node,
        tmp_path,
        values_a=f"{table}:score_a",
        values_b=f"{table}:score_b",
        test="spearman",
    )
    assert payload["statistic"] == pytest.approx(0.0)
    assert payload["p_value"] == pytest.approx(1.0)

    with pytest.raises(ValueError, match="equal length"):
        await _run(node, tmp_path / "m", values_a="1,2,3", values_b="1,2")
    with pytest.raises(ValueError, match="values_a"):
        await _run(node, tmp_path / "n", values_a="1,x,3", values_b="1,2,3")


@pytest.mark.asyncio
async def test_bootstrap_ci_deterministic(tmp_path: Path) -> None:
    node = PairedStatsNode()
    first = await _run(node, tmp_path, values_a="5,6,7,8,10", values_b="4,6,6,9,9")
    second = await _run(node, tmp_path / "again", values_a="5,6,7,8,10", values_b="4,6,6,9,9")
    assert first["ci95_low"] == second["ci95_low"]
    assert first["ci95_high"] == second["ci95_high"]
    assert first["ci95_low"] < first["ci95_high"]
