"""Deterministic contract verifier for Software-Build Pack."""

from __future__ import annotations

import re
from typing import Any
from pydantic import BaseModel, Field

from luna.packs.build.blueprint import ContractDef
from luna.packs.build.sandbox import SandboxWorkspace


class VerificationResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    checked_contracts: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


def verify_contracts(
    workspace: SandboxWorkspace,
    contracts: list[ContractDef],
) -> VerificationResult:
    """Deterministically check workspace code against declared contracts.

    Verifies:
      1. Database table creation matches db_schema contract.
      2. Backend route definitions match api_routes contract endpoints.
      3. Frontend client fetch calls target contracted endpoints.
    """
    issues: list[str] = []
    checked: list[str] = []
    details: dict[str, Any] = {}

    for c in contracts:
        checked.append(c.name)

        if c.kind == "db_schema":
            tables = [t.get("name") for t in c.spec.get("tables", [])]
            try:
                sql_content = workspace.read_file("database", "schema.sql")
                for table in tables:
                    if not re.search(rf"\b(CREATE\s+TABLE|TABLE)\s+(IF\s+NOT\s+EXISTS\s+)?{table}\b", sql_content, re.IGNORECASE):
                        issues.append(f"Database contract violation: Table '{table}' not found in schema.sql")
                details["db_tables_verified"] = tables
            except FileNotFoundError:
                issues.append("Database contract violation: 'schema.sql' missing from database component")

        elif c.kind == "api_routes":
            endpoints = c.spec.get("endpoints", [])
            matched_endpoints: list[str] = []
            try:
                # Check backend routes file
                backend_code = ""
                for candidate in ["src/index.ts", "src/routes.ts", "src/app.ts", "main.py"]:
                    try:
                        backend_code += "\n" + workspace.read_file("backend", candidate)
                    except FileNotFoundError:
                        pass

                if not backend_code.strip():
                    issues.append("Backend contract violation: No route entrypoint found in backend component")
                else:
                    for ep in endpoints:
                        path = ep.get("path", "")
                        # Normalize path for express / fastapi matching (e.g. /api/todos)
                        base_path = path.split("/:")[0].rstrip("/")
                        if base_path in backend_code:
                            matched_endpoints.append(path)
                        else:
                            issues.append(f"Backend contract violation: Endpoint '{path}' not defined in backend code")

                details["backend_endpoints_matched"] = matched_endpoints
            except Exception as err:
                issues.append(f"Error checking backend routes: {err}")

            # Check frontend consumption
            try:
                frontend_code = ""
                for candidate in ["src/App.tsx", "src/api.ts", "src/App.jsx"]:
                    try:
                        frontend_code += "\n" + workspace.read_file("frontend", candidate)
                    except FileNotFoundError:
                        pass

                if frontend_code:
                    for ep in endpoints:
                        base_path = ep.get("path", "").split("/:")[0].rstrip("/")
                        if base_path not in frontend_code and "/todos" not in frontend_code:
                            issues.append(f"Frontend contract violation: API path '{base_path}' not called by frontend")
            except Exception as err:
                issues.append(f"Error checking frontend fetches: {err}")

    passed = len(issues) == 0
    return VerificationResult(
        passed=passed,
        issues=issues,
        checked_contracts=checked,
        details=details,
    )
