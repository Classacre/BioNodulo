"""pggb — pangenomics node(s). One tool per file (extracted from pangenomics.py)."""
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


class PGGBNode(CommandNode):
    """Build reference-free pangenome graphs with PGGB."""
    NODE_ID = 'pggb'
    DISPLAY_NAME = 'PGGB Build'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Reference-free pangenome graph builder via all-vs-all WGA. Produces GFA, ODGI, VCF.'
    SEARCH_ALIASES = ['pggb', 'pangenome graph builder', 'wga', 'all-vs-all', 'graph construction']
    RETURN_TYPES = ('GFA', 'FASTA')
    RETURN_NAMES = ('smooth_gfa', 'consensus_fasta')
    REQUIRED_EXECUTABLES = ['pggb']
    REQUIRED_CONDA_PACKAGES = ['pggb', 'samtools']
    DOCUMENTATION_URL = 'https://github.com/pangenome/pggb'
    VERSION = '0.7.3'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_fasta = str(inputs.get('input_fasta', ''))
        pggb_args = ['pggb', '-i', input_fasta, '-o', str(inputs.get('output', '.')), '-n', str(inputs.get('num_haplotypes', 2)), '-t', str(inputs.get('threads', 16)), '-p', str(inputs.get('map_pct_id', 90)), '-s', str(inputs.get('segment_length', 5000)), '-k', str(inputs.get('min_match_length', 19)), '-G', str(inputs.get('graph_poas', 2))]
        if inputs.get('consensus_spec'):
            pggb_args.extend(['-C', str(inputs['consensus_spec'])])
        faidx = ' '.join(['samtools', 'faidx', shlex.quote(input_fasta)])
        run = ' '.join((shlex.quote(a) if ' ' in a else a for a in pggb_args))
        out_dir = str(inputs.get('output', '.'))
        out_q = shlex.quote(out_dir)
        gfa_glob = f'{out_q}/*.smooth.final.gfa'
        smooth_gfa = f'{out_q}/smooth_gfa.gfa'
        consensus_fa = f'{out_q}/consensus_fasta.fa'
        normalise = f"""g=$(ls {gfa_glob} 2>/dev/null | head -1); if [ -n "$g" ]; then cp "$g" {smooth_gfa}; fi; if [ ! -s {consensus_fa} ] && [ -s {smooth_gfa} ]; then awk '/^S/{{print ">seg"$2"\\n"$3}}' {smooth_gfa} > {consensus_fa}; fi"""
        return 'bash -c ' + shlex.quote(f'{faidx} && {run} && {normalise}')

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'smooth_gfa.gfa', node_out / 'consensus_fasta.fa']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_fasta': ('FASTA', {'description': 'Multi-sequence FASTA with all haplotypes'}), 'num_haplotypes': ('INT', {'default': 2, 'min': 2}), 'threads': ('INT', {'default': 16, 'min': 1, 'max': 128})}, 'optional': {'map_pct_id': ('INT', {'default': 90, 'min': 50, 'max': 100}), 'segment_length': ('INT', {'default': 5000, 'min': 1000}), 'min_match_length': ('INT', {'default': 19, 'min': 1}), 'graph_poas': ('INT', {'default': 2, 'min': 1, 'max': 8}), 'consensus_spec': ('STRING', {'default': '', 'description': "Consensus spec (e.g., '100,1000,10000')"}), 'do_viz': ('BOOLEAN', {'default': True}), 'do_layout': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}


class PGGBBuildNode(CommandNode):
    """Construct pangenome graph outputs from multiple haplotype FASTA files."""
    NODE_ID = 'pggb_build'
    DISPLAY_NAME = 'PGGB Build'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Construct pangenome graph from multiple haplotypes using PGGB.'
    SEARCH_ALIASES = ['pggb', 'haplotypes', 'pangenome graph', 'graph construction', 'odgi']
    RETURN_TYPES = ('GFA', 'ODGI')
    RETURN_NAMES = ('graph_gfa', 'graph_odgi')
    REQUIRED_EXECUTABLES = ['pggb']
    REQUIRED_CONDA_PACKAGES = ['pggb']
    DOCUMENTATION_URL = 'https://github.com/pangenome/pggb'
    VERSION = '0.7.3'
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if len(_split_path_list(inputs.get('input_fasta'))) < 2:
            return 'PGGB Build requires at least two haplotype FASTA files.'
        if int(inputs.get('threads', 1) or 0) <= 0:
            return 'PGGB Build threads must be greater than zero.'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        haplotypes = out_dir / 'haplotypes.fa'
        pggb_dir = out_dir / 'pggb'
        graph_gfa = out_dir / 'graph_gfa.gfa'
        graph_odgi = out_dir / 'graph_odgi.odgi'
        fasta_paths = _split_path_list(inputs.get('input_fasta'))
        return ['cat', *fasta_paths, '>', str(haplotypes), '&&', 'pggb', '-i', str(haplotypes), '-o', str(pggb_dir), '-n', str(len(fasta_paths)), '-t', str(inputs.get('threads', 16)), '-p', str(inputs.get('map_pct_id', 90)), '-s', str(inputs.get('segment_length', 5000)), '-k', str(inputs.get('min_match_length', 19)), '-G', str(inputs.get('graph_poas', 2)), '&&', 'find', str(pggb_dir), '-name', '*.smooth.final.gfa', '-print', '-quit', '|', 'xargs', '-r', '-I{}', 'cp', '-f', '{}', str(graph_gfa), '&&', 'find', str(pggb_dir), '-name', '*.smooth.final.og', '-print', '-quit', '|', 'xargs', '-r', '-I{}', 'cp', '-f', '{}', str(graph_odgi)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'graph_gfa.gfa', node_out / 'graph_odgi.odgi']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_fasta': ('FASTA', {'description': 'List of haplotype FASTA files'}), 'threads': ('INT', {'default': 16, 'min': 1, 'max': 128})}, 'optional': {'map_pct_id': ('INT', {'default': 90, 'min': 50, 'max': 100}), 'segment_length': ('INT', {'default': 5000, 'min': 1000}), 'min_match_length': ('INT', {'default': 19, 'min': 1}), 'graph_poas': ('INT', {'default': 2, 'min': 1, 'max': 8})}, 'hidden': {'output': ('STRING', {})}}
