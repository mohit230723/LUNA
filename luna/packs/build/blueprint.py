"""Blueprint DAG generator for Software-Build Pack with contract definitions and wave ordering."""

from __future__ import annotations

import json
from typing import Any, Optional
from pydantic import BaseModel, Field
import networkx as nx

from luna.graph.store import GraphStore


class ContractDef(BaseModel):
    name: str
    kind: str  # "api_routes" | "db_schema" | "env_config"
    spec: dict[str, Any]


class ComponentDef(BaseModel):
    name: str
    tech: str
    role: str  # "database" | "backend" | "frontend"
    provides: list[ContractDef] = Field(default_factory=list)
    consumes: list[str] = Field(default_factory=list)  # contract names
    depends_on: list[str] = Field(default_factory=list)  # component names


class Blueprint(BaseModel):
    project_name: str
    components: list[ComponentDef]
    contracts: list[ContractDef]
    waves: list[list[str]]  # components grouped into sequential execution waves


def generate_blueprint(
    project_name: str,
    tech: dict[str, str],
    features: list[str],
) -> Blueprint:
    """Generate a DAG blueprint of components and contracts sorted into execution waves.

    Validates acyclicity using topological sort.
    """
    fe_tech = tech.get("frontend", "react")
    be_tech = tech.get("backend", "express")
    db_tech = tech.get("database", "postgres")

    # 1. Define Contracts
    db_schema_contract = ContractDef(
        name="db_schema",
        kind="db_schema",
        spec={
            "tables": [
                {
                    "name": "todos",
                    "columns": [
                        {"name": "id", "type": "SERIAL PRIMARY KEY"},
                        {"name": "title", "type": "VARCHAR(255) NOT NULL"},
                        {"name": "completed", "type": "BOOLEAN DEFAULT FALSE"},
                        {"name": "created_at", "type": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"},
                    ],
                }
            ]
        },
    )

    api_routes_contract = ContractDef(
        name="api_routes",
        kind="api_routes",
        spec={
            "base_url": "http://localhost:3001/api",
            "endpoints": [
                {"method": "GET", "path": "/api/todos", "description": "List all todos"},
                {"method": "POST", "path": "/api/todos", "description": "Create new todo", "body": {"title": "string"}},
                {"method": "PATCH", "path": "/api/todos/:id", "description": "Toggle completed status"},
                {"method": "DELETE", "path": "/api/todos/:id", "description": "Delete a todo by id"},
            ],
        },
    )

    env_config_contract = ContractDef(
        name="env_config",
        kind="env_config",
        spec={
            "PORT": 3001,
            "DATABASE_URL": "postgres://postgres:postgres@localhost:5432/todos_db",
            "VITE_API_URL": "http://localhost:3001",
        },
    )

    # 2. Define Components
    comp_database = ComponentDef(
        name="database",
        tech=db_tech,
        role="database",
        provides=[db_schema_contract],
        consumes=[],
        depends_on=[],
    )

    comp_backend = ComponentDef(
        name="backend",
        tech=be_tech,
        role="backend",
        provides=[api_routes_contract, env_config_contract],
        consumes=["db_schema"],
        depends_on=["database"],
    )

    comp_frontend = ComponentDef(
        name="frontend",
        tech=fe_tech,
        role="frontend",
        provides=[],
        consumes=["api_routes", "env_config"],
        depends_on=["backend"],
    )

    components = [comp_database, comp_backend, comp_frontend]
    contracts = [db_schema_contract, api_routes_contract, env_config_contract]

    # 3. Build NetworkX DiGraph for Cycle Detection and Topological Wave Sorting
    dag = nx.DiGraph()
    for c in components:
        dag.add_node(c.name)
    for c in components:
        for dep in c.depends_on:
            dag.add_edge(dep, c.name)

    if not nx.is_directed_acyclic_graph(dag):
        cycles = list(nx.simple_cycles(dag))
        raise ValueError(f"Cyclic component dependency detected in blueprint: {cycles}")

    # Compute topological waves (longest path from roots)
    levels: dict[str, int] = {}
    for node in nx.topological_sort(dag):
        preds = list(dag.predecessors(node))
        levels[node] = 0 if not preds else max(levels[p] for p in preds) + 1

    max_level = max(levels.values()) if levels else 0
    waves: list[list[str]] = [[] for _ in range(max_level + 1)]
    for node, lvl in levels.items():
        waves[lvl].append(node)

    return Blueprint(
        project_name=project_name,
        components=components,
        contracts=contracts,
        waves=waves,
    )


def persist_blueprint(
    store: GraphStore,
    run_graph_name: str,
    blueprint: Blueprint,
    task_id: str,
) -> None:
    """Persist Blueprint DAG nodes and relationships into the run memory graph."""
    # Persist Contracts
    for contract in blueprint.contracts:
        store.query(
            run_graph_name,
            "MERGE (c:Contract {name: $name}) "
            "ON CREATE SET c.kind = $kind, c.spec = $spec",
            {
                "name": contract.name,
                "kind": contract.kind,
                "spec": json.dumps(contract.spec),
            },
        )

    # Persist Components
    for comp in blueprint.components:
        store.query(
            run_graph_name,
            "MERGE (cp:Component {name: $name}) "
            "ON CREATE SET cp.tech = $tech, cp.role = $role",
            {
                "name": comp.name,
                "tech": comp.tech,
                "role": comp.role,
            },
        )

        # Component -[:PROVIDES]-> Contract
        for p_con in comp.provides:
            store.query(
                run_graph_name,
                "MATCH (cp:Component {name: $cname}) "
                "MATCH (c:Contract {name: $con_name}) "
                "MERGE (cp)-[:PROVIDES]->(c)",
                {"cname": comp.name, "con_name": p_con.name},
            )

        # Component -[:CONSUMES]-> Contract
        for c_con in comp.consumes:
            store.query(
                run_graph_name,
                "MATCH (cp:Component {name: $cname}) "
                "MATCH (c:Contract {name: $con_name}) "
                "MERGE (cp)-[:CONSUMES]->(c)",
                {"cname": comp.name, "con_name": c_con},
            )

        # Component -[:DEPENDS_ON]-> Component
        for dep in comp.depends_on:
            store.query(
                run_graph_name,
                "MATCH (cp:Component {name: $cname}) "
                "MATCH (dep:Component {name: $dep_name}) "
                "MERGE (cp)-[:DEPENDS_ON]->(dep)",
                {"cname": comp.name, "dep_name": dep},
            )

    # Link Task -[:HAS_BLUEPRINT]-> Component
    for comp in blueprint.components:
        store.query(
            run_graph_name,
            "MATCH (t:Task {id: $tid}) "
            "MATCH (cp:Component {name: $cname}) "
            "MERGE (t)-[:HAS_COMPONENT]->(cp)",
            {"tid": task_id, "cname": comp.name},
        )
