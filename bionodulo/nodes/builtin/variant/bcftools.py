"""bcftools — variant node(s). One tool per file (extracted from annotation.py)."""
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


class BcftoolsAnnotateNode(CommandNode):
    """Annotate VCF records from BED, VCF, or TSV annotation files."""
    NODE_ID = 'bcftools_annotate'
    DISPLAY_NAME = 'BCFtools Annotate'
    CATEGORY = 'variant'
    DESCRIPTION = 'Annotate and edit VCF/BCF records using BED, tabular, VCF, or BCF annotation sources.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'bcftools', 'annotate', 'annotate vcf', 'edit vcf annotations', 'custom annotation', 'bed annotation', 'remove annotations']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('annotated_vcf',)
    REQUIRED_EXECUTABLES = ['bcftools', 'bgzip', 'tabix']
    REQUIRED_CONDA_PACKAGES = ['bcftools', 'htslib']
    DOCUMENTATION_URL = 'https://www.htslib.org/doc/bcftools.html#annotate'
    CITATION_DOIS = BCFTOOLS_CITATION_DOIS
    CITATION_URLS = BCFTOOLS_CITATION_URLS
    CITATION_TEXT = BCFTOOLS_CITATION_TEXT
    VERSION = '1.22+galaxy0'
    SHELL = True
    OUTPUT_TYPES = ['b', 'u', 'z', 'v']
    ANNOTATION_FORMATS = ['none', 'vcf', 'tab']

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output', inputs.get('output_dir', '.')))

    @classmethod
    def _input_file(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_file', inputs.get('vcf', '')))

    @classmethod
    def _annotations(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('annotations', inputs.get('annotation_file', '')))

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return {'b': '.bcf', 'u': '.bcf', 'z': '.vcf.gz', 'v': '.vcf'}.get(str(inputs.get('output_type', 'z') or 'z'), '.vcf.gz')

    @classmethod
    def _annotation_format(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get('annotation_format', '') or '').strip()
        if value:
            return value
        annotations = cls._annotations(inputs)
        if not annotations:
            return 'none'
        suffixes = ''.join(Path(annotations).suffixes).lower()
        if suffixes.endswith(('.vcf', '.vcf.gz', '.bcf')):
            return 'vcf'
        return 'tab'

    @classmethod
    def _add_if_value(cls, cmd: list[str], flag: str, value: Any) -> None:
        if value is not None and str(value) != '':
            cmd.extend([flag, str(value)])

    @classmethod
    def _annotation_prep(cls, inputs: dict[str, Any], out: str) -> tuple[list[str], str, str]:
        annotation_format = cls._annotation_format(inputs)
        annotations = cls._annotations(inputs)
        if annotation_format == 'none':
            return ([], '', '')
        if annotation_format == 'vcf':
            if annotations.endswith('.bcf'):
                prepared = f'{out}/annotations.bcf'
                return (['ln', '-s', annotations, prepared, '&&', 'bcftools', 'index', prepared, '&&'], prepared, '')
            prepared = f'{out}/annotations.vcf.gz'
            return (['bgzip', '-c', annotations, '>', prepared, '&&', 'bcftools', 'index', prepared, '&&'], prepared, '')
        if annotations.endswith('.bed') or annotations.endswith('.bed.gz'):
            prepared = f'{out}/annotations.bed.gz'
            prep = ['bgzip', '-c', annotations, '>', prepared, '&&', 'tabix', '-s', '1', '-b', '2', '-e', '3', prepared, '&&']
            return (prep, prepared, '')
        prepared = f'{out}/annotations.tab.gz'
        prep = ['bgzip', '-c', annotations, '>', prepared, '&&', 'tabix', '-s', '1', '-b', '2', '-e', '2', prepared, '&&']
        return (prep, prepared, '')

    @classmethod
    def _annotate_cmd(cls, inputs: dict[str, Any], prepared_annotations: str, header_path: str) -> list[str]:
        cmd = ['bcftools', 'annotate']
        columns = inputs.get('columns', inputs.get('annotation_columns'))
        header_lines = str(inputs.get('header_lines', '') or '')
        header_file = header_path or inputs.get('header_file')
        if not header_file and header_lines and Path(header_lines).suffix:
            header_file = header_lines
        cls._add_if_value(cmd, '--columns', columns)
        cls._add_if_value(cmd, '--annotations', prepared_annotations)
        cls._add_if_value(cmd, '--header-lines', header_file)
        cls._add_if_value(cmd, '--set-id', inputs.get('set_id'))
        cls._add_if_value(cmd, '--mark-sites', inputs.get('mark_sites'))
        cls._add_if_value(cmd, '--min-overlap', inputs.get('min_overlap'))
        cls._add_if_value(cmd, '--rename-chrs', inputs.get('rename_chrs'))
        cls._add_if_value(cmd, '--remove', inputs.get('remove'))
        cls._add_if_value(cmd, '--rename-annots', inputs.get('rename_annots'))
        cls._add_if_value(cmd, '--collapse', inputs.get('collapse'))
        cls._add_if_value(cmd, '--regions', inputs.get('regions'))
        cls._add_if_value(cmd, '--regions-overlap', inputs.get('regions_overlap'))
        cls._add_if_value(cmd, '--targets', inputs.get('targets'))
        cls._add_if_value(cmd, '--targets-overlap', inputs.get('targets_overlap'))
        samples = inputs.get('samples')
        if samples is not None and str(samples) != '':
            prefix = '^' if inputs.get('invert_samples') else ''
            cmd.extend(['--samples', f'{prefix}{samples}'])
        samples_file = inputs.get('samples_file')
        if samples_file is not None and str(samples_file) != '':
            prefix = '^' if inputs.get('invert_samples_file') else ''
            cmd.extend(['--samples-file', f'{prefix}{samples_file}'])
        cls._add_if_value(cmd, '--include', inputs.get('include'))
        cls._add_if_value(cmd, '--exclude', inputs.get('exclude'))
        cmd.extend(['--output-type', str(inputs.get('output_type', 'z') or 'z')])
        threads = inputs.get('threads')
        if threads not in (None, '', 0, '0'):
            cmd.extend(['--threads', str(threads)])
        cmd.append(cls._input_file(inputs))
        cmd.extend(['>', f'{cls._out(inputs)}/annotated{cls._output_suffix(inputs)}'])
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str | list[str]:
        out = cls._out(inputs)
        prep, prepared_annotations, _ = cls._annotation_prep(inputs, out)
        header_lines = str(inputs.get('header_lines', '') or '')
        header_path = ''
        if header_lines and (not Path(header_lines).suffix):
            header_path = f'{out}/annotation.hdr'
            header_write = f"cat > {header_path} <<'EOF'\n{header_lines}\nEOF\n"
            return header_write + _shell_join([*prep, *cls._annotate_cmd(inputs, prepared_annotations, header_path)])
        cmd = [*prep, *cls._annotate_cmd(inputs, prepared_annotations, header_path)]
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / f'annotated{cls._output_suffix(inputs)}']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._input_file(inputs).strip():
            return 'input_file is required'
        annotation_format = cls._annotation_format(inputs)
        if annotation_format not in cls.ANNOTATION_FORMATS:
            return f"annotation_format must be one of: {', '.join(cls.ANNOTATION_FORMATS)}"
        if annotation_format in {'vcf', 'tab'} and (not cls._annotations(inputs).strip()):
            return f'annotations is required when annotation_format is {annotation_format}'
        columns = str(inputs.get('columns', inputs.get('annotation_columns', '')) or '').strip()
        if annotation_format in {'vcf', 'tab'} and (not columns):
            return f'columns is required when annotation_format is {annotation_format}'
        output_type = str(inputs.get('output_type', 'z') or 'z')
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('VCF', {'description': 'VCF/BCF file to annotate or edit'})}, 'optional': {'annotation_format': ('STRING', {'default': 'none', 'options': cls.ANNOTATION_FORMATS, 'description': 'Annotation source type'}), 'annotations': ('FILE', {'default': '', 'description': 'BED, tab-delimited, VCF, or BCF annotations'}), 'columns': ('STRING', {'default': '', 'description': 'Annotation columns such as CHROM,POS,REF,ALT,INFO/TAG'}), 'header_file': ('FILE', {'description': 'Header lines file to append to the output VCF'}), 'header_lines': ('STRING', {'default': '', 'description': 'Inline VCF header lines to append'}), 'set_id': ('STRING', {'default': '', 'description': 'Set variant IDs from a bcftools expression'}), 'mark_sites': ('STRING', {'default': '', 'description': 'Flag sites present or absent from the annotation file'}), 'min_overlap': ('STRING', {'default': '', 'description': 'Minimum overlap for annotation intersections'}), 'rename_chrs': ('TSV', {'description': 'Map old chromosome names to new names'}), 'remove': ('STRING', {'default': '', 'description': 'Annotations to remove, such as INFO, FORMAT, or INFO/TAG'}), 'rename_annots': ('TSV', {'description': 'Rename FILTER, INFO, or FORMAT annotations'}), 'collapse': ('STRING', {'default': '', 'options': ['', 'snps', 'indels', 'both', 'some', 'any', 'none', 'id']}), 'regions': ('STRING', {'default': '', 'description': 'Restrict to regions'}), 'regions_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy regions-overlap mode'}), 'targets': ('STRING', {'default': '', 'description': 'Restrict to targets'}), 'targets_overlap': ('STRING', {'default': '', 'options': ['', '0', '1', '2'], 'description': 'Galaxy targets-overlap mode'}), 'samples': ('STRING', {'default': '', 'description': 'Comma-separated samples to include or exclude'}), 'invert_samples': ('BOOLEAN', {'default': False, 'description': 'Exclude the samples listed in samples'}), 'samples_file': ('TSV', {'description': 'File of samples to include or exclude'}), 'invert_samples_file': ('BOOLEAN', {'default': False, 'description': 'Exclude samples listed in samples_file'}), 'include': ('STRING', {'default': '', 'description': 'Include-expression filter'}), 'exclude': ('STRING', {'default': '', 'description': 'Exclude-expression filter'}), 'output_type': ('STRING', {'default': 'z', 'options': cls.OUTPUT_TYPES, 'description': 'BCFtools output type'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'}), 'vcf': ('VCF_GZ', {'description': 'Compatibility alias for input_file', 'advanced': True}), 'annotation_columns': ('STRING', {'default': '', 'description': 'Compatibility alias for columns', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
