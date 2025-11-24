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
    Hierarchical layout: nodes do NOT need static x,y.
    The solver will position them based on edge flow (User -> API -> DB).
    """
    return [
        Node(id="User", label="User", size=25, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/user.png", color=_heat_color("user", 0)),
        Node(id="API", label="API Gateway", size=25, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/api-settings.png", color=_heat_color("infra", recency.get("api", 999))),
        Node(id="Emb Model", label="Embedding", size=20, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/artificial-intelligence.png", color=_heat_color("ai", recency.get("emb_model", 999))),
        Node(id="VectorDB", label="VectorDB (E)", size=20, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/database.png", color=_heat_color("infra", recency.get("vectordb", 999))),
        Node(id="Mongo", label="MongoDB (Unified)", size=20, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/server.png", color=_heat_color("infra", recency.get("mongo", 999))),
        Node(id="Worker", label="Macro Worker", size=20, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/worker.png", color=_heat_color("infra", recency.get("worker", 999))),
        Node(id="Redis", label="Redis (Cache)", size=20, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/redis.png", color=_heat_color("infra", recency.get("redis", 999))),
        Node(id="GenAI (Macro)", label="GenAI (Macro)", size=20, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/brain.png", color=_heat_color("ai", recency.get("genai_macro", 999))),
        Node(id="GenAI (Run)", label="GenAI (Run)", size=20, shape="circularImage", image="https://img.icons8.com/dusk/64/000000/robot.png", color=_heat_color("ai", recency.get("genai_run", 999))),
    ]


def build_edges() -> list[Edge]:
    # Define edges to enforce hierarchy: User -> API -> [Services]
    return [
        Edge(source="User", target="API", label="HTTP"),
        Edge(source="API", target="Emb Model", label="gRPC"),
        Edge(source="Emb Model", target="VectorDB", label="Upsert"),
        Edge(source="API", target="Mongo", label="Log/Read"),
        Edge(source="API", target="Redis", label="Cache"),
        Edge(source="API", target="GenAI (Run)", label="Paraphrase"),
        
        # Worker Flow (Offline/Async)
        Edge(source="Mongo", target="Worker", label="Stream"),
        Edge(source="Worker", target="GenAI (Macro)", label="Analysis"),
        Edge(source="GenAI (Macro)", target="Redis", label="Write Cache"),
    ]


def render_topology(recency: Dict[str, float], height: int = 600) -> Optional[str]:
    nodes = build_nodes(recency)
    edges = build_edges()
    
    # Hierarchical Layout Configuration
    config = Config(
        width="100%",
        height=height,
        directed=True,
        physics=False, 
        hierarchical=True,  # Enable Hierarchy
        # sortMethod='directed' ensures nodes follow edge direction
        # direction='LR' (Left-to-Right) or 'UD' (Up-Down)
        layout={
            "hierarchical": {
                "enabled": True,
                "levelSeparation": 150,
                "nodeSpacing": 100,
                "treeSpacing": 200,
                "blockShifting": True,
                "edgeMinimization": True,
                "parentCentralization": True,
                "direction": "LR",        # Left to Right Flow
                "sortMethod": "directed", # Arrange by direction
            }
        },
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=False,
        link={
            "type": "CURVE_SMOOTH", 
            "renderLabel": True, 
            "strokeWidth": 1.5, 
            "color": "#cfcfcf"
        },
    )
    return agraph(nodes=nodes, edges=edges, config=config)
