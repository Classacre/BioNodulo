"""Genome annotation nodes for BioNodulo.

Provides nodes for prokaryotic genome annotation with Prokka and Bakta,
and functional annotation with eggNOG-mapper.
"""
from __future__ import annotations

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
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
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
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
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
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str) -> list:
        from pathlib import Path
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
