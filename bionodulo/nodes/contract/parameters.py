import math
import re
from collections.abc import Iterator, Mapping
from enum import StrEnum
from typing import Annotated, Any, Final, Self

from pydantic import (
    AfterValidator,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

from bionodulo.nodes.contract.artifacts import ArtifactId, _StrictFrozenModel


_ENVIRONMENT_VARIABLE_PATTERN = r"^[A-Z_][A-Z0-9_]*$"
_ENVIRONMENT_VARIABLE_RE = re.compile(_ENVIRONMENT_VARIABLE_PATTERN)
# Bounds every later recursive operation, including dump, equality, and hashing.
_MAX_JSON_NESTING: Final = 128


def _require_full_environment_variable_match(value: str) -> str:
    if _ENVIRONMENT_VARIABLE_RE.fullmatch(value) is None:
        raise ValueError(f"must match {_ENVIRONMENT_VARIABLE_PATTERN}")
    return value


_EnvironmentVariable = Annotated[
    str,
    StringConstraints(pattern=_ENVIRONMENT_VARIABLE_PATTERN),
    AfterValidator(_require_full_environment_variable_match),
]


class _FrozenJsonArray(tuple[Any, ...]):
    __slots__ = ()

    def __eq__(self, other: object) -> bool:
        return type(other) is _FrozenJsonArray and _json_values_equal(self, other)

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash(("array", tuple(_json_value_hash(value) for value in self)))


class _FrozenJsonObject(Mapping[str, Any]):
    __slots__ = ("_items",)

    def __init__(self, items: tuple[tuple[str, Any], ...]) -> None:
        object.__setattr__(self, "_items", items)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __getitem__(self, key: str) -> Any:
        for item_key, value in self._items:
            if item_key == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __eq__(self, other: object) -> bool:
        return type(other) is _FrozenJsonObject and _json_values_equal(self, other)

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash(
            (
                "object",
                tuple((key, _json_value_hash(value)) for key, value in self._items),
            )
        )

    def __repr__(self) -> str:
        return repr({key: value for key, value in self._items})


def _freeze_json(
    value: Any,
    *,
    path: str = "$",
    _active_containers: set[int] | None = None,
    _depth: int = 0,
) -> Any:
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite numbers")
        return value
    if type(value) in (list, dict, _FrozenJsonArray, _FrozenJsonObject):
        if _depth >= _MAX_JSON_NESTING:
            raise ValueError(f"{path} exceeds maximum JSON nesting depth of {_MAX_JSON_NESTING}")
        active_containers = set() if _active_containers is None else _active_containers
        container_id = id(value)
        if container_id in active_containers:
            raise ValueError(f"{path} contains a cyclic container")
        active_containers.add(container_id)
        try:
            if type(value) in (list, _FrozenJsonArray):
                return _FrozenJsonArray(
                    _freeze_json(
                        item,
                        path=f"{path}[{index}]",
                        _active_containers=active_containers,
                        _depth=_depth + 1,
                    )
                    for index, item in enumerate(value)
                )
            if type(value) is dict:
                raw_items = value.items()
            else:
                if not hasattr(value, "_items"):
                    raise ValueError(f"{path} object storage must be present")
                raw_items = value._items
                if type(raw_items) not in (list, tuple):
                    raise ValueError(f"{path} object storage must be a list or tuple")
            canonical_items: list[tuple[str, Any]] = []
            seen_keys: set[str] = set()
            for entry in raw_items:
                if type(entry) is not tuple or len(entry) != 2:
                    raise ValueError(f"{path} object entries must be key-value pairs")
                key, item = entry
                if type(key) is not str:
                    raise ValueError(f"{path} object keys must be strings")
                if key in seen_keys:
                    raise ValueError(f"{path} object keys must be unique")
                seen_keys.add(key)
                canonical_items.append(
                    (
                        key,
                        _freeze_json(
                            item,
                            path=f"{path}.{key}",
                            _active_containers=active_containers,
                            _depth=_depth + 1,
                        ),
                    )
                )
            return _FrozenJsonObject(tuple(sorted(canonical_items)))
        finally:
            active_containers.remove(container_id)
    raise ValueError(f"{path} is not an exact JSON value")


def _thaw_json(value: Any) -> Any:
    if type(value) is _FrozenJsonArray:
        return [_thaw_json(item) for item in value]
    if type(value) is _FrozenJsonObject:
        return {key: _thaw_json(item) for key, item in value.items()}
    return value


def _json_values_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        if type(left) in (int, float) and type(right) in (int, float):
            return left == right
        return False
    if type(left) is _FrozenJsonArray:
        return len(left) == len(right) and all(
            _json_values_equal(left_item, right_item) for left_item, right_item in zip(left, right, strict=True)
        )
    if type(left) is _FrozenJsonObject:
        return len(left._items) == len(right._items) and all(
            left_key == right_key and _json_values_equal(left_value, right_value)
            for (left_key, left_value), (right_key, right_value) in zip(
                left._items,
                right._items,
                strict=True,
            )
        )
    return left == right


def _json_value_hash(value: Any) -> int:
    if type(value) is _FrozenJsonArray:
        return hash(value)
    if type(value) is _FrozenJsonObject:
        return hash(value)
    if type(value) in (int, float):
        return hash(("number", value))
    return hash((type(value), value))


def _json_choice_sequences_equal(
    left: tuple[Any, ...] | None,
    right: tuple[Any, ...] | None,
) -> bool:
    if left is None or right is None:
        return left is right
    return len(left) == len(right) and all(
        _json_values_equal(left_item, right_item) for left_item, right_item in zip(left, right, strict=True)
    )


def _json_choice_sequence_hash(value: tuple[Any, ...] | None) -> int:
    if value is None:
        return hash(("choices", None))
    return hash(("choices", tuple(_json_value_hash(choice) for choice in value)))


class ValueKind(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    JSON = "json"


class ParameterSpec(_StrictFrozenModel):
    parameter_id: ArtifactId
    kind: ValueKind
    required: bool = False
    has_default: bool = False
    default: Any = None
    choices: tuple[Any, ...] | None = None
    minimum: int | float | None = None
    maximum: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    description: str = ""

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return False
        for field_name in type(self).model_fields:
            left = getattr(self, field_name)
            right = getattr(other, field_name)
            if field_name == "default":
                if not _json_values_equal(left, right):
                    return False
            elif field_name == "choices":
                if not _json_choice_sequences_equal(left, right):
                    return False
            elif left != right:
                return False
        return True

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        field_hashes: list[tuple[str, int]] = []
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            if field_name == "default":
                value_hash = _json_value_hash(value)
            elif field_name == "choices":
                value_hash = _json_choice_sequence_hash(value)
            else:
                value_hash = hash(value)
            field_hashes.append((field_name, value_hash))
        return hash((type(self), tuple(field_hashes)))

    @field_validator("minimum", "maximum", mode="before")
    @classmethod
    def _require_exact_numeric_bound_input(cls, value: Any) -> Any:
        if value is not None and type(value) not in (int, float):
            raise ValueError("numeric bounds must be exact integers or floats")
        return value

    @field_validator("default", mode="after")
    @classmethod
    def _freeze_default(cls, value: Any) -> Any:
        return _freeze_json(value)

    @field_validator("choices", mode="after")
    @classmethod
    def _freeze_choices(cls, value: tuple[Any, ...] | None) -> tuple[Any, ...] | None:
        if value is None:
            return None
        return tuple(_freeze_json(choice, path=f"choices[{index}]") for index, choice in enumerate(value))

    @field_serializer("default")
    def _serialize_default(self, value: Any) -> Any:
        return _thaw_json(value)

    @field_serializer("choices")
    def _serialize_choices(self, value: tuple[Any, ...] | None) -> tuple[Any, ...] | None:
        if value is None:
            return None
        return tuple(_thaw_json(choice) for choice in value)

    @model_validator(mode="after")
    def _validate_parameter(self) -> Self:
        if self.required and self.has_default:
            raise ValueError("required parameters cannot declare a default")
        if not self.has_default and self.default is not None:
            raise ValueError("default must be null when has_default is false")

        compiled_pattern = self._validate_declared_constraints()
        if self.has_default:
            self._validate_value(self.default, role="default", pattern=compiled_pattern)

        if self.choices is not None:
            if not self.choices:
                raise ValueError("choices must be nonempty when present")
            for index, choice in enumerate(self.choices):
                self._validate_value(
                    choice,
                    role=f"choice at index {index}",
                    pattern=compiled_pattern,
                )
                if any(_json_values_equal(choice, previous) for previous in self.choices[:index]):
                    raise ValueError(f"duplicate choice at index {index}")

            if self.has_default and not any(_json_values_equal(self.default, choice) for choice in self.choices):
                raise ValueError("default must be a member of choices")
        return self

    def _validate_declared_constraints(self) -> re.Pattern[str] | None:
        numeric_fields = (self.minimum, self.maximum)
        string_fields = (self.min_length, self.max_length, self.pattern)
        if self.kind not in (ValueKind.INTEGER, ValueKind.NUMBER) and any(
            value is not None for value in numeric_fields
        ):
            raise ValueError("numeric bounds require integer or number kind")
        if self.kind is not ValueKind.STRING and any(value is not None for value in string_fields):
            raise ValueError("string constraints require string kind")

        if self.kind in (ValueKind.INTEGER, ValueKind.NUMBER):
            for name, bound in (("minimum", self.minimum), ("maximum", self.maximum)):
                if bound is not None:
                    self._validate_numeric_bound(bound, name=name)
            if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
                raise ValueError("minimum must be less than or equal to maximum")

        if self.kind is not ValueKind.STRING:
            return None

        for name, length in (("min_length", self.min_length), ("max_length", self.max_length)):
            if length is not None and (type(length) is not int or length < 0):
                raise ValueError(f"{name} must be a nonnegative exact integer")
        if self.min_length is not None and self.max_length is not None and self.min_length > self.max_length:
            raise ValueError("min_length must be less than or equal to max_length")
        if self.pattern is None:
            return None
        try:
            return re.compile(self.pattern)
        except re.error as error:
            raise ValueError(f"pattern must compile: {error}") from error

    def _validate_numeric_bound(self, bound: int | float, *, name: str) -> None:
        if self.kind is ValueKind.INTEGER:
            if type(bound) is not int:
                raise ValueError(f"{name} must be an exact integer")
            return
        if type(bound) not in (int, float):
            raise ValueError(f"{name} must be an exact number")
        if type(bound) is float and not math.isfinite(bound):
            raise ValueError(f"{name} must be finite")

    def _validate_value(
        self,
        value: Any,
        *,
        role: str,
        pattern: re.Pattern[str] | None,
    ) -> None:
        if self.kind is ValueKind.STRING:
            if type(value) is not str:
                raise ValueError(f"{role} must be an exact string")
            self._validate_string_constraints(value, role=role, pattern=pattern)
            return
        if self.kind is ValueKind.INTEGER:
            if type(value) is not int:
                raise ValueError(f"{role} must be an exact integer")
            self._validate_numeric_constraints(value, role=role)
            return
        if self.kind is ValueKind.NUMBER:
            if type(value) not in (int, float):
                raise ValueError(f"{role} must be an exact number")
            if type(value) is float and not math.isfinite(value):
                raise ValueError(f"{role} must be finite")
            self._validate_numeric_constraints(value, role=role)
            return
        if self.kind is ValueKind.BOOLEAN:
            if type(value) is not bool:
                raise ValueError(f"{role} must be an exact boolean")
            return
        if not _is_frozen_json_value(value):
            raise ValueError(f"{role} must be a JSON value")

    def _validate_numeric_constraints(self, value: int | float, *, role: str) -> None:
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{role} must be greater than or equal to minimum")
        if self.maximum is not None and value > self.maximum:
            raise ValueError(f"{role} must be less than or equal to maximum")

    def _validate_string_constraints(
        self,
        value: str,
        *,
        role: str,
        pattern: re.Pattern[str] | None,
    ) -> None:
        if self.min_length is not None and len(value) < self.min_length:
            raise ValueError(f"{role} must satisfy min_length")
        if self.max_length is not None and len(value) > self.max_length:
            raise ValueError(f"{role} must satisfy max_length")
        if pattern is not None and pattern.search(value) is None:
            raise ValueError(f"{role} must match pattern with re.search semantics")


def _is_frozen_json_value(value: Any) -> bool:
    return value is None or type(value) in (
        bool,
        int,
        float,
        str,
        _FrozenJsonArray,
        _FrozenJsonObject,
    )


class ValuePort(_StrictFrozenModel):
    port_id: ArtifactId
    kind: ValueKind
    required: bool = True
    description: str = ""

    @property
    def connectable(self) -> bool:
        return True


class SecretSpec(_StrictFrozenModel):
    secret_id: ArtifactId
    environment_variable: _EnvironmentVariable
    required: bool
    description: str = ""


__all__ = ["ParameterSpec", "SecretSpec", "ValueKind", "ValuePort"]
