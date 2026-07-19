"""Shared validation and wrapper authority for assembly and typing contracts."""

from __future__ import annotations

import math
from typing import Any

from bionodulo.nodes.command_node import CommandNode


TOOLS_IUC_GIT_URL = "https://github.com/galaxyproject/tools-iuc.git"
TOOLS_IUC_GIT_COMMIT = "8eb66da1f6f16fde92688ee6c500d2bcdc924a47"
CHEWBBACA_GALAXY1_GIT_COMMIT = "4aa71967426065e30613cbe151c32614363eaf1e"


class ValidatedCommandContract(CommandNode):
    """Validate declared required values, choices, scalar types, and bounds."""

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        path_types = {
            "BAM",
            "DIRECTORY",
            "FASTA",
            "FASTQ",
            "FILE",
            "GFA",
            "GFF",
            "JSON",
            "NEWICK",
            "STOCKHOLM",
            "TSV",
            "TXT",
            "VCF",
            "ZIP",
        }
        for section in ("required", "optional"):
            for name, spec in cls.INPUT_TYPES().get(section, {}).items():
                config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                if name not in inputs or inputs[name] is None:
                    if section == "required" and "default" not in config:
                        return f"Required input '{name}' is missing"
                    continue

                value = inputs[name]
                type_spec = spec[0]
                choices = config.get("options")
                is_multi = bool(config.get("multiple") or config.get("list") or config.get("is_list"))
                if (is_multi or str(type_spec).endswith("_LIST")) and isinstance(value, (list, tuple, set)):
                    if choices:
                        allowed = {str(choice) for choice in choices}
                        invalid = [str(item) for item in value if str(item) not in allowed]
                        if invalid:
                            return f"Input '{name}' contains unsupported values: {', '.join(invalid)}"
                    if type_spec not in path_types:
                        continue

                if isinstance(type_spec, list):
                    if str(value) not in {str(choice) for choice in type_spec}:
                        return f"Input '{name}' must be one of: {', '.join(str(choice) for choice in type_spec)}"
                elif type_spec == "BOOLEAN" and not isinstance(value, bool):
                    return f"Input '{name}' must be a boolean"
                elif type_spec == "INT":
                    if isinstance(value, bool):
                        return f"Input '{name}' must be an integer"
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        return f"Input '{name}' must be an integer"
                    if isinstance(inputs[name], float) and not inputs[name].is_integer():
                        return f"Input '{name}' must be an integer"
                elif type_spec == "FLOAT":
                    if isinstance(value, bool):
                        return f"Input '{name}' must be a number"
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        return f"Input '{name}' must be a number"
                    if not math.isfinite(value):
                        return f"Input '{name}' must be finite"
                elif type_spec == "STRING" and not isinstance(value, str):
                    return f"Input '{name}' must be a string"
                elif type_spec in path_types:
                    if isinstance(value, (list, tuple)):
                        if not value and config.get("default") in ([], ""):
                            continue
                        if not value or any(not str(item).strip() for item in value):
                            return f"Input '{name}' must contain non-empty paths"
                    elif not str(value).strip() and config.get("default") == "":
                        continue
                    elif not str(value).strip():
                        return f"Input '{name}' must be a non-empty path"

                if choices and str(value) not in {str(choice) for choice in choices}:
                    return f"Input '{name}' must be one of: {', '.join(str(choice) for choice in choices)}"
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if "min" in config and value < config["min"]:
                        return f"Input '{name}' must be at least {config['min']}"
                    if "max" in config and value > config["max"]:
                        return f"Input '{name}' must be at most {config['max']}"
        return True


class ToolsIUCCommandContract(ValidatedCommandContract):
    """Base identity for contracts reconstructed from a pinned Tools-IUC wrapper."""

    GIT_URL = TOOLS_IUC_GIT_URL
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    GALAXY_WRAPPER_GIT_URL = TOOLS_IUC_GIT_URL
    GALAXY_WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    EXIT_SEMANTICS = "Wrapper validation or external command failure must produce a non-zero result."
