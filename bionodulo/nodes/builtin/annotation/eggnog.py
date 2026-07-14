"""eggnog — annotation node(s). One tool per file (extracted from annotation.py)."""
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


class EggNOGMapperNode(CommandNode):
    """Functional annotation with eggNOG-mapper."""
    NODE_ID = 'eggnog_mapper'
    DISPLAY_NAME = 'eggNOG-mapper'
    CATEGORY = 'annotation'
    DESCRIPTION = 'Fast genome-wide functional annotation via orthology'
    SEARCH_ALIASES = ['eggnog', 'emapper', 'functional', 'cog', 'go']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('annotations',)
    REQUIRED_EXECUTABLES = ['emapper.py']
    REQUIRED_CONDA_PACKAGES = ['eggnog-mapper']
    DOCUMENTATION_URL = 'https://github.com/eggnogdb/eggnog-mapper'
    VERSION = '2.1.14'
    COMMAND = ['emapper.py', '-i', '{inputs.proteins}', '--output', '{inputs.prefix}', '--output_dir', '{output}', '-m', '{inputs.mode}', '--cpu', '{inputs.threads}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'proteins': ('FASTA', {'description': 'Protein FASTA file (.faa)'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'}), 'prefix': ('STRING', {'default': 'annotations'})}, 'optional': {'mode': ('STRING', {'default': 'diamond', 'description': 'Search mode: diamond, mmseqs, or hmmer'}), 'data_dir': ('DIRECTORY', {'description': 'eggNOG data directory'}), 'itype': ('STRING', {'default': 'proteins', 'options': ['proteins', 'CDS', 'genome', 'metagenome'], 'label': 'Input Type', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['emapper.py', '-i', str(inputs.get('proteins', '')), '--output', str(inputs.get('prefix', 'annotations')), '--output_dir', str(inputs.get('output', '.')), '-m', str(inputs.get('mode', 'diamond')), '--cpu', str(inputs.get('threads', 8))]
        if inputs.get('data_dir'):
            cmd.extend(['--data_dir', str(inputs['data_dir'])])
        if inputs.get('itype'):
            cmd.extend(['--itype', str(inputs['itype'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        prefix = inputs.get('prefix', 'annotations')
        od = Path(output_dir)
        return [od / cls.NODE_ID / f'{prefix}.annotations.tsv']

    async def run(self, **kwargs: Any) -> Any:
        """Run eggNOG-mapper and copy annotations to planned path."""
        result = await super().run(**kwargs)
        import shutil
        from pathlib import Path
        node_out = Path(kwargs['output_dir'])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get('prefix', 'annotations')
        if outputs:
            outputs[0].parent.mkdir(parents=True, exist_ok=True)
            actual = node_out / f'{prefix}.annotations'
            if actual.exists():
                shutil.copy2(str(actual), str(outputs[0]))
        return result
