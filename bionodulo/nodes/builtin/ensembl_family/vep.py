"""Ensembl REST Variant Effect Predictor batches."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from bionodulo.nodes.base import BaseNode

from .adapter import (
    COMMON_ENSEMBL_SPECIES_OPTIONS,
    ENSEMBL_API_REVISION,
    ENSEMBL_API_VERSION,
    ENSEMBL_SOURCE_COMMIT,
    ENSEMBL_SOURCE_REVISION,
    ENSEMBL_VEP_HGVS_DOCUMENTATION_SHA256,
    ENSEMBL_VEP_REGION_DOCUMENTATION_SHA256,
    base_url_for_assembly,
    node_output_dir,
    post_json,
    validate_assembly_species,
)


VEP_POST_MAX = 200
VEP_TABLE_COLUMNS = ("input", "gene_symbol", "gene_id", "transcript_id", "consequence_terms", "impact")


def _vcf_variants(vcf_file: str | Path) -> list[str]:
    variants: list[str] = []
    with Path(vcf_file).open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) < 8:
                raise ValueError(f"VCF record on line {line_number} must have at least 8 columns")
            variants.append(" ".join(fields[:8]))
    if not variants:
        raise ValueError("Ensembl VEP requires at least one VCF variant record")
    return variants


def _summary_rows(payload: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record_index, record in enumerate(payload if isinstance(payload, list) else []):
        if not isinstance(record, dict):
            raise RuntimeError(f"Ensembl VEP record {record_index} is not a JSON object")
        consequences = record.get("transcript_consequences")
        if consequences is None or consequences == []:
            consequences = [{}]
        elif not isinstance(consequences, list):
            raise RuntimeError(f"Ensembl VEP record {record_index} has invalid transcript consequences")
        for consequence_index, consequence in enumerate(consequences):
            if not isinstance(consequence, dict):
                raise RuntimeError(
                    f"Ensembl VEP record {record_index} consequence {consequence_index} "
                    "is not a JSON object"
                )
            terms = consequence.get("consequence_terms", [])
            if not isinstance(terms, list):
                raise RuntimeError(
                    f"Ensembl VEP record {record_index} consequence {consequence_index} "
                    "has invalid consequence terms"
                )
            rows.append(
                {
                    "input": str(record.get("input", "")),
                    "gene_symbol": str(consequence.get("gene_symbol", "")),
                    "gene_id": str(consequence.get("gene_id", "")),
                    "transcript_id": str(consequence.get("transcript_id", "")),
                    "consequence_terms": ",".join(str(term) for term in terms),
                    "impact": str(consequence.get("impact", "")),
                }
            )
    return rows


class EnsemblVEPNode(BaseNode):
    """Annotate HGVS, VCF, or Ensembl region variants through REST VEP."""

    NODE_ID = "ensembl_vep"
    DISPLAY_NAME = "Ensembl VEP"
    CATEGORY = "databases"
    DESCRIPTION = "Annotate variants through the Ensembl REST VEP POST endpoints."
    SEARCH_ALIASES = ["Ensembl", "VEP", "variant consequence", "HGVS", "VCF", "SIFT", "PolyPhen"]
    RETURN_TYPES = ("JSON", "TSV")
    RETURN_NAMES = ("vep_json", "annotation_table")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = f"Ensembl REST {ENSEMBL_API_VERSION} contract snapshot"
    GIT_URL = "https://github.com/Ensembl/ensembl-rest.git"
    GIT_COMMIT = ENSEMBL_SOURCE_COMMIT
    DOCUMENTATION_URL = "https://rest.ensembl.org/documentation/info/vep_region_post"
    SOURCE_URL = DOCUMENTATION_URL
    SOURCE_REVISION = ENSEMBL_API_REVISION
    SOURCE_SHA256 = ENSEMBL_VEP_REGION_DOCUMENTATION_SHA256
    HGVS_SOURCE_URL = "https://rest.ensembl.org/documentation/info/vep_hgvs_post"
    HGVS_SOURCE_SHA256 = ENSEMBL_VEP_HGVS_DOCUMENTATION_SHA256
    UPSTREAM_SOURCE_REVISION = ENSEMBL_SOURCE_REVISION
    UPSTREAM_SOURCE = "root/documentation/vep.conf; lib/EnsEMBL/REST/Controller/VEP.pm"
    NETWORK_SEMANTICS = (
        "Inputs are chunked to the documented 200-variant POST limit; "
        "responses reflect live Ensembl data."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "species": ("STRING", {"default": "homo_sapiens", "options": list(COMMON_ENSEMBL_SPECIES_OPTIONS)}),
            },
            "optional": {
                "variants": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": "HGVS variants, one per line",
                        "displayOptions": {"show": {"variant_format": ["hgvs"]}},
                    },
                ),
                "variant_format": ("STRING", {"default": "hgvs", "options": ["hgvs", "vcf"]}),
                "vcf_file": (
                    "VCF",
                    {
                        "default": "",
                        "description": "VCF input for variant_format=vcf",
                        "displayOptions": {"show": {"variant_format": ["vcf"]}},
                    },
                ),
                "assembly": ("STRING", {"default": "current", "options": ["current", "GRCh38", "GRCh37"]}),
                "canonical": ("BOOLEAN", {"default": False}),
                "domains": ("BOOLEAN", {"default": False}),
                "variant_class": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        species = str(kwargs.get("species", "homo_sapiens") or "homo_sapiens").strip()
        assembly = str(kwargs.get("assembly", "current"))
        validate_assembly_species(assembly, species)
        variant_format = str(kwargs.get("variant_format", "hgvs") or "hgvs").lower()
        if variant_format not in {"hgvs", "vcf"}:
            raise ValueError(f"Unsupported Ensembl VEP variant_format: {variant_format}")
        variants_text = str(kwargs.get("variants", "") or "").strip()
        if variant_format == "vcf":
            vcf_file = str(kwargs.get("vcf_file", "") or "").strip()
            if not vcf_file:
                raise ValueError("Ensembl VEP requires a VCF file")
            variants = _vcf_variants(vcf_file)
            endpoint = "region"
        else:
            variants = [line.strip() for line in variants_text.splitlines() if line.strip()]
            if not variants:
                raise ValueError("Ensembl VEP requires at least one variant")
            endpoint = "hgvs"
        params = {
            "canonical": 1 if kwargs.get("canonical", False) else 0,
            "domains": 1 if kwargs.get("domains", False) else 0,
            "variant_class": 1 if kwargs.get("variant_class", False) else 0,
        }
        resource = f"vep/{quote(species, safe='')}/{endpoint}"
        payload: list[Any] = []
        for start in range(0, len(variants), VEP_POST_MAX):
            chunk = variants[start : start + VEP_POST_MAX]
            body_key = "hgvs_notations" if endpoint == "hgvs" else "variants"
            response = await post_json(
                resource,
                {body_key: chunk},
                params,
                base_url=base_url_for_assembly(assembly),
            )
            if not isinstance(response, list):
                raise RuntimeError("Ensembl VEP returned a non-list response")
            if not response:
                raise RuntimeError("Ensembl VEP returned an empty response")
            payload.extend(response)
        output = node_output_dir(self, context)
        json_path = output / "vep_results.json"
        table_path = output / "annotation_table.tsv"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with table_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=VEP_TABLE_COLUMNS, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(_summary_rows(payload))
        return {"outputs": {"vep_json": str(json_path), "annotation_table": str(table_path)}}
