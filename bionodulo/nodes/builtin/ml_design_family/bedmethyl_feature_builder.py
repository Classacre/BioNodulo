"""Per-transcript modified-base feature aggregation from modkit bedMethyl pileups."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from .adapter import (
    MLDesignNode,
    existing_file,
    node_output_dir,
    validate_float_input,
    validate_int_input,
    write_json_file,
    write_tsv_file,
)

FEATURE_COLUMNS = [
    "transcript_id",
    "biotype",
    "n_sites",
    "n_covered_sites",
    "n_mod_sites",
    "mean_mod_fraction",
    "mod_sites_per_kb",
    "mean_coverage",
    "length_bp",
    "alignment_mean_cov",
]


class BedmethylFeatureBuilderNode(MLDesignNode):
    """Aggregate a modkit bedMethyl pileup into per-transcript ML features."""

    NODE_ID = "bedmethyl_feature_builder"
    DISPLAY_NAME = "bedMethyl Feature Builder"
    DESCRIPTION = (
        "Aggregate a modkit pileup bedMethyl TSV (chrom, start, end, mod code, score, "
        "strand, ..., Nvalid_cov, percent modified) into per-transcript features: "
        "coverage-weighted mean modification fraction, n_mod_sites, n_covered_sites, "
        "mod_sites_per_kb, and mean coverage. Sites are grouped via an optional "
        "transcript BED (chrom, tx_start, tx_end, transcript_id[, biotype]); without it "
        "sites group by chromosome and length_bp is the grouped site span. mod_codes "
        "filters the raw 4th-column values (modkit single-letter/ChEBI codes; 'm,CG,0' "
        "matches code 'm'; modBAM short codes: 'm'=5mC, 'a'=m6A, so filter m6A sites with mod_codes 'a'). percent_scale selects the modkit "
        "0-100 percent convention or the bedMethyl 0-1000 score convention."
    )
    SEARCH_ALIASES = [
        "bedMethyl",
        "modkit",
        "m6A",
        "modification",
        "direct RNA",
        "multi-omics",
        "feature matrix",
        "epitranscriptome",
        "nanopore",
    ]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("features", "summary")
    DOCUMENTATION_URL = "https://nanoporetech.github.io/modkit/intro_pileup.html"

    _MOD_CODE_ALIASES: ClassVar[dict[str, str]] = {"m6a": "m", "5mc": "m", "5hmc": "h"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bedmethyl": ("FILE", {"description": "modkit pileup bedMethyl TSV, with or without header"}),
            },
            "optional": {
                "coverage_tsv": (
                    "FILE",
                    {"default": "", "description": "Per-transcript coverage TSV with chrom, transcript, mean_cov header"},
                ),
                "transcript_bed": (
                    "FILE",
                    {"default": "", "description": "Transcript BED: chrom, tx_start, tx_end, transcript_id[, biotype]"},
                ),
                "mod_codes": (
                    "STRING",
                    {"default": "", "description": "Comma-separated 4th-column mod codes; empty keeps all"},
                ),
                "min_coverage": ("INT", {"default": 1, "min": 0, "max": 1000000000}),
                "min_percent_modified": ("FLOAT", {"default": 10.0, "min": 0.0, "max": 100.0}),
                "percent_scale": ("STRING", {"default": "100", "options": ["100", "1000"]}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_int_input(
            inputs.get("min_coverage", 1), "min_coverage", minimum=0, maximum=1000000000
        )
        if validation is not True:
            return validation
        return validate_float_input(
            inputs.get("min_percent_modified", 10.0),
            "min_percent_modified",
            minimum=0.0,
            maximum=100.0,
        )

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        mod_codes = self._selected_codes(kwargs.get("mod_codes"))
        min_coverage = int(kwargs.get("min_coverage", 1))
        threshold = float(kwargs.get("min_percent_modified", 10.0))
        scale = float(str(kwargs.get("percent_scale", "100") or "100"))

        transcripts = self._transcripts(kwargs.get("transcript_bed"))
        coverage = self._coverage(kwargs.get("coverage_tsv"))
        sites, n_rows_total = self._parse_sites(kwargs["bedmethyl"], mod_codes, scale)

        keys = sorted({site[0] for site in sites}) if transcripts is None else sorted(transcripts)
        grouped: dict[str, list[tuple[int, int, int, float]]] = {key: [] for key in keys}
        unassigned = 0
        for chrom, start, end, coverage_value, fraction in sites:
            key = self._assign(chrom, start, transcripts)
            if key is None:
                unassigned += 1
                continue
            grouped.setdefault(key, []).append((start, end, coverage_value, fraction))

        rows: list[dict[str, Any]] = []
        kept = 0
        for key in keys:
            entries = grouped.get(key, [])
            kept += len(entries)
            covered = [entry for entry in entries if entry[2] >= min_coverage]
            modified = [entry for entry in covered if entry[3] * 100.0 >= threshold]
            weight = sum(entry[2] for entry in covered)
            mean_fraction = (
                sum(entry[2] * entry[3] for entry in covered) / weight if weight > 0 else 0.0
            )
            length_bp = self._length_bp(key, transcripts, entries)
            rows.append(
                {
                    "transcript_id": key,
                    "biotype": transcripts[key][3] if transcripts else "",
                    "n_sites": len(entries),
                    "n_covered_sites": len(covered),
                    "n_mod_sites": len(modified),
                    "mean_mod_fraction": mean_fraction,
                    "mod_sites_per_kb": len(modified) / (max(length_bp, 1) / 1000.0),
                    "mean_coverage": (sum(entry[2] for entry in entries) / len(entries)) if entries else 0.0,
                    "length_bp": length_bp,
                    "alignment_mean_cov": coverage.get(key, ""),
                }
            )

        output_dir = node_output_dir(self, context)
        tsv_path = output_dir / "features.tsv"
        json_path = output_dir / "summary.json"
        write_tsv_file(tsv_path, FEATURE_COLUMNS, rows)
        write_json_file(
            json_path,
            {
                "n_transcripts": len(rows),
                "n_sites_total": n_rows_total,
                "n_sites_matched": len(sites),
                "n_sites_kept": kept,
                "n_unassigned_sites": unassigned,
                "mod_codes_used": mod_codes,
                "params": {
                    "min_coverage": min_coverage,
                    "min_percent_modified": threshold,
                    "percent_scale": scale,
                },
                "feature_columns": FEATURE_COLUMNS,
            },
        )
        return (str(tsv_path), str(json_path))

    def _parse_sites(
        self,
        value: Any,
        mod_codes: list[str],
        scale: float,
    ) -> tuple[list[tuple[str, int, int, int, float]], int]:
        path = existing_file(value, "bedmethyl")
        rows = self._read_rows(path)
        sites: list[tuple[str, int, int, int, float]] = []
        for line_number, fields in enumerate(rows, start=1):
            if len(fields) < 10:
                raise ValueError(
                    f"Input 'bedmethyl' row {line_number} has {len(fields)} columns; "
                    "modkit bedMethyl requires at least 10"
                )
            raw_code = fields[3].strip()
            if mod_codes and not self._code_matches(raw_code, mod_codes):
                continue
            try:
                start = int(fields[1])
                end = int(fields[2])
                coverage = int(float(fields[9]))
                percent = float(fields[10]) if len(fields) >= 11 else float(fields[4])
            except ValueError as exc:
                raise ValueError(
                    f"Input 'bedmethyl' row {line_number} has non-numeric coordinate/coverage fields: {exc}"
                ) from exc
            fraction = min(max(percent / scale, 0.0), 1.0)
            sites.append((fields[0].strip(), start, end, coverage, fraction))
        return sites, len(rows)

    def _selected_codes(self, value: Any) -> list[str]:
        raw = [item.strip() for item in str(value or "").split(",") if item.strip()]
        return [self._MOD_CODE_ALIASES.get(item.lower(), item) for item in raw]

    @staticmethod
    def _code_matches(raw_code: str, mod_codes: list[str]) -> bool:
        token = raw_code.split(",")[0]
        return raw_code in mod_codes or token in mod_codes

    @staticmethod
    def _read_rows(path: Path) -> list[list[str]]:
        lines = [
            line.rstrip("\r\n")
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if not lines:
            raise ValueError(f"Input 'bedmethyl' is empty: {path}")
        split = lines[0].split("\t") if "\t" in lines[0] else lines[0].split()
        if BedmethylFeatureBuilderNode._looks_like_header(split):
            lines = lines[1:]
        rows: list[list[str]] = []
        for line in lines:
            rows.append(line.split("\t") if "\t" in line else line.split())
        if not rows:
            raise ValueError(f"Input 'bedmethyl' contains no site rows: {path}")
        return rows

    @staticmethod
    def _looks_like_header(fields: list[str]) -> bool:
        if len(fields) < 4:
            return False
        third = fields[2].strip().lower()
        fourth = fields[3].strip().lower()
        return not third.isdigit() or fourth in {"mod_code", "modcode", "mod_code_or_motif", "code"}

    def _transcripts(self, value: Any) -> dict[str, tuple[str, int, int, str]] | None:
        if value in (None, ""):
            return None
        path = existing_file(value, "transcript_bed")
        lines = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        if not lines:
            raise ValueError(f"Input 'transcript_bed' is empty: {path}")
        first = lines[0].split("\t") if "\t" in lines[0] else lines[0].split()
        if not first[1].strip().isdigit():
            lines = lines[1:]
        intervals: dict[str, tuple[str, int, int, str]] = {}
        for line_number, line in enumerate(lines, start=1):
            fields = line.split("\t") if "\t" in line else line.split()
            if len(fields) < 4:
                raise ValueError(
                    f"Input 'transcript_bed' row {line_number} has {len(fields)} columns; "
                    "expected chrom, tx_start, tx_end, transcript_id[, biotype]"
                )
            try:
                chrom, start, end = fields[0].strip(), int(fields[1]), int(fields[2])
            except ValueError as exc:
                raise ValueError(
                    f"Input 'transcript_bed' row {line_number} has non-integer coordinates: {exc}"
                ) from exc
            identifier = fields[3].strip()
            if not identifier:
                raise ValueError(f"Input 'transcript_bed' row {line_number} has an empty transcript_id")
            if identifier in intervals:
                raise ValueError(f"Input 'transcript_bed' contains duplicate transcript_id: {identifier}")
            if start >= end:
                raise ValueError(f"Input 'transcript_bed' row {line_number} has tx_start >= tx_end")
            intervals[identifier] = (chrom, start, end, fields[4].strip() if len(fields) > 4 else "")
        return intervals

    @staticmethod
    def _coverage(value: Any) -> dict[str, str]:
        if value in (None, ""):
            return {}
        path = existing_file(value, "coverage_tsv")
        header: list[str] | None = None
        mapping: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            fields = line.split("\t") if "\t" in line else line.split()
            if header is None:
                header = [field.strip() for field in fields]
                for column in ("transcript", "mean_cov"):
                    if column not in header:
                        raise ValueError(f"Input 'coverage_tsv' header must contain a '{column}' column")
                continue
            row = dict(zip(header, fields, strict=False))
            identifier = row.get("transcript", "").strip()
            if not identifier:
                continue
            if identifier in mapping:
                raise ValueError(f"Input 'coverage_tsv' contains duplicate transcript: {identifier}")
            mapping[identifier] = row.get("mean_cov", "").strip()
        if header is None:
            raise ValueError(f"Input 'coverage_tsv' is empty: {path}")
        return mapping

    @staticmethod
    def _assign(
        chrom: str,
        start: int,
        transcripts: dict[str, tuple[str, int, int, str]] | None,
    ) -> str | None:
        if transcripts is None:
            return chrom
        matches = sorted(
            (interval[1], identifier)
            for identifier, interval in transcripts.items()
            if interval[0] == chrom and interval[1] <= start < interval[2]
        )
        return matches[0][1] if matches else None

    @staticmethod
    def _length_bp(
        key: str,
        transcripts: dict[str, tuple[str, int, int, str]] | None,
        entries: list[tuple[int, int, int, float]],
    ) -> int:
        if transcripts is not None:
            interval = transcripts[key]
            return interval[2] - interval[1]
        if not entries:
            return 0
        return max(entry[1] for entry in entries) - min(entry[0] for entry in entries)
