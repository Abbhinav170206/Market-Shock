"""
app.py
------
MarketShock dashboard: the Streamlit user interface.

This file is deliberately limited to layout and user interaction. The network
lives in network.py, the maths lives in simulation.py, and the charts live in
visualization.py.

Run with:  streamlit run app.py
"""

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

import data
import network
import simulation
import visualization

PAGE_TITLE = "MarketShock"

st.set_page_config(
    page_title=f"{PAGE_TITLE} · Systemic Risk Analysis",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# STYLING
# ---------------------------------------------------------------------------

def inject_styles() -> None:
    """Apply the dark FinTech dashboard theme."""
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(1100px 500px at 12% -10%, #16233f 0%, rgba(0,0,0,0) 60%),
                radial-gradient(900px 500px at 95% 0%, #10243a 0%, rgba(0,0,0,0) 55%),
                #0a0f1c;
        }
        section[data-testid="stSidebar"] {
            background: #0d1526;
            border-right: 1px solid rgba(255,255,255,0.07);
        }
        /* ---- header ---- */
        .ms-header {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 14px;
            padding: 22px 26px;
            margin-bottom: 18px;
            background: linear-gradient(100deg, rgba(56,189,248,0.10), rgba(10,15,28,0.2));
        }
        .ms-title {
            font-size: 34px; font-weight: 700; letter-spacing: -0.5px;
            color: #f2f6ff; margin: 0;
        }
        .ms-title span { color: #38bdf8; }
        .ms-subtitle { color: #8b98b0; font-size: 15px; margin-top: 4px; }
        .ms-tag {
            display: inline-block; margin-top: 12px; padding: 4px 11px;
            border-radius: 999px; font-size: 11.5px; letter-spacing: 0.4px;
            color: #7dd3fc; background: rgba(56,189,248,0.10);
            border: 1px solid rgba(56,189,248,0.30);
        }
        /* ---- metric cards ---- */
        .ms-metric {
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px; padding: 16px 18px; height: 100%;
            background: rgba(255,255,255,0.025);
        }
        .ms-metric-label {
            color: #8b98b0; font-size: 11.5px; letter-spacing: 1.1px;
            text-transform: uppercase; margin-bottom: 6px;
        }
        .ms-metric-value {
            color: #f2f6ff; font-size: 28px; font-weight: 700; line-height: 1.15;
        }
        .ms-metric-note { color: #6f7c94; font-size: 12px; margin-top: 5px; }
        /* ---- section headings ---- */
        .ms-section {
            color: #f2f6ff; font-size: 17px; font-weight: 600;
            margin: 6px 0 2px 0;
        }
        .ms-section-note { color: #8b98b0; font-size: 13px; margin-bottom: 10px; }
        /* ---- propagation pathway cards ---- */
        .ms-path {
            border: 1px solid rgba(255,255,255,0.08);
            border-left: 3px solid #38bdf8;
            border-radius: 10px; padding: 12px 15px; margin-bottom: 9px;
            background: rgba(255,255,255,0.025);
        }
        .ms-path-head {
            display: flex; justify-content: space-between;
            align-items: baseline; gap: 12px; flex-wrap: wrap;
        }
        .ms-path-route { color: #f2f6ff; font-size: 15px; font-weight: 600; }
        .ms-path-impact { color: #f59e0b; font-size: 15px; font-weight: 700; }
        .ms-path-meta { color: #7b88a1; font-size: 12px; margin-top: 5px; }
        .ms-path-meta code {
            background: rgba(56,189,248,0.09); color: #9fd8f7;
            padding: 1px 6px; border-radius: 5px; font-size: 11.5px;
        }
        /* ---- disclaimer ---- */
        .ms-disclaimer {
            border: 1px solid rgba(245,158,11,0.28);
            background: rgba(245,158,11,0.07);
            color: #d5b98a; border-radius: 10px;
            padding: 11px 15px; font-size: 12.5px; margin-top: 22px;
        }
        div[data-testid="stMetricValue"] { color: #f2f6ff; }
        .stTabs [data-baseweb="tab-list"] { gap: 4px; }
        .stTabs [data-baseweb="tab"] { color: #8b98b0; }
        .stTabs [aria-selected="true"] { color: #38bdf8 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, note: str = "") -> str:
    """Return the HTML for one metric tile."""
    return (
        f"<div class='ms-metric'>"
        f"<div class='ms-metric-label'>{label}</div>"
        f"<div class='ms-metric-value'>{value}</div>"
        f"<div class='ms-metric-note'>{note}</div>"
        f"</div>"
    )


def section_heading(title: str, note: str = "") -> None:
    st.markdown(
        f"<div class='ms-section'>{title}</div>"
        f"<div class='ms-section-note'>{note}</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_network():
    """Build the graph once and reuse it across reruns.

    Returns (graph, positions, error_message). The error is returned rather
    than raised so the UI can show a friendly message instead of a traceback.
    """
    try:
        graph = network.build_network()
        return graph, network.get_node_positions(graph), None
    except network.NetworkDataError as exc:
        return None, None, str(exc)


# ---------------------------------------------------------------------------
# SIDEBAR CONTROLS
# ---------------------------------------------------------------------------

def apply_scenario_defaults() -> None:
    """Prefill the origin and magnitude when a preset scenario is chosen.

    Runs as a widget callback, so the new values are in place before the
    controls are drawn again.
    """
    scenario = st.session_state.get("scenario_choice")
    preset = data.SCENARIOS.get(scenario)
    if preset:
        st.session_state["origin_choice"] = preset["origin"]
        st.session_state["magnitude_pct"] = float(preset["magnitude"]) * 100


def render_sidebar(node_names: List[str]) -> Dict[str, object]:
    """Draw every control and return the current settings as a dictionary."""
    st.sidebar.markdown("### ⚙️ Simulation Controls")

    scenario_options = [data.CUSTOM_SCENARIO_LABEL] + list(data.SCENARIOS)
    scenario = st.sidebar.selectbox(
        "Scenario",
        scenario_options,
        index=scenario_options.index("Energy Shock"),
        key="scenario_choice",
        on_change=apply_scenario_defaults,
        help="Pick a predefined scenario, or build your own with the controls below.",
    )

    preset = data.SCENARIOS.get(scenario)
    if preset:
        st.sidebar.caption(f"📄 {preset['description']}")

    # Seed the widgets on first load so the app opens with a working run.
    if "origin_choice" not in st.session_state:
        st.session_state["origin_choice"] = (
            preset["origin"] if preset else node_names[0]
        )
    if "magnitude_pct" not in st.session_state:
        st.session_state["magnitude_pct"] = (
            float(preset["magnitude"]) * 100 if preset else 20.0
        )

    st.sidebar.markdown("---")

    origin = st.sidebar.selectbox(
        "Shock origin",
        node_names,
        key="origin_choice",
        help="The entity where the disruption starts.",
    )
    magnitude_pct = st.sidebar.slider(
        "Shock magnitude (%)",
        min_value=-50.0, max_value=50.0, step=0.5,
        key="magnitude_pct",
        help="Signed size of the initial shock. Negative means a decline.",
    )

    with st.sidebar.expander("Engine settings", expanded=False):
        damping = st.slider(
            "Damping factor", 0.05, 1.0, simulation.DEFAULT_DAMPING, 0.05,
            help="Share of the force retained at each additional hop.",
        )
        threshold_pct = st.slider(
            "Propagation threshold (%)", 0.1, 10.0,
            simulation.DEFAULT_THRESHOLD * 100, 0.1,
            help="Impacts smaller than this stop travelling further.",
        )
        max_depth = st.slider(
            "Maximum depth", 1, 8, simulation.DEFAULT_MAX_DEPTH, 1,
            help="How many hops away from the origin the shock may travel.",
        )

    st.sidebar.markdown("---")
    run_clicked = st.sidebar.button(
        "▶  Run Simulation", type="primary", width="stretch"
    )
    save_clicked = st.sidebar.button(
        "＋  Save to Comparison", width="stretch"
    )
    if st.sidebar.button("Clear saved scenarios", width="stretch"):
        st.session_state["comparison_runs"] = []

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Network data is an illustrative / controlled prototype network, "
        "not real exposure data."
    )

    return {
        "scenario": scenario,
        "origin": origin,
        "magnitude": magnitude_pct / 100.0,
        "damping": damping,
        "threshold": threshold_pct / 100.0,
        "max_depth": max_depth,
        "run_clicked": run_clicked,
        "save_clicked": save_clicked,
    }


# ---------------------------------------------------------------------------
# SIMULATION HANDLING
# ---------------------------------------------------------------------------

def settings_signature(settings: Dict[str, object]) -> tuple:
    """The subset of settings that actually changes a simulation's output."""
    return (
        settings["origin"], settings["magnitude"], settings["damping"],
        settings["threshold"], settings["max_depth"],
    )


def describe_run(scenario: str, result: simulation.SimulationResult) -> str:
    """Name a run for the comparison table.

    The preset's own name is only used when the run still matches that preset.
    Once the user edits the origin or magnitude it is no longer, say, the
    Energy Shock, so it is named after what was actually simulated.
    """
    preset = data.SCENARIOS.get(scenario)
    matches_preset = (
        preset is not None
        and preset["origin"] == result.origin
        and abs(float(preset["magnitude"]) - result.magnitude) < 1e-9
    )
    if matches_preset:
        return scenario
    return f"{result.origin} {result.magnitude:+.1%}"


def run_simulation(graph, settings: Dict[str, object]):
    """Run the engine, converting any bad input into a UI message.

    Returns (result, error_message).
    """
    try:
        result = simulation.simulate_shock(
            graph,
            origin=str(settings["origin"]),
            magnitude=float(settings["magnitude"]),
            damping=float(settings["damping"]),
            threshold=float(settings["threshold"]),
            max_depth=int(settings["max_depth"]),
        )
        return result, None
    except (ValueError, KeyError) as exc:
        return None, str(exc)


# ---------------------------------------------------------------------------
# PAGE SECTIONS
# ---------------------------------------------------------------------------

def render_header() -> None:
    st.markdown(
        f"""
        <div class="ms-header">
            <div class="ms-title">Market<span>Shock</span></div>
            <div class="ms-subtitle">
                Financial Market Shock Propagation &amp; Systemic Risk Analysis
            </div>
            <div class="ms-tag">ILLUSTRATIVE / CONTROLLED PROTOTYPE NETWORK</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(result: simulation.SimulationResult, graph) -> None:
    """Draw the top row of headline metrics."""
    band = simulation.risk_band(result.risk_score)
    worst = result.most_affected or "—"
    worst_value = (
        f"{result.impacts[worst]:+.2%}" if worst in result.impacts else "—"
    )
    total_others = graph.number_of_nodes() - 1

    tiles = [
        metric_card("Systemic Risk", f"{result.risk_score:g}", f"{band} · out of 100"),
        metric_card("Shock Applied", f"{result.magnitude:+.1%}", f"Origin: {result.origin}"),
        metric_card("Affected Entities", f"{result.affected_count}",
                    f"of {total_others} other entities"),
        metric_card("Propagation Events", f"{result.event_count}",
                    f"Max depth reached: level {result.max_level}"),
        metric_card("Largest Single Impact", worst_value, f"{worst}"),
    ]
    for column, tile in zip(st.columns(5), tiles):
        column.markdown(tile, unsafe_allow_html=True)


def render_impact_tab(result, graph) -> None:
    impact_df = simulation.impact_table(result, graph)

    if impact_df.empty:
        st.info(
            "No entity was affected. The shock was either too small to clear "
            "the propagation threshold, or the origin has no outgoing "
            "relationships in this network."
        )
        return

    left, right = st.columns([1.15, 1])

    with left:
        section_heading(
            "Most Affected Entities",
            "Ranked by the absolute impact each entity absorbed.",
        )
        st.plotly_chart(
            visualization.create_impact_bar(impact_df),
            width="stretch",
            config={"displayModeBar": False},
        )

    with right:
        section_heading(
            "Impact Detail",
            "Level is the shortest number of hops from the shock origin. "
            "Channels In counts how many separate transmissions landed on the entity.",
        )
        display = impact_df.copy()
        display["Impact"] = display["Impact"] * 100
        display = display.drop(columns=["Absolute Impact"])
        st.dataframe(
            display,
            width="stretch",
            hide_index=True,
            column_config={
                "Impact": st.column_config.NumberColumn(
                    "Impact", format="%+.2f%%",
                    help="Signed impact absorbed by this entity.",
                ),
                "Level": st.column_config.NumberColumn("Level", format="%d"),
                "Channels In": st.column_config.NumberColumn(
                    "Channels In", format="%d"
                ),
            },
        )

    section_heading(
        "Systemic Risk Score Breakdown",
        "Blue shows the points each component contributed; grey shows the "
        "maximum that component could contribute.",
    )
    st.plotly_chart(
        visualization.create_risk_breakdown(result.risk_breakdown),
        width="stretch",
        config={"displayModeBar": False},
    )


def render_pathways_tab(result) -> None:
    """Show individual propagation events, grouped by level."""
    if not result.events:
        st.info(
            "No propagation events were generated. Try a larger shock "
            "magnitude, a lower threshold, or an origin with outgoing links."
        )
        return

    if result.truncated:
        st.warning(
            f"The run hit the safety limit of {simulation.MAX_EVENTS} events "
            "and stopped early. Raise the threshold or lower the maximum "
            "depth for a cleaner result."
        )

    pathways = simulation.pathway_table(result)
    levels = sorted(pathways["Level"].unique())

    chosen = st.multiselect(
        "Filter by propagation level",
        options=levels,
        default=levels,
        help="Level 1 events come directly from the shock origin.",
    )
    filtered = pathways[pathways["Level"].isin(chosen)] if chosen else pathways.iloc[0:0]

    if filtered.empty:
        st.info("No propagation events match the selected levels.")
        return

    st.caption(f"Showing {len(filtered)} of {len(pathways)} propagation events.")

    for level in sorted(filtered["Level"].unique()):
        level_events = filtered[filtered["Level"] == level]
        st.markdown(
            f"<div class='ms-section'>Level {level} "
            f"<span style='color:#6f7c94;font-size:13px'>"
            f"· {len(level_events)} events</span></div>",
            unsafe_allow_html=True,
        )
        for _, row in level_events.iterrows():
            st.markdown(
                f"""
                <div class="ms-path">
                    <div class="ms-path-head">
                        <span class="ms-path-route">{row['Transmission']}</span>
                        <span class="ms-path-impact">{row['Impact']:+.2%}</span>
                    </div>
                    <div class="ms-path-meta">
                        <code>{row['Calculation']}</code>
                        &nbsp;·&nbsp; Route: {row['Path']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_comparison_tab(runs: List[Dict[str, object]]) -> None:
    """Compare the scenarios the user has saved during this session."""
    section_heading(
        "Scenario Comparison",
        "Use “Save to Comparison” in the sidebar to add the current run, "
        "then compare scenarios side by side.",
    )

    if not runs:
        st.info(
            "No saved scenarios yet. Run a scenario and press "
            "“＋ Save to Comparison” in the sidebar."
        )
        return

    comparison_df = pd.DataFrame(runs)

    display = comparison_df.copy()
    for column in ("Shock", "Total Impact", "Max Impact"):
        display[column] = display[column] * 100

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "Shock": st.column_config.NumberColumn("Shock", format="%+.1f%%"),
            "Total Impact": st.column_config.NumberColumn(
                "Total Impact", format="%.2f%%",
                help="Sum of absolute impact across all affected entities.",
            ),
            "Max Impact": st.column_config.NumberColumn(
                "Max Impact", format="%.2f%%"
            ),
            "Risk Score": st.column_config.NumberColumn(
                "Risk Score", format="%.1f"
            ),
        },
    )

    metric = st.selectbox(
        "Compare on",
        ["Risk Score", "Affected Entities", "Total Impact",
         "Propagation Events", "Max Impact", "Depth"],
    )
    st.plotly_chart(
        visualization.create_comparison_chart(comparison_df, metric),
        width="stretch",
        config={"displayModeBar": False},
    )


def render_network_tab(graph) -> None:
    left, right = st.columns(2)
    with left:
        section_heading(
            "Entities",
            "Outgoing exposure is the summed weight of a node's outgoing "
            "links; incoming exposure is the same for links pointing at it.",
        )
        st.dataframe(
            network.node_summary_table(graph),
            width="stretch", hide_index=True,
        )
    with right:
        section_heading(
            "Relationships",
            "Every directed dependency and its weight, as defined in data.py.",
        )
        st.dataframe(
            network.edge_table(graph),
            width="stretch", hide_index=True,
            column_config={
                "Weight": st.column_config.ProgressColumn(
                    "Weight", min_value=0.0, max_value=1.0, format="%.2f"
                )
            },
        )


def render_methodology_tab(result) -> None:
    st.markdown(
        f"""
#### How propagation works

Starting at the shock origin, the engine walks outwards one hop at a time.
For every relationship it crosses:

```
delivered impact = incoming impact × relationship weight × damping factor
```

A route stops when the delivered impact falls below the **threshold**
(currently {result.threshold:.2%}), when it reaches the **maximum depth**
(currently {result.max_depth}), or when it would revisit an entity it has
already passed through. An entity's reported impact is the **sum** of
everything delivered to it from every route, so entities fed by several
channels accumulate more.

The algorithm is fully deterministic: the same inputs always produce the
same output, and every number in this dashboard traces back to one
multiplication.

#### How the systemic risk score works

Four components, each normalised to a 0–1 fraction of its own maximum:

| Component | Definition | Weight |
|---|---|---|
| Breadth | affected entities ÷ all other entities | 0.35 |
| Intensity | total absolute impact ÷ (other entities × shock size) | 0.30 |
| Peak | largest single impact ÷ shock size | 0.20 |
| Reach | deepest level reached ÷ maximum allowed depth | 0.15 |

```
score = 100 × (0.35·breadth + 0.30·intensity + 0.20·peak + 0.15·reach)
```

Bands: 0–30 Contained · 30–50 Moderate · 50–70 Elevated · 70–100 Severe.

#### Limitations

* The network is hand-authored and illustrative — it is not estimated from
  market data and does not represent real institutional exposures.
* Relationships are treated as linear and instantaneous; real transmission
  is non-linear, lagged, and changes over time.
* The sign of a shock is carried through unchanged, which assumes every
  downstream entity moves in the same direction as its upstream driver.
* The risk score is a prototype comparison metric, not a regulatory or
  industry-standard measure.
        """
    )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    inject_styles()
    render_header()

    graph, positions, load_error = load_network()
    if load_error or graph is None:
        st.error(f"The financial network could not be loaded: {load_error}")
        st.caption("Check the NODE_CATEGORIES and EDGES definitions in data.py.")
        st.stop()

    node_names = network.list_nodes(graph)
    settings = render_sidebar(node_names)

    st.session_state.setdefault("comparison_runs", [])
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("result_signature", None)

    # Run on the very first load so the dashboard is never empty, and again
    # whenever the user presses the Run button.
    if settings["run_clicked"] or st.session_state["result"] is None:
        result, run_error = run_simulation(graph, settings)
        if run_error:
            st.error(f"The simulation could not run: {run_error}")
            st.stop()
        st.session_state["result"] = result
        st.session_state["result_signature"] = settings_signature(settings)

    result: Optional[simulation.SimulationResult] = st.session_state["result"]

    # Saving happens after the run above, so the saved row always matches
    # what is currently on screen.
    if settings["save_clicked"] and result is not None:
        label = describe_run(str(settings["scenario"]), result)
        existing = {row["Scenario"] for row in st.session_state["comparison_runs"]}
        if label in existing:
            st.toast(f"“{label}” is already saved.")
        else:
            st.session_state["comparison_runs"].append(
                simulation.comparison_row(label, result)
            )
            st.toast(f"Saved “{label}” to the comparison.")

    # Tell the user when the controls no longer match the displayed run.
    if st.session_state["result_signature"] != settings_signature(settings):
        st.info(
            "Controls have changed. Press **▶ Run Simulation** in the sidebar "
            "to update the results below.",
            icon="🔄",
        )

    render_metrics(result, graph)
    st.write("")

    section_heading(
        "Financial Network Propagation Map",
        "Gold diamond = shock origin · larger, warmer nodes absorbed more "
        "impact · bright edges carried the shock · grey nodes were untouched. "
        "Hover any node or link for detail.",
    )
    st.plotly_chart(
        visualization.create_network_figure(graph, positions, result),
        width="stretch",
        config={"displayModeBar": False},
    )

    impact_tab, pathways_tab, comparison_tab, network_tab, method_tab = st.tabs(
        ["📊 Impact Analysis", "🔀 Propagation Pathways", "⚖️ Scenario Comparison",
         "🕸️ Network Data", "📘 Methodology"]
    )
    with impact_tab:
        render_impact_tab(result, graph)
    with pathways_tab:
        render_pathways_tab(result)
    with comparison_tab:
        render_comparison_tab(st.session_state["comparison_runs"])
    with network_tab:
        render_network_tab(graph)
    with method_tab:
        render_methodology_tab(result)

    st.markdown(
        f"<div class='ms-disclaimer'>⚠️ {data.DISCLAIMER}</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
