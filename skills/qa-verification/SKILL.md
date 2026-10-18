---
name: QA Verification
description: Verify the finished build compiles, runs, and that the frontend and API agree on their contracts.
capabilities: [verify_contracts]
technologies: [TypeScript, Python]
checklist:
  - id: build
    text: Every package builds and type-checks cleanly (npm run build, tsc --noEmit, python -m compileall) with no errors.
  - id: smoke
    text: The app starts and every page and endpoint in the plan responds correctly in a recorded smoke run.
  - id: contracts
    text: Every API call made by the frontend matches an implemented endpoint's path, method, request body and response shape.
---
You are the last task. Do not add features; find and fix defects that stop the build from
working, and report anything you could not fix. Read every upstream task's submission first.

## Build and type checks
- Frontend: `npm ci` (or `npm install`), `npm run build`, and `npx tsc --noEmit`.
  Treat TypeScript errors as failures, not warnings.
- Python API: `python -m compileall api` and, if present, `pytest -q`.
- Node API: `npx tsc --noEmit -p api` and the project's test command if present.
- Fix root causes. Never silence errors with `any`, `// @ts-ignore`, `# type: ignore` or by
  deleting the failing code.

## Smoke test
- Start the API (port 8000) and the frontend (`npm run dev`, port 5173) the way the README says.
- Request `GET /health`, then each list endpoint, one create, one update and one delete;
  record method, path, status code and a short note for each.
- Open every route in the browser at 375px and 1280px; confirm there are no console errors,
  no failed network requests, and that loading, empty and error states render.
- If the README commands do not work as written, fix the README or the scripts.

## Contract check
- List every `fetch`/client call in `src/` (path, method, body type, expected response type)
  and every route the API defines.
- For each frontend call confirm a matching route exists, the HTTP method matches, the
  request fields and casing match the API model, and the response type matches what the API
  returns, including status codes for errors.
- Confirm the API's CORS origin matches the frontend dev URL and that `VITE_API_URL` is set
  in `.env.example`.
- Flag endpoints nobody calls and calls with no endpoint as contract gaps.

## Report
- Submit a table of checks with pass/fail and the command or URL used, the list of fixes
  you made with file paths, and any remaining gaps with a suggested owner task.
