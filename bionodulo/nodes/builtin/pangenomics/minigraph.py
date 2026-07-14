"""minigraph — pangenomics node(s). One tool per file (extracted from pangenomics.py)."""
from __future__ import annotations
from pathlib import Path
import re
import shlex
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _split_path_list(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item)]
    return [item for item in re.split('[\\s,]+', str(value or '')) if item]
def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub('\\.(gz|bz2|xz|zip)$', '', stem)
    stem = re.sub('[^A-Za-z0-9_.-]+', '_', stem).strip('._-')
    return stem or fallback


class MinigraphNode(CommandNode):
    """Construct or align pangenome graphs with minigraph."""
    NODE_ID = 'minigraph'
    DISPLAY_NAME = 'Minigraph'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Fast sequence-to-graph aligner and pangenome constructor for large genomes.'
    SEARCH_ALIASES = ['minigraph', 'graph align', 'pangenome', 'sv graph', 'sequence to graph']
    RETURN_TYPES = ('GFA',)
    RETURN_NAMES = ('output_gfa',)
    REQUIRED_EXECUTABLES = ['minigraph']
    REQUIRED_CONDA_PACKAGES = ['minigraph']
    DOCUMENTATION_URL = 'https://github.com/lh3/minigraph'
    VERSION = '0.21'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        mode = inputs.get('mode', 'construct')
        threads = str(inputs.get('threads', 8))
        if mode == 'construct':
            cmd = ['minigraph', '-cxggs', '-t', threads]
            if inputs.get('preset'):
                cmd.extend(['-x', str(inputs['preset'])])
            assemblies = inputs.get('assemblies', [])
            if isinstance(assemblies, list | tuple):
                cmd.extend((str(assembly) for assembly in assemblies if assembly))
            elif assemblies:
                cmd.append(str(assemblies))
        else:
            cmd = ['minigraph', '-cx', str(inputs.get('preset', 'ggs')), '-t', threads, str(inputs.get('graph_gfa', '')), str(inputs.get('query_fasta', ''))]
        cmd.extend(['>', str(out_dir / 'output_gfa.gfa')])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'output_gfa.gfa']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mode': ('STRING', {'default': 'construct', 'options': ['construct', 'align']}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64})}, 'optional': {'assemblies': ('FASTA', {'description': 'Assemblies (first=reference)'}), 'graph_gfa': ('GFA', {'description': 'Graph GFA (for align mode)'}), 'query_fasta': ('FASTA', {'description': 'Query FASTA (for align mode)'}), 'preset': ('STRING', {'default': 'ggs', 'options': ['ggs', 'asm', 'ggsa']})}, 'hidden': {'output': ('STRING', {})}}


class MinigraphCactusNode(CommandNode):
    """Build pangenome graphs from multiple assemblies with Minigraph-Cactus."""
    NODE_ID = 'minigraph_cactus'
    DISPLAY_NAME = 'Minigraph-Cactus'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Build pangenome graphs from assemblies using the Cactus Minigraph-Cactus pipeline.'
    SEARCH_ALIASES = ['minigraph-cactus', 'cactus-pangenome', 'HPRC', 'pangenome construction', 'whole-genome alignment', 'giraffe']
    RETURN_TYPES = ('GBZ', 'VCF_GZ', 'GFA', 'ODGI')
    RETURN_NAMES = ('graph_gbz', 'variants_vcf', 'graph_gfa', 'graph_odgi')
    REQUIRED_EXECUTABLES = ['cactus-pangenome']
    REQUIRED_CONDA_PACKAGES = ['cactus']
    DOCUMENTATION_URL = 'https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/pangenome.md'
    VERSION = '2.9.0'
    _OUTPUT_FLAGS = ('gbz', 'vcf', 'gfa', 'odgi')

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if int(inputs.get('threads', 1) or 0) <= 0:
            return 'Minigraph-Cactus threads must be greater than zero.'
        if not any((bool(inputs.get(flag, False)) for flag in cls._OUTPUT_FLAGS)):
            return 'Minigraph-Cactus requires at least one graph or variant output flag.'
        return True

    @classmethod
    def _out_name(cls, inputs: dict[str, Any]) -> str:
        return _safe_output_stem(inputs.get('out_name'), 'pangenome')

    @classmethod
    def _work_dir(cls, inputs: dict[str, Any], out_dir: Path) -> Path:
        if inputs.get('work_dir'):
            return Path(str(inputs['work_dir']))
        return out_dir / 'work'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        work_dir = cls._work_dir(inputs, out_dir)
        max_cores = int(inputs.get('max_cores', 0) or 0)
        if max_cores <= 0:
            max_cores = int(inputs.get('threads', 1) or 1)
        cmd = ['cactus-pangenome', str(work_dir), str(inputs.get('seq_file', '')), '--outDir', str(out_dir), '--outName', cls._out_name(inputs), '--reference', str(inputs.get('reference', '')), '--maxCores', str(max_cores)]
        cons_batch_size = int(inputs.get('cons_batch_size', 0) or 0)
        if cons_batch_size > 0:
            cmd.extend(['--batchSize', str(cons_batch_size)])
        for flag in ('gbz', 'giraffe', 'vcf', 'gfa', 'odgi', 'viz'):
            if inputs.get(flag):
                cmd.append(f'--{flag}')
        if inputs.get('chrom_vg'):
            cmd.append('--chrom-vg')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        out_name = cls._out_name(inputs)
        return [node_out / f'{out_name}.gbz', node_out / f'{out_name}.vcf.gz', node_out / f'{out_name}.gfa.gz', node_out / f'{out_name}.og']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'seq_file': ('FILE', {'description': 'Cactus seqFile listing assembly names and FASTA paths'}), 'reference': ('STRING', {'description': 'Reference genome name from the seqFile'})}, 'optional': {'out_name': ('STRING', {'default': 'pangenome', 'description': 'Output filename prefix'}), 'work_dir': ('STRING', {'default': '', 'description': 'Optional Cactus working directory'}), 'threads': ('INT', {'default': 16, 'min': 1, 'max': 512, 'display': 'slider'}), 'max_cores': ('INT', {'default': 0, 'min': 0, 'max': 512, 'display': 'slider'}), 'cons_batch_size': ('INT', {'default': 0, 'min': 0, 'max': 100000}), 'gbz': ('BOOLEAN', {'default': True}), 'giraffe': ('BOOLEAN', {'default': True}), 'vcf': ('BOOLEAN', {'default': True}), 'gfa': ('BOOLEAN', {'default': True}), 'odgi': ('BOOLEAN', {'default': False}), 'viz': ('BOOLEAN', {'default': False}), 'chrom_vg': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}
