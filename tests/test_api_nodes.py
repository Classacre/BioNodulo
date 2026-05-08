from bionodulo.api_nodes.base import ApiNode


class DummyContext:
    def resolve_secret(self, name):
        return {"ncbi": "secret-token"}.get(name, "")


def test_api_node_resolves_server_side_secret_reference():
    node = ApiNode()

    assert node.resolve_secret(DummyContext(), "ncbi") == "secret-token"
    assert node.resolve_secret(DummyContext(), "missing") == ""
