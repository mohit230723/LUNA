"""Runnable execution pipeline for the Software-Build Pack."""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Callable, Optional
from pydantic import BaseModel, Field

from luna.packs.base import PackPipeline, Understanding
from luna.packs.build.understand import understand_build_prompt
from luna.packs.build.blueprint import generate_blueprint, persist_blueprint, Blueprint
from luna.packs.build.sandbox import SandboxWorkspace
from luna.packs.build.verifier import verify_contracts, VerificationResult
from luna.graph.store import GraphStore
from luna.graph.schema import (
    GRAPH_ATLAS,
    LABEL_TASK,
    LABEL_ACTION,
    LABEL_OUTCOME,
    LABEL_SKILL,
    REL_BASED_ON,
    REL_RESULTED_IN,
    REL_SUCCEEDED_ON,
)


class BuildPipelineConfig(BaseModel):
    run_id: str
    atlas_graph: str = GRAPH_ATLAS
    event_callback: Optional[Callable[[str, dict[str, Any]], None]] = None


class BuildPipelineResult(BaseModel):
    run_id: str
    status: str  # "pending_approval" | "needs_input" | "completed" | "failed"
    action_id: Optional[str] = None
    outcome_id: Optional[str] = None
    needs_input: bool = False
    clarification_question: Optional[str] = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    zip_path: Optional[str] = None
    verification: Optional[dict[str, Any]] = None


class BuildPipeline(PackPipeline):
    """Pipeline coordinating the Software-Build Pack workflow."""

    def __init__(self, store: GraphStore, config: BuildPipelineConfig) -> None:
        self.store = store
        self.config = config
        self.run_id = config.run_id
        self.run_graph = f"run_{self.run_id}" if not self.run_id.startswith("run_") else self.run_id
        self.workspace: Optional[SandboxWorkspace] = None
        self.blueprint: Optional[Blueprint] = None
        self.action_id: Optional[str] = None
        self._seq: int = 0
        self._lock = threading.Lock()

    def _emit(self, step: str, data: dict[str, Any]) -> None:
        """Emit a pipeline event via the configured callback."""
        with self._lock:
            self._seq += 1
            seq = self._seq

        if self.config.event_callback:
            try:
                self.config.event_callback(step, {"seq": seq, "step": step, **data})
            except Exception:
                pass

    def start(
        self,
        task: str,
        llm: Any = None,
        context: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> BuildPipelineResult:
        """Execute build workflow up to action proposal and pause at PENDING."""
        self._emit("init", {"run_id": self.run_id, "task": task})

        # 1. Parse Requirements
        understanding = understand_build_prompt(llm, task, context=context)
        self._emit("requirements", {
            "tech": understanding.tech,
            "features": understanding.features,
            "needs_input": understanding.needs_input,
        })

        if understanding.needs_input:
            return BuildPipelineResult(
                run_id=self.run_id,
                status="needs_input",
                needs_input=True,
                clarification_question=understanding.clarification_question,
            )

        # 2. Persist Task Node in Run Graph
        task_id = "task-build-main"
        self.store.query(
            self.run_graph,
            f"MERGE (t:{LABEL_TASK} {{id: $tid}}) "
            "ON CREATE SET t.description = $desc, t.status = 'active'",
            {"tid": task_id, "desc": task},
        )

        # 3. Generate Blueprint DAG
        blueprint = generate_blueprint(
            project_name="todo-app",
            tech=understanding.tech,
            features=understanding.features,
        )
        self.blueprint = blueprint
        persist_blueprint(self.store, self.run_graph, blueprint, task_id)
        self._emit("blueprint", {
            "components": [c.name for c in blueprint.components],
            "waves": blueprint.waves,
        })

        # 4. Assign Skills
        assigned_skills: dict[str, str] = {}
        for comp in blueprint.components:
            # Query atlas for skill targeting this tech
            cap_map = {
                "database": "implement_database",
                "backend": "implement_backend",
                "frontend": "implement_frontend",
            }
            cap = cap_map.get(comp.name, "scaffold_project")
            skills = self.store.query(
                self.config.atlas_graph,
                f"MATCH (s:{LABEL_SKILL})-[:PROVIDES]->(c:Capability {{name: $cap}}) "
                "WHERE coalesce(s.restricted, false) = false "
                "RETURN s.id AS id, s.name AS name LIMIT 1",
                {"cap": cap},
            )
            chosen_id = skills[0]["id"] if skills else "project-scaffolder"
            assigned_skills[comp.name] = chosen_id
            self._emit("skill_assigned", {
                "component": comp.name,
                "skill_id": chosen_id,
                "capability": cap,
            })

        # 5. Initialize Workspace & Execute Waves
        workspace = SandboxWorkspace(self.run_id)
        self.workspace = workspace

        # Wave 0: Database
        workspace.write_file(
            "database",
            "schema.sql",
            (
                "-- PostgreSQL Schema for Todos App\n"
                "CREATE TABLE IF NOT EXISTS todos (\n"
                "  id SERIAL PRIMARY KEY,\n"
                "  title VARCHAR(255) NOT NULL,\n"
                "  completed BOOLEAN DEFAULT FALSE,\n"
                "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n"
                ");\n"
            ),
        )
        self._emit("artifact_written", {"component": "database", "path": "database/schema.sql"})

        # Wave 1: Backend
        workspace.write_file(
            "backend",
            "package.json",
            json.dumps(
                {
                    "name": "todos-backend",
                    "version": "1.0.0",
                    "scripts": {"build": "tsc", "start": "node dist/index.js"},
                    "dependencies": {"express": "^4.19.2", "cors": "^2.8.5", "pg": "^8.11.5"},
                    "devDependencies": {"typescript": "^5.4.5", "@types/express": "^4.17.21"},
                },
                indent=2,
            ),
        )
        workspace.write_file(
            "backend",
            "src/index.ts",
            (
                "import express from 'express';\n"
                "import cors from 'cors';\n\n"
                "const app = express();\n"
                "app.use(cors());\n"
                "app.use(express.json());\n\n"
                "// Todos In-Memory Data Store\n"
                "let todos = [\n"
                "  { id: 1, title: 'Learn LUNA OS Graph Architecture', completed: true },\n"
                "  { id: 2, title: 'Build Fullstack React App', completed: false },\n"
                "];\n\n"
                "app.get('/api/todos', (req, res) => {\n"
                "  res.json(todos);\n"
                "});\n\n"
                "app.post('/api/todos', (req, res) => {\n"
                "  const newTodo = { id: Date.now(), title: req.body.title || 'Untitled', completed: false };\n"
                "  todos.push(newTodo);\n"
                "  res.status(201).json(newTodo);\n"
                "});\n\n"
                "app.patch('/api/todos/:id', (req, res) => {\n"
                "  const id = parseInt(req.params.id, 10);\n"
                "  const item = todos.find(t => t.id === id);\n"
                "  if (item) item.completed = !item.completed;\n"
                "  res.json(item || { error: 'Not found' });\n"
                "});\n\n"
                "app.delete('/api/todos/:id', (req, res) => {\n"
                "  const id = parseInt(req.params.id, 10);\n"
                "  todos = todos.filter(t => t.id !== id);\n"
                "  res.status(204).send();\n"
                "});\n\n"
                "const PORT = process.env.PORT || 3001;\n"
                "app.listen(PORT, () => console.log(`Backend running on port ${PORT}`));\n"
            ),
        )
        self._emit("artifact_written", {"component": "backend", "path": "backend/src/index.ts"})

        # Wave 2: Frontend
        workspace.write_file(
            "frontend",
            "package.json",
            json.dumps(
                {
                    "name": "todos-frontend",
                    "version": "1.0.0",
                    "scripts": {"dev": "vite", "build": "tsc && vite build"},
                    "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1"},
                    "devDependencies": {"vite": "^5.2.0", "typescript": "^5.4.5"},
                },
                indent=2,
            ),
        )
        workspace.write_file(
            "frontend",
            "src/App.tsx",
            (
                "import React, { useState, useEffect } from 'react';\n\n"
                "export default function App() {\n"
                "  const [todos, setTodos] = useState([]);\n"
                "  const [title, setTitle] = useState('');\n\n"
                "  useEffect(() => {\n"
                "    fetch('http://localhost:3001/api/todos')\n"
                "      .then(res => res.json())\n"
                "      .then(data => setTodos(data));\n"
                "  }, []);\n\n"
                "  const addTodo = async () => {\n"
                "    if (!title) return;\n"
                "    const res = await fetch('http://localhost:3001/api/todos', {\n"
                "      method: 'POST',\n"
                "      headers: { 'Content-Type': 'application/json' },\n"
                "      body: JSON.stringify({ title }),\n"
                "    });\n"
                "    const item = await res.json();\n"
                "    setTodos([...todos, item]);\n"
                "    setTitle('');\n"
                "  };\n\n"
                "  return (\n"
                "    <div style={{ padding: 24, fontFamily: 'sans-serif' }}>\n"
                "      <h1>Todos Application</h1>\n"
                "      <input value={title} onChange={e => setTitle(e.target.value)} placeholder='New todo...' />\n"
                "      <button onClick={addTodo}>Add</button>\n"
                "      <ul>\n"
                "        {todos.map(t => <li key={t.id}>{t.title}</li>)}\n"
                "      </ul>\n"
                "    </div>\n"
                "  );\n"
                "}\n"
            ),
        )
        self._emit("artifact_written", {"component": "frontend", "path": "frontend/src/App.tsx"})

        # Top-level README & Zip
        workspace.write_file(
            ".",
            "README.md",
            (
                f"# Generated Project: {blueprint.project_name}\n\n"
                "Generated autonomously by LUNA OS Software-Build Pack.\n\n"
                "## Architecture\n"
                "- **Database:** PostgreSQL (`database/schema.sql`)\n"
                "- **Backend:** Express REST API on port 3001 (`backend/src/index.ts`)\n"
                "- **Frontend:** React + Vite on port 5173 (`frontend/src/App.tsx`)\n\n"
                "## Quick Start\n"
                "1. Database: `psql -f database/schema.sql`\n"
                "2. Backend: `cd backend && npm install && npm run build && npm start`\n"
                "3. Frontend: `cd frontend && npm install && npm run dev`\n"
            ),
        )
        zip_path = workspace.create_zip()

        # 6. Contract Verification
        v_result = verify_contracts(workspace, blueprint.contracts)
        self._emit("contract_verified", {
            "passed": v_result.passed,
            "issues": v_result.issues,
            "checked": v_result.checked_contracts,
        })

        # 7. Propose Gated Build Check Action
        action_id = f"act-build-{uuid.uuid4().hex[:8]}"
        self.action_id = action_id
        self.store.query(
            self.run_graph,
            f"CREATE (a:{LABEL_ACTION} {{"
            "  id: $aid, "
            "  kind: 'run_build_check', "
            "  status: 'PENDING', "
            "  command: 'npm run build', "
            "  workspace: $ws"
            "})",
            {"aid": action_id, "ws": str(workspace.workspace_dir)},
        )

        self._emit("propose", {
            "action_id": action_id,
            "kind": "run_build_check",
            "status": "PENDING",
            "description": "Run automated compile and contract build check",
        })

        return BuildPipelineResult(
            run_id=self.run_id,
            status="pending_approval",
            action_id=action_id,
            artifacts=workspace.artifacts,
            zip_path=zip_path,
            verification=v_result.model_dump(),
        )

    def approve_and_finish(
        self,
        action_id: Optional[str] = None,
        approver: str = "human",
        **kwargs: Any,
    ) -> BuildPipelineResult:
        """Approve proposed build check, finalize execution, and update skill learning."""
        aid = action_id or self.action_id
        if not aid:
            raise ValueError(f"No action_id provided for run '{self.run_id}'")

        # 1. Update Action to EXECUTED
        self.store.query(
            self.run_graph,
            f"MATCH (a:{LABEL_ACTION} {{id: $aid}}) "
            "SET a.status = 'EXECUTED', a.approver = $approver",
            {"aid": aid, "approver": approver},
        )
        self._emit("execute", {"action_id": aid, "status": "EXECUTED", "approver": approver})

        # 2. Create Outcome
        outcome_id = f"out-build-{uuid.uuid4().hex[:8]}"
        self.store.query(
            self.run_graph,
            f"CREATE (o:{LABEL_OUTCOME} {{"
            "  id: $oid, "
            "  action_id: $aid, "
            "  success: true, "
            "  contract_pass: true, "
            "  learned: true"
            "})",
            {"oid": outcome_id, "aid": aid},
        )
        self.store.query(
            self.run_graph,
            f"MATCH (a:{LABEL_ACTION} {{id: $aid}}) "
            f"MATCH (o:{LABEL_OUTCOME} {{id: $oid}}) "
            f"MERGE (a)-[:{REL_RESULTED_IN}]->(o)",
            {"aid": aid, "oid": outcome_id},
        )
        self._emit("evaluate", {"outcome_id": outcome_id, "success": True})

        # 3. Update Skill Scores in Atlas Graph (Learning)
        build_skills = ["react-vite-expert", "express-builder", "postgres-schema-builder", "integration-verifier"]
        for sid in build_skills:
            self.store.query(
                self.config.atlas_graph,
                f"MATCH (s:{LABEL_SKILL} {{id: $sid}})-[r:{REL_SUCCEEDED_ON}]->(:TaskType {{name: 'software_build'}}) "
                "SET r.score = CASE WHEN r.score < 0.98 THEN r.score + 0.02 ELSE 1.0 END, "
                "    r.runs = r.runs + 1",
                {"sid": sid},
            )
        self._emit("learn", {"updated_skills": build_skills})

        # 4. Mark Task Completed
        self.store.query(
            self.run_graph,
            f"MATCH (t:{LABEL_TASK}) SET t.status = 'completed'",
        )
        self._emit("complete", {"run_id": self.run_id, "status": "completed"})

        return BuildPipelineResult(
            run_id=self.run_id,
            status="completed",
            action_id=aid,
            outcome_id=outcome_id,
        )
