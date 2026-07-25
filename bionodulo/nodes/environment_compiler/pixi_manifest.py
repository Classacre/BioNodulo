"""Selected direct-dependency projection from exact Pixi manifest bytes."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterable
from types import MappingProxyType
from typing import Mapping

from packaging.utils import canonicalize_name

from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.environment_compiler import pixi_specs


_MAX_PIXI_TOML_BYTES = 1024 * 1024
_CONDA_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValueError(f"{label} must be a string-keyed TOML table")
    return value


def _dependency_table(value: object, *, label: str) -> dict[str, object]:
    table = _mapping(value, label=label)
    for name, spec in table.items():
        if not name or len(name) > 128 or type(spec) not in (str, dict):
            raise ValueError(f"{label} must contain bounded dependency specifications")
    return table


def _text(value: object, *, label: str, maximum: int = 4096) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise ValueError(f"{label} must be a nonempty string of at most {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} must not contain control characters")
    return value


def _string_list(value: object, *, label: str) -> tuple[str, ...]:
    if type(value) is not list or len(value) > 256:
        raise ValueError(f"{label} must be a bounded string array")
    return tuple(_text(item, label=f"{label} item", maximum=128) for item in value)


def _selected_features(
    document: dict[str, object],
    *,
    environment_name: str,
) -> tuple[dict[str, object], ...]:
    feature_tables = _mapping(document.get("feature", {}), label="pixi.toml feature")
    environments_value = document.get("environments")
    if environments_value is None:
        if environment_name != "default":
            raise ValueError(f"pixi.toml does not define environment {environment_name!r}")
        feature_names: tuple[str, ...] = ()
        no_default_feature = False
    else:
        environments = _mapping(environments_value, label="pixi.toml environments")
        if environment_name not in environments:
            if environment_name != "default":
                raise ValueError(f"pixi.toml does not define environment {environment_name!r}")
            feature_names = ()
            no_default_feature = False
        else:
            selected = environments[environment_name]
            if type(selected) is list:
                feature_names = _string_list(selected, label=f"environment {environment_name} features")
                no_default_feature = False
            else:
                environment = _mapping(selected, label=f"environment {environment_name}")
                unknown = tuple(
                    key for key in environment if key not in ("features", "solve-group", "no-default-feature")
                )
                if unknown:
                    raise ValueError(f"environment {environment_name} contains unknown fields: {', '.join(unknown)}")
                feature_names = _string_list(
                    environment.get("features", []),
                    label=f"environment {environment_name} features",
                )
                no_default_feature_value = environment.get("no-default-feature", False)
                if type(no_default_feature_value) is not bool:
                    raise ValueError(f"environment {environment_name} no-default-feature must be a boolean")
                no_default_feature = no_default_feature_value
    selected_features: list[dict[str, object]] = []
    for name in feature_names:
        if name not in feature_tables:
            raise ValueError(f"environment {environment_name} selects unknown feature {name!r}")
        selected_features.append(_mapping(feature_tables[name], label=f"feature {name}"))
    if not no_default_feature:
        selected_features.append(document)
    return tuple(selected_features)


def _target_matches(selector: str, *, resolver_platform: str) -> bool:
    if selector == resolver_platform:
        return True
    if resolver_platform.startswith("linux-"):
        return selector in ("linux", "unix")
    return False


def _target_views(feature: dict[str, object], *, resolver_platform: str) -> tuple[dict[str, object], ...]:
    views: list[dict[str, object]] = [feature]
    targets_value = feature.get("target")
    if targets_value is None:
        return tuple(views)
    targets = _mapping(targets_value, label="pixi.toml target")
    for selector, raw_target in targets.items():
        _text(selector, label="pixi.toml target selector", maximum=32)
        target = _mapping(raw_target, label=f"pixi.toml target {selector}")
        if _target_matches(selector, resolver_platform=resolver_platform):
            views.append(target)
    return tuple(views)


def _resolved_table(
    feature: dict[str, object],
    *,
    field: str,
    resolver_platform: str,
) -> dict[str, object]:
    resolved: dict[str, object] = {}
    for target in _target_views(feature, resolver_platform=resolver_platform):
        if field in target:
            resolved.update(_dependency_table(target[field], label=f"pixi.toml {field}"))
    return resolved


def _pypi_name(value: str, *, label: str) -> str:
    name = _text(value, label=label, maximum=128)
    normalized = canonicalize_name(name)
    if not normalized:
        raise ValueError(f"{label} must be a valid PyPI package name")
    return normalized.replace("-", "_")


def _resolved_pypi(feature: dict[str, object], *, resolver_platform: str) -> dict[str, object]:
    resolved: dict[str, object] = {}
    for target in _target_views(feature, resolver_platform=resolver_platform):
        if "pypi-dependencies" not in target:
            continue
        dependencies = _dependency_table(target["pypi-dependencies"], label="pixi.toml pypi-dependencies")
        for name, spec in dependencies.items():
            resolved[_pypi_name(name, label=f"PyPI dependency {name}")] = spec
    return resolved


def _conda_name(value: str, *, label: str) -> tuple[str, str]:
    name = _text(value, label=label, maximum=128)
    if _CONDA_NAME.fullmatch(name) is None:
        raise ValueError(f"{label} contains invalid Conda package-name characters")
    return name.lower(), name


def _extend_unique(
    target: dict[str, list[pixi_specs._RenderedSpec]],
    values: Iterable[tuple[str, pixi_specs._RenderedSpec]],
) -> None:
    for name, spec in values:
        specs = target.setdefault(name, [])
        if all(existing.identity != spec.identity for existing in specs):
            specs.append(spec)


def _extend_conda_unique(
    target: dict[str, tuple[str, list[pixi_specs._RenderedSpec]]],
    values: Iterable[tuple[str, pixi_specs._RenderedSpec]],
) -> None:
    for raw_name, spec in values:
        normalized, source_name = _conda_name(raw_name, label=f"Conda dependency {raw_name}")
        if normalized not in target:
            target[normalized] = (source_name, [spec])
        elif all(existing.identity != spec.identity for existing in target[normalized][1]):
            target[normalized][1].append(spec)


def _overwrite_conda(
    target: dict[str, tuple[str, pixi_specs._RenderedSpec]],
    values: Iterable[tuple[str, pixi_specs._RenderedSpec]],
) -> None:
    for raw_name, spec in values:
        normalized, source_name = _conda_name(raw_name, label=f"Conda dependency {raw_name}")
        first_source = target.get(normalized, (source_name, spec))[0]
        target[normalized] = (first_source, spec)


def _derive_requested_specs(
    content: bytes,
    *,
    environment_name: str,
    target_platform: ExecutionPlatform,
) -> Mapping[str, str]:
    """Return Pixi list's selected requested-spec map.

    Source: Pixi 0.68.1 commit a2453cacd4a02bc99ee84b5e6015ec83bbb2d397,
    crates/pixi_api/src/workspace/list/mod.rs:115-135 and
    crates/pixi_core/src/workspace/environment.rs:397-412.
    """

    if type(content) is not bytes:
        raise TypeError("pixi.toml content must be exact bytes")
    if not content or len(content) > _MAX_PIXI_TOML_BYTES:
        raise ValueError(f"pixi.toml size must be between 1 and {_MAX_PIXI_TOML_BYTES} bytes")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("pixi.toml must be UTF-8") from error
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"pixi.toml is malformed: {error}") from error
    resolver_platform = "linux-64" if target_platform is ExecutionPlatform.LINUX_AMD64 else "linux-aarch64"
    conda_specs: dict[str, tuple[str, list[pixi_specs._RenderedSpec]]] = {}
    pypi_specs: dict[str, list[pixi_specs._RenderedSpec]] = {}
    for feature in _selected_features(document, environment_name=environment_name):
        platforms_value = feature.get("platforms")
        if platforms_value is not None and resolver_platform not in _string_list(
            platforms_value,
            label="feature platforms",
        ):
            continue
        combined_conda: dict[str, tuple[str, pixi_specs._RenderedSpec]] = {}
        for target in _target_views(feature, resolver_platform=resolver_platform):
            target_conda: dict[str, tuple[str, pixi_specs._RenderedSpec]] = {}
            for field in ("dependencies", "host-dependencies", "build-dependencies"):
                if field not in target:
                    continue
                field_values = _dependency_table(target[field], label=f"pixi.toml {field}")
                _overwrite_conda(
                    target_conda,
                    (
                        (name, pixi_specs._render_conda_spec(spec, label=f"Conda dependency {name}"))
                        for name, spec in field_values.items()
                    ),
                )
            _overwrite_conda(combined_conda, target_conda.values())
        _extend_conda_unique(
            conda_specs,
            combined_conda.values(),
        )
        _extend_unique(
            pypi_specs,
            (
                (
                    name,
                    pixi_specs._render_pypi_spec(spec, label=f"PyPI dependency {name}"),
                )
                for name, spec in _resolved_pypi(feature, resolver_platform=resolver_platform).items()
            ),
        )
    requested = {source_name: ", ".join(spec.display for spec in specs) for source_name, specs in conda_specs.values()}
    requested.update({name: specs[0].display for name, specs in pypi_specs.items()})
    return MappingProxyType(requested)
