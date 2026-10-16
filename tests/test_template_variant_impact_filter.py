"""Keep the official impact filters compatible with BCFtools' basic regexes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bionodulo.nodes.builtin.bcftools_family.filter_vcf import FilterVCFNode


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("stem", ["variant_calling_pipeline", "wgs_variant_pipeline"])
def test_template_impact_filter_keeps_both_classes_with_the_pass_guard(
    stem: str, tmp_path: Path,
) -> None:
    workflow = json.loads((ROOT / "templates" / f"{stem}.json").read_text(encoding="utf-8"))
    node = next(node for node in workflow["nodes"] if node["type"] == "filter_vcf")
    command = FilterVCFNode.render_command({
        **node["params"], "vcf": "annotated.vcf", "output": tmp_path,
    })
    expression = command[command.index("--include") + 1]
    prefix = 'FILTER == "PASS" && ('
    assert expression.startswith(prefix) and expression.endswith(")")
    clauses = expression[len(prefix):-1].split(" || ")
    # The pinned filter.c calls regcomp without REG_EXTENDED. An unescaped
    # HIGH|MODERATE inside one regex therefore matches a literal pipe, not OR.
    patterns = [re.fullmatch(r"INFO/ANN ~ '([A-Z]+)'", clause) for clause in clauses]
    assert len(patterns) == 2 and all(patterns)
    impacts = {pattern.group(1) for pattern in patterns if pattern is not None}
    assert impacts == {"HIGH", "MODERATE"}
    for impact, expected in (("HIGH", True), ("MODERATE", True), ("LOW", False), ("MODIFIER", False)):
        annotation = f"label|effect|{impact}|other"
        assert any(pattern in annotation for pattern in impacts) is expected
    # OR remains inside the PASS conjunction and one argv element; it must
    # neither admit non-PASS records nor become a shell pipeline.
    assert command[:2] == ["bcftools", "view"]
    assert FilterVCFNode.SHELL is False
    assert "||" not in command
