"""intersect — annotation node(s). One tool per file (extracted from annotation.py)."""
from __future__ import annotations
import csv
import json
import re
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode, _shell_join
DOI_URL = 'https://doi.org/'
BCFTOOLS_CITATION_DOIS = ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btp352']
BCFTOOLS_CITATION_URLS = [f'{DOI_URL}{doi}' for doi in BCFTOOLS_CITATION_DOIS]
BCFTOOLS_CITATION_TEXT = 'Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools.'
def _annotation_node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _safe_output_stem(value: str, default: str) -> str:
    stem = '_'.join(str(value or '').strip().split())
    stem = ''.join((char if char.isalnum() or char in '._-' else '_' for char in stem))
    stem = stem.strip('._-')
    return stem or default
def _split_annotation_files(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in re.split('[\\n,]+', str(value)) if part.strip()]
def _split_annotation_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]
def _normalise_gene(value: Any, case_sensitive: bool) -> str:
    gene = str(value or '').strip()
    return gene if case_sensitive else gene.upper()
def _read_gene_query(path: str | Path, column: str, case_sensitive: bool) -> list[tuple[str, str]]:
    raw = Path(path).read_text(encoding='utf-8').splitlines()
    if not raw:
        return []
    if column:
        with Path(path).open(newline='', encoding='utf-8') as fh:
            sample = fh.read(2048)
            fh.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=',\t') if sample.strip() else csv.excel_tab
            reader = csv.DictReader(fh, dialect=dialect)
            if reader.fieldnames is None or column not in reader.fieldnames:
                raise ValueError(f'Column {column!r} not found in gene input')
            values = [row.get(column, '') for row in reader]
    else:
        values = raw
    genes: list[tuple[str, str]] = []
    seen: set[str] = set()
    for value in values:
        original = str(value or '').strip()
        normalised = _normalise_gene(original, case_sensitive)
        if normalised and normalised not in seen:
            seen.add(normalised)
            genes.append((original, normalised))
    return genes
def _read_gene_sets(path: str | Path, database_format: str, case_sensitive: bool) -> dict[str, list[tuple[str, str]]]:
    fmt = str(database_format or 'auto').lower()
    source = Path(path)
    if fmt == 'auto':
        fmt = 'json' if source.suffix.lower() == '.json' else 'tsv'
    if fmt == 'json':
        payload = json.loads(source.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('JSON gene set database must be an object mapping set names to gene lists')
        gene_sets: dict[str, list[tuple[str, str]]] = {}
        for name, genes in payload.items():
            if not isinstance(genes, list):
                raise ValueError(f'Gene set {name!r} must be a list')
            gene_sets[str(name)] = [(str(gene).strip(), _normalise_gene(gene, case_sensitive)) for gene in genes]
        return gene_sets
    if fmt not in {'tsv', 'csv'}:
        raise ValueError(f'Unsupported database format: {database_format}')
    delimiter = ',' if fmt == 'csv' else '\t'
    gene_sets = {}
    with source.open(newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None or not {'gene_set', 'gene'}.issubset(reader.fieldnames):
            raise ValueError('Table gene set database must contain gene_set and gene columns')
        for row in reader:
            name = str(row.get('gene_set', '')).strip()
            gene = str(row.get('gene', '')).strip()
            if name and gene:
                gene_sets.setdefault(name, []).append((gene, _normalise_gene(gene, case_sensitive)))
    return gene_sets


class IntersectGenesNode(BaseNode):
    """Intersect a query gene list with pathway or gene set databases."""
    NODE_ID = 'intersect_genes'
    DISPLAY_NAME = 'Intersect Genes'
    CATEGORY = 'annotation'
    DESCRIPTION = 'Intersect variant or gene lists with pathway or gene set databases.'
    SEARCH_ALIASES = ['gene set', 'pathway overlap', 'enrichment', 'intersect', 'genes']
    RETURN_TYPES = ('TSV', 'JSON')
    RETURN_NAMES = ('overlap', 'enrichment')
    REQUIRES_EXTERNAL_TOOLS = False
    DOCUMENTATION_URL = 'https://en.wikipedia.org/wiki/Gene_set_enrichment_analysis'
    VERSION = '1.0.0'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_genes': ('FILE', {'description': 'Gene list or table containing query genes'}), 'database': ('FILE', {'description': 'Gene set database as JSON or gene_set/gene table'})}, 'optional': {'input_column': ('STRING', {'default': '', 'description': 'Column name when input_genes is a table'}), 'database_format': ('STRING', {'default': 'auto', 'options': ['auto', 'json', 'tsv', 'csv']}), 'case_sensitive': ('BOOLEAN', {'default': False})}, 'hidden': {}}

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop('context', None)
        case_sensitive = bool(kwargs.get('case_sensitive', False))
        query_genes = _read_gene_query(kwargs['input_genes'], str(kwargs.get('input_column', '')), case_sensitive)
        gene_sets = _read_gene_sets(kwargs['database'], str(kwargs.get('database_format', 'auto')), case_sensitive)
        query_index = {normalised: original for original, normalised in query_genes}
        overlap_rows: list[dict[str, str]] = []
        enrichment_sets: list[dict[str, Any]] = []
        for gene_set, genes in gene_sets.items():
            matched: list[str] = []
            seen: set[str] = set()
            for _source_gene, normalised in genes:
                if normalised in query_index and normalised not in seen:
                    seen.add(normalised)
                    matched.append(query_index[normalised])
            for gene in matched:
                overlap_rows.append({'gene': gene, 'gene_set': gene_set})
            if matched:
                enrichment_sets.append({'gene_set': gene_set, 'overlap_count': len(matched), 'set_size': len({normalised for _gene, normalised in genes if normalised}), 'genes': matched})
        enrichment_sets.sort(key=lambda item: (-item['overlap_count'], item['gene_set']))
        out_dir = _annotation_node_output_dir(self, context)
        overlap_path = out_dir / 'overlap.tsv'
        enrichment_path = out_dir / 'enrichment.json'
        with overlap_path.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=['gene', 'gene_set'], delimiter='\t')
            writer.writeheader()
            writer.writerows(overlap_rows)
        enrichment_path.write_text(json.dumps({'query_gene_count': len(query_genes), 'overlap_gene_count': len({row['gene'] for row in overlap_rows}), 'sets': enrichment_sets}, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        return (str(overlap_path), str(enrichment_path))
