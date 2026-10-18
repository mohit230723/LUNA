---
name: Backend API
description: Build a JSON REST API with FastAPI (Python) or Express (Node) that the frontend can call.
capabilities: [implement_backend]
technologies: [FastAPI, Express, Python, Node]
requires: [project-scaffold]
checklist:
  - id: endpoints
    text: Every resource in the request has documented list/get/create/update/delete endpoints plus GET /health.
  - id: errors
    text: 'Invalid input returns 400/422 and missing records 404, both with a JSON body of the form {"error": "..."}; no stack traces leak.'
  - id: cors
    text: CORS allows exactly the frontend origin from configuration, not "*", and the frontend can call the API from the browser.
---
You build the HTTP API in `api/`. Use FastAPI when the request says Python or FastAPI,
otherwise Express with TypeScript. Read the database task's schema before writing handlers.

## FastAPI (Python)
- Python 3.11+, a `requirements.txt` with `fastapi`, `uvicorn[standard]` and `pydantic`.
- Layout: `api/main.py` (app, CORS, routers), `api/routes/<resource>.py`, `api/models.py`
  (Pydantic request/response models), `api/db.py` (connection from the database task).
- Separate `Create`, `Update` and `Read` models; never return database rows directly.
- Run with `uvicorn api.main:app --reload --port 8000`; the docs at `/docs` must load.

## Express (Node)
- Node 20+, `express`, `cors`, `zod`, and `tsx` for development. Layout: `api/src/server.ts`,
  `api/src/routes/<resource>.ts`, `api/src/schemas.ts`.
- Call `app.use(express.json())`, validate every body and param with zod, and run with
  `tsx watch src/server.ts` on port 8000.
- End with one error-handling middleware `(err, req, res, next)` that logs and returns JSON.

## Endpoint conventions
- REST routes under `/api`: `GET /api/<items>`, `GET /api/<items>/{id}`, `POST /api/<items>`,
  `PATCH /api/<items>/{id}`, `DELETE /api/<items>/{id}`, plus `GET /health` returning `{"status": "ok"}`.
- Status codes: 200 read/update, 201 create (return the created object), 204 delete,
  400/422 validation, 404 not found, 500 unexpected (generic message only).
- Use parameterised queries only; never build SQL with string formatting.
- Read config from environment variables (`PORT`, `DATABASE_URL`, `CORS_ORIGIN`) and document
  them in `.env.example`.

## CORS and integration
- Allow only `CORS_ORIGIN` (default `http://localhost:5173`) with the methods you use.
- Write an `API.md` or a README section listing each endpoint, its request body and its response.
- Smoke-test every endpoint with `curl` or the test client (FastAPI `TestClient`, `supertest`
  for Express), including one invalid-input and one not-found case, and report the results.
