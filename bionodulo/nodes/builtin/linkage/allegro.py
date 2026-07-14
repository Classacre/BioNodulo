"""allegro — linkage node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class AllegroNode(CommandNode):
    """Run Allegro linkage, haplotype, and IBD sharing analysis."""
    NODE_ID = 'allegro'
    DISPLAY_NAME = 'Allegro'
    REQUIRED_CONDA_PACKAGES = ['allegro']
    CATEGORY = 'linkage'
    DESCRIPTION = 'Multipoint genetic linkage, haplotype, IBD sharing, and simulation analysis.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Allegro', 'allegro', 'multipoint linkage analysis', 'haplotype analysis', 'IBD sharing', 'parametric linkage', 'allele sharing', 'Genehunter']
    RETURN_TYPES = ('FILE', 'FILE', 'FILE', 'TXT', 'TXT')
    RETURN_NAMES = ('haplotypes', 'linkage', 'descent', 'linear_expression', 'combined_crossovers')
    REQUIRED_EXECUTABLES = ['allegro']
    DOCUMENTATION_URL = 'https://www.decode.com/software/allegro/'
    CITATION_DOIS = ALLEGRO_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in ALLEGRO_CITATION_DOIS]
    CITATION_TEXT = ALLEGRO_CITATION_TEXT
    VERSION = '3+galaxy0'
    SHELL = True
    ANALYSIS_MODES = ['haplotypes', 'linkage']
    LINKAGE_TYPES = ['defaults', 'allele_sharing', 'classical']
    LINKAGE_MPTSPT = ['mpt', 'spt']
    LINEXP_OPTIONS = ['lin', 'exp']
    SCORING_OPTIONS = ['pairs', 'all', 'homoz', 'mnallele', 'robdom', 'ps:mm/mf/ff']
    WEIGHTING_OPTIONS = ['equal', 'power:0.5']
    STEPS_TYPES = ['STEPS', 'STEPFILE', 'MAXSTEPLENGTH']
    PAIRWISE_TYPES = ['all', 'genotype', 'affected', 'informative']
    UNIT_OPTIONS = ['recombination', 'centimorgan']

    @classmethod
    def _out_dir(cls, inputs: dict[str, Any]) -> str:
        return _out(inputs)

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any]) -> dict[str, str]:
        out = cls._out_dir(inputs)
        return {'haplotypes': f'{out}/haplotypes.ihaplo', 'linkage': f'{out}/linkage.fparam', 'descent': f'{out}/descent.out', 'linear_expression': f'{out}/linear_expression.txt', 'combined_crossovers': f'{out}/combined_crossovers.txt'}

    @classmethod
    def _is_true(cls, inputs: dict[str, Any], name: str, default: bool=False) -> bool:
        value = inputs.get(name, default)
        if isinstance(value, str):
            return value.lower() in {'true', '1', 'yes', 'on'}
        return bool(value)

    @classmethod
    def _analysis_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('analysis_mode', 'linkage') or 'linkage')

    @classmethod
    def _linkage_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('linkage_type', 'defaults') or 'defaults')

    @classmethod
    def _config_lines(cls, inputs: dict[str, Any]) -> list[str]:
        paths = cls._output_paths(inputs)
        lines = [f"PREFILE {inputs.get('inp_ped', '')}", f"DATFILE {inputs.get('inp_dat', '')}"]
        if str(inputs.get('inp_map', '')).strip():
            lines.append(f"MAPFILE {inputs.get('inp_map')}")
        lines.append('')
        if cls._analysis_mode(inputs) == 'haplotypes':
            lines.append(f"HAPLOTYPE haplo.out {paths['haplotypes']} {paths['descent']} inher.out")
            if cls._is_true(inputs, 'crossover'):
                lines.append(f"CROSSOVERRATE combined.out {paths['combined_crossovers']}")
        else:
            linkage_mptspt = str(inputs.get('linkage_mptspt', 'mpt') or 'mpt')
            linkage_type = cls._linkage_type(inputs)
            opt_xlinked = str(inputs.get('xlinked', '') or '')
            if linkage_type == 'allele_sharing':
                lines.append(f"MODEL {linkage_mptspt} {inputs.get('linkage_linexp', 'lin')} {inputs.get('linkage_scoring', 'pairs')} {inputs.get('weighting', 'equal')} param.mpt {paths['linear_expression']}")
            else:
                suffix = ''
                if linkage_type == 'classical' and cls._is_true(inputs, 'custom_freqs'):
                    suffix = f" freq:{inputs.get('par_freq', 0)} pen:{inputs.get('par_pen', 'p0/p1/p2')}"
                het = str(inputs.get('par_het', '') or 'het')
                lines.append(f"MODEL {linkage_mptspt} par {opt_xlinked}{suffix} {het} param.mpt {paths['linkage']}")
            steps_type = str(inputs.get('steps_type', 'STEPS') or 'STEPS')
            if steps_type == 'STEPFILE':
                lines.append(f"STEPFILE {inputs.get('stepfile', '')}")
            elif steps_type == 'MAXSTEPLENGTH':
                lines.append(f"MAXSTEPLENGTH {inputs.get('max_step_length', 2)}")
            else:
                lines.append(f"STEPS {inputs.get('steps', 2)}")
        if cls._is_true(inputs, 'sexspecific'):
            lines.append('SEXSPECIFIC on')
        lines.append(f"ENTROPY {('on' if cls._is_true(inputs, 'entropy') else 'off')}")
        lines.append(f"NPLEXACTP {('on' if cls._is_true(inputs, 'nplexactp') else 'off')}")
        if cls._is_true(inputs, 'pairwise'):
            linkage_mptspt = str(inputs.get('linkage_mptspt', 'mpt') or 'mpt')
            lines.append(f"PAIRWISEIBD {linkage_mptspt} {inputs.get('pairwise_type', 'all')}")
        if cls._is_true(inputs, 'simulate'):
            sim_tokens = []
            if str(inputs.get('sim_dloc', '')).strip():
                sim_tokens.append(f"dloc:{inputs.get('sim_dloc')}")
            sim_tokens.extend([f"npre:{inputs.get('sim_npre', 1)}", f"rep:{inputs.get('sim_rep', 1)}", f"err:{inputs.get('sim_err', 0)}", f"yield:{inputs.get('sim_yield', 1)}", f"het:{inputs.get('sim_het', 0)}"])
            lines.append(f"SIMULATE {' '.join(sim_tokens)}")
        lines.extend(['MAXMEMORY 102400', f"UNIT {inputs.get('unit', 'recombination')}", 'UNINFORMATIVE'])
        return lines

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out_dir(inputs)
        conf = f'{out}/allegro.conf'
        config = '\n'.join(cls._config_lines(inputs)) + '\n'
        return f"mkdir -p {shlex.quote(out)} && cat > {shlex.quote(conf)} <<'EOF'\n{config}EOF\nallegro {shlex.quote(conf)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        mode = cls._analysis_mode(inputs)
        linkage_type = cls._linkage_type(inputs)
        if mode == 'haplotypes':
            outputs = [out / 'haplotypes.ihaplo', out / 'descent.out']
            if cls._is_true(inputs, 'crossover'):
                outputs.append(out / 'combined_crossovers.txt')
            return outputs
        if linkage_type == 'allele_sharing':
            return [out / 'linear_expression.txt']
        return [out / 'linkage.fparam']

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, default: str, options: list[str]) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_min(cls, inputs: dict[str, Any], name: str, default: int | float, minimum: int | float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be numeric'
        if value < minimum:
            return f'{name} must be >= {minimum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('inp_ped', '')).strip():
            return 'Pedigree input is required'
        if not str(inputs.get('inp_dat', '')).strip():
            return 'Recombination data input is required'
        for name, default, options in [('analysis_mode', 'linkage', cls.ANALYSIS_MODES), ('linkage_mptspt', 'mpt', cls.LINKAGE_MPTSPT), ('linkage_type', 'defaults', cls.LINKAGE_TYPES), ('linkage_linexp', 'lin', cls.LINEXP_OPTIONS), ('linkage_scoring', 'pairs', cls.SCORING_OPTIONS), ('weighting', 'equal', cls.WEIGHTING_OPTIONS), ('steps_type', 'STEPS', cls.STEPS_TYPES), ('pairwise_type', 'all', cls.PAIRWISE_TYPES), ('unit', 'recombination', cls.UNIT_OPTIONS)]:
            result = cls._validate_choice(inputs, name, default, options)
            if result is not True:
                return result
        if str(inputs.get('steps_type', 'STEPS') or 'STEPS') == 'STEPFILE' and (not str(inputs.get('stepfile', '')).strip()):
            return 'stepfile is required when steps_type is STEPFILE'
        for name, default, minimum in [('steps', 2, 1), ('max_step_length', 2, 1), ('sim_npre', 1, 1), ('sim_rep', 1, 1), ('sim_err', 0, 0), ('sim_yield', 1, 0), ('sim_het', 0, 0)]:
            result = cls._validate_min(inputs, name, default, minimum)
            if result is not True:
                return result
        if cls._is_true(inputs, 'custom_freqs'):
            try:
                par_freq = float(inputs.get('par_freq', 0))
            except (TypeError, ValueError):
                return 'par_freq must be numeric'
            if not 0 <= par_freq <= 1:
                return 'par_freq must be between 0 and 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'inp_ped': ('FILE', {'description': 'Linkage pedigree input file'}), 'inp_dat': ('FILE', {'description': 'Linkage data/recombination frequency input file'})}, 'optional': {'inp_map': ('FILE', {'default': '', 'description': 'Optional marker map positions file'}), 'analysis_mode': ('STRING', {'default': 'linkage', 'options': cls.ANALYSIS_MODES, 'description': 'Run haplotype reconstruction or linkage analysis'}), 'crossover': ('BOOLEAN', {'default': False, 'description': 'Report combined crossover rates for haplotypes'}), 'linkage_mptspt': ('STRING', {'default': 'mpt', 'options': cls.LINKAGE_MPTSPT, 'description': 'Use multipoint or single-point IBD probabilities'}), 'linkage_type': ('STRING', {'default': 'defaults', 'options': cls.LINKAGE_TYPES, 'description': 'Galaxy linkage analysis type'}), 'linkage_linexp': ('STRING', {'default': 'lin', 'options': cls.LINEXP_OPTIONS, 'description': 'Linear or exponential allele-sharing model'}), 'linkage_scoring': ('STRING', {'default': 'pairs', 'options': cls.SCORING_OPTIONS, 'description': 'Allele-sharing scoring function'}), 'weighting': ('STRING', {'default': 'equal', 'options': cls.WEIGHTING_OPTIONS, 'description': 'Allele-sharing weighting function'}), 'custom_freqs': ('BOOLEAN', {'default': False, 'description': 'Use custom classical model frequencies'}), 'par_freq': ('FLOAT', {'default': 0, 'min': 0, 'max': 1, 'description': 'Classical model allele frequency'}), 'par_pen': ('STRING', {'default': 'p0/p1/p2', 'description': 'Classical model penetrance'}), 'par_het': ('FLOAT', {'default': '', 'description': 'Optional classical model heterogeneity frequency'}), 'steps_type': ('STRING', {'default': 'STEPS', 'options': cls.STEPS_TYPES, 'description': 'Marker interval calculation mode'}), 'steps': ('INT', {'default': 2, 'min': 1, 'description': 'Calculations between adjacent markers'}), 'stepfile': ('FILE', {'default': '', 'description': 'Positions file for STEPFILE mode'}), 'max_step_length': ('FLOAT', {'default': 2, 'min': 1, 'description': 'Periodic cM interval for MAXSTEPLENGTH mode'}), 'xlinked': ('STRING', {'default': '', 'options': ['', 'X'], 'description': 'Autosomal or X-linked disease model'}), 'entropy': ('BOOLEAN', {'default': False, 'description': 'Calculate entropy'}), 'nplexactp': ('BOOLEAN', {'default': False, 'description': 'Use exact non-parametric linkage p-values'}), 'pairwise': ('BOOLEAN', {'default': False, 'description': 'Perform pairwise IBD analysis'}), 'pairwise_type': ('STRING', {'default': 'all', 'options': cls.PAIRWISE_TYPES, 'description': 'Pairwise IBD weighting mode'}), 'simulate': ('BOOLEAN', {'default': False, 'description': 'Simulate multipoint data'}), 'sim_dloc': ('FLOAT', {'default': '', 'min': 0, 'description': 'Optional disease locus in cM'}), 'sim_npre': ('INT', {'default': 1, 'min': 1, 'description': 'Number of prefiles to generate'}), 'sim_rep': ('INT', {'default': 1, 'min': 1, 'description': 'Family pattern repeat count'}), 'sim_err': ('FLOAT', {'default': 0, 'min': 0, 'description': 'Simulation error rate'}), 'sim_yield': ('FLOAT', {'default': 1, 'min': 0, 'description': 'Simulation genotype yield'}), 'sim_het': ('FLOAT', {'default': 0, 'min': 0, 'description': 'Simulation heterogeneity probability'}), 'sexspecific': ('BOOLEAN', {'default': False, 'description': 'Use sex-specific penetrances from the data file'}), 'unit': ('STRING', {'default': 'recombination', 'options': cls.UNIT_OPTIONS, 'description': 'Distance unit used in the data file'})}, 'hidden': {'output': ('STRING', {})}}
