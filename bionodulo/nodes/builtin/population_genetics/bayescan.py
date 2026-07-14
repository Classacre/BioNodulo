"""bayescan — population_genetics node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BayeScanNode(CommandNode):
    """Detect loci under selection from population genotype data with BayeScan."""
    NODE_ID = 'bayescan'
    DISPLAY_NAME = 'BayeScan'
    REQUIRED_CONDA_PACKAGES = ['bayescan']
    CATEGORY = 'population_genetics'
    DESCRIPTION = 'Identify candidate loci under natural selection from population allele-frequency differences.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BayeScan', 'bayescan2', 'natural selection', 'population genetics', 'FST', 'genome scan', 'dominant markers', 'codominant markers']
    RETURN_TYPES = ('TXT', 'TXT', 'TXT', 'TXT', 'TXT', 'TXT')
    RETURN_NAMES = ('log', 'selection', 'verification', 'acceptance_rate', 'pilot_runs', 'allele_frequencies')
    REQUIRED_EXECUTABLES = ['bayescan2']
    DOCUMENTATION_URL = 'http://cmpg.unibe.ch/software/BayeScan/'
    CITATION_DOIS = ['10.1534/genetics.108.092221']
    CITATION_URLS = [f'{DOI_URL}10.1534/genetics.108.092221']
    CITATION_TEXT = 'A genome-scan method to identify selected loci appropriate for both dominant and codominant markers.'
    VERSION = '2.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        discovered_dir = f'{out}/output_dir'
        cmd = ['mkdir', '-p', discovered_dir, '&&', 'bayescan2', str(inputs.get('input', '')), '-od', discovered_dir]
        if inputs.get('discard_loci_file'):
            cmd.extend(['-d', str(inputs.get('discard_loci_file'))])
        if inputs.get('snp_genotypes_matrix'):
            cmd.append('-fstat')
        if inputs.get('fstats'):
            cmd.append('-snp')
        if inputs.get('pilot_runs'):
            cmd.append('-out_pilot')
        if inputs.get('allele_frequency'):
            cmd.append('-out_freq')
        cmd.extend(['-o', 'bayescan', '-n', str(inputs.get('sample_size', 5000)), '-thin', str(inputs.get('thinning_interval', 10)), '-nbp', str(inputs.get('num_pilot_runs', 20)), '-pilot', str(inputs.get('length_pilot_run', 5000)), '-burn', str(inputs.get('burn', 50000)), '-pr_odds', str(inputs.get('prior_odds', 10)), '-lb_fis', str(inputs.get('lower_prior', 0.0)), '-hb_fis', str(inputs.get('higher_prior', 1.0)), '-aflp_pc', str(inputs.get('threshold', 0.1)), '>', f'{out}/bayescan.log'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        discovered_dir = out / 'output_dir'
        discovered_dir.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'bayescan.log', discovered_dir / 'bayescan.sel', discovered_dir / 'bayescan_Verif.txt', discovered_dir / 'bayescan_AccRte.txt']
        if inputs.get('pilot_runs'):
            outputs.append(discovered_dir / 'bayescan_prop.txt')
        if inputs.get('allele_frequency'):
            outputs.append(discovered_dir / 'bayescan_freq.txt')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TXT', {'description': 'BayeScan genotype data file in tab- or space-delimited text format'})}, 'optional': {'discard_loci_file': ('TSV', {'default': '', 'description': 'Optional list of loci to discard before analysis'}), 'snp_genotypes_matrix': ('BOOLEAN', {'default': False, 'description': 'Use SNP genotypes matrix input mode (-fstat in the Galaxy wrapper)'}), 'fstats': ('BOOLEAN', {'default': False, 'description': 'Only estimate F-statistics without selection testing'}), 'sample_size': ('INT', {'default': 5000, 'min': 1, 'description': 'Number of output iterations'}), 'thinning_interval': ('INT', {'default': 10, 'min': 1, 'description': 'MCMC thinning interval'}), 'num_pilot_runs': ('INT', {'default': 20, 'min': 0, 'description': 'Number of pilot runs'}), 'length_pilot_run': ('INT', {'default': 5000, 'min': 1, 'description': 'Length of each pilot run'}), 'burn': ('INT', {'default': 50000, 'min': 0, 'description': 'Additional burn-in length'}), 'prior_odds': ('INT', {'default': 10, 'min': 1, 'description': 'Prior odds for the neutral model'}), 'lower_prior': ('FLOAT', {'default': 0.0, 'min': 0, 'max': 1, 'description': 'Lower bound for the dominant-data Fis prior'}), 'higher_prior': ('FLOAT', {'default': 1.0, 'min': 0, 'max': 1, 'description': 'Upper bound for the dominant-data Fis prior'}), 'threshold': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'AFLP recessive-genotype threshold fraction'}), 'pilot_runs': ('BOOLEAN', {'default': False, 'description': 'Write optional pilot-run diagnostics'}), 'allele_frequency': ('BOOLEAN', {'default': False, 'description': 'Write optional allele-frequency output'})}, 'hidden': {'output': ('STRING', {})}}
