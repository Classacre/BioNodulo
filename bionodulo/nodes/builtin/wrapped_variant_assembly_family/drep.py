"""Focused drep node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class DrepCompareNode(CommandNode):
    """Compare genome FASTA files with dRep."""

    NODE_ID = "drep_compare"
    DISPLAY_NAME = "dRep compare"
    REQUIRED_CONDA_PACKAGES = ["drep"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Compare genome sets with dRep using Mash primary clustering and optional secondary ANI clustering."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "dRep",
        "dRep compare",
        "dRep genome comparison",
        "genome dereplication",
        "average nucleotide identity",
        "Mash ANI clustering",
    ]
    RETURN_TYPES = ("TXT", "TXT", "PDF", "PDF", "PDF", "PDF", "CSV", "CSV", "CSV", "CSV")
    RETURN_NAMES = (
        "log",
        "warnings",
        "primary_clustering_dendrogram",
        "secondary_clustering_dendrograms",
        "secondary_clustering_mds",
        "clustering_scatterplots",
        "bdb",
        "cdb",
        "mdb",
        "ndb",
    )
    REQUIRED_EXECUTABLES = ["dRep"]
    DOCUMENTATION_URL = "https://drep.readthedocs.io/en/latest/overview.html"
    CITATION_DOIS = [DREP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{DREP_CITATION_DOI}"]
    CITATION_TEXT = DREP_CITATION_TEXT
    VERSION = "3.6.2"
    SHELL = True

    COMPARISON_STEPS = ["default", "SkipMash", "SkipSecondary"]
    SECONDARY_ALGORITHMS = ["fastANI", "ANImf", "ANIn", "gANI", "goANI"]
    NUCMER_PRESETS = ["normal", "tight"]
    COVERAGE_METHODS = ["larger", "total"]
    CLUSTER_ALGORITHMS = ["average", "ward", "single", "median", "centroid", "weighted"]
    DEFAULT_OUTPUTS = ["log", "warnings", "Primary_clustering_dendrogram", "Clustering_scatterplots"]
    OUTPUTS = {
        "log": ("outdir/log/logger.log", "log.txt"),
        "warnings": ("outdir/log/warnings.txt", "warnings.txt"),
        "Primary_clustering_dendrogram": (
            "outdir/figures/Primary_clustering_dendrogram.pdf",
            "Primary_clustering_dendrogram.pdf",
        ),
        "Secondary_clustering_dendrograms": (
            "outdir/figures/Secondary_clustering_dendrograms.pdf",
            "Secondary_clustering_dendrograms.pdf",
        ),
        "Secondary_clustering_MDS": ("outdir/figures/Secondary_clustering_MDS.pdf", "Secondary_clustering_MDS.pdf"),
        "Clustering_scatterplots": ("outdir/figures/Clustering_scatterplots.pdf", "Clustering_scatterplots.pdf"),
        "Bdb": ("outdir/data_tables/Bdb.csv", "Bdb.csv"),
        "Cdb": ("outdir/data_tables/Cdb.csv", "Cdb.csv"),
        "Mdb": ("outdir/data_tables/Mdb.csv", "Mdb.csv"),
        "Ndb": ("outdir/data_tables/Ndb.csv", "Ndb.csv"),
    }

    @classmethod
    def _genomes(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("genomes"))

    @classmethod
    def _genome_identifiers(cls, inputs: dict[str, Any], genomes: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("genome_identifiers", inputs.get("element_identifiers")))
        if not identifiers:
            identifiers = [Path(path).name for path in genomes]
        identifiers.extend(Path(path).name for path in genomes[len(identifiers) :])
        return [_safe_identifier(identifier) for identifier in identifiers[: len(genomes)]]

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get("select_outputs"))
        if not selected:
            return cls.DEFAULT_OUTPUTS.copy()
        return [output for output in selected if output in cls.OUTPUTS]

    @classmethod
    def _add_mash_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(
            [
                "--MASH_sketch",
                str(inputs.get("MASH_sketch", 1000)),
                "--P_ani",
                str(inputs.get("P_ani", 0.9)),
            ]
        )
        if inputs.get("multiround_primary_clustering"):
            cmd.append("--multiround_primary_clustering")
        cmd.extend(["--primary_chunksize", str(inputs.get("primary_chunksize", 5000))])

    @classmethod
    def _add_secondary_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        algorithm = str(inputs.get("S_algorithm", "ANImf") or "ANImf")
        cmd.extend(["--S_algorithm", algorithm])
        if algorithm == "fastANI":
            if inputs.get("greedy_secondary_clustering"):
                cmd.append("--greedy_secondary_clustering")
        elif algorithm in {"ANImf", "ANIn"}:
            cmd.extend(["--n_PRESET", str(inputs.get("n_PRESET", "normal"))])
            cmd.extend(["--coverage_method", str(inputs.get("coverage_method", "larger"))])
        cmd.extend(["--S_ani", str(inputs.get("S_ani", 0.99))])
        cmd.extend(["--cov_thresh", str(inputs.get("cov_thresh", 0.1))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        genomes = cls._genomes(inputs)
        genome_names = [f"{identifier}.fasta" for identifier in cls._genome_identifiers(inputs, genomes)]
        commands = [_shell_join(["mkdir", "-p", out])]
        for genome, genome_name in zip(genomes, genome_names, strict=False):
            commands.append(_shell_join(["ln", "-s", genome, genome_name]))

        cmd = ["dRep", "compare", "outdir", "-g", *genome_names]
        comparison_steps = str(inputs.get("comparison_steps", inputs.get("select", "default")) or "default")
        if comparison_steps == "default":
            cls._add_mash_options(cmd, inputs)
            cls._add_secondary_options(cmd, inputs)
        elif comparison_steps == "SkipMash":
            cmd.append("--SkipMash")
            cls._add_secondary_options(cmd, inputs)
        else:
            cls._add_mash_options(cmd, inputs)
            cmd.append("--SkipSecondary")
        cmd.extend(["--clusterAlg", str(inputs.get("clusterAlg", "average"))])
        if inputs.get("run_tertiary_clustering"):
            cmd.append("--run_tertiary_clustering")
        cmd.extend(["--warn_dist", str(inputs.get("warn_dist", 0.25))])
        cmd.extend(["--warn_sim", str(inputs.get("warn_sim", 0.98))])
        cmd.extend(["--warn_aln", str(inputs.get("warn_aln", 0.25))])
        cmd.extend(["--processors", f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        commands.append(_shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}"))
        for output in cls._selected_outputs(inputs):
            source, filename = cls.OUTPUTS[output]
            commands.append(_shell_join(["cp", source, f"{out}/{filename}"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUTS[output][1] for output in cls._selected_outputs(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genomes": ("FASTA_LIST", {"multiple": True, "min": 2, "description": "Genome FASTA files to compare"}),
            },
            "optional": {
                "genome_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy collection element identifiers"},
                ),
                "comparison_steps": (
                    "STRING",
                    {"default": "default", "options": cls.COMPARISON_STEPS, "description": "Genome comparison stages to run"},
                ),
                "MASH_sketch": ("INT", {"default": 1000, "min": 0, "description": "Mash sketch size"}),
                "P_ani": ("FLOAT", {"default": 0.9, "min": 0, "max": 1, "description": "ANI threshold for primary clusters"}),
                "multiround_primary_clustering": (
                    "BOOLEAN",
                    {"default": False, "description": "Cluster primary chunks separately before merging"},
                ),
                "primary_chunksize": ("INT", {"default": 5000, "min": 1, "description": "Genome chunk size for primary clustering"}),
                "S_algorithm": (
                    "STRING",
                    {"default": "ANImf", "options": cls.SECONDARY_ALGORITHMS, "description": "Secondary clustering algorithm"},
                ),
                "greedy_secondary_clustering": (
                    "BOOLEAN",
                    {"default": False, "description": "Use greedy secondary clustering with fastANI"},
                ),
                "n_PRESET": ("STRING", {"default": "normal", "options": cls.NUCMER_PRESETS, "description": "Nucmer preset"}),
                "coverage_method": (
                    "STRING",
                    {"default": "larger", "options": cls.COVERAGE_METHODS, "description": "Alignment coverage calculation"},
                ),
                "S_ani": ("FLOAT", {"default": 0.99, "min": 0, "max": 1, "description": "ANI threshold for secondary clusters"}),
                "cov_thresh": ("FLOAT", {"default": 0.1, "min": 0, "max": 1, "description": "Minimum overlap for secondary comparisons"}),
                "clusterAlg": ("STRING", {"default": "average", "options": cls.CLUSTER_ALGORITHMS, "description": "SciPy linkage algorithm"}),
                "run_tertiary_clustering": ("BOOLEAN", {"default": False, "description": "Run an additional clustering pass"}),
                "warn_dist": ("FLOAT", {"default": 0.25, "min": 0, "max": 1, "description": "Distance from threshold for cluster warnings"}),
                "warn_sim": ("FLOAT", {"default": 0.98, "min": 0, "max": 1, "description": "Similarity threshold for warnings"}),
                "warn_aln": ("FLOAT", {"default": 0.25, "min": 0, "max": 1, "description": "Minimum aligned fraction for warnings"}),
                "select_outputs": (
                    "STRING_LIST",
                    {"default": cls.DEFAULT_OUTPUTS.copy(), "options": list(cls.OUTPUTS), "description": "Galaxy dRep outputs to collect"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if len(cls._genomes(inputs)) < 2:
            return "at least two genome FASTA files are required"
        comparison_steps = str(inputs.get("comparison_steps", inputs.get("select", "default")) or "default")
        if comparison_steps not in cls.COMPARISON_STEPS:
            return "comparison_steps must be one of: default, SkipMash, SkipSecondary"
        algorithm = str(inputs.get("S_algorithm", "ANImf") or "ANImf")
        if algorithm not in cls.SECONDARY_ALGORITHMS:
            return "S_algorithm must be one of: fastANI, ANImf, ANIn, gANI, goANI"
        if str(inputs.get("n_PRESET", "normal") or "normal") not in cls.NUCMER_PRESETS:
            return "n_PRESET must be one of: normal, tight"
        if str(inputs.get("coverage_method", "larger") or "larger") not in cls.COVERAGE_METHODS:
            return "coverage_method must be one of: larger, total"
        if str(inputs.get("clusterAlg", "average") or "average") not in cls.CLUSTER_ALGORITHMS:
            return "clusterAlg must be one of: average, ward, single, median, centroid, weighted"
        for name, minimum in {"MASH_sketch": 0, "primary_chunksize": 1, "threads": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name in ["P_ani", "S_ani", "cov_thresh", "warn_dist", "warn_sim", "warn_aln"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if not 0 <= value <= 1:
                return f"{name} must be between 0 and 1"
        return super().VALIDATE_INPUTS(inputs)

class DrepDereplicateNode(DrepCompareNode):
    """De-replicate genome FASTA files with dRep."""

    NODE_ID = "drep_dereplicate"
    DISPLAY_NAME = "dRep dereplicate"
    REQUIRED_CONDA_PACKAGES = ["drep", "checkm-genome"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "De-replicate genome sets with dRep, genome quality filtering, and representative genome scoring."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "dRep",
        "dRep dereplicate",
        "dRep genome dereplication",
        "bin dereplication",
        "metagenome genome recovery",
        "representative genomes",
    ]
    RETURN_TYPES = ("DIRECTORY", "TXT", "TXT", "PDF", "PDF", "PDF", "PDF", "CSV", "CSV", "CSV", "CSV", "PDF", "PDF", "CSV", "TSV")
    RETURN_NAMES = (
        "dereplicated_genomes",
        "log",
        "warnings",
        "primary_clustering_dendrogram",
        "secondary_clustering_dendrograms",
        "secondary_clustering_mds",
        "clustering_scatterplots",
        "bdb",
        "cdb",
        "mdb",
        "ndb",
        "cluster_scoring",
        "winning_genomes",
        "widb",
        "chdb",
    )
    REQUIRED_EXECUTABLES = ["dRep"]
    DOCUMENTATION_URL = "https://drep.readthedocs.io/en/latest/overview.html#genome-de-replication"
    CITATION_DOIS = [DREP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{DREP_CITATION_DOI}"]
    CITATION_TEXT = DREP_CITATION_TEXT
    VERSION = "3.6.2"
    SHELL = True

    QUALITY_SOURCES = ["checkm", "genomeInfo", "ignoreGenomeQuality"]
    CHECKM_METHODS = ["lineage_wf", "taxonomy_wf"]
    DEFAULT_OUTPUTS = [
        "log",
        "warnings",
        "Primary_clustering_dendrogram",
        "Clustering_scatterplots",
        "Cluster_scoring",
        "Winning_genomes",
        "Widb",
    ]
    OUTPUTS = {
        **DrepCompareNode.OUTPUTS,
        "Cluster_scoring": ("outdir/figures/Cluster_scoring.pdf", "Cluster_scoring.pdf"),
        "Winning_genomes": ("outdir/figures/Winning_genomes.pdf", "Winning_genomes.pdf"),
        "Widb": ("outdir/data_tables/Widb.csv", "Widb.csv"),
        "Chdb": ("outdir/data/checkM/checkM_outdir/Chdb.tsv", "Chdb.tsv"),
    }

    @classmethod
    def _add_filter_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(["--length", str(inputs.get("length", 50000))])
        cmd.extend(["--completeness", str(inputs.get("completeness", 75))])
        cmd.extend(["--contamination", str(inputs.get("contamination", 25))])

    @classmethod
    def _add_quality_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        source = str(inputs.get("quality_source", inputs.get("source", "checkm")) or "checkm")
        if source == "checkm":
            cmd.extend(["--checkM_method", str(inputs.get("checkM_method", "lineage_wf"))])
            if str(inputs.get("set_recursion", "")) != "":
                cmd.extend(["--set_recurison", str(inputs.get("set_recursion"))])
            cmd.extend(["--checkm_group_size", str(inputs.get("checkm_group_size", 2000))])
        elif source == "genomeInfo":
            cmd.extend(["--genomeInfo", str(inputs.get("genomeInfo", ""))])
        else:
            cmd.append("--ignoreGenomeQuality")

    @classmethod
    def _add_scoring_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(["--completeness_weight", str(inputs.get("completeness_weight", 1))])
        cmd.extend(["--contamination_weight", str(inputs.get("contamination_weight", 5))])
        cmd.extend(["--strain_heterogeneity_weight", str(inputs.get("strain_heterogeneity_weight", 1))])
        cmd.extend(["--N50_weight", str(inputs.get("N50_weight", 0.5))])
        cmd.extend(["--size_weight", str(inputs.get("size_weight", 0))])
        cmd.extend(["--centrality_weight", str(inputs.get("centrality_weight", 1))])
        if str(inputs.get("extra_weight_table", "")) != "":
            cmd.extend(["--extra_weight_table", str(inputs.get("extra_weight_table"))])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        genomes = cls._genomes(inputs)
        genome_names = [f"{identifier}.fasta" for identifier in cls._genome_identifiers(inputs, genomes)]
        commands = [_shell_join(["mkdir", "-p", out])]
        for genome, genome_name in zip(genomes, genome_names, strict=False):
            commands.append(_shell_join(["ln", "-s", genome, genome_name]))

        cmd = ["dRep", "dereplicate", "outdir", "-g", *genome_names]
        cls._add_filter_options(cmd, inputs)
        cls._add_quality_options(cmd, inputs)
        comparison_steps = str(inputs.get("comparison_steps", inputs.get("select", "default")) or "default")
        if comparison_steps == "default":
            cls._add_mash_options(cmd, inputs)
            cls._add_secondary_options(cmd, inputs)
        elif comparison_steps == "SkipMash":
            cmd.append("--SkipMash")
            cls._add_secondary_options(cmd, inputs)
        else:
            cls._add_mash_options(cmd, inputs)
            cmd.append("--SkipSecondary")
        cmd.extend(["--clusterAlg", str(inputs.get("clusterAlg", "average"))])
        if inputs.get("run_tertiary_clustering"):
            cmd.append("--run_tertiary_clustering")
        cls._add_scoring_options(cmd, inputs)
        cmd.extend(["--warn_dist", str(inputs.get("warn_dist", 0.25))])
        cmd.extend(["--warn_sim", str(inputs.get("warn_sim", 0.98))])
        cmd.extend(["--warn_aln", str(inputs.get("warn_aln", 0.25))])
        cmd.extend(["--processors", f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"])
        commands.append(
            _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")
            + " || (rc=$?; ls -ltr `find outdir -type f`; cat outdir/data/checkM/checkM_outdir/checkm.log; "
            "cat outdir/log/logger.log; exit $rc)"
        )
        commands.append(_shell_join(["cp", "-r", "outdir/dereplicated_genomes", f"{out}/dereplicated_genomes"]))
        for output in cls._selected_outputs(inputs):
            source, filename = cls.OUTPUTS[output]
            commands.append(_shell_join(["cp", source, f"{out}/{filename}"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "dereplicated_genomes").mkdir(parents=True, exist_ok=True)
        return [out / "dereplicated_genomes", *[out / cls.OUTPUTS[output][1] for output in cls._selected_outputs(inputs)]]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        parent = super().INPUT_TYPES()
        optional = dict(parent["optional"])
        optional.update(
            {
                "length": ("INT", {"default": 50000, "min": 1, "description": "Minimum genome length"}),
                "completeness": ("INT", {"default": 75, "min": 0, "max": 100, "description": "Minimum genome completeness percent"}),
                "contamination": ("INT", {"default": 25, "min": 0, "max": 100, "description": "Maximum genome contamination percent"}),
                "quality_source": (
                    "STRING",
                    {"default": "checkm", "options": cls.QUALITY_SOURCES, "description": "Genome quality filtering source"},
                ),
                "checkM_method": ("STRING", {"default": "lineage_wf", "options": cls.CHECKM_METHODS, "description": "CheckM workflow"}),
                "set_recursion": ("INT", {"default": "", "min": 1, "advanced": True, "description": "Optional Python recursion limit"}),
                "checkm_group_size": ("INT", {"default": 2000, "min": 1, "description": "Number of genomes passed to CheckM at a time"}),
                "genomeInfo": ("CSV", {"default": "", "description": "CSV quality information for genomes"}),
                "completeness_weight": ("FLOAT", {"default": 1, "description": "Scoring weight for completeness"}),
                "contamination_weight": ("FLOAT", {"default": 5, "description": "Scoring weight for contamination"}),
                "strain_heterogeneity_weight": (
                    "FLOAT",
                    {"default": 1, "min": 0, "max": 1, "description": "Scoring weight for strain heterogeneity"},
                ),
                "N50_weight": ("FLOAT", {"default": 0.5, "description": "Scoring weight for log genome N50"}),
                "size_weight": ("FLOAT", {"default": 0, "description": "Scoring weight for log genome size"}),
                "centrality_weight": ("FLOAT", {"default": 1, "description": "Scoring weight for cluster centrality"}),
                "extra_weight_table": ("TSV", {"default": "", "description": "Genome-specific extra scoring weights"}),
                "select_outputs": (
                    "STRING_LIST",
                    {"default": cls.DEFAULT_OUTPUTS.copy(), "options": list(cls.OUTPUTS), "description": "Galaxy dRep outputs to collect"},
                ),
            }
        )
        return {
            "required": parent["required"],
            "optional": optional,
            "hidden": parent["hidden"],
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        quality_source = str(inputs.get("quality_source", inputs.get("source", "checkm")) or "checkm")
        if quality_source not in cls.QUALITY_SOURCES:
            return "quality_source must be one of: checkm, genomeInfo, ignoreGenomeQuality"
        if quality_source == "genomeInfo" and not str(inputs.get("genomeInfo", "")).strip():
            return "genomeInfo is required"
        if str(inputs.get("checkM_method", "lineage_wf") or "lineage_wf") not in cls.CHECKM_METHODS:
            return "checkM_method must be one of: lineage_wf, taxonomy_wf"
        for name, minimum in {"length": 1, "checkm_group_size": 1, "set_recursion": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name in ["completeness", "contamination"]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if not 0 <= value <= 100:
                return f"{name} must be between 0 and 100"
        for name in [
            "completeness_weight",
            "contamination_weight",
            "strain_heterogeneity_weight",
            "N50_weight",
            "size_weight",
            "centrality_weight",
        ]:
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if name == "strain_heterogeneity_weight" and not 0 <= value <= 1:
                return "strain_heterogeneity_weight must be between 0 and 1"
        return True

pin_contract(DrepCompareNode)
pin_contract(DrepDereplicateNode)

__all__ = ['DrepCompareNode', 'DrepDereplicateNode']
