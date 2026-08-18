"""CDS codon-usage metric node (CAI, GC, Nc, codon pair score)."""

from __future__ import annotations

from typing import Any

from .adapter import (
    CODON_USAGE_SOURCE,
    DNA_ALPHABET,
    CodonDesignNode,
    STOP_CODONS,
    cai_score,
    codon_pair_score,
    codons_of,
    effective_number_of_codons,
    gc_by_codon_position,
    gc_fraction,
    read_fasta_records,
    require_dna_cds,
    validate_sequence_literal,
    write_json,
    write_record_table,
)

PER_RECORD_COLUMNS = ["id", "cai", "gc", "gc_window_max_dev", "n_codons"]


class CodonMetricsNode(CodonDesignNode):
    """Compute CAI, GC frame content, Nc, and codon pair score for one CDS."""

    NODE_ID = "codon_metrics"
    DISPLAY_NAME = "Codon Metrics"
    DESCRIPTION = (
        "Compute codon-usage metrics for one CDS: CAI (Sharp & Li 1987), GC/GC1/GC2/GC3, sliding-window "
        "GC, Wright's effective number of codons (Nc, 1990), and a usage-referenced codon pair score. "
        f"CAI weights: {CODON_USAGE_SOURCE}."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "codon usage",
        "CAI",
        "effective number of codons",
        "Nc",
        "GC content",
        "GC3",
        "codon pair score",
    ]
    RETURN_TYPES = ("JSON", "TSV", "TSV", "JSON")
    RETURN_NAMES = ("metrics", "metrics_table", "per_record", "per_record_json")
    OUTPUT_FILENAMES = ("metrics.json", "metrics.tsv", "per_record.tsv", "per_record.json")
    DOCUMENTATION_URL = "https://www.kazusa.or.jp/codon/"
    CITATION_DOIS = ["10.1093/nar/15.3.1281", "10.1016/0378-1119(90)90491-9", "10.1093/nar/28.1.292"]
    CITATION_URLS = [
        "https://doi.org/10.1093/nar/15.3.1281",
        "https://doi.org/10.1016/0378-1119(90)90491-9",
        "https://doi.org/10.1093/nar/28.1.292",
    ]
    CITATION_TEXT = (
        "The codon adaptation index; The 'effective number of codons' used in a gene; codon usage "
        "tabulated from international DNA sequence databases."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cds": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "CDS sequence, or a path to a FASTA/plain CDS file"},
                ),
            },
            "optional": {
                "window": ("INT", {"default": 30, "min": 3, "max": 10000, "description": "Sliding window size for GC profiling"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("cds", "") or "").strip():
            return "Input 'cds' must be a non-empty sequence or file path"
        validation = validate_sequence_literal(
            inputs.get("cds"), "cds", alphabet=DNA_ALPHABET, divisible_by_3=True
        )
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("window", 30), "window", minimum=3, maximum=10000)

    async def run(self, **kwargs: Any) -> tuple[str, str, str, str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        context = kwargs.get("context")
        records = [
            (record_id, require_dna_cds(sequence, "cds"))
            for record_id, sequence in read_fasta_records(kwargs.get("cds"), "cds")
        ]
        cds = "".join(sequence for _, sequence in records)
        window = int(kwargs.get("window", 30))

        codon_list = codons_of(cds)
        internal_stops = sum(1 for codon in codon_list[:-1] if codon in STOP_CODONS)
        gc_positions = gc_by_codon_position(cds)
        gc_windows = [
            {
                "start": offset + 1,
                "end": min(offset + window, len(cds)),
                "gc": gc_fraction(cds[offset:offset + window]),
            }
            for offset in range(0, len(cds), window)
            if cds[offset:offset + window]
        ]
        window_values = [entry["gc"] for entry in gc_windows]
        metrics: dict[str, Any] = {
            "length_nt": len(cds),
            "length_codons": len(codon_list),
            "cai": cai_score(cds),
            "gc": gc_fraction(cds),
            "gc1": gc_positions.get("1"),
            "gc2": gc_positions.get("2"),
            "gc3": gc_positions.get("3"),
            "nc_effective": effective_number_of_codons(cds),
            "codon_pair_score": codon_pair_score(cds),
            "starts_with_atg": cds[:3] == "ATG",
            "internal_stop_count": internal_stops,
            "ends_with_stop": codon_list[-1] in STOP_CODONS if codon_list else False,
            "window_size": window,
            "window_count": len(gc_windows),
            "window_gc_min": min(window_values) if window_values else None,
            "window_gc_max": max(window_values) if window_values else None,
            "window_gc_mean": (sum(window_values) / len(window_values)) if window_values else None,
            "gc_windows": gc_windows,
            "usage_source": CODON_USAGE_SOURCE,
        }

        json_path = self.node_output_path(context, "metrics.json")
        write_json(json_path, metrics)
        tsv_path = self.node_output_path(context, "metrics.tsv")
        scalar_rows = [
            (key, value)
            for key, value in metrics.items()
            if value is not None and not isinstance(value, (list, dict))
        ]
        lines = ["metric\tvalue"]
        lines.extend(f"{key}\t{value}" for key, value in scalar_rows)
        tsv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        per_record_rows = [self._record_row(record_id, sequence, window) for record_id, sequence in records]
        per_record_tsv = self.node_output_path(context, "per_record.tsv")
        write_record_table(per_record_tsv, PER_RECORD_COLUMNS, per_record_rows)
        per_record_json = self.node_output_path(context, "per_record.json")
        write_json(per_record_json, per_record_rows)
        return (str(json_path), str(tsv_path), str(per_record_tsv), str(per_record_json))

    @staticmethod
    def _record_row(record_id: str, sequence: str, window: int) -> dict[str, Any]:
        overall_gc = gc_fraction(sequence)
        window_gc_values = [
            gc_fraction(sequence[offset:offset + window])
            for offset in range(0, len(sequence), window)
            if sequence[offset:offset + window]
        ]
        return {
            "id": record_id,
            "cai": cai_score(sequence),
            "gc": overall_gc,
            "gc_window_max_dev": max((abs(value - overall_gc) for value in window_gc_values), default=0.0),
            "n_codons": len(codons_of(sequence)),
        }
