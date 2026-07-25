"""MetaboAnalystR 4.2.0 normalization, PCA, and two-class tests."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import (
    MetabolomicsCommandNode,
    path_value,
    r_string,
    safe_output_stem,
    validate_choice,
    validate_number,
)


def _r_bool(value: Any) -> str:
    return "TRUE" if bool(value) else "FALSE"


class MetaboAnalystStatsNode(MetabolomicsCommandNode):
    """Run source-pinned MetaboAnalystR statistical functions."""

    NODE_ID = "metaboanalyst_stats"
    DISPLAY_NAME = "MetaboAnalyst Stats"
    DESCRIPTION = "Normalize a concentration table and optionally run PCA and a two-class test."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "MetaboAnalystR",
        "normalization",
        "PCA",
        "t-test",
        "Wilcoxon",
        "metabolomics",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "FILE", "JSON")
    RETURN_NAMES = (
        "normalized_table",
        "pca_scores",
        "pca_loadings",
        "test_results",
        "metaboanalyst_object",
        "summary",
    )
    OUTPUT_SUFFIXES = (
        ".normalized.tsv",
        ".pca_scores.tsv",
        ".pca_loadings.tsv",
        ".test_results.tsv",
        ".metaboanalyst.rds",
        ".summary.json",
    )
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "r-jsonlite", "r-readr"]
    REQUIRED_R_PACKAGES = ["MetaboAnalystR", "jsonlite", "readr"]
    CONDA_PACKAGE_CONSTRAINTS = {"r-base": "4.5.*", "r-jsonlite": "2.0.0", "r-readr": "2.2.0"}
    VERSION = "4.2.0"
    GIT_URL = "https://github.com/xia-lab/MetaboAnalystR.git"
    GIT_COMMIT = "89dd939c7a5c6bb1b87a241c332e89a378048cd3"
    DOCUMENTATION_URL = "https://github.com/xia-lab/MetaboAnalystR/tree/v4.2.0"
    SOURCE_URL = GIT_URL
    UPSTREAM_SOURCE = (
        "R/general_data_utils.R; R/general_norm_utils.R; R/stats_chemometrics.R; "
        "R/stats_univariates.R"
    )
    R_INSTALL_SOURCE = "remotes::install_github('xia-lab/MetaboAnalystR@89dd939c7a5c6bb1b87a241c332e89a378048cd3')"
    EXIT_SEMANTICS = (
        "Any R error is fatal; BioNodulo requires all six deterministic tabular/object artifacts."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data_table": ("FILE", {"description": "MetaboAnalyst concentration table with class labels"}),
            },
            "optional": {
                "format": ("STRING", {"default": "rowu", "options": ["rowu", "colu", "rowp", "colp"]}),
                "label_type": ("STRING", {"default": "disc", "options": ["disc", "cont"]}),
                "row_norm": (
                    "STRING",
                    {"default": "MedianNorm", "options": ["MedianNorm", "SumNorm", "QuantileNorm", "CompNorm", "SpecNorm"]},
                ),
                "trans_norm": ("STRING", {"default": "LogNorm", "options": ["LogNorm", "CrNorm", "NULL"]}),
                "scale_norm": (
                    "STRING",
                    {"default": "AutoNorm", "options": ["AutoNorm", "ParetoNorm", "MeanCenter", "RangeNorm", "NULL"]},
                ),
                "run_pca": ("BOOLEAN", {"default": True}),
                "run_ttest": ("BOOLEAN", {"default": True}),
                "test_method": ("STRING", {"default": "welch", "options": ["welch", "student", "wilcox"]}),
                "p_threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "pval_type": ("STRING", {"default": "fdr", "options": ["fdr", "raw"]}),
                "paired": ("BOOLEAN", {"default": False}),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("data_table")):
            return "Input 'data_table' must be a non-empty path-like value"
        choices = {
            "format": ("rowu", "colu", "rowp", "colp"),
            "label_type": ("disc", "cont"),
            "row_norm": ("MedianNorm", "SumNorm", "QuantileNorm", "CompNorm", "SpecNorm"),
            "trans_norm": ("LogNorm", "CrNorm", "NULL"),
            "scale_norm": ("AutoNorm", "ParetoNorm", "MeanCenter", "RangeNorm", "NULL"),
            "test_method": ("welch", "student", "wilcox"),
            "pval_type": ("fdr", "raw"),
        }
        defaults = {
            "format": "rowu",
            "label_type": "disc",
            "row_norm": "MedianNorm",
            "trans_norm": "LogNorm",
            "scale_norm": "AutoNorm",
            "test_method": "welch",
            "pval_type": "fdr",
        }
        for key, allowed in choices.items():
            validation = validate_choice(inputs.get(key, defaults[key]), key, allowed)
            if validation is not True:
                return validation
        return validate_number(inputs.get("p_threshold", 0.05), "p_threshold", minimum=0, maximum=1)

    @classmethod
    def output_stem(cls, inputs: dict[str, Any], fallback: str) -> str:
        source = safe_output_stem(inputs.get("data_table"), "metaboanalyst")
        return safe_output_stem(inputs.get("output_name"), source)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        output.mkdir(parents=True, exist_ok=True)
        stem = cls.output_stem(inputs, "metaboanalyst")
        script_file = output / "metaboanalyst_stats.R"
        normalized, scores, loadings, tests, rds_file, summary = [
            output / f"{stem}{suffix}" for suffix in cls.OUTPUT_SUFFIXES
        ]
        method = str(inputs.get("test_method", "welch"))
        nonpar = method == "wilcox"
        equal_var = method == "student"
        pca_block = (
            """
            mSet <- PCA.Anal(mSet)
            pca_scores <- data.frame(sample = rownames(mSet$analSet$pca$x), mSet$analSet$pca$x, check.names = FALSE)
            pca_loadings <- data.frame(feature = rownames(mSet$analSet$pca$rotation), mSet$analSet$pca$rotation, check.names = FALSE)
            """
            if inputs.get("run_pca", True)
            else "pca_scores <- data.frame()\npca_loadings <- data.frame()"
        )
        test_block = (
            f"""
            mSet <- Ttests.Anal(
                mSet,
                nonpar = {_r_bool(nonpar)},
                threshp = {inputs.get('p_threshold', 0.05)},
                paired = {_r_bool(inputs.get('paired', False))},
                equal.var = {_r_bool(equal_var)},
                pvalType = {r_string(inputs.get('pval_type', 'fdr'))},
                all_results = TRUE
            )
            tt <- mSet$analSet$tt
            test_results <- data.frame(
                feature = names(tt$p.value),
                statistic = unname(tt$t.score),
                p_value = unname(tt$p.value),
                neg_log10_p = unname(tt$p.log),
                fdr = unname(tt$fdr.p),
                check.names = FALSE
            )
            """
            if inputs.get("run_ttest", True)
            else "test_results <- data.frame()"
        )
        script = textwrap.dedent(
            f"""\
            suppressPackageStartupMessages({{
                library("MetaboAnalystR")
                library("jsonlite")
                library("readr")
            }})

            data_table <- {r_string(path_value(inputs.get('data_table')))}
            if (!file.exists(data_table)) stop(paste("Input data table not found:", data_table))
            mSet <- InitDataObjects("conc", "stat", paired = {_r_bool(inputs.get('paired', False))})
            mSet <- Read.TextData(mSet, data_table, format = {r_string(inputs.get('format', 'rowu'))}, lbl.type = {r_string(inputs.get('label_type', 'disc'))})
            mSet <- SanityCheckData(mSet)
            mSet <- ReplaceMin(mSet)
            mSet <- PreparePrenormData(mSet)
            mSet <- Normalization(
                mSet,
                rowNorm = {r_string(inputs.get('row_norm', 'MedianNorm'))},
                transNorm = {r_string(inputs.get('trans_norm', 'LogNorm'))},
                scaleNorm = {r_string(inputs.get('scale_norm', 'AutoNorm'))}
            )
            normalized_table <- data.frame(sample = rownames(mSet$dataSet$norm), mSet$dataSet$norm, check.names = FALSE)
            {pca_block}
            {test_block}
            write_tsv(normalized_table, {r_string(normalized.as_posix())})
            write_tsv(pca_scores, {r_string(scores.as_posix())})
            write_tsv(pca_loadings, {r_string(loadings.as_posix())})
            write_tsv(test_results, {r_string(tests.as_posix())})
            saveRDS(mSet, {r_string(rds_file.as_posix())})
            write_json(
                list(
                    metaboanalystr_version = "4.2.0",
                    data_table = data_table,
                    run_pca = {_r_bool(inputs.get('run_pca', True))},
                    run_ttest = {_r_bool(inputs.get('run_ttest', True))},
                    test_method = {r_string(method)},
                    p_threshold = {inputs.get('p_threshold', 0.05)},
                    pval_type = {r_string(inputs.get('pval_type', 'fdr'))}
                ),
                {r_string(summary.as_posix())},
                pretty = TRUE,
                auto_unbox = TRUE
            )
            """
        )
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]
