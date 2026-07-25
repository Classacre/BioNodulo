"""Deterministic BioNodulo gene-set overlap operation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import path_value, validate_choice


def _normalise_gene(value: Any, case_sensitive: bool) -> str:
    gene = str(value or "").strip()
    return gene if case_sensitive else gene.upper()


def _table_dialect(path: Path, sample: str) -> csv.Dialect:
    if path.suffix.lower() == ".csv":
        return csv.excel
    if path.suffix.lower() in {".tsv", ".tab"}:
        return csv.excel_tab
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t")
    except csv.Error:
        return csv.excel_tab


def _read_query(path: Path, column: str, case_sensitive: bool) -> list[tuple[str, str]]:
    raw = path.read_text(encoding="utf-8").splitlines()
    if not raw:
        return []
    if column:
        with path.open(newline="", encoding="utf-8") as handle:
            sample = handle.read(4096)
            handle.seek(0)
            reader = csv.DictReader(handle, dialect=_table_dialect(path, sample))
            if reader.fieldnames is None or column not in reader.fieldnames:
                raise ValueError(f"Column {column!r} not found in gene input")
            values = [row.get(column, "") for row in reader]
    else:
        values = raw

    genes: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in values:
        original = str(value or "").strip()
        normalised = _normalise_gene(original, case_sensitive)
        if normalised and normalised not in seen:
            seen.add(normalised)
            genes.append((original, normalised))
    return genes


def _database_format(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    if path.suffix.lower() == ".json":
        return "json"
    if path.suffix.lower() == ".csv":
        return "csv"
    return "tsv"


def _read_gene_sets(path: Path, requested_format: str, case_sensitive: bool) -> dict[str, list[str]]:
    database_format = _database_format(path, requested_format)
    if database_format == "json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON gene set database must map set names to gene lists")
        gene_sets: dict[str, list[str]] = {}
        for name, genes in payload.items():
            if not isinstance(genes, list):
                raise ValueError(f"Gene set {name!r} must be a list")
            gene_sets[str(name)] = [
                normalised for gene in genes if (normalised := _normalise_gene(gene, case_sensitive))
            ]
        return gene_sets

    delimiter = "," if database_format == "csv" else "\t"
    gene_sets = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None or not {"gene_set", "gene"}.issubset(reader.fieldnames):
            raise ValueError("Table gene set database must contain gene_set and gene columns")
        for row in reader:
            name = str(row.get("gene_set", "")).strip()
            gene = _normalise_gene(row.get("gene", ""), case_sensitive)
            if name and gene:
                gene_sets.setdefault(name, []).append(gene)
    return gene_sets


class IntersectGenesNode(BaseNode):
    """Intersect a query gene list with JSON, TSV, or CSV gene sets."""

    NODE_ID = "intersect_genes"
    DISPLAY_NAME = "Intersect Genes"
    CATEGORY = "annotation"
    DESCRIPTION = "Deterministic gene-set overlap without statistical enrichment claims."
    SEARCH_ALIASES = ["gene set", "pathway overlap", "intersect", "genes", "BioNodulo builtin"]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("overlap", "enrichment")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    VERSION = "1.0.0"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = "ca74cf20800257fe98db3f8b4787885f6815b8fb"
    DOCUMENTATION_URL = "https://github.com/Classacre/BioNodulo"
    SOURCE_URL = (
        "https://github.com/Classacre/BioNodulo/blob/"
        "ca74cf20800257fe98db3f8b4787885f6815b8fb/bionodulo/nodes/builtin/annotation.py"
    )
    UPSTREAM_SOURCE = "bionodulo/nodes/builtin/annotation.py:1344"
    EXIT_SEMANTICS = "Malformed JSON/tables and missing named query columns raise ValueError."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_genes": ("FILE", {"description": "Gene list or table"}),
                "database": ("FILE", {"description": "JSON or gene_set/gene table"}),
            },
            "optional": {
                "input_column": ("STRING", {"default": ""}),
                "database_format": (
                    "STRING",
                    {"default": "auto", "options": ["auto", "json", "tsv", "csv"]},
                ),
                "case_sensitive": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / "overlap.tsv", node_dir / "enrichment.json"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("input_genes", "database"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        return validate_choice(
            inputs.get("database_format", "auto"),
            "database_format",
            ("auto", "json", "tsv", "csv"),
        )

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        output_dir = kwargs.pop("output_dir", None)
        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        case_sensitive = bool(kwargs.get("case_sensitive", False))
        query = _read_query(
            Path(path_value(kwargs["input_genes"])),
            str(kwargs.get("input_column", "")),
            case_sensitive,
        )
        gene_sets = _read_gene_sets(
            Path(path_value(kwargs["database"])),
            str(kwargs.get("database_format", "auto")),
            case_sensitive,
        )
        query_by_key = {normalised: original for original, normalised in query}

        overlap_rows: list[dict[str, str]] = []
        matched_sets: list[dict[str, Any]] = []
        for gene_set in sorted(gene_sets):
            genes = gene_sets[gene_set]
            matched = [query_by_key[gene] for gene in dict.fromkeys(genes) if gene in query_by_key]
            overlap_rows.extend({"gene": gene, "gene_set": gene_set} for gene in matched)
            if matched:
                matched_sets.append(
                    {
                        "gene_set": gene_set,
                        "overlap_count": len(matched),
                        "set_size": len(set(genes)),
                        "genes": matched,
                    }
                )
        matched_sets.sort(key=lambda item: (-item["overlap_count"], item["gene_set"]))

        base_dir = output_dir
        if base_dir is None and context is not None:
            base_dir = getattr(context, "node_dir", ".")
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_dir or ".")
        with outputs[0].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["gene", "gene_set"], delimiter="\t")
            writer.writeheader()
            writer.writerows(overlap_rows)
        outputs[1].write_text(
            json.dumps(
                {
                    "query_gene_count": len(query),
                    "overlap_gene_count": len({row["gene"] for row in overlap_rows}),
                    "sets": matched_sets,
                },
                indent=2,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return str(outputs[0]), str(outputs[1])
