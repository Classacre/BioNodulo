"""Graph algorithms for BioNodulo workflows.

Provides topological sort, edge mapping, and upstream/downstream
queries on the workflow DAG.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any


def edge_source(edge: Any) -> str:
    """Return the source node id from any supported edge shape."""
    if isinstance(edge, dict):
        source = (
            edge.get("source")
            or edge.get("from_node")
            or edge.get("source_node")
        )
        if source is None and "from" in edge:
            from_data = edge["from"]
            source = from_data.get("node") if isinstance(from_data, dict) else from_data
        return str(source) if source is not None else ""
    source = getattr(edge, "source", None) or getattr(edge, "from_node", None) or getattr(edge, "source_node", "")
    return str(source) if source is not None else ""


def edge_target(edge: Any) -> str:
    """Return the target node id from any supported edge shape."""
    if isinstance(edge, dict):
        target = (
            edge.get("target")
            or edge.get("to_node")
            or edge.get("target_node")
        )
        if target is None and "to" in edge:
            to_data = edge["to"]
            target = to_data.get("node") if isinstance(to_data, dict) else to_data
        return str(target) if target is not None else ""
    target = getattr(edge, "target", None) or getattr(edge, "to_node", None) or getattr(edge, "target_node", "")
    return str(target) if target is not None else ""


def edge_source_port(edge: Any, default: str = "default") -> str:
    """Return the source output port from any supported edge shape."""
    if isinstance(edge, dict):
        port = edge.get("source_output") or edge.get("from_output") or edge.get("output")
        if port is None and isinstance(edge.get("from"), dict):
            port = edge["from"].get("output")
        return str(port or default)
    port = getattr(edge, "source_output", None) or getattr(edge, "from_output", None) or getattr(edge, "output", None)
    return str(port or default)


def edge_target_port(edge: Any, default: str = "default") -> str:
    """Return the target input port from any supported edge shape."""
    if isinstance(edge, dict):
        port = edge.get("target_input") or edge.get("to_input") or edge.get("input")
        if port is None and isinstance(edge.get("to"), dict):
            port = edge["to"].get("input")
        return str(port or default)
    port = getattr(edge, "target_input", None) or getattr(edge, "to_input", None) or getattr(edge, "input", None)
    return str(port or default)


def incoming_edges(workflow: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build a map of node_id -> list of incoming edges."""
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in workflow.get("edges", []):
        target = edge_target(edge)
        if target:
            d = edge if isinstance(edge, dict) else edge.model_dump()
            result[target].append(d)
    return dict(result)


def outgoing_edges(workflow: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build a map of node_id -> list of outgoing edges."""
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in workflow.get("edges", []):
        source = edge_source(edge)
        if source:
            d = edge if isinstance(edge, dict) else edge.model_dump()
            result[source].append(d)
    return dict(result)


def _get_all_node_ids(workflow: dict[str, Any]) -> set[str]:
    """Extract all node IDs from a workflow dictionary."""
    nodes = workflow.get("nodes", {})
    if isinstance(nodes, dict):
        return set(nodes.keys())
    if isinstance(nodes, list):
        return {n["id"] if isinstance(n, dict) else getattr(n, "id", "") for n in nodes}
    return set()


def _build_adjacency(workflow: dict[str, Any]) -> dict[str, list[str]]:
    """Build adjacency list: node -> list of downstream node IDs."""
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.get("edges", []):
        src = edge_source(edge)
        dst = edge_target(edge)
        if src and dst:
            adj[src].append(dst)
    return dict(adj)


def _build_indegree(workflow: dict[str, Any]) -> dict[str, int]:
    """Build indegree map for topological sort."""
    node_ids = _get_all_node_ids(workflow)
    indegree = {nid: 0 for nid in node_ids}
    for edge in workflow.get("edges", []):
        dst = edge_target(edge)
        if dst in indegree:
            indegree[dst] += 1
    return indegree


def topological_sort(workflow: dict[str, Any]) -> list[str]:
    """Return a topologically sorted list of node IDs using Kahn's algorithm.

    Raises ValueError if the graph contains a cycle.
    """
    node_ids = _get_all_node_ids(workflow)
    if not node_ids:
        return []

    adj = _build_adjacency(workflow)
    indegree = _build_indegree(workflow)

    queue = deque([nid for nid in node_ids if indegree.get(nid, 0) == 0])
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in adj.get(node, []):
            indegree[neighbor] = indegree.get(neighbor, 0) - 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if len(result) != len(node_ids):
        remaining = node_ids - set(result)
        raise ValueError(f"Workflow contains a cycle. Remaining nodes: {remaining}")

    return result


def downstream_nodes(
    workflow: dict[str, Any],
    start_node_ids: list[str],
) -> list[str]:
    """Find all nodes downstream of the given start nodes (BFS)."""
    adj = _build_adjacency(workflow)
    visited: set[str] = set(start_node_ids)
    queue = deque(start_node_ids)
    result: list[str] = []

    while queue:
        current = queue.popleft()
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                result.append(neighbor)
                queue.append(neighbor)

    return result


def upstream_nodes(
    workflow: dict[str, Any],
    start_node_ids: list[str],
) -> list[str]:
    """Find all nodes upstream of the given start nodes (reverse BFS)."""
    reverse_adj: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.get("edges", []):
        src = edge_source(edge)
        dst = edge_target(edge)
        if src and dst:
            reverse_adj[dst].append(src)

    visited: set[str] = set(start_node_ids)
    queue = deque(start_node_ids)
    result: list[str] = []

    while queue:
        current = queue.popleft()
        for neighbor in reverse_adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                result.append(neighbor)
                queue.append(neighbor)

    return result
