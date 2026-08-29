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
        "'score' (or 'improved' as 1/0) into while_loop numeric condition modes. "
        "Empty-tolerant: an empty or null incoming batch passes the current best "
        "through unchanged (or null when no best exists yet) with improved=false."
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
                "candidates": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Optional candidate pool (TSV or JSON) containing the sequences "
                            "(a cds/cds_sequence/sequence column). When provided, the best "
                            "record also carries best_cds: the winning candidate's sequence, "
                            "so downstream FASTA conversion can consume the best design."
                        ),
                    },
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

        current_raw = kwargs.get("current")
        current = None
        if current_raw not in (None, ""):
            entries = self._entries(current_raw, "current", key)
            current = self._best(entries, mode, key) if entries else None

        # Empty-tolerant: an empty incoming batch (e.g. a first iteration where
        # every evaluator produced no rows) passes the current best through
        # unchanged — or null when no best exists yet — instead of erroring.
        if not incoming:
            best = current
            improved = False
            score = float(best[key]) if best is not None else 0.0
            output_dir = node_output_dir(self, context)
            best_path = output_dir / "best.json"
            write_json_file(best_path, best)
            return (str(best_path), improved, score)

        best_incoming = self._best(incoming, mode, key)
        improved = current is None or self._better(best_incoming[key], current[key], mode)
        best = best_incoming if improved else current

        candidates_raw = kwargs.get("candidates")
        if candidates_raw not in (None, ""):
            best = self._with_best_cds(best, candidates_raw)

        output_dir = node_output_dir(self, context)
        best_path = output_dir / "best.json"
        write_json_file(best_path, best)
        return (str(best_path), improved, float(best[key]))

    _SEQUENCE_COLUMNS = ("cds", "cds_sequence", "sequence")

    @classmethod
    def _with_best_cds(cls, best: dict[str, Any] | None, candidates_raw: Any) -> dict[str, Any] | None:
        """Join the winning candidate's sequence into the best record as best_cds.

        The ranked batches that feed this node carry ids and scores but not
        sequences, so downstream FASTA export of the winning design needs the
        sequence re-attached from the iteration's candidate pool. A pool row
        with a matching id and a non-empty sequence column wins; anything else
        leaves the record unchanged (the loop's design loops always emit the
        candidate table, but this node must not break other uses).
        """
        if best is None:
            return best
        try:
            payload, table = load_json_or_table(candidates_raw, "candidates")
        except Exception:
            return best
        rows: list[dict[str, Any]]
        if table is not None:
            rows = [dict(row) for row in table[1]]
        elif isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            rows = [payload]
        else:
            return best
        best_id = str(best.get("id", ""))
        for row in rows:
            if str(row.get("id", "")) != best_id:
                continue
            for column in cls._SEQUENCE_COLUMNS:
                value = str(row.get(column, "") or "")
                if value:
                    return {**best, "best_cds": value}
        return best

    @staticmethod
    def _entries(value: Any, name: str, key: str) -> list[dict[str, Any]]:
        payload, table = load_json_or_table(value, name)
        if table is not None:
            fieldnames, rows = table
            if not rows:
                return []  # header-only / empty table: nothing to compare
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
