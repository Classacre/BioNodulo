"""Source-pinned BCFtools 1.24 plugin nodes."""

from __future__ import annotations

from typing import Any

from .adapter import (
    COMMON_FILTER_INPUTS,
    BCFtoolsCommandNode,
    FixedVcfOutputNode,
    add_common_filters,
    add_fixed_vcf_output,
    add_flag,
    add_plugin_separator,
    add_value,
    as_list,
    common_input_types,
    require_path,
    uses_regions,
    validate_choice,
    validate_data_index,
    validate_exclusive,
)


def _plugin_transform(
    node: type[FixedVcfOutputNode],
    plugin: str,
    inputs: dict[str, Any],
    plugin_arguments: list[str] | None = None,
    *,
    common_filters: bool = False,
) -> list[str]:
    command = ["bcftools", f"+{plugin}"]
    if common_filters:
        add_common_filters(command, inputs)
    add_fixed_vcf_output(command, node, inputs)
    command.append(str(inputs["input_file"]))
    add_plugin_separator(command, plugin_arguments or [])
    return command


class BCFtoolsPluginCountsNode(BCFtoolsCommandNode):
    """Retain the complete six-category output written by +counts."""

    NODE_ID = "bcftools_plugin_counts"
    DISPLAY_NAME = "BCFtools +counts"
    DESCRIPTION = "Count samples, SNPs, INDELs, MNPs, other variants, and all sites"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "counts", "variant counts"]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("counts",)
    OUTPUT_FILENAMES = ("counts.txt",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/counts.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        schema = common_input_types()
        schema["optional"] = dict(COMMON_FILTER_INPUTS)
        return schema

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        if uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "+counts"]
        add_common_filters(command, inputs)
        command.append(str(inputs["input_file"]))
        return command


class BCFtoolsPluginDosageNode(BCFtoolsCommandNode):
    """Print genotype dosage using an ordered documented tag preference."""

    NODE_ID = "bcftools_plugin_dosage"
    DISPLAY_NAME = "BCFtools +dosage"
    DESCRIPTION = "Print per-sample genotype dosage from PL, GL, or GT tags"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "dosage", "genotype dosage"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("dosage_table",)
    OUTPUT_FILENAMES = ("dosage.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/dosage.c"
    TAGS = ("PL", "GL", "GT")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF containing dosage source tags"})},
            "optional": {"tags": ("STRING_LIST", {"default": ["PL", "GL", "GT"], "options": list(cls.TAGS)})},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        tags = as_list(inputs.get("tags", ["PL", "GL", "GT"]))
        if not tags:
            return "tags must contain at least one of PL, GL, GT"
        if len(tags) != len(set(tags)) or any(tag not in cls.TAGS for tag in tags):
            return "tags must be an ordered unique subset of: PL, GL, GT"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        tags = ",".join(as_list(inputs.get("tags", ["PL", "GL", "GT"])))
        return ["bcftools", "+dosage", str(inputs["input_file"]), "--", "-t", tags]


class BCFtoolsPluginMissing2refNode(FixedVcfOutputNode):
    """Set fully missing genotypes to reference or the major allele."""

    NODE_ID = "bcftools_plugin_missing2ref"
    DISPLAY_NAME = "BCFtools +missing2ref"
    DESCRIPTION = "Set missing genotypes to reference or the major allele"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "missing2ref", "missing genotypes"]
    RETURN_NAMES = ("missing2ref_vcf",)
    OUTPUT_FILENAME = "missing2ref.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/missing2ref.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF with missing genotypes"})},
            "optional": {
                "phased": ("BOOLEAN", {"default": False}),
                "major": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return require_path(inputs, "input_file")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        arguments: list[str] = []
        add_flag(arguments, "--phased", inputs.get("phased"))
        add_flag(arguments, "--major", inputs.get("major"))
        return _plugin_transform(cls, "missing2ref", inputs, arguments)


class BCFtoolsPluginTag2tagNode(FixedVcfOutputNode):
    """Perform one explicit conversion between related FORMAT tag families."""

    NODE_ID = "bcftools_plugin_tag2tag"
    DISPLAY_NAME = "BCFtools +tag2tag"
    DESCRIPTION = "Convert between genotype likelihood, quality, and localized FORMAT tags"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "tag2tag", "GL PL GP conversion"]
    RETURN_NAMES = ("tag2tag_vcf",)
    OUTPUT_FILENAME = "tag2tag.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/tag2tag.c"
    CONVERSIONS = (
        "GP-to-GL", "GP-to-PL", "GP-to-GT", "GL-to-GP", "GL-to-PL", "GL-to-GT",
        "PL-to-GL", "PL-to-GP", "PL-to-GT", "QR-QA-to-QS", "LXX-to-XX",
        "LPL-to-PL", "LAD-to-AD", "XX-to-LXX", "PL-to-LPL", "AD-to-LAD",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF containing source FORMAT tags"})},
            "optional": {
                "conversion": ("STRING", {"default": "GP-to-GL", "options": list(cls.CONVERSIONS)}),
                "replace": ("BOOLEAN", {"default": False}),
                "threshold": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0}),
                "skip_nalt": ("INT", {"default": 0, "min": 0}),
                "defaults": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        return validate_choice(str(inputs.get("conversion", "GP-to-GL")), "conversion", cls.CONVERSIONS)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        arguments = [f"--{inputs.get('conversion', 'GP-to-GL')}"]
        add_flag(arguments, "--replace", inputs.get("replace"))
        if inputs.get("threshold", 0.0):
            arguments.extend(["--threshold", str(inputs["threshold"])])
        if inputs.get("skip_nalt", 0):
            arguments.extend(["--skip-nalt", str(inputs["skip_nalt"])])
        add_value(arguments, "--defaults", inputs.get("defaults"))
        return _plugin_transform(cls, "tag2tag", inputs, arguments)


class BCFtoolsPluginFillAnAcNode(FixedVcfOutputNode):
    """Expose the distinct deprecated +fill-AN-AC operation faithfully."""

    NODE_ID = "bcftools_plugin_fill_an_ac"
    DISPLAY_NAME = "BCFtools +fill-AN-AC"
    DESCRIPTION = "Fill INFO/AN and INFO/AC with the deprecated dedicated plugin"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "fill-AN-AC", "allele counts"]
    RETURN_NAMES = ("fill_an_ac_vcf",)
    OUTPUT_FILENAME = "fill_an_ac.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/fill-AN-AC.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {"required": {"input_file": ("VCF", {"description": "VCF with genotypes"})}, "optional": {}, "hidden": {"output": ("STRING", {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return require_path(inputs, "input_file")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return _plugin_transform(cls, "fill-AN-AC", inputs)


class BCFtoolsPluginFillTagsNode(FixedVcfOutputNode):
    """Fill INFO/FORMAT tags, optionally by sample populations."""

    NODE_ID = "bcftools_plugin_fill_tags"
    DISPLAY_NAME = "BCFtools +fill-tags"
    DESCRIPTION = "Calculate documented INFO and FORMAT tags from sample genotypes"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "fill-tags", "allele frequency"]
    RETURN_NAMES = ("fill_tags_vcf",)
    OUTPUT_FILENAME = "fill_tags.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugin.fill-tags.html"
    UPSTREAM_SOURCE = "plugins/fill-tags.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF with genotypes"})},
            "optional": {
                "tags": ("STRING", {"default": "all", "description": "Comma-separated tags or expressions"}),
                "samples_file": ("TSV", {"default": "", "description": "Sample and population mapping"}),
                "drop_missing": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        if not str(inputs.get("tags", "all")).strip():
            return "tags must be non-empty"
        if inputs.get("samples") or inputs.get("invert_samples"):
            return "fill-tags supports only the plugin --samples-file population mapping"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        arguments = ["--tags", str(inputs.get("tags", "all"))]
        add_value(arguments, "--samples-file", inputs.get("samples_file"))
        add_flag(arguments, "--drop-missing", inputs.get("drop_missing"))
        return _plugin_transform(cls, "fill-tags", inputs, arguments)


class BCFtoolsPluginSetgtNode(FixedVcfOutputNode):
    """Set selected genotypes with the documented +setGT codes."""

    NODE_ID = "bcftools_plugin_setgt"
    DISPLAY_NAME = "BCFtools +setGT"
    DESCRIPTION = "Select genotypes and replace them with a documented genotype code"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "setGT", "set genotypes"]
    RETURN_NAMES = ("setgt_vcf",)
    OUTPUT_FILENAME = "setgt.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugin.setGT.html"
    UPSTREAM_SOURCE = "plugins/setGT.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF whose genotypes will be changed"})},
            "optional": {
                "target_gt": ("STRING", {"default": ".", "description": "./., ./x, ., a, b:EXPR, q, or r:FLOAT combinations"}),
                "new_gt": ("STRING", {"default": "0", "description": "., 0, c:GT, i, m, M, X, p, or u"}),
                "include": ("STRING", {"default": ""}),
                "exclude": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": 0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @staticmethod
    def _valid_target(value: str) -> bool:
        if value in {"./.", "./x", ".", "a", "q"}:
            return True
        if value.startswith("b:") and len(value) > 2:
            return True
        if value.startswith("r:"):
            try:
                return 0 < float(value[2:]) < 1
            except ValueError:
                return False
        return False

    @staticmethod
    def _valid_new(value: str) -> bool:
        if value in {".", "0", "i", "m", "M", "X", "p", "u", "0p"}:
            return True
        return value.startswith("c:") and len(value) > 2

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        target = str(inputs.get("target_gt", "."))
        if not cls._valid_target(target):
            return "target_gt is not a documented +setGT target code"
        new_gt = str(inputs.get("new_gt", "0"))
        if not cls._valid_new(new_gt):
            return "new_gt is not a documented +setGT replacement code"
        validation = validate_exclusive(inputs, "include", "exclude")
        if validation is not True:
            return validation
        has_expression = bool(inputs.get("include") or inputs.get("exclude"))
        has_query_target = "q" in target.split(",")
        if has_expression and not has_query_target:
            return "include or exclude requires target_gt containing q"
        if has_query_target and not has_expression:
            return "target_gt=q requires include or exclude"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        arguments = ["-t", str(inputs.get("target_gt", ".")), "-n", str(inputs.get("new_gt", "0"))]
        add_value(arguments, "--include", inputs.get("include"))
        add_value(arguments, "--exclude", inputs.get("exclude"))
        if inputs.get("seed", 0):
            arguments.extend(["--seed", str(inputs["seed"])])
        return _plugin_transform(cls, "setGT", inputs, arguments)


class BCFtoolsPluginFixploidyNode(FixedVcfOutputNode):
    """Resize FORMAT/GT according to a ploidy map or a forced ploidy."""

    NODE_ID = "bcftools_plugin_fixploidy"
    DISPLAY_NAME = "BCFtools +fixploidy"
    DESCRIPTION = "Fix genotype ploidy using a region map, sample sex, or one forced value"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "fixploidy", "genotype ploidy"]
    RETURN_NAMES = ("fixploidy_vcf",)
    OUTPUT_FILENAME = "fixploidy.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/fixploidy.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF with FORMAT/GT"})},
            "optional": {
                "ploidy_file": ("TSV", {"default": ""}),
                "sex": ("TSV", {"default": ""}),
                "default_ploidy": ("INT", {"default": 2, "min": 0}),
                "force_ploidy": ("INT", {"default": None, "min": 0}),
                "tags": ("STRING", {"default": "GT", "options": ["GT"]}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        if str(inputs.get("tags", "GT")) != "GT":
            return "tags must be GT; +fixploidy 1.24 supports only FORMAT/GT"
        if inputs.get("force_ploidy") not in (None, "") and inputs.get("ploidy_file"):
            return "force_ploidy and ploidy_file are mutually exclusive"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        arguments = ["--default-ploidy", str(inputs.get("default_ploidy", 2)), "--tags", "GT"]
        add_value(arguments, "--force-ploidy", inputs.get("force_ploidy"))
        add_value(arguments, "--ploidy", inputs.get("ploidy_file"))
        add_value(arguments, "--sex", inputs.get("sex"))
        return _plugin_transform(cls, "fixploidy", inputs, arguments)


class BCFtoolsPluginMendelianNode(FixedVcfOutputNode):
    """Annotate or filter VCF records using complete trio definitions."""

    NODE_ID = "bcftools_plugin_mendelian"
    DISPLAY_NAME = "BCFtools +mendelian2"
    DESCRIPTION = "Annotate Mendelian errors for one complete trio or trios from PED"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "mendelian2", "trio errors"]
    RETURN_NAMES = ("mendelian_vcf",)
    OUTPUT_FILENAME = "mendelian.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugin.mendelian.html"
    UPSTREAM_SOURCE = "plugins/mendelian2.c"
    MODES = frozenset("adeEgmMS")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF containing trio samples"})},
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "ped": ("TSV", {"default": ""}),
                "child": ("STRING", {"default": ""}),
                "father": ("STRING", {"default": ""}),
                "mother": ("STRING", {"default": ""}),
                "num_x": ("STRING", {"default": "2X", "options": ["1X", "2X"]}),
                "mode": ("STRING", {"default": "a", "description": "One or more VCF modes a,d,e,E,g,m,M,S"}),
                "rules": ("STRING", {"default": "GRCh37", "options": ["GRCh37", "GRCh38"]}),
                "rules_file": ("TSV", {"default": ""}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "trio_file": ("TSV", {"default": "", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _ped(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("ped") or inputs.get("trio_file")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        ped = cls._ped(inputs)
        inline = [str(inputs.get(key, "")).strip() for key in ("child", "father", "mother")]
        if ped and any(inline):
            return "ped and inline trio fields are mutually exclusive"
        if not ped and not all(inline):
            return "provide either ped or complete child, father, and mother fields"
        mode = str(inputs.get("mode", "a"))
        if not mode or any(char not in cls.MODES for char in mode):
            return "mode must contain only VCF modes: a, d, e, E, g, m, M, S"
        if inputs.get("rules_file") and inputs.get("rules") not in (None, "", "GRCh37"):
            return "rules and rules_file are mutually exclusive"
        for ignored in ("regions_overlap", "targets_overlap"):
            if inputs.get(ignored) not in (None, ""):
                return f"{ignored} is not accepted by +mendelian2 1.24"
        if uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "+mendelian2"]
        add_value(command, "--include", inputs.get("include"))
        add_value(command, "--exclude", inputs.get("exclude"))
        add_value(command, "--regions", inputs.get("regions"))
        add_value(command, "--regions-file", inputs.get("regions_file"))
        add_value(command, "--targets", inputs.get("targets"))
        add_value(command, "--targets-file", inputs.get("targets_file"))
        add_fixed_vcf_output(command, cls, inputs)
        command.append(str(inputs["input_file"]))
        arguments = ["--mode", str(inputs.get("mode", "a"))]
        if cls._ped(inputs):
            arguments.extend(["--ped", str(cls._ped(inputs))])
        else:
            arguments.extend(["--pfm", f"{inputs.get('num_x', '2X')}:{inputs['child']},{inputs['father']},{inputs['mother']}"])
        if inputs.get("rules_file"):
            arguments.extend(["--rules-file", str(inputs["rules_file"])])
        else:
            arguments.extend(["--rules", str(inputs.get("rules", "GRCh37"))])
        add_plugin_separator(command, arguments)
        return command


class BCFtoolsPluginImputeInfoNode(FixedVcfOutputNode):
    """Add IMPUTE2 INFO where FORMAT/GP is suitable and preserve other records."""

    NODE_ID = "bcftools_plugin_impute_info"
    DISPLAY_NAME = "BCFtools +impute-info"
    DESCRIPTION = "Add IMPUTE2 INFO from diploid biallelic FORMAT/GP probabilities"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "impute-info", "IMPUTE2 INFO"]
    RETURN_NAMES = ("impute_info_vcf",)
    OUTPUT_FILENAME = "impute_info.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/impute-info.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {"required": {"input_file": ("VCF", {"description": "VCF with FORMAT/GP probabilities"})}, "optional": {}, "hidden": {"output": ("STRING", {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return require_path(inputs, "input_file")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return _plugin_transform(cls, "impute-info", inputs)


class BCFtoolsPluginColorChrsNode(BCFtoolsCommandNode):
    """Write the native phased-segment prefix.dat artifact."""

    NODE_ID = "bcftools_plugin_color_chrs"
    DISPLAY_NAME = "BCFtools +color-chrs"
    DESCRIPTION = "Color shared phased chromosomal segments for one trio or unrelated pair"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "color-chrs", "phased segments"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("segments_table",)
    OUTPUT_FILENAMES = ("color_chrs.dat",)
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/color-chrs.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF with phased FORMAT/GT"})},
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "mother": ("STRING", {"default": ""}),
                "father": ("STRING", {"default": ""}),
                "child": ("STRING", {"default": ""}),
                "sample_a": ("STRING", {"default": ""}),
                "sample_b": ("STRING", {"default": ""}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "sample_rel_sel": ("STRING", {"default": "", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        trio = [str(inputs.get(key, "")).strip() for key in ("mother", "father", "child")]
        unrelated = [str(inputs.get(key, "")).strip() for key in ("sample_a", "sample_b")]
        if any(trio) and any(unrelated):
            return "trio and unrelated sample definitions are mutually exclusive"
        if not (all(trio) or all(unrelated)):
            return "provide either complete mother, father, child or complete sample_a, sample_b"
        if uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "+color-chrs"]
        add_common_filters(command, inputs)
        command.append(str(inputs["input_file"]))
        if inputs.get("mother"):
            relationship = ["--trio", f"{inputs['mother']},{inputs['father']},{inputs['child']}"]
        else:
            relationship = ["--unrelated", f"{inputs['sample_a']},{inputs['sample_b']}"]
        prefix = cls.output_dir(inputs) / "color_chrs"
        add_plugin_separator(command, [*relationship, "-p", str(prefix)])
        return command


class BCFtoolsPluginFrameshiftsNode(FixedVcfOutputNode):
    """Annotate frameshifts using pre-indexed BGZF exon intervals."""

    NODE_ID = "bcftools_plugin_frameshifts"
    DISPLAY_NAME = "BCFtools +frameshifts"
    DESCRIPTION = "Annotate out-of-frame indels from indexed BGZF exon intervals"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "frameshifts", "OOF annotation"]
    RETURN_NAMES = ("frameshifts_vcf",)
    OUTPUT_FILENAME = "frameshifts.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugins.html"
    UPSTREAM_SOURCE = "plugins/frameshifts.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("VCF", {"description": "VCF containing indels"}),
                "exons": ("BED", {"description": "BGZF-compressed exon intervals"}),
                "exons_index": ("VCF_INDEX", {"description": "Colocated TBI or CSI for exons"}),
            },
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("input_file", "exons"):
            validation = require_path(inputs, key)
            if validation is not True:
                return validation
        if not str(inputs["exons"]).lower().endswith((".gz", ".bgz", ".bgzf")):
            return "exons must be BGZF-compressed; provide the existing compressed file and index"
        validation = validate_data_index(inputs, data_key="exons", index_key="exons_index")
        if validation is not True:
            return validation
        if uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return _plugin_transform(
            cls,
            "frameshifts",
            inputs,
            ["--exons", str(inputs["exons"])],
            common_filters=True,
        )


class BCFtoolsPluginSplitVepNode(FixedVcfOutputNode):
    """Extract structured annotation columns into INFO tags."""

    NODE_ID = "bcftools_plugin_split_vep"
    DISPLAY_NAME = "BCFtools +split-vep"
    DESCRIPTION = "Extract structured CSQ, BCSQ, or ANN fields into compressed VCF INFO tags"
    SEARCH_ALIASES = ["BioNodulo builtin", "bcftools", "plugin", "split-vep", "structured annotations"]
    RETURN_NAMES = ("split_vep_vcf",)
    OUTPUT_FILENAME = "split_vep.vcf.gz"
    DOCUMENTATION_URL = "https://samtools.github.io/bcftools/howtos/plugin.split-vep.html"
    UPSTREAM_SOURCE = "plugins/split-vep.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input_file": ("VCF", {"description": "VCF with structured INFO annotations"})},
            "optional": {
                "input_index": COMMON_FILTER_INPUTS["input_index"],
                "annotation": ("STRING", {"default": "", "description": "Unset to auto-detect CSQ, BCSQ, then ANN"}),
                "columns": ("STRING", {"default": "", "description": "Fields or indexes to extract as INFO tags"}),
                "format": ("STRING", {"default": "", "description": "Compatibility signal for a requested query format"}),
                "duplicate": ("BOOLEAN", {"default": False}),
                "allow_undef_tags": ("BOOLEAN", {"default": False}),
                "annot_prefix": ("STRING", {"default": ""}),
                "select": ("STRING", {"default": ""}),
                "drop_sites": ("BOOLEAN", {"default": False}),
                "keep_sites": ("BOOLEAN", {"default": False}),
                "include": COMMON_FILTER_INPUTS["include"],
                "exclude": COMMON_FILTER_INPUTS["exclude"],
                "regions": COMMON_FILTER_INPUTS["regions"],
                "regions_file": COMMON_FILTER_INPUTS["regions_file"],
                "regions_overlap": COMMON_FILTER_INPUTS["regions_overlap"],
                "targets": COMMON_FILTER_INPUTS["targets"],
                "targets_file": COMMON_FILTER_INPUTS["targets_file"],
                "targets_overlap": COMMON_FILTER_INPUTS["targets_overlap"],
                "a": ("STRING", {"default": "", "advanced": True}),
                "c": ("STRING", {"default": "", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _annotation(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("annotation") or inputs.get("a")

    @classmethod
    def _columns(cls, inputs: dict[str, Any]) -> Any:
        return inputs.get("columns") or inputs.get("c")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = require_path(inputs, "input_file")
        if validation is not True:
            return validation
        if not str(cls._columns(inputs) or inputs.get("format") or "").strip():
            return "columns or format must be non-empty; refusing a no-op split-vep transform"
        if inputs.get("format") and not cls._columns(inputs):
            return "format-only split-vep produces text, not the focused VCF_GZ artifact; provide columns"
        if inputs.get("drop_sites") and inputs.get("keep_sites"):
            return "drop_sites and keep_sites are mutually exclusive"
        if uses_regions(inputs):
            validation = validate_data_index(inputs)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = ["bcftools", "+split-vep"]
        add_value(command, "--annotation", cls._annotation(inputs))
        add_value(command, "--columns", cls._columns(inputs))
        add_flag(command, "--duplicate", inputs.get("duplicate"))
        add_flag(command, "--allow-undef-tags", inputs.get("allow_undef_tags"))
        add_value(command, "--annot-prefix", inputs.get("annot_prefix"))
        add_value(command, "--select", inputs.get("select"))
        add_flag(command, "--drop-sites", inputs.get("drop_sites"))
        add_flag(command, "--keep-sites", inputs.get("keep_sites"))
        add_common_filters(command, inputs)
        add_fixed_vcf_output(command, cls, inputs)
        command.append(str(inputs["input_file"]))
        return command
