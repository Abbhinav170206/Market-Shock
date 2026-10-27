"""
simulation.py
-------------
The shock propagation engine and the systemic risk score.

The model is deliberately simple, deterministic and explainable: given the
same inputs it always produces the same output, and every number shown in the
UI can be traced back to a single multiplication.

    propagated impact = incoming impact x edge weight x damping factor

This is a scenario / stress-testing tool. It is NOT a validated prediction of
real market behaviour.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx
import pandas as pd

# --- Engine defaults -------------------------------------------------------
DEFAULT_DAMPING = 0.85       # each additional hop retains 85% of the force
DEFAULT_THRESHOLD = 0.01     # ignore impacts smaller than 1 percentage point
DEFAULT_MAX_DEPTH = 5        # never propagate more than 5 hops from the origin
MAX_EVENTS = 5000            # hard safety cap so the loop can always terminate


@dataclass
class PropagationEvent:
    """A single transmission of impact along one edge."""

    source: str
    target: str
    weight: float
    incoming_impact: float   # impact arriving at `source` on this path
    impact: float            # impact delivered to `target` (signed)
    level: int               # hops from the origin (origin -> level 1)
    path: List[str]          # full route taken, starting at the origin

    def explain(self, damping: float) -> str:
        """Return the arithmetic behind this event, for the pathways view."""
        return (
            f"{self.incoming_impact:+.2%} x {self.weight:.2f} (weight) "
            f"x {damping:.2f} (damping) = {self.impact:+.2%}"
        )


@dataclass
class SimulationResult:
    """Everything a single simulation run produced."""

    origin: str
    magnitude: float
    damping: float
    threshold: float
    max_depth: int
    impacts: Dict[str, float] = field(default_factory=dict)   # signed totals
    levels: Dict[str, int] = field(default_factory=dict)      # first-reached hop
    events: List[PropagationEvent] = field(default_factory=list)
    risk_score: float = 0.0
    risk_breakdown: Dict[str, float] = field(default_factory=dict)
    truncated: bool = False   # True if the safety cap stopped the run early

    # -- Convenience summaries used by the dashboard ------------------------

    @property
    def affected_entities(self) -> List[str]:
        """Nodes that received impact, excluding the shock origin itself."""
        return [node for node in self.impacts if node != self.origin]

    @property
    def affected_count(self) -> int:
        return len(self.affected_entities)

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def max_level(self) -> int:
        """Deepest propagation level actually reached."""
        return max((event.level for event in self.events), default=0)

    @property
    def total_impact(self) -> float:
        """Sum of absolute impact across every affected entity."""
        return sum(abs(self.impacts[node]) for node in self.affected_entities)

    @property
    def max_impact(self) -> float:
        """Largest single absolute impact on any affected entity."""
        return max(
            (abs(self.impacts[node]) for node in self.affected_entities),
            default=0.0,
        )

    @property
    def most_affected(self) -> Optional[str]:
        """Name of the worst-hit entity, or None if nothing was affected."""
        if not self.affected_entities:
            return None
        return max(self.affected_entities, key=lambda n: abs(self.impacts[n]))


def simulate_shock(
    graph: nx.DiGraph,
    origin: str,
    magnitude: float,
    damping: float = DEFAULT_DAMPING,
    threshold: float = DEFAULT_THRESHOLD,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> SimulationResult:
    """Propagate a shock outwards from `origin` through the network.

    The traversal is a breadth-first sweep, so entities are reached in order
    of how many hops separate them from the origin. Along each edge:

        delivered = incoming impact x edge weight x damping

    Propagation along a route stops when the delivered impact falls below
    `threshold`, when `max_depth` hops have been taken, or when the route
    would revisit a node it has already passed through (which prevents a
    cycle in the network from looping forever).

    A node's reported impact is the SUM of everything delivered to it from
    every route, which is how an entity sitting downstream of several
    channels ends up more exposed than one fed by a single channel.

    Args:
        graph: the weighted directed network from network.build_network().
        origin: node the shock starts at.
        magnitude: signed shock size as a fraction (0.20 means +20%).
        damping: force retained per hop, in (0, 1].
        threshold: minimum absolute impact worth propagating.
        max_depth: maximum hops from the origin.

    Returns:
        A SimulationResult, including the systemic risk score.

    Raises:
        ValueError: if the origin is not in the network or a parameter is
            outside its valid range.
    """
    # --- Validate inputs so the UI never has to handle a crash later -------
    if origin not in graph:
        raise ValueError(f"{origin!r} is not an entity in this network.")
    if not 0 < damping <= 1:
        raise ValueError("Damping must be greater than 0 and at most 1.")
    if threshold < 0:
        raise ValueError("Threshold cannot be negative.")
    if max_depth < 1:
        raise ValueError("Maximum depth must be at least 1.")

    result = SimulationResult(
        origin=origin,
        magnitude=float(magnitude),
        damping=float(damping),
        threshold=float(threshold),
        max_depth=int(max_depth),
    )

    # The origin always carries the applied shock itself, even when that
    # shock is zero -- the UI relies on the origin being present.
    result.impacts[origin] = float(magnitude)
    result.levels[origin] = 0

    # A zero-sized shock has nothing to propagate; return early rather than
    # pretending something happened.
    if magnitude == 0:
        return result

    # Queue entries are (node, impact arriving at that node, level, route).
    queue = deque([(origin, float(magnitude), 0, [origin])])

    while queue:
        node, incoming_impact, level, path = queue.popleft()

        if level >= max_depth:
            continue

        # Sorting keeps the event order deterministic regardless of the order
        # the edges happened to be inserted in.
        for target in sorted(graph.successors(node)):
            if target in path:
                continue  # never revisit a node on the same route

            weight = graph[node][target]["weight"]
            delivered = incoming_impact * weight * damping

            if abs(delivered) < threshold:
                continue  # too weak to matter; this route ends here

            if len(result.events) >= MAX_EVENTS:
                result.truncated = True
                queue.clear()
                break

            next_level = level + 1
            result.events.append(
                PropagationEvent(
                    source=node,
                    target=target,
                    weight=weight,
                    incoming_impact=incoming_impact,
                    impact=delivered,
                    level=next_level,
                    path=path + [target],
                )
            )

            result.impacts[target] = result.impacts.get(target, 0.0) + delivered
            # Record the SHALLOWEST level at which the node was first reached.
            if target not in result.levels or next_level < result.levels[target]:
                result.levels[target] = next_level

            queue.append((target, delivered, next_level, path + [target]))

    result.risk_score, result.risk_breakdown = calculate_risk_score(result, graph)
    return result


# ---------------------------------------------------------------------------
# SYSTEMIC RISK SCORE
# ---------------------------------------------------------------------------
# Four components, each normalised to 0-1 and then weighted. The score is a
# prototype analytical metric for comparing scenarios against each other --
# it is NOT a regulatory or industry-standard risk measure.
RISK_WEIGHTS: Dict[str, float] = {
    "breadth": 0.35,     # how much of the network was touched
    "intensity": 0.30,   # how much total force landed on the network
    "peak": 0.20,        # how hard the worst-hit entity was hit
    "reach": 0.15,       # how deep into the network the shock travelled
}

RISK_COMPONENT_LABELS: Dict[str, str] = {
    "breadth": "Breadth (share of network affected)",
    "intensity": "Intensity (total impact vs. shock size)",
    "peak": "Peak (worst single entity vs. shock size)",
    "reach": "Reach (depth travelled vs. depth allowed)",
}


def calculate_risk_score(
    result: SimulationResult, graph: nx.DiGraph
) -> Tuple[float, Dict[str, float]]:
    """Compute an explainable 0-100 systemic risk score.

    Each component is expressed as a fraction of its own theoretical maximum,
    so all four are directly comparable:

      breadth   = affected entities / every other entity in the network
      intensity = total absolute impact / (other entities x shock size)
      peak      = largest single impact / shock size
      reach     = deepest level reached / maximum allowed depth

    score = 100 x (0.35*breadth + 0.30*intensity + 0.20*peak + 0.15*reach)

    Returns:
        (score, breakdown) where breakdown holds each component in 0-1.
    """
    other_nodes = max(graph.number_of_nodes() - 1, 1)
    shock_size = abs(result.magnitude)

    if shock_size == 0 or not result.affected_entities:
        return 0.0, {key: 0.0 for key in RISK_WEIGHTS}

    # Each component is capped at 1 so no single term can dominate the score.
    breakdown = {
        "breadth": min(result.affected_count / other_nodes, 1.0),
        "intensity": min(result.total_impact / (other_nodes * shock_size), 1.0),
        "peak": min(result.max_impact / shock_size, 1.0),
        "reach": min(result.max_level / result.max_depth, 1.0),
    }

    score = 100.0 * sum(RISK_WEIGHTS[key] * value for key, value in breakdown.items())
    return round(score, 1), breakdown


def risk_band(score: float) -> str:
    """Turn a numeric score into a plain-English band for the dashboard."""
    if score >= 70:
        return "Severe"
    if score >= 50:
        return "Elevated"
    if score >= 30:
        return "Moderate"
    return "Contained"


# ---------------------------------------------------------------------------
# TABLE BUILDERS (used by the dashboard)
# ---------------------------------------------------------------------------

def impact_table(result: SimulationResult, graph: nx.DiGraph) -> pd.DataFrame:
    """Rank affected entities by absolute impact, largest first."""
    columns = ["Entity", "Category", "Impact", "Absolute Impact",
               "Level", "Channels In"]
    rows = [
        {
            "Entity": node,
            "Category": graph.nodes[node].get("category", "-"),
            "Impact": result.impacts[node],
            "Absolute Impact": abs(result.impacts[node]),
            "Level": result.levels.get(node, 0),
            # How many separate transmissions landed on this entity.
            "Channels In": sum(1 for e in result.events if e.target == node),
        }
        for node in result.affected_entities
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values("Absolute Impact", ascending=False)
        .reset_index(drop=True)
    )


def pathway_table(result: SimulationResult) -> pd.DataFrame:
    """List every propagation event, shallowest and strongest first."""
    columns = ["Level", "Transmission", "Edge Weight", "Impact",
               "Absolute Impact", "Calculation", "Path"]
    rows = [
        {
            "Level": event.level,
            "Transmission": f"{event.source} -> {event.target}",
            "Edge Weight": event.weight,
            "Impact": event.impact,
            "Absolute Impact": abs(event.impact),
            "Calculation": event.explain(result.damping),
            "Path": " -> ".join(event.path),
        }
        for event in result.events
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values(["Level", "Absolute Impact"], ascending=[True, False])
        .reset_index(drop=True)
    )


def comparison_row(label: str, result: SimulationResult) -> Dict[str, object]:
    """Summarise one run as a single row for the scenario comparison table."""
    return {
        "Scenario": label,
        "Origin": result.origin,
        "Shock": result.magnitude,
        "Risk Score": result.risk_score,
        "Risk Band": risk_band(result.risk_score),
        "Affected Entities": result.affected_count,
        "Propagation Events": result.event_count,
        "Total Impact": result.total_impact,
        "Max Impact": result.max_impact,
        "Depth": result.max_level,
    }
