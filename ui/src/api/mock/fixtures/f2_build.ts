import {
  ActionRequest,
  ActionResult,
  Block,
  FileNode,
  RunEvent,
  SkillAssignment,
  TraceResponse,
} from '../../contract';

export const F2_RUN_ID = 'run_build_002';

export const F2_SKILL_ASSIGNMENTS: SkillAssignment[] = [
  {
    subject: 'database',
    chosen: 'db-postgres',
    fit: 0.92,
    backend: 'scripted',
    rejected: [
      { skill: 'db-mongodb', reason: 'tech_mismatch' },
      { skill: 'db-sqlite', reason: 'tech_mismatch' },
    ],
  },
  {
    subject: 'api',
    chosen: 'backend-express',
    fit: 0.88,
    backend: 'scripted',
    rejected: [
      { skill: 'backend-fastify', reason: 'tech_mismatch' },
      { skill: 'backend-nestjs', reason: 'tech_mismatch' },
    ],
  },
  {
    subject: 'web',
    chosen: 'frontend-react-vite',
    fit: 0.9,
    backend: 'scripted',
    rejected: [
      { skill: 'frontend-nextjs', reason: 'tech_mismatch' },
      { skill: 'frontend-vue-vite', reason: 'tech_mismatch' },
    ],
  },
  {
    subject: 'verify',
    chosen: 'integration-verifier',
    fit: 0.85,
    backend: 'scripted',
    rejected: [{ skill: 'shell-runner', reason: 'policy_restricted' }],
  },
];

export const F2_FILES_TREE: FileNode[] = [
  { path: 'README.md', kind: 'file', bytes: 640 },
  {
    path: 'database',
    kind: 'dir',
    children: [
      { path: 'database/schema.sql', kind: 'file', bytes: 512 },
      { path: 'database/seed.sql', kind: 'file', bytes: 280 },
    ],
  },
  {
    path: 'api',
    kind: 'dir',
    children: [
      { path: 'api/package.json', kind: 'file', bytes: 340 },
      { path: 'api/.env.example', kind: 'file', bytes: 120 },
      { path: 'api/src/index.js', kind: 'file', bytes: 480 },
      { path: 'api/src/db.js', kind: 'file', bytes: 310 },
      { path: 'api/src/routes/todos.js', kind: 'file', bytes: 1240 },
    ],
  },
  {
    path: 'web',
    kind: 'dir',
    children: [
      { path: 'web/package.json', kind: 'file', bytes: 390 },
      { path: 'web/index.html', kind: 'file', bytes: 260 },
      { path: 'web/vite.config.js', kind: 'file', bytes: 180 },
      { path: 'web/src/main.jsx', kind: 'file', bytes: 210 },
      { path: 'web/src/App.jsx', kind: 'file', bytes: 1100 },
      { path: 'web/src/api.js', kind: 'file', bytes: 620 },
      { path: 'web/src/styles.css', kind: 'file', bytes: 450 },
    ],
  },
];

export const F2_FILE_CONTENTS: Record<string, string> = {
  'README.md': `# Todo Application\n\nFull-stack reactive todo platform built with React, Vite, Express, and PostgreSQL.\n\n## Getting Started\n\n1. Start Database:\n   \`psql -U postgres -d todos -f database/schema.sql\`\n2. Run API server:\n   \`cd api && npm install && npm run dev\`\n3. Run Web client:\n   \`cd web && npm install && npm run dev\`\n`,
  'database/schema.sql': `CREATE TABLE IF NOT EXISTS todos (\n  id SERIAL PRIMARY KEY,\n  title VARCHAR(255) NOT NULL,\n  done BOOLEAN DEFAULT FALSE,\n  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP\n);\n`,
  'api/src/routes/todos.js': `const express = require('express');\nconst router = express.Router();\nconst db = require('../db');\n\nrouter.get('/', async (req, res) => {\n  const result = await db.query('SELECT * FROM todos ORDER BY id ASC');\n  res.json(result.rows);\n});\n\nrouter.post('/', async (req, res) => {\n  const { title } = req.body;\n  const result = await db.query('INSERT INTO todos (title) VALUES ($1) RETURNING *', [title]);\n  res.status(201).json(result.rows[0]);\n});\n\nrouter.patch('/:id', async (req, res) => {\n  const { id } = req.params;\n  const { done } = req.body;\n  const result = await db.query('UPDATE todos SET done = $1 WHERE id = $2 RETURNING *', [done, id]);\n  res.json(result.rows[0]);\n});\n\nrouter.delete('/:id', async (req, res) => {\n  const { id } = req.params;\n  await db.query('DELETE FROM todos WHERE id = $1', [id]);\n  res.status(204).end();\n});\n\nmodule.exports = router;\n`,
  'web/src/api.js': `const API_BASE = '/api/todos';\n\nexport async function getTodos() {\n  const res = await fetch(API_BASE);\n  return res.json();\n}\n\nexport async function createTodo(title) {\n  const res = await fetch(API_BASE, {\n    method: 'POST',\n    headers: { 'Content-Type': 'application/json' },\n    body: JSON.stringify({ title }),\n  });\n  return res.json();\n}\n`,
};

export const F2_ACTION_REQUEST: ActionRequest = {
  action_id: 'act_build_check_002',
  kind: 'run_build_check',
  status: 'PENDING',
  commands: [
    { cmd: 'npm install --prefix api && npm install --prefix web', timeout_s: 180 },
    { cmd: 'npm run build --prefix web', timeout_s: 180 },
  ],
  reason: 'Execute automated build and bundling verification across client and server packages',
};

export const F2_ACTION_RESULT_SUCCESS: ActionResult = {
  ok: true,
  commands: [
    {
      cmd: 'npm install --prefix api && npm install --prefix web',
      exit_code: 0,
      log_tail: 'added 245 packages in 3.4s\naudited 245 packages in 3.5s\nfound 0 vulnerabilities',
      executed: true,
    },
    {
      cmd: 'npm run build --prefix web',
      exit_code: 0,
      log_tail: 'vite v6.1.0 building for production...\n✓ 42 modules transformed.\ndist/index.html 0.45 kB\ndist/assets/index.js 142 kB\n✓ built in 480ms',
      executed: true,
    },
  ],
};

export const F2_ACTION_RESULT_NOT_EXECUTED: ActionResult = {
  ok: false,
  commands: [
    {
      cmd: 'npm install',
      exit_code: null,
      log_tail: '',
      executed: false,
      note: 'npm binary not found in container execution path',
    },
  ],
};

export const F2_TRACE: TraceResponse = {
  mode: 'blueprint',
  summary:
    'Decomposed into 4 components (database, api, web, docs). Satisfied 7 inter-component contracts with 1 violation remediated.',
  path_node_ids: ['comp_db', 'comp_api', 'comp_web', 'cnt_endpoint_todos', 'art_routes'],
  nodes: [
    { id: 'req_frontend', label: 'React + Vite', props: { type: 'Requirement', kind: 'frontend' } },
    { id: 'req_backend', label: 'Express', props: { type: 'Requirement', kind: 'backend' } },
    { id: 'req_database', label: 'Postgres', props: { type: 'Requirement', kind: 'database' } },
    { id: 'comp_db', label: 'database', props: { type: 'Component', tech: 'postgres' } },
    { id: 'comp_api', label: 'api', props: { type: 'Component', tech: 'express' } },
    { id: 'comp_web', label: 'web', props: { type: 'Component', tech: 'react+vite' } },
    { id: 'comp_docs', label: 'docs', props: { type: 'Component', tech: 'markdown' } },
    { id: 'sk_db', label: 'db-postgres', props: { type: 'SkillRef' } },
    { id: 'sk_api', label: 'backend-express', props: { type: 'SkillRef' } },
    { id: 'sk_web', label: 'frontend-react-vite', props: { type: 'SkillRef' } },
    { id: 'sk_verify', label: 'integration-verifier', props: { type: 'SkillRef' } },
    { id: 'cnt_endpoint_todos', label: 'GET /api/todos', props: { type: 'Contract', kind: 'endpoint' } },
    { id: 'cnt_table_todos', label: 'table todos', props: { type: 'Contract', kind: 'table' } },
    { id: 'art_schema', label: 'schema.sql', props: { type: 'Artifact', path: 'database/schema.sql' } },
    { id: 'art_routes', label: 'todos.js', props: { type: 'Artifact', path: 'api/src/routes/todos.js' } },
    { id: 'art_app', label: 'App.jsx', props: { type: 'Artifact', path: 'web/src/App.jsx' } },
    { id: 'viol_01', label: 'Singular Route', props: { type: 'Violation', status: 'resolved' } },
  ],
  edges: [
    { id: 'eb_01', src: 'req_database', dst: 'comp_db', rel: 'HAS_REQUIREMENT', on_path: true },
    { id: 'eb_02', src: 'req_backend', dst: 'comp_api', rel: 'HAS_REQUIREMENT', on_path: true },
    { id: 'eb_03', src: 'req_frontend', dst: 'comp_web', rel: 'HAS_REQUIREMENT', on_path: true },
    { id: 'eb_04', src: 'comp_api', dst: 'comp_db', rel: 'DEPENDS_ON', on_path: true },
    { id: 'eb_05', src: 'comp_web', dst: 'comp_api', rel: 'DEPENDS_ON', on_path: true },
    { id: 'eb_06', src: 'comp_api', dst: 'cnt_endpoint_todos', rel: 'PROVIDES', on_path: true },
    { id: 'eb_07', src: 'comp_web', dst: 'cnt_endpoint_todos', rel: 'CONSUMES', on_path: true },
    { id: 'eb_08', src: 'sk_api', dst: 'comp_api', rel: 'CHOSE', on_path: true },
    { id: 'eb_09', src: 'comp_api', dst: 'art_routes', rel: 'WROTE', on_path: true },
    { id: 'eb_10', src: 'art_routes', dst: 'cnt_endpoint_todos', rel: 'IMPLEMENTS', on_path: true },
  ],
  steps: [
    { seq: 1, from: 'req_database', to: 'comp_db', rel: 'HAS_REQUIREMENT', tool: 'planner', agent_id: 'orchestrator', note: 'Mapped database requirement to PostgreSQL component' },
    { seq: 2, from: 'comp_api', to: 'sk_api', rel: 'CHOSE', tool: 'atlas_query', agent_id: 'orchestrator', note: 'Assigned backend-express skill; rejected fastify and nestjs' },
    { seq: 3, from: 'comp_db', to: 'art_schema', rel: 'WROTE', tool: 'fs_writer', agent_id: 'agent_db', note: 'Wrote database/schema.sql' },
    { seq: 4, from: 'comp_api', to: 'art_routes', rel: 'WROTE', tool: 'fs_writer', agent_id: 'agent_api', note: 'Wrote api/src/routes/todos.js declaring contracts' },
    { seq: 5, from: 'comp_web', to: 'viol_01', rel: 'VIOLATION', tool: 'contract_checker', agent_id: 'agent_verifier', note: 'Contract violation: web called GET /api/todo instead of /api/todos' },
    { seq: 6, from: 'comp_web', to: 'art_app', rel: 'REMEDIATED', tool: 'code_patcher', agent_id: 'agent_web', note: 'Remediated endpoint URL in web/src/api.js' },
  ],
  truncated: false,
};

export const F2_BLOCKS: Block[] = [
  {
    type: 'routing',
    data: {
      pack: 'build',
      intent: 'Generate full-stack React + Express + Postgres application',
      confidence: 0.99,
      backend: 'scripted',
    },
  },
  {
    type: 'plan',
    data: {
      components: [
        { id: 'comp_db', name: 'database', kind: 'database', tech: 'postgres' },
        { id: 'comp_api', name: 'api', kind: 'backend', tech: 'express' },
        { id: 'comp_web', name: 'web', kind: 'frontend', tech: 'react+vite' },
        { id: 'comp_docs', name: 'docs', kind: 'docs', tech: 'markdown' },
      ],
      contracts: [
        { id: 'cnt_01', kind: 'endpoint', key: 'GET /api/todos', status: 'implemented' },
        { id: 'cnt_02', kind: 'endpoint', key: 'POST /api/todos', status: 'implemented' },
        { id: 'cnt_03', kind: 'endpoint', key: 'PATCH /api/todos/:id', status: 'implemented' },
        { id: 'cnt_04', kind: 'endpoint', key: 'DELETE /api/todos/:id', status: 'implemented' },
        { id: 'cnt_05', kind: 'table', key: 'table todos(id, title, done, created_at)', status: 'implemented' },
        { id: 'cnt_06', kind: 'env', key: 'DATABASE_URL', status: 'implemented' },
        { id: 'cnt_07', kind: 'port', key: 'PORT=3001', status: 'implemented' },
      ],
    },
  },
  {
    type: 'skills',
    data: {
      assignments: F2_SKILL_ASSIGNMENTS,
    },
  },
  {
    type: 'files',
    data: {
      tree: F2_FILES_TREE,
      zip_url: '/api/runs/run_build_002/artifacts.zip',
      contracts_implemented: 7,
      contracts_total: 7,
      open_violations: [],
    },
  },
  {
    type: 'action_request',
    data: F2_ACTION_REQUEST,
  },
  {
    type: 'answer',
    data: {
      text: `Your full-stack todo application has been scaffolded across 13 files with complete schema definitions, Express REST routes, and reactive React components.\n\n7 of 7 inter-component contracts implemented. Database schema matches REST endpoints. Build check is pending your approval.\n\nNOT EXECUTED: Automated npm build checks run only after human approval.`,
      cited_cids: [],
      backend: 'scripted',
    },
  },
];

export const F2_EVENTS: RunEvent[] = [
  { run_id: F2_RUN_ID, seq: 1, ts: '2026-10-18T09:10:00Z', type: 'routed', backend: 'scripted', data: { pack: 'build', intent: 'Scaffold todo app' } },
  { run_id: F2_RUN_ID, seq: 2, ts: '2026-10-18T09:10:01Z', type: 'requirements', backend: 'scripted', data: { frontend: 'react+vite', backend: 'express', database: 'postgres' } },
  { run_id: F2_RUN_ID, seq: 3, ts: '2026-10-18T09:10:02Z', type: 'blueprint', backend: 'scripted', data: { components: 4, contracts: 7 } },
  { run_id: F2_RUN_ID, seq: 4, ts: '2026-10-18T09:10:03Z', type: 'skill_assigned', backend: 'scripted', data: { assignments: F2_SKILL_ASSIGNMENTS } },
  { run_id: F2_RUN_ID, seq: 5, ts: '2026-10-18T09:10:04Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_db', skill: 'db-postgres' } },
  { run_id: F2_RUN_ID, seq: 6, ts: '2026-10-18T09:10:05Z', type: 'artifact_written', backend: 'scripted', data: { path: 'database/schema.sql' } },
  { run_id: F2_RUN_ID, seq: 7, ts: '2026-10-18T09:10:06Z', type: 'agent_done', backend: 'scripted', data: { agent_id: 'agent_db' } },
  { run_id: F2_RUN_ID, seq: 8, ts: '2026-10-18T09:10:07Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_api', skill: 'backend-express' } },
  { run_id: F2_RUN_ID, seq: 9, ts: '2026-10-18T09:10:08Z', type: 'artifact_written', backend: 'scripted', data: { path: 'api/src/routes/todos.js' } },
  { run_id: F2_RUN_ID, seq: 10, ts: '2026-10-18T09:10:09Z', type: 'agent_done', backend: 'scripted', data: { agent_id: 'agent_api' } },
  { run_id: F2_RUN_ID, seq: 11, ts: '2026-10-18T09:10:10Z', type: 'agent_started', backend: 'scripted', data: { agent_id: 'agent_web', skill: 'frontend-react-vite' } },
  { run_id: F2_RUN_ID, seq: 12, ts: '2026-10-18T09:10:11Z', type: 'contract_violation', backend: 'scripted', data: { violation: 'Singular route GET /api/todo undeclared' } },
  { run_id: F2_RUN_ID, seq: 13, ts: '2026-10-18T09:10:12Z', type: 'remediation', backend: 'scripted', data: { round: 1, resolved: true } },
  { run_id: F2_RUN_ID, seq: 14, ts: '2026-10-18T09:10:13Z', type: 'artifact_written', backend: 'scripted', data: { path: 'web/src/App.jsx' } },
  { run_id: F2_RUN_ID, seq: 15, ts: '2026-10-18T09:10:14Z', type: 'agent_done', backend: 'scripted', data: { agent_id: 'agent_web' } },
  { run_id: F2_RUN_ID, seq: 16, ts: '2026-10-18T09:10:15Z', type: 'action_proposed', backend: 'scripted', data: F2_ACTION_REQUEST },
  { run_id: F2_RUN_ID, seq: 17, ts: '2026-10-18T09:10:16Z', type: 'answer', backend: 'scripted', data: { text: F2_BLOCKS[4]?.data } },
  { run_id: F2_RUN_ID, seq: 18, ts: '2026-10-18T09:10:17Z', type: 'completed', backend: 'scripted', data: { run_id: F2_RUN_ID } },
];
