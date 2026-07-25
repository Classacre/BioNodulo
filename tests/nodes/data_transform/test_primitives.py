"""Focused scalar primitive behavior and safety bounds."""

from __future__ import annotations

import pytest

from bionodulo.nodes.builtin.data_transform_family import MathExpressionNode, StringFormatNode


@pytest.mark.asyncio
async def test_string_format_uses_python_312_format_specs() -> None:
    result = await StringFormatNode().run(
        template="{sample}: {value:.2f}",
        variables_json='{"sample":"S1","value":2.345}',
    )
    assert result == ("S1: 2.35",)


@pytest.mark.asyncio
async def test_math_expression_supports_round_and_rejects_unbounded_or_unsafe_ast() -> None:
    result = await MathExpressionNode().run(
        expression="round(sqrt(x) + 0.005, 2)",
        variables_json='{"x":9}',
    )
    assert result == (3.0, 3, True, "3")

    with pytest.raises(ValueError, match="Only approved math functions"):
        await MathExpressionNode().run(expression="__import__('os')", variables_json="{}")
    with pytest.raises(ValueError, match="Absolute exponent must not exceed 100"):
        await MathExpressionNode().run(expression="2 ** 101", variables_json="{}")
