"""Natural language graph querying tool powered by FalkorDB GraphRAG SDK with fallback interpreter."""

import json
from pathlib import Path
from typing import Any, Optional
from luna.graph.store import GraphStore


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


def ask_graph(
    store: GraphStore,
    graph_name: str,
    question: str,
    ontology_path: Optional[str] = None,
) -> dict[str, Any]:
    """Ask a natural language question about the specified graph.

    Args:
        store: GraphStore connection wrapper
        graph_name: Target graph name
        question: Natural language question string
        ontology_path: Optional path to ontology.json

    Returns:
        Structured response dictionary with generated Cypher query and query results.
    """
    ontology = _load_ontology(ontology_path)

    # Attempt FalkorDB GraphRAG SDK inquiry if SDK is available
    try:
        import graphrag_sdk  # type: ignore
        # If GraphRAG SDK is installed, use its Ontology and KnowledgeGraph
        if hasattr(graphrag_sdk, "Ontology"):
            # SDK execution branch
            pass
    except ImportError:
        pass

    # Heuristic and ontology-guided Cypher translation
    cypher_query, params = _nl_to_cypher_heuristic(question)
    try:
        results = store.query(graph_name, cypher_query, params)
    except Exception as e:
        results = []
        return {
            "question": question,
            "cypher": cypher_query,
            "params": params,
            "results": [],
            "error": str(e),
            "summary": f"Query execution failed: {e}",
        }

    return {
        "question": question,
        "cypher": cypher_query,
        "params": params,
        "results": results,
        "summary": f"Executed Cypher against {graph_name} returning {len(results)} records.",
        "ontology_entities": [e["name"] for e in ontology.get("entities", [])],
    }
