"""format — data_transform node(s). One tool per file (extracted from data_transform.py)."""
from __future__ import annotations
import ast
import csv
import json
import math
import operator
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable
from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import _shell_join
from bionodulo.nodes.types import file_extension_for
def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, 'node_dir', '.') if context else '.')
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir
def _delimiter(value: str, path: str | Path | None=None) -> str:
    mode = (value or 'auto').strip().lower()
    if mode == 'csv':
        return ','
    if mode == 'tsv':
        return '\t'
    if path and str(path).lower().endswith('.csv'):
        return ','
    return '\t'
def _read_table(path: str | Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open(newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f'Table has no header row: {path}')
        return (list(reader.fieldnames), [dict(row) for row in reader])
def _write_table(path: Path, fieldnames: list[str], rows: list[dict[str, Any]], delimiter: str) -> None:
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=delimiter, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _format_scalar(row.get(name, '')) for name in fieldnames})
def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or '').split(',') if item.strip()]
def _parse_rename_map(value: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in _split_csv(value):
        if ':' not in item:
            raise ValueError(f'Rename entry must be old:new, got {item!r}')
        old, new = item.split(':', 1)
        old = old.strip()
        new = new.strip()
        if not old or not new:
            raise ValueError(f'Rename entry must be old:new, got {item!r}')
        mapping[old] = new
    return mapping
def _format_scalar(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
def _as_number(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    return float(str(value).strip())
def _normalise_table_format(value: str, path: str | Path | None=None) -> str:
    requested = str(value or 'auto').strip().lower()
    if requested == 'auto':
        suffixes = ''.join(Path(str(path)).suffixes).lower() if path else ''
        if suffixes.endswith('.json'):
            return 'json'
        if suffixes.endswith('.csv'):
            return 'csv'
        return 'tsv'
    if requested not in {'csv', 'tsv', 'json'}:
        raise ValueError(f'Unsupported table format: {value}')
    return requested
def _fieldnames_from_records(records: list[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            name = str(key)
            if name not in seen:
                seen.add(name)
                fieldnames.append(name)
    return fieldnames
def _read_records(path: str | Path, input_format: str) -> list[dict[str, Any]]:
    if input_format in {'csv', 'tsv'}:
        _fieldnames, rows = _read_table(path, ',' if input_format == 'csv' else '\t')
        return rows
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(payload, dict) and isinstance(payload.get('rows'), list):
        payload = payload['rows']
    elif isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not all((isinstance(item, dict) for item in payload)):
        raise ValueError('JSON input must be an object, a list of objects, or an object with a rows list')
    return [dict(item) for item in payload]
def _write_records(path: Path, output_format: str, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == 'json':
        path.write_text(json.dumps(records, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
        return
    fieldnames = _fieldnames_from_records(records)
    _write_table(path, fieldnames, records, ',' if output_format == 'csv' else '\t')
def _fasta_header(value: Any) -> str:
    header = re.sub('\\s+', '_', str(value or '').strip())
    header = re.sub('[^A-Za-z0-9_.|:-]', '_', header)
    return header or 'sequence'
def _fasta_sequence(value: Any) -> str:
    return re.sub('\\s+', '', str(value or '')).upper()
def _wrap_sequence(sequence: str, line_width: int) -> list[str]:
    if line_width <= 0:
        return [sequence]
    return [sequence[index:index + line_width] for index in range(0, len(sequence), line_width)]


class FormatConverterNode(BaseNode):
    """Convert table records in-process and bio formats with standard tools."""
    NODE_ID = 'format_converter'
    DISPLAY_NAME = 'Format Converter'
    CATEGORY = 'data_transform'
    DESCRIPTION = 'Convert table records between CSV, TSV, and JSON, or convert common bioinformatics formats with samtools, bcftools, gffread, and seqtk.'
    SEARCH_ALIASES = ['format', 'convert', 'converter', 'csv', 'tsv', 'json', 'table', 'convert format', 'bam to cram', 'vcf to bcf', 'gff to gtf', 'fastq to fasta', 'samtools convert', 'bcftools convert', 'file converter']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('converted_file',)
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ['samtools', 'bcftools', 'gffread', 'seqtk']
    REQUIRED_CONDA_PACKAGES = ['samtools', 'bcftools', 'gffread', 'seqtk']
    _EXTENSIONS = {'csv': '.csv', 'tsv': '.tsv', 'json': '.json'}
    _TABLE_FORMATS = {'csv', 'tsv', 'json'}
    _ALIGNMENT_FORMATS = {'SAM', 'BAM', 'CRAM'}
    _VARIANT_FORMATS = {'VCF', 'VCF_GZ', 'BCF'}
    _ANNOTATION_FORMATS = {'GFF', 'GTF'}
    _SEQUENCE_FORMATS = {'FASTQ', 'FASTA'}
    _BIO_FORMATS = _ALIGNMENT_FORMATS | _VARIANT_FORMATS | _ANNOTATION_FORMATS | _SEQUENCE_FORMATS
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('BAM,CRAM,SAM,VCF,VCF_GZ,BCF,GFF,GTF,FASTQ,FASTA,CSV,TSV,JSON', {'description': 'Input table or bioinformatics file'}), 'output_format': ('STRING', {'default': 'tsv', 'options': ['csv', 'tsv', 'json', 'SAM', 'BAM', 'CRAM', 'VCF', 'VCF_GZ', 'BCF', 'GFF', 'GTF', 'FASTQ', 'FASTA']})}, 'optional': {'input_format': ('STRING', {'default': 'auto', 'options': ['auto', 'csv', 'tsv', 'json']}), 'reference': ('FASTA,FASTA_INDEX', {'default': '', 'description': 'Reference FASTA required for CRAM output'}), 'compression_level': ('INT', {'default': 6, 'min': 0, 'max': 9}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {}), 'output_dir': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        output_format_raw = str(inputs.get('output_format', 'tsv'))
        output_format = cls._normalise_format_name(output_format_raw)
        if output_format in cls._TABLE_FORMATS:
            return True
        if output_format not in cls._BIO_FORMATS:
            return f'Unsupported output format: {output_format_raw}'
        input_format = cls._infer_bio_format(inputs.get('input_file', ''), inputs.get('input_format', 'auto'))
        if input_format is None:
            return 'Bio format conversion requires a recognised input file extension or input_format'
        if not cls._conversion_supported(input_format, output_format):
            return f'Cannot convert {input_format} to {output_format} with format_converter'
        if output_format == 'CRAM' and (not str(inputs.get('reference', '') or '').strip()):
            return 'reference is required for CRAM output'
        try:
            compression_level = int(inputs.get('compression_level', 6))
        except (TypeError, ValueError):
            return 'compression_level must be an integer'
        if not 0 <= compression_level <= 9:
            return 'compression_level must be between 0 and 9'
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be at least 1'
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_dir = Path(output_dir)
        node_out = output_dir / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        output_format = cls._normalise_format_name(str(inputs.get('output_format', 'tsv')))
        return [node_out / cls._output_filename(inputs, output_format)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_format = cls._normalise_format_name(str(inputs.get('output_format', 'tsv')))
        output = Path(str(inputs.get('output', inputs.get('output_dir', '.'))))
        input_file = str(inputs.get('input_file', ''))
        output_path = output / cls._output_filename(inputs, output_format)
        threads = str(int(inputs.get('threads', 1)))
        compression_level = str(int(inputs.get('compression_level', 6)))
        if output_format in cls._ALIGNMENT_FORMATS:
            cmd = ['samtools', 'view', '-@', threads]
            if output_format == 'BAM':
                cmd.extend(['-b', '-l', compression_level])
            elif output_format == 'CRAM':
                cmd.extend(['-C', '-l', compression_level])
                reference = str(inputs.get('reference', '') or '').strip()
                if reference:
                    cmd.extend(['-T', reference])
            elif output_format == 'SAM':
                cmd.append('-h')
            cmd.extend(['-o', str(output_path), input_file])
            return cmd
        if output_format in cls._VARIANT_FORMATS:
            out_flag = {'VCF': '-Ov', 'VCF_GZ': '-Oz', 'BCF': '-Ob'}[output_format]
            return ['bcftools', 'view', '--threads', threads, out_flag, '-o', str(output_path), input_file]
        if output_format in cls._ANNOTATION_FORMATS:
            cmd = ['gffread', input_file]
            if output_format == 'GTF':
                cmd.append('-T')
            cmd.extend(['-o', str(output_path)])
            return cmd
        if output_format in cls._SEQUENCE_FORMATS:
            cmd = ['seqtk', 'seq']
            if output_format == 'FASTA':
                cmd.append('-A')
            cmd.extend([input_file, '>', str(output_path)])
            return cmd
        raise ValueError(f'Unsupported command output format: {output_format}')

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop('context', None)
        input_file = Path(str(kwargs['input_file']))
        output_format_raw = str(kwargs.get('output_format', 'tsv'))
        output_format = self._normalise_format_name(output_format_raw)
        if output_format not in self._TABLE_FORMATS:
            output_dir = Path(getattr(context, 'node_dir', '.') if context else '.')
            output_path = self.PLAN_OUTPUTS(kwargs, output_dir)[0]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            kwargs['output'] = str(output_path.parent)
            kwargs['output_dir'] = str(output_path.parent)
            validation = self.VALIDATE_INPUTS(kwargs)
            if validation is not True:
                raise ValueError(f'Input validation failed: {validation}')
            cmd = self.render_command(kwargs)
            rendered_cmd: str | list[str] = _shell_join(cmd) if self.SHELL else cmd
            if context is not None and hasattr(context, 'run_command'):
                result = await context.run_command(rendered_cmd, cwd=output_dir)
            else:
                from bionodulo.execution.subprocess_runner import run_subprocess
                result = await run_subprocess(rendered_cmd, cwd=output_dir, stdout_path=output_path.parent / 'stdout.log', stderr_path=output_path.parent / 'stderr.log')
            if result.get('returncode', 0) != 0:
                stderr = result.get('stderr', '')
                raise RuntimeError(f'Format conversion failed: {stderr[:500]}')
            return (str(output_path),)
        input_format = _normalise_table_format(str(kwargs.get('input_format', 'auto')), input_file)
        records = _read_records(input_file, input_format)
        output_stem = str(kwargs.get('output_name', '') or '').strip() or input_file.stem
        output_name = f'{Path(output_stem).stem}{self._EXTENSIONS[output_format]}'
        output_path = _node_output_dir(self, context) / output_name
        _write_records(output_path, output_format, records)
        return (str(output_path),)

    @classmethod
    def _normalise_format_name(cls, value: str) -> str:
        cleaned = str(value or '').strip()
        lower = cleaned.lower()
        if lower in cls._TABLE_FORMATS:
            return lower
        return cleaned.upper()

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any], output_format: str) -> str:
        input_file = Path(str(inputs.get('input_file', cls.NODE_ID)))
        output_stem = str(inputs.get('output_name', '') or '').strip()
        if output_stem:
            stem = re.sub('[^A-Za-z0-9_.-]+', '_', Path(output_stem).stem).strip('._') or cls.NODE_ID
        else:
            stem = cls._clean_input_stem(input_file)
            if output_format not in cls._TABLE_FORMATS:
                stem = f'{stem}.to_{output_format.lower()}'
        extension = cls._EXTENSIONS.get(output_format, file_extension_for(output_format))
        return f'{stem}{extension}'

    @staticmethod
    def _clean_input_stem(path: Path) -> str:
        name = path.name
        for suffix in ('.fastq.gz', '.fq.gz', '.vcf.gz', '.gff3.gz', '.gtf.gz'):
            if name.lower().endswith(suffix):
                return name[:-len(suffix)]
        stem = path.stem
        if stem.endswith('.vcf'):
            return stem[:-4]
        return stem

    @classmethod
    def _infer_bio_format(cls, input_file: Any, input_format: Any='auto') -> str | None:
        requested = cls._normalise_format_name(str(input_format or 'auto'))
        if requested != 'AUTO' and requested not in cls._TABLE_FORMATS:
            return requested
        name = str(input_file or '').lower()
        if name.endswith(('.sam', '.sam.gz')):
            return 'SAM'
        if name.endswith(('.bam', '.bam.gz')):
            return 'BAM'
        if name.endswith(('.cram', '.cram.gz')):
            return 'CRAM'
        if name.endswith('.vcf.gz'):
            return 'VCF_GZ'
        if name.endswith('.vcf'):
            return 'VCF'
        if name.endswith('.bcf'):
            return 'BCF'
        if name.endswith(('.gff', '.gff3', '.gff.gz', '.gff3.gz')):
            return 'GFF'
        if name.endswith(('.gtf', '.gtf.gz')):
            return 'GTF'
        if name.endswith(('.fastq', '.fq', '.fastq.gz', '.fq.gz')):
            return 'FASTQ'
        if name.endswith(('.fasta', '.fa', '.fna', '.faa', '.fasta.gz', '.fa.gz', '.fna.gz', '.faa.gz')):
            return 'FASTA'
        return None

    @classmethod
    def _conversion_supported(cls, input_format: str, output_format: str) -> bool:
        if input_format == output_format:
            return True
        groups = (cls._ALIGNMENT_FORMATS, cls._VARIANT_FORMATS, cls._ANNOTATION_FORMATS, cls._SEQUENCE_FORMATS)
        return any((input_format in group and output_format in group for group in groups))
