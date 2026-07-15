import json
from collections.abc import Mapping, Sequence
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bionodulo.nodes.contract.parameters import (
    ParameterSpec,
    SecretSpec,
    ValueKind,
    ValuePort,
    _FrozenJsonArray,
    _FrozenJsonObject,
)


def parameter(kind: ValueKind, **updates: object) -> ParameterSpec:
    values: dict[str, object] = {
        "parameter_id": "parameter",
        "kind": kind,
    }
    values.update(updates)
    return ParameterSpec(**values)


def assert_no_mutable_json(value: object) -> None:
    assert not isinstance(value, (dict, list))
    if isinstance(value, Mapping):
        for key, nested in value.items():
            assert type(key) is str
            assert_no_mutable_json(nested)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for nested in value:
            assert_no_mutable_json(nested)


def test_value_kind_wire_values_are_exact() -> None:
    assert tuple(ValueKind) == (
        ValueKind.STRING,
        ValueKind.INTEGER,
        ValueKind.NUMBER,
        ValueKind.BOOLEAN,
        ValueKind.JSON,
    )
    assert tuple(kind.value for kind in ValueKind) == (
        "string",
        "integer",
        "number",
        "boolean",
        "json",
    )


@pytest.mark.parametrize(
    ("kind", "default"),
    (
        (ValueKind.STRING, ""),
        (ValueKind.INTEGER, 0),
        (ValueKind.NUMBER, 1.5),
        (ValueKind.BOOLEAN, False),
        (ValueKind.JSON, {"items": [None, True, 1, 1.5, "value"]}),
    ),
)
def test_parameter_accepts_each_value_kind_and_roundtrips_json(
    kind: ValueKind,
    default: object,
) -> None:
    spec = parameter(kind, has_default=True, default=default)
    payload = spec.model_dump_json()

    assert spec.kind is kind
    assert json.loads(payload)["kind"] == kind.value
    assert ParameterSpec.model_validate_json(payload) == spec


def test_parameter_dump_contains_only_declared_state_and_plain_json_shapes() -> None:
    spec = ParameterSpec(
        parameter_id="request.body",
        kind=ValueKind.JSON,
        has_default=True,
        default={"z": [1, {"ok": True}], "a": None},
        choices=({"z": [1, {"ok": True}], "a": None},),
        description="Request body",
    )

    dumped = spec.model_dump()

    assert tuple(dumped) == (
        "parameter_id",
        "kind",
        "required",
        "has_default",
        "default",
        "choices",
        "minimum",
        "maximum",
        "min_length",
        "max_length",
        "pattern",
        "description",
    )
    assert dumped == {
        "parameter_id": "request.body",
        "kind": ValueKind.JSON,
        "required": False,
        "has_default": True,
        "default": {"a": None, "z": [1, {"ok": True}]},
        "choices": ({"a": None, "z": [1, {"ok": True}]},),
        "minimum": None,
        "maximum": None,
        "min_length": None,
        "max_length": None,
        "pattern": None,
        "description": "Request body",
    }
    assert json.loads(spec.model_dump_json())["default"] == {
        "a": None,
        "z": [1, {"ok": True}],
    }


@pytest.mark.parametrize("model", (ParameterSpec, ValuePort, SecretSpec))
def test_parameter_contract_models_share_the_strict_frozen_config(model: type) -> None:
    assert model.model_config["extra"] == "forbid"
    assert model.model_config["frozen"] is True
    assert model.model_config["strict"] is True
    assert model.model_config["validate_default"] is True
    assert model.model_config["revalidate_instances"] == "always"


def test_parameter_rejects_extras_and_mutation() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        parameter(ValueKind.STRING, unexpected=True)

    spec = parameter(ValueKind.STRING)
    with pytest.raises(ValidationError, match="frozen_instance"):
        spec.parameter_id = "replacement"


@pytest.mark.parametrize(
    "update",
    (
        {"parameter_id": "BAD"},
        {"kind": "string"},
        {"required": 1},
        {"has_default": True, "default": 1},
        {"choices": ["one"]},
        {"unexpected": True},
    ),
)
def test_parameter_copy_revalidates_updates(update: dict[str, object]) -> None:
    spec = parameter(ValueKind.STRING)

    with pytest.raises(ValidationError):
        spec.model_copy(update=update)


def test_parameter_copy_preserves_subclasses_and_frozen_json() -> None:
    class SpecializedParameter(ParameterSpec):
        label: str

    spec = SpecializedParameter(
        parameter_id="request.body",
        kind=ValueKind.JSON,
        has_default=True,
        default={"items": [1, 2]},
        label="Body",
    )

    copied = spec.model_copy(update={"label": "JSON body"}, deep=True)

    assert isinstance(copied, SpecializedParameter)
    assert copied.label == "JSON body"
    assert copied == copied.model_copy()
    assert hash(copied) == hash(copied.model_copy())
    assert_no_mutable_json(copied.default)


def test_constructed_parameter_is_revalidated_by_validation_and_copy() -> None:
    invalid = ParameterSpec.model_construct(
        parameter_id="BAD",
        kind=ValueKind.INTEGER,
        required=False,
        has_default=True,
        default=True,
        choices=None,
        minimum=None,
        maximum=None,
        min_length=None,
        max_length=None,
        pattern=None,
        description="",
    )

    with pytest.raises(ValidationError):
        ParameterSpec.model_validate(invalid)
    with pytest.raises(ValidationError):
        invalid.model_copy()


@pytest.mark.parametrize("contract_id", ("a", "api_key", "input.value-1", "value_2.test"))
@pytest.mark.parametrize(
    "model_factory",
    (
        lambda contract_id: ParameterSpec(parameter_id=contract_id, kind=ValueKind.STRING),
        lambda contract_id: ValuePort(port_id=contract_id, kind=ValueKind.STRING),
        lambda contract_id: SecretSpec(
            secret_id=contract_id,
            environment_variable="TOKEN",
            required=True,
        ),
    ),
)
def test_contract_ids_share_the_canonical_id_rule(contract_id: str, model_factory: object) -> None:
    model_factory(contract_id)


@pytest.mark.parametrize(
    "contract_id",
    (
        "",
        "Uppercase",
        "1leading",
        "has space",
        "has/slash",
        " leading",
        "trailing ",
        "trailing\n",
    ),
)
@pytest.mark.parametrize(
    "model_factory",
    (
        lambda contract_id: ParameterSpec(parameter_id=contract_id, kind=ValueKind.STRING),
        lambda contract_id: ValuePort(port_id=contract_id, kind=ValueKind.STRING),
        lambda contract_id: SecretSpec(
            secret_id=contract_id,
            environment_variable="TOKEN",
            required=True,
        ),
    ),
)
def test_contract_ids_reject_noncanonical_forms_without_trimming(
    contract_id: str,
    model_factory: object,
) -> None:
    with pytest.raises(ValidationError):
        model_factory(contract_id)


@pytest.mark.parametrize("environment_variable", ("A", "API_KEY", "_TOKEN", "A1_B2"))
def test_secret_accepts_exact_shell_environment_variable_ids(environment_variable: str) -> None:
    secret = SecretSpec(
        secret_id="secret",
        environment_variable=environment_variable,
        required=True,
    )

    assert secret.environment_variable == environment_variable


@pytest.mark.parametrize(
    "environment_variable",
    ("", "lowercase", "1TOKEN", "HAS-DASH", "HAS SPACE", " TOKEN", "TOKEN ", "TOKEN\n"),
)
def test_secret_rejects_invalid_environment_variable_ids(environment_variable: str) -> None:
    with pytest.raises(ValidationError):
        SecretSpec(
            secret_id="secret",
            environment_variable=environment_variable,
            required=True,
        )


@pytest.mark.parametrize(
    ("kind", "required", "has_default", "default", "valid"),
    (
        (ValueKind.STRING, False, False, None, True),
        (ValueKind.STRING, True, False, None, True),
        (ValueKind.STRING, False, False, "", False),
        (ValueKind.STRING, True, False, "", False),
        (ValueKind.STRING, False, True, "", True),
        (ValueKind.STRING, True, True, "", False),
        (ValueKind.STRING, False, True, None, False),
        (ValueKind.JSON, False, True, None, True),
        (ValueKind.JSON, True, True, None, False),
        (ValueKind.JSON, True, False, None, True),
    ),
)
def test_parameter_default_truth_table(
    kind: ValueKind,
    required: bool,
    has_default: bool,
    default: object,
    valid: bool,
) -> None:
    values = {
        "required": required,
        "has_default": has_default,
        "default": default,
    }

    if valid:
        spec = parameter(kind, **values)
        assert spec.default == default
    else:
        with pytest.raises(ValidationError):
            parameter(kind, **values)


@pytest.mark.parametrize("field", ("required", "has_default"))
def test_parameter_boolean_flags_are_exact(field: str) -> None:
    with pytest.raises(ValidationError):
        parameter(ValueKind.STRING, **{field: 1})


@pytest.mark.parametrize(
    ("kind", "value"),
    (
        (ValueKind.STRING, "text"),
        (ValueKind.INTEGER, 1),
        (ValueKind.NUMBER, 1),
        (ValueKind.NUMBER, 1.25),
        (ValueKind.BOOLEAN, True),
        (ValueKind.JSON, None),
        (ValueKind.JSON, False),
        (ValueKind.JSON, 1),
        (ValueKind.JSON, 1.25),
        (ValueKind.JSON, "text"),
        (ValueKind.JSON, [1, "two"]),
        (ValueKind.JSON, {"one": 1}),
    ),
)
def test_parameter_accepts_exact_kind_values(kind: ValueKind, value: object) -> None:
    spec = parameter(kind, has_default=True, default=value)

    assert spec.has_default is True


@pytest.mark.parametrize(
    ("kind", "value"),
    (
        (ValueKind.STRING, b"text"),
        (ValueKind.STRING, 1),
        (ValueKind.INTEGER, True),
        (ValueKind.INTEGER, 1.0),
        (ValueKind.INTEGER, "1"),
        (ValueKind.INTEGER, ""),
        (ValueKind.NUMBER, True),
        (ValueKind.NUMBER, "1.5"),
        (ValueKind.NUMBER, ""),
        (ValueKind.BOOLEAN, 1),
        (ValueKind.BOOLEAN, "true"),
        (ValueKind.JSON, b"json"),
        (ValueKind.JSON, (1, 2)),
        (ValueKind.JSON, {1, 2}),
        (ValueKind.JSON, Decimal("1.2")),
        (ValueKind.JSON, {1: "non-string key"}),
    ),
)
def test_parameter_rejects_wrong_or_coercible_kind_values(kind: ValueKind, value: object) -> None:
    with pytest.raises(ValidationError):
        parameter(kind, has_default=True, default=value)


@pytest.mark.parametrize("value", (float("nan"), float("inf"), float("-inf")))
@pytest.mark.parametrize("kind", (ValueKind.NUMBER, ValueKind.JSON))
def test_parameter_rejects_nonfinite_numeric_defaults(kind: ValueKind, value: float) -> None:
    with pytest.raises(ValidationError):
        parameter(kind, has_default=True, default=value)


@pytest.mark.parametrize(
    "value",
    (
        [1, float("nan")],
        {"nested": float("inf")},
        {"deep": [{"value": float("-inf")}]},
    ),
)
def test_json_rejects_nested_nonfinite_numbers(value: object) -> None:
    with pytest.raises(ValidationError):
        parameter(ValueKind.JSON, has_default=True, default=value)


def test_json_rejects_cyclic_arrays_as_non_json_values() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)

    with pytest.raises(ValidationError, match="cyclic"):
        parameter(ValueKind.JSON, has_default=True, default=cyclic)


def test_json_serialized_object_text_remains_a_string_value() -> None:
    spec = parameter(ValueKind.JSON, has_default=True, default="{}")

    assert spec.default == "{}"
    assert spec.model_dump()["default"] == "{}"
    assert json.loads(spec.model_dump_json())["default"] == "{}"


def test_json_values_are_recursively_immutable_hashable_and_deterministic() -> None:
    first = parameter(
        ValueKind.JSON,
        has_default=True,
        default={"z": [{"b": 2, "a": 1}], "a": [True, None]},
    )
    second = parameter(
        ValueKind.JSON,
        has_default=True,
        default={"a": [True, None], "z": [{"a": 1, "b": 2}]},
    )

    assert first == second
    assert hash(first) == hash(second)
    assert_no_mutable_json(first.default)
    with pytest.raises(TypeError):
        first.default["new"] = "value"
    with pytest.raises((AttributeError, TypeError)):
        first.default["z"].append(3)
    with pytest.raises(TypeError):
        first.default["z"][0]["a"] = 3


def test_json_model_equality_and_hashing_are_type_aware_at_every_depth() -> None:
    boolean = parameter(ValueKind.JSON, has_default=True, default=True, choices=(True,))
    integer = parameter(ValueKind.JSON, has_default=True, default=1, choices=(1,))
    nested_boolean = parameter(ValueKind.JSON, has_default=True, default=[{"value": True}])
    nested_integer = parameter(ValueKind.JSON, has_default=True, default=[{"value": 1}])
    numeric_int = parameter(ValueKind.JSON, has_default=True, default={"value": [1]})
    numeric_float = parameter(ValueKind.JSON, has_default=True, default={"value": [1.0]})

    assert boolean != integer
    assert len({boolean, integer}) == 2
    assert nested_boolean.default != nested_integer.default
    assert nested_boolean != nested_integer
    assert len({nested_boolean, nested_integer}) == 2
    assert numeric_int == numeric_float
    assert hash(numeric_int) == hash(numeric_float)


def test_forged_frozen_json_containers_are_recursively_recanonicalized() -> None:
    forged_array = _FrozenJsonArray(([1],))
    forged_object = _FrozenJsonObject([("value", [{"nested": True}])])

    array_spec = parameter(ValueKind.JSON, has_default=True, default=forged_array)
    object_spec = parameter(ValueKind.JSON, has_default=True, default=forged_object)

    assert_no_mutable_json(array_spec.default)
    assert_no_mutable_json(object_spec.default)
    assert array_spec.model_dump()["default"] == [[1]]
    assert object_spec.model_dump()["default"] == {"value": [{"nested": True}]}
    assert hash(array_spec)
    assert hash(object_spec)


@pytest.mark.parametrize(
    "forged",
    (
        _FrozenJsonObject(((1, "value"),)),
        _FrozenJsonObject((("value", float("nan")),)),
        _FrozenJsonObject((("value", object()),)),
        _FrozenJsonObject((("duplicate", 1), ("duplicate", 2))),
    ),
)
def test_forged_frozen_json_objects_cannot_bypass_validation(forged: object) -> None:
    with pytest.raises(ValidationError):
        parameter(ValueKind.JSON, has_default=True, default=forged)


@pytest.mark.parametrize("entrypoint", ("construction", "copy", "validation"))
def test_malformed_frozen_json_object_storage_fails_as_validation_error(
    entrypoint: str,
) -> None:
    malformed = _FrozenJsonObject(None)
    valid = parameter(ValueKind.JSON, has_default=True, default={})

    with pytest.raises(ValidationError, match="object storage"):
        if entrypoint == "construction":
            parameter(ValueKind.JSON, has_default=True, default=malformed)
        elif entrypoint == "copy":
            valid.model_copy(update={"default": malformed})
        else:
            ParameterSpec.model_validate(
                {
                    "parameter_id": "body",
                    "kind": ValueKind.JSON,
                    "has_default": True,
                    "default": malformed,
                }
            )


def test_json_decoded_payloads_are_frozen_and_dump_back_as_json_shapes() -> None:
    payload = """
    {
      "parameter_id": "body",
      "kind": "json",
      "has_default": true,
      "default": {"array": [1, {"ok": true}]},
      "choices": [{"array": [1, {"ok": true}]}]
    }
    """

    spec = ParameterSpec.model_validate_json(payload)

    assert_no_mutable_json(spec.default)
    assert_no_mutable_json(spec.choices)
    assert spec.model_dump()["default"] == {"array": [1, {"ok": True}]}
    assert json.loads(spec.model_dump_json())["default"] == {"array": [1, {"ok": True}]}


def test_python_mapping_and_array_json_defaults_freeze_without_aliasing() -> None:
    original = {"array": [{"value": 1}]}
    spec = parameter(ValueKind.JSON, has_default=True, default=original)

    original["array"][0]["value"] = 2
    original["array"].append({"value": 3})

    assert spec.model_dump()["default"] == {"array": [{"value": 1}]}


def test_choices_are_optional_immutable_and_nonempty_when_present() -> None:
    without_choices = parameter(ValueKind.STRING)
    with_choices = parameter(ValueKind.STRING, choices=("one", "two"))

    assert without_choices.choices is None
    assert with_choices.choices == ("one", "two")
    assert isinstance(with_choices.choices, tuple)
    with pytest.raises(ValidationError):
        parameter(ValueKind.STRING, choices=())
    with pytest.raises(ValidationError):
        parameter(ValueKind.STRING, choices=["one"])


@pytest.mark.parametrize(
    ("kind", "choices"),
    (
        (ValueKind.STRING, ("same", "same")),
        (ValueKind.INTEGER, (1, 1)),
        (ValueKind.JSON, ({"a": [1]}, {"a": [1]})),
    ),
)
def test_choices_reject_type_aware_duplicates(kind: ValueKind, choices: tuple[object, ...]) -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        parameter(kind, choices=choices)


@pytest.mark.parametrize(
    ("kind", "choices"),
    (
        (ValueKind.JSON, (True, 1)),
        (ValueKind.JSON, ([True], [1])),
        (ValueKind.JSON, ({"value": True}, {"value": 1})),
    ),
)
def test_choices_keep_python_equal_but_json_distinct_values(
    kind: ValueKind,
    choices: tuple[object, ...],
) -> None:
    spec = parameter(kind, choices=choices)

    assert len(spec.choices) == len(choices)


@pytest.mark.parametrize(
    "choices",
    (
        (1, 1.0),
        ([1], [1.0]),
        ({"value": 1}, {"value": 1.0}),
    ),
)
def test_choices_treat_int_and_float_as_the_same_json_number(
    choices: tuple[object, ...],
) -> None:
    with pytest.raises(ValidationError, match="duplicate"):
        parameter(ValueKind.JSON, choices=choices)


@pytest.mark.parametrize(
    ("kind", "choices"),
    (
        (ValueKind.STRING, (1,)),
        (ValueKind.INTEGER, (True,)),
        (ValueKind.NUMBER, (False,)),
        (ValueKind.BOOLEAN, (1,)),
        (ValueKind.JSON, (b"value",)),
    ),
)
def test_choices_reject_values_of_the_wrong_kind(
    kind: ValueKind,
    choices: tuple[object, ...],
) -> None:
    with pytest.raises(ValidationError):
        parameter(kind, choices=choices)


def test_explicit_default_must_be_a_type_aware_choice_member() -> None:
    matching = parameter(
        ValueKind.JSON,
        has_default=True,
        default={"value": [True, 1]},
        choices=({"value": [True, 1]}, {"value": [1, True]}),
    )

    assert matching.has_default is True
    with pytest.raises(ValidationError, match="choice"):
        parameter(
            ValueKind.JSON,
            has_default=True,
            default={"value": [True]},
            choices=({"value": [1]},),
        )
    numeric_match = parameter(
        ValueKind.JSON,
        has_default=True,
        default={"value": [1]},
        choices=({"value": [1.0]},),
    )

    assert numeric_match.has_default is True


@pytest.mark.parametrize("kind", (ValueKind.INTEGER, ValueKind.NUMBER))
def test_numeric_bounds_are_inclusive_for_defaults_and_choices(kind: ValueKind) -> None:
    spec = parameter(
        kind,
        has_default=True,
        default=1,
        choices=(1, 2),
        minimum=1,
        maximum=2,
    )

    assert spec.default == 1
    assert spec.choices == (1, 2)


@pytest.mark.parametrize("kind", (ValueKind.STRING, ValueKind.BOOLEAN, ValueKind.JSON))
@pytest.mark.parametrize("field", ("minimum", "maximum"))
def test_numeric_bounds_are_rejected_for_irrelevant_kinds(kind: ValueKind, field: str) -> None:
    with pytest.raises(ValidationError):
        parameter(kind, **{field: 1})


@pytest.mark.parametrize(
    ("kind", "bound"),
    (
        (ValueKind.INTEGER, True),
        (ValueKind.INTEGER, 1.0),
        (ValueKind.INTEGER, "1"),
        (ValueKind.NUMBER, True),
        (ValueKind.NUMBER, "1"),
        (ValueKind.NUMBER, Decimal("1.0")),
        (ValueKind.NUMBER, float("nan")),
        (ValueKind.NUMBER, float("inf")),
    ),
)
@pytest.mark.parametrize("field", ("minimum", "maximum"))
def test_numeric_bounds_reject_wrong_exact_types_and_nonfinite_values(
    kind: ValueKind,
    bound: object,
    field: str,
) -> None:
    with pytest.raises(ValidationError):
        parameter(kind, **{field: bound})


@pytest.mark.parametrize(
    ("kind", "minimum", "maximum"),
    (
        (ValueKind.INTEGER, 2, 1),
        (ValueKind.NUMBER, 2.0, 1),
    ),
)
def test_numeric_bounds_reject_inverted_ranges(
    kind: ValueKind,
    minimum: int | float,
    maximum: int | float,
) -> None:
    with pytest.raises(ValidationError):
        parameter(kind, minimum=minimum, maximum=maximum)


@pytest.mark.parametrize(
    ("default", "minimum", "maximum"),
    ((0, 1, None), (3, None, 2)),
)
def test_numeric_bounds_reject_out_of_range_defaults(
    default: int,
    minimum: int | None,
    maximum: int | None,
) -> None:
    with pytest.raises(ValidationError):
        parameter(
            ValueKind.INTEGER,
            has_default=True,
            default=default,
            minimum=minimum,
            maximum=maximum,
        )


@pytest.mark.parametrize("choices", ((0, 1), (2, 3)))
def test_numeric_bounds_reject_out_of_range_choices(choices: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError):
        parameter(ValueKind.INTEGER, choices=choices, minimum=1, maximum=2)


@pytest.mark.parametrize("kind", (ValueKind.INTEGER, ValueKind.NUMBER, ValueKind.BOOLEAN, ValueKind.JSON))
@pytest.mark.parametrize("field", ("min_length", "max_length", "pattern"))
def test_string_constraints_are_rejected_for_irrelevant_kinds(kind: ValueKind, field: str) -> None:
    value: object = "text" if field == "pattern" else 1
    with pytest.raises(ValidationError):
        parameter(kind, **{field: value})


@pytest.mark.parametrize("field", ("min_length", "max_length"))
@pytest.mark.parametrize("value", (-1, True, 1.0, "1"))
def test_string_lengths_reject_negative_or_noninteger_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        parameter(ValueKind.STRING, **{field: value})


def test_string_lengths_reject_inverted_ranges() -> None:
    with pytest.raises(ValidationError):
        parameter(ValueKind.STRING, min_length=2, max_length=1)


def test_string_pattern_must_compile() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        parameter(ValueKind.STRING, pattern="[")


def test_string_constraints_use_inclusive_lengths_and_re_search() -> None:
    spec = parameter(
        ValueKind.STRING,
        has_default=True,
        default="abc123",
        choices=("abc123", "x9y"),
        min_length=3,
        max_length=6,
        pattern=r"\d+",
    )

    assert spec.default == "abc123"
    with pytest.raises(ValidationError):
        parameter(
            ValueKind.STRING,
            has_default=True,
            default="abc123",
            pattern=r"^\d+$",
        )


@pytest.mark.parametrize(
    "updates",
    (
        {"has_default": True, "default": "a", "min_length": 2},
        {"has_default": True, "default": "abc", "max_length": 2},
        {"has_default": True, "default": "abc", "pattern": r"^\d+$"},
        {"choices": ("a", "ab"), "min_length": 2},
        {"choices": ("ab", "abc"), "max_length": 2},
        {"choices": ("123", "abc"), "pattern": r"^\d+$"},
    ),
)
def test_string_constraints_reject_invalid_defaults_and_choices(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        parameter(ValueKind.STRING, **updates)


def test_empty_string_is_valid_without_a_restrictive_rule() -> None:
    spec = parameter(
        ValueKind.STRING,
        has_default=True,
        default="",
        choices=("", "value"),
    )

    assert spec.default == ""
    with pytest.raises(ValidationError):
        parameter(ValueKind.STRING, has_default=True, default="", min_length=1)


@pytest.mark.parametrize("kind", (ValueKind.INTEGER, ValueKind.NUMBER))
def test_numeric_default_regressions_reject_empty_strings_and_booleans(kind: ValueKind) -> None:
    for default in ("", True):
        with pytest.raises(ValidationError):
            parameter(kind, has_default=True, default=default)


def test_value_port_has_exact_fields_and_nonserialized_connectable_property() -> None:
    port = ValuePort(port_id="text", kind=ValueKind.STRING)

    assert port.model_dump() == {
        "port_id": "text",
        "kind": ValueKind.STRING,
        "required": True,
        "description": "",
    }
    assert port.connectable is True
    assert "connectable" not in ValuePort.model_fields
    assert "connectable" not in ValuePort.model_json_schema()["properties"]
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ValuePort(
            port_id="text",
            kind=ValueKind.STRING,
            connectable=False,
        )


@pytest.mark.parametrize("extra", ("default", "choices", "secret", "value"))
def test_value_port_rejects_parameter_or_secret_state(extra: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ValuePort(
            port_id="text",
            kind=ValueKind.STRING,
            **{extra: None},
        )


def test_value_port_is_strict_frozen_copy_validated_and_json_roundtrippable() -> None:
    port = ValuePort(
        port_id="count",
        kind=ValueKind.INTEGER,
        required=False,
        description="Count",
    )

    with pytest.raises(ValidationError):
        ValuePort(port_id="count", kind="integer")
    with pytest.raises(ValidationError):
        port.model_copy(update={"kind": "number"})
    with pytest.raises(ValidationError, match="frozen_instance"):
        port.required = True
    assert ValuePort.model_validate_json(port.model_dump_json()) == port


def test_secret_has_exact_required_reference_fields() -> None:
    secret = SecretSpec(
        secret_id="api_key",
        environment_variable="EXAMPLE_API_KEY",
        required=True,
    )

    assert secret.model_dump() == {
        "secret_id": "api_key",
        "environment_variable": "EXAMPLE_API_KEY",
        "required": True,
        "description": "",
    }
    assert tuple(SecretSpec.model_fields) == (
        "secret_id",
        "environment_variable",
        "required",
        "description",
    )
    assert tuple(SecretSpec.model_json_schema()["properties"]) == (
        "secret_id",
        "environment_variable",
        "required",
        "description",
    )
    with pytest.raises(ValidationError, match="Field required"):
        SecretSpec(secret_id="api_key", environment_variable="EXAMPLE_API_KEY")


@pytest.mark.parametrize(
    "field",
    (
        "value",
        "default",
        "token",
        "password",
        "example",
        "secret_value",
    ),
)
def test_secret_rejects_every_value_bearing_extra(field: str) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SecretSpec(
            secret_id="api_key",
            environment_variable="EXAMPLE_API_KEY",
            required=True,
            **{field: "do-not-store"},
        )


def test_secret_is_strict_frozen_copy_validated_and_json_roundtrippable() -> None:
    secret = SecretSpec(
        secret_id="api_key",
        environment_variable="EXAMPLE_API_KEY",
        required=False,
        description="Optional API key",
    )

    with pytest.raises(ValidationError):
        secret.model_copy(update={"environment_variable": "lowercase"})
    with pytest.raises(ValidationError):
        secret.model_copy(update={"required": 0})
    with pytest.raises(ValidationError, match="frozen_instance"):
        secret.required = True
    assert SecretSpec.model_validate_json(secret.model_dump_json()) == secret


@pytest.mark.parametrize(
    ("model_type", "python_values", "json_values"),
    (
        (
            ParameterSpec,
            {"parameter_id": "text", "kind": "string"},
            '{"parameter_id":"text","kind":"string"}',
        ),
        (
            ValuePort,
            {"port_id": "text", "kind": "string"},
            '{"port_id":"text","kind":"string"}',
        ),
    ),
)
def test_python_rejects_enum_wire_strings_while_json_accepts_them(
    model_type: type,
    python_values: dict[str, object],
    json_values: str,
) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(python_values)

    assert model_type.model_validate_json(json_values).kind is ValueKind.STRING


def test_parameter_schema_forbids_extras_and_exposes_kind_enum() -> None:
    schema = ParameterSpec.model_json_schema()
    kind_schema = schema["$defs"]["ValueKind"]

    assert schema["additionalProperties"] is False
    assert kind_schema["enum"] == ["string", "integer", "number", "boolean", "json"]
    assert ValuePort.model_json_schema()["additionalProperties"] is False
    assert SecretSpec.model_json_schema()["additionalProperties"] is False
