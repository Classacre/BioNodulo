"""Check designed candidates for leakage against the predictor training set."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.base import path_probe_is_file

from .adapter import MLDesignNode, node_output_dir, read_table, write_json_file, write_tsv_file

KMER_LENGTH = 31
CONTAINMENT_THRESHOLD = 0.5


class TrainingLeakageCheckNode(MLDesignNode):
    """Exact-duplicate and k-mer containment audit of candidates vs training data."""

    NODE_ID = "training_leakage_check"
    DISPLAY_NAME = "Training Leakage Check"
    DESCRIPTION = (
        "Audits designed candidates (E1/E2 outputs) for leakage into a predictor's "
        "training data. Inputs: candidates as a multi-record FASTA path or inline "
        "FASTA text; training as a TSV/CSV with a sequence column (set "
        "training_seq_column, default 'RNA.sequence') or a FASTA. Reports the "
        "exact full-sequence duplicate count with ids, and per-candidate 31-mer "
        "containment in the training set: the number of candidate sequences with "
        ">=50% of their 31-mers present in training, the maximum containment "
        "fraction per sequence and overall. Sequences shorter than 31 nt have no "
        "k-mers and are excluded from containment statistics. Pure stdlib set "
        "arithmetic over k-mer strings."
    )
    SEARCH_ALIASES = [
        "leakage",
        "training set",
        "contamination",
        "memorization",
        "kmer containment",
        "duplicate sequences",
        "generalization",
    ]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("summary", "per_candidate")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "candidates": (
                    "STRING",
                    {"description": "Designed candidate sequences: multi-record FASTA path or inline FASTA text"},
                ),
                "training": (
                    "STRING",
                    {"description": "Training sequences: TSV/CSV path (sequence column) or FASTA path/text"},
                ),
            },
            "optional": {
                "training_seq_column": (
                    "STRING",
                    {"default": "RNA.sequence", "description": "Sequence column name when 'training' is a TSV/CSV"},
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        column = str(kwargs.get("training_seq_column", "RNA.sequence") or "RNA.sequence").strip()
        candidates = self._fasta_records(kwargs["candidates"], "candidates")
        if not candidates:
            raise ValueError("Input 'candidates' must contain at least one FASTA record")
        training = self._training_sequences(kwargs["training"], column)
        if not training:
            raise ValueError("Input 'training' must contain at least one sequence")

        training_set = set(training)
        training_kmers: set[str] = set()
        for sequence in training:
            training_kmers.update(self._kmers(sequence))

        per_candidate: list[dict[str, Any]] = []
        exact_ids: list[str] = []
        max_containment: float | None = None
        over_threshold = 0
        with_kmers = 0
        for identifier, sequence in candidates:
            exact = sequence in training_set
            if exact:
                exact_ids.append(identifier)
            kmers = set(self._kmers(sequence))
            if kmers:
                with_kmers += 1
                shared = len(kmers & training_kmers)
                containment = shared / len(kmers)
                if max_containment is None or containment > max_containment:
                    max_containment = containment
                if containment >= CONTAINMENT_THRESHOLD:
                    over_threshold += 1
            else:
                shared = 0
                containment = None
            per_candidate.append(
                {
                    "id": identifier,
                    "n_kmers": len(kmers),
                    "n_shared": shared,
                    "containment": containment,
                    "exact_duplicate": exact,
                }
            )

        summary = {
            "kmer_length": KMER_LENGTH,
            "containment_threshold": CONTAINMENT_THRESHOLD,
            "n_candidates": len(candidates),
            "n_training": len(training),
            "exact_duplicates": len(exact_ids),
            "ids_exact": exact_ids,
            "max_kmer_containment": max_containment,
            "frac_seqs_over_50pct": (over_threshold / len(candidates)) if candidates else 0.0,
            "n_seqs_over_50pct": over_threshold,
            "n_seqs_with_kmers": with_kmers,
        }

        output_dir = node_output_dir(self, context)
        summary_path = output_dir / "summary.json"
        per_candidate_path = output_dir / "per_candidate.tsv"
        write_json_file(summary_path, summary)
        write_tsv_file(
            per_candidate_path,
            ["id", "n_kmers", "n_shared", "containment", "exact_duplicate"],
            per_candidate,
        )
        return (str(summary_path), str(per_candidate_path))

    @staticmethod
    def _kmers(sequence: str) -> list[str]:
        return [sequence[index : index + KMER_LENGTH] for index in range(len(sequence) - KMER_LENGTH + 1)]

    @staticmethod
    def _fasta_records(value: Any, key: str) -> list[tuple[str, str]]:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"Input '{key}' must be a FASTA path or inline FASTA text")
        if path_probe_is_file(text):
            text = Path(text).expanduser().read_text(encoding="utf-8")
        records: list[tuple[str, str]] = []
        identifier = ""
        chunks: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if identifier and chunks:
                    records.append((identifier, "".join(chunks).upper()))
                identifier = line[1:].split()[0] if line[1:].split() else ""
                chunks = []
            else:
                chunks.append("".join(line.split()))
        if identifier and chunks:
            records.append((identifier, "".join(chunks).upper()))
        if not records:
            raise ValueError(f"Input '{key}' contains no FASTA records")
        return records

    @staticmethod
    def _training_sequences(value: Any, column: str) -> list[str]:
        text = str(value or "").strip()
        if not text:
            raise ValueError("Input 'training' must be a TSV/CSV path or a FASTA path")
        if not path_probe_is_file(text):
            raise ValueError(f"Input 'training' is not an existing file: {text}")
        path = Path(text).expanduser()
        content = path.read_text(encoding="utf-8")
        if content.lstrip().startswith(">"):
            return [sequence for _, sequence in TrainingLeakageCheckNode._fasta_records(text, "training")]
        fieldnames, rows = read_table(path)
        if column not in fieldnames:
            raise ValueError(
                f"Input 'training' table has no '{column}' column (available: {', '.join(fieldnames)})"
            )
        return ["".join(row.get(column, "").split()).upper() for row in rows if row.get(column, "").strip()]
