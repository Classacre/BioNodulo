"""Paired statistical tests for design-loop A/B comparisons, scipy-free."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import numpy as np

from bionodulo.nodes.base import path_probe_is_file

from .adapter import (
    MLDesignNode,
    average_ranks,
    node_output_dir,
    path_value,
    read_table,
    spearman,
    validate_choice_input,
    write_json_file,
)

TESTS = ("wilcoxon_signed_rank", "paired_t", "spearman")
ALTERNATIVES = ("two_sided", "greater", "less")
EXACT_WILCOXON_MAX_N = 20
BOOTSTRAP_DRAWS = 10000
_BETACF_MAX_ITERATIONS = 200
_BETACF_EPSILON = 3e-14
_BETACF_FPMIN = 1e-300


def _betacf(a: float, b: float, x: float) -> float:
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _BETACF_FPMIN:
        d = _BETACF_FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, _BETACF_MAX_ITERATIONS + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _BETACF_FPMIN:
            d = _BETACF_FPMIN
        c = 1.0 + aa / c
        if abs(c) < _BETACF_FPMIN:
            c = _BETACF_FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _BETACF_FPMIN:
            d = _BETACF_FPMIN
        c = 1.0 + aa / c
        if abs(c) < _BETACF_FPMIN:
            c = _BETACF_FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _BETACF_EPSILON:
            break
    else:
        raise ValueError("Incomplete-beta continued fraction failed to converge")
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a, b); Numerical Recipes 3rd ed. 6.4."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _t_two_sided_p(t: float, df: int) -> float:
    return _betai(0.5 * df, 0.5, df / (df + t * t))


def _normal_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _wilcoxon(diffs: list[float], alternative: str) -> tuple[float, float, int]:
    nonzero = [value for value in diffs if value != 0.0]
    n = len(nonzero)
    if n == 0:
        return 0.0, 1.0, 0
    ranks = average_ranks(np.abs(np.asarray(nonzero, dtype=float)))
    ranks = [float(rank) for rank in ranks]
    statistic = sum(rank for rank, value in zip(ranks, nonzero, strict=True) if value > 0)
    if n <= EXACT_WILCOXON_MAX_N:
        sums: dict[float, int] = {0.0: 1}
        for rank in ranks:
            updated: dict[float, int] = {}
            for total, count in sums.items():
                for candidate in (total + rank, total - rank):
                    updated[candidate] = updated.get(candidate, 0) + count
            sums = updated
        observed = 2.0 * statistic - sum(ranks)
        total_assignments = 2**n
        if alternative == "two_sided":
            extreme = sum(count for total, count in sums.items() if abs(total) >= abs(observed) - 1e-9)
        elif alternative == "greater":
            extreme = sum(count for total, count in sums.items() if total >= observed - 1e-9)
        else:
            extreme = sum(count for total, count in sums.items() if total <= observed + 1e-9)
        return statistic, min(extreme / total_assignments, 1.0), n
    mean = n * (n + 1) / 4.0
    variance = n * (n + 1) * (2 * n + 1) / 24.0
    tied: dict[float, int] = {}
    for value in ranks:
        tied[value] = tied.get(value, 0) + 1
    variance -= sum(count**3 - count for count in tied.values()) / 48.0
    if variance <= 0:
        return statistic, 1.0, n
    standard_deviation = math.sqrt(variance)
    if alternative == "two_sided":
        z = (abs(statistic - mean) - 0.5) / standard_deviation
        return statistic, min(2.0 * _normal_sf(z), 1.0), n
    if alternative == "greater":
        z = (statistic - mean - 0.5) / standard_deviation
        return statistic, _normal_sf(z), n
    z = (statistic - mean + 0.5) / standard_deviation
    return statistic, 1.0 - _normal_sf(z), n


def _paired_t(diffs: list[float], alternative: str) -> tuple[float, float]:
    n = len(diffs)
    mean = sum(diffs) / n
    variance = sum((value - mean) ** 2 for value in diffs) / (n - 1) if n > 1 else 0.0
    if variance <= 0.0:
        t_statistic = math.inf if mean > 0 else -math.inf if mean < 0 else 0.0
        if t_statistic == 0.0:
            return 0.0, 1.0
        p_two = 0.0
    else:
        t_statistic = mean / math.sqrt(variance / n)
        p_two = _t_two_sided_p(abs(t_statistic), n - 1)
    if alternative == "two_sided":
        return t_statistic, p_two
    if alternative == "greater":
        return t_statistic, p_two / 2.0 if t_statistic > 0 else 1.0 - p_two / 2.0
    return t_statistic, p_two / 2.0 if t_statistic < 0 else 1.0 - p_two / 2.0


def _spearman_test(a: list[float], b: list[float], alternative: str) -> tuple[float, float]:
    rho = spearman(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    if rho is None:
        raise ValueError("Spearman correlation is undefined for constant input")
    n = len(a)
    if abs(rho) >= 1.0:
        return rho, 0.0
    t_statistic = rho * math.sqrt((n - 2) / (1.0 - rho * rho))
    p_two = _t_two_sided_p(abs(t_statistic), n - 2)
    if alternative == "two_sided":
        return rho, p_two
    if alternative == "greater":
        return rho, p_two / 2.0 if rho > 0 else 1.0 - p_two / 2.0
    return rho, p_two / 2.0 if rho < 0 else 1.0 - p_two / 2.0


def _bootstrap_mean_ci(diffs: list[float], draws: int, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    means: list[float] = []
    for _ in range(draws):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        means.append(total / n)
    means.sort()
    low = means[int(0.025 * draws)]
    high = means[min(int(0.975 * draws), draws - 1)]
    return low, high


class PairedStatsNode(MLDesignNode):
    """Wilcoxon signed-rank, paired t, and Spearman tests without scipy."""

    NODE_ID = "paired_stats"
    DISPLAY_NAME = "Paired Stats"
    DESCRIPTION = (
        "Paired-statistics node for comparing two aligned score vectors from the "
        "design loop (JSON list, TSV path optionally suffixed ':column', or comma "
        "list; equal lengths required). Tests: exact Wilcoxon signed-rank via full "
        "sign-combination enumeration for n<=20 nonzero differences (2^n <= 1M "
        "assignments) with a tie-corrected normal approximation beyond that; "
        "paired t and Spearman p-values via the regularized incomplete beta "
        "function using the Numerical Recipes 3rd ed. section 6.4 betacf/betai "
        "continued fraction. The 95% confidence interval for the mean difference "
        "is a deterministic seeded bootstrap (10000 draws)."
    )
    SEARCH_ALIASES = [
        "wilcoxon",
        "signed rank",
        "paired t test",
        "spearman",
        "statistics",
        "significance",
        "a b test",
    ]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("stats",)
    CITATION_URLS = ["http://numerical.recipes/"]
    REQUIRED_CONDA_PACKAGES = ["numpy"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "values_a": ("STRING", {"description": "First sample: JSON list, 'path.tsv:column', or comma list"}),
                "values_b": ("STRING", {"description": "Second sample, same length as values_a"}),
            },
            "optional": {
                "test": ("STRING", {"default": "wilcoxon_signed_rank", "options": list(TESTS)}),
                "alternative": ("STRING", {"default": "two_sided", "options": list(ALTERNATIVES)}),
                "alpha": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "description": "Significance threshold"}),
                "seed": ("INT", {"default": 1301, "min": 0, "description": "Bootstrap RNG seed"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name, default, choices in (
            ("test", "wilcoxon_signed_rank", TESTS),
            ("alternative", "two_sided", ALTERNATIVES),
        ):
            check = validate_choice_input(inputs.get(name, default), name, choices)
            if check is not True:
                return check
        alpha = inputs.get("alpha")
        if alpha is not None:
            if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
                return "Input 'alpha' must be a number between 0 and 1"
            if not 0.0 < float(alpha) < 1.0:
                return "Input 'alpha' must be between 0 and 1 (exclusive)"
        return True

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        test = str(kwargs.get("test", "wilcoxon_signed_rank"))
        alternative = str(kwargs.get("alternative", "two_sided"))
        alpha = float(kwargs.get("alpha", 0.05))
        seed = int(kwargs.get("seed", 1301))
        values_a = self._values(kwargs["values_a"], "values_a")
        values_b = self._values(kwargs["values_b"], "values_b")
        if not values_a or not values_b:
            # Empty-tolerance: an upstream filter that matched nothing is a valid
            # "no data" outcome, not a hard failure — emit a null-stats payload so
            # downstream consumers can render NaN and the run continues.
            payload = {
                "test": test,
                "alternative": alternative,
                "n": 0,
                "statistic": None,
                "p_value": None,
                "effect_mean_a": None,
                "effect_mean_b": None,
                "mean_diff": None,
                "ci95_low": None,
                "ci95_high": None,
                "alpha": alpha,
                "significant": False,
                "empty": True,
                "note": f"no paired rows (values_a={len(values_a)}, values_b={len(values_b)})",
            }
            output_dir = node_output_dir(self, context)
            stats_path = output_dir / "stats.json"
            write_json_file(stats_path, payload)
            return (str(stats_path),)
        if len(values_a) != len(values_b):
            raise ValueError(
                f"Inputs 'values_a' and 'values_b' must have equal length (got {len(values_a)} vs {len(values_b)})"
            )
        if len(values_a) < 2:
            raise ValueError("Inputs 'values_a'/'values_b' must contain at least two values each")

        diffs = [a - b for a, b in zip(values_a, values_b, strict=True)]
        mean_diff = sum(diffs) / len(diffs)
        if test == "wilcoxon_signed_rank":
            statistic, p_value, n_nonzero = _wilcoxon(diffs, alternative)
        elif test == "paired_t":
            statistic, p_value = _paired_t(diffs, alternative)
            n_nonzero = sum(value != 0.0 for value in diffs)
        else:
            statistic, p_value = _spearman_test(values_a, values_b, alternative)
            n_nonzero = len(diffs)
        ci_low, ci_high = _bootstrap_mean_ci(diffs, BOOTSTRAP_DRAWS, seed)
        payload = {
            "test": test,
            "alternative": alternative,
            "n": len(values_a),
            "statistic": statistic,
            "p_value": p_value,
            "effect_mean_a": sum(values_a) / len(values_a),
            "effect_mean_b": sum(values_b) / len(values_b),
            "mean_diff": mean_diff,
            "ci95_low": ci_low,
            "ci95_high": ci_high,
            "alpha": alpha,
            "significant": p_value < alpha,
        }
        if test == "wilcoxon_signed_rank":
            payload["n_nonzero_diffs"] = n_nonzero
            payload["exact"] = n_nonzero <= EXACT_WILCOXON_MAX_N

        output_dir = node_output_dir(self, context)
        stats_path = output_dir / "stats.json"
        write_json_file(stats_path, payload)
        return (str(stats_path),)

    @staticmethod
    def _values(value: Any, key: str) -> list[float]:
        text = path_value(value)
        if not text:
            raise ValueError(f"Input '{key}' must be a JSON list, TSV path, or comma list")
        if path_probe_is_file(text):
            content = Path(text).expanduser().read_text(encoding="utf-8").lstrip()
            if content.startswith(("{", "[")):
                return PairedStatsNode._json_list(content, key, text)
            try:
                fieldnames, rows = read_table(Path(text).expanduser())
            except ValueError:
                return []  # zero-byte / headerless table = no data
            if not fieldnames or not rows:
                return []
            column = PairedStatsNode._column(text, fieldnames, key)
            return [PairedStatsNode._number(row.get(column, ""), f"Input '{key}' row {index}") for index, row in enumerate(rows)]
        separator = text.rfind(":")
        if separator > 0:
            table_path = text[:separator].strip()
            if path_probe_is_file(table_path):
                try:
                    fieldnames, rows = read_table(Path(table_path).expanduser())
                except ValueError:
                    return []
                if not fieldnames or not rows:
                    return []
                column = PairedStatsNode._column(text, fieldnames, key)
                return [PairedStatsNode._number(row.get(column, ""), f"Input '{key}' row {index}") for index, row in enumerate(rows)]
        if text.lstrip().startswith(("{", "[")):
            return PairedStatsNode._json_list(text, key, None)
        return [PairedStatsNode._number(item, f"Input '{key}' item {index}") for index, item in enumerate(text.split(","))]

    @staticmethod
    def _json_list(text: str, key: str, source: str | None) -> list[float]:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            where = f" ({source})" if source else ""
            raise ValueError(f"Input '{key}' is not valid JSON{where}: {exc}") from exc
        if not isinstance(payload, list):
            raise ValueError(f"Input '{key}' JSON payload must be a list of numbers")
        return [PairedStatsNode._number(item, f"Input '{key}' entry {index}") for index, item in enumerate(payload)]

    @staticmethod
    def _column(text: str, fieldnames: list[str], key: str) -> str:
        if len(fieldnames) == 1:
            return fieldnames[0]
        separator = text.rfind(":")
        if separator > 0:
            candidate = text[separator + 1 :].strip()
            path_probe = text[:separator].strip()
            if candidate in fieldnames and path_probe_is_file(path_probe):
                return candidate
        raise ValueError(
            f"Input '{key}' table has multiple columns {fieldnames}; request one as 'path:column'"
        )

    @staticmethod
    def _number(item: Any, context: str) -> float:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            try:
                item = float(str(item).strip())
            except ValueError as exc:
                raise ValueError(f"{context} is not numeric: {item!r}") from exc
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"{context} must be finite")
        return number
