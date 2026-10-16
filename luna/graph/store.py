"""GraphStore connection wrapper and execution engine for FalkorDB."""

from typing import Any, Optional
import re
import falkordb
from luna.config import settings


class GraphStore:
    """Manages multi-graph connections, queries, and lifecycle on FalkorDB.

    Security Architecture:
    Strict query parameterization ($param) is the primary protection against Cypher injection.
    The internal validation guard (_validate_query_safety) is a secondary safety net to catch
    accidental string interpolation, format placeholders, or statement chaining before transmission.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.host = host or settings.FALKORDB_HOST
        self.port = port or settings.FALKORDB_PORT
        self._client = client
        self._procedure_cache: Optional[set[str]] = None

    @property
    def client(self) -> falkordb.FalkorDB:
        """Lazily initialize FalkorDB client connection."""
        if self._client is None:
            self._client = falkordb.FalkorDB(host=self.host, port=self.port)
        return self._client

    def _validate_query_safety(self, query_str: str, params: Optional[dict[str, Any]]) -> None:
        """Enforce parameterized query safety and reject unsafe interpolation patterns."""
        if not query_str or not isinstance(query_str, str):
            raise ValueError("Query string must be a non-empty string.")

        # Reject python string formatting indicators (%s, %d, {}, {0})
        if (
            "%s" in query_str
            or "%d" in query_str
            or "%r" in query_str
            or "%f" in query_str
            or "{}" in query_str
            or re.search(r"\{[0-9]+\}", query_str)
        ):
            raise ValueError("Unsafe string formatting detected in query. Use $param syntax.")

        # Check for multiple statements / SQL-injection-style chaining
        if ";" in query_str.rstrip(";"):
            raise ValueError("Multiple statements separated by semicolon are not permitted.")

        # If parameters exist in query ($param), ensure params dictionary is provided
        param_matches = set(re.findall(r"\$([a-zA-Z0-9_]+)", query_str))
        if param_matches:
            if not params:
                raise ValueError(
                    f"Query references parameters {param_matches} but no params dictionary was provided."
                )
            missing = param_matches - set(params.keys())
            if missing:
                raise ValueError(f"Missing query parameters: {missing}")

    def select_graph(self, graph_name: str) -> Any:
        """Get graph instance for specified named graph."""
        if not graph_name or not isinstance(graph_name, str):
            raise ValueError("Graph name must be a valid non-empty string.")
        return self.client.select_graph(graph_name)

    def _parse_query_result(self, result: Any) -> list[dict[str, Any]]:
        """Parse QueryResult extracting decoded headers and node/edge/primitive properties."""
        rows: list[dict[str, Any]] = []
        if not hasattr(result, "result_set") or not result.result_set:
            return rows

        # Extract column names from header
        headers: list[str] = []
        if hasattr(result, "header") and result.header:
            for col in result.header:
                val = col[1] if (isinstance(col, (list, tuple)) and len(col) > 1) else col
                if isinstance(val, bytes):
                    headers.append(val.decode("utf-8"))
                else:
                    headers.append(str(val))

        for record in result.result_set:
            row_dict: dict[str, Any] = {}
            for idx, item in enumerate(record):
                col_name = headers[idx] if idx < len(headers) else f"col_{idx}"
                # Handle FalkorDB Node/Edge or primitive objects
                if hasattr(item, "properties"):
                    row_dict[col_name] = item.properties
                else:
                    row_dict[col_name] = item
            rows.append(row_dict)

        return rows

    def query(
        self,
        graph_name: str,
        query_str: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Execute a parameterized Cypher query and return rows as dictionaries."""
        self._validate_query_safety(query_str, params)
        graph = self.select_graph(graph_name)
        result = graph.query(query_str, params or {})
        return self._parse_query_result(result)

    def read_query(
        self,
        graph_name: str,
        query_str: str,
        params: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Execute a read-only parameterized Cypher query using FalkorDB's ro_query."""
        self._validate_query_safety(query_str, params)
        graph = self.select_graph(graph_name)
        if hasattr(graph, "ro_query"):
            result = graph.ro_query(query_str, params or {})
        else:
            result = graph.query(query_str, params or {})
        return self._parse_query_result(result)

    def delete_graph(self, graph_name: str) -> bool:
        """Delete named graph from FalkorDB."""
        try:
            graph = self.select_graph(graph_name)
            if hasattr(graph, "delete"):
                graph.delete()
                return True
            return False
        except Exception:
            return False

    def list_graphs(self) -> list[str]:
        """List all active graphs in FalkorDB instance."""
        try:
            return self.client.list_graphs()
        except Exception:
            return []

    def copy_graph(self, source_graph_name: str, target_graph_name: str) -> bool:
        """Copy a graph into another named graph."""
        try:
            graph = self.select_graph(source_graph_name)
            if hasattr(graph, "copy"):
                graph.copy(target_graph_name)
                return True
            return False
        except Exception:
            return False

    def supports_procedure(self, name: str) -> bool:
        """Check if FalkorDB instance supports a given procedure name (cached per instance)."""
        if self._procedure_cache is None:
            self._procedure_cache = set()
            try:
                # Probe procedures via CALL dbms.procedures()
                rows = self.query("domain", "CALL dbms.procedures()")
                for r in rows:
                    proc_name = r.get("name")
                    if proc_name:
                        self._procedure_cache.add(str(proc_name))
            except Exception:
                pass
        return name in self._procedure_cache

