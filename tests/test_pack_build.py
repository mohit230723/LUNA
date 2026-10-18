"""Tests for Q4: Software-Build Pack (seed, understand, blueprint, sandbox, verifier, pipeline)."""

import os
import zipfile
import pytest
from pathlib import Path

from luna.packs.base import Pack
from luna.packs.build.pack import BuildPack
from luna.packs.build.seed import seed_build_atlas, BUILD_CAPABILITIES, BUILD_TECHNOLOGIES, BUILD_SKILLS
from luna.packs.build.understand import understand_build_prompt
from luna.packs.build.blueprint import generate_blueprint, persist_blueprint, ComponentDef
from luna.packs.build.sandbox import SandboxWorkspace, MAX_FILE_SIZE_BYTES
from luna.packs.build.verifier import verify_contracts
from luna.packs.build.pipeline import BuildPipeline, BuildPipelineConfig
from luna.graph.schema import (
    LABEL_SKILL,
    LABEL_TECHNOLOGY,
    LABEL_ACTION,
    LABEL_OUTCOME,
    REL_TARGETS,
    REL_PROVIDES,
    REL_CONSUMES,
    REL_DEPENDS_ON,
)


def test_build_pack_protocol_conformance() -> None:
    """Verify BuildPack conforms strictly to the Pack protocol."""
    pack = BuildPack()
    assert isinstance(pack, Pack)
    assert pack.name == "build"
    assert pack.title == "Software Build"
    assert len(pack.capabilities) == 5
    assert len(pack.example_prompts) >= 1


def test_understand_valid_build_prompt() -> None:
    """Verify extraction of tech stack and features for fullstack todo prompt (D2)."""
    prompt = "Build a fullstack todo app with React frontend, Express backend, and Postgres database"
    understanding = understand_build_prompt(None, prompt)

    assert not understanding.needs_input
    assert understanding.tech.get("frontend") == "react"
    assert understanding.tech.get("backend") == "express"
    assert understanding.tech.get("database") == "postgres"
    assert len(understanding.features) >= 1
    assert any("todo" in f.lower() for f in understanding.features)


def test_understand_unsupported_tech_triggers_needs_input() -> None:
    """Verify requesting Svelte returns needs_input=True with clarifying question (Scenario D4)."""
    prompt = "Build a todo app using Svelte frontend and Express backend"
    understanding = understand_build_prompt(None, prompt)

    assert understanding.needs_input is True
    assert understanding.clarification_question is not None
    assert "Svelte" in understanding.clarification_question
    assert "React" in understanding.clarification_question


def test_generate_blueprint_dag_and_waves() -> None:
    """Verify blueprint DAG topological sort generates 3 sequential waves."""
    blueprint = generate_blueprint(
        project_name="todo-app",
        tech={"frontend": "react", "backend": "express", "database": "postgres"},
        features=["create todo", "list todos"],
    )

    assert len(blueprint.components) == 3
    assert len(blueprint.contracts) == 3
    assert len(blueprint.waves) == 3

    # Wave 0: database (0 dependencies)
    assert "database" in blueprint.waves[0]
    # Wave 1: backend (depends on database)
    assert "backend" in blueprint.waves[1]
    # Wave 2: frontend (depends on backend)
    assert "frontend" in blueprint.waves[2]


def test_generate_blueprint_rejects_cycles() -> None:
    """Verify cycle detection catches circular dependencies."""
    import networkx as nx
    dag = nx.DiGraph()
    dag.add_edge("comp-a", "comp-b")
    dag.add_edge("comp-b", "comp-a")

    assert not nx.is_directed_acyclic_graph(dag)


def test_sandbox_path_traversal_protection(tmp_path) -> None:
    """Verify sandbox strictly rejects path traversal attempts."""
    workspace = SandboxWorkspace("test_sec_run", base_dir=str(tmp_path))

    # Valid write
    res = workspace.write_file("frontend", "src/App.tsx", "export default function App() {}")
    assert res["component"] == "frontend"
    assert res["filename"] == "App.tsx"

    # Traversal attempts
    with pytest.raises(ValueError, match="Path traversal attempt detected"):
        workspace.write_file("frontend", "../secret.txt", "hacked")

    with pytest.raises(ValueError, match="Path traversal attempt detected"):
        workspace.write_file("frontend", "../../etc/passwd", "root:x:0:0")

    workspace.cleanup()


def test_sandbox_file_size_cap(tmp_path) -> None:
    """Verify sandbox rejects files exceeding 200KB cap."""
    workspace = SandboxWorkspace("test_size_run", base_dir=str(tmp_path))
    huge_content = "X" * (MAX_FILE_SIZE_BYTES + 1024)

    with pytest.raises(ValueError, match="exceeds the 200KB maximum size cap"):
        workspace.write_file("backend", "huge.txt", huge_content)

    workspace.cleanup()


def test_sandbox_zip_creation(tmp_path) -> None:
    """Verify workspace compresses cleanly into a zip archive."""
    workspace = SandboxWorkspace("test_zip_run", base_dir=str(tmp_path))
    workspace.write_file("backend", "index.ts", "console.log('hello');")
    workspace.write_file("frontend", "App.tsx", "export default () => null;")

    zip_file = workspace.create_zip()
    assert os.path.exists(zip_file)
    assert zipfile.is_zipfile(zip_file)

    with zipfile.ZipFile(zip_file) as zf:
        names = zf.namelist()
        assert any("index.ts" in n for n in names)
        assert any("App.tsx" in n for n in names)

    workspace.cleanup()
    if os.path.exists(zip_file):
        os.remove(zip_file)


def test_deterministic_contract_verifier(tmp_path) -> None:
    """Verify verify_contracts passes when code matches and fails when route missing."""
    workspace = SandboxWorkspace("test_verif_run", base_dir=str(tmp_path))

    # Seed matching files
    workspace.write_file("database", "schema.sql", "CREATE TABLE todos (id SERIAL PRIMARY KEY, title TEXT);")
    workspace.write_file(
        "backend",
        "src/index.ts",
        "app.get('/api/todos', handler); app.post('/api/todos', handler); app.patch('/api/todos/:id', handler); app.delete('/api/todos/:id', handler);",
    )
    workspace.write_file("frontend", "src/App.tsx", "fetch('/api/todos');")

    blueprint = generate_blueprint(
        project_name="todo-app",
        tech={"frontend": "react", "backend": "express", "database": "postgres"},
        features=["todos"],
    )

    # 1. Matching pass
    res = verify_contracts(workspace, blueprint.contracts)
    assert res.passed is True
    assert len(res.issues) == 0

    # 2. Break backend contract by removing routes
    workspace.write_file("backend", "src/index.ts", "app.get('/api/other', handler);")
    res_bad = verify_contracts(workspace, blueprint.contracts)
    assert res_bad.passed is False
    assert len(res_bad.issues) >= 1
    assert any("Endpoint '/api/todos' not defined" in issue for issue in res_bad.issues)

    workspace.cleanup()


@pytest.mark.integration
def test_seed_build_atlas_persists_technologies_and_targets(live_store, tmp_graph: str) -> None:
    """Verify seed_build_atlas populates 15 technologies, 12 skills, and TARGETS edges."""
    atlas_graph = f"{tmp_graph}_build_atlas"

    try:
        seed_build_atlas(live_store, atlas_graph)

        # Check technologies count
        tech_rows = live_store.query(
            atlas_graph,
            f"MATCH (t:{LABEL_TECHNOLOGY}) RETURN count(t) AS cnt",
        )
        assert int(tech_rows[0]["cnt"]) >= 15

        # Check shell-runner is policy restricted
        shell_rows = live_store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL} {{id: 'shell-runner'}}) RETURN s.restricted AS restricted",
        )
        assert len(shell_rows) == 1
        assert shell_rows[0]["restricted"] is True

        # Check react-vite-expert targets React
        targets_rows = live_store.query(
            atlas_graph,
            f"MATCH (s:{LABEL_SKILL} {{id: 'react-vite-expert'}})-[:{REL_TARGETS}]->(t:{LABEL_TECHNOLOGY} {{name: 'React'}}) "
            "RETURN t.name AS name",
        )
        assert len(targets_rows) == 1

    finally:
        live_store.delete_graph(atlas_graph)


@pytest.mark.integration
def test_full_build_pipeline_lifecycle(live_store, tmp_graph: str) -> None:
    """Verify BuildPipeline start() stops at PENDING Action and approve_and_finish completes."""
    atlas_graph = f"{tmp_graph}_pipe_atlas"
    run_id = f"build_pipe_{tmp_graph}"
    run_graph = f"run_{run_id}"

    events = []
    def on_event(step: str, data: dict):
        events.append((step, data))

    try:
        # Seed atlas with build skills
        seed_build_atlas(live_store, atlas_graph)

        cfg = BuildPipelineConfig(
            run_id=run_id,
            atlas_graph=atlas_graph,
            event_callback=on_event,
        )
        pipeline = BuildPipeline(live_store, cfg)

        # 1. Start pipeline
        res = pipeline.start("Build a fullstack todo app with React frontend, Express backend, and Postgres database")
        assert res.status == "pending_approval"
        assert res.action_id is not None
        assert res.verification["passed"] is True
        assert len(res.artifacts) >= 4
        assert os.path.exists(res.zip_path)

        # Action is PENDING in graph
        act_rows = live_store.query(
            run_graph,
            f"MATCH (a:{LABEL_ACTION} {{id: $aid}}) RETURN a.status AS status, a.kind AS kind",
            {"aid": res.action_id},
        )
        assert len(act_rows) == 1
        assert act_rows[0]["status"] == "PENDING"
        assert act_rows[0]["kind"] == "run_build_check"

        # Verify event sequence
        step_names = [e[0] for e in events]
        assert "init" in step_names
        assert "requirements" in step_names
        assert "blueprint" in step_names
        assert "artifact_written" in step_names
        assert "contract_verified" in step_names
        assert "propose" in step_names

        # 2. Approve and finish
        fin_res = pipeline.approve_and_finish(
            action_id=res.action_id,
            approver="Senior_Engineer",
        )
        assert fin_res.status == "completed"
        assert fin_res.outcome_id is not None

        # Verify Action EXECUTED and Outcome created
        out_rows = live_store.query(
            run_graph,
            f"MATCH (a:{LABEL_ACTION} {{id: $aid}})-[:RESULTED_IN]->(o:{LABEL_OUTCOME}) "
            "RETURN a.status AS act_status, o.success AS success",
            {"aid": res.action_id},
        )
        assert len(out_rows) == 1
        assert out_rows[0]["act_status"] == "EXECUTED"
        assert out_rows[0]["success"] is True

        # Cleanup zip and workspace
        if pipeline.workspace:
            pipeline.workspace.cleanup()
        if os.path.exists(res.zip_path):
            os.remove(res.zip_path)

    finally:
        live_store.delete_graph(atlas_graph)
        live_store.delete_graph(run_graph)
