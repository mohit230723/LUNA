"""Unit tests for LLMClient protocol, OllamaLLM wrapper, and MockLLMClient."""

from unittest.mock import MagicMock
from luna.llm.client import MockLLMClient, OllamaLLM


def test_mock_llm_pattern_registration_and_response():
    """Verify MockLLMClient returns matched pattern responses and captures history."""
    mock_llm = MockLLMClient(default_response={"default": True})

    mock_llm.register_response(
        r"decompose",
        {"subtasks": [{"id": "sub_1", "capability": "link_entities"}]},
    )
    mock_llm.register_response(
        r"analyze",
        "Analysis complete.",
    )

    # 1. Matching pattern 1
    res1 = mock_llm.complete("Please decompose the investigation task.", system="You are an orchestrator.")
    assert isinstance(res1, dict)
    assert res1["subtasks"][0]["capability"] == "link_entities"

    # 2. Matching pattern 2
    res2 = mock_llm.complete("Analyze the graph slice.")
    assert res2 == "Analysis complete."

    # 3. Unmatched prompt returns default response
    res3 = mock_llm.complete("Unmatched random query.")
    assert res3 == {"default": True}

    # 4. Check call history
    assert len(mock_llm.call_history) == 3
    assert mock_llm.call_history[0]["prompt"] == "Please decompose the investigation task."
    assert mock_llm.call_history[0]["system"] == "You are an orchestrator."


def test_ollama_llm_json_parsing_and_mock_invoke():
    """Verify OllamaLLM binds json format and parses response content."""
    ollama = OllamaLLM(base_url="http://localhost:11434", model="llama3.1:8b")

    mock_chat_ollama = MagicMock()
    mock_bound_llm = MagicMock()
    mock_chat_ollama.bind.return_value = mock_bound_llm

    # Mock response with JSON string content
    mock_response = MagicMock()
    mock_response.content = '{"verdict": "suspicious", "confidence": 0.95}'
    mock_bound_llm.invoke.return_value = mock_response

    ollama._llm = mock_chat_ollama

    schema = {"type": "object", "properties": {"verdict": {"type": "string"}}}
    result = ollama.complete("Evaluate entity cust_1", json_schema=schema)

    assert isinstance(result, dict)
    assert result["verdict"] == "suspicious"
    assert result["confidence"] == 0.95

    mock_chat_ollama.bind.assert_called_once_with(format="json")
    mock_bound_llm.invoke.assert_called_once()
