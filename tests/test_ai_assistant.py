import pytest

from bionodulo.ai import chat_with_assistant
from bionodulo.api.schemas import AIChatMessage, AIChatRequest
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow


def registry():
    reg = NodeRegistry()
    reg.load_builtin_nodes()
    return reg


@pytest.mark.asyncio
async def test_ai_chat_without_api_key_uses_local_guidance(tmp_path):
    workflow = Workflow.model_validate({"nodes": [], "edges": [], "outputs": []})
    payload = AIChatRequest(workflow=workflow, messages=[AIChatMessage(role="user", content="Explain this workflow")])

    result = await chat_with_assistant(payload, registry(), tmp_path)

    assert result["provider"] == "local"
    assert "Add an API key" in result["reply"]
    assert result["workflow"] is None
