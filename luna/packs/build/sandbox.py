"""Sandboxed filesystem workspace for Software-Build Pack with path traversal defense."""

from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Optional

MAX_FILE_SIZE_BYTES = 200 * 1024  # 200 KB cap per file


class SandboxWorkspace:
    """Sandboxed workspace providing isolated disk storage per run.

    Enforces path traversal protection and artifact sha256 integrity tracking.
    """

    def __init__(self, run_id: str, base_dir: str = "workspaces") -> None:
        self.run_id = run_id
        self.workspace_dir = Path(base_dir).resolve() / run_id
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts: list[dict[str, Any]] = []

    def _resolve_safe_path(self, component: str, rel_path: str) -> Path:
        """Resolve path ensuring it strictly resides inside the component sandbox."""
        clean_rel = rel_path.lstrip("/\\")
        target_path = (self.workspace_dir / component / clean_rel).resolve()
        component_root = (self.workspace_dir / component).resolve()

        # Strict containment check against directory traversal
        try:
            target_path.relative_to(component_root)
        except ValueError:
            raise ValueError(
                f"Path traversal attempt detected: '{rel_path}' escapes component sandbox '{component}'"
            )

        return target_path

    def write_file(self, component: str, rel_path: str, content: str) -> dict[str, Any]:
        """Write text file safely into component sandbox, enforcing size caps and calculating sha256."""
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File '{rel_path}' ({len(encoded)} bytes) exceeds the 200KB maximum size cap."
            )

        target = self._resolve_safe_path(component, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        sha256 = hashlib.sha256(encoded).hexdigest()
        norm_path = f"{component}/{rel_path.lstrip('/\\')}".replace("\\", "/")

        artifact_info = {
            "component": component,
            "path": norm_path,
            "filename": target.name,
            "size_bytes": len(encoded),
            "sha256": sha256,
        }
        self.artifacts.append(artifact_info)
        return artifact_info

    def read_file(self, component: str, rel_path: str) -> str:
        """Read text file safely from component sandbox."""
        target = self._resolve_safe_path(component, rel_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File '{rel_path}' not found in component '{component}'")
        return target.read_text(encoding="utf-8")

    def list_files(self, component: Optional[str] = None) -> list[str]:
        """List all relative file paths inside the workspace or component."""
        search_root = (self.workspace_dir / component) if component else self.workspace_dir
        if not search_root.exists():
            return []

        rel_paths: list[str] = []
        for path in search_root.rglob("*"):
            if path.is_file():
                rel = path.relative_to(self.workspace_dir).as_posix()
                rel_paths.append(rel)
        return sorted(rel_paths)

    def create_zip(self, output_path: Optional[str] = None) -> str:
        """Compress the entire workspace into a zip archive."""
        dest = output_path or str(self.workspace_dir.parent / f"{self.run_id}.zip")
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in self.workspace_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.workspace_dir).as_posix()
                    zf.write(file_path, arcname=arcname)
        return dest

    def cleanup(self) -> None:
        """Remove workspace directory and contents."""
        if self.workspace_dir.exists():
            shutil.rmtree(self.workspace_dir, ignore_errors=True)
