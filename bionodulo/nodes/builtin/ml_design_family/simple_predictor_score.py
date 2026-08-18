"""Apply a trained simple-predictor model JSON to a feature table."""

from __future__ import annotations

from typing import Any

from .adapter import (
    MLDesignNode,
    existing_file,
    load_json_mapping,
    node_output_dir,
    path_probe_is_file,
    read_table,
    write_json_file,
    write_tsv_file,
)


class SimplePredictorScoreNode(MLDesignNode):
    """Score a feature table with a saved simple_predictor_train model."""

    NODE_ID = "simple_predictor_score"
    DISPLAY_NAME = "Simple Predictor Score"
    DESCRIPTION = (
        "Load a model JSON written by simple_predictor_train and score a headered "
        "feature table, writing per-row predictions as TSV and JSON. Use it to fold a "
        "learned evaluator back into the mRNA design loop's multi_objective_scorer. "
        "An EMPTY 'model' input is not an error: the node writes a header-only "
        "predictions TSV and an empty predictions JSON so shared evaluator subgraphs "
        "can leave the learned member untrained (multi_objective_scorer skips empty "
        "score tables fail-soft)."
    )
    SEARCH_ALIASES = [
        "predict",
        "inference",
        "scoring",
        "regression",
        "machine learning",
        "model apply",
    ]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("predictions", "predictions_json")
    REQUIRED_CONDA_PACKAGES = ["numpy"]
    DOCUMENTATION_URL = "https://numpy.org/doc/stable/user/basics.io.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "model": ("JSON", {"description": "Model JSON from simple_predictor_train"}),
                "feature_table": ("FILE", {"description": "Headered CSV/TSV with the id column and model features"}),
            },
            "optional": {
                "id_column": ("STRING", {"default": "", "description": "Id column override; defaults to the training id column"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        model = str(inputs.get("model", "") or "").strip()
        if model and not path_probe_is_file(model) and not model.startswith("{"):
            return "Input 'model' must be a model JSON path or inline JSON"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        import numpy as np

        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        output_dir = node_output_dir(self, context)
        tsv_path = output_dir / "predictions.tsv"
        json_path = output_dir / "predictions.json"

        if not str(kwargs.get("model", "") or "").strip():
            write_tsv_file(tsv_path, ["id", "prediction"], [])
            write_json_file(json_path, {"model": None, "predictions": []})
            return (str(tsv_path), str(json_path))

        model_payload = load_json_mapping(kwargs["model"], "model")
        if model_payload is None:
            raise ValueError("Input 'model' is required")
        model_type = model_payload.get("model")
        feature_names = model_payload.get("feature_names")
        if model_type not in ("ridge", "boosted_stumps") or not isinstance(feature_names, list) or not feature_names:
            raise ValueError("Input 'model' is not a simple_predictor_train model JSON")

        table = existing_file(kwargs["feature_table"], "feature_table")
        fieldnames, rows = read_table(table)
        id_column = str(kwargs.get("id_column", "") or model_payload.get("id_column", "id") or "id").strip()
        if id_column not in fieldnames:
            raise ValueError(f"Input 'feature_table' header must contain a '{id_column}' column")
        missing = [name for name in feature_names if name not in fieldnames]
        if missing:
            raise ValueError(
                f"Input 'feature_table' is missing {len(missing)} model feature column(s): {', '.join(missing[:10])}"
            )

        records: list[dict[str, Any]] = []
        matrix_rows: list[list[float]] = []
        for row in rows:
            identifier = row[id_column].strip()
            if not identifier:
                raise ValueError("Input 'feature_table' contains an empty id value")
            values: list[float] = []
            for column in feature_names:
                raw = str(row[column]).strip()
                try:
                    values.append(float(raw))
                except ValueError as exc:
                    raise ValueError(
                        f"Input 'feature_table' feature column '{column}' has a non-numeric value "
                        f"for id {identifier}: {raw!r}"
                    ) from exc
            records.append({"id": identifier})
            matrix_rows.append(values)
        x = np.asarray(matrix_rows, dtype=np.float64)
        predictions = self._apply(np, model_payload, x)
        for record, prediction in zip(records, predictions, strict=True):
            record["prediction"] = float(prediction)

        write_tsv_file(tsv_path, ["id", "prediction"], records)
        write_json_file(json_path, {"model": model_type, "predictions": records})
        return (str(tsv_path), str(json_path))

    @staticmethod
    def _apply(np: Any, model_payload: dict[str, Any], x: Any) -> Any:
        if model_payload["model"] == "ridge":
            standardized = (x - np.asarray(model_payload["means"])) / np.asarray(model_payload["scales"])
            return standardized @ np.asarray(model_payload["weights"]) + model_payload["bias"]
        prediction = np.full(x.shape[0], model_payload["base"])
        for stump in model_payload["stumps"]:
            column = x[:, stump["feature_index"]]
            prediction = prediction + np.where(
                column <= stump["threshold"], stump["left_value"], stump["right_value"]
            )
        return prediction
