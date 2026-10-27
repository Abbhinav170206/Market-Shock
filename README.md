# MarketShock

**Financial Market Shock Propagation & Systemic Risk Analysis**

Team: *Works on my machine*

---

> ⚠️ **Read this first.** MarketShock is a scenario-analysis prototype built on an
> **illustrative / controlled prototype network**. The entities and relationship
> weights are hand-authored for demonstration; they are **not** real institutional
> exposure data and are not estimated from market data. Results are simulations of
> a hypothetical shock travelling through that network — **not** financial
> predictions, not forecasts of market crashes, and not investment advice.

---

## 1. Problem Statement

Financial markets are deeply interconnected. A disruption in one asset, sector or
economic factor can create cascading effects across other parts of the financial
ecosystem. Traditional market dashboards focus on individual indicators, which
makes it hard to see **how interconnected shocks propagate** and **where systemic
vulnerabilities emerge**.

## 2. Solution

MarketShock models a financial ecosystem as a **weighted directed graph** and lets
a user introduce a hypothetical shock at any entity. The application then:

1. propagates the shock through the network along dependency relationships,
2. identifies which entities are affected and how badly,
3. computes an explainable 0–100 systemic risk score,
4. visualises the propagation as an interactive network map, and
5. shows every individual transmission so the result can be audited by hand.

Explainability is the point: every number on screen traces back to a single
multiplication that a judge can verify with a calculator.

## 3. Features

| Feature | What it does |
|---|---|
| **Interactive network map** | Plotly graph with directed arrows, hover detail, impact-scaled nodes and a clearly marked shock origin. |
| **Shock input** | Choose any origin entity and a signed magnitude from −50% to +50%. |
| **Predefined scenarios** | Five ready-to-demo scenarios, selectable in one click. |
| **Propagation engine** | Deterministic breadth-first cascade with configurable damping, threshold and depth. |
| **Systemic risk score** | Explainable 0–100 metric with a component-by-component breakdown chart. |
| **Impact analysis** | Ranked chart and table of the most affected entities. |
| **Propagation pathways** | Every transmission listed with its arithmetic and full route, filterable by level. |
| **Scenario comparison** | Save multiple runs and compare risk score, affected entities, total impact and depth. |
| **Network data view** | Full entity and relationship tables, including incoming/outgoing exposure. |
| **Methodology tab** | The formulas and limitations, in the app itself. |

## 4. Architecture

```
User (browser)
      │
      ▼
   app.py            ← layout, controls, session state, error messages
      │
      ├─► network.py        ← builds + validates the weighted directed graph
      │         │
      │         └─► data.py ← all entities, relationships and scenarios
      │
      ├─► simulation.py     ← propagation engine + systemic risk score + tables
      │
      └─► visualization.py  ← every Plotly chart
```

Each file has one responsibility, so any team member can explain "their" file:

| File | Responsibility |
|---|---|
| `app.py` | The dashboard. Layout, sidebar controls, tabs, error handling. Contains no maths. |
| `data.py` | All input data: entities, positions, relationships, scenarios. Change the scenario here without touching any logic. |
| `network.py` | Turns `data.py` into a validated `networkx.DiGraph`; provides layout positions and summary tables. |
| `simulation.py` | The propagation engine, the risk score, and the DataFrames the UI displays. |
| `visualization.py` | All Plotly figures and the shared colour palette. |
| `smoke_test.py` | *Extra file, and here is why:* it verifies the network, the engine, the edge cases and the charts in about a second without launching Streamlit. It is how we prove the engine is deterministic and how we catch a broken change before a demo. |
| `.streamlit/config.toml` | *Extra file, and here is why:* it sets the dark theme before the page renders, avoiding a white flash on load. |

## 5. Technology Stack

- **Python 3.9+**
- **Streamlit** — the dashboard UI
- **NetworkX** — the directed graph structure
- **Pandas** / **NumPy** — tabular results
- **Plotly** — the interactive network map and charts

No database, no API server, no containers, no cloud services. The application is
completely self-contained and runs on a normal laptop.

## 6. The Network

Ten entities across four categories:

| Category | Entities |
|---|---|
| Commodity | Crude Oil |
| Sector | Airlines, Chemicals, Shipping, Travel, Manufacturing, Logistics, Consumer Goods |
| Financial Institution | Banks |
| Market Indicator | Market Index |

Seventeen directed relationships, each with a weight in (0, 1]. Read an edge as
*"a disturbance in the source transmits this share of its force into the target,
before damping"*:

```
Crude Oil → Airlines        0.70      Manufacturing → Consumer Goods  0.65
Crude Oil → Chemicals       0.65      Manufacturing → Banks           0.40
Crude Oil → Shipping        0.60      Logistics     → Consumer Goods  0.50
Airlines  → Travel          0.75      Logistics     → Banks           0.30
Airlines  → Banks           0.35      Consumer Goods→ Banks           0.35
Chemicals → Manufacturing   0.70      Banks         → Market Index    0.60
Chemicals → Consumer Goods  0.40      Consumer Goods→ Market Index    0.30
Shipping  → Logistics       0.80
Shipping  → Manufacturing   0.45
Travel    → Consumer Goods  0.30
```

These weights are **authored, not measured**.

## 7. Propagation Methodology

Starting at the shock origin, the engine walks outwards one hop at a time
(breadth-first). Crossing any relationship:

```
delivered impact = incoming impact × relationship weight × damping factor
```

**Worked example** — Energy Shock, Crude Oil +20%, damping 0.85:

| Step | Calculation | Result |
|---|---|---|
| Crude Oil → Airlines | 20.00% × 0.70 × 0.85 | **+11.90%** |
| Airlines → Travel | 11.90% × 0.75 × 0.85 | **+7.59%** |
| Travel → Consumer Goods | 7.59% × 0.30 × 0.85 | **+1.93%** |

A route stops travelling when:

- the delivered impact falls below the **propagation threshold** (default 1%),
- it has taken **maximum depth** hops from the origin (default 5), or
- it would **revisit an entity already on that route** — this is what makes a
  cycle in the network safe.

A hard cap of 5,000 events guarantees the loop always terminates; if it is hit,
the UI says so rather than silently truncating.

An entity's reported impact is the **sum of everything delivered to it from every
route**. That is why Consumer Goods — fed by Chemicals, Travel, Manufacturing and
Logistics — ends up more exposed than an entity reached through a single channel.

The sign of the shock is carried through unchanged: a −15% shock produces negative
impacts downstream. The engine is fully **deterministic** — successors are
processed in sorted order, so the same inputs always produce byte-identical
output.

## 8. Systemic Risk Methodology

Four components, each normalised to a 0–1 fraction of its own theoretical maximum
so they are directly comparable:

| Component | Definition | Weight | Captures |
|---|---|---|---|
| Breadth | affected entities ÷ all other entities | 0.35 | how much of the network was touched |
| Intensity | total absolute impact ÷ (other entities × shock size) | 0.30 | how much total force landed |
| Peak | largest single impact ÷ shock size | 0.20 | how hard the worst-hit entity was hit |
| Reach | deepest level reached ÷ maximum allowed depth | 0.15 | how deep the shock travelled |

```
score = 100 × (0.35·breadth + 0.30·intensity + 0.20·peak + 0.15·reach)
```

Each component is capped at 1.0 so no single term can dominate. Bands:

| Score | Band |
|---|---|
| 0–30 | Contained |
| 30–50 | Moderate |
| 50–70 | Elevated |
| 70–100 | Severe |

This is a **prototype analytical metric for comparing scenarios against each
other**. It is not a regulatory measure, not an industry standard, and it has no
meaning outside this application.

## 9. Limitations

- The network is hand-authored and illustrative. It does not represent real
  institutional exposures, and the weights are not estimated from data.
- Relationships are linear and instantaneous. Real transmission is non-linear,
  lagged, regime-dependent, and changes over time.
- The sign of a shock is carried through unchanged, which assumes every
  downstream entity moves in the same direction as its upstream driver. Real
  relationships include hedges and inverse exposures.
- Summing impacts across routes can double-count a shared underlying driver.
- The risk score is a comparison metric, not a validated risk measure.
- There is no uncertainty, no confidence interval and no back-testing.

## 10. Installation

Requires Python 3.9 or newer.

```bash
python -m venv .venv
```

Activate it — Windows (PowerShell):

```bash
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Then install the dependencies:

```bash
pip install -r requirements.txt
```

### Troubleshooting

**`ImportError: DLL load failed while importing lib` (pyarrow, on Windows)** —
Windows could not load a native library because the folder path is too long.
Move the project to a short path such as `C:\MarketShock` and recreate the
virtual environment there.

**`streamlit: command not found`** — the virtual environment is not active.
Activate it, or run the app as `python -m streamlit run app.py`.

## 11. How to Run

```bash
streamlit run app.py
```

The dashboard opens at <http://localhost:8501>. It runs the Energy Shock scenario
on load, so there is always something on screen.

To verify the engine without the UI:

```bash
python smoke_test.py
```

### Using the dashboard

1. Pick a **Scenario** in the sidebar — this prefills the origin and magnitude.
2. Or build your own: choose a **Shock origin** and a **Shock magnitude**.
3. Optionally open **Engine settings** to change damping, threshold or depth.
4. Press **▶ Run Simulation**.
5. Read the metrics, explore the network map, then open the tabs below for
   impact analysis, pathways, comparison, the raw network and the methodology.
6. Press **＋ Save to Comparison** to keep a run, then switch to the
   **Scenario Comparison** tab to compare it against others.

## 12. Example Scenarios

| Scenario | Origin | Shock | Story |
|---|---|---|---|
| **Energy Shock** | Crude Oil | +20% | Crude oil spikes after a supply disruption. |
| **Financial Shock** | Banks | −15% | Banking sector falls on a credit-quality scare. |
| **Supply Chain Shock** | Shipping | −20% | Ocean freight capacity drops on a route closure. |
| **Aviation Disruption** | Airlines | −25% | Airline capacity cut by a grounding event. |
| **Industrial Slowdown** | Manufacturing | −18% | Industrial output contracts on weak orders. |

Energy Shock is the best opening demo: Crude Oil sits upstream of three sectors,
so the cascade reaches the whole network and the propagation map fills up.
Financial Shock is a useful contrast — Banks sits near the end of the network, so
the same tool reports a much smaller cascade. That difference is the argument for
looking at structure rather than at individual indicators.

## 13. Future Scope

Deliberately **not** implemented in this MVP:

- **Real financial datasets** — replace the authored weights with correlations or
  exposures estimated from historical returns.
- **Real-time market data** — live prices driving the shock inputs.
- **Multi-layer networks** — separate credit, liquidity, trade and sentiment
  layers that interact.
- **Historical crisis replay** — calibrate against 2008 or March 2020 and compare
  the simulated cascade to what actually happened.
- **Portfolio stress testing** — map a user's holdings onto the network and
  report portfolio-level exposure.
- **Advanced statistical / ML models** — Granger causality, vector autoregression
  or graph neural networks for learned transmission strengths.
- **Richer exposure modelling** — non-linear and time-lagged transmission,
  capacity and threshold effects, feedback loops with attenuation.

---

*MarketShock is a scenario-analysis prototype using illustrative network
relationships. Results are simulations, not financial predictions or investment
advice.*
# Market-Shock
