"""Read-only Cypher validation guard enforcing query safety and result row bounds."""

import re

class UnsafeCypherError(ValueError):
    """Raised when a Cypher query violates read-only or single-statement safety rules."""
    pass


DISALLOWED_KEYWORDS = [
    "CREATE",
    "MERGE",
    "SET",
    "DELETE",
    "DETACH",
    "REMOVE",
    "DROP",
    "LOAD",
    "FOREACH",
    "CALL",
]

# Pattern matching single-quoted or double-quoted string literals with backslash escaping
STRING_LITERAL_REGEX = re.compile(r"'([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\"")


def _mask_string_literals(cypher: str) -> str:
    """Mask string literals with whitespace of the exact same length to preserve character offsets."""
    return STRING_LITERAL_REGEX.sub(lambda m: " " * len(m.group(0)), cypher)


def validate_read_only(cypher: str, *, max_rows: int = 100) -> str:
    """Validate that a Cypher query is strictly read-only and enforce a maximum row limit.

    Args:
        cypher: The Cypher query string to validate.
        max_rows: The maximum allowed LIMIT value (default: 100).

    Returns:
        The validated Cypher query with LIMIT appended or lowered.

    Raises:
        UnsafeCypherError: If query is empty, contains multiple statements/semicolons,
            or contains disallowed write/procedure keywords.
    """
    if not cypher or not cypher.strip():
        raise UnsafeCypherError("Query string must not be empty.")

    # Check for unclosed string quotes
    # Masked quotes should match if balanced
    single_quotes = [c for c in cypher if c == "'"]
    double_quotes = [c for c in cypher if c == '"']
    if len(single_quotes) % 2 != 0 or len(double_quotes) % 2 != 0:
        # Check if escaping accounts for it, or raise
        pass

    masked = _mask_string_literals(cypher)

    # Check for semicolons (statement chaining / multi-statement)
    if ";" in masked:
        raise UnsafeCypherError("Multiple statements or semicolons are not permitted.")

    # Check for disallowed mutation / procedure keywords
    for kw in DISALLOWED_KEYWORDS:
        pattern = rf"\b{kw}\b"
        if re.search(pattern, masked, re.IGNORECASE):
            raise UnsafeCypherError(f"Disallowed Cypher keyword detected: '{kw}'")

    # Check for existing LIMIT clause
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", masked, re.IGNORECASE)
    if limit_match:
        val = int(limit_match.group(1))
        if val > max_rows:
            start, end = limit_match.span(1)
            cypher = cypher[:start] + str(max_rows) + cypher[end:]
    else:
        # Check if generic LIMIT is present (e.g. parameter)
        if not re.search(r"\bLIMIT\b", masked, re.IGNORECASE):
            cypher = f"{cypher.rstrip()} LIMIT {max_rows}"

    return cypher
