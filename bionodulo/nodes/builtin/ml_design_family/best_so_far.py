"""Stateless argmax tracker for iterative design loops."""

from __future__ import annotations

from typing import Any

from .adapter import (
    MLDesignNode,
    load_json_or_table,
    node_output_dir,
    numeric_field,
    validate_choice_input,
    write_json_file,
)

MODES = ("maximize", "minimize")


class BestSoFarNode(MLDesignNode):
    """Keep the best candidate across loop iterations without hidden state."""

    NODE_ID = "best_so_far"
    DISPLAY_NAME = "Best So Far"
    DESCRIPTION = (
        "Stateless argmax tracker for while_loop design loops: compares the incoming "
        "candidate batch's best key value against the current best and emits the updated "
        "best plus an 'improved' boolean and numeric 'score'. Wire it as: while_loop "
        "'value' -> best_so_far 'current', each iteration's ranked/candidate batch -> "
        "best_so_far 'incoming', and best_so_far 'best' -> the loop-body node that feeds "
        "the while_loop 'value' input, so state arrives purely through loop wiring. Feed "
        "'score' (or 'improved' as 1/0) into while_loop numeric condition modes."
    )
    SEARCH_ALIASES = [
        "best so far",
        "argmax",
        "running best",
        "loop state",
        "convergence",
        "while loop",
        "design loop",
    ]
    RETURN_TYPES = ("JSON", "BOOLEAN", "FLOAT")
    RETURN_NAMES = ("best", "improved", "score")
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/functions.html#max"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "incoming": (
                    "STRING",
                    {"description": "Candidate batch this iteration: JSON array with id and the key field, or TSV"},
                ),
            },
            "optional": {
                "current": (
                    "STRING",
                    {"default": "", "description": "Current best carried by the loop; empty on iteration one"},
                ),
                "mode": ("STRING", {"default": "maximize", "options": list(MODES)}),
                "key": ("STRING", {"default": "composite", "description": "Numeric field compared across entries"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_choice_input(inputs.get("mode", "maximize"), "mode", MODES)
        if validation is not True:
            return validation
        if not str(inputs.get("key", "composite") or "composite").strip():
            return "Input 'key' must be a non-empty field name"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, bool, float]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        mode = str(kwargs.get("mode", "maximize"))
        key = str(kwargs.get("key", "composite") or "composite").strip()
        incoming = self._entries(kwargs["incoming"], "incoming", key)
        if not incoming:
            raise ValueError("Input 'incoming' must contain at least one entry")
        best_incoming = self._best(incoming, mode, key)

        current_raw = kwargs.get("current")
        current = None
        if current_raw not in (None, ""):
            entries = self._entries(current_raw, "current", key)
            if not entries:
                raise ValueError("Input 'current' must contain at least one entry")
            current = self._best(entries, mode, key)

        improved = current is None or self._better(best_incoming[key], current[key], mode)
        best = best_incoming if improved else current

        output_dir = node_output_dir(self, context)
        best_path = output_dir / "best.json"
        write_json_file(best_path, best)
        return (str(best_path), improved, float(best[key]))

    @staticmethod
    def _entries(value: Any, name: str, key: str) -> list[dict[str, Any]]:
        payload, table = load_json_or_table(value, name)
        if table is not None:
            fieldnames, rows = table
            for column in ("id", key):
                if column not in fieldnames:
                    raise ValueError(f"Input '{name}' TSV header must contain an '{column}' column")
            payload = [{**row, key: row.get(key, "")} for row in rows]
        if payload is None:
            return []
        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            raise ValueError(f"Input '{name}' must be a JSON object, a JSON array of objects, or a TSV file")
        entries: list[dict[str, Any]] = []
        for index, entry in enumerate(payload):
            if not isinstance(entry, dict):
                raise ValueError(f"Input '{name}' entry {index} must be a JSON object")
            entries.append(dict(entry))
        for entry in entries:
            entry[key] = numeric_field(entry, key, f"Input '{name}' entry {entry.get('id', '?')}")
        return entries

    @staticmethod
    def _best(entries: list[dict[str, Any]], mode: str, key: str) -> dict[str, Any]:
        sign = -1.0 if mode == "minimize" else 1.0
        return sorted(entries, key=lambda entry: (-sign * entry[key], str(entry.get("id", ""))))[0]

    @staticmethod
    def _better(candidate: float, incumbent: float, mode: str) -> bool:
        return candidate < incumbent if mode == "minimize" else candidate > incumbent
