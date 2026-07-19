"""Structured LLM extraction with deterministic JSON and CSV artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .adapter import (
    LiteLLMNode,
    _llm_config_from_kwargs,
    _messages,
    _node_output_dir,
    call_llm,
    require_artifacts,
    safe_json_parse,
    validate_choice,
)


class AIDataExtractionNode(LiteLLMNode):
    """Extract structured biological entities from unstructured text with an LLM."""

    NODE_ID = "ai_data_extraction"
    DISPLAY_NAME = "AI Data Extraction"
    CATEGORY = "ai"
    DESCRIPTION = "Extract structured biological entities from unstructured text into JSON and CSV outputs."
    SEARCH_ALIASES = [
        "extract",
        "ner",
        "entities",
        "parse",
        "genes",
        "variants",
        "diseases",
        "text-mining",
        "biocuration",
    ]
    RETURN_TYPES = ("JSON", "CSV")
    RETURN_NAMES = ("extracted_json", "extracted_csv")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_text": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": "Unstructured text to extract entities from",
                    },
                ),
                "extraction_schema": (
                    "STRING",
                    {
                        "default": "genes_variants_diseases",
                        "options": [
                            "genes_variants_diseases",
                            "drugs_targets",
                            "clinical_trial",
                            "pathway_interactions",
                            "custom",
                        ],
                    },
                ),
            },
            "optional": {
                "custom_entities": ("STRING", {"default": "", "multiline": True}),
                "input_file": ("FILE", {"description": "Optional text file to read instead of input_text"}),
                "output_format": ("STRING", {"default": "both", "options": ["json", "csv", "both"]}),
                "include_context": ("BOOLEAN", {"default": True}),
                "normalize_ids": ("BOOLEAN", {"default": True}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "extracted.json"
        csv_path = out_dir / "extracted.csv"

        input_text = _read_data_extraction_text(kwargs.get("input_text", ""), kwargs.get("input_file", ""))
        extraction_schema = validate_choice(
            kwargs.get("extraction_schema", "genes_variants_diseases"),
            "extraction_schema",
            tuple(_EXTRACTION_SCHEMAS) + ("custom",),
        )
        custom_entities = _parse_custom_entities(str(kwargs.get("custom_entities", "") or ""))
        if extraction_schema == "custom" and not custom_entities:
            raise ValueError("custom_entities is required when extraction_schema is custom")
        output_format = validate_choice(kwargs.get("output_format", "both"), "output_format", ("json", "csv", "both"))
        include_context = bool(kwargs.get("include_context", True))
        normalize_ids = bool(kwargs.get("normalize_ids", True))

        config = _llm_config_from_kwargs({**kwargs, "context": context})
        response = await call_llm(
            config,
            _messages(
                system_prompt=(
                    "You are an expert biomedical entity extraction system. Extract only entities supported "
                    "by the supplied text and return valid JSON."
                ),
                prompt=_data_extraction_prompt(
                    text=input_text,
                    extraction_schema=extraction_schema,
                    custom_entities=custom_entities,
                    include_context=include_context,
                    normalize_ids=normalize_ids,
                ),
            ),
            json_mode=True,
        )
        entities = safe_json_parse(response.content) or {"raw_extraction": response.content}
        payload = {
            "extraction_schema": extraction_schema,
            "source_text_length": _data_extraction_source_text_length(input_text),
            "entities": entities,
            "usage": response.usage,
            "model": response.model or config.model,
        }
        if extraction_schema == "custom":
            payload["custom_entities"] = [entity["name"] for entity in custom_entities]

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_extraction_csv(csv_path, entities)
        require_artifacts(json_path, csv_path)

        return {
            "outputs": {
                "extracted_json": str(json_path) if output_format in {"json", "both"} else "",
                "extracted_csv": str(csv_path) if output_format in {"csv", "both"} else "",
            }
        }


_EXTRACTION_SCHEMAS: dict[str, dict[str, Any]] = {
    "genes_variants_diseases": {
        "description": "Extract genes, variants, and diseases",
        "entities": [
            {
                "name": "genes",
                "type": "list",
                "fields": ["gene_symbol", "full_name", "normalized_id", "context"],
            },
            {
                "name": "variants",
                "type": "list",
                "fields": ["hgvs", "gene", "significance", "context"],
            },
            {
                "name": "diseases",
                "type": "list",
                "fields": ["disease_name", "mondo_id", "context"],
            },
        ],
    },
    "drugs_targets": {
        "description": "Extract drug-target relationships",
        "entities": [
            {
                "name": "drugs",
                "type": "list",
                "fields": ["drug_name", "drug_class", "mechanism", "context"],
            },
            {
                "name": "targets",
                "type": "list",
                "fields": ["target_gene", "target_protein", "context"],
            },
            {
                "name": "relationships",
                "type": "list",
                "fields": ["drug", "target", "relationship_type", "evidence", "context"],
            },
        ],
    },
    "clinical_trial": {
        "description": "Extract clinical trial details",
        "entities": [
            {"name": "trial_id", "type": "string"},
            {"name": "phase", "type": "string"},
            {"name": "interventions", "type": "list", "fields": ["type", "name", "context"]},
            {"name": "conditions", "type": "list", "fields": ["condition", "context"]},
            {"name": "endpoints", "type": "list", "fields": ["endpoint_type", "description", "context"]},
            {"name": "patient_count", "type": "integer"},
        ],
    },
    "pathway_interactions": {
        "description": "Extract pathway and interaction information",
        "entities": [
            {
                "name": "pathways",
                "type": "list",
                "fields": ["pathway_name", "source_database", "context"],
            },
            {
                "name": "interactions",
                "type": "list",
                "fields": ["entity_a", "entity_b", "interaction_type", "confidence", "context"],
            },
        ],
    },
}


def _read_data_extraction_text(input_text: Any, input_file: Any) -> str:
    file_value = str(input_file or "").strip()
    if file_value:
        path = Path(file_value)
        if not path.exists():
            raise FileNotFoundError(f"Data extraction input file not found: {path}")
        return path.read_text(encoding="utf-8-sig")
    return str(input_text or "")


def _data_extraction_source_text_length(text: str) -> int:
    return len(text) + 2 if text else 0


def _parse_custom_entities(value: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for line in value.splitlines():
        text = line.strip()
        if not text:
            continue
        if ":" in text:
            name, description = text.split(":", 1)
        else:
            name, description = text, ""
        name = name.strip()
        if name:
            entities.append({"name": name, "description": description.strip()})
    return entities


def _data_extraction_schema(schema_name: str, custom_entities: list[dict[str, str]]) -> dict[str, Any]:
    if schema_name == "custom":
        entities = [
            {
                "name": entity["name"],
                "type": "list",
                "fields": ["value", "context"],
                "description": entity.get("description", ""),
            }
            for entity in custom_entities
        ]
        return {"description": "Custom entity extraction", "entities": entities}
    return _EXTRACTION_SCHEMAS.get(schema_name, _EXTRACTION_SCHEMAS["genes_variants_diseases"])


def _data_extraction_prompt(
    *,
    text: str,
    extraction_schema: str,
    custom_entities: list[dict[str, str]],
    include_context: bool,
    normalize_ids: bool,
) -> str:
    schema = _data_extraction_schema(extraction_schema, custom_entities)
    entity_lines = []
    for entity in schema.get("entities", []):
        name = str(entity.get("name", "entity")).strip()
        entity_type = str(entity.get("type", "list")).strip()
        if entity_type == "list":
            fields = ", ".join(str(field) for field in entity.get("fields", ["value"]))
            description = str(entity.get("description", "") or "").strip()
            suffix = f" ({description})" if description else ""
            entity_lines.append(f"- {name}: list of objects with fields {fields}{suffix}")
        else:
            entity_lines.append(f"- {name}: {entity_type}")

    instructions = [
        f"Extraction schema: {extraction_schema}",
        str(schema.get("description", "") or "").strip(),
        "Extract the following entities from the text below:",
        "\n".join(entity_lines),
    ]
    if include_context:
        instructions.append("Include the surrounding text context for each extracted entity.")
    if normalize_ids:
        instructions.append(
            "Add normalized database IDs where possible, such as HGNC for genes, ClinVar for variants, "
            "MONDO for diseases, and ChEMBL or DrugBank for drugs."
        )
    instructions.extend(
        [
            "Return a JSON object with a top-level key for each entity type.",
            "Use empty arrays or empty strings when no entity of that type is found.",
            f"Text:\n{text}",
        ]
    )
    return "\n\n".join(part for part in instructions if part)


def _write_extraction_csv(path: Path, entities: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["entity_type", "field", "value", "context"])
        for row in _flatten_extraction_rows(entities):
            writer.writerow(row)


def _flatten_extraction_rows(entities: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for entity_type, entity_value in entities.items():
        if isinstance(entity_value, list):
            for item in entity_value:
                if isinstance(item, dict):
                    context = str(item.get("context", "") or "")
                    for field, value in item.items():
                        if field == "context" or value in (None, ""):
                            continue
                        rows.append([str(entity_type), str(field), _csv_value(value), context])
                elif item not in (None, ""):
                    rows.append([str(entity_type), "value", _csv_value(item), ""])
        elif isinstance(entity_value, dict):
            context = str(entity_value.get("context", "") or "")
            for field, value in entity_value.items():
                if field == "context" or value in (None, ""):
                    continue
                rows.append([str(entity_type), str(field), _csv_value(value), context])
        elif entity_value not in (None, ""):
            rows.append([str(entity_type), "value", _csv_value(entity_value), ""])
    return rows


def _csv_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)
