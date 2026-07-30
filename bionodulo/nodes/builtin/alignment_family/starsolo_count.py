"""STARsolo droplet single-cell quantification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .star_adapter import STAR_INDEX_MARKERS, STARCommandNode, path_value


class STARsoloCountNode(STARCommandNode):
    """Quantify droplet single-cell reads into a barcode x feature matrix.

    This exists because Cell Ranger cannot be used in an automated pipeline:
    10x Genomics distributes it under a click-through licence, so the download
    URL answers 403 to any unattended fetch and no conda channel may
    redistribute it. STARsolo is the maintained open equivalent, lives in the
    same STAR binary already used for bulk alignment, and emits the same
    Matrix-Market triple that Scanpy reads.

    Barcode geometry is explicit rather than auto-detected: 10x v2 is 16 bp CB +
    10 bp UMI, v3 is 16 bp CB + 12 bp UMI, and guessing wrong yields an
    all-empty matrix rather than an error.
    """

    NODE_ID = "starsolo_count"
    DISPLAY_NAME = "STARsolo Count"
    CATEGORY = "single_cell"
    DESCRIPTION = "Quantify droplet single-cell reads into a barcode x feature matrix with STARsolo."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "STARsolo",
        "single cell",
        "10x",
        "count matrix",
        "droplet",
        "cellranger alternative",
    ]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY", "TXT")
    RETURN_NAMES = ("filtered_matrix", "raw_matrix", "log_final")
    #: The Cell Ranger v3 layout, which is what `scanpy.read_10x_mtx` detects.
    #: STARsolo writes these three UNCOMPRESSED; scanpy then looks for
    #: `matrix.mtx.gz`, does not find it, and raises FileNotFoundError. The
    #: command gzips them so the output is a drop-in v3 matrix directory.
    MATRIX_FILES = ("matrix.mtx.gz", "features.tsv.gz", "barcodes.tsv.gz")
    RAW_MATRIX_NAMES = ("matrix.mtx", "features.tsv", "barcodes.tsv")
    SOLO_TYPES = ("CB_UMI_Simple", "CB_UMI_Complex", "SmartSeq")
    SOLO_FEATURES = ("Gene", "GeneFull", "GeneFull_Ex50pAS", "SJ", "Velocyto")
    CELL_FILTERS = ("EmptyDrops_CR", "CellRanger2.2", "TopCells", "None")
    UPSTREAM_SOURCE = "source/STAR.cpp; source/parametersDefault; doc/STARmanual.pdf (Section 12, STARsolo)"
    REQUIRED_PATH_INPUTS = ("genome_dir", "cdna_fastq", "barcode_fastq")
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    # SHELL because the matrix files are gzipped after STAR returns.
    SHELL = True
    EXIT_SEMANTICS = (
        "STAR exits non-zero on an unreadable index, a missing FASTQ, or a barcode "
        "geometry longer than the barcode read; Solo.out is written under the "
        "--outFileNamePrefix directory."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome_dir": ("DIRECTORY", {"description": "STAR index directory built with a GTF"}),
                "cdna_fastq": (
                    "FASTQ",
                    {"description": "cDNA read (10x R2), the read that aligns to the transcriptome"},
                ),
                "barcode_fastq": (
                    "FASTQ",
                    {"description": "Cell barcode + UMI read (10x R1)"},
                ),
            },
            "optional": {
                "solo_type": ("STRING", {"default": "CB_UMI_Simple", "options": list(cls.SOLO_TYPES)}),
                "cb_length": (
                    "INT",
                    {
                        "default": 16,
                        "min": 1,
                        "max": 64,
                        "description": "Cell barcode length; 16 for 10x v2 and v3",
                    },
                ),
                "umi_length": (
                    "INT",
                    {
                        "default": 12,
                        "min": 1,
                        "max": 64,
                        "description": "UMI length; 10 for 10x v2, 12 for 10x v3",
                    },
                ),
                "solo_features": ("STRING", {"default": "Gene", "options": list(cls.SOLO_FEATURES)}),
                "cell_filter": ("STRING", {"default": "EmptyDrops_CR", "options": list(cls.CELL_FILTERS)}),
                "whitelist": (
                    "FILE",
                    {
                        "description": (
                            "Barcode whitelist. Omit to pass --soloCBwhitelist None, which "
                            "accepts any barcode; 10x whitelists ship only inside Cell Ranger."
                        )
                    },
                ),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        validation = cls.validate_threads(inputs)
        if validation is not True:
            return validation

        for field, choices in (
            ("solo_type", cls.SOLO_TYPES),
            ("solo_features", cls.SOLO_FEATURES),
            ("cell_filter", cls.CELL_FILTERS),
        ):
            value = inputs.get(field)
            if value in (None, ""):
                continue
            if str(value) not in choices:
                return f"{field} must be one of {', '.join(choices)}"

        for field, default in (("cb_length", 16), ("umi_length", 12)):
            value = inputs.get(field, default)
            if value is None:
                value = default
            if isinstance(value, bool) or not isinstance(value, int):
                return f"{field} must be an integer"
            if not 1 <= value <= 64:
                return f"{field} must be between 1 and 64"

        genome_dir = path_value(inputs.get("genome_dir"))
        if genome_dir:
            index = Path(genome_dir)
            if index.is_dir():
                # A partially-mirrored index is the failure this catches: the
                # public cellranger-tiny-ref publishes star/Genome and
                # star/SAindex but no star/SA, and STAR then aborts with a
                # message that does not name the missing file.
                missing = [name for name in STAR_INDEX_MARKERS if not (index / name).is_file()]
                if missing:
                    return (
                        "genome_dir is not a complete STAR index; missing: "
                        + ", ".join(missing)
                    )
        return True

    @classmethod
    def _solo_root(cls, inputs: dict[str, Any]) -> Path:
        # The runner already sets `output` to <run>/<NODE_ID>, so appending
        # NODE_ID again produced .../starsolo_count/starsolo_count/ and the
        # planned outputs were never written. PLAN_OUTPUTS is the one that adds
        # NODE_ID, because it is handed the run root instead.
        return cls.output_dir(inputs)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        feature = str(inputs.get("solo_features") or "Gene")
        root = Path(output_dir) / cls.NODE_ID
        solo = root / "Solo.out" / feature
        (solo / "filtered").mkdir(parents=True, exist_ok=True)
        (solo / "raw").mkdir(parents=True, exist_ok=True)
        return [solo / "filtered", solo / "raw", root / "Log.final.out"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        root = cls._solo_root(inputs)
        cdna = str(path_value(inputs.get("cdna_fastq")))
        barcode = str(path_value(inputs.get("barcode_fastq")))
        whitelist = path_value(inputs.get("whitelist")) or "None"

        command = [
            "STAR",
            "--runThreadN",
            str(int(inputs.get("threads", 8) or 8)),
            "--genomeDir",
            str(path_value(inputs.get("genome_dir"))),
            # STARsolo takes the cDNA read FIRST and the barcode read second;
            # reversing them produces an empty matrix, not an error.
            "--readFilesIn",
            cdna,
            barcode,
            "--soloType",
            str(inputs.get("solo_type") or "CB_UMI_Simple"),
            "--soloCBwhitelist",
            whitelist,
            "--soloCBlen",
            str(int(inputs.get("cb_length", 16) or 16)),
            "--soloUMIlen",
            str(int(inputs.get("umi_length", 12) or 12)),
            "--soloUMIstart",
            str(int(inputs.get("cb_length", 16) or 16) + 1),
            "--soloFeatures",
            str(inputs.get("solo_features") or "Gene"),
            "--soloCellFilter",
            str(inputs.get("cell_filter") or "EmptyDrops_CR"),
            # No BAM: the matrix is the product, and a BAM of a whole 10x run is
            # large enough to dominate both runtime and storage.
            "--outSAMtype",
            "None",
            "--outFileNamePrefix",
            f"{root}/",
        ]
        if cdna.endswith(".gz") or barcode.endswith(".gz"):
            command.extend(["--readFilesCommand", "zcat"])

        feature = str(inputs.get("solo_features") or "Gene")
        solo = root / "Solo.out" / feature
        command.append("&&")
        command.extend(["gzip", "-f"])
        for subdir in ("filtered", "raw"):
            for name in cls.RAW_MATRIX_NAMES:
                command.append(str(solo / subdir / name))
        return command

    @classmethod
    def REQUIRED_OUTPUT_PATHS(cls, inputs: dict[str, Any], outputs: list[Path]) -> list[Path]:
        # Only the filtered matrix is required downstream; `raw` always exists
        # but carries every barcode, including empty droplets.
        return [outputs[0] / name for name in cls.MATRIX_FILES]

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """A matrix with no cells reads as success but plots nothing."""
        if not outputs:
            return
        matrix = outputs[0] / "matrix.mtx.gz"
        if not matrix.is_file():
            raise ValueError(f"STARsolo did not write {matrix}")
        barcodes = outputs[0] / "barcodes.tsv.gz"
        if barcodes.is_file():
            import gzip

            with gzip.open(barcodes, "rt", encoding="utf-8") as handle:
                cells = sum(1 for line in handle if line.strip())
            if cells == 0:
                raise ValueError(
                    "STARsolo produced zero cells; check that cdna_fastq and "
                    "barcode_fastq are not swapped and that cb_length/umi_length "
                    "match the chemistry"
                )
