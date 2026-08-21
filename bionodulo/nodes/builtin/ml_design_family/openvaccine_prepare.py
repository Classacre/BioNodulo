"""Prepare OpenVaccine RYOS degradation data for design-loop evaluation."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import path_probe_is_file

from .adapter import MLDesignNode, node_output_dir, write_json_file, write_tsv_file

DEFAULT_ARMS = "deg_Mg_pH10,deg_pH10,deg_Mg_50C,deg_50C"
RDAT_ARM = "reactivity"


class OpenvaccinePrepareNode(MLDesignNode):
    """Summarize per-nt degradation arrays as k_deg / t_half per molecule and arm."""

    NODE_ID = "openvaccine_prepare"
    DISPLAY_NAME = "OpenVaccine Prepare"
    DESCRIPTION = (
        "Prepares OpenVaccine RYOS degradation measurements for the design loop. "
        "JSON input (preferred): the published RYOS_FULL_23Jul2021.json columnar "
        "schema, i.e. a top-level object whose 'ID', 'sequence', and arm keys each "
        "map row-key -> value ('ID': {row: construct_id}, 'sequence': {row: RNA "
        "sequence}, 'deg_Mg_pH10': {row: [per-nt floats]}, ...; deg arrays are "
        "aligned to 'seqpos' and are shorter than the full sequence). A JSON array "
        "of {id, sequence, <arm>} entry objects is also accepted. Per molecule and "
        "arm the node emits k_deg = sum(per-nt values) / max(n_measured - 1, 1), "
        "the sum-over-linkages form of the Wayment-Steele degradation relation "
        "normalized per linkage, and t_half = ln(2) / k_deg. The arrays are "
        "reactivity-like measurements, not calibrated rates, so k_deg and t_half "
        "are documented proxies for relative ranking only. Arms with missing/null "
        "arrays for a molecule (common in RYOS_FULL) are skipped and counted per "
        "arm in the summary. RDAT input (fallback): a minimal parser extracts "
        "SEQUENCE and REACTIVITY blocks and reports them under the 'reactivity' "
        "arm. Null array entries are skipped."
    )
    SEARCH_ALIASES = [
        "openvaccine",
        "ryos",
        "degradation",
        "k_deg",
        "half life",
        "mrna stability",
        "eterna",
        "rdat",
    ]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("molecules", "summary")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {},
            "optional": {
                "json_path": ("STRING", {"default": "", "description": "RYOS_FULL-style JSON file path (preferred)"}),
                "rdat_path": ("STRING", {"default": "", "description": "RDAT file path; REACTIVITY sections parsed minimally"}),
                "arms": ("STRING", {"default": DEFAULT_ARMS, "description": "Comma-separated degradation arms to include"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        json_path = str(kwargs.get("json_path") or "").strip()
        rdat_path = str(kwargs.get("rdat_path") or "").strip()
        if bool(json_path) == bool(rdat_path):
            raise ValueError("Provide exactly one of 'json_path' or 'rdat_path'")
        arms = self._arms(kwargs.get("arms", DEFAULT_ARMS))

        molecules, missing_counts = self._from_json(json_path, arms) if json_path else self._from_rdat(rdat_path, arms)
        # Public datasets carry duplicate construct IDs (RYOS alone has 8), and
        # tsv_to_fasta treats colliding normalized IDs as fatal. Suffix repeats
        # here so every molecule keeps a unique, stable identity end-to-end.
        seen_ids: set[str] = set()
        duplicated_ids = 0
        for entry in molecules:
            candidate = str(entry["id"])
            if candidate in seen_ids:
                duplicated_ids += 1
                counter = 1
                while f"{candidate}-dup{counter}" in seen_ids:
                    counter += 1
                candidate = f"{candidate}-dup{counter}"
                entry["id"] = candidate
            seen_ids.add(candidate)
        rows = [
            {
                "id": entry["id"],
                "arm": arm,
                "sequence": entry["sequence"],
                "k_deg": entry["arms"][arm]["k_deg"],
                "t_half": entry["arms"][arm]["t_half"],
                "n_nt": len(entry["sequence"]),
                "n_measured": entry["arms"][arm]["n_measured"],
            }
            for entry in molecules
            for arm in sorted(entry["arms"])
        ]
        if not rows:
            raise ValueError("No molecule x arm degradation values were found for the requested arms")

        arm_stats: dict[str, dict[str, Any]] = {}
        for arm in arms:
            k_values = [row["k_deg"] for row in rows if row["arm"] == arm and row["k_deg"] is not None]
            t_values = [row["t_half"] for row in rows if row["arm"] == arm and row["t_half"] is not None]
            arm_stats[arm] = {
                "n": len(k_values),
                "n_missing": missing_counts.get(arm, 0),
                "mean_k_deg": sum(k_values) / len(k_values) if k_values else None,
                "mean_t_half": sum(t_values) / len(t_values) if t_values else None,
            }
        summary = {
            "n_molecules": len(molecules),
            "n_duplicated_ids_suffixed": duplicated_ids,
            "arms": sorted(arm_stats),
            "per_arm": arm_stats,
            "k_deg_definition": "sum(per-nt values) / max(n_measured - 1, 1)",
            "t_half_definition": "ln(2) / k_deg",
            "proxy_note": "RYOS arrays are reactivity-like measurements, not calibrated rates; k_deg/t_half are relative-ranking proxies",
        }

        output_dir = node_output_dir(self, context)
        molecules_path = output_dir / "molecules.tsv"
        summary_path = output_dir / "summary.json"
        write_tsv_file(
            molecules_path,
            ["id", "arm", "sequence", "k_deg", "t_half", "n_nt", "n_measured"],
            rows,
        )
        write_json_file(summary_path, summary)
        return (str(molecules_path), str(summary_path))

    @staticmethod
    def _arms(value: Any) -> list[str]:
        text = str(value if value not in (None, "") else DEFAULT_ARMS)
        arms = [part.strip() for part in text.split(",") if part.strip()]
        if not arms:
            raise ValueError("Input 'arms' must contain at least one arm name")
        if len(set(arms)) != len(arms):
            raise ValueError("Input 'arms' contains duplicate arm names")
        return arms

    @classmethod
    def _from_json(cls, json_path: str, arms: list[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
        if not path_probe_is_file(json_path):
            raise ValueError(f"Input 'json_path' is not an existing file: {json_path}")
        payload = json.loads(Path(json_path).expanduser().read_text(encoding="utf-8"))
        if isinstance(payload, list):
            keys = [str(index) for index in range(len(payload))]
            identifiers = {str(index): str(entry.get("id", index)) for index, entry in enumerate(payload)}
            sequences = {str(index): entry.get("sequence", "") for index, entry in enumerate(payload)}
            arm_columns = {arm: {str(index): entry.get(arm) for index, entry in enumerate(payload)} for arm in arms}
        elif isinstance(payload, dict) and isinstance(payload.get("sequence"), dict):
            keys = sorted(payload["sequence"], key=lambda key: (int(key) if key.isdigit() else math.inf, key))
            ids = payload.get("ID")
            identifiers = {key: str(ids[key]) if isinstance(ids, dict) and key in ids else key for key in keys}
            sequences = payload["sequence"]
            arm_columns = {arm: payload.get(arm) for arm in arms}
        else:
            raise ValueError(
                "Input 'json_path' must be the RYOS columnar object ('ID'/'sequence'/arm column dicts) "
                "or a JSON array of {id, sequence, arm} entries"
            )

        molecules: list[dict[str, Any]] = []
        missing_counts = {arm: 0 for arm in arms}
        for key in keys:
            sequence = str(sequences.get(key, "") or "").upper()
            if not sequence:
                continue
            per_arm: dict[str, dict[str, Any]] = {}
            for arm in arms:
                column = arm_columns.get(arm)
                values = column.get(key) if isinstance(column, dict) else None
                if not isinstance(values, list):
                    missing_counts[arm] += 1
                    continue
                numbers = [float(item) for item in values if item is not None]
                per_arm[arm] = cls._kinetics(numbers)
            molecules.append({"id": identifiers[key], "sequence": sequence, "arms": per_arm})
        return molecules, missing_counts

    @staticmethod
    def _kinetics(numbers: list[float]) -> dict[str, Any]:
        if not numbers:
            return {"k_deg": None, "t_half": None, "n_measured": 0}
        k_deg = sum(numbers) / max(len(numbers) - 1, 1)
        t_half = math.log(2.0) / k_deg if k_deg > 0 else None
        return {"k_deg": k_deg, "t_half": t_half, "n_measured": len(numbers)}

    @classmethod
    def _from_rdat(cls, rdat_path: str, arms: list[str]) -> tuple[list[dict[str, Any]], dict[str, int]]:
        if not path_probe_is_file(rdat_path):
            raise ValueError(f"Input 'rdat_path' is not an existing file: {rdat_path}")
        if arms != [RDAT_ARM]:
            raise ValueError(f"RDAT input supports only the '{RDAT_ARM}' arm; set arms='{RDAT_ARM}' (requested: {', '.join(arms)})")
        text = Path(rdat_path).expanduser().read_text(encoding="utf-8")
        records: list[dict[str, Any]] = []
        current_id: str | None = None
        current_sequence: str | None = None
        current_values: list[str] | None = None
        section = 0

        def flush() -> None:
            nonlocal current_id, current_sequence, current_values, section
            if current_sequence is not None and current_values is not None:
                numbers = [float(item) for item in current_values if item.upper() not in ("NAN", "NULL", "-", "NA", "")]
                records.append(
                    {
                        "id": current_id or f"rdat_{section}",
                        "sequence": current_sequence.upper(),
                        "arms": {RDAT_ARM: cls._kinetics(numbers)},
                    }
                )
            section += 1
            current_id = None
            current_sequence = None
            current_values = None

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("ID:"):
                flush()
                current_id = line[3:].strip()
            elif line.startswith("CONSTRUCT:"):
                flush()
                current_id = line[10:].strip()
            elif line.startswith("SEQUENCE:"):
                if current_sequence is not None:
                    flush()
                current_sequence = line[9:].strip()
            elif line.startswith("REACTIVITY:"):
                current_values = line[11:].split()
        flush()
        return [record for record in records if record["arms"]], {RDAT_ARM: 0}
