import { Block } from '../../contract';

export const F4_RUN_ID = 'run_clarification_004';

export const F4_BLOCKS: Block[] = [
  {
    type: 'routing',
    data: {
      pack: 'build',
      intent: 'Initialize project with custom stack',
      confidence: 0.95,
      backend: 'scripted',
    },
  },
  {
    type: 'needs_input',
    data: {
      question: 'Svelte is not in the Skill Atlas. Which frontend should I use?',
      options: ['React + Vite', 'Vue + Vite', 'Next.js'],
      allow_free_text: false,
    },
  },
];

export const F4_EVENTS: any[] = [
  { run_id: F4_RUN_ID, seq: 1, ts: '2026-10-18T09:30:00Z', type: 'routed', backend: 'scripted', data: { pack: 'build' } },
  { run_id: F4_RUN_ID, seq: 2, ts: '2026-10-18T09:30:01Z', type: 'requirements', backend: 'scripted', data: { frontend: 'svelte', status: 'unsupported' } },
  {
    run_id: F4_RUN_ID,
    seq: 3,
    ts: '2026-10-18T09:30:02Z',
    type: 'needs_input',
    backend: 'scripted',
    data: {
      question: 'Svelte is not in the Skill Atlas. Which frontend should I use?',
      options: ['React + Vite', 'Vue + Vite', 'Next.js'],
    },
  },
];
