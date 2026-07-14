"""abyss — assembly node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ABySSPENode(CommandNode):
    """Assemble reads with the ABySS paired-end pipeline."""
    NODE_ID = 'abyss_pe'
    DISPLAY_NAME = 'ABySS'
    REQUIRED_CONDA_PACKAGES = ['abyss', 'bwa']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Run the ABySS de novo assembler pipeline for paired-end, mate-pair, single-end, or long-read libraries.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ABySS', 'abyss-pe', 'de novo assembler', 'short read assembly', 'paired-end assembly', 'genome assembler']
    RETURN_TYPES = ('FASTA', 'FASTA', 'FASTA', 'FASTA', 'FASTA', 'TSV')
    RETURN_NAMES = ('unitigs', 'contigs', 'scaffolds', 'long_scaffolds', 'indels', 'stats')
    REQUIRED_EXECUTABLES = ['abyss-pe']
    DOCUMENTATION_URL = 'https://github.com/bcgsc/abyss'
    CITATION_DOIS = ['10.1101/gr.214346.116', '10.1101/gr.089532.108']
    CITATION_URLS = [f'{DOI_URL}10.1101/gr.214346.116', f'{DOI_URL}10.1101/gr.089532.108']
    CITATION_TEXT = 'ABySS 2.0: resource-efficient assembly of large genomes using a Bloom filter; ABySS: a parallel assembler for short read sequence data.'
    VERSION = '2.3.10'
    SHELL = True
    PARAM_DEFAULTS = {'k': 41, 'q': '', 'Q': '', 'e': '', 'E': '', 't': '', 'c': '', 'b': '', 'm': '', 'p': '', 'a': '', 'l': '', 's': '', 'n': '', 'd': '', 'S': '', 'N': ''}

    @classmethod
    def _libraries(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        libraries = inputs.get('libraries') or inputs.get('libs') or []
        if isinstance(libraries, dict):
            return [libraries]
        return list(libraries)

    @classmethod
    def _read_list(cls, value: Any) -> list[str]:
        if isinstance(value, dict):
            return [str(v) for v in value.get('reads') or value.get('read') or []]
        return _as_list(value)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd: list[str] = []
        libnames: dict[str, list[str]] = {'lib': [], 'mp': [], 'long': []}
        library_assignments: list[str] = []
        for index, library in enumerate(cls._libraries(inputs)):
            lib_type = str(library.get('type', library.get('lib_type', 'lib')))
            if lib_type in {'lib', 'mp'}:
                forward = str(library.get('forward', library.get('read1', '')))
                reverse = str(library.get('reverse', library.get('read2', '')))
                forward_link = f"{out}/{lib_type}_forward_{index}.{(_safe_name(forward).split('.', 1)[1] if '.' in _safe_name(forward) else 'fastq')}"
                reverse_link = f"{out}/{lib_type}_reverse_{index}.{(_safe_name(reverse).split('.', 1)[1] if '.' in _safe_name(reverse) else 'fastq')}"
                cmd.extend(['ln', '-sf', forward, forward_link, '&&', 'ln', '-sf', reverse, reverse_link, '&&'])
                name = f'{lib_type}{index}'
                libnames[lib_type].append(name)
                library_assignments.append(f'{name}={forward_link} {reverse_link}')
            elif lib_type == 'se':
                links: list[str] = []
                for read_index, read in enumerate(cls._read_list(library.get('reads', library.get('read', [])))):
                    link = f"{out}/se_{index}_{read_index}.{(_safe_name(read).split('.', 1)[1] if '.' in _safe_name(read) else 'fastq')}"
                    cmd.extend(['ln', '-sf', read, link, '&&'])
                    links.append(link)
                if links:
                    library_assignments.append(f"se={' '.join(links)}")
            elif lib_type == 'long':
                for read_index, read in enumerate(cls._read_list(library.get('reads', library.get('read', [])))):
                    link = f"{out}/long_{index + read_index}.{(_safe_name(read).split('.', 1)[1] if '.' in _safe_name(read) else 'fasta')}"
                    cmd.extend(['ln', '-sf', read, link, '&&'])
                    name = f'long{index + read_index}'
                    libnames['long'].append(name)
                    library_assignments.append(f'{name}={link}')
        cmd.extend(['abyss-pe', 'name=abyss', f"j=${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}", f"B=$(( ${{GALAXY_MEMORY_MB:-{inputs.get('memory_mb', 2048)}}} * 9 / 10 ))M", f"k={inputs.get('k', 41)}"])
        for key, default in cls.PARAM_DEFAULTS.items():
            if key == 'k':
                continue
            value = inputs.get(key, default)
            if value is not None and str(value) != '':
                cmd.append(f'{key}={value}')
        if inputs.get('K') is not None and str(inputs.get('K')) != '':
            insert_at = cmd.index(f"k={inputs.get('k', 41)}") + 1
            cmd.insert(insert_at, f"K={inputs.get('K')}")
        if inputs.get('SS'):
            insert_at = cmd.index(f"k={inputs.get('k', 41)}") + 1
            while insert_at < len(cmd) and cmd[insert_at].split('=', 1)[0] in {'K', 'q', 'Q', 'e', 'E', 't', 'c', 'b'}:
                insert_at += 1
            cmd.insert(insert_at, 'SS=--SS')
        for lib_type in ('lib', 'mp', 'long'):
            if libnames[lib_type]:
                cmd.append(f"{lib_type}={' '.join(libnames[lib_type])}")
        cmd.extend(library_assignments)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        lib_types = {str(library.get('type', library.get('lib_type', 'lib'))) for library in cls._libraries(inputs)}
        outputs = [out / 'abyss-unitigs.fa']
        if 'lib' in lib_types:
            outputs.append(out / 'abyss-contigs.fa')
        if lib_types & {'lib', 'mp'}:
            outputs.append(out / 'abyss-scaffolds.fa')
        if 'long' in lib_types:
            outputs.append(out / 'abyss-long-scaffs.fa')
        outputs.extend([out / 'abyss-indel.fa', out / 'abyss-stats.tab'])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'libraries': ('JSON', {'description': 'ABySS libraries: objects with type lib/mp/se/long and read paths'}), 'k': ('INT', {'default': 41, 'min': 1, 'description': 'K-mer length or k-mer-pair span'})}, 'optional': {'K': ('INT', {'default': '', 'min': 1, 'description': 'Single k-mer length in a k-mer pair'}), 'q': ('INT', {'default': 3, 'min': 0, 'max': 40, 'description': 'Minimum base quality when trimming'}), 'Q': ('INT', {'default': 0, 'min': 0, 'max': 40, 'description': 'Mask bases below this quality as N'}), 'e': ('INT', {'default': '', 'min': 0, 'description': 'Minimum erosion k-mer coverage'}), 'E': ('INT', {'default': '', 'min': 0, 'description': 'Minimum erosion k-mer coverage per strand'}), 't': ('INT', {'default': '', 'min': 0, 'description': 'Maximum length of blunt contigs to trim'}), 'c': ('FLOAT', {'default': '', 'min': 0, 'description': 'Minimum mean k-mer coverage of a unitig'}), 'b': ('INT', {'default': '', 'min': 0, 'description': 'Maximum bubble length'}), 'SS': ('BOOLEAN', {'default': False, 'description': 'Assemble in strand-specific mode'}), 'm': ('INT', {'default': '', 'min': 0, 'description': 'Minimum overlap of two unitigs'}), 'p': ('FLOAT', {'default': 0.9, 'min': 0, 'max': 1, 'description': 'Minimum sequence identity of a bubble'}), 'a': ('INT', {'default': 2, 'min': 0, 'description': 'Maximum number of branches of a bubble'}), 'l': ('INT', {'default': '', 'min': 1, 'description': 'Minimum alignment length of a read'}), 's': ('INT', {'default': 200, 'min': 0, 'description': 'Minimum unitig length for building contigs'}), 'n': ('INT', {'default': 10, 'min': 0, 'description': 'Minimum number of pairs for building contigs'}), 'd': ('INT', {'default': 6, 'min': 0, 'description': 'Allowable error of a distance estimate'}), 'S': ('STRING', {'default': '', 'description': 'Minimum contig size for building scaffolds'}), 'N': ('STRING', {'default': '', 'description': 'Minimum number of pairs for building scaffolds'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 256, 'display': 'slider'}), 'memory_mb': ('INT', {'default': 2048, 'min': 1, 'description': 'Memory in MB for ABySS Bloom filter'})}, 'hidden': {'output': ('STRING', {})}}
