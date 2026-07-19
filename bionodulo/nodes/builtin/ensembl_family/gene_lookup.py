"""Ensembl gene lookup by symbol or stable ID."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from bionodulo.nodes.base import BaseNode

from .adapter import (
    COMMON_ENSEMBL_SPECIES_OPTIONS,
    ENSEMBL_API_REVISION,
    ENSEMBL_API_VERSION,
    ENSEMBL_GRCH37_HOMOLOGY_DOCUMENTATION_SHA256,
    ENSEMBL_HOMOLOGY_DOCUMENTATION_SHA256,
    ENSEMBL_ID_LOOKUP_DOCUMENTATION_SHA256,
    ENSEMBL_LOOKUP_DOCUMENTATION_SHA256,
    ENSEMBL_SOURCE_COMMIT,
    ENSEMBL_SOURCE_REVISION,
    base_url_for_assembly,
    coerce_species_list,
    is_stable_id,
    request_json,
    validate_assembly_species,
)


def _summary(payload: dict[str, Any]) -> dict[str, Any]:
    region = payload.get("seq_region_name", "")
    start = payload.get("start", "")
    end = payload.get("end", "")
    strand = payload.get("strand", "")
    return {
        "id": str(payload.get("id", "")),
        "display_name": str(payload.get("display_name", "")),
        "description": str(payload.get("description", "")),
        "species": str(payload.get("species", "")),
        "assembly_name": str(payload.get("assembly_name", "")),
        "object_type": str(payload.get("object_type", "")),
        "biotype": str(payload.get("biotype", "")),
        "location": f"{region}:{start}-{end}:{strand}" if region and start and end else "",
    }


class EnsemblGeneLookupNode(BaseNode):
    """Lookup one Ensembl gene and optionally its orthologues."""

    NODE_ID = "ensembl_gene_lookup"
    DISPLAY_NAME = "Ensembl Gene Lookup"
    CATEGORY = "databases"
    DESCRIPTION = "Lookup an Ensembl gene by symbol or stable ID through Ensembl REST."
    SEARCH_ALIASES = ["Ensembl", "gene symbol", "stable ID", "transcript", "orthologue"]
    RETURN_TYPES = ("JSON", "JSON")
    RETURN_NAMES = ("gene_info", "transcripts")
    REQUIRES_EXTERNAL_TOOLS = False
    EXPERIMENTAL = True
    VERSION = f"Ensembl REST {ENSEMBL_API_VERSION} contract snapshot"
    GIT_URL = "https://github.com/Ensembl/ensembl-rest.git"
    GIT_COMMIT = ENSEMBL_SOURCE_COMMIT
    DOCUMENTATION_URL = "https://rest.ensembl.org/documentation/info/symbol_lookup"
    SOURCE_URL = DOCUMENTATION_URL
    SOURCE_REVISION = ENSEMBL_API_REVISION
    SOURCE_SHA256 = ENSEMBL_LOOKUP_DOCUMENTATION_SHA256
    ID_LOOKUP_SOURCE_URL = "https://rest.ensembl.org/documentation/info/lookup"
    ID_LOOKUP_SOURCE_SHA256 = ENSEMBL_ID_LOOKUP_DOCUMENTATION_SHA256
    HOMOLOGY_SOURCE_URL = "https://rest.ensembl.org/documentation/info/homology_species_gene_id"
    HOMOLOGY_SOURCE_SHA256 = ENSEMBL_HOMOLOGY_DOCUMENTATION_SHA256
    GRCH37_HOMOLOGY_SOURCE_URL = (
        "https://grch37.rest.ensembl.org/documentation/info/homology_species_gene_id"
    )
    GRCH37_HOMOLOGY_SOURCE_SHA256 = ENSEMBL_GRCH37_HOMOLOGY_DOCUMENTATION_SHA256
    UPSTREAM_SOURCE_REVISION = ENSEMBL_SOURCE_REVISION
    UPSTREAM_SOURCE = (
        "root/documentation/lookup.conf; root/documentation/compara.conf; "
        "root/documentation/compara_grch37.conf; "
        "lib/EnsEMBL/REST/Controller/Lookup.pm; "
        "lib/EnsEMBL/REST/Controller/Homology.pm"
    )
    NETWORK_SEMANTICS = "Responses reflect the live Ensembl release; GRCh37 requests use the dedicated human GRCh37 host."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "species": ("STRING", {"default": "homo_sapiens", "options": list(COMMON_ENSEMBL_SPECIES_OPTIONS)}),
            },
            "optional": {
                "gene_symbol": ("STRING", {"default": "", "description": "Gene symbol or Ensembl stable ID"}),
                "query": ("STRING", {"default": "", "advanced": True, "description": "Compatibility alias"}),
                "expand": ("BOOLEAN", {"default": False}),
                "assembly": ("STRING", {"default": "current", "options": ["current", "GRCh37"]}),
                "fetch_homologs": ("BOOLEAN", {"default": False}),
                "homolog_species": ("STRING", {"default": "", "description": "Comma-separated target species"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.pop("context", None)
        query = str(kwargs.get("gene_symbol", "") or kwargs.get("query", "")).strip()
        if not query:
            raise ValueError("Ensembl Gene Lookup requires a non-empty gene_symbol")
        species = str(kwargs.get("species", "homo_sapiens") or "homo_sapiens").strip()
        assembly = str(kwargs.get("assembly", "current"))
        validate_assembly_species(assembly, species)
        base_url = base_url_for_assembly(assembly)
        resource = (
            f"lookup/id/{quote(query, safe='')}"
            if is_stable_id(query)
            else f"lookup/symbol/{quote(species, safe='')}/{quote(query, safe='')}"
        )
        lookup_params: dict[str, Any] = {"expand": 1 if kwargs.get("expand", False) else 0}
        if is_stable_id(query):
            lookup_params["species"] = species
        payload = await request_json(resource, lookup_params, base_url=base_url)
        transcripts = payload.get("Transcript", [])
        if not isinstance(transcripts, list):
            transcripts = []
        gene_info = dict(payload)
        gene_info["summary"] = _summary(payload)
        gene_id = str(payload.get("id", "") or "")
        if kwargs.get("fetch_homologs", False):
            if assembly.strip().upper() == "GRCH37":
                raise ValueError("Ensembl GRCh37 does not support orthologue lookup")
            if not gene_id or str(payload.get("object_type", "")).lower() != "gene":
                raise ValueError("Ensembl homology/id requires a resolved gene stable ID")
            targets = coerce_species_list(kwargs.get("homolog_species", ""))
            homology_resource = (
                f"homology/id/{quote(species, safe='')}/{quote(gene_id, safe='')}"
            )
            if len(targets) > 1:
                gene_info["homologs_by_species"] = {}
                for target in targets:
                    gene_info["homologs_by_species"][target] = await request_json(
                        homology_resource,
                        {"type": "orthologues", "target_species": target},
                        base_url=base_url,
                    )
            else:
                params: dict[str, Any] = {"type": "orthologues"}
                if targets:
                    params["target_species"] = targets[0]
                gene_info["homologs"] = await request_json(homology_resource, params, base_url=base_url)
        return {"outputs": {"gene_info": gene_info, "transcripts": transcripts}}
