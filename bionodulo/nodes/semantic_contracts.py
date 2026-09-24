"""Semantic contract schema: port-level data-state assumptions and guarantees.

The design is grounded in ``Possible PhD/BioNodulo-PhD-Research-Dossier-v1.md``
sections 2 and 8.1. Three properties drive every decision here:

* Dimensions are registry-driven closed enums with an explicit ``unknown``
  member, so the system extends without code changes and every per-edge check
  stays decidable (truth-table subsumption, not ontology reasoning).
* A port contract is a conjunction of per-dimension clauses. Input ports
  declare assumptions (what the node requires about incoming data state);
  output ports declare guarantee transforms (how the node changes that state).
* ``unknown`` is a first-class gradual value [Siek and Taha 2006]: it never
  rejects an edge by itself, it asks for a runtime detection step instead.

Citation tags below ([S#], [E#], [G#]) refer to the dossier reference list.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

UNKNOWN = "unknown"

_BUNDLED_CONTRACTS_PATH = (
    Path(__file__).parent / "generated" / "semantic_contracts.json"
)


class SemanticDimension(BaseModel):
    """A closed enum of data-state values for one dimension (e.g. sort_order)."""

    name: str
    description: str = ""
    values: tuple[str, ...]

    @field_validator("values")
    @classmethod
    def _values_are_closed(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("dimension must declare at least one value")
        if len(set(values)) != len(values):
            raise ValueError("dimension values must be unique")
        for value in values:
            if not value or not value.replace("_", "").replace("-", "").isalnum():
                raise ValueError(f"invalid dimension value: {value!r}")
        return values

    @model_validator(mode="after")
    def _unknown_is_member(self) -> Self:
        # The gradual value must exist so every state in the graph is
        # representable [S26].
        if UNKNOWN not in self.values:
            raise ValueError(f"dimension {self.name} must include '{UNKNOWN}'")
        return self


class Clause(BaseModel):
    """One assumption about a single dimension of an input port's state.

    ``operator`` is ``eq`` (default), ``in`` (any listed value satisfies),
    ``any`` (no constraint; useful for documentation), or ``param_map``
    (the required value is derived from a node parameter through a mapping,
    as with featureCounts ``-s`` 0/1/2 to strandedness [E11]; an absent or
    unmapped parameter resolves to ``unknown``, which never rejects).
    """

    dimension: str
    operator: str = Field(default="eq", validation_alias=AliasChoices("operator", "op"))
    value: str | None = None
    values: tuple[str, ...] = ()
    param: str | None = None
    param_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _operator_shape(self) -> Self:
        if self.operator == "eq":
            if self.value is None:
                raise ValueError("eq clause requires a value")
        elif self.operator == "in":
            if not self.values:
                raise ValueError("in clause requires values")
        elif self.operator == "any":
            if self.value is not None or self.values:
                raise ValueError("any clause takes no values")
        elif self.operator == "param_map":
            if self.param is None or not self.param_map:
                raise ValueError("param_map clause requires param and param_map")
        else:
            raise ValueError(f"unsupported operator: {self.operator}")
        return self

    def resolve_required(self, node_params: dict[str, Any] | None) -> Clause:
        """Return the static clause implied by this clause for a node config."""
        if self.operator != "param_map" or self.param is None:
            return self
        params = node_params or {}
        raw = params.get(self.param)
        if raw is None:
            return Clause(dimension=self.dimension, operator="any")
        mapped = self.param_map.get(str(raw))
        if mapped is None:
            return Clause(dimension=self.dimension, operator="any")
        return Clause(dimension=self.dimension, operator="eq", value=mapped)

    def accepts(self, state_value: str | None) -> bool:
        if self.operator == "any":
            return True
        if state_value is None or state_value == UNKNOWN:
            # Gradual: an assumption is only checked against known state.
            return False
        if self.operator == "eq":
            return state_value == self.value
        return state_value in self.values

    def describe(self) -> str:
        if self.operator == "any":
            return f"{self.dimension}: any"
        if self.operator == "in":
            joined = "|".join(self.values)
            return f"{self.dimension} in ({joined})"
        if self.operator == "param_map":
            joined = ",".join(f"{k}->{v}" for k, v in sorted(self.param_map.items()))
            return f"{self.dimension} from param {self.param} ({joined})"
        return f"{self.dimension}={self.value}"


class Guarantee(BaseModel):
    """How a node's output state is derived, per dimension.

    Ops:

    * ``set``: the output state is a constant (samtools_sort sets
      sort_order=coordinate).
    * ``propagate``: the output carries the input state through (format
      converters keep assembly and strandedness). ``from_port`` defaults to
      the node's single artifact input.
    * ``param_map``: the output/assumed state is read from a node parameter
      through a mapping (featureCounts ``-s`` 0/1/2 to strandedness values
      [E11]). Unmapped or absent parameters resolve to ``unknown``.
    * ``param_tuple_map``: the output state is selected from more than one
      parameter. Keys join values with ``|`` in the declared parameter order;
      this is used when one CLI flag overrides another.
    * ``unknown``: the node destroys knowledge of this dimension.
    """

    dimension: str
    op: str = "propagate"
    value: str | None = None
    from_port: str | None = None
    param: str | None = None
    params: tuple[str, ...] = ()
    param_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _op_shape(self) -> Self:
        if self.op == "set":
            if self.value is None:
                raise ValueError("set guarantee requires a value")
        elif self.op == "param_map":
            if self.param is None or not self.param_map:
                raise ValueError("param_map guarantee requires param and param_map")
        elif self.op == "param_tuple_map":
            if not self.params or not self.param_map:
                raise ValueError(
                    "param_tuple_map guarantee requires params and param_map"
                )
            if any("|" in name for name in self.params):
                raise ValueError("param_tuple_map parameter names cannot contain '|'")
        elif self.op not in ("propagate", "unknown"):
            raise ValueError(f"unsupported guarantee op: {self.op}")
        return self


class NodeSemanticContract(BaseModel):
    """Assumptions and guarantees for one node type.

    ``inputs`` maps input port names to assumption clause lists; ``outputs``
    maps output port names to guarantee lists. Ports without entries are
    gradual (unknown state, warned but never rejected).
    """

    node_type: str
    source: str = "repository_seed"
    review_status: Literal[
        "unreviewed",
        "documentation_backed",
        "expert_confirmed",
        "runtime_validated",
    ] = "unreviewed"
    notes: str = ""
    version: str | None = None
    inputs: dict[str, list[Clause]] = Field(default_factory=dict)
    outputs: dict[str, list[Guarantee]] = Field(default_factory=dict)


class CoercionRule(BaseModel):
    """A typed rewrite from one state value to another via a converter node.

    Preconditions are declarative (e.g. a chain file for an assembly
    transition [S41][S42][S43]); the checker reports them in the suggestion
    instead of silently applying an unsafe coercion. ``detection`` rules do
    not change state; they insert a runtime check node that resolves
    ``unknown`` (RSeQC-style gradual checks [E9][E10]).
    """

    id: str
    dimension: str
    from_value: str
    to_value: str
    converter_node_type: str
    converter_input_port: str
    converter_output_port: str
    cost: int = 10
    requires: tuple[str, ...] = ()
    params: dict[str, Any] = Field(default_factory=dict)
    detection: bool = False

    @model_validator(mode="after")
    def _detection_shape(self) -> Self:
        if self.detection and self.to_value != UNKNOWN:
            # A detection coercion resolves unknown, it never rewrites a
            # known-wrong value: that would be an unsafe repair [E57].
            raise ValueError("detection rules must target 'unknown'")
        return self


class SemanticContractLibrary(BaseModel):
    """The loaded dimension registry, node contracts, and coercion rules."""

    schema_version: Literal["0.1", "0.2"] = "0.1"
    dimensions: tuple[SemanticDimension, ...]
    contracts: tuple[NodeSemanticContract, ...] = ()
    coercions: tuple[CoercionRule, ...] = ()

    # -- construction ----------------------------------------------------

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SemanticContractLibrary":
        source = Path(path) if path is not None else _BUNDLED_CONTRACTS_PATH
        payload = json.loads(source.read_text(encoding="utf-8"))
        return cls.model_validate(payload)

    @classmethod
    @lru_cache(maxsize=1)
    def bundled(cls) -> "SemanticContractLibrary":
        return cls.load()

    # -- lookups ----------------------------------------------------------

    def dimension_values(self, name: str) -> tuple[str, ...]:
        for dimension in self.dimensions:
            if dimension.name == name:
                return dimension.values
        raise KeyError(f"unknown semantic dimension: {name}")

    def contract_for(self, node_type: str) -> NodeSemanticContract | None:
        for contract in self.contracts:
            if contract.node_type == node_type:
                return contract
        return None

    def coercions_for(self, dimension: str) -> tuple[CoercionRule, ...]:
        return tuple(rule for rule in self.coercions if rule.dimension == dimension)

    # -- validation -------------------------------------------------------

    @model_validator(mode="after")
    def _references_resolve(self) -> Self:
        dimension_names = {dimension.name for dimension in self.dimensions}
        for contract in self.contracts:
            for port, clauses in contract.inputs.items():
                for clause in clauses:
                    if clause.dimension not in dimension_names:
                        raise ValueError(
                            f"contract for {contract.node_type} port {port} references"
                            f" unknown dimension {clause.dimension}"
                        )
                    if clause.operator in ("eq", "in"):
                        allowed = self.dimension_values(clause.dimension)
                        candidates = (
                            (clause.value,) if clause.value is not None else clause.values
                        )
                        for value in candidates:
                            if value not in allowed:
                                raise ValueError(
                                    f"clause value {value!r} is not a member of dimension"
                                    f" {clause.dimension}"
                                )
                    if clause.operator == "param_map":
                        allowed = self.dimension_values(clause.dimension)
                        for value in clause.param_map.values():
                            if value not in allowed:
                                raise ValueError(
                                    f"param_map value {value!r} is not a member of"
                                    f" dimension {clause.dimension}"
                                )
            for port, guarantees in contract.outputs.items():
                for guarantee in guarantees:
                    if guarantee.dimension not in dimension_names:
                        raise ValueError(
                            f"guarantee for {contract.node_type} port {port} references"
                            f" unknown dimension {guarantee.dimension}"
                        )
                    if guarantee.value is not None:
                        allowed = self.dimension_values(guarantee.dimension)
                        if guarantee.op == "set" and guarantee.value not in allowed:
                            raise ValueError(
                                f"guarantee value {guarantee.value!r} is not a member of"
                                f" dimension {guarantee.dimension}"
                            )
                    if guarantee.op in ("param_map", "param_tuple_map"):
                        allowed = self.dimension_values(guarantee.dimension)
                        for value in guarantee.param_map.values():
                            if value not in allowed:
                                raise ValueError(
                                    f"guarantee param_map value {value!r} is not a member of"
                                    f" dimension {guarantee.dimension}"
                                )
        for rule in self.coercions:
            if rule.dimension not in dimension_names:
                raise ValueError(
                    f"coercion {rule.id} references unknown dimension {rule.dimension}"
                )
            allowed = self.dimension_values(rule.dimension)
            if rule.from_value not in allowed or rule.to_value not in allowed:
                raise ValueError(
                    f"coercion {rule.id} values must be members of {rule.dimension}"
                )
        return self

    @model_validator(mode="after")
    def _duplicate_contracts(self) -> Self:
        seen: set[str] = set()
        for contract in self.contracts:
            if contract.node_type in seen:
                raise ValueError(f"duplicate contract for {contract.node_type}")
            seen.add(contract.node_type)
        rule_ids = {rule.id for rule in self.coercions}
        if len(rule_ids) != len(self.coercions):
            raise ValueError("coercion rule ids must be unique")
        return self


def bundled_contracts_path() -> Path:
    return _BUNDLED_CONTRACTS_PATH
