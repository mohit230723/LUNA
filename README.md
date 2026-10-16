# LUNA OS

Multi-agent graph-native fraud investigation OS built on FalkorDB.

## Running Tests

Start the live FalkorDB container:
```bash
docker compose up -d
```

Run integration tests against the live FalkorDB container:
```bash
pytest -m integration -q
```

Run all non-slow tests (offline unit tests + live integration tests):
```bash
pytest -m "not slow" -q
```

Run offline unit tests only (passes with FalkorDB stopped):
```bash
pytest -m "not integration and not slow" -q
```
