from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.single_cell_spatial_family.squidpy_qc import SquidpyQCNode


PINNED_REQUIRED_FILES = (
    "filtered_feature_bc_matrix.h5",
    "spatial/scalefactors_json.json",
    "spatial/tissue_hires_image.png",
    "spatial/tissue_lowres_image.png",
)
PINNED_POSITION_FILES = (
    "spatial/tissue_positions.csv",
    "spatial/tissue_positions_list.csv",
)


def _materialize_visium(root: Path, *, positions_name: str = "tissue_positions.csv") -> Path:
    root.mkdir(parents=True)
    for relative in SquidpyQCNode.VISIUM_REQUIRED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic")
    positions = root / "spatial" / positions_name
    positions.write_bytes(b"synthetic")
    return root


def _outputs(root: Path) -> list[Path]:
    return [root / "adata.h5ad", root / "spatial_plot.png"]


def test_visium_preflight_pins_squidpy_1_8_2_sibling_set() -> None:
    assert SquidpyQCNode.VISIUM_REQUIRED_FILES == PINNED_REQUIRED_FILES
    assert SquidpyQCNode.VISIUM_POSITION_FILES == PINNED_POSITION_FILES


@pytest.mark.parametrize("positions_name", ["tissue_positions.csv", "tissue_positions_list.csv"])
def test_visium_preflight_accepts_both_pinned_position_filenames(
    tmp_path: Path,
    positions_name: str,
) -> None:
    visium = _materialize_visium(tmp_path / "visium", positions_name=positions_name)

    SquidpyQCNode.PREPARE_EXECUTION(
        {"visium_path": str(visium)},
        _outputs(tmp_path / "run"),
    )


def test_visium_preflight_rejects_missing_hires_image(tmp_path: Path) -> None:
    visium = _materialize_visium(tmp_path / "visium")
    (visium / "spatial/tissue_hires_image.png").unlink()

    with pytest.raises(ValueError, match="spatial/tissue_hires_image.png"):
        SquidpyQCNode.PREPARE_EXECUTION(
            {"visium_path": str(visium)},
            _outputs(tmp_path / "run"),
        )


def test_visium_preflight_requires_one_position_file(tmp_path: Path) -> None:
    visium = _materialize_visium(tmp_path / "visium")
    (visium / "spatial/tissue_positions.csv").unlink()

    with pytest.raises(ValueError, match="tissue_positions.csv or spatial/tissue_positions_list.csv"):
        SquidpyQCNode.PREPARE_EXECUTION(
            {"visium_path": str(visium)},
            _outputs(tmp_path / "run"),
        )
