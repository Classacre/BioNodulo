"""Deterministic seeded subsetting of a POD5 file via the pod5 Python API."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.base import BaseNode, path_probe_is_file

POD5_VERSION = "0.3.44"
POD5_GIT_URL = "https://github.com/nanoporetech/pod5-file-format.git"
POD5_GIT_COMMIT = "23346e11be006f8f7c4047172d10e542172b7af6"
POD5_SOURCE_TAG = "0.3.44"
MAX_NUM_READS = 50_000_000
_READ_CHUNK = 1 << 20


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_READ_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Pod5SubsetNode(BaseNode):
    """Write a seeded random subset of reads from one POD5 file."""

    NODE_ID = "pod5_subset"
    DISPLAY_NAME = "POD5 Subset"
    CATEGORY = "long_read"
    DESCRIPTION = (
        "Subset a POD5 file to a seeded random sample of reads with the pod5 Python "
        "API: a first pass counts reads (the footer num_reads lookup when present, "
        "otherwise a full serial counting pass), then indices are drawn with "
        "random.Random(seed).sample over the file order and copied with Writer.add_read, "
        "so the same seed always yields the same subset. Emits the subset POD5 plus a "
        "JSON summary with input/output read counts, seed, and output sha256."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "POD5",
        "pod5",
        "subsetting",
        "downsampling",
        "Oxford Nanopore",
        "ONT",
    ]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("subset_pod5", "summary")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: ClassVar[list[str]] = []
    REQUIRED_CONDA_PACKAGES = ["pod5"]
    CONDA_PACKAGE_CONSTRAINTS = {"pod5": POD5_VERSION}
    PACKAGE_CONSTRAINT = "pod5 = 0.3.44"
    VERSION = POD5_VERSION
    GIT_URL = POD5_GIT_URL
    GIT_COMMIT = POD5_GIT_COMMIT
    SOURCE_TAG = POD5_SOURCE_TAG
    SOURCE_REF = f"tag {POD5_SOURCE_TAG} at {POD5_GIT_COMMIT}"
    DOCUMENTATION_URL = "https://pod5-file-format.readthedocs.io/en/latest"
    ENVIRONMENT = {"python": "3.12", "conda_package": "pod5 = 0.3.44"}
    EXIT_SEMANTICS = (
        "Input validation, unreadable POD5 files, and writer failures raise the "
        "standard node runtime error; only the declared outputs are successful artifacts."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "pod5_path": ("FILE", {"description": "Input POD5 file"}),
            },
            "optional": {
                "num_reads": (
                    "INT",
                    {"default": 1_000_000, "min": 1, "max": MAX_NUM_READS, "description": "Reads to keep"},
                ),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2_147_483_647}),
                "output_name": (
                    "STRING",
                    {"default": "subset.pod5", "description": "Output file name inside the node directory"},
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key, default, minimum, maximum in (
            ("num_reads", 1_000_000, 1, MAX_NUM_READS),
            ("seed", 0, 0, 2_147_483_647),
        ):
            value = inputs.get(key, default)
            if isinstance(value, bool) or not isinstance(value, int):
                return f"Input '{key}' must be an integer"
            if value < minimum:
                return f"Input '{key}' must be at least {minimum}"
            if value > maximum:
                return f"Input '{key}' must be at most {maximum}"
        name = str(inputs.get("output_name", "subset.pod5") or "subset.pod5").strip()
        if not name or Path(name).name != name or name in {".", ".."}:
            return "Input 'output_name' must be a plain file name without path separators"
        return True

    @staticmethod
    def selected_indices(n_total: int, num_reads: int, seed: int) -> list[int]:
        """Return the sorted file-order indices forming the deterministic subset."""
        if n_total <= 0:
            return []
        count = min(num_reads, n_total)
        return sorted(random.Random(seed).sample(range(n_total), count))

    @staticmethod
    def _count_reads(reader: Any) -> tuple[int, bool]:
        footer_count = getattr(reader, "num_reads", None)
        if isinstance(footer_count, int) and footer_count >= 0:
            return footer_count, True
        return sum(1 for _ in reader.reads()), False

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        try:
            import pod5 as p5
        except ImportError as exc:
            raise RuntimeError(
                "The 'pod5' Python package is required by pod5_subset; install the "
                "pinned conda package 'pod5 = 0.3.44'"
            ) from exc

        source_text = str(kwargs["pod5_path"]).strip()
        source = Path(source_text).expanduser()
        if not path_probe_is_file(source_text):
            raise ValueError(f"Input file does not exist: {source}")
        num_reads = int(kwargs.get("num_reads", 1_000_000))
        seed = int(kwargs.get("seed", 0))
        output_name = str(kwargs.get("output_name", "subset.pod5") or "subset.pod5").strip()
        if not output_name.endswith(".pod5"):
            output_name = f"{output_name}.pod5"

        base = Path(getattr(context, "node_dir", ".") if context else ".")
        output_dir = base / self.NODE_ID
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_name
        summary_path = output_dir / "summary.json"

        with p5.Reader(str(source)) as reader:
            n_total, counted_from_footer = self._count_reads(reader)
            selected = set(self.selected_indices(n_total, num_reads, seed))
            if output_path.exists():
                output_path.unlink()
            with p5.Writer(str(output_path)) as writer:
                for index, read in enumerate(reader.reads()):
                    if index in selected:
                        writer.add_read(read.to_read())

        n_output = len(selected)
        payload = {
            "input_pod5": str(source),
            "output_pod5": str(output_path),
            "n_input_reads": n_total,
            "n_output_reads": n_output,
            "num_reads_requested": num_reads,
            "seed": seed,
            "sha256": _sha256_file(output_path),
            "counted_from_footer": counted_from_footer,
            "selection": "random.Random(seed).sample over deterministic POD5 file order",
        }
        summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return (str(output_path), str(summary_path))
