"""
smoke_test.py
-------------
A plain-Python check of the network, the propagation engine and the charts,
with no Streamlit involved.

This exists so the team can verify the maths in a few seconds -- and prove to
judges that the engine is deterministic -- without launching the dashboard.

Run with:  python smoke_test.py
"""

import data
import network
import simulation
import visualization


def check(condition: bool, message: str) -> None:
    """Print a pass/fail line and raise on failure."""
    print(f"  [{'PASS' if condition else 'FAIL'}] {message}")
    if not condition:
        raise AssertionError(message)


def main() -> None:
    print("\n1. Network construction")
    graph = network.build_network()
    positions = network.get_node_positions(graph)
    check(graph.number_of_nodes() == 10, "10 entities loaded")
    check(graph.number_of_edges() == 17, "17 relationships loaded")
    check(len(positions) == graph.number_of_nodes(), "every entity has a position")
    check(
        all(0 < d["weight"] <= 1 for _, _, d in graph.edges(data=True)),
        "all weights are within (0, 1]",
    )

    print("\n2. Predefined scenarios")
    for name, preset in data.SCENARIOS.items():
        result = simulation.simulate_shock(
            graph, str(preset["origin"]), float(preset["magnitude"])
        )
        print(
            f"  {name:<20} origin={result.origin:<14} "
            f"shock={result.magnitude:+.0%}  risk={result.risk_score:>5.1f} "
            f"({simulation.risk_band(result.risk_score):<9}) "
            f"affected={result.affected_count}  events={result.event_count}  "
            f"depth={result.max_level}"
        )
        check(0 <= result.risk_score <= 100, f"{name}: risk score within 0-100")

    print("\n3. Manual arithmetic check (Crude Oil +20% -> Airlines)")
    result = simulation.simulate_shock(graph, "Crude Oil", 0.20)
    first = next(e for e in result.events if e.target == "Airlines")
    expected = 0.20 * 0.70 * simulation.DEFAULT_DAMPING  # 0.119
    check(abs(first.impact - expected) < 1e-9, f"impact equals {expected:.4f}")
    print(f"       {first.explain(result.damping)}")

    print("\n4. Determinism")
    again = simulation.simulate_shock(graph, "Crude Oil", 0.20)
    check(result.impacts == again.impacts, "identical impacts across runs")
    check(result.risk_score == again.risk_score, "identical risk score across runs")
    check(
        [(e.source, e.target, e.impact) for e in result.events]
        == [(e.source, e.target, e.impact) for e in again.events],
        "identical event sequence across runs",
    )

    print("\n5. Edge cases")
    zero = simulation.simulate_shock(graph, "Crude Oil", 0.0)
    check(zero.affected_count == 0 and zero.risk_score == 0.0, "zero shock is inert")

    sink = simulation.simulate_shock(graph, "Market Index", -0.30)
    check(sink.affected_count == 0, "terminal entity produces no propagation")

    tiny = simulation.simulate_shock(graph, "Crude Oil", 0.005)
    check(tiny.event_count == 0, "shock below the threshold does not propagate")

    negative = simulation.simulate_shock(graph, "Banks", -0.15)
    check(
        all(v <= 0 for v in negative.impacts.values()),
        "a negative shock stays negative downstream",
    )

    for bad_call, label in [
        (lambda: simulation.simulate_shock(graph, "Nonexistent", 0.2), "unknown origin"),
        (lambda: simulation.simulate_shock(graph, "Banks", 0.2, damping=0), "damping of 0"),
        (lambda: simulation.simulate_shock(graph, "Banks", 0.2, max_depth=0), "depth of 0"),
    ]:
        try:
            bad_call()
            check(False, f"{label} raises ValueError")
        except ValueError:
            check(True, f"{label} raises ValueError")

    print("\n6. Tables and charts build")
    impacts = simulation.impact_table(result, graph)
    paths = simulation.pathway_table(result)
    check(not impacts.empty, "impact table has rows")
    check(len(paths) == result.event_count, "pathway table matches event count")
    check(simulation.impact_table(zero, graph).empty, "empty result yields empty table")

    visualization.create_network_figure(graph, positions, result)
    visualization.create_network_figure(graph, positions, None)
    visualization.create_risk_gauge(result.risk_score, simulation.risk_band(result.risk_score))
    visualization.create_impact_bar(impacts)
    visualization.create_impact_bar(simulation.impact_table(zero, graph))
    visualization.create_risk_breakdown(result.risk_breakdown)
    import pandas as pd

    comparison = pd.DataFrame([simulation.comparison_row("Energy Shock", result)])
    visualization.create_comparison_chart(comparison, "Risk Score")
    visualization.create_comparison_chart(pd.DataFrame(), "Risk Score")
    check(True, "all figures built without error")

    print("\nAll checks passed.\n")


if __name__ == "__main__":
    main()
