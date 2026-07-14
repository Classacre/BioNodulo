"""trim — trimming node(s). One tool per file (extracted from trimming.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _read_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    return [text] if text else []
def _fastq_stem(value: Any, default: str) -> str:
    name = Path(str(value or default)).name
    for suffix in ('.fastq.gz', '.fq.gz', '.fastq', '.fq', '.gz'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return name or default


class TrimGaloreNode(CommandNode):
    """Bisulfite-aware FASTQ trimming with Trim Galore."""
    NODE_ID = 'trim_galore'
    DISPLAY_NAME = 'Trim Galore'
    REQUIRED_CONDA_PACKAGES = ['trim-galore']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Adapter and quality trimming for FASTQ reads with bisulfite-aware Trim Galore modes.'
    SEARCH_ALIASES = ['trim galore', 'trim_galore', 'bisulfite', 'rrbs', 'cutadapt', 'adapter', 'quality trim']
    RETURN_TYPES = ('FASTQ_LIST', 'HTML_REPORT')
    RETURN_NAMES = ('trimmed_reads', 'fastqc_report')
    REQUIRED_EXECUTABLES = ['trim_galore']
    DOCUMENTATION_URL = 'https://github.com/FelixKrueger/TrimGalore'
    VERSION = '0.6.10'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        reads = _read_list(inputs.get('reads'))
        paired = bool(inputs.get('paired', True))
        if paired and len(reads) != 2:
            return 'paired mode requires exactly two reads.'
        if not paired and len(reads) != 1:
            return 'single-end mode requires exactly one read.'
        if int(inputs.get('threads', 1)) < 1:
            return 'threads must be at least 1.'
        for field in ('quality', 'length', 'clip_r1', 'clip_r2', 'three_prime_clip_r1', 'three_prime_clip_r2'):
            if int(inputs.get(field, 0) or 0) < 0:
                return f'{field} must be zero or greater.'
        return True

    @classmethod
    def _trimmed_read_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        reads = _read_list(inputs.get('reads'))
        out_dir = Path(output_dir)
        paired = bool(inputs.get('paired', True))
        if paired:
            r1 = _fastq_stem(reads[0] if reads else 'R1', 'R1')
            r2 = _fastq_stem(reads[1] if len(reads) > 1 else 'R2', 'R2')
            return [out_dir / f'{r1}_val_1.fq.gz', out_dir / f'{r2}_val_2.fq.gz']
        stem = _fastq_stem(reads[0] if reads else 'reads', 'reads')
        return [out_dir / f'{stem}_trimmed.fq.gz']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output = str(inputs.get('output', inputs.get('output_dir', '.')))
        reads = _read_list(inputs.get('reads'))
        cmd = ['trim_galore']
        if inputs.get('paired', True):
            cmd.append('--paired')
        cmd.extend(['--cores', str(inputs.get('threads', 1))])
        for field, flag in (('quality', '--quality'), ('length', '--length'), ('clip_r1', '--clip_R1'), ('clip_r2', '--clip_R2'), ('three_prime_clip_r1', '--three_prime_clip_R1'), ('three_prime_clip_r2', '--three_prime_clip_R2')):
            value = int(inputs.get(field, 0) or 0)
            if value > 0:
                cmd.extend([flag, str(value)])
        if inputs.get('rrbs'):
            cmd.append('--rrbs')
        if inputs.get('non_directional'):
            cmd.append('--non_directional')
        if inputs.get('gzip', True):
            cmd.append('--gzip')
        if inputs.get('fastqc', True):
            cmd.append('--fastqc')
        cmd.extend(['-o', output])
        cmd.extend(reads)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return cls._trimmed_read_paths(inputs, node_out) + [node_out / 'fastqc_report.html']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ_LIST', {'description': 'Input FASTQ read(s); paired mode expects [R1, R2]'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 8, 'display': 'slider'})}, 'optional': {'paired': ('BOOLEAN', {'default': True, 'description': 'Run paired-end trimming'}), 'quality': ('INT', {'default': 20, 'min': 0, 'max': 40}), 'length': ('INT', {'default': 20, 'min': 0}), 'clip_r1': ('INT', {'default': 0, 'min': 0}), 'clip_r2': ('INT', {'default': 0, 'min': 0}), 'three_prime_clip_r1': ('INT', {'default': 0, 'min': 0}), 'three_prime_clip_r2': ('INT', {'default': 0, 'min': 0}), 'rrbs': ('BOOLEAN', {'default': False, 'description': 'Enable RRBS mode'}), 'non_directional': ('BOOLEAN', {'default': False, 'description': 'Enable non-directional RRBS libraries'}), 'gzip': ('BOOLEAN', {'default': True, 'description': 'Compress FASTQ outputs'}), 'fastqc': ('BOOLEAN', {'default': True, 'description': 'Run FastQC after trimming'})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run Trim Galore and return grouped trimmed FASTQ paths."""
        output_dir = kwargs.get('output_dir')
        ctx = kwargs.get('context')
        if output_dir is None and ctx is not None:
            output_dir = getattr(ctx, 'node_dir', '.')
        if output_dir is None:
            output_dir = '.'
        await super().run(**kwargs)
        out = Path(output_dir) / self.NODE_ID
        return {'outputs': {'trimmed_reads': [str(path) for path in self.__class__._trimmed_read_paths(kwargs, out)], 'fastqc_report': str(out / 'fastqc_report.html')}}
