---
name: Project Scaffold
description: Create a runnable Vite + React + TypeScript project skeleton with scripts, layout and a README.
capabilities: [scaffold_project]
technologies: [Vite, React, TypeScript, Node]
checklist:
  - id: runs
    text: "`npm install` then `npm run dev` and `npm run build` succeed with no errors on a clean checkout."
  - id: readme
    text: README.md states the stack, the prerequisites, and the exact commands to install, run, build and test.
---
You lay the foundation every other task builds on. Keep it minimal, conventional and
runnable: later tasks add pages, styling, an API and a database on top of what you create.

## Create the project
- Require Node 20+ (`node --version`). Use npm unless the repo already has a lockfile for pnpm or yarn.
- Generate with `npm create vite@latest <name> -- --template react-ts`, or copy its layout
  if the directory is not empty. Never overwrite existing source files without reading them.
- Keep the standard layout: `index.html`, `src/main.tsx`, `src/App.tsx`, `src/index.css`,
  `public/`, `vite.config.ts`, `tsconfig.json`, `tsconfig.node.json`.
- Turn on `"strict": true` in `tsconfig.json`; do not weaken it to make code compile.
- Add `src/pages/` and `src/components/` folders (with a `.gitkeep` if empty) so the
  frontend task has an obvious home for routes and components.
- If the plan includes a backend, put the client in `web/` and leave `api/` for the server;
  otherwise keep the client at the repository root.

## Scripts and configuration
- `package.json` scripts must include: `dev` (`vite`), `build` (`tsc -b && vite build`),
  `preview` (`vite preview`) and `lint` (`tsc --noEmit` is enough if no linter is set up).
- Add a `.gitignore` covering `node_modules/`, `dist/`, `.env`, `.env.local`, `*.log`.
- Add `.env.example` listing every variable the app reads (for example `VITE_API_URL=`),
  never real secrets. Read client variables only through `import.meta.env.VITE_*`.
- Pin `engines.node` to `>=20` in `package.json`.

## README
- Title and a one-sentence description of what is being built.
- A "Stack" list naming each technology and its version from `package.json`.
- "Getting started": prerequisites, `npm install`, `npm run dev`, the local URL
  (default http://localhost:5173), `npm run build`, and how to run tests if any exist.
- A short "Project layout" section mapping each top-level folder to its purpose.

## Verify before handing off
- Run `npm install`, `npm run build` and start `npm run dev` once; fix every error and warning
  that comes from your own files.
- Replace the Vite demo counter in `App.tsx` with a neutral placeholder heading so the
  frontend task starts clean, and remove unused demo assets.
- Report the exact commands you ran and their results in your submission.
