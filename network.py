"""
network.py
----------
Builds the financial network (a weighted directed graph) from data.py and
provides small helper functions for querying it.

Keeping graph construction separate from the simulation means the propagation
engine never needs to know where the data came from.
"""

from typing import Dict, List, Tuple

import networkx as nx
import pandas as pd

import data


class NetworkDataError(ValueError):
    """Raised when the configured network data is invalid."""


def build_network() -> nx.DiGraph:
    """Build the weighted directed graph of the financial ecosystem.

    Nodes carry a ``category`` and ``description`` attribute; edges carry a
    ``weight`` in (0, 1] describing how strongly a disturbance transmits.

    Raises:
        NetworkDataError: if an edge references an unknown node or the weight
            is outside the valid range. Catching bad data here means the app
            can show a friendly message instead of failing deep inside the
            simulation.
    """
    graph = nx.DiGraph()

    for node, category in data.NODE_CATEGORIES.items():
        graph.add_node(
            node,
            category=category,
            description=data.NODE_DESCRIPTIONS.get(node, ""),
        )

    for source, target, weight in data.EDGES:
        if source not in graph or target not in graph:
            raise NetworkDataError(
                f"Edge '{source} -> {target}' references a node that is not "
                f"defined in NODE_CATEGORIES."
            )
        if not 0 < weight <= 1:
            raise NetworkDataError(
                f"Edge '{source} -> {target}' has weight {weight}; "
                f"weights must be greater than 0 and at most 1."
            )
        graph.add_edge(source, target, weight=float(weight))

    if graph.number_of_nodes() == 0:
        raise NetworkDataError("The network contains no nodes.")

    return graph


def get_node_positions(graph: nx.DiGraph) -> Dict[str, Tuple[float, float]]:
    """Return a fixed (x, y) position for every node.

    Hand-authored positions from data.py are used where available so the
    layout is stable and readable. Any node without one falls back to a
    seeded spring layout, which keeps the result deterministic.
    """
    positions = {
        node: data.NODE_POSITIONS[node]
        for node in graph.nodes
        if node in data.NODE_POSITIONS
    }

    missing = [node for node in graph.nodes if node not in positions]
    if missing:
        # seed=42 makes the fallback layout reproducible between runs.
        fallback = nx.spring_layout(graph, seed=42)
        for node in missing:
            x, y = fallback[node]
            positions[node] = (float(x) * 5.0, float(y) * 5.0)

    return positions


def list_nodes(graph: nx.DiGraph) -> List[str]:
    """Return node names in a stable, human-friendly (alphabetical) order."""
    return sorted(graph.nodes)


def node_summary_table(graph: nx.DiGraph) -> pd.DataFrame:
    """Return a table describing each node's role in the network.

    ``Outgoing Exposure`` is the sum of the weights of a node's outgoing
    edges: a rough measure of how much force it can push into the system.
    ``Incoming Exposure`` is the same for edges pointing at it: how exposed
    it is to the rest of the network.
    """
    rows = []
    for node in list_nodes(graph):
        outgoing = sum(d["weight"] for _, _, d in graph.out_edges(node, data=True))
        incoming = sum(d["weight"] for _, _, d in graph.in_edges(node, data=True))
        rows.append(
            {
                "Entity": node,
                "Category": graph.nodes[node]["category"],
                "Outgoing Links": graph.out_degree(node),
                "Incoming Links": graph.in_degree(node),
                "Outgoing Exposure": round(outgoing, 2),
                "Incoming Exposure": round(incoming, 2),
            }
        )
    return pd.DataFrame(rows)


def edge_table(graph: nx.DiGraph) -> pd.DataFrame:
    """Return every relationship in the network as a table."""
    rows = [
        {"Source": u, "Target": v, "Weight": d["weight"]}
        for u, v, d in graph.edges(data=True)
    ]
    return pd.DataFrame(rows).sort_values(
        ["Source", "Weight"], ascending=[True, False]
    ).reset_index(drop=True)
