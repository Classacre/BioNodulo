"""Fail-closed validation gate for accession download manifests."""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path
from typing import Any

from .adapter import MLDesignNode, existing_file, node_output_dir, write_json_file

MANIFEST_COLUMNS = (
    "accession",
    "resolved_version",
    "feature_used",
    "fetch_date",
    "sha256",
    "file",
    "notes",
)
REQUIRED_COLUMNS = ("accession", "sha256", "file")
_READ_CHUNK = 1 << 20


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_fetch_date(text: str) -> str | None:
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _resolve_file(raw: str, manifest_dir: Path) -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        for base in (manifest_dir, Path.cwd()):
            resolved = (base / candidate).resolve()
            if resolved.exists():
                return resolved
    return candidate


class AccessionGateNode(MLDesignNode):
    """Validate an accession manifest TSV and optionally verify file hashes."""

    NODE_ID = "accession_gate"
    DISPLAY_NAME = "Accession Gate"
    DESCRIPTION = (
        "Validate a manifest TSV (columns accession, resolved_version, feature_used, fetch_date, "
        "sha256, file, notes): header present, at least one row, every row has non-empty accession, "
        "sha256, and file, and fetch_date parses as YYYY-MM-DD. With require_files_exist (default "
        "true) each file path is resolved (relative paths tried against the manifest directory then "
        "the working directory) and its sha256 recomputed and compared case-insensitively. Writes "
        "manifest_status.json with passed plus per-row results and returns all_pass; fail_closed "
        "(default true) raises when not every row passes."
    )
    SEARCH_ALIASES = [
        "accession",
        "manifest",
        "provenance",
        "checksum",
        "sha256",
        "validation",
        "gate",
        "reproducibility",
    ]
    RETURN_TYPES = ("JSON", "BOOLEAN")
    RETURN_NAMES = ("manifest_status", "all_pass")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "manifest": ("FILE", {"description": "Manifest TSV with an accession/sha256/file header"}),
            },
            "optional": {
                "require_files_exist": (
                    "BOOLEAN",
                    {"default": True, "description": "Verify each file exists and its sha256 matches"},
                ),
                "fail_closed": (
                    "BOOLEAN",
                    {"default": True, "description": "Raise instead of returning all_pass=false"},
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("require_files_exist", "fail_closed"):
            if not isinstance(inputs.get(key, True), bool):
                return f"Input '{key}' must be a boolean"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, bool]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        require_files_exist = bool(kwargs.get("require_files_exist", True))
        fail_closed = bool(kwargs.get("fail_closed", True))
        path = existing_file(kwargs["manifest"], "manifest")

        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"Input 'manifest' is empty: {path}")
        fieldnames = [name.strip() for name in lines[0].split("\t")]
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing_columns:
            raise ValueError(
                f"Input 'manifest' header is missing required column(s): {', '.join(missing_columns)} "
                f"(found: {', '.join(fieldnames)})"
            )
        unknown_columns = [name for name in fieldnames if name and name not in MANIFEST_COLUMNS]
        if unknown_columns:
            raise ValueError(f"Input 'manifest' header has unexpected column(s): {', '.join(unknown_columns)}")

        row_results: list[dict[str, Any]] = []
        for line_number, line in enumerate(lines[1:], start=2):
            values = [item.strip() for item in line.split("\t")]
            if len(values) != len(fieldnames):
                raise ValueError(
                    f"Input 'manifest' row {line_number} has {len(values)} fields; expected {len(fieldnames)}"
                )
            row = dict(zip(fieldnames, values, strict=True))
            errors: list[str] = []
            for column in REQUIRED_COLUMNS:
                if not row.get(column, ""):
                    errors.append(f"empty {column}")
            parsed_date = _parse_fetch_date(row.get("fetch_date", ""))
            if parsed_date is None:
                errors.append("fetch_date is not a valid YYYY-MM-DD date")
            file_status = "skipped"
            observed_sha256 = ""
            file_path = ""
            if not errors and require_files_exist:
                file_path = str(_resolve_file(row["file"], path.parent))
                if not Path(file_path).is_file():
                    errors.append("file does not exist")
                    file_status = "missing"
                else:
                    observed_sha256 = _sha256_file(Path(file_path))
                    if observed_sha256.lower() != row["sha256"].lower():
                        errors.append("sha256 mismatch")
                        file_status = "hash_mismatch"
                    else:
                        file_status = "verified"
            row_results.append(
                {
                    "row": line_number,
                    "accession": row.get("accession", ""),
                    "resolved_version": row.get("resolved_version", ""),
                    "feature_used": row.get("feature_used", ""),
                    "fetch_date": parsed_date or row.get("fetch_date", ""),
                    "sha256": row.get("sha256", ""),
                    "file": row.get("file", ""),
                    "resolved_file": file_path,
                    "observed_sha256": observed_sha256,
                    "file_status": file_status,
                    "errors": errors,
                    "passed": not errors,
                }
            )

        if not row_results:
            raise ValueError(f"Input 'manifest' contains no data rows: {path}")
        all_pass = all(result["passed"] for result in row_results)
        payload = {
            "manifest": str(path),
            "passed": all_pass,
            "n_rows": len(row_results),
            "n_failed": sum(1 for result in row_results if not result["passed"]),
            "require_files_exist": require_files_exist,
            "rows": row_results,
        }
        output_dir = node_output_dir(self, context)
        status_path = output_dir / "manifest_status.json"
        write_json_file(status_path, payload)
        if fail_closed and not all_pass:
            failed = ", ".join(str(result["row"]) for result in row_results if not result["passed"])
            raise RuntimeError(f"Accession manifest gate failed for row(s): {failed} (see {status_path})")
        return (str(status_path), all_pass)
