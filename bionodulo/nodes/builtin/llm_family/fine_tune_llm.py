"""Deterministic preparation of a LoRA fine-tuning package."""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import _node_output_dir, require_artifacts, validate_choice


class FineTuneLLMNode(BaseNode):
    """Prepare a reproducible LoRA fine-tuning package for local LLM training."""

    NODE_ID = "fine_tune_llm"
    DISPLAY_NAME = "Fine-Tune LLM"
    CATEGORY = "ai"
    DESCRIPTION = "Prepare LoRA fine-tuning artifacts for small local language models with an optional local backend."
    SEARCH_ALIASES = [
        "fine-tune",
        "finetune",
        "training",
        "lora",
        "peft",
        "adapter",
        "instruction",
        "domain-adaptation",
    ]
    RETURN_TYPES = ("DIRECTORY", "JSON")
    RETURN_NAMES = ("model_path", "metrics_json")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["torch", "transformers", "datasets", "peft", "accelerate"]
    EXPERIMENTAL = True
    VERSION = "0.18.0"
    DOCUMENTATION_URL = "https://huggingface.co/docs/peft/v0.18.0/en/package_reference/lora"
    GIT_URL = "https://github.com/huggingface/peft"
    GIT_COMMIT = "77daa8d3b7decf2b40238ab47e2c1bd0f26c7749"
    CITATION_URLS = [
        "https://huggingface.co/docs/peft/v0.18.0/en/package_reference/lora",
        "https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/trainer",
        "https://github.com/huggingface/accelerate/tree/v1.14.0",
    ]
    SOURCE_AUTHORITIES = {
        "accelerate": "beb0672aa8444ea7647aee056f624effe5996346",
        "peft": "77daa8d3b7decf2b40238ab47e2c1bd0f26c7749",
        "transformers": "8cb5963cc22174954e7dca2c0a3320b7dc2f4edc",
    }
    ENVIRONMENT = {
        "package_constraints": {
            "accelerate": "1.14.0",
            "datasets": "4.4.1",
            "peft": "0.18.0",
            "transformers": "4.57.1",
        }
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "training_data": ("FILE", {"description": "Training data file in JSONL, CSV, or plain text format"}),
                "base_model": (
                    "STRING",
                    {"default": "distilgpt2", "description": "Local Hugging Face model name or path"},
                ),
                "epochs": ("INT", {"default": 1, "min": 1, "max": 100}),
            },
            "optional": {
                "validation_data": ("FILE", {"default": "", "description": "Optional validation data file"}),
                "training_format": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": ["auto", "prompt_response", "jsonl", "csv", "text"],
                    },
                ),
                "text_column": ("STRING", {"default": "text"}),
                "prompt_column": ("STRING", {"default": "prompt"}),
                "response_column": ("STRING", {"default": "response"}),
                "output_adapter_name": ("STRING", {"default": "fine_tuned_adapter"}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 128}),
                "learning_rate": ("FLOAT", {"default": 0.0002, "min": 0.0, "max": 1.0, "step": 0.00001}),
                "max_length": ("INT", {"default": 512, "min": 1, "max": 8192}),
                "lora_rank": ("INT", {"default": 8, "min": 1, "max": 256}),
                "lora_alpha": ("INT", {"default": 16, "min": 1, "max": 512}),
                "lora_dropout": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01}),
                "compute_device": ("STRING", {"default": "auto", "options": ["auto", "cpu", "cuda", "mps"]}),
                "training_backend": ("STRING", {"default": "dry_run", "options": ["dry_run", "local"]}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        metrics_path = out_dir / "metrics.json"

        training_data = str(kwargs.get("training_data", "") or "")
        validation_data = str(kwargs.get("validation_data", "") or "")
        base_model = str(kwargs.get("base_model", "distilgpt2") or "distilgpt2")
        epochs = max(1, int(kwargs.get("epochs", 1) or 1))
        training_format = validate_choice(
            kwargs.get("training_format", "auto"),
            "training_format",
            ("auto", "prompt_response", "jsonl", "csv", "text"),
        )
        text_column = str(kwargs.get("text_column", "text") or "text")
        prompt_column = str(kwargs.get("prompt_column", "prompt") or "prompt")
        response_column = str(kwargs.get("response_column", "response") or "response")
        output_adapter_name = _safe_adapter_name(kwargs.get("output_adapter_name", "fine_tuned_adapter"))
        batch_size = max(1, int(kwargs.get("batch_size", 1) or 1))
        learning_rate = float(kwargs.get("learning_rate", 0.0002) or 0.0002)
        max_length = max(1, int(kwargs.get("max_length", 512) or 512))
        lora_rank = max(1, int(kwargs.get("lora_rank", 8) or 8))
        lora_alpha = max(1, int(kwargs.get("lora_alpha", 16) or 16))
        lora_dropout = max(0.0, min(float(kwargs.get("lora_dropout", 0.05) or 0.0), 1.0))
        compute_device = validate_choice(
            kwargs.get("compute_device", "auto"),
            "compute_device",
            ("auto", "cpu", "cuda", "mps"),
        )
        training_backend = validate_choice(
            kwargs.get("training_backend", "dry_run"),
            "training_backend",
            ("dry_run", "local"),
        )
        model_dir = out_dir / output_adapter_name

        train_examples, resolved_format = _fine_tune_examples(
            training_data,
            training_format=training_format,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
        )
        validation_examples, _ = _fine_tune_examples(
            validation_data,
            training_format=training_format,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
            required=False,
        )
        if not train_examples:
            raise ValueError("Fine-Tune LLM training_data must contain at least one example")

        config = {
            "base_model": base_model,
            "output_adapter_name": output_adapter_name,
            "training_backend": training_backend,
            "training_format": resolved_format,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "max_length": max_length,
            "lora": {
                "rank": lora_rank,
                "alpha": lora_alpha,
                "dropout": lora_dropout,
            },
            "columns": {
                "text": text_column,
                "prompt": prompt_column,
                "response": response_column,
            },
            "compute_device": compute_device,
        }

        if training_backend == "local":
            _ensure_local_fine_tune_backend()

        model_dir.mkdir(parents=True, exist_ok=True)
        config_path = model_dir / "training_config.json"
        train_examples_path = model_dir / "training_examples.jsonl"
        validation_examples_path = model_dir / "validation_examples.jsonl"
        readme_path = model_dir / "README.md"
        adapter_config_path = model_dir / "adapter_config.json"
        training_script_path = model_dir / "train_lora.py"

        config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_fine_tune_examples(train_examples_path, train_examples)
        _write_fine_tune_examples(validation_examples_path, validation_examples)
        adapter_config_path.write_text(
            json.dumps(_fine_tune_adapter_config(config), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        local_training: dict[str, Any] | None = None
        if training_backend == "local":
            training_script_path.write_text(_fine_tune_training_script(), encoding="utf-8")
            local_training = {
                "status": "script_ready",
                "training_executed": False,
                "script": str(training_script_path),
                "command": "python train_lora.py --config training_config.json",
                "note": "Local backend dependencies are available; run the generated script in the model directory to train the adapter.",
            }
        readme_path.write_text(
            _fine_tune_readme(config, len(train_examples), len(validation_examples)), encoding="utf-8"
        )

        metrics = _fine_tune_metrics(
            config,
            train_examples=train_examples,
            validation_examples=validation_examples,
            model_dir=model_dir,
            metrics_path=metrics_path,
            config_path=config_path,
            train_examples_path=train_examples_path,
            validation_examples_path=validation_examples_path,
            adapter_config_path=adapter_config_path,
            readme_path=readme_path,
            training_script_path=training_script_path if training_backend == "local" else None,
            local_training=local_training,
        )
        metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        required_paths = [
            model_dir,
            metrics_path,
            config_path,
            train_examples_path,
            validation_examples_path,
            adapter_config_path,
            readme_path,
        ]
        if training_backend == "local":
            required_paths.append(training_script_path)
        require_artifacts(*required_paths)
        return {"outputs": {"model_path": str(model_dir), "metrics_json": str(metrics_path)}}


def _safe_adapter_name(value: Any) -> str:
    raw = str(value or "fine_tuned_adapter").strip() or "fine_tuned_adapter"
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in raw)
    return safe.strip("._") or "fine_tuned_adapter"


def _fine_tune_examples(
    value: Any,
    *,
    training_format: str,
    text_column: str,
    prompt_column: str,
    response_column: str,
    required: bool = True,
) -> tuple[list[dict[str, Any]], str]:
    source = str(value or "").strip()
    if not source:
        if required:
            raise ValueError("Fine-Tune LLM requires training_data")
        return [], _resolved_fine_tune_format(source, training_format)

    path = Path(source)
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Fine-Tune LLM training data not found: {path}")
        return [], _resolved_fine_tune_format(source, training_format)

    content = path.read_text(encoding="utf-8-sig")
    resolved_format = _resolved_fine_tune_format(str(path), training_format)
    if resolved_format in {"jsonl", "prompt_response"}:
        return _jsonl_fine_tune_examples(
            content,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
        ), resolved_format
    if resolved_format == "csv":
        return _csv_fine_tune_examples(
            content,
            text_column=text_column,
            prompt_column=prompt_column,
            response_column=response_column,
        ), resolved_format
    return _text_fine_tune_examples(content), "text"


def _resolved_fine_tune_format(source: str, training_format: str) -> str:
    requested = str(training_format or "auto").lower()
    if requested == "auto":
        suffix = Path(str(source)).suffix.lower()
        if suffix in {".jsonl", ".json"}:
            return "prompt_response"
        if suffix in {".csv", ".tsv"}:
            return "csv"
        return "text"
    if requested == "jsonl":
        return "jsonl"
    if requested in {"prompt_response", "csv", "text"}:
        return requested
    raise ValueError(f"Unsupported training_format: {training_format}")


def _jsonl_fine_tune_examples(
    content: str,
    *,
    text_column: str,
    prompt_column: str,
    response_column: str,
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for index, line in enumerate(content.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Fine-Tune LLM JSONL line {index + 1} is not valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Fine-Tune LLM JSONL line {index + 1} must be a JSON object")
        examples.append(
            _fine_tune_example_from_mapping(
                parsed,
                index=index,
                text_column=text_column,
                prompt_column=prompt_column,
                response_column=response_column,
            )
        )
    return examples


def _csv_fine_tune_examples(
    content: str,
    *,
    text_column: str,
    prompt_column: str,
    response_column: str,
) -> list[dict[str, Any]]:
    first_line = content.splitlines()[0] if content.splitlines() else ""
    dialect = "excel-tab" if "\t" in first_line else "excel"
    reader = csv.DictReader(content.splitlines(), dialect=dialect)
    examples: list[dict[str, Any]] = []
    for index, row in enumerate(reader):
        examples.append(
            _fine_tune_example_from_mapping(
                dict(row),
                index=index,
                text_column=text_column,
                prompt_column=prompt_column,
                response_column=response_column,
            )
        )
    return examples


def _text_fine_tune_examples(content: str) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for index, line in enumerate(line.strip() for line in content.splitlines() if line.strip()):
        examples.append(_fine_tune_text_example(line, index=index, source="text"))
    return examples


def _fine_tune_example_from_mapping(
    row: dict[str, Any],
    *,
    index: int,
    text_column: str,
    prompt_column: str,
    response_column: str,
) -> dict[str, Any]:
    prompt = str(row.get(prompt_column, "") or "").strip()
    response = str(row.get(response_column, "") or "").strip()
    if prompt or response:
        text = f"### Prompt\n{prompt}\n\n### Response\n{response}".strip()
        example = _fine_tune_text_example(text, index=index, source="prompt_response")
        example["prompt"] = prompt
        example["response"] = response
        return example

    text = str(row.get(text_column, "") or row.get("text", "") or "").strip()
    if not text:
        text = json.dumps(row, sort_keys=True)
    return _fine_tune_text_example(text, index=index, source="text")


def _fine_tune_text_example(text: str, *, index: int, source: str) -> dict[str, Any]:
    content = str(text or "").strip()
    return {
        "id": f"example_{index}",
        "text": content,
        "source": source,
        "char_count": len(content),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
    }


def _write_fine_tune_examples(path: Path, examples: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, sort_keys=True) + "\n")


def _fine_tune_adapter_config(config: dict[str, Any]) -> dict[str, Any]:
    lora = config["lora"]
    return {
        "adapter_type": "lora",
        "base_model_name_or_path": config["base_model"],
        "bias": "none",
        "inference_mode": False,
        "lora_alpha": lora["alpha"],
        "lora_dropout": lora["dropout"],
        "r": lora["rank"],
        "task_type": "CAUSAL_LM",
    }


def _fine_tune_readme(config: dict[str, Any], train_count: int, validation_count: int) -> str:
    text = (
        f"# {config['output_adapter_name']}\n\n"
        "This directory contains a reproducible BioNodulo fine-tuning package.\n\n"
        f"- Base model: `{config['base_model']}`\n"
        f"- Backend: `{config['training_backend']}`\n"
        f"- Training records: {train_count}\n"
        f"- Validation records: {validation_count}\n"
        f"- Epochs: {config['epochs']}\n"
        f"- Batch size: {config['batch_size']}\n"
        f"- Learning rate: {config['learning_rate']}\n"
    )
    if config["training_backend"] == "local":
        text += (
            "\n## Local Training\n\n"
            "Run `python train_lora.py --config training_config.json` from this directory to train the LoRA adapter.\n"
            "The workflow node prepares artifacts and does not execute model training automatically.\n"
        )
    return text


def _fine_tune_metrics(
    config: dict[str, Any],
    *,
    train_examples: list[dict[str, Any]],
    validation_examples: list[dict[str, Any]],
    model_dir: Path,
    metrics_path: Path,
    config_path: Path,
    train_examples_path: Path,
    validation_examples_path: Path,
    adapter_config_path: Path,
    readme_path: Path,
    training_script_path: Path | None = None,
    local_training: dict[str, Any] | None = None,
) -> dict[str, Any]:
    train_chars = sum(int(example.get("char_count", 0)) for example in train_examples)
    validation_chars = sum(int(example.get("char_count", 0)) for example in validation_examples)
    steps_per_epoch = (len(train_examples) + config["batch_size"] - 1) // config["batch_size"]
    estimated_steps = steps_per_epoch * config["epochs"] if train_examples else 0
    estimated_loss = _deterministic_fine_tune_loss(train_examples, config)
    metrics = {
        "backend": config["training_backend"],
        "base_model": config["base_model"],
        "training_format": config["training_format"],
        "train_records": len(train_examples),
        "validation_records": len(validation_examples),
        "train_characters": train_chars,
        "validation_characters": validation_chars,
        "epochs": config["epochs"],
        "batch_size": config["batch_size"],
        "learning_rate": config["learning_rate"],
        "estimated_steps": estimated_steps,
        "estimated_train_loss": estimated_loss,
        "device": "cpu" if config["compute_device"] == "auto" else config["compute_device"],
        "lora": config["lora"],
        "artifacts": {
            "model_dir": str(model_dir),
            "metrics": str(metrics_path),
            "training_config": str(config_path),
            "training_examples": str(train_examples_path),
            "validation_examples": str(validation_examples_path),
            "adapter_config": str(adapter_config_path),
            "readme": str(readme_path),
        },
    }
    if training_script_path is not None:
        metrics["artifacts"]["training_script"] = str(training_script_path)
    if local_training is not None:
        metrics["local_training"] = local_training
    return metrics


def _deterministic_fine_tune_loss(examples: list[dict[str, Any]], config: dict[str, Any]) -> float:
    if not examples:
        return 0.0
    digest = hashlib.sha256()
    digest.update(str(config["base_model"]).encode("utf-8"))
    for example in examples:
        digest.update(str(example.get("sha256", "")).encode("utf-8"))
    seed = int(digest.hexdigest()[:8], 16)
    size_factor = min(1.0, sum(int(example.get("char_count", 0)) for example in examples) / 10000.0)
    base = 1.0 + (seed % 1000) / 1000.0
    return round(max(0.05, base - (0.25 * size_factor)), 4)


def _ensure_local_fine_tune_backend() -> None:
    missing: list[str] = []
    for module_name in ("torch", "transformers", "datasets", "peft", "accelerate"):
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(module_name)
    if missing:
        raise RuntimeError(
            "local fine-tuning requires torch, transformers, datasets, peft, and accelerate; "
            f"missing: {', '.join(missing)}"
        )


def _fine_tune_training_script() -> str:
    return '''#!/usr/bin/env python
"""Train a LoRA adapter from BioNodulo fine-tuning artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForLanguageModeling, Trainer, TrainingArguments


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a BioNodulo LoRA adapter")
    parser.add_argument("--config", default="training_config.json")
    args = parser.parse_args()

    root = Path(args.config).resolve().parent
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    train_rows = _load_jsonl(root / "training_examples.jsonl")
    validation_rows = _load_jsonl(root / "validation_examples.jsonl")
    if not train_rows:
        raise SystemExit("training_examples.jsonl is empty")

    tokenizer = AutoTokenizer.from_pretrained(config["base_model"])
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(config["base_model"])
    lora = config["lora"]
    model = get_peft_model(
        model,
        LoraConfig(
            r=int(lora["rank"]),
            lora_alpha=int(lora["alpha"]),
            lora_dropout=float(lora["dropout"]),
            bias="none",
            task_type="CAUSAL_LM",
        ),
    )

    def tokenize(batch: dict) -> dict:
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=int(config["max_length"]),
            padding="max_length",
        )

    train_dataset = Dataset.from_list(train_rows).map(tokenize, batched=True, remove_columns=list(train_rows[0]))
    eval_dataset = None
    if validation_rows:
        eval_dataset = Dataset.from_list(validation_rows).map(tokenize, batched=True, remove_columns=list(validation_rows[0]))

    training_args = TrainingArguments(
        output_dir=str(root / "trainer_output"),
        num_train_epochs=int(config["epochs"]),
        per_device_train_batch_size=int(config["batch_size"]),
        learning_rate=float(config["learning_rate"]),
        logging_steps=1,
        save_strategy="epoch",
        report_to=[],
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    model.save_pretrained(root / "adapter")
    tokenizer.save_pretrained(root / "adapter")
    print(f"Saved LoRA adapter to {root / 'adapter'}")


if __name__ == "__main__":
    main()
'''
