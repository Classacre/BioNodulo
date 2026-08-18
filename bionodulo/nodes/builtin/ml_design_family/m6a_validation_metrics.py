"""Site-level validation of our m6A calls against GLORI ground truth."""

from __future__ import annotations

import gzip
import re
from pathlib import Path
from typing import Any, ClassVar

from .adapter import (
    MLDesignNode,
    average_ranks,
    existing_file,
    node_output_dir,
    spearman,
    validate_choice_input,
    validate_float_input,
    validate_int_input,
    write_json_file,
    write_tsv_file,
)

CHROM_ALIASES = ("chrom", "Chr", "chr", "chromosome", "Chromosome")
POS_ALIASES = ("pos", "start", "position", "Position")
STRAND_ALIASES = ("strand", "Strand")
COVERAGE_ALIASES = ("valid_coverage", "Nvalid_cov", "coverage", "cov")
VALUE_ALIASES = ("mod_ratio", "fraction_modified", "mod_fraction", "percent_modified", "percent_mod", "score")
CANONICAL_ALIASES = ("canonical_base", "canonical", "ref_base")
ZERO_BASED_POS_COLUMNS = frozenset({"start"})
SCALE_DIVISORS = {"100": 100.0, "1000": 1000.0, "fraction": 1.0}
FDR_COLUMNS = ("P_adjust", "Pvalue")
GLORI_POS_COL = "Sites"
METAGENE_BINS = 50
INPUT_MODES = ("auto", "per_site", "extract_raw")
EXTRACT_CHROM_ALIASES = ("chrom", "chrm", "chr", "chromosome")
EXTRACT_POS_ALIASES = ("ref_position", "pos_on_chrm", "pos", "position")
EXTRACT_STRAND_ALIASES = ("ref_mod_strand", "ref_strand", "strand")
EXTRACT_QUAL_ALIASES = ("mod_qual", "qual", "mod_prob")
EXTRACT_CANONICAL_ALIASES = ("canonical_base", "canonical", "ref_base")
JOINED_COLUMNS = [
    "chrom",
    "pos",
    "strand",
    "our_ratio",
    "coverage",
    "canonical_base",
    "glori_ratio",
    "glori_pvalue",
    "glori_fdr",
    "glori_positive",
    "our_call",
    "classification",
]
METAGENE_SITE_COLUMNS = ["chrom", "pos", "strand", "ratio", "transcript_id", "region", "fractional_position"]
METAGENE_BIN_COLUMNS = ["bin", "fraction_start", "fraction_end", "n_sites"]
_TRANSCRIPT_ID_RE = re.compile(r'transcript_id "([^"]+)"')


def normalise_chrom(name: str) -> str:
    """Map UCSC and Ensembl chromosome names onto one canonical form."""
    text = str(name).strip()
    if text.startswith("chr"):
        text = text[3:]
    if text == "M":
        return "MT"
    return text


_average_ranks = average_ranks


def mann_whitney_auroc(labels: Any, scores: Any) -> float | None:
    """Rank-based AUROC with ties counted as half-wins."""
    labels = labels.astype(bool)
    n_pos = int(labels.sum())
    n_neg = int((~labels).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = _average_ranks(scores)
    rank_sum = float(ranks[labels].sum())
    u1 = rank_sum - n_pos * (n_pos + 1) / 2.0
    return u1 / (n_pos * n_neg)


def precision_at_recall(labels: Any, scores: Any, target_recall: float = 0.5) -> dict[str, float] | None:
    """Sweep score thresholds downward; report precision where recall is first reached."""
    import numpy as np

    labels = labels.astype(bool)
    n_positives = int(labels.sum())
    if n_positives == 0:
        return None
    for threshold in np.unique(scores)[::-1]:
        called = scores >= threshold
        n_called = int(called.sum())
        if n_called == 0:
            continue
        true_positives = int((called & labels).sum())
        if true_positives / n_positives >= target_recall:
            return {
                "precision": true_positives / n_called,
                "threshold": float(threshold),
                "recall": true_positives / n_positives,
            }
    return None


def _pick_column(fieldnames: list[str], aliases: tuple[str, ...], fallback: str | None = None) -> str | None:
    for alias in aliases:
        if alias in fieldnames:
            return alias
    return fallback


def _read_table_text(path: Path) -> str:
    """Read plain or gzip-compressed table text transparently."""
    if path.name.lower().endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return handle.read()
    return path.read_text(encoding="utf-8")


def _table_delimiter(path: Path) -> str:
    return "," if path.name.lower().removesuffix(".gz").endswith(".csv") else "\t"


def _looks_like_extract_raw(fieldnames: list[str]) -> bool:
    return "read_id" in fieldnames and any(name in fieldnames for name in EXTRACT_POS_ALIASES)


def _parse_float(text: str) -> float | None:
    stripped = text.strip()
    if not stripped or stripped in {"NA", "nan", "NaN", "None", "."}:
        return None
    return float(stripped)


class Transcript:
    """One GTF transcript with CDS and UTR feature ranges."""

    def __init__(self, transcript_id: str, chrom: str, strand: str, start: int, end: int) -> None:
        self.transcript_id = transcript_id
        self.chrom = chrom
        self.strand = strand
        self.start = start
        self.end = end
        self.cds: list[tuple[int, int]] = []
        self.utr5: list[tuple[int, int]] = []
        self.utr3: list[tuple[int, int]] = []

    @property
    def span(self) -> int:
        return max(self.end - self.start + 1, 1)

    def contains(self, chrom: str, position: int) -> bool:
        return chrom == self.chrom and self.start <= position <= self.end

    def region_of(self, position: int) -> str:
        for start, end in self.cds:
            if start <= position <= end:
                return "CDS"
        for start, end in self.utr5:
            if start <= position <= end:
                return "5UTR"
        for start, end in self.utr3:
            if start <= position <= end:
                return "3UTR"
        if self.cds:
            cds_start = min(start for start, _ in self.cds)
            cds_end = max(end for _, end in self.cds)
            if self.strand == "-":
                if position > cds_end:
                    return "5UTR"
                if position < cds_start:
                    return "3UTR"
            else:
                if position < cds_start:
                    return "5UTR"
                if position > cds_end:
                    return "3UTR"
        return "other"

    def fractional_position(self, position: int) -> float:
        if self.strand == "-":
            fraction = (self.end - position) / self.span
        else:
            fraction = (position - self.start) / self.span
        return min(max(fraction, 0.0), 1.0)


def parse_gtf(path: Path) -> list[Transcript]:
    transcripts: dict[str, Transcript] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 9:
            continue
        chrom, _, feature, start_text, end_text, _, strand, _, attributes = fields[:9]
        if feature not in {"transcript", "exon", "CDS", "five_prime_utr", "three_prime_utr", "UTR", "gene"}:
            continue
        match = _TRANSCRIPT_ID_RE.search(attributes)
        if match is None:
            continue
        transcript_id = match.group(1)
        start, end = int(start_text), int(end_text)
        record = transcripts.get(transcript_id)
        if record is None:
            record = Transcript(transcript_id, normalise_chrom(chrom), strand.strip(), start, end)
            transcripts[transcript_id] = record
        record.start = min(record.start, start)
        record.end = max(record.end, end)
        if feature == "CDS":
            record.cds.append((start, end))
        elif feature == "five_prime_utr":
            record.utr5.append((start, end))
        elif feature == "three_prime_utr":
            record.utr3.append((start, end))
        elif feature == "UTR" and record.cds:
            cds_start = min(item[0] for item in record.cds)
            cds_end = max(item[1] for item in record.cds)
            if strand.strip() == "-":
                (record.utr5 if end > cds_end else record.utr3).append((start, end))
            else:
                (record.utr5 if start < cds_start else record.utr3).append((start, end))
    return list(transcripts.values())


def assign_transcript(transcripts: list[Transcript], chrom: str, position: int) -> Transcript | None:
    matches = [record for record in transcripts if record.contains(chrom, position)]
    if not matches:
        return None
    return min(matches, key=lambda record: (record.span, record.transcript_id))


class M6AValidationMetricsNode(MLDesignNode):
    """Score our per-site m6A calls against GLORI per-site ground truth."""

    NODE_ID = "m6a_validation_metrics"
    DISPLAY_NAME = "m6A Validation Metrics"
    DESCRIPTION = (
        "Join our per-site m6A TSV (chrom/Chr, pos/start, strand, valid_coverage/Nvalid_cov, "
        "percent_modified or mod_ratio; percent_scale selects '100', '1000', or 'fraction') against "
        "GLORI per-site CSV (Chr, Sites, Strand, ..., Ratio 0-1, P_adjust) on normalised chromosome "
        "names (UCSC chr prefix and chrM/MT are reconciled). GLORI-positive ground truth defaults to "
        "Ratio>=0.10 and P_adjust<=0.05 (both params). Computes rank-based AUROC with ties, precision "
        "at recall=0.5 by threshold sweep, recall at ratio_threshold over all GLORI positives, and "
        "stoichiometry Spearman (our ratio vs GLORI Ratio) on GLORI-positive joined sites. Optional "
        "Ensembl GTF annotates our positive sites with 5UTR/CDS/3UTR region and fractional transcript "
        "position (50-bin metagene). drach_filter (default true) keeps only A-canonical sites using the "
        "canonical_base column of our extract TSV when present; motif-context filtering beyond the "
        "canonical base is out of scope. sites_tsv may instead be the raw per-read output of "
        "`modkit extract full` (input_mode auto-sniffs read_id + ref_position columns and aggregates "
        "per chrom/pos/strand site: valid_coverage = read count, percent_modified = mean mod_qual, "
        "with 0-255 mod_qual scaling handled); .gz inputs for both tables are read transparently."
    )
    SEARCH_ALIASES = [
        "m6A",
        "GLORI",
        "validation",
        "AUROC",
        "Spearman",
        "metagene",
        "direct RNA",
        "epitranscriptome",
        "modified bases",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "JSON")
    RETURN_NAMES = ("joined_sites", "metagene_sites", "metagene_bins", "summary")
    REQUIRED_CONDA_PACKAGES = ["numpy"]
    DOCUMENTATION_URL = "https://nanoporetech.github.io/modkit/intro_extract.html"

    _GLORI_REQUIRED: ClassVar[tuple[str, ...]] = ("Chr", "Sites", "Strand", "Ratio")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sites_tsv": ("FILE", {"description": "Our per-site TSV (modkit-extract-aggregated or pileup-derived)"}),
                "glori_csv": ("FILE", {"description": "GLORI per-site CSV (Chr, Sites, Strand, Ratio, P_adjust, ...)"}),
            },
            "optional": {
                "gtf": ("FILE", {"default": "", "description": "Ensembl GTF for metagene transcript/region annotation"}),
                "percent_scale": (
                    "STRING",
                    {"default": "100", "options": ["100", "1000", "fraction"], "description": "Scale of our value column"},
                ),
                "min_coverage": ("INT", {"default": 20, "min": 0, "max": 1000000000}),
                "ratio_threshold": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 1.0, "description": "Our calling operating point"}),
                "glori_ratio_threshold": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 1.0, "description": "GLORI-positive Ratio cutoff"}),
                "glori_fdr_threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "description": "GLORI-positive FDR cutoff"}),
                "fdr_col": (
                    "STRING",
                    {"default": "P_adjust", "options": list(FDR_COLUMNS), "description": "GLORI column used for FDR gating"},
                ),
                "drach_filter": (
                    "BOOLEAN",
                    {"default": True, "description": "Keep only A-canonical sites via the canonical_base column when present"},
                ),
                "input_mode": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": list(INPUT_MODES),
                        "description": "Read sites_tsv as a per-site table, a raw modkit-extract table, or auto-sniff the header",
                    },
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_choice_input(inputs.get("input_mode", "auto"), "input_mode", INPUT_MODES)
        if validation is not True:
            return validation
        for key in ("percent_scale", "fdr_col"):
            choices = ("100", "1000", "fraction") if key == "percent_scale" else FDR_COLUMNS
            validation = validate_choice_input(inputs.get(key, "100" if key == "percent_scale" else "P_adjust"), key, choices)
            if validation is not True:
                return validation
        validation = validate_int_input(inputs.get("min_coverage", 20), "min_coverage", minimum=0, maximum=1000000000)
        if validation is not True:
            return validation
        for key, default in (
            ("ratio_threshold", 0.10),
            ("glori_ratio_threshold", 0.10),
            ("glori_fdr_threshold", 0.05),
        ):
            validation = validate_float_input(inputs.get(key, default), key, minimum=0.0, maximum=1.0)
            if validation is not True:
                return validation
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str, str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "The 'numpy' Python package is required by m6a_validation_metrics; "
                "install the conda package 'numpy'"
            ) from exc

        scale = float(SCALE_DIVISORS[str(kwargs.get("percent_scale", "100") or "100")])
        min_coverage = int(kwargs.get("min_coverage", 20))
        ratio_threshold = float(kwargs.get("ratio_threshold", 0.10))
        glori_ratio_threshold = float(kwargs.get("glori_ratio_threshold", 0.10))
        glori_fdr_threshold = float(kwargs.get("glori_fdr_threshold", 0.05))
        fdr_col = str(kwargs.get("fdr_col", "P_adjust") or "P_adjust")
        drach_filter = bool(kwargs.get("drach_filter", True))
        input_mode = str(kwargs.get("input_mode", "auto") or "auto")

        sites, columns_used, n_rows_total, mode_used = self._load_our_sites(
            kwargs["sites_tsv"], scale, drach_filter, input_mode
        )
        sites = [site for site in sites if site["coverage"] >= min_coverage]
        glori, n_glori_rows = self._load_glori(kwargs["glori_csv"], fdr_col, glori_ratio_threshold, glori_fdr_threshold)

        joined_rows: list[dict[str, Any]] = []
        scores: list[float] = []
        labels: list[bool] = []
        gloripos_scores: list[tuple[float, float]] = []
        seen_keys: set[tuple[str, int, str]] = set()
        n_tp = n_fp = n_fn_joined = n_tn = 0
        n_ours_called = 0
        for site in sites:
            our_call = site["ratio"] >= ratio_threshold
            if our_call:
                n_ours_called += 1
            key = (site["chrom_norm"], site["pos1"], site["strand"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            record = glori.get(key)
            if record is None:
                continue
            glori_positive = record["positive"]
            if our_call and glori_positive:
                classification = "TP"
                n_tp += 1
            elif our_call:
                classification = "FP"
                n_fp += 1
            elif glori_positive:
                classification = "FN"
                n_fn_joined += 1
            else:
                classification = "TN"
                n_tn += 1
            scores.append(site["ratio"])
            labels.append(glori_positive)
            if glori_positive:
                gloripos_scores.append((site["ratio"], record["ratio"]))
            joined_rows.append(
                {
                    "chrom": site["chrom"],
                    "pos": site["pos"],
                    "strand": site["strand"],
                    "our_ratio": site["ratio"],
                    "coverage": site["coverage"],
                    "canonical_base": site["canonical"],
                    "glori_ratio": record["ratio"],
                    "glori_pvalue": record["pvalue"],
                    "glori_fdr": record["fdr"],
                    "glori_positive": glori_positive,
                    "our_call": our_call,
                    "classification": classification,
                }
            )

        score_array = np.array(scores, dtype=float)
        label_array = np.array(labels, dtype=bool)
        n_glori_positive = sum(1 for record in glori.values() if record["positive"])
        auroc = mann_whitney_auroc(label_array, score_array)
        precision = precision_at_recall(label_array, score_array, 0.5)
        recall_at_threshold = (n_tp / n_glori_positive) if n_glori_positive else None
        stoichiometry = (
            spearman(np.array([item[0] for item in gloripos_scores]), np.array([item[1] for item in gloripos_scores]))
            if gloripos_scores
            else None
        )

        positive_sites = [site for site in sites if site["ratio"] >= ratio_threshold]
        transcripts = parse_gtf(existing_file(kwargs.get("gtf"), "gtf")) if kwargs.get("gtf") else []
        metagene_rows: list[dict[str, Any]] = []
        n_unassigned = 0
        for site in positive_sites:
            record = assign_transcript(transcripts, site["chrom_norm"], site["pos1"])
            if record is None:
                n_unassigned += 1
                metagene_rows.append(
                    {
                        "chrom": site["chrom"],
                        "pos": site["pos"],
                        "strand": site["strand"],
                        "ratio": site["ratio"],
                        "transcript_id": "",
                        "region": "",
                        "fractional_position": "",
                    }
                )
                continue
            metagene_rows.append(
                {
                    "chrom": site["chrom"],
                    "pos": site["pos"],
                    "strand": site["strand"],
                    "ratio": site["ratio"],
                    "transcript_id": record.transcript_id,
                    "region": record.region_of(site["pos1"]),
                    "fractional_position": record.fractional_position(site["pos1"]),
                }
            )
        bin_counts = [0] * METAGENE_BINS
        for row in metagene_rows:
            if row["fractional_position"] == "":
                continue
            index = min(int(float(row["fractional_position"]) * METAGENE_BINS), METAGENE_BINS - 1)
            bin_counts[index] += 1
        bin_rows = [
            {
                "bin": index,
                "fraction_start": index / METAGENE_BINS,
                "fraction_end": (index + 1) / METAGENE_BINS,
                "n_sites": count,
            }
            for index, count in enumerate(bin_counts)
        ]

        output_dir = node_output_dir(self, context)
        joined_path = output_dir / "joined_sites.tsv"
        metagene_path = output_dir / "metagene_sites.tsv"
        bins_path = output_dir / "metagene_bins.tsv"
        summary_path = output_dir / "summary.json"
        write_tsv_file(joined_path, JOINED_COLUMNS, joined_rows)
        write_tsv_file(metagene_path, METAGENE_SITE_COLUMNS, metagene_rows)
        write_tsv_file(bins_path, METAGENE_BIN_COLUMNS, bin_rows)
        summary = {
            "n_ours_input_rows": n_rows_total,
            "n_ours_sites": len(sites),
            "n_ours_called": n_ours_called,
            "input_mode_used": mode_used,
            "n_glori_rows": n_glori_rows,
            "n_glori_sites": len(glori),
            "n_glori_positive": n_glori_positive,
            "n_joined": len(joined_rows),
            "n_joined_positive": int(label_array.sum()) if len(labels) else 0,
            "confusion_joined": {"TP": n_tp, "FP": n_fp, "FN": n_fn_joined, "TN": n_tn},
            "metrics": {
                "auroc": auroc,
                "precision_at_recall_0_5": precision,
                "recall_at_ratio_threshold": recall_at_threshold,
                "stoichiometry_spearman": stoichiometry,
            },
            "metagene": {
                "enabled": bool(transcripts),
                "n_transcripts": len(transcripts),
                "n_positive_sites": len(positive_sites),
                "n_annotated": len(metagene_rows) - n_unassigned,
                "n_unassigned": n_unassigned,
                "bins": METAGENE_BINS,
            },
            "columns_used": columns_used,
            "params": {
                "percent_scale": str(kwargs.get("percent_scale", "100") or "100"),
                "min_coverage": min_coverage,
                "ratio_threshold": ratio_threshold,
                "glori_ratio_threshold": glori_ratio_threshold,
                "glori_fdr_threshold": glori_fdr_threshold,
                "fdr_col": fdr_col,
                "drach_filter": drach_filter,
                "drach_filter_applied": columns_used["canonical_base"] is not None,
                "input_mode": input_mode,
            },
        }
        write_json_file(summary_path, summary)
        return (str(joined_path), str(metagene_path), str(bins_path), str(summary_path))

    def _load_our_sites(
        self,
        value: Any,
        scale: float,
        drach_filter: bool,
        input_mode: str,
    ) -> tuple[list[dict[str, Any]], dict[str, str | None], int, str]:
        path = existing_file(value, "sites_tsv")
        delimiter = _table_delimiter(path)
        lines = [line for line in _read_table_text(path).splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"Input 'sites_tsv' is empty: {path}")
        fieldnames = [name.strip() for name in lines[0].split(delimiter)]
        use_extract_raw = input_mode == "extract_raw" or (
            input_mode == "auto" and _looks_like_extract_raw(fieldnames)
        )
        if use_extract_raw:
            return (*self._load_extract_raw(lines, delimiter, drach_filter), "extract_raw")
        sites, picks, n_rows = self._load_per_site(lines, delimiter, fieldnames, scale, drach_filter)
        return sites, picks, n_rows, "per_site"

    def _load_per_site(
        self,
        lines: list[str],
        delimiter: str,
        fieldnames: list[str],
        scale: float,
        drach_filter: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, str | None], int]:
        picks = {
            "chrom": _pick_column(fieldnames, CHROM_ALIASES),
            "pos": _pick_column(fieldnames, POS_ALIASES),
            "strand": _pick_column(fieldnames, STRAND_ALIASES),
            "coverage": _pick_column(fieldnames, COVERAGE_ALIASES),
            "value": _pick_column(fieldnames, VALUE_ALIASES),
            "canonical_base": _pick_column(fieldnames, CANONICAL_ALIASES),
        }
        missing = [key for key in ("chrom", "pos", "strand", "coverage", "value") if picks[key] is None]
        if missing:
            raise ValueError(
                f"Input 'sites_tsv' header is missing required column(s): {', '.join(missing)} "
                f"(found: {', '.join(fieldnames)})"
            )
        pos_column = picks["pos"] or ""
        zero_based = pos_column in ZERO_BASED_POS_COLUMNS
        sites: list[dict[str, Any]] = []
        for line_number, line in enumerate(lines[1:], start=2):
            values = [item.strip() for item in line.split(delimiter)]
            if len(values) != len(fieldnames):
                raise ValueError(
                    f"Input 'sites_tsv' row {line_number} has {len(values)} fields; expected {len(fieldnames)}"
                )
            row = dict(zip(fieldnames, values, strict=True))
            try:
                position = int(row[pos_column])
                coverage = int(float(row[picks["coverage"] or ""]))
                value = float(row[picks["value"] or ""])
            except ValueError as exc:
                raise ValueError(f"Input 'sites_tsv' row {line_number} has non-numeric fields: {exc}") from exc
            canonical = row.get(picks["canonical_base"] or "", "").strip() if picks["canonical_base"] else ""
            if drach_filter and picks["canonical_base"] and canonical.upper() != "A":
                continue
            sites.append(
                {
                    "chrom": row[picks["chrom"] or ""],
                    "chrom_norm": normalise_chrom(row[picks["chrom"] or ""]),
                    "pos": position,
                    "pos1": position if not zero_based else position + 1,
                    "strand": row[picks["strand"] or ""],
                    "coverage": coverage,
                    "ratio": min(max(value / scale, 0.0), 1.0),
                    "canonical": canonical,
                }
            )
        if not sites:
            raise ValueError("Input 'sites_tsv' contains no usable site rows")
        return sites, dict(picks), len(lines) - 1

    def _load_extract_raw(
        self,
        lines: list[str],
        delimiter: str,
        drach_filter: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, str | None], int]:
        fieldnames = [name.strip() for name in lines[0].split(delimiter)]
        picks = {
            "chrom": _pick_column(fieldnames, EXTRACT_CHROM_ALIASES),
            "pos": _pick_column(fieldnames, EXTRACT_POS_ALIASES),
            "strand": _pick_column(fieldnames, EXTRACT_STRAND_ALIASES),
            "coverage": "n_reads",
            "value": _pick_column(fieldnames, EXTRACT_QUAL_ALIASES),
            "canonical_base": _pick_column(fieldnames, EXTRACT_CANONICAL_ALIASES),
        }
        missing = [key for key in ("chrom", "pos", "strand", "value") if picks[key] is None]
        if missing:
            raise ValueError(
                f"Input 'sites_tsv' does not look like a modkit-extract table: missing column(s) "
                f"{', '.join(missing)} (found: {', '.join(fieldnames)})"
            )
        raw_rows: list[dict[str, str]] = []
        for line_number, line in enumerate(lines[1:], start=2):
            values = [item.strip() for item in line.split(delimiter)]
            if len(values) != len(fieldnames):
                raise ValueError(
                    f"Input 'sites_tsv' row {line_number} has {len(values)} fields; expected {len(fieldnames)}"
                )
            raw_rows.append(dict(zip(fieldnames, values, strict=True)))
        if not raw_rows:
            raise ValueError("Input 'sites_tsv' contains no read-level rows to aggregate")

        chrom_column = picks["chrom"] or ""
        pos_column = picks["pos"] or ""
        strand_column = picks["strand"] or ""
        qual_column = picks["value"] or ""
        canonical_column = picks["canonical_base"]
        grouped: dict[tuple[str, int, str], dict[str, Any]] = {}
        probabilities: list[float] = []
        parsed: list[tuple[str, int, str, float, str]] = []
        for row in raw_rows:
            try:
                position = int(row[pos_column])
                quality = float(row[qual_column])
            except ValueError as exc:
                raise ValueError(f"Input 'sites_tsv' has a non-numeric extract field: {exc}") from exc
            if position < 0 or row[chrom_column] in {".", ""}:
                continue
            strand = row.get(strand_column, "")
            if strand == "." or not strand:
                strand = row.get("ref_strand", "+")
            canonical = row.get(canonical_column or "", "").strip() if canonical_column else ""
            if drach_filter and canonical_column and canonical and canonical.upper() != "A":
                continue
            parsed.append((row[chrom_column], position, strand, quality, canonical))
            probabilities.append(quality)
        if not parsed:
            raise ValueError("Input 'sites_tsv' contains no usable mapped extract rows")
        divisor = 255.0 if max(probabilities) > 1.0 else 1.0
        for chrom, position, strand, quality, canonical in parsed:
            key = (normalise_chrom(chrom), position + 1, strand)
            entry = grouped.get(key)
            if entry is None:
                entry = {"chrom": chrom, "pos": position + 1, "strand": strand, "quals": [], "canonical": canonical}
                grouped[key] = entry
            entry["quals"].append(quality / divisor)
            if not entry["canonical"] and canonical:
                entry["canonical"] = canonical
        sites = [
            {
                "chrom": entry["chrom"],
                "chrom_norm": key[0],
                "pos": entry["pos"],
                "pos1": entry["pos"],
                "strand": key[2],
                "coverage": len(entry["quals"]),
                "ratio": min(max(sum(entry["quals"]) / len(entry["quals"]), 0.0), 1.0),
                "canonical": entry["canonical"],
            }
            for key, entry in sorted(grouped.items())
        ]
        return sites, dict(picks), len(raw_rows)

    def _load_glori(
        self,
        value: Any,
        fdr_col: str,
        ratio_threshold: float,
        fdr_threshold: float,
    ) -> tuple[dict[tuple[str, int, str], dict[str, Any]], int]:
        path = existing_file(value, "glori_csv")
        delimiter = _table_delimiter(path)
        lines = [line for line in _read_table_text(path).splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"Input 'glori_csv' is empty: {path}")
        fieldnames = [name.strip() for name in lines[0].split(delimiter)]
        missing = [column for column in (*self._GLORI_REQUIRED, fdr_col) if column not in fieldnames]
        if missing:
            raise ValueError(
                f"Input 'glori_csv' header is missing required column(s): {', '.join(missing)} "
                f"(found: {', '.join(fieldnames)})"
            )
        records: dict[tuple[str, int, str], dict[str, Any]] = {}
        duplicates = 0
        for line_number, line in enumerate(lines[1:], start=2):
            values = [item.strip() for item in line.split(delimiter)]
            if len(values) != len(fieldnames):
                raise ValueError(
                    f"Input 'glori_csv' row {line_number} has {len(values)} fields; expected {len(fieldnames)}"
                )
            row = dict(zip(fieldnames, values, strict=True))
            try:
                position = int(row[GLORI_POS_COL])
            except ValueError as exc:
                raise ValueError(f"Input 'glori_csv' row {line_number} has a non-integer Sites value: {exc}") from exc
            ratio = _parse_float(row["Ratio"])
            fdr = _parse_float(row[fdr_col])
            pvalue = _parse_float(row.get("Pvalue", ""))
            key = (normalise_chrom(row["Chr"]), position, row["Strand"])
            if key in records:
                duplicates += 1
                continue
            records[key] = {
                "ratio": ratio,
                "pvalue": pvalue,
                "fdr": fdr,
                "positive": ratio is not None and fdr is not None and ratio >= ratio_threshold and fdr <= fdr_threshold,
            }
        if not records:
            raise ValueError(f"Input 'glori_csv' contains no site rows: {path}")
        if duplicates:
            raise ValueError(f"Input 'glori_csv' contains {duplicates} duplicate chrom/Sites/Strand rows")
        return records, len(lines) - 1
