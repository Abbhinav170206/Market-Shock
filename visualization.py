"""
visualization.py
----------------
Every Plotly chart used by the dashboard is built here, so app.py stays
focused on layout and user interaction.

All charts share one dark "financial terminal" palette defined at the top.
"""

from typing import Dict, Optional, Tuple

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

from simulation import RISK_COMPONENT_LABELS, RISK_WEIGHTS, SimulationResult

# --- Shared palette --------------------------------------------------------
BACKGROUND = "rgba(0,0,0,0)"
GRID_TEXT = "#8b98b0"
LABEL_TEXT = "#e8edf7"
IDLE_NODE = "#3a4560"        # entity the shock never reached
IDLE_EDGE = "rgba(120,134,163,0.28)"
ORIGIN_COLOR = "#facc15"     # the shock origin, always gold
ACCENT = "#38bdf8"

# Low -> high impact. Used for both node fill and active edge colour.
IMPACT_SCALE = [
    (0.00, "#2dd4bf"),
    (0.35, "#38bdf8"),
    (0.65, "#f59e0b"),
    (1.00, "#ef4444"),
]

# Gaps in data-coordinates left between a marker and the line touching it, so
# arrowheads stay visible and lines do not converge inside a node.
TARGET_GAP = 0.32
SOURCE_GAP = 0.24

# Active edges never drop below this colour intensity, so a weak-but-real
# transmission still reads as active rather than as an unused link.
MIN_ACTIVE_INTENSITY = 0.18


def _interpolate_color(fraction: float) -> str:
    """Pick a colour from IMPACT_SCALE for a 0-1 intensity value."""
    fraction = min(max(fraction, 0.0), 1.0)

    for i in range(len(IMPACT_SCALE) - 1):
        low_stop, low_color = IMPACT_SCALE[i]
        high_stop, high_color = IMPACT_SCALE[i + 1]
        if low_stop <= fraction <= high_stop:
            span = high_stop - low_stop
            local = 0.0 if span == 0 else (fraction - low_stop) / span
            return _blend(low_color, high_color, local)

    return IMPACT_SCALE[-1][1]


def _blend(hex_a: str, hex_b: str, ratio: float) -> str:
    """Blend two hex colours; ratio 0 returns hex_a, 1 returns hex_b."""
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    mixed = [round(a[i] + (b[i] - a[i]) * ratio) for i in range(3)]
    return f"rgb({mixed[0]},{mixed[1]},{mixed[2]})"


def _shorten(
    start: Tuple[float, float], end: Tuple[float, float], gap: float
) -> Tuple[float, float]:
    """Pull `end` back toward `start` by `gap`, so arrowheads stay visible."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = (dx ** 2 + dy ** 2) ** 0.5
    if length <= gap:
        return end
    scale = (length - gap) / length
    return start[0] + dx * scale, start[1] + dy * scale


def create_network_figure(
    graph: nx.DiGraph,
    positions: Dict[str, Tuple[float, float]],
    result: Optional[SimulationResult] = None,
) -> go.Figure:
    """Draw the financial network, highlighting a simulation if one is given.

    Visual encoding:
      * the shock origin is a large gold diamond
      * affected entities are circles sized and coloured by absolute impact
      * untouched entities stay small and grey
      * edges that actually carried impact are drawn bright and thick; the
        rest fade into the background

    Args:
        graph: the weighted directed network.
        positions: fixed (x, y) coordinates per node.
        result: an optional simulation to overlay. Without one, the plain
            network structure is drawn.
    """
    impacts = result.impacts if result else {}
    # Scale sizes/colours against the worst-hit entity in this run.
    peak = max((abs(v) for v in impacts.values()), default=0.0) or 1.0

    # Which edges carried impact, and how much (largest transmission wins).
    active_edges: Dict[Tuple[str, str], float] = {}
    if result:
        for event in result.events:
            key = (event.source, event.target)
            active_edges[key] = max(active_edges.get(key, 0.0), abs(event.impact))

    figure = go.Figure()
    annotations = []
    hover_x, hover_y, hover_text = [], [], []

    for source, target, edge_data in graph.edges(data=True):
        if source not in positions or target not in positions:
            continue

        start, end = positions[source], positions[target]
        # Trim both ends so the line runs between the markers, not through them.
        tail = _shorten(end, start, SOURCE_GAP)
        tip = _shorten(start, end, TARGET_GAP)
        carried = active_edges.get((source, target))

        if carried is not None:
            intensity = min(carried / peak, 1.0)
            color = _interpolate_color(max(intensity, MIN_ACTIVE_INTENSITY))
            width = 2.0 + 3.2 * intensity
            opacity = 0.95
        else:
            color, width, opacity = IDLE_EDGE, 1.2, 0.55

        annotations.append(
            dict(
                x=tip[0], y=tip[1], ax=tail[0], ay=tail[1],
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowsize=1.1,
                arrowwidth=width, arrowcolor=color, opacity=opacity,
            )
        )

        # Invisible midpoint marker so the edge itself is hoverable.
        hover_x.append((start[0] + end[0]) / 2)
        hover_y.append((start[1] + end[1]) / 2)
        carried_text = (
            f"<br>Impact carried: {carried:.2%}" if carried is not None
            else "<br>Not activated in this scenario"
        )
        hover_text.append(
            f"<b>{source} → {target}</b><br>"
            f"Relationship weight: {edge_data['weight']:.2f}{carried_text}"
        )

    figure.add_trace(
        go.Scatter(
            x=hover_x, y=hover_y, mode="markers",
            marker=dict(size=14, color="rgba(0,0,0,0)"),
            hoverinfo="text", hovertext=hover_text,
            showlegend=False, name="Relationships",
        )
    )

    # --- Nodes -------------------------------------------------------------
    node_x, node_y, labels, colors, sizes, symbols = [], [], [], [], [], []
    borders, texts, positions_text = [], [], []

    for node in graph.nodes:
        if node not in positions:
            continue
        x, y = positions[node]
        node_x.append(x)
        node_y.append(y)

        # Labels sit above nodes in the top half and below in the bottom half,
        # which keeps them clear of the edges. The blank spacer line pushes the
        # name away from the marker so large nodes do not cover their own text.
        if y >= 0:
            labels.append(f"{node}<br>&nbsp;")
            positions_text.append("top center")
        else:
            labels.append(f"&nbsp;<br>{node}")
            positions_text.append("bottom center")

        impact = impacts.get(node)
        is_origin = bool(result) and node == result.origin

        if is_origin:
            colors.append(ORIGIN_COLOR)
            sizes.append(46)
            symbols.append("diamond")
            borders.append("#ffffff")
        elif impact is not None:
            intensity = abs(impact) / peak
            colors.append(_interpolate_color(intensity))
            sizes.append(24 + 30 * intensity)
            symbols.append("circle")
            borders.append("rgba(255,255,255,0.85)")
        else:
            colors.append(IDLE_NODE)
            sizes.append(20)
            symbols.append("circle")
            borders.append("rgba(255,255,255,0.25)")

        detail = graph.nodes[node].get("description", "")
        if is_origin:
            status = f"<b>SHOCK ORIGIN</b><br>Applied shock: {impact:+.2%}"
        elif impact is not None:
            level = result.levels.get(node, 0)
            status = f"Impact: {impact:+.2%}<br>Reached at level {level}"
        else:
            status = "Not affected in this scenario"

        texts.append(
            f"<b>{node}</b><br>{graph.nodes[node].get('category', '')}<br>"
            f"{status}<br><span style='font-size:11px'>{detail}</span>"
        )

    figure.add_trace(
        go.Scatter(
            x=node_x, y=node_y, mode="markers+text",
            text=labels, textposition=positions_text,
            textfont=dict(color=LABEL_TEXT, size=12, family="Inter, sans-serif"),
            marker=dict(
                size=sizes, color=colors, symbol=symbols,
                line=dict(width=2, color=borders),
            ),
            hoverinfo="text", hovertext=texts,
            showlegend=False, name="Entities",
        )
    )

    figure.update_layout(
        annotations=annotations,
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=30),
        height=580,
        paper_bgcolor=BACKGROUND,
        plot_bgcolor=BACKGROUND,
        hoverlabel=dict(
            bgcolor="#111a2e", bordercolor=ACCENT,
            font=dict(color=LABEL_TEXT, size=12),
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=_axis_range([p[0] for p in positions.values()], 0.9)),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=_axis_range([p[1] for p in positions.values()], 1.2)),
    )
    return figure


def _axis_range(values, padding: float):
    """Return a padded [min, max] range so labels are not clipped."""
    if not values:
        return [-1, 1]
    return [min(values) - padding, max(values) + padding]


def create_risk_gauge(score: float, band: str) -> go.Figure:
    """Draw the systemic risk score as a 0-100 gauge."""
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number=dict(font=dict(size=40, color=LABEL_TEXT), suffix=""),
            title=dict(
                text=f"<span style='font-size:13px;color:{GRID_TEXT}'>"
                     f"SYSTEMIC RISK · {band.upper()}</span>"
            ),
            gauge=dict(
                axis=dict(range=[0, 100], tickcolor=GRID_TEXT,
                          tickfont=dict(color=GRID_TEXT, size=10)),
                bar=dict(color=_interpolate_color(score / 100), thickness=0.7),
                bgcolor="rgba(255,255,255,0.04)",
                borderwidth=0,
                steps=[
                    dict(range=[0, 30], color="rgba(45,212,191,0.12)"),
                    dict(range=[30, 50], color="rgba(56,189,248,0.12)"),
                    dict(range=[50, 70], color="rgba(245,158,11,0.14)"),
                    dict(range=[70, 100], color="rgba(239,68,68,0.16)"),
                ],
            ),
        )
    )
    figure.update_layout(
        height=240, margin=dict(l=20, r=20, t=50, b=10),
        paper_bgcolor=BACKGROUND, font=dict(color=LABEL_TEXT),
    )
    return figure


def create_impact_bar(impact_df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    """Horizontal bar chart of the most affected entities."""
    figure = go.Figure()
    if impact_df.empty:
        return _empty_figure("No entities were affected by this shock.")

    top = impact_df.head(top_n).iloc[::-1]  # reversed so the largest sits on top
    peak = top["Absolute Impact"].max() or 1.0
    colors = [_interpolate_color(v / peak) for v in top["Absolute Impact"]]

    figure.add_trace(
        go.Bar(
            x=top["Absolute Impact"], y=top["Entity"], orientation="h",
            marker=dict(color=colors),
            text=[f"{v:+.2%}" for v in top["Impact"]],
            textposition="outside",
            textfont=dict(color=LABEL_TEXT, size=12),
            hovertemplate="<b>%{y}</b><br>Impact: %{customdata:+.2%}<extra></extra>",
            customdata=top["Impact"],
        )
    )
    figure.update_layout(
        height=max(260, 42 * len(top)),
        margin=dict(l=10, r=60, t=20, b=30),
        paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        font=dict(color=LABEL_TEXT),
        xaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.06)",
            tickformat=".0%", tickfont=dict(color=GRID_TEXT),
            # Extra headroom so the value label on the longest bar is not clipped.
            range=[0, peak * 1.25],
            title=dict(text="Absolute impact", font=dict(color=GRID_TEXT, size=11)),
        ),
        yaxis=dict(showgrid=False, tickfont=dict(color=LABEL_TEXT, size=12)),
    )
    return figure


def create_risk_breakdown(breakdown: Dict[str, float]) -> go.Figure:
    """Show how each weighted component contributed to the risk score."""
    if not breakdown or all(value == 0 for value in breakdown.values()):
        return _empty_figure("No risk components to display.")

    keys = list(RISK_WEIGHTS)
    contributions = [100 * RISK_WEIGHTS[k] * breakdown.get(k, 0.0) for k in keys]
    maximums = [100 * RISK_WEIGHTS[k] for k in keys]
    labels = [RISK_COMPONENT_LABELS[k] for k in keys]

    figure = go.Figure()
    # Grey bars show each component's maximum possible contribution.
    figure.add_trace(
        go.Bar(
            x=maximums, y=labels, orientation="h",
            marker=dict(color="rgba(255,255,255,0.13)"),
            hoverinfo="skip", showlegend=False,
        )
    )
    figure.add_trace(
        go.Bar(
            x=contributions, y=labels, orientation="h",
            marker=dict(color=ACCENT), width=0.45,
            text=[f"{c:.1f}" for c in contributions],
            textposition="outside", textfont=dict(color=LABEL_TEXT, size=11),
            hovertemplate="<b>%{y}</b><br>Contributes %{x:.1f} points<extra></extra>",
            showlegend=False,
        )
    )
    figure.update_layout(
        barmode="overlay", height=240,
        margin=dict(l=10, r=50, t=20, b=30),
        paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        font=dict(color=LABEL_TEXT),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)",
                   tickfont=dict(color=GRID_TEXT),
                   title=dict(text="Points contributed (out of 100)",
                              font=dict(color=GRID_TEXT, size=11))),
        yaxis=dict(showgrid=False, tickfont=dict(color=LABEL_TEXT, size=11)),
    )
    return figure


def create_comparison_chart(comparison_df: pd.DataFrame, metric: str) -> go.Figure:
    """Compare a chosen metric across several saved scenario runs."""
    if comparison_df.empty or metric not in comparison_df:
        return _empty_figure("Run at least one scenario to compare.")

    values = comparison_df[metric]
    peak = values.abs().max() or 1.0
    colors = [_interpolate_color(abs(v) / peak) for v in values]
    is_percentage = metric in ("Total Impact", "Max Impact", "Shock")
    text = [f"{v:.2%}" if is_percentage else f"{v:g}" for v in values]

    figure = go.Figure(
        go.Bar(
            x=comparison_df["Scenario"], y=values,
            # A fixed bar width stops a single saved scenario from being drawn
            # as one enormous block filling the whole chart.
            marker=dict(color=colors), text=text, width=0.38,
            textposition="outside", textfont=dict(color=LABEL_TEXT, size=12),
            hovertemplate="<b>%{x}</b><br>" + metric + ": %{text}<extra></extra>",
        )
    )
    figure.update_layout(
        height=330, margin=dict(l=10, r=10, t=30, b=40),
        paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        font=dict(color=LABEL_TEXT),
        xaxis=dict(showgrid=False, tickfont=dict(color=LABEL_TEXT, size=11)),
        yaxis=dict(
            showgrid=True, gridcolor="rgba(255,255,255,0.06)",
            tickfont=dict(color=GRID_TEXT),
            tickformat=".0%" if is_percentage else None,
            # Headroom so the label above the tallest bar stays inside the
            # chart. min(0, ...) keeps the baseline visible if a metric ever
            # carries negative values.
            range=[min(0.0, float(values.min()) * 1.2), float(peak) * 1.2],
            title=dict(text=metric, font=dict(color=GRID_TEXT, size=11)),
        ),
    )
    return figure


def _empty_figure(message: str) -> go.Figure:
    """A blank chart carrying an explanatory message instead of an error."""
    figure = go.Figure()
    figure.add_annotation(
        text=message, showarrow=False,
        font=dict(color=GRID_TEXT, size=13),
        xref="paper", yref="paper", x=0.5, y=0.5,
    )
    figure.update_layout(
        height=240, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor=BACKGROUND, plot_bgcolor=BACKGROUND,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return figure
