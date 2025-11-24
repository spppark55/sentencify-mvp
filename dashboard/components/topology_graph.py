from __future__ import annotations

from typing import Dict, Optional

from streamlit_agraph import agraph, Node, Edge, Config


def _heat_color(role: str, seconds: float) -> str:
    """Map recency (seconds) to color."""
    if seconds < 3:
        return "#00ff00"  # neon green
    if seconds < 7:
        return "#4caf50"  # warm green
    if seconds < 15:
        return "#2e7d32"  # cooling
    # idle: fall back to role color
    return "#1f77b4" if role == "infra" else "#6a1b9a"


def build_nodes(recency: Dict[str, float]) -> list[Node]:
    """
    Static coordinates (x in [0,800], y in [0,600]) to keep layout stable.
    Recency controls node color (heatmap).
    """
    return [
        Node(id="User", label="User", size=18, color="#1f77b4", x=100, y=50),
        Node(id="API", label="API", size=20, color=_heat_color("infra", recency.get("api", 999)), x=100, y=200),
        Node(id="Emb Model", label="Emb Model", size=18, color=_heat_color("ai", recency.get("emb_model", 999)), x=350, y=200),
        Node(id="VectorDB", label="VectorDB", size=18, color=_heat_color("infra", recency.get("vectordb", 999)), x=550, y=200),
        Node(id="Mongo", label="MongoDB", size=18, color=_heat_color("infra", recency.get("mongo", 999)), x=50, y=380),
        Node(id="Worker", label="Worker", size=18, color=_heat_color("infra", recency.get("worker", 999)), x=150, y=500),
        Node(id="Redis", label="Redis", size=18, color=_heat_color("infra", recency.get("redis", 999)), x=350, y=380),
        Node(id="GenAI (Macro)", label="GenAI (Macro)", size=18, color=_heat_color("ai", recency.get("genai_macro", 999)), x=550, y=380),
        Node(id="GenAI (Run)", label="GenAI (Run)", size=18, color=_heat_color("ai", recency.get("genai_run", 999)), x=220, y=300),
    ]


def build_edges() -> list[Edge]:
    return [
        Edge(source="User", target="API"),
        Edge(source="API", target="Emb Model"),
        Edge(source="Emb Model", target="VectorDB"),
        Edge(source="API", target="Mongo"),
        Edge(source="API", target="Redis"),
        Edge(source="API", target="GenAI (Run)"),
        Edge(source="Worker", target="Mongo"),
        Edge(source="Worker", target="Redis"),
        Edge(source="Worker", target="GenAI (Macro)"),
        Edge(source="GenAI (Macro)", target="Redis"),
    ]


def render_topology(recency: Dict[str, float], height: int = 500) -> Optional[str]:
    nodes = build_nodes(recency)
    edges = build_edges()
    config = Config(
        width="100%",
        height=height,
        directed=True,
        physics=False,  # keep nodes fixed
        hierarchical=False,
        nodeHighlightBehavior=True,
        link={"label": "flow", "type": "CURVE_SMOOTH", "renderLabel": False, "strokeWidth": 2, "color": "#aaaaaa", "dashed": True},
    )
    return agraph(nodes=nodes, edges=edges, config=config)
