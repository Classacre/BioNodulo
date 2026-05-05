from __future__ import annotations

from collections import defaultdict, deque

from bionodulo.workflow.schema import Workflow


class GraphError(ValueError):
    pass


def incoming_edges(workflow: Workflow) -> dict[str, list]:
    incoming: dict[str, list] = defaultdict(list)
    for edge in workflow.edges:
        incoming[edge.to.node].append(edge)
    return incoming


def outgoing_edges(workflow: Workflow) -> dict[str, list]:
    outgoing: dict[str, list] = defaultdict(list)
    for edge in workflow.edges:
        outgoing[edge.from_.node].append(edge)
    return outgoing


def topological_sort(workflow: Workflow) -> list[str]:
    node_ids = [node.id for node in workflow.nodes]
    indegree = {node_id: 0 for node_id in node_ids}
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}

    for edge in workflow.edges:
        if edge.from_.node not in indegree or edge.to.node not in indegree:
            continue
        adjacency[edge.from_.node].append(edge.to.node)
        indegree[edge.to.node] += 1

    queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in adjacency[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(order) != len(node_ids):
        raise GraphError("Workflow graph contains a cycle")
    return order


def upstream_nodes(workflow: Workflow, output_ids: list[str]) -> set[str]:
    parents: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        parents[edge.to.node].append(edge.from_.node)
    wanted = set(output_ids)
    stack = list(output_ids)
    while stack:
        node_id = stack.pop()
        for parent in parents.get(node_id, []):
            if parent not in wanted:
                wanted.add(parent)
                stack.append(parent)
    return wanted
