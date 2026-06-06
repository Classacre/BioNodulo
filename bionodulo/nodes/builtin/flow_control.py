"""Flow-control routing nodes for BioNodulo workflows."""
from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"", "0", "false", "f", "no", "n", "off", "none", "null"}:
        return False
    return True


def _as_float(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    return float(str(value).strip())


def _split_cases(value: str) -> list[str]:
    normalised = str(value or "").replace("\n", ",")
    return [item.strip() for item in normalised.split(",") if item.strip()]


def _coerce_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
        path = Path(text)
        if path.exists() and path.is_file():
            return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if "\n" in text or "," in text:
            return [item.strip() for item in text.replace("\n", ",").split(",") if item.strip()]
        return [text]
    return [value]


def _split_error_types(value: Any) -> set[str]:
    return {
        item.strip().lower()
        for item in str(value or "").replace("\n", ",").split(",")
        if item.strip()
    }


def _error_type(error: Any) -> str:
    text = str(error or "").strip()
    if ":" in text:
        prefix = text.split(":", 1)[0].strip().lower()
        if prefix:
            return prefix
    lowered = text.lower()
    for candidate in ("validation", "tool_error", "timeout", "oom", "runtime"):
        if candidate in lowered:
            return candidate
    return "runtime"


def _is_catchable(error: Any, catch_errors: Any) -> bool:
    allowed = _split_error_types(catch_errors)
    return not allowed or _error_type(error) in allowed


class IfConditionNode(BaseNode):
    """Route a value to a true or false output based on a condition."""

    NODE_ID = "if_condition"
    DISPLAY_NAME = "If Condition"
    CATEGORY = "flow_control"
    DESCRIPTION = "Route data down true or false branches using boolean, numeric, string, regex, or file checks."
    SEARCH_ALIASES = ["if", "condition", "branch", "route", "gate", "boolean"]
    RETURN_TYPES = ("ANY", "ANY", "BOOLEAN")
    RETURN_NAMES = ("true", "false", "condition_result")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": ("ANY", {"description": "Value to evaluate and route"}),
                "condition_mode": ([
                    "boolean",
                    "numeric_equal",
                    "numeric_greater",
                    "numeric_less",
                    "numeric_greater_equal",
                    "numeric_less_equal",
                    "numeric_not_equal",
                    "string_equal",
                    "string_not_equal",
                    "string_contains",
                    "string_not_contains",
                    "string_startswith",
                    "string_endswith",
                    "regex_match",
                    "file_exists",
                    "is_empty",
                    "not_empty",
                ], {"default": "boolean", "description": "Condition evaluation mode"}),
                "compare_to": ("STRING", {"default": "", "description": "Comparison value"}),
            },
            "optional": {
                "invert": ("BOOLEAN", {"default": False}),
                "case_sensitive": ("BOOLEAN", {"default": True}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        value = kwargs.get("value")
        mode = str(kwargs.get("condition_mode", "boolean"))
        compare_to = kwargs.get("compare_to", "")
        case_sensitive = bool(kwargs.get("case_sensitive", True))
        invert = bool(kwargs.get("invert", False))

        condition_result = self._evaluate(value, mode, compare_to, case_sensitive)
        if invert:
            condition_result = not condition_result

        inactive = ["false"] if condition_result else ["true"]
        return {
            "outputs": {
                "true": value if condition_result else None,
                "false": value if not condition_result else None,
                "condition_result": condition_result,
            },
            "inactive_outputs": inactive,
        }

    @staticmethod
    def _evaluate(value: Any, mode: str, compare_to: Any, case_sensitive: bool) -> bool:
        if mode == "boolean":
            return _bool_value(value)
        if mode == "file_exists":
            return bool(value) and Path(str(value)).exists()
        if mode == "is_empty":
            if value is None:
                return True
            if isinstance(value, (list, tuple, dict, set)):
                return len(value) == 0
            return str(value).strip() == ""
        if mode == "not_empty":
            if value is None:
                return False
            if isinstance(value, (list, tuple, dict, set)):
                return len(value) > 0
            return str(value).strip() != ""

        if mode.startswith("numeric_"):
            try:
                left = _as_float(value)
                right = _as_float(compare_to)
            except ValueError:
                return False
            if mode == "numeric_equal":
                return left == right
            if mode == "numeric_greater":
                return left > right
            if mode == "numeric_less":
                return left < right
            if mode == "numeric_greater_equal":
                return left >= right
            if mode == "numeric_less_equal":
                return left <= right
            if mode == "numeric_not_equal":
                return left != right
            return False

        left_text = str(value)
        right_text = str(compare_to)
        flags = 0
        if not case_sensitive:
            left_text = left_text.lower()
            right_text = right_text.lower()
            flags = re.IGNORECASE
        if mode == "string_equal":
            return left_text == right_text
        if mode == "string_not_equal":
            return left_text != right_text
        if mode == "string_contains":
            return right_text in left_text
        if mode == "string_not_contains":
            return right_text not in left_text
        if mode == "string_startswith":
            return left_text.startswith(right_text)
        if mode == "string_endswith":
            return left_text.endswith(right_text)
        if mode == "regex_match":
            return re.search(str(compare_to), str(value), flags=flags) is not None
        return False


class SwitchNode(BaseNode):
    """Route a value to one of four case outputs or a default output."""

    NODE_ID = "switch"
    DISPLAY_NAME = "Switch"
    CATEGORY = "flow_control"
    DESCRIPTION = "Route data to one of several outputs by matching a value against comma-separated cases."
    SEARCH_ALIASES = ["switch", "case", "route", "branch", "match"]
    RETURN_TYPES = ("ANY", "ANY", "ANY", "ANY", "ANY")
    RETURN_NAMES = ("output_1", "output_2", "output_3", "output_4", "default")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": ("ANY", {"description": "Value to match against cases"}),
                "cases": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "description": "Comma- or newline-separated case values; first four map to output_1..output_4",
                }),
            },
            "optional": {
                "passthrough_data": ("ANY", {"description": "Data to emit on the matched output; defaults to value"}),
                "case_sensitive": ("BOOLEAN", {"default": True}),
                "rules": ("STRING", {
                    "default": "[]",
                    "multiline": True,
                    "description": "Optional JSON rules with branch_index, match_type, and pattern/min/max fields",
                }),
                "fallback": ("STRING", {"default": "last", "options": ["drop", "last", "error"]}),
                "match_mode": ("STRING", {"default": "first", "options": ["first", "all"]}),
                "auto_numeric": ("BOOLEAN", {"default": True}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        value = kwargs.get("value")
        passthrough = kwargs.get("passthrough_data", value)
        case_sensitive = bool(kwargs.get("case_sensitive", True))
        rules = self._parse_rules(kwargs.get("rules", "[]"))

        if rules:
            selected_names = self._selected_rule_outputs(
                value=value,
                rules=rules,
                case_sensitive=case_sensitive,
                match_mode=str(kwargs.get("match_mode", "first") or "first"),
                fallback=str(kwargs.get("fallback", "last") or "last"),
            )
            outputs = {name: None for name in self.RETURN_NAMES}
            for name in selected_names:
                outputs[name] = passthrough
            return {
                "outputs": outputs,
                "inactive_outputs": [name for name in self.RETURN_NAMES if name not in selected_names],
            }

        cases = _split_cases(str(kwargs.get("cases", "")))[:4]

        matched_index: int | None = None
        value_text = str(value)
        value_cmp = value_text if case_sensitive else value_text.lower()
        for idx, case in enumerate(cases):
            case_cmp = case if case_sensitive else case.lower()
            if value_cmp == case_cmp:
                matched_index = idx
                break

        selected_name = "default" if matched_index is None else self.RETURN_NAMES[matched_index]
        outputs = {name: None for name in self.RETURN_NAMES}
        outputs[selected_name] = passthrough
        return {
            "outputs": outputs,
            "inactive_outputs": [name for name in self.RETURN_NAMES if name != selected_name],
        }

    @staticmethod
    def _parse_rules(raw_rules: Any) -> list[dict[str, Any]]:
        if raw_rules in (None, ""):
            return []
        if isinstance(raw_rules, str):
            try:
                parsed = json.loads(raw_rules)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Switch rules must be valid JSON: {exc}") from exc
        else:
            parsed = raw_rules
        if not isinstance(parsed, list):
            raise ValueError("Switch rules must be a JSON array")
        if not all(isinstance(rule, dict) for rule in parsed):
            raise ValueError("Switch rules must contain JSON objects")
        return [dict(rule) for rule in parsed]

    @classmethod
    def _selected_rule_outputs(
        cls,
        *,
        value: Any,
        rules: list[dict[str, Any]],
        case_sensitive: bool,
        match_mode: str,
        fallback: str,
    ) -> list[str]:
        match_mode = match_mode.lower()
        fallback = fallback.lower()
        if match_mode not in {"first", "all"}:
            raise ValueError(f"Unsupported switch match_mode: {match_mode}")
        if fallback not in {"drop", "last", "error"}:
            raise ValueError(f"Unsupported switch fallback: {fallback}")

        selected: list[str] = []
        for index, rule in enumerate(rules):
            branch_index = int(rule.get("branch_index", -1))
            if not 0 <= branch_index < 4:
                raise ValueError(f"Switch rule {index} branch_index must be between 0 and 3")
            if cls._rule_matches(value, rule, case_sensitive):
                output_name = cls.RETURN_NAMES[branch_index]
                if output_name not in selected:
                    selected.append(output_name)
                if match_mode == "first":
                    break

        if selected:
            return selected
        if fallback == "drop":
            return []
        if fallback == "error":
            raise ValueError(f"Switch value did not match any rule: {value}")
        return [cls.RETURN_NAMES[3]]

    @staticmethod
    def _rule_matches(value: Any, rule: dict[str, Any], case_sensitive: bool) -> bool:
        match_type = str(rule.get("match_type", "exact") or "exact").lower()
        pattern = rule.get("pattern", "")
        value_text = str(value)
        pattern_text = str(pattern)
        compare_value = value_text if case_sensitive else value_text.lower()
        compare_pattern = pattern_text if case_sensitive else pattern_text.lower()

        if match_type in {"exact", "equals", "string_equal"}:
            return compare_value == compare_pattern
        if match_type == "contains":
            return compare_pattern in compare_value
        if match_type == "regex":
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.search(pattern_text, value_text, flags=flags) is not None
        if match_type in {"numeric_range", "range"}:
            try:
                numeric_value = _as_float(value)
                lower = rule.get("min", None)
                upper = rule.get("max", None)
                if lower not in (None, "") and numeric_value < _as_float(lower):
                    return False
                if upper not in (None, "") and numeric_value > _as_float(upper):
                    return False
                return True
            except ValueError:
                return False
        if match_type in {"file_extension", "extension"}:
            suffixes = "".join(Path(value_text).suffixes)
            return suffixes == pattern_text or value_text.endswith(pattern_text)
        raise ValueError(f"Unsupported switch match_type: {match_type}")


class ForEachNode(BaseNode):
    """Iterate over items by asking the executor to run a connected body subgraph."""

    NODE_ID = "foreach"
    DISPLAY_NAME = "For Each"
    CATEGORY = "flow_control"
    DESCRIPTION = "Run a connected loop body once for each item and collect the body results."
    SEARCH_ALIASES = ["foreach", "for each", "loop", "iterate", "batch", "map", "scatter"]
    RETURN_TYPES = ("ANY", "ANY", "INT", "BOOLEAN")
    RETURN_NAMES = ("iteration", "results", "count", "all_succeeded")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTES_LOOP_BODY = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "items": ("ANY", {"description": "Items to iterate over"}),
            },
            "optional": {
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 1000}),
                "iteration_mode": ("STRING", {"default": "single", "options": ["single", "batch"]}),
                "max_iterations": ("INT", {"default": 1000, "min": 1, "max": 100000}),
                "collect_mode": ("STRING", {"default": "list", "options": ["list", "concat", "merge"]}),
                "stop_on_error": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "body_result": ("ANY", {"description": "Loop body result returned to the collector"}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        items = _coerce_items(kwargs.get("items", []))
        return {
            "outputs": {
                "iteration": None,
                "results": items,
                "count": len(items),
                "all_succeeded": True,
            },
            "inactive_outputs": ["iteration"],
        }


class TryCatchNode(BaseNode):
    """Route work through try, retry, and catch phases for error recovery."""

    NODE_ID = "try_catch"
    DISPLAY_NAME = "Try / Catch"
    CATEGORY = "flow_control"
    DESCRIPTION = "Route execution through try and catch branches with retry metadata for recoverable failures."
    SEARCH_ALIASES = ["try", "catch", "error", "fallback", "retry", "recover", "rescue"]
    RETURN_TYPES = ("ANY", "ANY", "ANY", "BOOLEAN", "STRING", "INT")
    RETURN_NAMES = ("try", "catch", "output", "succeeded", "error_info", "retry_count")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTES_TRY_CATCH_BRANCHES = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "try_input": ("ANY", {"description": "Data to pass to the try branch"}),
            },
            "optional": {
                "max_retries": ("INT", {"default": 0, "min": 0, "max": 10}),
                "catch_errors": ("STRING", {
                    "default": "",
                    "description": "Comma-separated error types to catch; empty catches all",
                }),
                "retry_delay": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 300.0}),
                "pass_input_to_catch": ("BOOLEAN", {"default": True}),
                "pass_error_to_catch": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "_phase": ("STRING", {"default": "init"}),
                "_try_result": ("ANY", {}),
                "_try_error": ("STRING", {}),
                "_catch_result": ("ANY", {}),
                "_retry_count": ("INT", {"default": 0}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        try_input = kwargs.get("try_input")
        max_retries = int(kwargs.get("max_retries", 0) or 0)
        retry_delay = float(kwargs.get("retry_delay", 1.0) or 0.0)
        catch_errors = kwargs.get("catch_errors", "")
        pass_input_to_catch = bool(kwargs.get("pass_input_to_catch", True))
        pass_error_to_catch = bool(kwargs.get("pass_error_to_catch", True))
        phase = str(kwargs.get("_phase", "init") or "init")
        try_result = kwargs.get("_try_result")
        try_error = str(kwargs.get("_try_error", "") or "")
        retry_count = int(kwargs.get("_retry_count", 0) or 0)

        if phase == "init":
            return self._result(
                try_value=try_input,
                catch_value=None,
                output=None,
                succeeded=False,
                error_info="",
                retry_count=0,
                inactive=["catch", "output", "succeeded", "error_info", "retry_count"],
                flow_phase="trying",
            )

        if phase == "try_result":
            if try_result is not None and not try_error:
                return self._result(
                    try_value=None,
                    catch_value=None,
                    output=try_result,
                    succeeded=True,
                    error_info="",
                    retry_count=retry_count,
                    inactive=["try", "catch", "error_info"],
                    flow_phase="completed",
                )

            if try_error and not _is_catchable(try_error, catch_errors):
                return self._result(
                    try_value=None,
                    catch_value=None,
                    output=None,
                    succeeded=False,
                    error_info=try_error,
                    retry_count=retry_count,
                    inactive=["try", "catch", "output", "succeeded", "retry_count"],
                    flow_phase="uncaught_error",
                    error_type=_error_type(try_error),
                )

            if retry_count < max_retries:
                if retry_delay > 0:
                    await asyncio.sleep(retry_delay)
                next_retry = retry_count + 1
                return self._result(
                    try_value=try_input,
                    catch_value=None,
                    output=None,
                    succeeded=False,
                    error_info=try_error,
                    retry_count=next_retry,
                    inactive=["catch", "output", "succeeded"],
                    flow_phase="retrying",
                )

            catch_inputs: dict[str, Any] = {}
            if pass_input_to_catch:
                catch_inputs["input"] = try_input
            if pass_error_to_catch:
                catch_inputs["error"] = try_error
            catch_value: Any = catch_inputs if catch_inputs else None
            return self._result(
                try_value=None,
                catch_value=catch_value,
                output=None,
                succeeded=False,
                error_info=try_error,
                retry_count=retry_count,
                inactive=["try", "output", "succeeded", "retry_count"],
                flow_phase="catching",
                error_type=_error_type(try_error),
            )

        if phase == "catch_result":
            return self._result(
                try_value=None,
                catch_value=None,
                output=kwargs.get("_catch_result"),
                succeeded=False,
                error_info=try_error,
                retry_count=retry_count,
                inactive=["try", "catch", "succeeded"],
                flow_phase="completed_with_catch",
            )

        return self._result(
            try_value=None,
            catch_value=None,
            output=None,
            succeeded=False,
            error_info=f"Unknown try/catch phase: {phase}",
            retry_count=retry_count,
            inactive=["try", "catch", "output", "succeeded", "retry_count"],
            flow_phase="error",
        )

    @staticmethod
    def _result(
        *,
        try_value: Any,
        catch_value: Any,
        output: Any,
        succeeded: bool,
        error_info: str,
        retry_count: int,
        inactive: list[str],
        flow_phase: str,
        error_type: str | None = None,
    ) -> dict[str, Any]:
        flow_control: dict[str, Any] = {
            "type": "try_catch",
            "phase": flow_phase,
            "retry_count": retry_count,
        }
        if error_type:
            flow_control["error_type"] = error_type
        return {
            "outputs": {
                "try": try_value,
                "catch": catch_value,
                "output": output,
                "succeeded": succeeded,
                "error_info": error_info,
                "retry_count": retry_count,
            },
            "inactive_outputs": inactive,
            "flow_control": flow_control,
        }


class GateNode(BaseNode):
    """Conditionally pass data through, default it, or halt execution."""

    NODE_ID = "gate"
    DISPLAY_NAME = "Gate"
    CATEGORY = "flow_control"
    DESCRIPTION = "Conditionally pass data through; on failure skip, halt, or emit a default value."
    SEARCH_ALIASES = ["gate", "filter", "guard", "validate", "assert", "require", "checkpoint"]
    RETURN_TYPES = ("ANY", "BOOLEAN")
    RETURN_NAMES = ("output", "passed")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True

    _CONDITION_MODES = [
        "file_exists",
        "file_not_exists",
        "numeric_greater",
        "numeric_less",
        "numeric_equals",
        "numeric_not_equals",
        "string_equals",
        "string_contains",
        "regex_matches",
        "is_empty",
        "is_not_empty",
        "boolean_is_true",
        "boolean_is_false",
        "always_pass",
        "always_fail",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "value": ("ANY", {"description": "Value to validate and pass through"}),
                "condition_mode": ("STRING", {"default": "file_exists", "options": cls._CONDITION_MODES}),
            },
            "optional": {
                "compare_to": ("STRING", {"default": ""}),
                "on_fail": ("STRING", {"default": "skip", "options": ["skip", "halt", "default"]}),
                "default_value": ("ANY", {}),
                "error_message": ("STRING", {"default": "Gate condition failed"}),
            },
            "hidden": {
                "_loop_state": ("LOOP_STATE", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        value = kwargs.get("value")
        mode = str(kwargs.get("condition_mode", "file_exists") or "file_exists")
        compare_to = kwargs.get("compare_to", "")
        on_fail = str(kwargs.get("on_fail", "skip") or "skip")
        default_value = kwargs.get("default_value")
        error_message = str(kwargs.get("error_message", "Gate condition failed") or "Gate condition failed")

        passed = self._evaluate(value, mode, compare_to)
        if passed:
            return {
                "outputs": {"output": value, "passed": True},
                "inactive_outputs": [],
                "flow_control": {"type": "gate", "phase": "passed", "condition_mode": mode},
            }

        if on_fail == "halt":
            raise RuntimeError(f"Gate condition failed: {error_message} (mode={mode}, value={value})")
        if on_fail == "default":
            return {
                "outputs": {"output": default_value, "passed": False},
                "inactive_outputs": [],
                "flow_control": {"type": "gate", "phase": "defaulted", "condition_mode": mode},
            }
        if on_fail != "skip":
            raise ValueError(f"Unsupported gate failure mode: {on_fail}")
        return {
            "outputs": {"output": None, "passed": False},
            "inactive_outputs": ["output"],
            "flow_control": {"type": "gate", "phase": "skipped", "condition_mode": mode},
        }

    @staticmethod
    def _evaluate(value: Any, mode: str, compare_to: Any) -> bool:
        if mode == "always_pass":
            return True
        if mode == "always_fail":
            return False
        if mode == "file_exists":
            return bool(value) and Path(str(value)).exists()
        if mode == "file_not_exists":
            return not bool(value) or not Path(str(value)).exists()
        if mode == "is_empty":
            if value is None:
                return True
            if isinstance(value, (list, tuple, dict, set)):
                return len(value) == 0
            return str(value).strip() == ""
        if mode == "is_not_empty":
            return not GateNode._evaluate(value, "is_empty", compare_to)
        if mode == "boolean_is_true":
            return _bool_value(value) is True
        if mode == "boolean_is_false":
            return _bool_value(value) is False
        if mode.startswith("numeric_"):
            try:
                left = _as_float(value)
                right = _as_float(compare_to)
            except ValueError:
                return False
            if mode == "numeric_greater":
                return left > right
            if mode == "numeric_less":
                return left < right
            if mode == "numeric_equals":
                return left == right
            if mode == "numeric_not_equals":
                return left != right
            return False
        left_text = str(value)
        right_text = str(compare_to)
        if mode == "string_equals":
            return left_text == right_text
        if mode == "string_contains":
            return right_text in left_text
        if mode == "regex_matches":
            return re.search(right_text, left_text) is not None
        raise ValueError(f"Unknown gate condition mode: {mode}")


class MergeNode(BaseNode):
    """Fan in multiple inputs and combine them with a selected strategy."""

    NODE_ID = "merge"
    DISPLAY_NAME = "Merge"
    CATEGORY = "flow_control"
    DESCRIPTION = "Combine multiple input branches using append, zip, dict merge, first/last valid, or interleave strategies."
    SEARCH_ALIASES = ["merge", "join", "combine", "collect", "gather", "fanin", "wait_all"]
    RETURN_TYPES = ("ANY", "INT")
    RETURN_NAMES = ("merged", "received_count")
    REQUIRES_EXTERNAL_TOOLS = False
    ALLOW_INACTIVE_INPUTS = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        optional: dict[str, Any] = {
            "strategy": ("STRING", {
                "default": "append",
                "options": ["append", "zip", "dict_merge", "first_valid", "last_valid", "interleave"],
            }),
            "wait_mode": ("STRING", {"default": "all", "options": ["all", "any", "first_n"]}),
            "wait_n": ("INT", {"default": 1, "min": 1, "max": 10}),
            "timeout": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 86400.0}),
            "ignore_none": ("BOOLEAN", {"default": True}),
        }
        for index in range(10):
            optional[f"input_{index}"] = ("ANY", {"description": f"Input branch {index + 1}"})
        return {
            "required": {
                "num_inputs": ("INT", {"default": 2, "min": 1, "max": 10}),
            },
            "optional": optional,
            "hidden": {
                "_loop_state": ("LOOP_STATE", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        num_inputs = max(1, min(10, int(kwargs.get("num_inputs", 2) or 2)))
        strategy = str(kwargs.get("strategy", "append") or "append")
        wait_mode = str(kwargs.get("wait_mode", "all") or "all")
        wait_n = max(1, int(kwargs.get("wait_n", 1) or 1))
        ignore_none = bool(kwargs.get("ignore_none", True))

        values: list[Any] = []
        for index in range(num_inputs):
            value = kwargs.get(f"input_{index}")
            if value is not None or not ignore_none:
                values.append(value)

        values = self._apply_wait_mode(values, wait_mode, wait_n)
        non_none = [value for value in values if value is not None]
        merged = self._merge_values(non_none, strategy)
        return {
            "outputs": {
                "merged": merged,
                "received_count": len(values),
            },
            "flow_control": {
                "type": "merge",
                "strategy": strategy,
                "wait_mode": wait_mode,
                "received_count": len(values),
            },
        }

    @staticmethod
    def _apply_wait_mode(values: list[Any], wait_mode: str, wait_n: int) -> list[Any]:
        if wait_mode == "all":
            return values
        non_none = [value for value in values if value is not None]
        if wait_mode == "any":
            return non_none[:1]
        if wait_mode == "first_n":
            return non_none[:wait_n]
        raise ValueError(f"Unsupported merge wait mode: {wait_mode}")

    @staticmethod
    def _as_sequence(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    @classmethod
    def _merge_values(cls, values: list[Any], strategy: str) -> Any:
        if strategy == "append":
            merged: list[Any] = []
            for value in values:
                merged.extend(cls._as_sequence(value))
            return merged
        if strategy == "zip":
            sequences = [cls._as_sequence(value) for value in values]
            if not sequences:
                return []
            return [tuple(sequence[index] for sequence in sequences) for index in range(min(len(seq) for seq in sequences))]
        if strategy == "dict_merge":
            merged_dict: dict[Any, Any] = {}
            for value in values:
                if isinstance(value, dict):
                    merged_dict.update(value)
            return merged_dict
        if strategy == "first_valid":
            return values[0] if values else None
        if strategy == "last_valid":
            return values[-1] if values else None
        if strategy == "interleave":
            sequence_items = [
                (cls._as_sequence(value), not isinstance(value, (list, tuple)))
                for value in values
            ]
            sequences = [sequence for sequence, _repeat_scalar in sequence_items]
            if not sequences:
                return []
            merged = []
            for index in range(max(len(seq) for seq in sequences)):
                for sequence, repeat_scalar in sequence_items:
                    if index < len(sequence):
                        merged.append(sequence[index])
                    elif repeat_scalar and len(sequence) == 1:
                        merged.append(sequence[0])
            return merged
        raise ValueError(f"Unsupported merge strategy: {strategy}")


class DelayWaitNode(BaseNode):
    """Pause execution for a fixed delay or until a wait condition is met."""

    NODE_ID = "delay_wait"
    DISPLAY_NAME = "Delay / Wait"
    CATEGORY = "flow_control"
    DESCRIPTION = "Pause execution for a duration, until a timestamp, or while polling a file or URL."
    SEARCH_ALIASES = ["delay", "wait", "sleep", "pause", "poll", "watch", "timeout", "rate_limit"]
    RETURN_TYPES = ("ANY", "BOOLEAN", "FLOAT")
    RETURN_NAMES = ("value", "condition_met", "actual_wait_seconds")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mode": ("STRING", {
                    "default": "delay",
                    "options": [
                        "delay",
                        "until_time",
                        "file_exists",
                        "file_not_exists",
                        "process_complete",
                        "poll_url",
                    ],
                }),
            },
            "optional": {
                "delay_seconds": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 86400.0}),
                "target_time": ("STRING", {"default": ""}),
                "watch_path": ("STRING", {"default": ""}),
                "poll_url": ("STRING", {"default": ""}),
                "poll_interval": ("FLOAT", {"default": 5.0, "min": 0.0, "max": 3600.0}),
                "max_wait": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 86400.0}),
                "on_timeout": ("STRING", {"default": "error", "options": ["error", "pass_through"]}),
                "value": ("ANY", {}),
            },
            "hidden": {
                "_loop_state": ("LOOP_STATE", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        mode = str(kwargs.get("mode", "delay") or "delay")
        value = kwargs.get("value")
        max_wait = max(0.0, float(kwargs.get("max_wait", 0.0) or 0.0))
        on_timeout = str(kwargs.get("on_timeout", "error") or "error")
        started_at = time.monotonic()

        try:
            condition_met = await self._wait_for_mode(mode, kwargs, max_wait)
        except asyncio.TimeoutError as exc:
            if on_timeout != "pass_through":
                raise RuntimeError(f"Delay / Wait timed out after {max_wait:g}s in mode {mode}") from exc
            condition_met = False

        actual_wait = time.monotonic() - started_at
        return {
            "outputs": {
                "value": value,
                "condition_met": condition_met,
                "actual_wait_seconds": actual_wait,
            },
        }

    async def _wait_for_mode(self, mode: str, kwargs: dict[str, Any], max_wait: float) -> bool:
        if mode == "delay":
            delay_seconds = max(0.0, float(kwargs.get("delay_seconds", 5.0) or 0.0))
            if max_wait > 0 and delay_seconds > max_wait:
                await asyncio.sleep(max_wait)
                raise asyncio.TimeoutError()
            await asyncio.sleep(delay_seconds)
            return True

        if mode == "until_time":
            target_time = str(kwargs.get("target_time", "") or "")
            if not target_time:
                return True
            target = datetime.fromisoformat(target_time.replace("Z", "+00:00"))
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            wait_seconds = max(0.0, (target - datetime.now(timezone.utc)).total_seconds())
            if max_wait > 0 and wait_seconds > max_wait:
                await asyncio.sleep(max_wait)
                raise asyncio.TimeoutError()
            await asyncio.sleep(wait_seconds)
            return True

        poll_interval = max(0.0, float(kwargs.get("poll_interval", 5.0) or 0.0))
        if mode in {"file_exists", "file_not_exists", "process_complete"}:
            should_exist = mode == "file_exists"
            watch_path = str(kwargs.get("watch_path", "") or "")
            return await self._poll_until(lambda: Path(watch_path).exists() is should_exist, poll_interval, max_wait)

        if mode == "poll_url":
            poll_url = str(kwargs.get("poll_url", "") or "")
            return await self._poll_until(lambda: self._url_available(poll_url), poll_interval, max_wait)

        raise ValueError(f"Unsupported delay/wait mode: {mode}")

    async def _poll_until(self, predicate: Any, poll_interval: float, max_wait: float) -> bool:
        started_at = time.monotonic()
        while True:
            if predicate():
                return True
            elapsed = time.monotonic() - started_at
            if max_wait > 0 and elapsed >= max_wait:
                raise asyncio.TimeoutError()
            sleep_for = poll_interval
            if max_wait > 0:
                sleep_for = min(sleep_for, max(0.0, max_wait - elapsed))
            await asyncio.sleep(max(0.0, sleep_for))

    @staticmethod
    def _url_available(url: str) -> bool:
        if not url:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                return 200 <= int(response.status) < 400
        except (OSError, urllib.error.URLError, ValueError):
            return False


class SleepNode(BaseNode):
    """Pause execution for a fixed number of seconds."""

    NODE_ID = "sleep"
    DISPLAY_NAME = "Sleep"
    CATEGORY = "flow_control"
    DESCRIPTION = "Pause execution for a fixed number of seconds before passing through an optional value."
    SEARCH_ALIASES = ["sleep", "delay", "pause", "wait", "rate_limit"]
    RETURN_TYPES = ("BOOLEAN", "FLOAT", "ANY")
    RETURN_NAMES = ("done", "actual_wait_seconds", "value")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "seconds": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 86400.0}),
            },
            "optional": {
                "value": ("ANY", {}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        seconds = max(0.0, float(kwargs.get("seconds", 0.0) or 0.0))
        value = kwargs.get("value")
        started_at = time.monotonic()

        await asyncio.sleep(seconds)

        return {
            "outputs": {
                "done": True,
                "actual_wait_seconds": time.monotonic() - started_at,
                "value": value,
            },
        }


class WaitForNode(BaseNode):
    """Wait until a simple condition is met."""

    NODE_ID = "wait_for"
    DISPLAY_NAME = "Wait For"
    CATEGORY = "flow_control"
    DESCRIPTION = "Wait for a file condition or elapsed time before passing through an optional value."
    SEARCH_ALIASES = ["wait", "wait for", "file exists", "file not exists", "timer", "poll", "watch"]
    RETURN_TYPES = ("BOOLEAN", "FLOAT", "ANY")
    RETURN_NAMES = ("triggered", "actual_wait_seconds", "value")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "condition": ("STRING", {
                    "default": "file_exists",
                    "options": ["file_exists", "file_not_exists", "elapsed_time"],
                }),
            },
            "optional": {
                "path": ("STRING", {"default": "", "description": "Path for file_exists or file_not_exists"}),
                "seconds": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 86400.0}),
                "poll_interval": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3600.0}),
                "timeout": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 86400.0}),
                "on_timeout": ("STRING", {"default": "error", "options": ["error", "pass_through"]}),
                "value": ("ANY", {}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        condition = str(kwargs.get("condition", "file_exists") or "file_exists")
        timeout = max(0.0, float(kwargs.get("timeout", 0.0) or 0.0))
        on_timeout = str(kwargs.get("on_timeout", "error") or "error")
        value = kwargs.get("value")
        started_at = time.monotonic()

        try:
            triggered = await self._wait_for_condition(condition, kwargs, timeout)
        except asyncio.TimeoutError as exc:
            if on_timeout != "pass_through":
                raise RuntimeError(f"Wait For timed out after {timeout:g}s for condition {condition}") from exc
            triggered = False

        return {
            "outputs": {
                "triggered": triggered,
                "actual_wait_seconds": time.monotonic() - started_at,
                "value": value,
            },
        }

    async def _wait_for_condition(self, condition: str, kwargs: dict[str, Any], timeout: float) -> bool:
        if condition == "elapsed_time":
            seconds = max(0.0, float(kwargs.get("seconds", 0.0) or 0.0))
            if timeout > 0 and seconds > timeout:
                await asyncio.sleep(timeout)
                raise asyncio.TimeoutError()
            await asyncio.sleep(seconds)
            return True

        if condition in {"file_exists", "file_not_exists"}:
            path = Path(str(kwargs.get("path", "") or ""))
            should_exist = condition == "file_exists"
            poll_interval = max(0.0, float(kwargs.get("poll_interval", 1.0) or 0.0))
            return await self._poll_until(lambda: path.exists() is should_exist, poll_interval, timeout)

        raise ValueError(f"Unsupported wait condition: {condition}")

    async def _poll_until(self, predicate: Any, poll_interval: float, timeout: float) -> bool:
        waited = 0.0
        while True:
            if predicate():
                return True
            if timeout > 0 and waited >= timeout:
                raise asyncio.TimeoutError()
            sleep_for = poll_interval
            if timeout > 0:
                sleep_for = min(sleep_for, max(0.0, timeout - waited))
            await asyncio.sleep(max(0.0, sleep_for))
            waited += sleep_for


class BreakContinueNode(BaseNode):
    """Emit an explicit loop-control signal for ForEach body subgraphs."""

    NODE_ID = "break_continue"
    DISPLAY_NAME = "Break / Continue"
    CATEGORY = "flow_control"
    DESCRIPTION = "Conditionally request a For Each loop to break or continue."
    SEARCH_ALIASES = ["break", "continue", "loop", "stop", "skip iteration", "control flow"]
    RETURN_TYPES = ("STRING", "ANY", "BOOLEAN", "STRING")
    RETURN_NAMES = ("signal", "value", "triggered", "reason")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "action": ("STRING", {"default": "break", "options": ["break", "continue"]}),
            },
            "optional": {
                "condition": ("BOOLEAN", {"default": True}),
                "value": ("ANY", {}),
                "reason": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        requested = str(kwargs.get("action", "break") or "break").strip().lower()
        if requested not in {"break", "continue"}:
            raise ValueError(f"Unsupported break/continue action: {requested}")

        triggered = _bool_value(kwargs.get("condition", True))
        signal = requested if triggered else "none"
        reason = str(kwargs.get("reason", "") or "")
        return {
            "outputs": {
                "signal": signal,
                "value": kwargs.get("value"),
                "triggered": triggered,
                "reason": reason,
            },
            "flow_control": {
                "type": "break_continue",
                "action": signal,
                "triggered": triggered,
                "reason": reason,
            },
        }


class CounterAccumulatorNode(BaseNode):
    """Maintain counters and accumulated values across loop iterations."""

    NODE_ID = "counter_accumulator"
    DISPLAY_NAME = "Counter / Accumulator"
    CATEGORY = "flow_control"
    DESCRIPTION = "Maintain a counter or accumulator across loop iterations using arithmetic or list operations."
    SEARCH_ALIASES = ["counter", "accumulator", "index", "count", "sum", "tally", "running_total"]
    RETURN_TYPES = ("ANY", "INT", "ANY")
    RETURN_NAMES = ("value", "count", "accumulator")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": ("STRING", {
                    "default": "increment",
                    "options": [
                        "increment",
                        "decrement",
                        "add",
                        "subtract",
                        "multiply",
                        "divide",
                        "min",
                        "max",
                        "append",
                        "prepend",
                        "set",
                        "reset",
                        "length",
                    ],
                }),
            },
            "optional": {
                "operand": ("ANY", {}),
                "initial_value": ("ANY", {}),
                "accumulator_key": ("STRING", {"default": "default"}),
                "access_mode": ("STRING", {
                    "default": "read_write",
                    "options": ["read_write", "read_only", "write_only"],
                }),
            },
            "hidden": {
                "_loop_state": ("LOOP_STATE", {}),
                "_iteration": ("INT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        operation = str(kwargs.get("operation", "increment") or "increment")
        operand = kwargs.get("operand")
        initial_value = kwargs.get("initial_value")
        accumulator_key = str(kwargs.get("accumulator_key", "default") or "default")
        access_mode = str(kwargs.get("access_mode", "read_write") or "read_write")
        iteration = int(kwargs.get("_iteration", 0) or 0)

        loop_state = kwargs.get("_loop_state")
        accumulator = self._get_accumulator(loop_state)
        if access_mode == "write_only" or accumulator_key not in accumulator:
            accumulator[accumulator_key] = self._initial_value(operation, initial_value)

        current = accumulator.get(accumulator_key)
        if access_mode == "read_only":
            return self._result(current, iteration, accumulator)

        new_value = self._apply_operation(operation, current, operand, initial_value)
        accumulator[accumulator_key] = new_value
        self._save_accumulator(loop_state, accumulator)
        return self._result(new_value, iteration, accumulator)

    @staticmethod
    def _get_accumulator(loop_state: Any) -> dict[str, Any]:
        if loop_state is None:
            return {}
        if isinstance(loop_state, dict):
            return loop_state
        accumulator = getattr(loop_state, "accumulator", None)
        if isinstance(accumulator, dict):
            return accumulator
        return {}

    @staticmethod
    def _save_accumulator(loop_state: Any, accumulator: dict[str, Any]) -> None:
        if loop_state is not None and not isinstance(loop_state, dict) and hasattr(loop_state, "accumulator"):
            loop_state.accumulator = accumulator

    @staticmethod
    def _initial_value(operation: str, initial_value: Any) -> Any:
        if initial_value is not None:
            return initial_value
        if operation in {"append", "prepend"}:
            return []
        return 0

    @classmethod
    def _apply_operation(cls, operation: str, current: Any, operand: Any, initial_value: Any) -> Any:
        if operation == "increment":
            return cls._number(current, 0) + 1
        if operation == "decrement":
            return cls._number(current, 0) - 1
        if operation == "add":
            return cls._number(current, 0) + cls._number(operand, 0)
        if operation == "subtract":
            return cls._number(current, 0) - cls._number(operand, 0)
        if operation == "multiply":
            return cls._number(current, 1) * cls._number(operand, 1)
        if operation == "divide":
            denominator = cls._number(operand, 1)
            if denominator == 0:
                return current
            return cls._number(current, 0) / denominator
        if operation == "min":
            return operand if current is None else min(current, operand)
        if operation == "max":
            return operand if current is None else max(current, operand)
        if operation == "append":
            return cls._as_list(current) + [operand]
        if operation == "prepend":
            return [operand] + cls._as_list(current)
        if operation == "set":
            return operand
        if operation == "reset":
            return initial_value if initial_value is not None else 0
        if operation == "length":
            return len(current) if hasattr(current, "__len__") else 0
        raise ValueError(f"Unsupported counter/accumulator operation: {operation}")

    @staticmethod
    def _number(value: Any, default: int | float) -> int | float:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        if not text:
            return default
        parsed = float(text)
        return int(parsed) if parsed.is_integer() else parsed

    @staticmethod
    def _as_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    @staticmethod
    def _result(value: Any, iteration: int, accumulator: dict[str, Any]) -> dict[str, Any]:
        return {
            "outputs": {
                "value": value,
                "count": iteration,
                "accumulator": dict(accumulator),
            },
        }


class ParallelForNode(BaseNode):
    """Scatter items into chunks and gather externally produced parallel results."""

    NODE_ID = "parallel_for"
    DISPLAY_NAME = "Parallel For"
    CATEGORY = "flow_control"
    DESCRIPTION = "Scatter items across parallel branches, then gather results with all, any, first, or sorted strategies."
    SEARCH_ALIASES = ["parallel", "scatter", "gather", "fanout", "fanin", "concurrent", "map_reduce"]
    RETURN_TYPES = ("ANY", "INT", "BOOLEAN")
    RETURN_NAMES = ("results", "completed_count", "all_succeeded")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "items": ("ANY", {"description": "Items to scatter across parallel branches"}),
            },
            "optional": {
                "max_concurrency": ("INT", {"default": 4, "min": 1, "max": 100}),
                "gather": ("STRING", {"default": "all", "options": ["all", "any", "first", "sorted"]}),
                "first_n": ("INT", {"default": 1, "min": 1, "max": 100}),
                "sort_key": ("STRING", {"default": ""}),
                "chunk_size": ("INT", {"default": 1, "min": 1, "max": 100}),
            },
            "hidden": {
                "_parallel_results": ("ANY", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        items = _coerce_items(kwargs.get("items", []))
        max_concurrency = max(1, min(100, int(kwargs.get("max_concurrency", 4) or 4)))
        gather = str(kwargs.get("gather", "all") or "all")
        first_n = max(1, min(100, int(kwargs.get("first_n", 1) or 1)))
        sort_key = str(kwargs.get("sort_key", "") or "")
        chunk_size = max(1, min(100, int(kwargs.get("chunk_size", 1) or 1)))
        parallel_results = kwargs.get("_parallel_results")

        if parallel_results is None:
            chunks = [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]
            return {
                "outputs": {
                    "results": [],
                    "completed_count": 0,
                    "all_succeeded": False,
                },
                "inactive_outputs": ["results", "completed_count", "all_succeeded"],
                "flow_control": {
                    "type": "parallel_for",
                    "phase": "scatter",
                    "chunks": chunks,
                    "max_concurrency": max_concurrency,
                    "gather": gather,
                    "first_n": first_n,
                    "sort_key": sort_key,
                },
            }

        results = parallel_results if isinstance(parallel_results, list) else [parallel_results]
        completed = [result for result in results if result is not None]
        gathered = self._gather_results(completed, results, gather, first_n, sort_key)
        return {
            "outputs": {
                "results": gathered,
                "completed_count": len(completed),
                "all_succeeded": len(completed) == len(results),
            },
            "inactive_outputs": [],
            "flow_control": {
                "type": "parallel_for",
                "phase": "gather",
                "gather": gather,
                "completed_count": len(completed),
            },
        }

    @staticmethod
    def _gather_results(
        completed: list[Any],
        all_results: list[Any],
        gather: str,
        first_n: int,
        sort_key: str,
    ) -> Any:
        if gather == "any":
            return completed[0] if completed else None
        if gather == "first":
            return completed[:first_n]
        if gather == "sorted":
            if sort_key:
                return sorted(
                    completed,
                    key=lambda item: item.get(sort_key, "") if isinstance(item, dict) else str(item),
                )
            return sorted(completed, key=lambda item: str(item))
        if gather == "all":
            return all_results
        raise ValueError(f"Unsupported parallel gather strategy: {gather}")


class WhileLoopNode(BaseNode):
    """Track conditional loop state for iterative workflow sections."""

    NODE_ID = "while_loop"
    DISPLAY_NAME = "While Loop"
    CATEGORY = "flow_control"
    DESCRIPTION = "Repeat a loop body while a condition remains true, with a mandatory max-iteration limit."
    SEARCH_ALIASES = ["while", "until", "repeat", "convergence", "iterate"]
    RETURN_TYPES = ("ANY", "INT", "BOOLEAN")
    RETURN_NAMES = ("results", "iterations", "converged")
    REQUIRES_EXTERNAL_TOOLS = False
    ROUTES_FLOW = True
    EXECUTES_LOOP_BODY = True

    _CONDITION_MODES = [
        "file_exists",
        "file_not_exists",
        "numeric_equals",
        "numeric_not_equals",
        "numeric_greater",
        "numeric_less",
        "numeric_greater_equal",
        "numeric_less_equal",
        "boolean_is_true",
        "boolean_is_false",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "condition_mode": ("STRING", {"default": "file_not_exists", "options": cls._CONDITION_MODES}),
            },
            "optional": {
                "value": ("ANY", {}),
                "compare_to": ("STRING", {"default": ""}),
                "max_iterations": ("INT", {"default": 100, "min": 1, "max": 10000}),
                "check_frequency": ("INT", {"default": 1, "min": 1, "max": 100}),
            },
            "hidden": {
                "_loop_state": ("LOOP_STATE", {}),
                "_is_loop_iteration": ("BOOLEAN", {"default": False}),
                "_body_result": ("ANY", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        condition_mode = str(kwargs.get("condition_mode", "file_not_exists") or "file_not_exists")
        value = kwargs.get("value")
        compare_to = kwargs.get("compare_to", "")
        max_iterations = max(1, min(10000, int(kwargs.get("max_iterations", 100) or 100)))
        check_frequency = max(1, min(100, int(kwargs.get("check_frequency", 1) or 1)))
        is_loop_iteration = bool(kwargs.get("_is_loop_iteration", False))

        if not is_loop_iteration:
            loop_state = {
                "iteration": 0,
                "max_iterations": max_iterations,
                "check_frequency": check_frequency,
                "condition_mode": condition_mode,
                "compare_to": compare_to,
                "processed": [],
                "is_complete": False,
            }
            if not self._evaluate_condition(value, condition_mode, compare_to):
                loop_state["is_complete"] = True
                return self._result([], 0, True, "completed", loop_state, inactive=[])
            return self._result(
                [],
                0,
                False,
                "iterating",
                loop_state,
                inactive=["results", "iterations", "converged"],
            )

        loop_state = self._normalise_loop_state(kwargs.get("_loop_state"), condition_mode, compare_to, max_iterations)
        processed = list(loop_state.get("processed", []))
        body_result = kwargs.get("_body_result")
        if body_result is not None:
            processed.append(body_result)
        iteration = int(loop_state.get("iteration", 0) or 0) + 1
        loop_state["iteration"] = iteration
        loop_state["processed"] = processed

        if iteration >= int(loop_state.get("max_iterations", max_iterations) or max_iterations):
            loop_state["is_complete"] = True
            return self._result(processed, iteration, False, "max_iterations", loop_state, inactive=[])

        mode = str(loop_state.get("condition_mode", condition_mode) or condition_mode)
        compare = loop_state.get("compare_to", compare_to)
        if not self._evaluate_condition(value, mode, compare):
            loop_state["is_complete"] = True
            return self._result(processed, iteration, True, "completed", loop_state, inactive=[])

        return self._result(
            processed,
            iteration,
            False,
            "iterating",
            loop_state,
            inactive=["results", "iterations", "converged"],
        )

    @classmethod
    def _evaluate_condition(cls, value: Any, mode: str, compare_to: Any) -> bool:
        if mode == "file_exists":
            return bool(value) and Path(str(value)).exists()
        if mode == "file_not_exists":
            return not (bool(value) and Path(str(value)).exists())
        if mode == "boolean_is_true":
            return _bool_value(value) is True
        if mode == "boolean_is_false":
            return _bool_value(value) is False
        if mode.startswith("numeric_"):
            left = _as_float(value)
            right = _as_float(compare_to)
            if mode == "numeric_equals":
                return left == right
            if mode == "numeric_not_equals":
                return left != right
            if mode == "numeric_greater":
                return left > right
            if mode == "numeric_less":
                return left < right
            if mode == "numeric_greater_equal":
                return left >= right
            if mode == "numeric_less_equal":
                return left <= right
        raise ValueError(f"Unsupported while loop condition mode: {mode}")

    @staticmethod
    def _normalise_loop_state(
        loop_state: Any,
        condition_mode: str,
        compare_to: Any,
        max_iterations: int,
    ) -> dict[str, Any]:
        if isinstance(loop_state, dict):
            state = dict(loop_state)
        else:
            state = {}
            for key in ("iteration", "max_iterations", "processed", "is_complete"):
                if hasattr(loop_state, key):
                    state[key] = getattr(loop_state, key)
            context = getattr(loop_state, "context", None)
            if isinstance(context, dict):
                state.update(context)
        state.setdefault("iteration", 0)
        state.setdefault("max_iterations", max_iterations)
        state.setdefault("condition_mode", condition_mode)
        state.setdefault("compare_to", compare_to)
        state.setdefault("processed", [])
        state.setdefault("is_complete", False)
        return state

    @staticmethod
    def _result(
        results: list[Any],
        iterations: int,
        converged: bool,
        phase: str,
        loop_state: dict[str, Any],
        inactive: list[str],
    ) -> dict[str, Any]:
        return {
            "outputs": {
                "results": results,
                "iterations": iterations,
                "converged": converged,
            },
            "inactive_outputs": inactive,
            "flow_control": {
                "type": "while_loop",
                "phase": phase,
                "is_complete": bool(loop_state.get("is_complete", phase != "iterating")),
                "loop_state": dict(loop_state),
            },
        }
