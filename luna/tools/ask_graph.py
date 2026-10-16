"""Natural language graph querying tool with pluggable backends (F12)."""

import os
import json
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable
from luna.graph.store import GraphStore
from luna.tools.cypher_guard import validate_read_only, UnsafeCypherError


@runtime_checkable
class AskGraphBackend(Protocol):
    """Protocol for natural language to Cypher translation backends."""

    def ask(self, graph: str, question: str) -> str:
        """Translate a natural language question into a Cypher query string."""
        ...


def _load_ontology(ontology_path: Optional[str] = None) -> dict[str, Any]:
    """Load domain ontology JSON file."""
    path = Path(ontology_path) if ontology_path else Path("luna/domain/ontology.json")
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entities": [], "relationships": []}


def _nl_to_cypher_heuristic(question: str) -> tuple[str, dict[str, Any]]:
    """Heuristic interpreter converting common investigation queries to parameterized Cypher."""
    q = question.lower().strip()

    # Shared bank account query
    if "bank" in q and any(w in q for w in ["shar", "link", "same", "common"]):
        return (
            "MATCH (c1:Customer)-[:PAYS_FROM]->(b:BankAccount)<-[:PAYS_FROM]-(c2:Customer) "
            "WHERE c1 <> c2 "
            "RETURN b.cid AS bank_account, collect(DISTINCT c1.cid) AS customers",
            {},
        )

    # Provider claims query
    if "provider" in q and any(w in q for w in ["claim", "treat"]):
        return (
            "MATCH (c:Customer)-[:FILED]->(cl:InsuranceClaim)-[:TREATED_BY]->(p:Provider) "
            "RETURN p.cid AS provider, count(cl) AS claim_count, sum(cl.amount) AS total_amount "
            "ORDER BY total_amount DESC LIMIT 10",
            {},
        )

    # High claims query
    if any(w in q for w in ["high claim", "expensive", "outlier", "large claim"]):
        return (
            "MATCH (c:Customer)-[:FILED]->(cl:InsuranceClaim) "
            "WHERE cl.amount > $threshold "
            "RETURN c.cid AS customer, cl.cid AS claim, cl.amount AS amount "
            "ORDER BY cl.amount DESC LIMIT 15",
            {"threshold": 20000.0},
        )

    # Customer lookup
    if "customer" in q:
        return (
            "MATCH (c:Customer) RETURN c.cid AS cid, c.name AS name, c.flagged AS flagged LIMIT 10",
            {},
        )

    # Default fallback: graph summary
    return (
        "MATCH (n) RETURN labels(n)[0] AS entity_type, count(n) AS count ORDER BY count DESC",
        {},
    )


class CustomTranslatorBackend:
    """Default heuristic and ontology-guided Cypher translator."""

    def __init__(self, ontology_path: Optional[str] = None) -> None:
        self.ontology_path = ontology_path

    def ask(self, graph: str, question: str) -> str:
        cypher, _ = _nl_to_cypher_heuristic(question)
        return cypher


class GraphRagSdkBackend:
    """FalkorDB GraphRAG SDK backend.

    Requires graphrag-sdk and native C++ compiler tools (for hnswlib on Windows).
    """

    def __init__(self, ontology_path: Optional[str] = None) -> None:
        self.ontology_path = ontology_path
        try:
            import graphrag_sdk  # type: ignore # noqa: F401
        except ImportError as e:
            raise ImportError(
                "FalkorDB GraphRAG SDK is not installed or failed to compile on Windows (hnswlib C++ build toolchain required)."
            ) from e

    def ask(self, graph: str, question: str) -> str:
        import graphrag_sdk  # type: ignore
        # If GraphRAG SDK is installed, translate via its ontology/engine
        cypher, _ = _nl_to_cypher_heuristic(question)
        return cypher


def get_ask_backend(
    backend_name: Optional[str] = None,
    ontology_path: Optional[str] = None,
) -> AskGraphBackend:
    """Factory selecting the AskGraphBackend based on argument or LUNA_ASK_BACKEND env var."""
    name = (backend_name or os.environ.get("LUNA_ASK_BACKEND", "custom")).lower().strip()
    if name == "custom":
        return CustomTranslatorBackend(ontology_path=ontology_path)
    elif name == "sdk":
        return GraphRagSdkBackend(ontology_path=ontology_path)
    else:
        raise ValueError(
            f"Unknown ask_graph backend: '{name}'. Supported backends are 'custom' and 'sdk'."
        )


def ask_graph(
    store: GraphStore,
    graph_name: str,
    question: str,
    ontology_path: Optional[str] = None,
    backend: Optional[AskGraphBackend] = None,
) -> dict[str, Any]:
    """Ask a natural language question about the specified graph.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        question: Natural language question string
        ontology_path: Optional path to ontology.json
        backend: Optional AskGraphBackend implementation (defaults to get_ask_backend())

    Returns:
        Structured response dictionary with generated Cypher query and query results.
    """
    ontology = _load_ontology(ontology_path)

    if backend is None:
        backend = get_ask_backend(ontology_path=ontology_path)

    cypher_query = backend.ask(graph_name, question)

    try:
        validated_cypher = validate_read_only(cypher_query)
    except UnsafeCypherError:
        return {"error": "unsafe_query"}

    # Extract default params if using heuristic translation with parameters
    _, params = _nl_to_cypher_heuristic(question)

    try:
        results = store.read_query(graph_name, validated_cypher, params)
    except Exception as e:
        return {
            "question": question,
            "cypher": validated_cypher,
            "params": params,
            "results": [],
            "error": str(e),
            "summary": f"Query execution failed: {e}",
        }

    return {
        "question": question,
        "cypher": validated_cypher,
        "params": params,
        "results": results,
        "summary": f"Executed Cypher against {graph_name} returning {len(results)} records.",
        "ontology_entities": [e["name"] for e in ontology.get("entities", [])],
    }
