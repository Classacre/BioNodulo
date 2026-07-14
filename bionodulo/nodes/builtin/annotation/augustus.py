"""augustus — annotation node(s). One tool per file (extracted from wrapped_annotation_sequence.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class AugustusNode(CommandNode):
    """Predict genes with the Galaxy IUC AUGUSTUS wrapper behavior."""
    NODE_ID = 'augustus'
    DISPLAY_NAME = 'Augustus'
    REQUIRED_CONDA_PACKAGES = ['augustus']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Predict genes in prokaryotic and eukaryotic genomes with AUGUSTUS.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Augustus', 'AUGUSTUS', 'augustus', 'ab initio gene prediction', 'gene prediction', 'eukaryotic genome annotation', 'extrinsic hints']
    RETURN_TYPES = ('GTF', 'FASTA', 'FASTA')
    RETURN_NAMES = ('output', 'protein_output', 'codingseq_output')
    REQUIRED_EXECUTABLES = ['augustus', 'python']
    DOCUMENTATION_URL = AUGUSTUS_DOCUMENTATION_URL
    CITATION_DOIS = AUGUSTUS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in AUGUSTUS_CITATION_DOIS]
    CITATION_TEXT = AUGUSTUS_CITATION_TEXT
    VERSION = '3.5.0+galaxy0'
    SHELL = True
    MODEL_MODES = ['builtin', 'history']
    STRANDS = ['both', 'forward', 'backward']
    GENE_MODELS = ['complete', 'partial', 'intronless', 'atleastone', 'exactlyone']
    OUTPUT_SELECTIONS = ['protein', 'codingseq', 'introns', 'start', 'stop', 'cds']
    DEFAULT_OUTPUTS = ['protein', 'codingseq', 'cds']
    OUTPUT_FORMATS = ['gtf', 'gff3']
    ORGANISMS = ['human', 'fly', 'generic', 'arabidopsis', 'rice', 'maize', 'chicken', 'zebrafish', 'caenorhabditis', 's_aureus', 'E_coli_K12', 'template_prokaryotic']

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        if 'outputs' in inputs:
            return _as_list(inputs.get('outputs'))
        return list(cls.DEFAULT_OUTPUTS)

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        if 'output_format' in inputs:
            return str(inputs.get('output_format') or 'gtf')
        return 'gff3' if inputs.get('gff') else 'gtf'

    @classmethod
    def _main_filename(cls, inputs: dict[str, Any]) -> str:
        return 'augustus.gff3' if cls._output_format(inputs) == 'gff3' else 'augustus.gtf'

    @classmethod
    def _main_output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls._main_filename(inputs)}'

    @classmethod
    def _protein_output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/protein.fasta'

    @classmethod
    def _codingseq_output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/codingseq.fasta'

    @classmethod
    def _model_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('model_mode', inputs.get('augustus_mode', 'builtin')) or 'builtin')

    @classmethod
    def _history_model_stage(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._model_mode(inputs) != 'history':
            return []
        custom_model = str(inputs.get('custom_model', '') or '')
        return ['cp -r $(dirname $(command -v augustus))/../config/ augustus_dir/', 'mkdir -p augustus_dir/species/', f'tar -C augustus_dir/species/ -xzvf {shlex.quote(custom_model)} > /dev/null', 'export AUGUSTUS_CONFIG_PATH=./augustus_dir/']

    @classmethod
    def _augustus_command(cls, inputs: dict[str, Any]) -> str:
        selected = set(cls._selected_outputs(inputs))
        output_format = cls._output_format(inputs)
        cmd = ['augustus', f"--strand={str(inputs.get('strand', 'both') or 'both')}", f"--noInFrameStop={('true' if inputs.get('noInFrameStop') else 'false')}", '--gff3=on' if output_format == 'gff3' else '--gff3=off', '--uniqueGeneId=true']
        for output in cls.OUTPUT_SELECTIONS:
            cmd.append(f"--{output}={('on' if output in selected else 'off')}")
        cmd.append(f"--singlestrand={('true' if inputs.get('singlestrand') else 'false')}")
        cmd.append(str(inputs.get('input_genome', '') or ''))
        cmd.append('--UTR=on' if inputs.get('utr') else '--UTR=off')
        cmd.append(f"--genemodel={str(inputs.get('genemodel', 'partial') or 'partial')}")
        cmd.append(f"--softmasking={('1' if inputs.get('softmasking', True) else '0')}")
        hintsfile = str(inputs.get('hintsfile', '') or '')
        extrinsiccfg = str(inputs.get('extrinsiccfg', '') or '')
        if hintsfile or extrinsiccfg:
            cmd.extend(['--hintsfile', hintsfile, '--extrinsicCfgFile', extrinsiccfg])
        if inputs.get('range_start') not in (None, '') or inputs.get('range_stop') not in (None, ''):
            cmd.append(f"--predictionStart={inputs.get('range_start', '')}")
            cmd.append(f"--predictionEnd={inputs.get('range_stop', '')}")
        if cls._model_mode(inputs) == 'history':
            cmd.append('--species=local')
        else:
            cmd.append(f"--species={str(inputs.get('organism', 'human') or 'human')}")
        return _shell_join(cmd)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = cls._history_model_stage(inputs)
        selected = set(cls._selected_outputs(inputs))
        augustus_pipe = f'{cls._augustus_command(inputs)} | tee {shlex.quote(cls._main_output_path(inputs))}'
        extract_cmd = ['python', str(inputs.get('extract_features_path', 'extract_features.py') or 'extract_features.py')]
        if 'protein' in selected:
            extract_cmd.extend(['--protein', cls._protein_output_path(inputs)])
        if 'codingseq' in selected:
            extract_cmd.extend(['--codingseq', cls._codingseq_output_path(inputs)])
        if 'protein' in selected or 'codingseq' in selected:
            augustus_pipe = f'{augustus_pipe} | {_shell_join(extract_cmd)}'
        commands.append(augustus_pipe)
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(cls._selected_outputs(inputs))
        outputs = [out / cls._main_filename(inputs)]
        if 'protein' in selected:
            outputs.append(out / 'protein.fasta')
        if 'codingseq' in selected:
            outputs.append(out / 'codingseq.fasta')
        return outputs

    @classmethod
    def _validate_range_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        start_raw = inputs.get('range_start')
        stop_raw = inputs.get('range_stop')
        if start_raw in (None, '') and stop_raw in (None, ''):
            return True
        if start_raw in (None, ''):
            return 'range_start is required when range_stop is provided'
        if stop_raw in (None, ''):
            return 'range_stop is required when range_start is provided'
        try:
            start = int(start_raw)
            stop = int(stop_raw)
        except (TypeError, ValueError):
            return 'range_start and range_stop must be integers'
        if start < 1:
            return 'range_start must be greater than or equal to 1'
        if stop <= start:
            return 'range_stop must be greater than range_start'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_genome', '') or '').strip():
            return 'input_genome is required'
        model_mode = cls._model_mode(inputs)
        if model_mode not in cls.MODEL_MODES:
            return f"model_mode must be one of: {', '.join(cls.MODEL_MODES)}"
        if model_mode == 'history' and (not str(inputs.get('custom_model', '') or '').strip()):
            return 'custom_model is required when model_mode is history'
        strand = str(inputs.get('strand', 'both') or 'both')
        if strand not in cls.STRANDS:
            return f"strand must be one of: {', '.join(cls.STRANDS)}"
        genemodel = str(inputs.get('genemodel', 'partial') or 'partial')
        if genemodel not in cls.GENE_MODELS:
            return f"genemodel must be one of: {', '.join(cls.GENE_MODELS)}"
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_FORMATS:
            return f"output_format must be one of: {', '.join(cls.OUTPUT_FORMATS)}"
        invalid_outputs = [output for output in cls._selected_outputs(inputs) if output not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"outputs values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        hintsfile = str(inputs.get('hintsfile', '') or '')
        extrinsiccfg = str(inputs.get('extrinsiccfg', '') or '')
        if hintsfile and (not extrinsiccfg):
            return 'extrinsiccfg is required when hintsfile is provided'
        if extrinsiccfg and (not hintsfile):
            return 'hintsfile is required when extrinsiccfg is provided'
        range_result = cls._validate_range_inputs(inputs)
        if range_result is not True:
            return range_result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_genome': ('FASTA', {'description': 'Genome FASTA or FASTA.GZ sequence to annotate'}), 'model_mode': ('STRING', {'default': 'builtin', 'options': cls.MODEL_MODES, 'description': 'Use a predefined AUGUSTUS species model or a trained model archive from history'})}, 'optional': {'organism': ('STRING', {'default': 'human', 'options': cls.ORGANISMS, 'description': 'Built-in AUGUSTUS species model name; any installed species name may be entered'}), 'custom_model': ('FILE', {'default': '', 'description': 'AUGUSTUS trained model archive'}), 'strand': ('STRING', {'default': 'both', 'options': cls.STRANDS, 'description': 'Predict genes on both or one strand'}), 'genemodel': ('STRING', {'default': 'partial', 'options': cls.GENE_MODELS, 'description': 'AUGUSTUS gene model completeness mode'}), 'outputs': ('STRING_LIST', {'default': cls.DEFAULT_OUTPUTS, 'options': cls.OUTPUT_SELECTIONS, 'multiple': True, 'description': 'AUGUSTUS feature comments to emit and optional FASTA files to extract'}), 'output_format': ('STRING', {'default': 'gtf', 'options': cls.OUTPUT_FORMATS, 'description': 'Main annotation output format'}), 'noInFrameStop': ('BOOLEAN', {'default': False, 'description': 'Do not report transcripts with in-frame stop codons'}), 'singlestrand': ('BOOLEAN', {'default': False, 'description': 'Predict genes independently on each strand'}), 'utr': ('BOOLEAN', {'default': False, 'description': 'Predict untranslated regions in addition to coding sequence'}), 'softmasking': ('BOOLEAN', {'default': True, 'description': 'Treat lowercase bases as repeat-masked sequence'}), 'hintsfile': ('GFF', {'default': '', 'description': 'Optional extrinsic hints GFF file'}), 'extrinsiccfg': ('FILE', {'default': '', 'description': 'Extrinsic configuration file for hints'}), 'range_start': ('INT', {'default': '', 'min': 1, 'description': 'Optional first nucleotide position to predict'}), 'range_stop': ('INT', {'default': '', 'min': 1, 'description': 'Optional last nucleotide position to predict'}), 'extract_features_path': ('STRING', {'default': 'extract_features.py', 'advanced': True, 'description': 'Path to Galaxy extract_features.py helper'})}, 'hidden': {'output': ('STRING', {})}}


class AugustusTrainingNode(CommandNode):
    """Train an AUGUSTUS species model from MAKER annotations."""
    NODE_ID = 'augustus_training'
    DISPLAY_NAME = 'Train Augustus'
    REQUIRED_CONDA_PACKAGES = ['augustus', 'maker']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Train an AUGUSTUS species model from genome sequence and MAKER gene annotations.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Train Augustus', 'AUGUSTUS training', 'augustus_training', 'MAKER', 'maker2zff', 'autoAugTrain.pl', 'gene predictor training']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('output_tar',)
    REQUIRED_EXECUTABLES = ['augustus', 'maker2zff', 'zff2gff3.pl', 'autoAugTrain.pl', 'perl', 'tar']
    DOCUMENTATION_URL = AUGUSTUS_DOCUMENTATION_URL
    CITATION_DOIS = AUGUSTUS_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in AUGUSTUS_CITATION_DOIS]
    CITATION_TEXT = AUGUSTUS_CITATION_TEXT
    VERSION = '3.5.0+galaxy0'
    SHELL = True
    OUTPUT_FILENAME = 'output_tar.augustus'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/{cls.OUTPUT_FILENAME}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        genome = str(inputs.get('genome', '') or '')
        maker_gff = str(inputs.get('maker_gff', '') or '')
        return ' && '.join(['cp -r $(dirname $(command -v augustus))/../config/ augustus_dir/', 'export AUGUSTUS_CONFIG_PATH=$(pwd)/augustus_dir/', _shell_join(['maker2zff', maker_gff]), "zff2gff3.pl genome.ann | perl -plne 's/\\t(\\S+)$/\\t\\.\\t$1/' > genome.gff3", f'autoAugTrain.pl --genome={shlex.quote(genome)} --species=local --trainingset=genome.gff3 -v', f'cd augustus_dir/species/ && tar cvfz {shlex.quote(cls._output_path(inputs))} local'])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('genome', '') or '').strip():
            return 'genome is required'
        if not str(inputs.get('maker_gff', '') or '').strip():
            return 'maker_gff is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'genome': ('FASTA', {'description': 'Genome FASTA sequence used for AUGUSTUS training'}), 'maker_gff': ('GFF', {'description': 'MAKER GFF/GFF3 annotation used as the training set'})}, 'hidden': {'output': ('STRING', {})}}
