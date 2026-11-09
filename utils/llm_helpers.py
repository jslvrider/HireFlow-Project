"""Helpers for working with raw LLM responses."""

import json
from typing import Any


def parse_json_response(text: str) -> Any:
    """Extract and parse JSON from an LLM reply.

    Handles replies wrapped in ```json fences, bare ``` fences,
    or plain JSON with surrounding whitespace.

    Raises:
        ValueError: if the cleaned text is not valid JSON.
    """
    cleaned = text.strip()

    # Remove an opening fence line: ```json or ```
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""

    # Remove a closing fence
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM response was not valid JSON: {text[:200]!r}"
        ) from e