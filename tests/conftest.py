"""Global pytest configuration and fixtures for LUNA test suite."""

import uuid
import pytest
from luna.graph.store import GraphStore


@pytest.fixture(scope="session")
def live_store():
    """Session fixture connecting to live FalkorDB instance on localhost:6379.
    
    Skips tests if FalkorDB is unreachable.
    """
    store = GraphStore(host="localhost", port=6379)
    try:
        store.client.list_graphs()
    except Exception as e:
        pytest.skip(f"FalkorDB unreachable on localhost:6379: {e}")
    return store


@pytest.fixture
def tmp_graph(live_store):
    """Yield a unique temporary graph name and delete it after test completion."""
    graph_name = f"tmp_{uuid.uuid4().hex[:8]}"
    yield graph_name
    try:
        live_store.delete_graph(graph_name)
    except Exception:
        pass
