import re


TITLE_MAX_LENGTH = 50
TITLE_TRUNCATED_LENGTH = 47


def conversation_title_from_first_message(message: str) -> str:
    """Return a stable, LLM-free title from the first client message."""
    normalized = re.sub(r"\s+", " ", message.strip())
    if len(normalized) <= TITLE_MAX_LENGTH:
        return normalized
    return normalized[:TITLE_TRUNCATED_LENGTH] + "..."
