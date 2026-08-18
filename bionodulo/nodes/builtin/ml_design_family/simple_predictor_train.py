"""Deterministic numpy ridge / gradient-boosted-stump regression trainer."""

from __future__ import annotations

from typing import Any

from .adapter import (
    MLDesignNode,
    existing_file,
    node_output_dir,
    read_table,
    spearman,
    validate_choice_input,
    validate_float_input,
    validate_int_input,
    write_json_file,
    write_tsv_file,
)

MODELS = ("ridge", "boosted_stumps")


class SimplePredictorTrainNode(MLDesignNode):
    """Fit a tiny deterministic numpy regressor on a feature table."""

    NODE_ID = "simple_predictor_train"
    DISPLAY_NAME = "Simple Predictor Train"
    DESCRIPTION = (
        "Train a small deterministic regressor (ridge or gradient-boosted stumps, numpy "
        "only) on a headered feature table with an id column and numeric target. Splits "
        "a seeded train/validation fraction, reports train/val R2 and RMSE, and writes "
        "the model JSON plus per-row predictions. Intended for thousands, not millions, "
        "of rows."
    )
    SEARCH_ALIASES = [
        "regression",
        "ridge",
        "boosted stumps",
        "gradient boosting",
        "machine learning",
        "predictor",
        "supervised",
    ]
    RETURN_TYPES = ("JSON", "JSON", "TSV")
    RETURN_NAMES = ("model", "metrics", "predictions")
    REQUIRED_CONDA_PACKAGES = ["numpy"]
    DOCUMENTATION_URL = "https://numpy.org/doc/stable/reference/generated/numpy.linalg.solve.html"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "feature_table": ("FILE", {"description": "Headered CSV/TSV with id, numeric features, and target columns"}),
                "target_column": ("STRING", {"description": "Column predicted by the model"}),
            },
            "optional": {
                "feature_columns": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "description": (
                            "Comma/newline-separated allowlist of numeric feature columns; empty uses "
                            "every non-id, non-target column (all of which must be numeric)"
                        ),
                    },
                ),
                "id_column": ("STRING", {"default": "id"}),
                "model": ("STRING", {"default": "ridge", "options": list(MODELS)}),
                "n_stumps": ("INT", {"default": 50, "min": 1, "max": 200}),
                "learning_rate": ("FLOAT", {"default": 0.1, "min": 0.001, "max": 1.0}),
                "l2": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1000000.0, "description": "Ridge penalty (ridge only)"}),
                "val_fraction": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 0.5}),
                "n_folds": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 100,
                        "description": "Repeated K-fold cross-validation fold count; 0 keeps the single split",
                    },
                ),
                "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("target_column", "")).strip():
            return "Input 'target_column' must be a non-empty column name"
        if not str(inputs.get("id_column", "id") or "id").strip():
            return "Input 'id_column' must be a non-empty column name"
        validation = validate_choice_input(inputs.get("model", "ridge"), "model", MODELS)
        if validation is not True:
            return validation
        for key, default, minimum, maximum in (
            ("n_stumps", 50, 1, 200),
            ("n_folds", 0, 0, 100),
            ("seed", 0, 0, 2147483647),
        ):
            validation = validate_int_input(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        for key, default, minimum, maximum in (
            ("learning_rate", 0.1, 0.001, 1.0),
            ("l2", 1.0, 0.0, 1000000.0),
            ("val_fraction", 0.2, 0.0, 0.5),
        ):
            validation = validate_float_input(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str, str]:
        import numpy as np

        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        table = existing_file(kwargs["feature_table"], "feature_table")
        fieldnames, rows = read_table(table)
        id_column = str(kwargs.get("id_column", "id") or "id").strip()
        target_column = str(kwargs["target_column"]).strip()
        for column in (id_column, target_column):
            if column not in fieldnames:
                raise ValueError(f"Input 'feature_table' header must contain a '{column}' column")
        allowed = [
            token.strip()
            for token in str(kwargs.get("feature_columns", "") or "").replace("\n", ",").split(",")
            if token.strip()
        ]
        feature_columns = [
            name
            for name in fieldnames
            if name not in (id_column, target_column) and (not allowed or name in allowed)
        ]
        if not feature_columns:
            raise ValueError("Input 'feature_table' must contain at least one feature column")

        identifiers: list[str] = []
        matrix_rows: list[list[float]] = []
        targets: list[float] = []
        for row in rows:
            identifier = row[id_column].strip()
            if not identifier:
                raise ValueError("Input 'feature_table' contains an empty id value")
            identifiers.append(identifier)
            values: list[float] = []
            for column in feature_columns:
                raw = str(row[column]).strip()
                try:
                    values.append(float(raw))
                except ValueError as exc:
                    raise ValueError(
                        f"Input 'feature_table' feature column '{column}' has a non-numeric value "
                        f"for id {identifier}: {raw!r}"
                    ) from exc
            try:
                target = float(str(row[target_column]).strip())
            except ValueError as exc:
                raise ValueError(
                    f"Input 'feature_table' target column '{target_column}' has a non-numeric value "
                    f"for id {identifier}: {row[target_column]!r}"
                ) from exc
            matrix_rows.append(values)
            targets.append(target)
        x = np.asarray(matrix_rows, dtype=np.float64)
        y = np.asarray(targets, dtype=np.float64)

        model_type = str(kwargs.get("model", "ridge"))
        val_fraction = float(kwargs.get("val_fraction", 0.2))
        seed = int(kwargs.get("seed", 0))
        n_folds = int(kwargs.get("n_folds", 0))
        rng = np.random.default_rng(seed)
        if n_folds >= 2:
            return await self._run_k_fold(
                np=np,
                context=context,
                kwargs=kwargs,
                identifiers=identifiers,
                x=x,
                y=y,
                feature_columns=feature_columns,
                model_type=model_type,
                n_folds=n_folds,
                seed=seed,
            )
        n_val = int(round(len(y) * val_fraction))
        n_val = min(max(n_val, 0), len(y) - 1) if len(y) > 1 else 0
        permutation = rng.permutation(len(y))
        val_indices = np.sort(permutation[:n_val]) if n_val else np.array([], dtype=int)
        train_indices = np.sort(permutation[n_val:]) if n_val else np.arange(len(y))
        if len(train_indices) < 2:
            raise ValueError("Training split must retain at least two rows; lower val_fraction")

        model_payload = self._fit(
            np,
            model_type,
            x[train_indices],
            y[train_indices],
            feature_columns,
            kwargs,
        )
        train_predictions = self._apply(np, model_payload, x[train_indices])
        val_predictions = self._apply(np, model_payload, x[val_indices]) if n_val else train_predictions

        splits = np.empty(len(y), dtype=object)
        splits[:] = "train"
        if n_val:
            splits[val_indices] = "val"
        predictions = self._apply(np, model_payload, x)
        metrics = {
            "model": model_type,
            "n": int(len(y)),
            "n_train": int(len(train_indices)),
            "n_val": int(n_val),
            "train_r2": self._r2(np, y[train_indices], train_predictions),
            "train_rmse": self._rmse(np, y[train_indices], train_predictions),
            "val_r2": self._r2(np, y[val_indices], val_predictions) if n_val else None,
            "val_rmse": self._rmse(np, y[val_indices], val_predictions) if n_val else None,
        }

        output_dir = node_output_dir(self, context)
        model_path = output_dir / "model.json"
        metrics_path = output_dir / "metrics.json"
        predictions_path = output_dir / "predictions.tsv"
        write_json_file(model_path, model_payload)
        write_json_file(metrics_path, metrics)
        id_name = str(kwargs.get("id_column", "id") or "id").strip()
        write_tsv_file(
            predictions_path,
            [id_name, "target", "prediction", "split"],
            [
                {
                    id_name: identifiers[index],
                    "target": float(y[index]),
                    "prediction": float(predictions[index]),
                    "split": str(splits[index]),
                }
                for index in range(len(y))
            ],
        )
        return (str(model_path), str(metrics_path), str(predictions_path))

    async def _run_k_fold(
        self,
        *,
        np: Any,
        context: Any,
        kwargs: dict[str, Any],
        identifiers: list[str],
        x: Any,
        y: Any,
        feature_columns: list[str],
        model_type: str,
        n_folds: int,
        seed: int,
    ) -> tuple[str, str, str]:
        if n_folds >= len(y):
            raise ValueError(f"Input 'n_folds' must be smaller than the row count ({len(y)})")
        permutation = np.random.default_rng(seed).permutation(len(y))
        fold_index = np.empty(len(y), dtype=int)
        for fold, rows in enumerate(np.array_split(permutation, n_folds)):
            fold_index[rows] = fold

        fold_r2: list[float | None] = []
        fold_rmse: list[float | None] = []
        fold_spearman: list[float | None] = []
        for fold in range(n_folds):
            val_rows = np.where(fold_index == fold)[0]
            train_rows = np.where(fold_index != fold)[0]
            fold_model = self._fit(np, model_type, x[train_rows], y[train_rows], feature_columns, kwargs)
            val_prediction = self._apply(np, fold_model, x[val_rows])
            fold_r2.append(self._r2(np, y[val_rows], val_prediction))
            fold_rmse.append(self._rmse(np, y[val_rows], val_prediction))
            fold_spearman.append(spearman(y[val_rows], val_prediction))

        model_payload = self._fit(np, model_type, x, y, feature_columns, kwargs)
        predictions = self._apply(np, model_payload, x)

        def _summarise(values: list[float | None]) -> tuple[float | None, float | None]:
            usable = [float(value) for value in values if value is not None and np.isfinite(value)]
            if not usable:
                return None, None
            mean = sum(usable) / len(usable)
            variance = sum((value - mean) ** 2 for value in usable) / len(usable)
            return mean, variance**0.5

        r2_mean, r2_std = _summarise(fold_r2)
        rmse_mean, rmse_std = _summarise(fold_rmse)
        spearman_mean, spearman_std = _summarise(fold_spearman)
        metrics = {
            "model": model_type,
            "n": int(len(y)),
            "n_train": int(len(y)),
            "n_val": int(len(y)),
            "n_folds": n_folds,
            "train_r2": self._r2(np, y, predictions),
            "train_rmse": self._rmse(np, y, predictions),
            "val_r2": r2_mean,
            "val_rmse": rmse_mean,
            "val_r2_std": r2_std,
            "val_rmse_std": rmse_std,
            "val_spearman": spearman_mean,
            "val_spearman_std": spearman_std,
            "fold_val_r2": fold_r2,
            "fold_val_rmse": fold_rmse,
            "fold_val_spearman": fold_spearman,
        }

        output_dir = node_output_dir(self, context)
        model_path = output_dir / "model.json"
        metrics_path = output_dir / "metrics.json"
        predictions_path = output_dir / "predictions.tsv"
        write_json_file(model_path, model_payload)
        write_json_file(metrics_path, metrics)
        id_name = str(kwargs.get("id_column", "id") or "id").strip()
        write_tsv_file(
            predictions_path,
            [id_name, "target", "prediction", "split", "fold"],
            [
                {
                    id_name: identifiers[index],
                    "target": float(y[index]),
                    "prediction": float(predictions[index]),
                    "split": "val",
                    "fold": int(fold_index[index]),
                }
                for index in range(len(y))
            ],
        )
        return (str(model_path), str(metrics_path), str(predictions_path))

    def _fit(
        self,
        np: Any,
        model_type: str,
        x: Any,
        y: Any,
        feature_columns: list[str],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        if model_type == "ridge":
            return self._fit_ridge(np, x, y, feature_columns, float(kwargs.get("l2", 1.0)))
        return self._fit_stumps(
            np,
            x,
            y,
            feature_columns,
            int(kwargs.get("n_stumps", 50)),
            float(kwargs.get("learning_rate", 0.1)),
        )

    @staticmethod
    def _fit_ridge(np: Any, x: Any, y: Any, feature_columns: list[str], l2: float) -> dict[str, Any]:
        means = x.mean(axis=0)
        scales = x.std(axis=0)
        scales[scales == 0] = 1.0
        standardized = (x - means) / scales
        design = np.hstack([standardized, np.ones((standardized.shape[0], 1))])
        penalty = np.eye(design.shape[1]) * l2
        penalty[-1, -1] = 0.0
        solution = np.linalg.solve(design.T @ design + penalty, design.T @ y)
        return {
            "model": "ridge",
            "feature_names": feature_columns,
            "means": [float(value) for value in means],
            "scales": [float(value) for value in scales],
            "weights": [float(value) for value in solution[:-1]],
            "bias": float(solution[-1]),
        }

    @staticmethod
    def _fit_stumps(
        np: Any,
        x: Any,
        y: Any,
        feature_columns: list[str],
        n_stumps: int,
        learning_rate: float,
    ) -> dict[str, Any]:
        n_rows, n_features = x.shape
        prediction = np.full(n_rows, float(y.mean()))
        stumps: list[dict[str, Any]] = []
        for _ in range(n_stumps):
            residual = y - prediction
            best: tuple[float, int, float, float, float] | None = None
            for feature_index in range(n_features):
                column = x[:, feature_index]
                quantiles = np.quantile(column, np.linspace(0.05, 0.95, 19))
                for threshold in sorted({float(value) for value in quantiles}):
                    left = column <= threshold
                    n_left = int(left.sum())
                    if n_left == 0 or n_left == n_rows:
                        continue
                    left_value = float(residual[left].mean())
                    right_value = float(residual[~left].mean())
                    error = float(
                        np.square(residual - np.where(left, left_value, right_value)).sum()
                    )
                    candidate = (error, feature_index, threshold, left_value, right_value)
                    if best is None or candidate < best:
                        best = candidate
            if best is None:
                break
            error, feature_index, threshold, left_value, right_value = best
            stumps.append(
                {
                    "feature_index": int(feature_index),
                    "feature_name": feature_columns[feature_index],
                    "threshold": float(threshold),
                    "left_value": float(learning_rate * left_value),
                    "right_value": float(learning_rate * right_value),
                }
            )
            column = x[:, feature_index]
            prediction = prediction + np.where(column <= threshold, learning_rate * left_value, learning_rate * right_value)
        return {
            "model": "boosted_stumps",
            "feature_names": feature_columns,
            "base": float(y.mean()),
            "stumps": stumps,
        }

    @staticmethod
    def _apply(np: Any, model_payload: dict[str, Any], x: Any) -> Any:
        if model_payload["model"] == "ridge":
            standardized = (x - np.asarray(model_payload["means"])) / np.asarray(model_payload["scales"])
            return standardized @ np.asarray(model_payload["weights"]) + model_payload["bias"]
        prediction = np.full(x.shape[0], model_payload["base"])
        for stump in model_payload["stumps"]:
            column = x[:, stump["feature_index"]]
            prediction = prediction + np.where(column <= stump["threshold"], stump["left_value"], stump["right_value"])
        return prediction

    @staticmethod
    def _r2(np: Any, y: Any, predictions: Any) -> float | None:
        if len(y) == 0:
            return None
        total = float(np.square(y - y.mean()).sum())
        residual = float(np.square(y - predictions).sum())
        if total == 0:
            return 0.0 if residual == 0 else float("-inf")
        return 1.0 - residual / total

    @staticmethod
    def _rmse(np: Any, y: Any, predictions: Any) -> float | None:
        if len(y) == 0:
            return None
        return float(np.sqrt(np.square(y - predictions).mean()))
