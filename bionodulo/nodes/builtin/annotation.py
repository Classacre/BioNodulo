"""Genome annotation nodes for BioNodulo.

Provides nodes for prokaryotic genome annotation with Prokka and Bakta,
and functional annotation with eggNOG-mapper.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


class ProkkaNode(CommandNode):
    """Prokaryotic genome annotation with Prokka."""
    NODE_ID = "prokka"
    DISPLAY_NAME = "Prokka"
    REQUIRED_CONDA_PACKAGES = ['prokka']
    CATEGORY = "annotation"
    DESCRIPTION = "Rapid prokaryotic genome annotation"
    SEARCH_ALIASES = ["prokka", "annotate", "bacteria", "archaea", "genome"]
    RETURN_TYPES = ("GFF", "GBK", "FAA")
    RETURN_NAMES = ("gff", "genbank", "proteins")
    REQUIRED_EXECUTABLES = ["prokka"]
    DOCUMENTATION_URL = "https://github.com/tseemann/prokka"
    VERSION = "1.15.6"
    COMMAND = [
        "prokka",
        "--outdir", "{output}",
        "--prefix", "{inputs.prefix}",
        "--cpus", "{inputs.threads}",
        "--kingdom", "{inputs.kingdom}",
        "--force",
        "{inputs.assembly}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("ASSEMBLY", {"description": "Genome assembly FASTA"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "genome"}),
            },
            "optional": {
                "kingdom": ("STRING", {"default": "Bacteria"}),
                "genus": ("STRING", {"default": ""}),
                "species": ("STRING", {"default": ""}),
                "strain": ("STRING", {"default": ""}),
                "gcode": ("INT", {"default": 11, "min": 1, "max": 33}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "prokka",
            "--outdir", str(inputs.get("output", ".")),
            "--prefix", str(inputs.get("prefix", "genome")),
            "--cpus", str(inputs.get("threads", 8)),
            "--kingdom", str(inputs.get("kingdom", "Bacteria")),
            "--force",
            str(inputs.get("assembly", "")),
        ]
        if inputs.get("genus"):
            cmd.extend(["--genus", str(inputs["genus"])])
        if inputs.get("species"):
            cmd.extend(["--species", str(inputs["species"])])
        if inputs.get("strain"):
            cmd.extend(["--strain", str(inputs["strain"])])
        if inputs.get("gcode") is not None:
            cmd.extend(["--gcode", str(inputs["gcode"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        prefix = inputs.get("prefix", "genome")
        od = Path(output_dir)
        return [
            od / cls.NODE_ID / f"{prefix}.gff",
            od / cls.NODE_ID / f"{prefix}.gbk",
            od / cls.NODE_ID / f"{prefix}.faa",
        ]

    async def run(self, **kwargs: Any) -> Any:
        """Run Prokka and copy outputs to planned paths."""
        result = await super().run(**kwargs)
        import shutil
        from pathlib import Path
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get("prefix", "genome")
        files = [f"{prefix}.gff", f"{prefix}.gbk", f"{prefix}.faa"]
        for i, fname in enumerate(files):
            if i < len(outputs):
                actual = node_out / fname
                if actual.exists():
                    outputs[i].parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(actual), str(outputs[i]))
        return result


class BaktaNode(CommandNode):
    """Prokaryotic annotation with Bakta (Prokka successor)."""
    NODE_ID = "bakta"
    DISPLAY_NAME = "Bakta"
    CATEGORY = "annotation"
    DESCRIPTION = "Rapid & standardized annotation of bacterial genomes"
    SEARCH_ALIASES = ["bakta", "annotate", "bacteria", "annotation"]
    RETURN_TYPES = ("GFF3", "FAA")
    RETURN_NAMES = ("gff", "proteins")
    REQUIRED_EXECUTABLES = ["bakta"]
    REQUIRED_CONDA_PACKAGES = ['bakta']
    DOCUMENTATION_URL = "https://github.com/oschwengers/bakta"
    VERSION = "1.12.0"
    COMMAND = [
        "bakta",
        "--output", "{output}",
        "--prefix", "{inputs.prefix}",
        "--threads", "{inputs.threads}",
        "{inputs.assembly}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "assembly": ("ASSEMBLY", {"description": "Genome assembly FASTA"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "genome"}),
            },
            "optional": {
                "db": ("DIRECTORY", {"description": "Bakta DB path"}),
                "translation_table": ("INT", {"default": 11}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "bakta",
            "--output", str(inputs.get("output", ".")),
            "--prefix", str(inputs.get("prefix", "genome")),
            "--threads", str(inputs.get("threads", 8)),
            str(inputs.get("assembly", "")),
        ]
        if inputs.get("db"):
            cmd.extend(["--db", str(inputs["db"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        prefix = inputs.get("prefix", "genome")
        od = Path(output_dir)
        return [
            od / cls.NODE_ID / f"{prefix}.gff3",
            od / cls.NODE_ID / f"{prefix}.faa",
        ]

    async def run(self, **kwargs: Any) -> Any:
        """Run Bakta and copy outputs to planned paths."""
        result = await super().run(**kwargs)
        import shutil
        from pathlib import Path
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get("prefix", "genome")
        files = [f"{prefix}.gff3", f"{prefix}.faa"]
        for i, fname in enumerate(files):
            if i < len(outputs):
                actual = node_out / fname
                if actual.exists():
                    outputs[i].parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(actual), str(outputs[i]))
        return result


class EggNOGMapperNode(CommandNode):
    """Functional annotation with eggNOG-mapper."""
    NODE_ID = "eggnog_mapper"
    DISPLAY_NAME = "eggNOG-mapper"
    CATEGORY = "annotation"
    DESCRIPTION = "Fast genome-wide functional annotation via orthology"
    SEARCH_ALIASES = ["eggnog", "emapper", "functional", "cog", "go"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("annotations",)
    REQUIRED_EXECUTABLES = ["emapper.py"]
    REQUIRED_CONDA_PACKAGES = ['eggnog-mapper']
    DOCUMENTATION_URL = "https://github.com/eggnogdb/eggnog-mapper"
    VERSION = "2.1.14"
    COMMAND = [
        "emapper.py",
        "-i", "{inputs.proteins}",
        "--output", "{inputs.prefix}",
        "--output_dir", "{output}",
        "-m", "{inputs.mode}",
        "--cpu", "{inputs.threads}",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "proteins": ("FASTA", {"description": "Protein FASTA file (.faa)"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
                "prefix": ("STRING", {"default": "annotations"}),
            },
            "optional": {
                "mode": ("STRING", {"default": "diamond", "description": "Search mode: diamond, mmseqs, or hmmer"}),
                "data_dir": ("DIRECTORY", {"description": "eggNOG data directory"}),
                "itype": ("STRING", {"default": "proteins", "options": ["proteins", "CDS", "genome", "metagenome"], "label": "Input Type", "advanced": True}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "emapper.py",
            "-i", str(inputs.get("proteins", "")),
            "--output", str(inputs.get("prefix", "annotations")),
            "--output_dir", str(inputs.get("output", ".")),
            "-m", str(inputs.get("mode", "diamond")),
            "--cpu", str(inputs.get("threads", 8)),
        ]
        if inputs.get("data_dir"):
            cmd.extend(["--data_dir", str(inputs["data_dir"])])
        if inputs.get("itype"):
            cmd.extend(["--itype", str(inputs["itype"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        prefix = inputs.get("prefix", "annotations")
        od = Path(output_dir)
        return [od / cls.NODE_ID / f"{prefix}.annotations.tsv"]

    async def run(self, **kwargs: Any) -> Any:
        """Run eggNOG-mapper and copy annotations to planned path."""
        result = await super().run(**kwargs)
        import shutil
        from pathlib import Path
        node_out = Path(kwargs["output_dir"])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get("prefix", "annotations")
        if outputs:
            outputs[0].parent.mkdir(parents=True, exist_ok=True)
            actual = node_out / f"{prefix}.annotations"
            if actual.exists():
                shutil.copy2(str(actual), str(outputs[0]))
        return result


class SnpEffNode(CommandNode):
    """Annotate variants and predict effects with SnpEff."""
    NODE_ID = "snpeff"
    DISPLAY_NAME = "SnpEff"
    CATEGORY = "annotation"
    DESCRIPTION = "Fast variant annotation: missense, nonsense, frameshift, splice site. Supports many genomes."
    SEARCH_ALIASES = ["snpeff", "variant annotation", "effect prediction", "functional effect"]
    RETURN_TYPES = ("VCF", "HTML_REPORT")
    RETURN_NAMES = ("annotated_vcf", "summary_report")
    REQUIRED_EXECUTABLES = ["snpEff"]
    REQUIRED_CONDA_PACKAGES = ["snpeff"]
    DOCUMENTATION_URL = "https://pcingola.github.io/SnpEff/"
    VERSION = "5.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        genome = str(inputs.get("genome", "GRCh38"))
        cmd = [
            "java",
            "-jar",
            f"-Xmx{inputs.get('memory', 4)}g",
            "snpEff.jar",
            "-v",
            "-stats",
            f"{out_dir}/summary_report.html",
        ]
        if inputs.get("canonical"):
            cmd.append("-canon")
        if inputs.get("no_upstream"):
            cmd.append("-no-upstream")
        if inputs.get("no_downstream"):
            cmd.append("-no-downstream")
        if inputs.get("no_intergenic"):
            cmd.append("-no-intergenic")
        cmd.extend([genome, str(inputs.get("vcf", "")), ">", f"{out_dir}/annotated_vcf.vcf"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "annotated_vcf.vcf", node_out / "summary_report.html"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "VCF to annotate"}),
                "genome": ("STRING", {"default": "GRCh38", "description": "SnpEff genome (GRCh38, GRCh37, GRCm39)"}),
                "memory": ("INT", {"default": 4, "min": 1, "max": 128, "label": "Max Memory (GB)"}),
            },
            "optional": {
                "canonical": ("BOOLEAN", {"default": False, "description": "Canonical transcripts only"}),
                "no_upstream": ("BOOLEAN", {"default": False}),
                "no_downstream": ("BOOLEAN", {"default": False}),
                "no_intergenic": ("BOOLEAN", {"default": False}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class VEPNode(CommandNode):
    """Annotate variants with Ensembl Variant Effect Predictor."""
    NODE_ID = "vep"
    DISPLAY_NAME = "VEP"
    CATEGORY = "annotation"
    DESCRIPTION = "Ensembl Variant Effect Predictor. Comprehensive functional annotation with frequencies, clinical significance."
    SEARCH_ALIASES = ["vep", "variant effect predictor", "ensembl", "variant annotation", "clinvar"]
    RETURN_TYPES = ("VCF", "HTML_REPORT")
    RETURN_NAMES = ("annotated_vcf", "vep_report")
    REQUIRED_EXECUTABLES = ["vep"]
    REQUIRED_CONDA_PACKAGES = ["ensembl-vep"]
    DOCUMENTATION_URL = "https://www.ensembl.org/info/docs/tools/vep/"
    VERSION = "113"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        vcf = str(inputs.get("vcf", ""))
        fmt = str(inputs.get("output_format", "vcf"))
        cmd = [
            "vep",
            "-i",
            vcf,
            "-o",
            f"{out_dir}/annotated_vcf.{fmt}",
            "--format",
            "vcf",
            f"--{fmt}",
            "--fork",
            str(inputs.get("threads", 4)),
            "--assembly",
            str(inputs.get("assembly", "GRCh38")),
            "--cache",
            "--dir_cache",
            str(inputs.get("cache_dir", "~/.vep")),
        ]
        if inputs.get("everything"):
            cmd.append("--everything")
        if inputs.get("symbol"):
            cmd.append("--symbol")
        if inputs.get("af"):
            cmd.append("--af")
        if inputs.get("max_af"):
            cmd.append("--max_af")
        if inputs.get("sift"):
            cmd.extend(["--sift", str(inputs["sift"])])
        if inputs.get("polyphen"):
            cmd.extend(["--polyphen", str(inputs["polyphen"])])
        if inputs.get("clinvar"):
            cmd.extend(["--custom", f"{inputs['clinvar']},ClinVar,vcf,exact,0,CLNSIG"])
        cmd.extend(["--stats_file", f"{out_dir}/vep_report.html"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        fmt = str(inputs.get("output_format", "vcf"))
        return [node_out / f"annotated_vcf.{fmt}", node_out / "vep_report.html"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("VCF_GZ", {"description": "Input VCF"}),
                "assembly": ("STRING", {"default": "GRCh38"}),
                "cache_dir": ("DIRECTORY", {"description": "VEP cache (~10-20GB)"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "everything": ("BOOLEAN", {"default": True}),
                "symbol": ("BOOLEAN", {"default": True}),
                "af": ("BOOLEAN", {"default": True}),
                "max_af": ("BOOLEAN", {"default": True}),
                "sift": ("STRING", {"default": "b", "options": ["b", "s", "p"]}),
                "polyphen": ("STRING", {"default": "b", "options": ["b", "s", "p"]}),
                "clinvar": ("VCF_GZ", {"description": "ClinVar VCF"}),
                "output_format": ("STRING", {"default": "vcf", "options": ["vcf", "tab"]}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
