"""
data.py
-------
All input data for the MarketShock prototype lives here.

IMPORTANT HONESTY NOTE
======================
The network below is an ILLUSTRATIVE / CONTROLLED PROTOTYPE NETWORK.
It is hand-authored for demonstration purposes. It is NOT real institutional
exposure data, and the weights are not estimated from market data.

Keeping the data in one file means a non-programmer can change the scenario
without touching any of the simulation logic.
"""

from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 1. NODES
# ---------------------------------------------------------------------------
# Every node has a category (used only for grouping/colour in the UI) and a
# fixed position on the canvas. Fixed positions keep the network visualisation
# stable between runs, which makes the demo much easier to follow than a
# layout that reshuffles itself every time.

NODE_CATEGORIES: Dict[str, str] = {
    "Crude Oil": "Commodity",
    "Airlines": "Sector",
    "Chemicals": "Sector",
    "Shipping": "Sector",
    "Travel": "Sector",
    "Manufacturing": "Sector",
    "Logistics": "Sector",
    "Consumer Goods": "Sector",
    "Banks": "Financial Institution",
    "Market Index": "Market Indicator",
}

# Laid out left-to-right so that shocks visually flow across the screen.
NODE_POSITIONS: Dict[str, Tuple[float, float]] = {
    "Crude Oil": (0.0, 0.0),
    "Airlines": (1.2, 2.0),
    "Chemicals": (1.2, 0.0),
    "Shipping": (1.2, -2.0),
    "Travel": (2.6, 2.6),
    "Manufacturing": (2.6, 0.2),
    "Logistics": (2.6, -2.4),
    "Consumer Goods": (4.0, 1.0),
    "Banks": (4.0, -1.4),
    "Market Index": (5.4, -0.2),
}

# Short plain-English description shown in the hover tooltip.
NODE_DESCRIPTIONS: Dict[str, str] = {
    "Crude Oil": "Benchmark energy commodity; a cost input for most physical industries.",
    "Airlines": "Passenger and cargo aviation; highly fuel-cost sensitive.",
    "Chemicals": "Petrochemical producers; crude oil is a direct feedstock.",
    "Shipping": "Ocean freight carriers; bunker fuel is a major cost line.",
    "Travel": "Tourism, hotels and booking platforms; demand follows air capacity.",
    "Manufacturing": "Industrial production; depends on chemicals and freight.",
    "Logistics": "Land freight, warehousing and distribution networks.",
    "Consumer Goods": "Retail and packaged goods; absorbs upstream cost pressure.",
    "Banks": "Lenders with credit exposure across the sectors above.",
    "Market Index": "Broad market barometer aggregating the ecosystem.",
}

# ---------------------------------------------------------------------------
# 2. EDGES (dependency / exposure relationships)
# ---------------------------------------------------------------------------
# (source, target, weight) where weight is in (0, 1].
# Read an edge as: "a disturbance in <source> transmits <weight> of its force
# into <target>, before damping is applied".

EDGES: List[Tuple[str, str, float]] = [
    ("Crude Oil", "Airlines", 0.70),
    ("Crude Oil", "Chemicals", 0.65),
    ("Crude Oil", "Shipping", 0.60),
    ("Airlines", "Travel", 0.75),
    ("Airlines", "Banks", 0.35),
    ("Chemicals", "Manufacturing", 0.70),
    ("Chemicals", "Consumer Goods", 0.40),
    ("Shipping", "Logistics", 0.80),
    ("Shipping", "Manufacturing", 0.45),
    ("Travel", "Consumer Goods", 0.30),
    ("Manufacturing", "Consumer Goods", 0.65),
    ("Manufacturing", "Banks", 0.40),
    ("Logistics", "Consumer Goods", 0.50),
    ("Logistics", "Banks", 0.30),
    ("Consumer Goods", "Banks", 0.35),
    ("Banks", "Market Index", 0.60),
    ("Consumer Goods", "Market Index", 0.30),
]

# ---------------------------------------------------------------------------
# 3. PREDEFINED DEMO SCENARIOS
# ---------------------------------------------------------------------------
# magnitude is a signed fraction: 0.20 means "+20%", -0.15 means "-15%".
# The sign is carried through the propagation as the *direction* of the
# disturbance; severity is always measured on the absolute value.

SCENARIOS: Dict[str, Dict[str, object]] = {
    "Energy Shock": {
        "origin": "Crude Oil",
        "magnitude": 0.20,
        "description": "Crude oil spikes +20% after a supply disruption.",
    },
    "Financial Shock": {
        "origin": "Banks",
        "magnitude": -0.15,
        "description": "Banking sector falls 15% on a credit-quality scare.",
    },
    "Supply Chain Shock": {
        "origin": "Shipping",
        "magnitude": -0.20,
        "description": "Ocean freight capacity drops 20% on a route closure.",
    },
    "Aviation Disruption": {
        "origin": "Airlines",
        "magnitude": -0.25,
        "description": "Airline capacity cut 25% by a grounding event.",
    },
    "Industrial Slowdown": {
        "origin": "Manufacturing",
        "magnitude": -0.18,
        "description": "Industrial output contracts 18% on weak orders.",
    },
}

CUSTOM_SCENARIO_LABEL = "Custom Shock"

DISCLAIMER = (
    "MarketShock is a scenario-analysis prototype using illustrative network "
    "relationships. Results are simulations, not financial predictions or "
    "investment advice."
)
