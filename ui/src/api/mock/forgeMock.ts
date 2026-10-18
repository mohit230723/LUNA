import type {
  Api,
  ForgeAgent,
  ForgeEvent,
  ForgeReport,
  ForgeRunDetail,
  ForgeRunSummary,
  ForgeSkillDetail,
  ForgeSkillSummary,
  ForgeTask,
} from '../contract';

type ForgeMethods =
  | 'forgeConnect'
  | 'forgeAgents'
  | 'forgeRuns'
  | 'forgeRun'
  | 'subscribeForge'
  | 'forgeSkills'
  | 'forgeSkill'
  | 'uploadForgeSkill'
  | 'approveForgeSkill'
  | 'rejectForgeSkill'
  | 'reimportForgeSkills';

const RUN_ID = 'run-portfolio-1';
const NOW = '2026-10-19T09:00:00+00:00';

const task = (
  task_id: string,
  title: string,
  capability: string,
  skill_id: string,
  depends_on: string[],
  wave: number,
  status: string,
  extra: Partial<ForgeTask> = {}
): ForgeTask => ({
  task_id,
  title,
  capability,
  skill_id,
  depends_on,
  wave,
  status,
  claimed_by: '',
  agent_label: '',
  lease_expires_at: '',
  assignment: null,
  candidates: [],
  result: null,
  ...extra,
});

const FIXTURE_TASKS: ForgeTask[] = [
  task('scaffold_project', 'Scaffold the project', 'scaffold', 'project-scaffold', [], 0, 'done', {
    claimed_by: 'sess-claude',
    agent_label: 'claude-code',
    result: { summary: 'Vite + React scaffold created', files: ['package.json', 'src/main.tsx'], checks: [] },
  }),
  task('implement_frontend', 'Build the portfolio pages', 'frontend', 'react-vite-pages', ['scaffold_project'], 1, 'claimed', {
    claimed_by: 'sess-claude',
    agent_label: 'claude-code',
    lease_expires_at: '2026-10-19T09:30:00+00:00',
  }),
  task('qa_verification', 'Verify the build', 'qa', 'qa-verification', ['implement_frontend'], 2, 'pending'),
];

function fixtureRun(): ForgeRunDetail {
  return {
    run: { run_id: RUN_ID, prompt: 'Build a portfolio website', status: 'running', created_at: NOW },
    tasks: FIXTURE_TASKS.map((t) => ({ ...t })),
    report: null,
  };
}

const AGENTS: ForgeAgent[] = [
  {
    session_id: 'sess-claude',
    client_name: 'claude-code',
    client_version: '2.0.0',
    first_seen: NOW,
    last_seen: NOW,
    connected: true,
  },
  {
    session_id: 'sess-antigravity',
    client_name: 'antigravity',
    client_version: '1.0.0',
    first_seen: NOW,
    last_seen: '2026-10-19T08:00:00+00:00',
    connected: false,
  },
];

const skill = (
  id: string,
  name: string,
  description: string,
  capabilities: string[],
  technologies: string[],
  status = 'approved',
  source = 'repo'
): ForgeSkillSummary => ({
  id,
  name,
  description,
  status,
  source,
  capabilities,
  technologies,
  warnings_count: 0,
});

const SKILLS: ForgeSkillSummary[] = [
  skill('backend-api', 'Backend API', 'Design and build HTTP APIs.', ['backend'], ['fastapi']),
  skill('database-schema', 'Database Schema', 'Model tables and migrations.', ['database'], ['postgres']),
  skill('project-scaffold', 'Project Scaffold', 'Bootstrap a new project.', ['scaffold'], ['vite']),
  skill('qa-verification', 'QA Verification', 'Verify builds, tests and lint.', ['qa'], ['vitest']),
  skill('react-vite-pages', 'React Vite Pages', 'Build pages with React and Vite.', ['frontend'], ['react', 'vite']),
  skill('ui-styling', 'UI Styling', 'Style interfaces consistently.', ['styling'], ['css']),
  skill('uploaded-seo', 'SEO Audit', 'Uploaded skill awaiting review.', ['seo'], ['html'], 'pending_review', 'upload'),
];

function skillDetail(s: ForgeSkillSummary): ForgeSkillDetail {
  return {
    id: s.id,
    name: s.name,
    description: s.description,
    status: s.status,
    source: s.source,
    body: `# ${s.name}\n\n${s.description}\n`,
    capabilities: s.capabilities,
    technologies: s.technologies,
    sections: [{ slug: 'overview', title: 'Overview', content: s.description, order: 0 }],
    checklist: [{ id: 'c1', text: 'Output verified' }],
    requires: [],
    required_by: [],
    neighbourhood: {
      nodes: [
        { id: s.id, label: s.name, type: 'skill' },
        ...s.capabilities.map((c) => ({ id: c, label: c, type: 'capability' })),
      ],
      edges: s.capabilities.map((c) => ({ source: s.id, target: c, type: 'PROVIDES' })),
    },
  };
}

const REPORT: ForgeReport = {
  run_id: RUN_ID,
  status: 'complete',
  missing: [],
  tasks: FIXTURE_TASKS.map((t) => ({ task_id: t.task_id, status: 'done', summary: t.title, files: [] })),
  overlaps: {},
  gaps: [],
  summary: '3 of 3 tasks complete.',
};

function scriptedEvents(): ForgeEvent[] {
  const ev = (seq: number, type: string, data: Record<string, unknown>): ForgeEvent => ({
    seq,
    ts: NOW,
    type,
    data,
  });
  return [
    ev(1, 'task_updated', {
      run_id: RUN_ID,
      task_id: 'implement_frontend',
      status: 'done',
      claimed_by: 'sess-claude',
      agent_label: 'claude-code',
      result: { summary: 'Pages built', files: ['src/App.tsx'], checks: [] },
    }),
    ev(2, 'task_updated', { run_id: RUN_ID, task_id: 'qa_verification', status: 'ready' }),
    ev(3, 'run_assembled', { run_id: RUN_ID, report: REPORT }),
  ];
}

let skills = SKILLS.map((s) => ({ ...s }));

export const forgeMockMethods: Pick<Api, ForgeMethods> = {
  forgeConnect: () =>
    Promise.resolve({
      mcp_url: 'http://localhost:8000/mcp',
      token_required: false,
      snippets: {
        claude_code: 'claude mcp add --transport http luna http://localhost:8000/mcp',
        antigravity: '{"mcpServers":{"luna":{"serverUrl":"http://localhost:8000/mcp"}}}',
        claude_code_token:
          'claude mcp add --transport http luna http://localhost:8000/mcp --header "Authorization: Bearer <token>"',
        antigravity_token:
          '{"mcpServers":{"luna":{"serverUrl":"http://localhost:8000/mcp","headers":{"Authorization":"Bearer <token>"}}}}',
      },
    }),
  forgeAgents: () => Promise.resolve(AGENTS.map((a) => ({ ...a }))),
  forgeRuns: () => {
    const summary: ForgeRunSummary = {
      run_id: RUN_ID,
      prompt: 'Build a portfolio website',
      status: 'running',
      created_at: NOW,
      task_count: FIXTURE_TASKS.length,
    };
    return Promise.resolve([summary]);
  },
  forgeRun: (runId) =>
    runId === RUN_ID ? Promise.resolve(fixtureRun()) : Promise.reject(new Error(`run '${runId}' not found`)),
  subscribeForge: (opts) => {
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];
    const pending = scriptedEvents().filter((e) => e.seq > (opts.lastEventId ?? 0));
    opts.onState('open');
    pending.forEach((e, i) => {
      timers.push(
        setTimeout(() => {
          if (!cancelled) opts.onEvent(e);
        }, 1500 * (i + 1))
      );
    });
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      opts.onState('closed');
    };
  },
  forgeSkills: () => Promise.resolve(skills.map((s) => ({ ...s }))),
  forgeSkill: (id) => {
    const s = skills.find((x) => x.id === id);
    return s ? Promise.resolve(skillDetail(s)) : Promise.reject(new Error(`skill '${id}' not found`));
  },
  uploadForgeSkill: (file) => {
    const id = file.name.replace(/\.md$/i, '').toLowerCase() || 'uploaded-skill';
    skills = [...skills, skill(id, id, 'Uploaded skill awaiting review.', [], [], 'pending_review', 'upload')];
    return Promise.resolve({ skill_id: id, status: 'pending_review', warnings: [] });
  },
  approveForgeSkill: (id) => {
    skills = skills.map((s) => (s.id === id ? { ...s, status: 'approved' } : s));
    return Promise.resolve();
  },
  rejectForgeSkill: (id) => {
    skills = skills.map((s) => (s.id === id ? { ...s, status: 'rejected' } : s));
    return Promise.resolve();
  },
  reimportForgeSkills: () => Promise.resolve([]),
};
