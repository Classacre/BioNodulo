from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.ml_design_family import OpenvaccinePrepareNode


def _context(tmp_path: Path, name: str = "run") -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(node_dir=node_dir)


def _synthetic_json(path: Path) -> None:
    payload = {
        "index": [0, 1, 2],
        "ID": {"0": "ryos_1001", "1": "ryos_1002", "2": "ryos_1003"},
        "sequence": {
            "0": "ACGUACGUACGU",
            "1": "GGAAUUCCGGAAUUCC",
            "2": "UUUGGGCCC",
        },
        "seqpos": {"0": [0, 1, 2], "1": [0, 1, 2], "2": [0, 1]},
        "deg_Mg_pH10": {"0": [1.0, 1.0, 2.0], "1": [2.0, 4.0], "2": [0.5, None, 1.5]},
        "deg_pH10": {"0": [1.0, 0.0, 2.0], "1": [3.0, 3.0], "2": [1.0, 1.0]},
        "deg_Mg_50C": {"0": [0.5, 0.5, 0.5], "1": [1.0, 2.0], "2": [2.0, 2.0]},
        "deg_50C": {"0": [1.5, 1.5, 0.0], "1": [0.5, 0.5], "2": [3.0, None]},
        "split": {"0": "public_train", "1": "public_train", "2": "public_test"},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.asyncio
async def test_columnar_ryos_hand_math(tmp_path: Path) -> None:
    json_path = tmp_path / "ryos.json"
    _synthetic_json(json_path)
    node = OpenvaccinePrepareNode()
    molecules_path, summary_path = await node.run(
        json_path=str(json_path),
        arms="deg_Mg_pH10",
        context=_context(tmp_path),
    )

    with Path(molecules_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == 3
    assert [row["id"] for row in rows] == ["ryos_1001", "ryos_1002", "ryos_1003"]
    first, second, third = rows
    assert first["n_nt"] == "12" and first["n_measured"] == "3"
    assert float(first["k_deg"]) == pytest.approx(4.0 / 2)
    assert float(first["t_half"]) == pytest.approx(math.log(2.0) / 2.0, abs=1e-6)
    assert second["n_measured"] == "2"
    assert float(second["k_deg"]) == pytest.approx(6.0 / 1)
    assert float(second["t_half"]) == pytest.approx(math.log(2.0) / 6.0, abs=1e-6)
    assert third["n_measured"] == "2"
    assert float(third["k_deg"]) == pytest.approx(2.0 / 1)

    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["n_molecules"] == 3
    assert summary["arms"] == ["deg_Mg_pH10"]
    assert summary["per_arm"]["deg_Mg_pH10"]["n"] == 3
    assert summary["per_arm"]["deg_Mg_pH10"]["mean_k_deg"] == pytest.approx((2.0 + 6.0 + 2.0) / 3)
    assert "reactivity-like" in summary["proxy_note"]


@pytest.mark.asyncio
async def test_default_arms_four_rows_per_molecule(tmp_path: Path) -> None:
    json_path = tmp_path / "ryos.json"
    _synthetic_json(json_path)
    node = OpenvaccinePrepareNode()
    molecules_path, _ = await node.run(json_path=str(json_path), context=_context(tmp_path))
    with Path(molecules_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert len(rows) == 12
    assert {row["arm"] for row in rows} == {"deg_Mg_pH10", "deg_pH10", "deg_Mg_50C", "deg_50C"}


@pytest.mark.asyncio
async def test_missing_arm_arrays_skipped_and_counted(tmp_path: Path) -> None:
    json_path = tmp_path / "partial.json"
    payload = {
        "ID": {"0": "only_one"},
        "sequence": {"0": "ACGUACGUACGU"},
        "deg_Mg_pH10": {"0": [1.0, 1.0, 2.0]},
        "deg_pH10": {"0": None},
    }
    json_path.write_text(json.dumps(payload), encoding="utf-8")
    node = OpenvaccinePrepareNode()
    molecules_path, summary_path = await node.run(
        json_path=str(json_path),
        arms="deg_Mg_pH10,deg_pH10",
        context=_context(tmp_path),
    )
    with Path(molecules_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert [row["arm"] for row in rows] == ["deg_Mg_pH10"]
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["per_arm"]["deg_pH10"]["n"] == 0
    assert summary["per_arm"]["deg_pH10"]["n_missing"] == 1
    assert summary["per_arm"]["deg_Mg_pH10"]["n_missing"] == 0


@pytest.mark.asyncio
async def test_rdat_reactivity_blocks(tmp_path: Path) -> None:
    rdat = tmp_path / "react.rdat"
    rdat.write_text(
        "# RDAT2011 minimal\n"
        "ID: construct_A\n"
        "SEQUENCE: ACGUACGUACGU\n"
        "REACTIVITY: 1.0 1.0 2.0\n"
        "\n"
        "ID: construct_B\n"
        "SEQUENCE: GGGCCC\n"
        "REACTIVITY: NAN 3.0\n",
        encoding="utf-8",
    )
    node = OpenvaccinePrepareNode()
    molecules_path, summary_path = await node.run(
        rdat_path=str(rdat),
        arms="reactivity",
        context=_context(tmp_path),
    )
    with Path(molecules_path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    assert [row["id"] for row in rows] == ["construct_A", "construct_B"]
    assert float(rows[0]["k_deg"]) == pytest.approx(4.0 / 2)
    assert rows[1]["n_measured"] == "1"
    assert float(rows[1]["k_deg"]) == pytest.approx(3.0 / 1)
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    assert summary["arms"] == ["reactivity"]
    assert summary["n_molecules"] == 2


@pytest.mark.asyncio
async def test_input_presence_rules(tmp_path: Path) -> None:
    node = OpenvaccinePrepareNode()
    with pytest.raises(ValueError, match="exactly one"):
        await node.run(context=_context(tmp_path))
    json_path = tmp_path / "ryos.json"
    _synthetic_json(json_path)
    with pytest.raises(ValueError, match="exactly one"):
        await node.run(
            json_path=str(json_path),
            rdat_path=str(json_path),
            context=_context(tmp_path, "both"),
        )
    with pytest.raises(ValueError, match="not an existing file"):
        await node.run(json_path=str(tmp_path / "nope.json"), context=_context(tmp_path, "nope"))
